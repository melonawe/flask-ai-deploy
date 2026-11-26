"""동의한 사용자의 익명 응답을 데이터베이스에 저장한다.

- 환경 변수 DATABASE_URL이 있으면 그 데이터베이스(PostgreSQL)를 쓴다. 배포용.
  예: postgresql://user:password@host/dbname?sslmode=require
- 없으면 프로젝트 폴더의 SQLite 파일(responses.db, 또는 DATABASE_PATH)을 쓴다. 개발용.

이름, 이메일, IP 같은 식별 정보는 저장하지 않는다.
lived와 satisfaction은 나중에 모델을 학습시킬 때 정답(label)으로 쓰기 위한 선택 항목이다.
"""

import json
import os
import threading
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    Text,
    create_engine,
    inspect,
    select,
    text,
)

DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.db"),
)

LIVED_CHOICES = [
    ("none", "거주 경험 없음"),
    ("under1", "1년 미만 거주"),
    ("over1", "1년 이상 거주"),
]

metadata = MetaData()
responses = Table(
    "responses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", Text, nullable=False),
    Column("answers", Text, nullable=False),
    Column("total", Integer, nullable=False),
    Column("lived", Text),
    Column("satisfaction", Integer),
    Column("moods", Text),
    Column("feeling", Text),
    Column("emotions", Text),
    Column("version", Integer),
)

# 이전 버전에서 만든 테이블에 없을 수 있는 열
ADDED_COLUMNS = {"moods": "TEXT", "feeling": "TEXT", "emotions": "TEXT", "version": "INTEGER"}


def database_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///" + DB_PATH.replace("\\", "/")
    # Render, Neon, Supabase 등이 주는 주소를 SQLAlchemy의 psycopg 드라이버 형식으로 맞춘다.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


_engine = None
_engine_url = None
_lock = threading.Lock()


def engine():
    """처음 쓸 때 연결을 만들고 테이블을 준비한다. 주소가 바뀌면(테스트 등) 다시 만든다."""
    global _engine, _engine_url
    url = database_url()
    with _lock:
        if _engine is None or _engine_url != url:
            if _engine is not None:
                _engine.dispose()
                _engine = None
            # DB가 응답하지 않을 때 사용자가 오래 기다리지 않도록 연결 대기 시간을 5초로 제한한다.
            connect_args = {"connect_timeout": 5} if url.startswith("postgresql") else {}
            new_engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
            # 테이블 준비에 실패하면 엔진을 저장하지 않아, 다음 요청에서 다시 시도한다.
            _prepare(new_engine)
            _engine, _engine_url = new_engine, url
        return _engine


def _prepare(eng):
    metadata.create_all(eng)
    existing = {column["name"] for column in inspect(eng).get_columns("responses")}
    with eng.begin() as conn:
        for name, column_type in ADDED_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE responses ADD COLUMN {name} {column_type}"))


def save_response(
    answers,
    total,
    lived=None,
    satisfaction=None,
    moods=None,
    feeling=None,
    emotions=None,
    version=None,
):
    row = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "answers": json.dumps(answers, sort_keys=True),
        "total": total,
        "lived": lived,
        "satisfaction": satisfaction,
        "moods": json.dumps(moods or []),
        "feeling": feeling or None,
        "emotions": json.dumps(emotions, ensure_ascii=False) if emotions else None,
        "version": version,
    }
    with engine().begin() as conn:
        conn.execute(responses.insert().values(**row))


def load_responses():
    """학습용으로 저장된 응답을 dict 목록으로 돌려준다."""
    with engine().connect() as conn:
        rows = conn.execute(select(responses).order_by(responses.c.id)).mappings().all()
    return [
        {
            "created_at": row["created_at"],
            "answers": json.loads(row["answers"]),
            "total": row["total"],
            "lived": row["lived"],
            "satisfaction": row["satisfaction"],
            "moods": json.loads(row["moods"]) if row["moods"] else [],
            "feeling": row["feeling"],
            "emotions": json.loads(row["emotions"]) if row["emotions"] else {},
            "version": row["version"],
        }
        for row in rows
    ]

