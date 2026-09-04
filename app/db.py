from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS submissions (
                student_id TEXT NOT NULL,
                section TEXT NOT NULL CHECK(section IN ('po', 'kuo', 'shai')),
                answers_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (student_id, section),
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            );
            """
        )


def save_submission(
    db_path: Path,
    student_id: str,
    student_name: str,
    section: str,
    answers: dict[str, str],
) -> str:
    timestamp = now_iso()
    with connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT student_name FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if existing and existing["student_name"] != student_name:
            raise ValueError("该学号已使用其他姓名提交，请核对姓名和学号。")

        connection.execute(
            """
            INSERT INTO students (student_id, student_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                student_name = excluded.student_name,
                updated_at = excluded.updated_at
            """,
            (student_id, student_name, timestamp, timestamp),
        )
        connection.execute(
            """
            INSERT INTO submissions (student_id, section, answers_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id, section) DO UPDATE SET
                answers_json = excluded.answers_json,
                updated_at = excluded.updated_at
            """,
            (student_id, section, json.dumps(answers, ensure_ascii=False), timestamp, timestamp),
        )
    return timestamp


def load_submission(
    db_path: Path, student_id: str, student_name: str, section: str
) -> dict[str, Any] | None:
    with connect(db_path) as connection:
        student = connection.execute(
            "SELECT student_name FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if student and student["student_name"] != student_name:
            raise ValueError("姓名与该学号已有记录不一致，请核对后重试。")
        row = connection.execute(
            """
            SELECT answers_json, created_at, updated_at
            FROM submissions
            WHERE student_id = ? AND section = ?
            """,
            (student_id, section),
        ).fetchone()
    if not row:
        return None
    return {
        "answers": json.loads(row["answers_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def load_answers(db_path: Path, student_id: str, section: str) -> dict[str, str]:
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT answers_json FROM submissions WHERE student_id = ? AND section = ?",
            (student_id, section),
        ).fetchone()
    return json.loads(row["answers_json"]) if row else {}


def get_student(db_path: Path, student_id: str) -> dict[str, str] | None:
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT student_id, student_name, created_at, updated_at FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def list_students(db_path: Path) -> list[dict[str, Any]]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                s.student_id,
                s.student_name,
                MAX(CASE WHEN sub.section = 'po' THEN sub.updated_at END) AS po_updated_at,
                MAX(CASE WHEN sub.section = 'kuo' THEN sub.updated_at END) AS kuo_updated_at,
                MAX(CASE WHEN sub.section = 'shai' THEN sub.updated_at END) AS shai_updated_at,
                MAX(sub.updated_at) AS latest_updated_at
            FROM students s
            LEFT JOIN submissions sub ON sub.student_id = s.student_id
            GROUP BY s.student_id, s.student_name
            ORDER BY s.student_id COLLATE NOCASE
            """
        ).fetchall()
    return [dict(row) for row in rows]

