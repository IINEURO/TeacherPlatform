"""教师端 API（最小可运行版本）。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import (
    CourseCreate,
    CourseOut,
    CourseResourcesOut,
    GeneratedOutlineOut,
    KnowledgeEdgeOut,
    KnowledgeGraphOut,
    KnowledgeNodeOut,
    MaterialOut,
    SupplementExerciseBatchOut,
    SupplementExerciseOut,
)
from app.services.content_extractor import save_text_material, save_upload_and_extract_text
from app.services.knowledge_graph import build_course_knowledge_graph
from app.services.llm_client import (
    KNOWLEDGE_GRAPH_PROMPT_TEMPLATE,
    PROMPT_TEMPLATE,
    SUPPLEMENT_EXERCISES_PROMPT_TEMPLATE,
    get_llm_client,
)

router = APIRouter(prefix="/api/teacher", tags=["teacher"])
logger = logging.getLogger(__name__)


@router.post("/courses", response_model=CourseOut)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> CourseOut:
    """创建课程。"""

    return crud.create_course(
        db,
        title=payload.title,
        subject=payload.subject,
        difficulty_level=payload.difficulty_level,
        teaching_objective=payload.teaching_objective,
        target_audience=payload.target_audience,
    )


@router.get("/courses", response_model=list[CourseOut])
def list_courses(db: Session = Depends(get_db)) -> list[CourseOut]:
    """列出课程。"""

    return crud.list_courses(db)


@router.post("/courses/{course_id}/teaching-note")
def upload_teaching_note(
    course_id: int,
    note_text: str = Form(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    """上传教学说明文本。"""

    _ensure_course_exists(db, course_id)

    file_name, file_path, extracted_text = save_text_material(course_id, prefix="teaching_note", text=note_text)
    material = crud.create_material(
        db,
        course_id=course_id,
        material_type="note",
        file_name=file_name,
        file_path=file_path,
        extracted_text=extracted_text,
    )

    return {
        "message": "教学说明上传成功",
        "material": MaterialOut.model_validate(material).model_dump(),
    }


@router.post("/courses/{course_id}/ppt")
async def upload_ppt(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """上传 PPT 文件。"""

    _ensure_course_exists(db, course_id)

    if not (file.filename or "").lower().endswith((".ppt", ".pptx")):
        raise HTTPException(status_code=400, detail="请上传 .ppt 或 .pptx 文件")

    file_name, file_path, extracted_text = await save_upload_and_extract_text(course_id, file)
    material = crud.create_material(
        db,
        course_id=course_id,
        material_type="ppt",
        file_name=file_name,
        file_path=file_path,
        extracted_text=extracted_text,
    )

    return {
        "message": "PPT 上传成功",
        "material": MaterialOut.model_validate(material).model_dump(),
        "extracted_preview": extracted_text[:300],
    }


@router.post("/courses/{course_id}/video")
async def upload_video(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """上传教学视频文件（最小版只做文件存储）。"""

    _ensure_course_exists(db, course_id)

    if not (file.filename or "").lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        raise HTTPException(status_code=400, detail="请上传常见视频格式（mp4/mov/avi/mkv/webm）")

    file_name, file_path, extracted_text = await save_upload_and_extract_text(course_id, file)
    material = crud.create_material(
        db,
        course_id=course_id,
        material_type="video",
        file_name=file_name,
        file_path=file_path,
        extracted_text=extracted_text,
    )

    return {
        "message": "教学视频上传成功",
        "material": MaterialOut.model_validate(material).model_dump(),
    }


@router.post("/courses/{course_id}/question-text")
def upload_question_text(
    course_id: int,
    question_text: str = Form(..., min_length=1),
    db: Session = Depends(get_db),
) -> dict:
    """上传题目文本。"""

    _ensure_course_exists(db, course_id)

    file_name, file_path, extracted_text = save_text_material(course_id, prefix="question_text", text=question_text)
    material = crud.create_material(
        db,
        course_id=course_id,
        material_type="question_bank",
        file_name=file_name,
        file_path=file_path,
        extracted_text=extracted_text,
    )

    return {
        "message": "题目文本上传成功",
        "material": MaterialOut.model_validate(material).model_dump(),
    }


@router.get("/courses/{course_id}/resources", response_model=CourseResourcesOut)
def get_course_resources(course_id: int, db: Session = Depends(get_db)) -> CourseResourcesOut:
    """查看课程下已上传资源。"""

    course = _ensure_course_exists(db, course_id)

    notes = crud.list_materials(db, course_id, material_type="note")
    ppts = crud.list_materials(db, course_id, material_type="ppt")
    videos = crud.list_materials(db, course_id, material_type="video")
    questions = crud.list_materials(db, course_id, material_type="question_bank")

    return CourseResourcesOut(
        course=course,
        teaching_notes=notes,
        ppts=ppts,
        videos=videos,
        question_texts=questions,
    )


@router.post("/courses/{course_id}/generate-outline", response_model=GeneratedOutlineOut)
def generate_outline(course_id: int, db: Session = Depends(get_db)) -> GeneratedOutlineOut:
    """根据教学目标 + 教学说明 + PPT 文本生成教学大纲。"""

    course = _ensure_course_exists(db, course_id)

    notes = crud.list_materials(db, course_id, material_type="note")
    ppts = crud.list_materials(db, course_id, material_type="ppt")
    note_text = "\n".join((item.extracted_text or "").strip() for item in notes if item.extracted_text)
    ppt_text = "\n".join((item.extracted_text or "").strip() for item in ppts if item.extracted_text)

    validation_errors: list[str] = []
    if not notes:
        validation_errors.append("未上传教学说明文本")
    elif not note_text:
        validation_errors.append("教学说明文本为空")

    if not ppts:
        validation_errors.append("未上传 PPT 文件")
    elif not ppt_text:
        validation_errors.append("PPT 未提取到文本（建议优先使用 .pptx 文件）")

    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail=(
                f"生成前校验失败：{'；'.join(validation_errors)}。"
                f"当前统计：教学说明 {len(notes)} 份，PPT {len(ppts)} 份。"
            ),
        )

    try:
        llm_client = get_llm_client()
        generated = llm_client.generate_teaching_outline(
            teaching_objective=course.teaching_objective,
            teaching_note_text=note_text,
            ppt_text=ppt_text,
        )
    except ValueError as exc:
        detail = str(exc)
        if "DEEPSEEK_API_KEY" in detail or "LLM_API_KEY" in detail:
            detail = (
                "未配置模型 API Key。请在项目根目录 .env 中设置 "
                "DEEPSEEK_API_KEY，或先导出环境变量后再启动服务。"
            )
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc

    saved = crud.upsert_generated_outline(
        db,
        course_id=course_id,
        course_intro=generated["course_intro"],
        teaching_outline=generated["teaching_outline"],
        core_knowledge_points=generated["core_knowledge_points"],
        raw_model_output=generated.get("_raw_output", ""),
    )
    return _to_generated_outline_out(saved)


@router.get("/courses/{course_id}/generated-outline", response_model=GeneratedOutlineOut)
def get_generated_outline(course_id: int, db: Session = Depends(get_db)) -> GeneratedOutlineOut:
    """读取课程已生成的教学大纲。"""

    _ensure_course_exists(db, course_id)
    generated = crud.get_generated_outline(db, course_id)
    if not generated:
        raise HTTPException(status_code=404, detail="该课程尚未生成教学大纲")
    return _to_generated_outline_out(generated)


@router.post("/courses/{course_id}/generate-knowledge-graph", response_model=KnowledgeGraphOut)
def generate_knowledge_graph(course_id: int, db: Session = Depends(get_db)) -> KnowledgeGraphOut:
    """基于教学资源提取课程知识图谱（AI 优先，规则降级）。"""

    course = _ensure_course_exists(db, course_id)

    notes = crud.list_materials(db, course_id, material_type="note")
    ppts = crud.list_materials(db, course_id, material_type="ppt")
    note_text = "\n".join((item.extracted_text or "").strip() for item in notes if item.extracted_text)
    ppt_text = "\n".join((item.extracted_text or "").strip() for item in ppts if item.extracted_text)

    # 降级数据：若 AI 失败，则用既有大纲/知识点生成规则图谱
    generated = crud.get_generated_outline(db, course_id)
    fallback_outline = _safe_parse_list(generated.teaching_outline_json) if generated else []
    fallback_points = _safe_parse_list(generated.core_knowledge_points_json) if generated else []
    nodes_payload, edges_payload = build_course_knowledge_graph(
        teaching_outline=fallback_outline,
        core_knowledge_points=fallback_points,
    )

    has_resource_text = bool(note_text.strip() or ppt_text.strip())
    if has_resource_text:
        try:
            llm_client = get_llm_client()
            ai_graph = llm_client.generate_knowledge_graph(
                teaching_objective=course.teaching_objective,
                teaching_note_text=note_text,
                ppt_text=ppt_text,
            )
            ai_nodes = ai_graph.get("nodes", [])
            ai_links = ai_graph.get("links", [])
            if isinstance(ai_nodes, list) and isinstance(ai_links, list) and ai_nodes:
                nodes_payload = ai_nodes
                edges_payload = ai_links
        except Exception:
            logger.exception("知识图谱模型提取失败，启用规则降级。course_id=%s", course_id)

    if not nodes_payload:
        raise HTTPException(status_code=400, detail="缺少可用教学资源，无法生成知识图谱")

    nodes, edges = crud.replace_knowledge_graph(db, course_id=course_id, nodes=nodes_payload, edges=edges_payload)
    return _to_knowledge_graph_out(course=course, nodes=nodes, edges=edges)


@router.get("/courses/{course_id}/knowledge-graph", response_model=KnowledgeGraphOut)
def get_knowledge_graph(course_id: int, db: Session = Depends(get_db)) -> KnowledgeGraphOut:
    """读取课程知识图谱。"""

    course = _ensure_course_exists(db, course_id)
    nodes = crud.list_knowledge_nodes(db, course_id)
    if not nodes:
        raise HTTPException(status_code=404, detail="该课程尚未生成知识图谱")
    edges = crud.list_knowledge_edges(db, course_id)
    return _to_knowledge_graph_out(course=course, nodes=nodes, edges=edges)


@router.get("/prompt-template")
def get_prompt_template() -> dict:
    """返回当前 Prompt 模板，便于调试与比赛展示。"""

    return {
        "outline_prompt_template": PROMPT_TEMPLATE,
        "supplement_exercises_prompt_template": SUPPLEMENT_EXERCISES_PROMPT_TEMPLATE,
        "knowledge_graph_prompt_template": KNOWLEDGE_GRAPH_PROMPT_TEMPLATE,
    }


@router.post("/courses/{course_id}/generate-supplement-exercises", response_model=SupplementExerciseBatchOut)
def generate_supplement_exercises(course_id: int, db: Session = Depends(get_db)) -> SupplementExerciseBatchOut:
    """生成并保存 AI 补充练习题。"""

    course = _ensure_course_exists(db, course_id)
    generated_outline = crud.get_generated_outline(db, course_id)
    if not generated_outline:
        raise HTTPException(status_code=400, detail="请先生成教学大纲，再生成补充练习题")

    teaching_outline = _safe_parse_list(generated_outline.teaching_outline_json)
    core_knowledge_points = _safe_parse_list(generated_outline.core_knowledge_points_json)
    if not teaching_outline:
        raise HTTPException(status_code=400, detail="教学大纲为空，请先重新生成教学大纲")
    if not core_knowledge_points:
        raise HTTPException(status_code=400, detail="核心知识点为空，请先重新生成教学大纲")

    teacher_question_materials = crud.list_materials(db, course_id, material_type="question_bank")
    teacher_original_questions = _extract_teacher_questions(teacher_question_materials)

    try:
        llm_client = get_llm_client()
        generated = llm_client.generate_supplement_exercises(
            subject=course.subject,
            difficulty_level=course.difficulty_level,
            teaching_outline=teaching_outline,
            core_knowledge_points=core_knowledge_points,
            teacher_original_questions=teacher_original_questions,
        )
    except Exception as exc:
        # 比赛演示优先可用性：模型接口异常时，降级生成一批可自动批改的选择题。
        logger.exception("补充练习题模型调用失败，启用降级题目生成。course_id=%s", course_id)
        fallback_exercises = _build_fallback_supplement_exercises(
            subject=course.subject,
            difficulty_level=course.difficulty_level,
            core_knowledge_points=core_knowledge_points,
        )
        created = crud.replace_generated_exercises(db, course_id=course_id, exercises=fallback_exercises)
        return SupplementExerciseBatchOut(
            course_id=course_id,
            count=len(created),
            exercises=[_to_supplement_exercise_out(item) for item in created],
        )

    payload = generated.get("supplement_exercises", [])
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="模型返回题目格式异常")

    created = crud.replace_generated_exercises(db, course_id=course_id, exercises=payload)
    return SupplementExerciseBatchOut(
        course_id=course_id,
        count=len(created),
        exercises=[_to_supplement_exercise_out(item) for item in created],
    )


@router.get("/courses/{course_id}/generated-exercises", response_model=SupplementExerciseBatchOut)
def get_generated_exercises(course_id: int, db: Session = Depends(get_db)) -> SupplementExerciseBatchOut:
    """查看 AI 生成的补充练习题。"""

    _ensure_course_exists(db, course_id)
    exercises = crud.list_generated_exercises(db, course_id)
    return SupplementExerciseBatchOut(
        course_id=course_id,
        count=len(exercises),
        exercises=[_to_supplement_exercise_out(item) for item in exercises],
    )


def _ensure_course_exists(db: Session, course_id: int):
    """统一课程存在性检查。"""

    course = crud.get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


def _to_generated_outline_out(record) -> GeneratedOutlineOut:
    """将数据库记录转为响应结构。"""

    teaching_outline = _safe_parse_list(record.teaching_outline_json)
    core_points = _safe_parse_list(record.core_knowledge_points_json)
    return GeneratedOutlineOut(
        course_id=record.course_id,
        course_intro=record.course_intro,
        teaching_outline=teaching_outline,
        core_knowledge_points=core_points,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _to_knowledge_graph_out(course, nodes: list, edges: list, mastery_map: dict[str, float | None] | None = None):
    """将图谱数据库记录转换为响应结构。"""

    mastery_map = mastery_map or {}
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


def _safe_parse_list(raw: str) -> list[str]:
    try:
        payload = json.loads(raw)
        if isinstance(payload, list):
            return [str(item) for item in payload]
    except json.JSONDecodeError:
        pass
    return []


def _extract_teacher_questions(materials: list) -> list[str]:
    """从教师题目文本中提取可供模型参考的题干。"""

    questions: list[str] = []
    for material in materials:
        text = (material.extracted_text or "").strip()
        if not text:
            continue
        for line in text.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            if "||" in candidate:
                candidate = candidate.split("||", 1)[0].strip()
            if len(candidate) >= 4:
                questions.append(candidate)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in questions:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:12]


def _to_supplement_exercise_out(record) -> SupplementExerciseOut:
    """ORM -> 练习题响应结构。"""

    options = _safe_parse_list(record.options_json)
    return SupplementExerciseOut(
        id=record.id,
        course_id=record.course_id,
        source_type=record.source_type,
        question_type=record.question_type,
        question_text=record.question_text,
        options=options,
        answer=record.reference_answer,
        analysis=record.analysis,
        knowledge_point=record.knowledge_point,
    )


def _build_fallback_supplement_exercises(
    subject: str,
    difficulty_level: str,
    core_knowledge_points: list[str],
) -> list[dict[str, str | list[str]]]:
    """模型调用失败时的降级题目生成（固定 3 题，便于演示与自动批改）。"""

    points = [item.strip() for item in core_knowledge_points if item.strip()] or ["基础概念", "核心方法", "常见误区"]
    items: list[dict[str, str | list[str]]] = []
    for idx in range(3):
        point = points[idx % len(points)]
        items.append(
            {
                "question_type": "single_choice",
                "question_text": f"【降级题 {idx + 1}】在 {subject}（{difficulty_level}）学习中，关于“{point}”的说法正确的是？",
                "options": [
                    f"A. 先掌握“{point}”的定义与典型例题",
                    "B. 可以完全跳过该知识点",
                    "C. 只背答案不需要理解",
                    "D. 与本课程无关",
                ],
                "answer": "A",
                "analysis": f"该题为系统降级生成，建议结合课堂材料复习“{point}”后再做同类题。",
                "knowledge_point": point,
            }
        )
    return items
