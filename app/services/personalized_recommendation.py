"""规则驱动的个性化补练推荐服务。"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import crud
from app.models import Course, Exercise, Material, Student, Submission
from app.services.content_extractor import parse_question_bank_entries
from app.services.llm_client import get_llm_client


@dataclass
class WeakPoint:
    """薄弱知识点统计。"""

    knowledge_point: str
    accuracy: float
    total_answered: int


def build_personalized_recommendation(
    db: Session,
    course: Course,
    student: Student,
) -> dict:
    """生成个性化补练推荐。

    规则步骤：
    1. 统计知识点正确率。
    2. 准确率 < 60% 视为薄弱点。
    3. 先从已有题库/已有题目挑选对应知识点习题。
    4. 若数量不足，调用 AI 补 1~2 题。
    5. 生成学习建议文本。
    """

    submissions = crud.list_submissions_for_student_course(db, student.id, course.id)
    weak_points = _compute_weak_points(submissions)

    # 没有作答记录时，直接返回引导信息
    if not submissions:
        return {
            "course_id": course.id,
            "course_title": course.title,
            "student_name": student.name,
            "weak_knowledge_points": [],
            "recommended_exercises": [],
            "learning_comment": "你还没有提交练习题。建议先完成当前课程的基础题，再生成个性化补练推荐。",
        }

    weak_names = [item.knowledge_point for item in weak_points]

    recommended: list[dict] = []

    # 步骤1：优先从教师已有题库文本中选题
    question_bank_materials = crud.list_materials(db, course.id, material_type="question_bank")
    recommended.extend(_pick_from_question_bank(question_bank_materials, weak_names, limit=4))

    # 步骤2：若还不够，再从课程现有题目中选同知识点题
    if len(recommended) < 4 and weak_names:
        existing_exercises = crud.list_exercises_by_knowledge_points(db, course.id, weak_names)
        recommended.extend(_pick_from_existing_exercises(existing_exercises, recommended, limit=4 - len(recommended)))

    # 步骤3：若仍不足，调用 AI 再补 1~2 题
    ai_generated: list[dict] = []
    target_count = min(4, max(2, len(weak_names))) if weak_names else 0
    if weak_names and len(recommended) < target_count:
        ai_needed = max(1, min(2, target_count - len(recommended)))
        ai_generated = _generate_ai_practice(course, weak_names, ai_needed)
        recommended.extend(ai_generated)

        # 将 AI 补题持久化，便于后续复用
        if ai_generated:
            crud.create_personalized_exercises(db, course_id=course.id, exercises=ai_generated)

    # 去重并截断
    recommended = _deduplicate_by_question_text(recommended)[:6]

    learning_comment = _build_learning_comment(submissions, weak_points)

    return {
        "course_id": course.id,
        "course_title": course.title,
        "student_name": student.name,
        "weak_knowledge_points": [
            {
                "knowledge_point": item.knowledge_point,
                "accuracy": round(item.accuracy * 100, 2),
                "total_answered": item.total_answered,
            }
            for item in weak_points
        ],
        "recommended_exercises": recommended,
        "learning_comment": learning_comment,
    }


def _compute_weak_points(submissions: list[Submission]) -> list[WeakPoint]:
    """统计每个知识点正确率并筛选薄弱点。"""

    stats: dict[str, dict[str, float]] = defaultdict(lambda: {"correct": 0.0, "total": 0.0})

    for submission in submissions:
        exercise = submission.exercise
        if not exercise:
            continue
        point = (exercise.knowledge_point or "未标注知识点").strip() or "未标注知识点"
        stats[point]["total"] += 1
        if submission.score >= 1.0:
            stats[point]["correct"] += 1

    weak_points: list[WeakPoint] = []
    for point, value in stats.items():
        total = int(value["total"])
        if total <= 0:
            continue
        accuracy = value["correct"] / value["total"]
        if accuracy < 0.6:
            weak_points.append(WeakPoint(knowledge_point=point, accuracy=accuracy, total_answered=total))

    # 低准确率优先展示
    weak_points.sort(key=lambda item: (item.accuracy, -item.total_answered))
    return weak_points


def _pick_from_question_bank(materials: list[Material], weak_points: list[str], limit: int) -> list[dict]:
    """从教师上传题库中优先选题。"""

    if not weak_points or limit <= 0:
        return []

    results: list[dict] = []
    weak_set = {item.strip() for item in weak_points if item.strip()}

    for material in materials:
        entries = parse_question_bank_entries(material.extracted_text or "")
        for entry in entries:
            question = entry.get("question", "").strip()
            if not question:
                continue

            kp = (entry.get("knowledge_point", "") or "").strip()
            # 只选择“对应薄弱知识点”题；若未标注知识点，则尝试题干关键词匹配
            if kp:
                if kp not in weak_set:
                    continue
            elif not any(point in question for point in weak_set):
                continue

            options = _safe_load_options(entry.get("options", "[]"))
            answer = (entry.get("answer", "") or "").strip()
            question_type = "single_choice" if options else "short_answer"

            results.append(
                {
                    "source": "existing_bank",
                    "question_type": question_type,
                    "question_text": question,
                    "options": options,
                    "answer": answer or None,
                    "analysis": entry.get("analysis", "") or "建议先回顾对应知识点，再独立完成此题。",
                    "knowledge_point": kp or (weak_points[0] if weak_points else "未标注知识点"),
                }
            )
            if len(results) >= limit:
                return results

    return results


def _pick_from_existing_exercises(exercises: list[Exercise], existing: list[dict], limit: int) -> list[dict]:
    """从已有课程题目中补充推荐。"""

    if limit <= 0:
        return []

    existing_questions = {item.get("question_text", "") for item in existing}
    results: list[dict] = []

    for exercise in exercises:
        if exercise.question_text in existing_questions:
            continue

        options = _safe_load_options(exercise.options_json)
        results.append(
            {
                "source": "existing_exercise",
                "question_type": exercise.question_type,
                "question_text": exercise.question_text,
                "options": options,
                "answer": exercise.reference_answer,
                "analysis": exercise.analysis or "建议完成后对照课堂知识点进行复盘。",
                "knowledge_point": exercise.knowledge_point or "未标注知识点",
            }
        )
        if len(results) >= limit:
            break

    return results


def _generate_ai_practice(course: Course, weak_points: list[str], count: int) -> list[dict]:
    """调用 AI 生成 1~2 道薄弱点补练题。"""

    if count <= 0:
        return []

    try:
        llm_client = get_llm_client()
        generated = llm_client.generate_targeted_practice(
            subject=course.subject,
            difficulty_level=course.difficulty_level,
            weak_points=weak_points,
            max_count=count,
        )
        raw_items = generated.get("supplement_exercises", [])
        if not isinstance(raw_items, list):
            return []

        results: list[dict] = []
        for item in raw_items[:count]:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question_text", "")).strip()
            if not question:
                continue
            results.append(
                {
                    "source": "ai_generated",
                    "question_type": str(item.get("question_type", "single_choice")),
                    "question_text": question,
                    "options": item.get("options", []) if isinstance(item.get("options", []), list) else [],
                    "answer": str(item.get("answer", "")).strip() or None,
                    "analysis": str(item.get("analysis", "")).strip() or "建议完成后总结关键思路。",
                    "knowledge_point": str(item.get("knowledge_point", "")).strip()
                    or (weak_points[0] if weak_points else "核心知识点"),
                }
            )
        return results
    except Exception:
        # AI 失败时降级为规则题，保证功能可用
        return [
            {
                "source": "rule_fallback",
                "question_type": "single_choice",
                "question_text": f"下列关于“{weak_points[0]}”的说法，哪项更准确？",
                "options": ["A. 符合定义并可应用", "B. 只在极少数场景成立", "C. 与该概念无关", "D. 完全错误"],
                "answer": "A",
                "analysis": "先明确概念定义，再判断其适用场景。",
                "knowledge_point": weak_points[0],
            }
        ][:count]


def _build_learning_comment(submissions: list[Submission], weak_points: list[WeakPoint]) -> str:
    """生成简短学习评价。"""

    total = len(submissions)
    correct = sum(1 for item in submissions if item.score >= 1.0)
    accuracy = (correct / total) * 100 if total > 0 else 0.0

    if not weak_points:
        return f"整体表现较好，当前正确率约 {accuracy:.1f}%。建议保持练习频率，继续巩固综合应用能力。"

    weak_text = "、".join(item.knowledge_point for item in weak_points[:3])
    return (
        f"当前正确率约 {accuracy:.1f}%。薄弱点集中在：{weak_text}。"
        "建议先回顾对应知识点定义，再完成推荐补练题并复盘错因。"
    )


def _safe_load_options(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return []


def _deduplicate_by_question_text(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        question = str(item.get("question_text", "")).strip()
        if not question:
            continue
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
