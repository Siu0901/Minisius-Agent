"""append-only 이벤트 로그.

쓰기는 append() 하나뿐이다. 고치거나 지우는 기능은 없고, DB 의 트리거도 그것을 거절한다.

원본은 docs/ARCHITECTURE.md 5.6절.
"""

import asyncio
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import TypeAdapter

from minisius.core.events import Event, EventPayload
from minisius.errors import StoreError
from minisius.store import db

_PAYLOAD: TypeAdapter[EventPayload] = TypeAdapter(EventPayload)


class EventLog:
    """SQLite 파일 하나에 대한 이벤트 로그.

    sqlite3 는 블로킹이라 모든 DB 작업을 작업 스레드에서 한다.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    @classmethod
    async def open(cls, db_file: Path) -> Self:
        return cls(await asyncio.to_thread(db.connect, db_file))

    async def close(self) -> None:
        await asyncio.to_thread(self._close)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def append(self, session_id: str, payload: EventPayload) -> Event:
        """이벤트를 기록하고, 번호와 시각이 매겨진 Event 를 돌려준다.

        돌아왔다면 디스크에 남은 것이다.
        """
        return await asyncio.to_thread(self._append, session_id, payload)

    async def read(self, session_id: str) -> list[Event]:
        """세션의 이벤트를 번호 순서로 읽는다. 없는 세션이면 빈 목록."""
        return await asyncio.to_thread(self._read, session_id)

    def _close(self) -> None:
        with self._lock:
            self._conn.close()

    def _append(self, session_id: str, payload: EventPayload) -> Event:
        with self._lock:
            try:
                body = payload.model_dump_json(exclude={"type"})
                # 다른 프로세스와 번호가 겹치지 않도록 번호를 읽기 전에 쓰기 잠금을 잡는다.
                self._conn.execute("BEGIN IMMEDIATE")
                try:
                    # 잠금을 잡은 뒤에 찍어야 시각의 순서가 번호의 순서와 같다.
                    ts = datetime.now(UTC)
                    row = self._conn.execute(
                        "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    seq: int = row[0]
                    self._conn.execute(
                        "INSERT INTO events (session_id, seq, ts, type, payload)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (session_id, seq, ts.isoformat(), payload.type, body),
                    )
                    self._conn.execute("COMMIT")
                except BaseException:
                    self._conn.execute("ROLLBACK")
                    raise
            except sqlite3.Error as exc:
                raise StoreError(f"이벤트를 기록하지 못했습니다 ({exc})") from exc
            except ValueError as exc:
                raise StoreError(
                    f"이벤트를 기록하지 못했습니다: {payload.type} 에 저장할 수 없는 값이 "
                    f"있습니다 ({type(exc).__name__})"
                ) from None
        return Event(session_id=session_id, seq=seq, ts=ts, payload=payload)

    def _read(self, session_id: str) -> list[Event]:
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT seq, ts, type, payload FROM events WHERE session_id = ? ORDER BY seq",
                    (session_id,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise StoreError(f"이벤트를 읽지 못했습니다 ({exc})") from exc

        events: list[Event] = []
        for seq, ts, type_, body in rows:
            try:
                payload = _PAYLOAD.validate_python({**json.loads(body), "type": type_})
                events.append(
                    Event(
                        session_id=session_id,
                        seq=seq,
                        ts=datetime.fromisoformat(ts),
                        payload=payload,
                    )
                )
            except (ValueError, TypeError):
                # 원인을 붙이지 않는다. pydantic 오류에는 payload 내용이 들어 있다.
                raise StoreError(
                    f"이벤트를 해석하지 못했습니다: 세션 {session_id} 의 {seq}번 ({type_}). "
                    f"더 새 버전의 minisius 가 쓴 이벤트일 수 있습니다."
                ) from None
        return events
