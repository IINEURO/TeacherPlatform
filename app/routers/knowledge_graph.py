"""知识图谱可视化接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.schemas import KnowledgeGraphVisualLinkOut, KnowledgeGraphVisualNodeOut, KnowledgeGraphVisualOut
from app.services.knowledge_graph import build_mastery_map

router = APIRouter(tags=["knowledge_graph"])


@router.get("/knowledge_graph/{course_id}", response_model=KnowledgeGraphVisualOut)
def get_knowledge_graph_visual(
    course_id: int,
    student_name: str | None = None,
    db: Session = Depends(get_db),
) -> KnowledgeGraphVisualOut:
    """返回 ECharts graph 所需数据结构。"""

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

    node_items = [
        KnowledgeGraphVisualNodeOut(
            id=item.id,
            name=item.node_name,
            mastery_rate=mastery_map.get(item.node_key),
            color=_resolve_node_color(node_type=item.node_type, mastery_rate=mastery_map.get(item.node_key)),
            node_type=item.node_type,
        )
        for item in nodes
    ]

    node_id_set = {item.id for item in nodes}
    link_items = [
        KnowledgeGraphVisualLinkOut(
            source=item.source_node_id,
            target=item.target_node_id,
            relation=item.relation_type,
        )
        for item in edges
        if item.source_node_id in node_id_set and item.target_node_id in node_id_set
    ]

    return KnowledgeGraphVisualOut(nodes=node_items, links=link_items)


def _resolve_node_color(node_type: str, mastery_rate: float | None) -> str:
    """根据节点类型与掌握度映射展示色。"""

    if node_type == "chapter":
        return "#4f46e5"
    if mastery_rate is None:
        return "#94a3b8"
    if mastery_rate >= 80:
        return "#16a34a"
    if mastery_rate >= 60:
        return "#f59e0b"
    return "#ef4444"
