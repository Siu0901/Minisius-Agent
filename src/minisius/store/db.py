"""SQLite 연결과 스키마.

CLI 와 게이트웨이가 같은 파일을 동시에 열 수 있어서 WAL 모드로 연다.
스키마 버전은 SQLite 의 user_version 에 둔다.

원본은 docs/ARCHITECTURE.md 5.6절.
"""

import sqlite3
import time
from pathlib import Path

from minisius.errors import StoreError

BUSY_TIMEOUT_SECONDS = 5.0

# 순서대로 적용한다. 이미 배포한 항목은 고치지 않고 뒤에 새 항목을 더한다.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE events (
        session_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        ts TEXT NOT NULL,
        type TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (session_id, seq)
    );
    CREATE TRIGGER events_no_replace BEFORE INSERT ON events
    WHEN EXISTS (SELECT 1 FROM events WHERE session_id = NEW.session_id AND seq = NEW.seq)
    BEGIN
        SELECT RAISE(ABORT, 'events is append-only');
    END;
    CREATE TRIGGER events_no_update BEFORE UPDATE ON events
    BEGIN
        SELECT RAISE(ABORT, 'events is append-only');
    END;
    CREATE TRIGGER events_no_delete BEFORE DELETE ON events
    BEGIN
        SELECT RAISE(ABORT, 'events is append-only');
    END;
    """,
)


def connect(db_file: Path) -> sqlite3.Connection:
    """DB 를 열고 스키마를 최신으로 맞춘다. 파일이 없으면 만든다."""
    try:
        db_file.parent.mkdir(parents=True, exist_ok=True)
        # 트랜잭션을 직접 여닫으려고 autocommit 으로 연다.
        # EventLog 가 작업 스레드에서 쓰므로 스레드 검사를 끈다. 동시 접근은 EventLog 가 막는다.
        conn = sqlite3.connect(
            db_file,
            timeout=BUSY_TIMEOUT_SECONDS,
            isolation_level=None,
            check_same_thread=False,
        )
    except (OSError, sqlite3.Error) as exc:
        raise StoreError(f"DB 를 열지 못했습니다: {db_file} ({exc})") from exc

    try:
        _enable_wal(conn)
        # 기록했다고 답한 이벤트는 전원이 나가도 남아야 한다.
        conn.execute("PRAGMA synchronous=FULL")
        _migrate(conn)
    except sqlite3.Error as exc:
        conn.close()
        raise StoreError(f"DB 를 준비하지 못했습니다: {db_file} ({exc})") from exc
    except StoreError:
        conn.close()
        raise
    return conn


def _enable_wal(conn: sqlite3.Connection) -> None:
    """WAL 모드로 바꾼다.

    저널 모드 전환은 busy timeout 을 기다리지 않고 바로 실패한다. 두 프로세스가 새 DB 를 동시에
    처음 열 때 한쪽이 여기서 떨어지지 않도록 직접 기다렸다가 다시 시도한다.
    """
    deadline = time.monotonic() + BUSY_TIMEOUT_SECONDS
    while True:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def _migrate(conn: sqlite3.Connection) -> None:
    # 두 프로세스가 동시에 처음 열어도 한쪽만 적용하도록 쓰기 잠금을 먼저 잡고 버전을 읽는다.
    conn.execute("BEGIN IMMEDIATE")
    try:
        version: int = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > len(MIGRATIONS):
            raise StoreError(
                f"DB 가 이 버전의 minisius 보다 새 버전입니다 "
                f"(DB {version}, 프로그램 {len(MIGRATIONS)}). minisius 를 업데이트하세요."
            )
        for number, script in enumerate(MIGRATIONS[version:], start=version + 1):
            for statement in _statements(script):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version={number}")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _statements(script: str) -> list[str]:
    """스크립트를 문장으로 나눈다.

    executescript() 는 진행 중인 트랜잭션을 먼저 커밋해 버려서 쓰지 않는다.
    트리거 본문 안의 세미콜론에서 자르지 않도록 sqlite3.complete_statement 로 끝을 판단한다.
    """
    statements: list[str] = []
    current = ""
    for line in script.splitlines():
        current += line + "\n"
        if sqlite3.complete_statement(current):
            statements.append(current.strip())
            current = ""
    if current.strip():
        raise StoreError("마이그레이션 스크립트의 마지막 문장이 끝나지 않았습니다.")
    return statements
