"""基于答题表现生成个性化学习报告。"""

from __future__ import annotations

import json
from collections import Counter

from sqlalchemy.orm import Session

from app import crud, models
from app.services.ai_provider import AIProvider


def update_learning_report(
    db: Session,
    course: models.Course,
    student: models.Student,
    submissions: list[models.Submission],
    provider: AIProvider,
) -> models.LearningReport:
    """根据最新答题记录更新学习报告。"""

    if not submissions:
        return crud.upsert_learning_report(
            db,
            student_id=student.id,
            course_id=course.id,
            performance_level="待评估",
            weak_points=[],
            suggestion="请先完成至少一道练习题后再查看学习评价。",
            personalized_exercises=[],
        )

    scores = [item.score for item in submissions]
    average_score = sum(scores) / len(scores)

    weak_points = infer_weak_points(submissions)
    ai_result = provider.generate_learning_report(
        course_title=course.title,
        weak_points=weak_points,
        average_score=average_score,
    )

    performance_level = str(ai_result.get("performance_level", "待提升"))
    suggestion = str(ai_result.get("suggestion", "建议继续巩固基础概念。"))
    personalized_exercises = _normalize_personalized_exercises(ai_result.get("personalized_exercises", []))

    return crud.upsert_learning_report(
        db,
        student_id=student.id,
        course_id=course.id,
        performance_level=performance_level,
        weak_points=weak_points,
        suggestion=suggestion,
        personalized_exercises=personalized_exercises,
    )


def infer_weak_points(submissions: list[models.Submission]) -> list[str]:
    """根据低分题目统计薄弱点。"""

    counter: Counter[str] = Counter()
    for item in submissions:
        knowledge_point = (item.exercise.knowledge_point or "未标注知识点").strip()
        if item.score < 70:
            counter[knowledge_point] += 1

    if not counter:
        return []
    return [name for name, _count in counter.most_common(3)]


def report_to_dict(report: models.LearningReport, student_name: str) -> dict:
    return {
        "student_name": student_name,
        "course_id": report.course_id,
        "performance_level": report.performance_level,
        "weak_points": json.loads(report.weak_points_json),
        "suggestion": report.suggestion,
        "personalized_exercises": json.loads(report.personalized_exercises_json),
    }


def _normalize_personalized_exercises(raw_items: object) -> list[dict[str, str]]:
    if not isinstance(raw_items, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        if not question:
            continue
        normalized.append(
            {
                "question": question,
                "answer": str(item.get("answer", "")).strip(),
                "knowledge_point": str(item.get("knowledge_point", "")).strip(),
            }
        )
    return normalized
