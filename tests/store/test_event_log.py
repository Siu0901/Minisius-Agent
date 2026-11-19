"""append-only 이벤트 로그 (docs/ARCHITECTURE.md 5.6절). DB 는 tmp_path 안에만 만든다."""

import asyncio
import sqlite3
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from minisius.core.actions import Action, ActionKind
from minisius.core.events import (
    ErrorOccurred,
    EventPayload,
    LLMRequested,
    LLMResponded,
    SessionStarted,
    ToolCallFinished,
    ToolCallStarted,
    TurnFinished,
    UserMessage,
    messages_from_events,
    usage_from_events,
)
from minisius.core.messages import Message, OpaquePart, TextPart, ToolCallPart
from minisius.errors import StoreError
from minisius.store import db
from minisius.store.event_log import EventLog

ASSISTANT = Message(
    role="assistant",
    parts=[
        OpaquePart(provider="anthropic", data={"type": "thinking", "signature": "sig"}),
        TextPart(text="보겠습니다"),
        ToolCallPart(id="a", name="list_dir", arguments={"path": ".", "depth": 2}),
    ],
)

ONE_OF_EACH: list[EventPayload] = [
    SessionStarted(workdir="/작업/폴더", provider="anthropic", model="m", interface="cli"),
    UserMessage(message=Message.user("요약해 줘")),
    LLMRequested(model="m", message_count=1),
    LLMResponded(
        message=ASSISTANT,
        stop_reason="tool_use",
        input_tokens=1200,
        output_tokens=80,
        cache_read_tokens=3,
        cache_write_tokens=4,
        cost_usd=0.0123,
        duration_ms=900,
    ),
    ToolCallStarted(
        tool_call_id="a",
        name="list_dir",
        arguments={"path": ".", "depth": 2, "nested": {"k": [1, None, "v"]}},
        actions=(Action(kind=ActionKind.READ, target="."),),
    ),
    ToolCallFinished(tool_call_id="a", content="a.md\nb.md", is_error=False, duration_ms=3),
    ErrorOccurred(kind="RetryableProviderError", message="429", fatal=False),
    TurnFinished(reason="completed"),
]


@pytest.fixture
def db_file(tmp_path: Path) -> Path:
    return tmp_path / "minisius.db"


@pytest.fixture
async def log(db_file: Path) -> AsyncIterator[EventLog]:
    async with await EventLog.open(db_file) as opened:
        yield opened


# --- 번호와 시각 ---


async def test_seq_starts_at_one_and_increases(log: EventLog) -> None:
    events = [await log.append("s", TurnFinished(reason="completed")) for _ in range(3)]
    assert [event.seq for event in events] == [1, 2, 3]


async def test_each_session_has_its_own_numbering(log: EventLog) -> None:
    await log.append("s1", TurnFinished(reason="completed"))
    await log.append("s1", TurnFinished(reason="completed"))
    other = await log.append("s2", TurnFinished(reason="cancelled"))
    assert other.seq == 1
    assert [event.seq for event in await log.read("s1")] == [1, 2]
    assert [event.seq for event in await log.read("s2")] == [1]


async def test_log_assigns_the_current_time_in_utc(log: EventLog) -> None:
    event = await log.append("s", TurnFinished(reason="completed"))
    assert event.ts.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - event.ts) < timedelta(seconds=5)


async def test_concurrent_appends_get_distinct_numbers(log: EventLog) -> None:
    await asyncio.gather(*(log.append("s", TurnFinished(reason="completed")) for _ in range(30)))
    assert [event.seq for event in await log.read("s")] == list(range(1, 31))


# --- 왕복 ---


async def test_every_event_type_survives_a_round_trip(log: EventLog) -> None:
    appended = [await log.append("s", payload) for payload in ONE_OF_EACH]
    read = await log.read("s")
    assert read == appended
    assert [event.payload for event in read] == ONE_OF_EACH
    assert [event.type for event in read] == [
        "session_started",
        "user_message",
        "llm_request",
        "llm_response",
        "tool_call_started",
        "tool_call_finished",
        "error",
        "turn_finished",
    ]


async def test_unknown_session_reads_as_empty(log: EventLog) -> None:
    assert await log.read("없는-세션") == []


async def test_events_persist_after_reopening(db_file: Path) -> None:
    async with await EventLog.open(db_file) as first:
        appended = [await first.append("s", payload) for payload in ONE_OF_EACH]
    async with await EventLog.open(db_file) as second:
        assert await second.read("s") == appended
        assert (await second.append("s", TurnFinished(reason="completed"))).seq == 9


async def test_conversation_and_usage_can_be_rebuilt_from_the_log(db_file: Path) -> None:
    async with await EventLog.open(db_file) as first:
        for payload in ONE_OF_EACH:
            await first.append("s", payload)
    async with await EventLog.open(db_file) as second:
        events = await second.read("s")

    messages = messages_from_events(events)
    assert [message.role for message in messages] == ["user", "assistant", "tool"]
    assert messages[1] == ASSISTANT
    usage = usage_from_events(events)
    assert (usage.input_tokens, usage.output_tokens, usage.cost_usd) == (1200, 80, 0.0123)


# --- 두 연결 ---


async def test_two_connections_never_reuse_a_number(db_file: Path) -> None:
    async with await EventLog.open(db_file) as cli, await EventLog.open(db_file) as gateway:

        async def write(log: EventLog) -> None:
            for _ in range(25):
                await log.append("s", TurnFinished(reason="completed"))

        await asyncio.gather(write(cli), write(gateway))
        assert [event.seq for event in await cli.read("s")] == list(range(1, 51))


