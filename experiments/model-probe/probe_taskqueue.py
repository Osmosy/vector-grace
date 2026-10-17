"""taskqueue.py — очередь задач на SQLite (только стандартная библиотека).

Постановка задач с приоритетом и отложенным стартом, атомарный съём в работу,
повторы с экспоненциальной задержкой, лизинг для воскрешения задач умерших
воркеров, статистика по состояниям. Безопасна для нескольких потоков одного
процесса и для нескольких процессов на одном файле БД.

    from taskqueue import TaskQueue

    q = TaskQueue("tasks.db")
    q.enqueue("send_email", {"to": "a@b.c"}, priority=10, max_attempts=5)

    task = q.claim(worker="w1")              # None, если работы нет
    if task is not None:
        try:
            do_work(task.payload)
        except Exception as exc:
            q.fail(task.id, exc)             # pending с задержкой либо failed
        else:
            q.complete(task.id, {"ok": True})

    q.reap_expired()                         # вернуть зависшие задачи
    print(q.stats())
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Sequence

__all__ = [
    "TaskQueue", "Task", "TaskQueueError", "TaskNotFound",
    "PENDING", "RUNNING", "DONE", "FAILED", "STATES",
]

PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
STATES = (PENDING, RUNNING, DONE, FAILED)
TERMINAL_STATES = (DONE, FAILED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT    PRIMARY KEY,
    name          TEXT    NOT NULL,
    payload       TEXT,
    state         TEXT    NOT NULL DEFAULT 'pending'
                          CHECK (state IN ('pending', 'running', 'done', 'failed')),
    priority      INTEGER NOT NULL DEFAULT 0,
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 5,
    run_at        REAL    NOT NULL,
    lease_until   REAL,
    worker        TEXT,
    last_error    TEXT,
    result        TEXT,
    created_at    REAL    NOT NULL,
    updated_at    REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_tasks_ready ON tasks (state, run_at, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS ix_tasks_lease ON tasks (state, lease_until);
CREATE INDEX IF NOT EXISTS ix_tasks_name  ON tasks (name, state);
"""


class TaskQueueError(Exception):
    """Базовая ошибка очереди."""


class TaskNotFound(TaskQueueError):
    """Задача с таким id отсутствует."""


def _dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(raw: Optional[str]) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


