"""知识图谱构建与掌握度计算服务。"""

from __future__ import annotations

from collections import defaultdict

from app.models import KnowledgeNode, Submission


def build_course_knowledge_graph(
    teaching_outline: list[str],
    core_knowledge_points: list[str],
) -> tuple[list[dict], list[dict]]:
    """根据教学大纲和核心知识点，构建最小可演示知识图谱。"""

    chapters = _dedupe_items(teaching_outline)
    points = _dedupe_items(core_knowledge_points)

    if not chapters and points:
        # 无教学大纲时，给知识点补一个总览节点，便于图结构展示
        chapters = ["课程总览"]

    nodes: list[dict] = []
    chapter_keys: list[str] = []
    point_keys: list[str] = []

    for idx, chapter in enumerate(chapters, start=1):
        node_key = f"CH_{idx}"
        chapter_keys.append(node_key)
        nodes.append(
            {
                "node_key": node_key,
                "node_name": chapter,
                "node_type": "chapter",
                "description": "教学章节节点",
                "level": 1,
                "order_index": idx,
            }
        )

    for idx, point in enumerate(points, start=1):
        node_key = f"KP_{idx}"
        point_keys.append(node_key)
        nodes.append(
            {
                "node_key": node_key,
                "node_name": point,
                "node_type": "knowledge_point",
                "description": "核心知识点节点",
                "level": 2,
                "order_index": idx,
            }
        )

    edges: list[dict] = []

    # 章节顺序关系
    for idx in range(len(chapter_keys) - 1):
        edges.append(
            {
                "source_key": chapter_keys[idx],
                "target_key": chapter_keys[idx + 1],
                "relation_type": "next",
                "weight": 1.0,
            }
        )

    # 知识点先修关系
    for idx in range(len(point_keys) - 1):
        edges.append(
            {
                "source_key": point_keys[idx],
                "target_key": point_keys[idx + 1],
                "relation_type": "prerequisite",
                "weight": 1.0,
            }
        )

    # 章节覆盖知识点
    if chapter_keys and point_keys:
        for idx, point_key in enumerate(point_keys):
            chapter_key = chapter_keys[idx % len(chapter_keys)]
            edges.append(
                {
                    "source_key": chapter_key,
                    "target_key": point_key,
                    "relation_type": "covers",
                    "weight": 1.0,
                }
            )

    return nodes, edges


def build_mastery_map(nodes: list[KnowledgeNode], submissions: list[Submission]) -> dict[str, float | None]:
    """按知识点节点计算掌握度（正确率 %）。"""

    point_node_by_name: dict[str, KnowledgeNode] = {}
    for node in nodes:
        if node.node_type == "knowledge_point":
            point_node_by_name[node.node_name.strip()] = node

    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})

    for submission in submissions:
        exercise = submission.exercise
        if not exercise:
            continue
        raw_point = (exercise.knowledge_point or "").strip()
        if not raw_point:
            continue

        matched_name = _match_node_name(raw_point, point_node_by_name)
        if not matched_name:
            continue

        stats[matched_name]["total"] += 1
        if submission.score >= 1.0:
            stats[matched_name]["correct"] += 1

    mastery_map: dict[str, float | None] = {}
    for node in nodes:
        if node.node_type != "knowledge_point":
            mastery_map[node.node_key] = None
            continue

        row = stats.get(node.node_name.strip())
        if not row or row["total"] <= 0:
            mastery_map[node.node_key] = None
            continue

        mastery_map[node.node_key] = round((row["correct"] / row["total"]) * 100, 2)

    return mastery_map


def _dedupe_items(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _match_node_name(raw_point: str, point_node_by_name: dict[str, KnowledgeNode]) -> str | None:
    """将作答记录知识点映射到图谱节点名称。"""

    if raw_point in point_node_by_name:
        return raw_point

    for name in point_node_by_name.keys():
        if raw_point in name or name in raw_point:
            return name
    return None
