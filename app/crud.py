"""数据访问层（教师端最小功能）。

将数据库读写集中在这里，路由层只负责处理 HTTP 请求与响应。
"""

from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import models


def create_course(
    db: Session,
    title: str,
    subject: str,
    difficulty_level: str,
    teaching_objective: str,
    target_audience: str,
) -> models.Course:
    """创建课程。"""

    course = models.Course(
        title=title.strip(),
        subject=subject.strip(),
        difficulty_level=difficulty_level.strip() or "中等",
        teaching_objective=teaching_objective.strip(),
        target_audience=target_audience.strip(),
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def list_courses(db: Session) -> list[models.Course]:
    """按创建时间倒序列出课程。"""

    stmt = select(models.Course).order_by(models.Course.created_at.desc())
    return list(db.scalars(stmt))


def get_course(db: Session, course_id: int) -> models.Course | None:
    """根据 ID 读取课程。"""

    return db.get(models.Course, course_id)


def create_material(
    db: Session,
    course_id: int,
    material_type: str,
    file_name: str,
    file_path: str,
    extracted_text: str,
) -> models.Material:
    """保存上传资源记录。"""

    material = models.Material(
        course_id=course_id,
        material_type=material_type,
        file_name=file_name,
        file_path=file_path,
        extracted_text=extracted_text,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


def list_materials(db: Session, course_id: int, material_type: str | None = None) -> list[models.Material]:
    """按课程读取资源，可选按资源类型过滤。"""

    stmt = select(models.Material).where(models.Material.course_id == course_id)
    if material_type:
        stmt = stmt.where(models.Material.material_type == material_type)
    stmt = stmt.order_by(models.Material.created_at.desc())
    return list(db.scalars(stmt))


def upsert_generated_outline(
    db: Session,
    course_id: int,
    course_intro: str,
    teaching_outline: list[str],
    core_knowledge_points: list[str],
    raw_model_output: str,
) -> models.GeneratedContent:
    """写入或更新 AI 生成结果。"""

    teaching_outline_json = json.dumps(teaching_outline, ensure_ascii=False)
    core_points_json = json.dumps(core_knowledge_points, ensure_ascii=False)

    # 为兼容旧字段，这里同步维护 outline / knowledge_summary / extra_exercises_json
    outline_text = "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(teaching_outline))
    knowledge_summary = "\n".join(f"- {point}" for point in core_knowledge_points)

    existing = db.scalar(select(models.GeneratedContent).where(models.GeneratedContent.course_id == course_id))
    if existing:
        existing.course_intro = course_intro
        existing.teaching_outline_json = teaching_outline_json
        existing.core_knowledge_points_json = core_points_json
        existing.raw_model_output = raw_model_output
        existing.outline = outline_text or "暂无教学大纲"
        existing.knowledge_summary = knowledge_summary or "暂无核心知识点"
        existing.extra_exercises_json = core_points_json
        db.commit()
        db.refresh(existing)
        return existing

    record = models.GeneratedContent(
        course_id=course_id,
        course_intro=course_intro,
        teaching_outline_json=teaching_outline_json,
        core_knowledge_points_json=core_points_json,
        raw_model_output=raw_model_output,
        outline=outline_text or "暂无教学大纲",
        knowledge_summary=knowledge_summary or "暂无核心知识点",
        extra_exercises_json=core_points_json,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_generated_outline(db: Session, course_id: int) -> models.GeneratedContent | None:
    """查询课程 AI 生成结果。"""

    return db.scalar(select(models.GeneratedContent).where(models.GeneratedContent.course_id == course_id))


def replace_generated_exercises(
    db: Session,
    course_id: int,
    exercises: list[dict[str, str | list[str]]],
) -> list[models.Exercise]:
    """覆盖式写入 AI 补充练习题。"""

    db.execute(
        delete(models.Exercise).where(
            models.Exercise.course_id == course_id,
            models.Exercise.source_type == "generated",
        )
    )

    records: list[models.Exercise] = []
    for item in exercises:
        question_text = str(item.get("question_text", "")).strip()
        if not question_text:
            continue

        question_type = str(item.get("question_type", "single_choice")).strip() or "single_choice"
        options = item.get("options", [])
        if not isinstance(options, list):
            options = []

        record = models.Exercise(
            course_id=course_id,
            source_type="generated",
            question_type=question_type,
            question_text=question_text,
            options_json=json.dumps([str(opt) for opt in options], ensure_ascii=False),
            reference_answer=str(item.get("answer", "")).strip() or None,
            analysis=str(item.get("analysis", "")).strip() or None,
            knowledge_point=str(item.get("knowledge_point", "")).strip() or None,
        )
        db.add(record)
        records.append(record)

    # 同步更新 generated_contents 里的补充题快照，便于兼容旧逻辑
    generated = db.scalar(select(models.GeneratedContent).where(models.GeneratedContent.course_id == course_id))
    if generated:
        generated.extra_exercises_json = json.dumps(exercises, ensure_ascii=False)

    db.commit()
    for record in records:
        db.refresh(record)
    return records


def list_generated_exercises(db: Session, course_id: int) -> list[models.Exercise]:
    """读取课程下 AI 生成的补充练习题。"""

    stmt = (
        select(models.Exercise)
        .where(models.Exercise.course_id == course_id, models.Exercise.source_type == "generated")
        .order_by(models.Exercise.created_at.asc())
    )
    return list(db.scalars(stmt))


def list_choice_exercises(db: Session, course_id: int) -> list[models.Exercise]:
    """读取可自动批改的选择题（单选/多选）。"""

    stmt = (
        select(models.Exercise)
        .where(
            models.Exercise.course_id == course_id,
            models.Exercise.question_type.in_(["single_choice", "multiple_choice"]),
        )
        .order_by(models.Exercise.created_at.asc())
    )
    return list(db.scalars(stmt))


def get_exercises_by_ids(db: Session, exercise_ids: list[int]) -> list[models.Exercise]:
    """按 ID 批量读取题目。"""

    if not exercise_ids:
        return []
    stmt = select(models.Exercise).where(models.Exercise.id.in_(exercise_ids))
    return list(db.scalars(stmt))


def get_or_create_student(db: Session, student_name: str) -> models.Student:
    """获取或创建学生。"""

    normalized = student_name.strip()
    existing = db.scalar(select(models.Student).where(models.Student.name == normalized))
    if existing:
        return existing

    student = models.Student(name=normalized)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def create_submission(
    db: Session,
    exercise_id: int,
    student_id: int,
    answer_text: str,
    score: float,
    feedback: str,
) -> models.Submission:
    """保存单题作答记录。"""

    submission = models.Submission(
        exercise_id=exercise_id,
        student_id=student_id,
        answer_text=answer_text,
        score=score,
        feedback=feedback,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions_for_student_course(
    db: Session,
    student_id: int,
    course_id: int,
) -> list[models.Submission]:
    """读取学生在课程下的作答记录（含题目信息）。"""

    stmt = (
        select(models.Submission)
        .join(models.Exercise, models.Submission.exercise_id == models.Exercise.id)
        .where(
            models.Submission.student_id == student_id,
            models.Exercise.course_id == course_id,
        )
        .order_by(models.Submission.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_exercises_by_knowledge_points(
    db: Session,
    course_id: int,
    knowledge_points: list[str],
) -> list[models.Exercise]:
    """按知识点批量读取题目。"""

    if not knowledge_points:
        return []

    stmt = (
        select(models.Exercise)
        .where(
            models.Exercise.course_id == course_id,
            models.Exercise.knowledge_point.in_(knowledge_points),
        )
        .order_by(models.Exercise.created_at.asc())
    )
    return list(db.scalars(stmt))


def create_personalized_exercises(
    db: Session,
    course_id: int,
    exercises: list[dict[str, str | list[str]]],
) -> list[models.Exercise]:
    """保存 AI 生成的个性化补练题。"""

    records: list[models.Exercise] = []
    for item in exercises:
        question_text = str(item.get("question_text", "")).strip()
        if not question_text:
            continue

        options = item.get("options", [])
        if not isinstance(options, list):
            options = []

        record = models.Exercise(
            course_id=course_id,
            source_type="personalized",
            question_type=str(item.get("question_type", "single_choice")).strip() or "single_choice",
            question_text=question_text,
            options_json=json.dumps([str(opt) for opt in options], ensure_ascii=False),
            reference_answer=str(item.get("answer", "")).strip() or None,
            analysis=str(item.get("analysis", "")).strip() or None,
            knowledge_point=str(item.get("knowledge_point", "")).strip() or None,
        )
        db.add(record)
        records.append(record)

    db.commit()
    for record in records:
        db.refresh(record)
    return records