@dataclass(frozen=True)
class Task:
    """Снимок строки таблицы tasks."""

    id: str
    name: str
    payload: Any
    state: str
    priority: int
    attempts: int
    max_attempts: int
    run_at: float
    lease_until: Optional[float]
    worker: Optional[str]
    last_error: Optional[str]
    result: Any
    created_at: float
    updated_at: float

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(
            id=row["id"],
            name=row["name"],
            payload=_loads(row["payload"]),
            state=row["state"],
            priority=row["priority"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            run_at=row["run_at"],
            lease_until=row["lease_until"],
            worker=row["worker"],
            last_error=row["last_error"],
            result=_loads(row["result"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @property
    def attempts_left(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    def due_in(self, now: Optional[float] = None) -> float:
        """Секунд до готовности (<= 0 — уже готова)."""
        return self.run_at - (time.time() if now is None else now)


class TaskQueue:
    """Очередь задач в одном файле SQLite.

    Одно соединение на экземпляр + RLock: потокобезопасно внутри процесса.
    Между процессами атомарность даёт BEGIN IMMEDIATE (каждый процесс создаёт
    свой TaskQueue на том же пути).
    """

    def __init__(
        self,
        path: str = "tasks.db",
        *,
        default_max_attempts: int = 5,
        default_lease: float = 300.0,
        backoff_initial: float = 1.0,
        backoff_factor: float = 2.0,
        backoff_max: float = 3600.0,
        backoff_jitter: float = 0.1,
        timeout: float = 30.0,
        poll_interval: float = 0.25,
    ) -> None:
        self.path = str(path)
        self.default_max_attempts = int(default_max_attempts)
        self.default_lease = float(default_lease)
        self.backoff_initial = float(backoff_initial)
        self.backoff_factor = float(backoff_factor)
        self.backoff_max = float(backoff_max)
        self.backoff_jitter = float(backoff_jitter)
        self.timeout = float(timeout)
        self.poll_interval = float(poll_interval)
        self._lock = threading.RLock()
        self._closed = False
        self._conn = sqlite3.connect(
            self.path, timeout=self.timeout, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._configure()

    # ------------------------------------------------------------------ инфраструктура

    def _configure(self) -> None:
        self._conn.execute("PRAGMA busy_timeout = %d" % int(self.timeout * 1000))
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
                self._conn.execute("PRAGMA synchronous = NORMAL")
            except sqlite3.DatabaseError:
                pass
        self._conn.executescript(_SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Транзакция с немедленной блокировкой записи (атомарность между процессами)."""
        with self._lock:
            if self._closed:
                raise TaskQueueError("очередь закрыта")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __enter__(self) -> "TaskQueue":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ постановка

    def enqueue(
        self,
        name: str,
        payload: Any = None,
        *,
        priority: int = 0,
        max_attempts: Optional[int] = None,
        delay: float = 0.0,
        run_at: Optional[float] = None,
        task_id: Optional[str] = None,
        replace: bool = False,
    ) -> Task:
        """Поставить задачу и вернуть её снимок.

        delay — задержка в секундах, run_at — абсолютное время (перебивает delay),
        task_id — свой id, replace — перезаписать задачу с тем же id (идемпотентно).
        """
        if not name:
            raise ValueError("name не может быть пустым")
        now = time.time()
        when = float(run_at) if run_at is not None else now + max(0.0, float(delay))
        tid = task_id or uuid.uuid4().hex
        max_att = self.default_max_attempts if max_attempts is None else int(max_attempts)
        if max_att < 1:
            raise ValueError("max_attempts должен быть >= 1")
        sql = (
            "INSERT OR REPLACE INTO tasks (id, name, payload, state, priority, attempts,"
            " max_attempts, run_at, lease_until, worker, last_error, result, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, NULL, NULL, NULL, ?, ?)"
        )
        if not replace:
            sql = sql.replace("INSERT OR REPLACE", "INSERT")
        try:
            with self._tx() as conn:
                conn.execute(
                    sql, (tid, name, _dumps(payload), PENDING, int(priority), max_att, when, now, now)
                )
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise TaskQueueError(f"задача {tid!r} уже существует") from exc
        return Task._from_row(row)

    def enqueue_many(self, items: Iterable[Any], **kwargs: Any) -> List[Task]:
        """items: (name, payload) или (name, payload, {доп. kwargs для enqueue})."""
        out: List[Task] = []
        for item in items:
            if isinstance(item, (str, bytes)):
                name, payload, extra = item, None, {}
            else:
                parts = list(item)
                name = parts[0]
                payload = parts[1] if len(parts) > 1 else None
                extra = dict(parts[2]) if len(parts) > 2 else {}
            merged = dict(kwargs)
            merged.update(extra)
            out.append(self.enqueue(name, payload, **merged))
        return out

    # ------------------------------------------------------------------ съём в работу

    def claim(
        self,
        worker: Optional[str] = None,
        *,
        lease: Optional[float] = None,
        timeout: float = 0.0,
        now: Optional[float] = None,
    ) -> Optional[Task]:
        """Атомарно снять следующую готовую задачу.

        Порядок: priority DESC, затем run_at, затем created_at (FIFO внутри приоритета).
        attempts++ и state -> running происходят в момент съёма.
        timeout > 0 — ждать появления задачи до timeout секунд.
        """
        worker = worker or f"pid{os.getpid()}-t{threading.get_ident()}"
        deadline = time.time() + max(0.0, float(timeout))
        while True:
            ts = time.time() if now is None else now
            lease_until = ts + (self.default_lease if lease is None else float(lease))
            with self._tx() as conn:
                row = conn.execute(
                    "SELECT id FROM tasks WHERE state = ? AND run_at <= ?"
                    " ORDER BY priority DESC, run_at ASC, created_at ASC LIMIT 1",
                    (PENDING, ts),
                ).fetchone()
                if row is not None:
                    tid = row["id"]
                    cur = conn.execute(
                        "UPDATE tasks SET state = ?, attempts = attempts + 1, worker = ?,"
                        " lease_until = ?, updated_at = ? WHERE id = ? AND state = ?",
                        (RUNNING, worker, lease_until, ts, tid, PENDING),
                    )
                    if cur.rowcount == 1:
                        full = conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone()
                        return Task._from_row(full)
            if time.time() >= deadline:
                return None
            time.sleep(min(self.poll_interval, max(0.0, deadline - time.time())))

    # ------------------------------------------------------------------ завершение

    def complete(self, task_id: str, result: Any = None) -> Task:
        """running -> done с записью результата."""
        now = time.time()
        with self._tx() as conn:
            if conn.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
                raise TaskNotFound(task_id)
            conn.execute(
                "UPDATE tasks SET state = ?, result = ?, last_error = NULL, lease_until = NULL,"
                " worker = NULL, updated_at = ? WHERE id = ?",
                (DONE, _dumps(result), now, task_id),
            )
            full = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task._from_row(full)

    def fail(
        self,
        task_id: str,
        error: Any = "",
        *,
        retry_delay: Optional[float] = None,
        now: Optional[float] = None,
    ) -> Task:
        """Отметить попытку неудачной.

        Попытки исчерпаны -> failed. Иначе pending с задержкой backoff(attempts)
        либо с явной retry_delay. Терминальные задачи не меняются.
        """
        now = time.time() if now is None else now
        if isinstance(error, BaseException):
            message = f"{type(error).__name__}: {error}\n{traceback.format_exc()}"
        elif isinstance(error, str):
            message = error
        else:
            message = f"{type(error).__name__}: {error}"
        message = message[:4000]
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            if row["state"] in TERMINAL_STATES:
                return Task._from_row(row)
            attempts = int(row["attempts"])
            if attempts >= int(row["max_attempts"]):
                state, run_at = FAILED, now
            else:
                wait = self.backoff(attempts) if retry_delay is None else max(0.0, float(retry_delay))
                state, run_at = PENDING, now + wait
            conn.execute(
                "UPDATE tasks SET state = ?, run_at = ?, lease_until = NULL, worker = NULL,"
                " last_error = ?, updated_at = ? WHERE id = ?",
                (state, run_at, message, now, task_id),
            )
            full = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task._from_row(full)

    def backoff(self, attempts: int) -> float:
        """Задержка повтора: backoff_initial * factor^(attempts-1), потолок backoff_max, +/- джиттер."""
        attempts = max(1, int(attempts))
        delay = min(self.backoff_initial * (self.backoff_factor ** (attempts - 1)), self.backoff_max)
        return delay * (1.0 + random.uniform(0.0, self.backoff_jitter) if self.backoff_jitter > 0 else 1.0)

    # ------------------------------------------------------------------ служебное

    def touch(self, task_id: str, *, lease: Optional[float] = None,
              now: Optional[float] = None) -> bool:
        """Продлить лизинг работающей задачи (heartbeat). False — задача не running."""
        now = time.time() if now is None else now
        lease_until = now + (self.default_lease if lease is None else float(lease))
        with self._tx() as conn:
            cur = conn.execute(
                "UPDATE tasks SET lease_until = ?, updated_at = ? WHERE id = ? AND state = ?",
                (lease_until, now, task_id, RUNNING),
            )
        return cur.rowcount == 1

    def reap_expired(self, *, now: Optional[float] = None,
                     limit: Optional[int] = None) -> List[str]:
        """Вернуть в очередь задачи, чей воркер замолчал (lease_until истёк).

        Попытка уже засчитана при съёме, поэтому задача уходит на повтор, а если
        попытки исчерпаны — сразу в failed. Возвращает список затронутых id.
        """
        now = time.time() if now is None else now
        sql = ("SELECT id, attempts, max_attempts FROM tasks WHERE state = ?"
               " AND lease_until IS NOT NULL AND lease_until <= ? ORDER BY lease_until ASC")
        params: Sequence[Any] = (RUNNING, now)
        if limit is not None:
            sql += " LIMIT ?"
            params = (RUNNING, now, int(limit))
        reaped: List[str] = []
        with self._tx() as conn:
            for row in conn.execute(sql, params).fetchall():
                tid = row["id"]
                attempts = int(row["attempts"])
                if attempts >= int(row["max_attempts"]):
                    state, run_at = FAILED, now
                else:
                    state, run_at = PENDING, now + self.backoff(attempts)
                conn.execute(
                    "UPDATE tasks SET state = ?, run_at = ?, lease_until = NULL, worker = NULL,"
                    " last_error = COALESCE(last_error, 'lease expired'), updated_at = ?"
                    " WHERE id = ? AND state = ?",
                    (state, run_at, now, tid, RUNNING),
                )
                reaped.append(tid)
        return reaped

    def requeue(self, task_id: str, *, reset_attempts: bool = False, delay: float = 0.0,
                now: Optional[float] = None) -> Task:
        """Принудительно вернуть задачу в pending (в том числе из failed/done)."""
        now = time.time() if now is None else now
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            conn.execute(
                "UPDATE tasks SET state = ?, attempts = ?, run_at = ?, lease_until = NULL,"
                " worker = NULL, updated_at = ? WHERE id = ?",
                (PENDING, 0 if reset_attempts else int(row["attempts"]),
                 now + max(0.0, float(delay)), now, task_id),
            )
            full = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task._from_row(full)

    def requeue_all_failed(self, *, reset_attempts: bool = True, delay: float = 0.0) -> int:
        """Массово вернуть упавшие задачи в очередь. Возвращает количество."""
        now = time.time()
        run_at = now + max(0.0, float(delay))
        reset = ", attempts = 0" if reset_attempts else ""
        with self._tx() as conn:
            count = int(conn.execute("SELECT COUNT(*) FROM tasks WHERE state = ?",
                                     (FAILED,)).fetchone()[0])
            if count:
                conn.execute(
                    f"UPDATE tasks SET state = ?, run_at = ?{reset}, lease_until = NULL,"
                    " worker = NULL, updated_at = ? WHERE state = ?",
                    (PENDING, run_at, now, FAILED),
                )
        return count

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task._from_row(row) if row else None

    def list_tasks(self, *, state: Optional[str] = None, name: Optional[str] = None,
                   limit: int = 100) -> List[Task]:
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []
        if state is not None:
            sql += " AND state = ?"
            params.append(state)
        if name is not None:
            sql += " AND name = ?"
            params.append(name)
        sql += " ORDER BY priority DESC, run_at ASC, created_at ASC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [Task._from_row(r) for r in rows]

    def purge(self, *, states: Sequence[str] = (DONE,), older_than: float = 0.0,
              now: Optional[float] = None) -> int:
        """Удалить завершённые задачи старше older_than секунд, вернуть число удалённых."""
        states = tuple(states) or TERMINAL_STATES
        cutoff = (time.time() if now is None else now) - max(0.0, float(older_than))
        placeholders = ", ".join("?" for _ in states)
        with self._tx() as conn:
            cur = conn.execute(
                f"DELETE FROM tasks WHERE state IN ({placeholders}) AND updated_at <= ?",
                (*states, cutoff),
            )
        return cur.rowcount

    # ------------------------------------------------------------------ статистика

    def stats(self, *, now: Optional[float] = None) -> Dict[str, Any]:
        """Счётчики по состояниям плюс готовые к работе, ближайший запуск и пр."""
        now = time.time() if now is None else now
        with self._lock:
            counts = {s: 0 for s in STATES}
            for row in self._conn.execute(
                "SELECT state, COUNT(*) AS n FROM tasks GROUP BY state"
            ).fetchall():
                if row["state"] in counts:
                    counts[row["state"]] = int(row["n"])
            due = int(self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE state = ? AND run_at <= ?",
                (PENDING, now)).fetchone()[0])
            next_run_at = self._conn.execute(
                "SELECT MIN(run_at) FROM tasks WHERE state = ? AND run_at > ?",
                (PENDING, now)).fetchone()[0]
            expired = int(self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE state = ? AND lease_until IS NOT NULL"
                " AND lease_until <= ?", (RUNNING, now)).fetchone()[0])
            attempts_total = int(self._conn.execute(
                "SELECT COALESCE(SUM(attempts), 0) FROM tasks").fetchone()[0])
            oldest_pending = self._conn.execute(
                "SELECT MIN(created_at) FROM tasks WHERE state = ?", (PENDING,)).fetchone()[0]
        out: Dict[str, Any] = dict(counts)
        out.update(
            total=sum(counts.values()),
            due=due,
            next_run_at=next_run_at,
            next_run_in=None if next_run_at is None else max(0.0, next_run_at - now),
            running_expired=expired,
            attempts_total=attempts_total,
            oldest_pending_age=None if oldest_pending is None else now - oldest_pending,
            terminal=counts[DONE] + counts[FAILED],
        )
        return out

    def size(self, state: str = PENDING) -> int:
        with self._lock:
            return int(self._conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE state = ?", (state,)).fetchone()[0])

    # ------------------------------------------------------------------ воркер-хелперы

    def process_one(self, handler: Callable[[Task], Any], *, worker: Optional[str] = None,
                    lease: Optional[float] = None, timeout: float = 0.0,
                    retry_delay: Optional[float] = None) -> Optional[Task]:
        """Снять задачу, выполнить handler(task), зафиксировать done/failed.

        Возвращает итоговый снимок либо None, если работы не нашлось.
        """
        task = self.claim(worker=worker, lease=lease, timeout=timeout)
        if task is None:
            return None
        try:
            result = handler(task)
        except BaseException as exc:  # фиксируем любую ошибку задачи, воркер не падает
            return self.fail(task.id, exc, retry_delay=retry_delay)
        return self.complete(task.id, result)

    def drain(self, handler: Callable[[Task], Any], *, limit: Optional[int] = None,
              worker: Optional[str] = None, lease: Optional[float] = None) -> int:
        """Выполнять готовые задачи до пустоты (или до limit штук), вернуть счётчик."""
        done = 0
        while limit is None or done < limit:
            if self.process_one(handler, worker=worker, lease=lease) is None:
                break
            done += 1
        return done
