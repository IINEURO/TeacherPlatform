"""数据库初始化与会话管理。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import settings

SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.db_path}"

# SQLite 在多线程场景下需要关闭同线程限制
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话。"""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_teacher_migrations() -> None:
    """兼容历史数据库的最小迁移。

    比赛原型阶段不引入 Alembic，这里只处理教师端新增字段。
    """

    with engine.begin() as conn:
        columns = conn.execute(text("PRAGMA table_info(courses)")).fetchall()
        existing = {row[1] for row in columns}

        if "subject" not in existing:
            conn.execute(text("ALTER TABLE courses ADD COLUMN subject TEXT NOT NULL DEFAULT ''"))
        if "teaching_objective" not in existing:
            conn.execute(text("ALTER TABLE courses ADD COLUMN teaching_objective TEXT NOT NULL DEFAULT ''"))
        if "target_audience" not in existing:
            conn.execute(text("ALTER TABLE courses ADD COLUMN target_audience TEXT NOT NULL DEFAULT ''"))
        if "difficulty_level" not in existing:
            conn.execute(text("ALTER TABLE courses ADD COLUMN difficulty_level TEXT NOT NULL DEFAULT '中等'"))
        if "updated_at" not in existing:
            conn.execute(text("ALTER TABLE courses ADD COLUMN updated_at DATETIME"))
            # 老数据补一份默认更新时间，便于后续排序和展示
            conn.execute(text("UPDATE courses SET updated_at = created_at WHERE updated_at IS NULL"))

        generated_columns = conn.execute(text("PRAGMA table_info(generated_contents)")).fetchall()
        generated_existing = {row[1] for row in generated_columns}
        if generated_columns:
            if "course_intro" not in generated_existing:
                conn.execute(text("ALTER TABLE generated_contents ADD COLUMN course_intro TEXT NOT NULL DEFAULT ''"))
            if "teaching_outline_json" not in generated_existing:
                conn.execute(
                    text(
                        "ALTER TABLE generated_contents ADD COLUMN teaching_outline_json TEXT NOT NULL DEFAULT '[]'"
                    )
                )
            if "core_knowledge_points_json" not in generated_existing:
                conn.execute(
                    text(
                        "ALTER TABLE generated_contents "
                        "ADD COLUMN core_knowledge_points_json TEXT NOT NULL DEFAULT '[]'"
                    )
                )
            if "raw_model_output" not in generated_existing:
                conn.execute(text("ALTER TABLE generated_contents ADD COLUMN raw_model_output TEXT"))

        exercise_columns = conn.execute(text("PRAGMA table_info(exercises)")).fetchall()
        exercise_existing = {row[1] for row in exercise_columns}
        if exercise_columns:
            if "question_type" not in exercise_existing:
                conn.execute(
                    text("ALTER TABLE exercises ADD COLUMN question_type TEXT NOT NULL DEFAULT 'single_choice'")
                )
            if "options_json" not in exercise_existing:
                conn.execute(text("ALTER TABLE exercises ADD COLUMN options_json TEXT NOT NULL DEFAULT '[]'"))
            if "analysis" not in exercise_existing:
                conn.execute(text("ALTER TABLE exercises ADD COLUMN analysis TEXT"))