async def test_one_connection_sees_what_the_other_wrote(db_file: Path) -> None:
    async with await EventLog.open(db_file) as cli, await EventLog.open(db_file) as gateway:
        written = await cli.append("s", TurnFinished(reason="completed"))
        assert await gateway.read("s") == [written]


# --- 추가만 가능 ---


async def test_database_rejects_update_and_delete(db_file: Path) -> None:
    async with await EventLog.open(db_file) as log:
        written = await log.append("s", TurnFinished(reason="completed"))

    raw = sqlite3.connect(db_file)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("UPDATE events SET payload = '{}'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("DELETE FROM events")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            raw.execute("INSERT OR REPLACE INTO events VALUES ('s', 1, 't', 'x', '{}')")
    finally:
        raw.close()

    async with await EventLog.open(db_file) as log:
        assert await log.read("s") == [written]


def test_event_log_has_no_way_to_change_history() -> None:
    public = {name for name in vars(EventLog) if not name.startswith("_")}
    assert public == {"open", "close", "append", "read"}


# --- DB 설정 ---


async def test_database_is_opened_in_wal_mode_with_durable_writes(db_file: Path) -> None:
    conn = db.connect(db_file)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)
    finally:
        conn.close()


async def test_missing_parent_folder_is_created(tmp_path: Path) -> None:
    async with await EventLog.open(tmp_path / "새" / "폴더" / "minisius.db") as log:
        assert (await log.append("s", TurnFinished(reason="completed"))).seq == 1


# --- 오류 ---


async def test_unopenable_path_raises_store_error(tmp_path: Path) -> None:
    with pytest.raises(StoreError, match="열지 못했습니다"):
        await EventLog.open(tmp_path)  # 폴더는 DB 파일이 될 수 없다


@pytest.fixture
def not_a_database(db_file: Path) -> Path:
    db_file.write_bytes(b"this is not sqlite " * 100)
    return db_file


async def test_file_that_is_not_a_database_raises_store_error(not_a_database: Path) -> None:
    with pytest.raises(StoreError):
        await EventLog.open(not_a_database)


async def test_database_from_a_newer_version_is_refused(db_file: Path) -> None:
    db.connect(db_file).close()
    raw = sqlite3.connect(db_file)
    raw.execute(f"PRAGMA user_version={len(db.MIGRATIONS) + 1}")
    raw.close()
    with pytest.raises(StoreError, match="업데이트"):
        await EventLog.open(db_file)


async def test_value_that_cannot_be_stored_raises_store_error_and_log_keeps_working(
    log: EventLog,
) -> None:
    broken = "sk-do-not-print\udcff"  # 짝 없는 서로게이트. 잘못 디코딩한 명령 출력에서 나온다
    with pytest.raises(StoreError) as caught:
        await log.append("s", ToolCallFinished(tool_call_id="a", content=broken, duration_ms=1))
    assert "sk-do-not-print" not in str(caught.value)
    with pytest.raises(StoreError):
        await log.append("s\udcff", TurnFinished(reason="completed"))
    assert (await log.append("s", TurnFinished(reason="completed"))).seq == 1


def test_first_open_by_two_processes_at_once_succeeds(tmp_path: Path) -> None:
    script = (
        "import sys; from pathlib import Path; from minisius.store import db;"
        " db.connect(Path(sys.argv[1])).close()"
    )
    for round_ in range(10):
        target = str(tmp_path / f"{round_}.db")
        procs = [
            subprocess.Popen([sys.executable, "-c", script, target], stderr=subprocess.PIPE)
            for _ in range(4)
        ]
        failures = [p.communicate()[1].decode() for p in procs if p.wait() != 0]
        assert failures == []


def test_migration_script_with_unfinished_statement_is_refused() -> None:
    with pytest.raises(StoreError, match="끝나지"):
        db._statements("CREATE TABLE a (x);\nCREATE TABLE b (y)")


@pytest.mark.parametrize("body", ["[]", "null", "{bad"])
async def test_payload_that_is_not_an_object_raises_store_error(db_file: Path, body: str) -> None:
    db.connect(db_file).close()
    raw = sqlite3.connect(db_file)
    raw.execute(
        "INSERT INTO events VALUES ('s', 1, '2026-01-01T00:00:00+00:00', 'error', ?)", (body,)
    )
    raw.commit()
    raw.close()
    async with await EventLog.open(db_file) as log:
        with pytest.raises(StoreError):
            await log.read("s")


async def test_using_a_closed_log_raises_store_error(db_file: Path) -> None:
    log = await EventLog.open(db_file)
    await log.close()
    with pytest.raises(StoreError):
        await log.append("s", TurnFinished(reason="completed"))
    with pytest.raises(StoreError):
        await log.read("s")


async def test_unreadable_event_raises_store_error_without_leaking_payload(db_file: Path) -> None:
    async with await EventLog.open(db_file) as log:
        await log.append("s", TurnFinished(reason="completed"))
    raw = sqlite3.connect(db_file)
    raw.execute(
        "INSERT INTO events VALUES ('s', 2, '2026-01-01T00:00:00+00:00', 'from_the_future',"
        ' \'{"secret": "sk-do-not-print"}\')'
    )
    raw.commit()
    raw.close()

    async with await EventLog.open(db_file) as log:
        with pytest.raises(StoreError) as caught:
            await log.read("s")
    assert "2번" in str(caught.value)
    assert "from_the_future" in str(caught.value)
    assert "sk-do-not-print" not in str(caught.value)
    assert caught.value.__cause__ is None
