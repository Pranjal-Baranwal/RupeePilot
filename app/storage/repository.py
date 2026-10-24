
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config import PROJECT_ROOT
from app.schemas.financial_models import PlanningResult


DEFAULT_DATABASE_PATH = (
    PROJECT_ROOT / "data" / "rupeepilot.db"
)


class PlanningRepository:
    """SQLite repository for RupeePilot planning results."""

    def __init__(
        self,
        database_path: str | Path | None = None,
    ) -> None:
        self.database_path = Path(
            database_path or DEFAULT_DATABASE_PATH
        ).resolve()

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open a database connection and handle commit or rollback."""

        connection = sqlite3.connect(
            str(self.database_path),
            timeout=10,
        )
        connection.row_factory = sqlite3.Row

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the planning-records table if it does not exist."""

        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS planning_records (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save_result(self, result: PlanningResult) -> None:
        """Save a planning result.

        Saving an existing request_id updates its contents while
        preserving its original creation timestamp.
        """

        now = datetime.now(timezone.utc).isoformat()

        result_json = result.model_dump_json()

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO planning_records (
                    request_id,
                    status,
                    summary,
                    result_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
                (
                    result.request_id,
                    result.status,
                    result.summary,
                    result_json,
                    now,
                    now,
                ),
            )

    def get_result(
        self,
        request_id: str,
    ) -> PlanningResult | None:
        """Retrieve one planning result by its request ID."""

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT result_json
                FROM planning_records
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()

        if row is None:
            return None

        return PlanningResult.model_validate_json(
            row["result_json"]
        )

    def list_results(
        self,
        limit: int = 20,
    ) -> list[PlanningResult]:
        """Return the most recently updated planning results."""

        if not 1 <= limit <= 500:
            raise ValueError(
                "limit must be between 1 and 500."
            )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT result_json
                FROM planning_records
                ORDER BY updated_at DESC, request_id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            PlanningResult.model_validate_json(
                row["result_json"]
            )
            for row in rows
        ]

    def delete_result(self, request_id: str) -> bool:
        """Delete a record and report whether it existed."""

        with self._connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM planning_records
                WHERE request_id = ?
                """,
                (request_id,),
            )

            return cursor.rowcount > 0

    def count_results(self) -> int:
        """Return the total number of stored planning results."""

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM planning_records
                """
            ).fetchone()

        return int(row["total"])