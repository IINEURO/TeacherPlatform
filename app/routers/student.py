"""学生端 API（最小可运行）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import (
    CourseOut,
    KnowledgeEdgeOut,
    KnowledgeGraphOut,
    KnowledgeNodeOut,
    PersonalizedRecommendationOut,
    QuestionResultOut,
    StudentLearningContentOut,
    StudentVideoOut,
    StudentSubmitRequest,
    StudentSubmitResultOut,
    SupplementExerciseOut,
)
from app.services.knowledge_graph import build_mastery_map
from app.services.personalized_recommendation import build_personalized_recommendation

router = APIRouter(prefix="/api/student", tags=["student"])


@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseOut]:
    """学生端课程列表。"""

    return crud.list_courses(db)


@router.get("/courses/{course_id}/learning", response_model=StudentLearningContentOut)
def get_learning_content(course_id: int, db: Session = Depends(get_db)) -> StudentLearningContentOut:
    """获取学生学习页所需内容。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    generated = crud.get_generated_outline(db, course_id)
    if not generated:
        raise HTTPException(status_code=404, detail="该课程尚未生成教学大纲")

    teaching_outline = _safe_parse_list(generated.teaching_outline_json)
    core_points = _safe_parse_list(generated.core_knowledge_points_json)

    videos = crud.list_materials(db, course_id, material_type="video")
    video_items = [_to_student_video_out(item) for item in videos]

    exercises = crud.list_choice_exercises(db, course_id)
    exercise_items = [_to_supplement_exercise_out(item) for item in exercises]

    return StudentLearningContentOut(
        course=course,
        course_intro=generated.course_intro,
        teaching_outline=teaching_outline,
        core_knowledge_points=core_points,
        videos=video_items,
        exercises=exercise_items,
    )


@router.get("/courses/{course_id}/knowledge-graph", response_model=KnowledgeGraphOut)
def get_student_knowledge_graph(
    course_id: int,
    student_name: str | None = None,
    db: Session = Depends(get_db),
) -> KnowledgeGraphOut:
    """学生端读取知识图谱，并返回掌握度。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    nodes = crud.list_knowledge_nodes(db, course_id)
    if not nodes:
        raise HTTPException(status_code=404, detail="该课程尚未生成知识图谱")
    edges = crud.list_knowledge_edges(db, course_id)

    if student_name and student_name.strip():
        student = crud.get_student_by_name(db, student_name)
        submissions = crud.list_submissions_for_course(db, course_id, student.id) if student else []
    else:
        submissions = crud.list_submissions_for_course(db, course_id)

    mastery_map = build_mastery_map(nodes, submissions)
    return _to_knowledge_graph_out(course=course, nodes=nodes, edges=edges, mastery_map=mastery_map)


@router.post("/courses/{course_id}/submit", response_model=StudentSubmitResultOut)
def submit_answers(
    course_id: int,
    payload: StudentSubmitRequest,
    db: Session = Depends(get_db),
) -> StudentSubmitResultOut:
    """学生一次性提交答案并自动判分（选择题）。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    if not payload.answers:
        raise HTTPException(status_code=400, detail="请至少提交一道题的答案")

    student = crud.get_or_create_student(db, payload.student_name)

    answer_map: dict[int, str] = {}
    for item in payload.answers:
        selected = _normalize_choice_answer(item.selected_option)
        if selected not in {"A", "B", "C", "D"}:
            raise HTTPException(status_code=400, detail=f"题目 {item.exercise_id} 的选项无效")
        answer_map[item.exercise_id] = selected

    exercise_ids = list(answer_map.keys())
    exercises = crud.get_exercises_by_ids(db, exercise_ids)
    exercise_map = {item.id: item for item in exercises}

    if len(exercise_map) != len(exercise_ids):
        raise HTTPException(status_code=400, detail="提交中包含不存在的题目")

    results: list[QuestionResultOut] = []
    total_score = 0.0

    for exercise_id in exercise_ids:
        exercise = exercise_map[exercise_id]

        if exercise.course_id != course_id:
            raise HTTPException(status_code=400, detail=f"题目 {exercise_id} 不属于当前课程")
        if exercise.question_type not in {"single_choice", "multiple_choice"}:
            raise HTTPException(status_code=400, detail=f"题目 {exercise_id} 不是可自动批改的选择题")

        selected = answer_map[exercise_id]
        correct_answer = _normalize_choice_answer(exercise.reference_answer or "")
        is_correct = selected == correct_answer
        score = 1.0 if is_correct else 0.0
        total_score += score

        feedback = "回答正确" if is_correct else f"回答错误，正确答案：{correct_answer}"
        crud.create_submission(
            db,
            exercise_id=exercise.id,
            student_id=student.id,
            answer_text=selected,
            score=score,
            feedback=feedback,
        )

        results.append(
            QuestionResultOut(
                exercise_id=exercise.id,
                question_text=exercise.question_text,
                selected_option=selected,
                correct_answer=correct_answer,
                is_correct=is_correct,
                score=score,
                analysis=exercise.analysis,
                knowledge_point=exercise.knowledge_point,
            )
        )

    max_score = float(len(results))
    accuracy = round((total_score / max_score) * 100, 2) if max_score > 0 else 0.0
    correct_count = sum(1 for item in results if item.is_correct)
    wrong_count = len(results) - correct_count

    return StudentSubmitResultOut(
        course_id=course.id,
        course_title=course.title,
        student_name=student.name,
        total_score=total_score,
        max_score=max_score,
        accuracy=accuracy,
        correct_count=correct_count,
        wrong_count=wrong_count,
        results=results,
    )


