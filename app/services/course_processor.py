"""课程内容处理编排。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app import crud
from app.services.ai_provider import AIProvider
from app.services.content_extractor import parse_questions


def process_course_content(db: Session, course_id: int, provider: AIProvider) -> dict:
    """处理教师上传内容并产出教学大纲/知识点/补充题。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise ValueError("课程不存在")

    notes = crud.list_materials(db, course_id, material_type="note")
    ppts = crud.list_materials(db, course_id, material_type="ppt")
    question_banks = crud.list_materials(db, course_id, material_type="question_bank")

    notes_text = "\n".join(item.extracted_text or "" for item in notes)
    ppt_text = "\n".join(item.extracted_text or "" for item in ppts)

    uploaded_questions: list[dict[str, str]] = []
    for material in question_banks:
        uploaded_questions.extend(parse_questions(material.extracted_text or ""))

    ai_result = provider.generate_course_assets(
        course_title=course.title,
        teaching_notes=notes_text,
        ppt_text=ppt_text,
        uploaded_questions=uploaded_questions,
    )

    outline = str(ai_result.get("outline", "")).strip() or "暂无生成大纲"
    knowledge_summary = str(ai_result.get("knowledge_summary", "")).strip() or "暂无知识点总结"
    extra_exercises = _normalize_exercises(ai_result.get("extra_exercises", []))

    generated = crud.upsert_generated_content(
        db,
        course_id=course_id,
        outline=outline,
        knowledge_summary=knowledge_summary,
        extra_exercises=extra_exercises,
    )

    # 每次重新处理都覆盖上一批“系统补充题”
    crud.delete_exercises_by_source(db, course_id=course_id, source_type="generated")
    created_generated_exercises = crud.create_exercises(
        db,
        course_id=course_id,
        source_type="generated",
        exercises=extra_exercises,
    )

    return {
        "course_id": course_id,
        "outline": generated.outline,
        "knowledge_summary": generated.knowledge_summary,
        "extra_exercises": json.loads(generated.extra_exercises_json),
        "generated_exercise_count": len(created_generated_exercises),
    }


def _normalize_exercises(raw_exercises: object) -> list[dict[str, str]]:
    """兼容模型输出格式，统一为业务标准结构。"""

    if not isinstance(raw_exercises, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in raw_exercises:
        if isinstance(item, str):
            question = item.strip()
            if question:
                normalized.append({"question": question, "answer": "", "knowledge_point": ""})
            continue
        if isinstance(item, dict):
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
