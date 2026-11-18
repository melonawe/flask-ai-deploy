"""동의한 사용자의 익명 응답을 SQLite에 저장한다.

이름, 이메일, IP 같은 식별 정보는 저장하지 않는다.
lived와 satisfaction은 나중에 모델을 학습시킬 때 정답(label)으로 쓰기 위한 선택 항목이다.
"""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.db"),
)

LIVED_CHOICES = [
    ("none", "거주 경험 없음"),
    ("under1", "1년 미만 거주"),
    ("over1", "1년 이상 거주"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    answers TEXT NOT NULL,
    total INTEGER NOT NULL,
    lived TEXT,
    satisfaction INTEGER,
    moods TEXT,
    feeling TEXT,
    emotions TEXT
)
"""

# 이전 버전에서 만든 테이블에 없는 열
ADDED_COLUMNS = {"moods": "TEXT", "feeling": "TEXT", "emotions": "TEXT"}


def _prepare(conn):
    conn.execute(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(responses)")}
    for name, column_type in ADDED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE responses ADD COLUMN {name} {column_type}")


def save_response(
    answers, total, lived=None, satisfaction=None, moods=None, feeling=None, emotions=None
):
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            _prepare(conn)
            conn.execute(
                "INSERT INTO responses"
                " (created_at, answers, total, lived, satisfaction, moods, feeling, emotions)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    created_at,
                    json.dumps(answers, sort_keys=True),
                    total,
                    lived,
                    satisfaction,
                    json.dumps(moods or []),
                    feeling or None,
                    json.dumps(emotions, ensure_ascii=False) if emotions else None,
                ),
            )


def load_responses():
    """학습용으로 저장된 응답을 dict 목록으로 돌려준다."""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            _prepare(conn)
        rows = conn.execute(
            "SELECT created_at, answers, total, lived, satisfaction, moods, feeling, emotions"
            " FROM responses ORDER BY id"
        ).fetchall()
    return [
        {
            "created_at": created_at,
            "answers": json.loads(answers),
            "total": total,
            "lived": lived,
            "satisfaction": satisfaction,
            "moods": json.loads(moods) if moods else [],
            "feeling": feeling,
            "emotions": json.loads(emotions) if emotions else {},
        }
        for created_at, answers, total, lived, satisfaction, moods, feeling, emotions in rows
    ]