@router.get(
    "/courses/{course_id}/recommendation/{student_name}",
    response_model=PersonalizedRecommendationOut,
)
def get_personalized_recommendation(
    course_id: int,
    student_name: str,
    db: Session = Depends(get_db),
) -> PersonalizedRecommendationOut:
    """生成个性化补练推荐（规则驱动）。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")

    student = crud.get_or_create_student(db, student_name)
    result = build_personalized_recommendation(db=db, course=course, student=student)
    return PersonalizedRecommendationOut(**result)


def _safe_parse_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return []


def _normalize_choice_answer(value: str) -> str:
    text = (value or "").strip().upper()
    if not text:
        return ""
    return text[0]


def _to_supplement_exercise_out(record) -> SupplementExerciseOut:
    return SupplementExerciseOut(
        id=record.id,
        course_id=record.course_id,
        source_type=record.source_type,
        question_type=record.question_type,
        question_text=record.question_text,
        options=_safe_parse_list(record.options_json),
        answer=record.reference_answer,
        analysis=record.analysis,
        knowledge_point=record.knowledge_point,
    )


def _to_student_video_out(record) -> StudentVideoOut:
    return StudentVideoOut(
        id=record.id,
        file_name=record.file_name,
        url=f"/uploads/{record.course_id}/{record.file_name}",
        created_at=record.created_at,
    )


def _to_knowledge_graph_out(course, nodes: list, edges: list, mastery_map: dict[str, float | None]):
    node_by_id = {item.id: item for item in nodes}

    node_items = [
        KnowledgeNodeOut(
            id=item.id,
            node_key=item.node_key,
            node_name=item.node_name,
            node_type=item.node_type,
            description=item.description,
            level=item.level,
            order_index=item.order_index,
            mastery_rate=mastery_map.get(item.node_key),
        )
        for item in nodes
    ]

    edge_items: list[KnowledgeEdgeOut] = []
    for item in edges:
        source = node_by_id.get(item.source_node_id)
        target = node_by_id.get(item.target_node_id)
        if not source or not target:
            continue
        edge_items.append(
            KnowledgeEdgeOut(
                id=item.id,
                source_node_id=item.source_node_id,
                target_node_id=item.target_node_id,
                relation_type=item.relation_type,
                weight=item.weight,
                source_node_key=source.node_key,
                source_node_name=source.node_name,
                target_node_key=target.node_key,
                target_node_name=target.node_name,
            )
        )

    return KnowledgeGraphOut(
        course_id=course.id,
        course_title=course.title,
        node_count=len(node_items),
        edge_count=len(edge_items),
        nodes=node_items,
        edges=edge_items,
    )
