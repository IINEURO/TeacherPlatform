"""大模型调用封装。

- 单独封装 HTTP 调用，便于替换供应商。
- 默认使用 DeepSeek（OpenAI 兼容协议）。
- 提供基础 JSON 容错，避免模型输出格式波动导致流程中断。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

PROMPT_TEMPLATE = """你是一位资深教学设计专家。请根据输入内容输出严格 JSON，不要输出任何额外说明文字。

输入内容：
- 教学目标：{teaching_objective}
- 教学说明文本：{teaching_note_text}
- PPT提取文本：{ppt_text}

输出 JSON 结构必须为：
{{
  "course_intro": "课程简介（80-180字）",
  "teaching_outline": ["第1部分...", "第2部分...", "第3部分..."],
  "core_knowledge_points": ["知识点1", "知识点2", "知识点3"]
}}

要求：
1. teaching_outline 至少 4 条，按教学先后顺序组织。
2. core_knowledge_points 至少 5 条，尽量具体可教。
3. 必须返回合法 JSON。
"""

SUPPLEMENT_EXERCISES_PROMPT_TEMPLATE = """你是一位教学测评设计专家。请根据输入生成 3 到 5 道补充练习题，并严格输出 JSON，不要输出任何额外文字。

输入信息：
- 学科：{subject}
- 难度：{difficulty_level}
- 教学大纲：{teaching_outline}
- 核心知识点：{core_knowledge_points}
- 教师原始题目（可参考风格）：{teacher_questions}

输出 JSON 结构必须为：
{{
  "supplement_exercises": [
    {{
      "question_type": "single_choice",
      "question_text": "题干",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "analysis": "解析",
      "knowledge_point": "所属知识点标签"
    }}
  ]
}}

要求：
1. 共 3-5 题，优先 single_choice（至少 3 题为选择题）。
2. 选择题必须提供 4 个选项，answer 仅返回 A/B/C/D。
3. 题目要覆盖不同知识点。
4. 必须输出合法 JSON。
"""

TARGETED_PRACTICE_PROMPT_TEMPLATE = """你是一位教学辅导老师。请围绕薄弱知识点生成 1 到 2 道补练题，并严格输出 JSON，不要输出任何额外文字。

输入信息：
- 学科：{subject}
- 难度：{difficulty_level}
- 薄弱知识点：{weak_points}

输出 JSON 结构必须为：
{{
  "supplement_exercises": [
    {{
      "question_type": "single_choice",
      "question_text": "题干",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "analysis": "解析",
      "knowledge_point": "所属知识点标签"
    }}
  ]
}}

要求：
1. 只生成 1-2 题，优先 single_choice。
2. 题目必须紧扣薄弱知识点。
3. 必须输出合法 JSON。
"""


@dataclass
class LLMClient:
    """最小可用 LLM 客户端。"""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 30

    def generate_teaching_outline(
        self,
        teaching_objective: str,
        teaching_note_text: str,
        ppt_text: str,
    ) -> dict[str, Any]:
        """生成课程简介、教学大纲、核心知识点。"""

        prompt = PROMPT_TEMPLATE.format(
            teaching_objective=(teaching_objective.strip() or "（未提供）")[:1200],
            teaching_note_text=(teaching_note_text.strip() or "（未提供）")[:12000],
            ppt_text=(ppt_text.strip() or "（未提供）")[:12000],
        )

        raw_output = self._chat(prompt)
        parsed = parse_json_with_fallback(raw_output)
        normalized = normalize_generation_result(parsed)
        normalized["_raw_output"] = raw_output
        normalized["_prompt"] = prompt
        return normalized

    def generate_supplement_exercises(
        self,
        subject: str,
        difficulty_level: str,
        teaching_outline: list[str],
        core_knowledge_points: list[str],
        teacher_original_questions: list[str],
    ) -> dict[str, Any]:
        """生成补充练习题。"""

        prompt = SUPPLEMENT_EXERCISES_PROMPT_TEMPLATE.format(
            subject=(subject.strip() or "通用学科")[:80],
            difficulty_level=(difficulty_level.strip() or "中等")[:30],
            teaching_outline=json.dumps(teaching_outline[:8], ensure_ascii=False),
            core_knowledge_points=json.dumps(core_knowledge_points[:12], ensure_ascii=False),
            teacher_questions=json.dumps(teacher_original_questions[:10], ensure_ascii=False),
        )

        raw_output = self._chat(prompt)
        parsed = parse_json_with_fallback(raw_output)
        normalized = normalize_supplement_exercises_result(
            payload=parsed,
            subject=subject,
            difficulty_level=difficulty_level,
            core_knowledge_points=core_knowledge_points,
        )
        normalized["_raw_output"] = raw_output
        normalized["_prompt"] = prompt
        return normalized

    def generate_targeted_practice(
        self,
        subject: str,
        difficulty_level: str,
        weak_points: list[str],
        max_count: int = 2,
    ) -> dict[str, Any]:
        """针对薄弱知识点生成 1-2 道补练题。"""

        prompt = TARGETED_PRACTICE_PROMPT_TEMPLATE.format(
            subject=(subject.strip() or "通用学科")[:80],
            difficulty_level=(difficulty_level.strip() or "中等")[:30],
            weak_points=json.dumps(weak_points[:8], ensure_ascii=False),
        )

        raw_output = self._chat(prompt)
        parsed = parse_json_with_fallback(raw_output)
        normalized = normalize_targeted_practice_result(
            payload=parsed,
            subject=subject,
            difficulty_level=difficulty_level,
            weak_points=weak_points,
            max_count=max_count,
        )
        normalized["_raw_output"] = raw_output
        normalized["_prompt"] = prompt
        return normalized

    def _chat(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY（或 LLM_API_KEY）")

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是教学设计助手，输出必须是 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = (exc.response.text or "").strip()
            preview = body[:300] if body else exc.response.reason_phrase
            raise RuntimeError(f"模型接口错误 HTTP {exc.response.status_code}: {preview}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"模型接口连接失败: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise RuntimeError("模型接口返回非 JSON 内容") from exc

        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"模型接口返回结构异常: {str(data)[:300]}") from exc


def get_llm_client() -> LLMClient:
    """从配置创建客户端实例。"""

    return LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def parse_json_with_fallback(raw_output: str) -> dict[str, Any]:
    """解析模型返回；若非合法 JSON，进行基础容错。"""

    cleaned = raw_output.strip()
    if not cleaned:
        return {}

    # 情况1：直接是 JSON
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 情况2：包裹在 markdown code block
    fenced = re.search(r"```json\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        snippet = fenced.group(1)
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 情况3：截取首尾大括号
    left = cleaned.find("{")
    right = cleaned.rfind("}")
    if left != -1 and right != -1 and right > left:
        snippet = cleaned[left : right + 1]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 兜底：保留原文，后续 normalize 时生成最小结构
    return {"raw_text": cleaned}


def normalize_generation_result(payload: dict[str, Any]) -> dict[str, Any]:
    """统一返回结构，保证上游可稳定写库与展示。"""

    course_intro = str(payload.get("course_intro", "")).strip()

    teaching_outline = payload.get("teaching_outline", [])
    if isinstance(teaching_outline, str):
        teaching_outline = [line.strip() for line in teaching_outline.splitlines() if line.strip()]
    if not isinstance(teaching_outline, list):
        teaching_outline = []
    teaching_outline = [str(item).strip() for item in teaching_outline if str(item).strip()]

    core_points = payload.get("core_knowledge_points", [])
    if isinstance(core_points, str):
        core_points = [line.strip() for line in core_points.splitlines() if line.strip()]
    if not isinstance(core_points, list):
        core_points = []
    core_points = [str(item).strip() for item in core_points if str(item).strip()]

    # 当模型完全未按 JSON 输出时，给最小可展示结果
    raw_text = str(payload.get("raw_text", "")).strip()
    if not course_intro and raw_text:
        course_intro = raw_text[:180]
    if not teaching_outline and raw_text:
        teaching_outline = ["请根据课程内容补充教学环节（模型返回非标准JSON，已自动降级处理）"]
    if not core_points:
        core_points = ["请根据课程材料补充核心知识点"]

    return {
        "course_intro": course_intro or "暂无课程简介",
        "teaching_outline": teaching_outline,
        "core_knowledge_points": core_points,
    }


def normalize_supplement_exercises_result(
    payload: dict[str, Any],
    subject: str,
    difficulty_level: str,
    core_knowledge_points: list[str],
) -> dict[str, Any]:
    """统一补充练习题输出结构。"""

    raw_items = payload.get("supplement_exercises")
    if not isinstance(raw_items, list):
        raw_items = payload.get("exercises")
    if not isinstance(raw_items, list):
        raw_items = []

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        question_text = str(item.get("question_text", "")).strip()
        if not question_text:
            continue

        question_type = str(item.get("question_type", "single_choice")).strip().lower()
        if question_type in {"choice", "mcq", "single", "single-choice"}:
            question_type = "single_choice"
        if question_type not in {"single_choice", "multiple_choice", "short_answer"}:
            question_type = "single_choice"

        options = item.get("options", [])
        if isinstance(options, str):
            options = [line.strip() for line in options.splitlines() if line.strip()]
        if not isinstance(options, list):
            options = []
        options = [str(opt).strip() for opt in options if str(opt).strip()]

        answer = str(item.get("answer", "")).strip()
        analysis = str(item.get("analysis", "")).strip()
        knowledge_point = str(item.get("knowledge_point", "")).strip()

        # 选择题兜底处理，确保便于演示和自动批改
        if question_type in {"single_choice", "multiple_choice"}:
            if len(options) < 4:
                options = _default_options_by_answer(answer)
            answer = _normalize_choice_answer(answer)
            if answer not in {"A", "B", "C", "D"}:
                answer = "A"

        normalized.append(
            {
                "question_type": question_type,
                "question_text": question_text,
                "options": options if question_type in {"single_choice", "multiple_choice"} else [],
                "answer": answer,
                "analysis": analysis or "建议回顾相关知识点后再完成同类题。",
                "knowledge_point": knowledge_point or _pick_knowledge_point(core_knowledge_points, len(normalized)),
            }
        )

    # 数量兜底：控制在 3~5
    if len(normalized) > 5:
        normalized = normalized[:5]
    while len(normalized) < 3:
        idx = len(normalized)
        kp = _pick_knowledge_point(core_knowledge_points, idx)
        normalized.append(_build_fallback_choice(subject, difficulty_level, kp, idx + 1))

    # 至少 3 题为选择题，便于演示和自动批改
    choice_count = sum(1 for item in normalized if item["question_type"] in {"single_choice", "multiple_choice"})
    if choice_count < 3:
        for item in normalized:
            if item["question_type"] in {"single_choice", "multiple_choice"}:
                continue
            item["question_type"] = "single_choice"
            item["options"] = _default_options_by_answer(item.get("answer", "A"))
            item["answer"] = _normalize_choice_answer(str(item.get("answer", "A")))
            choice_count += 1
            if choice_count >= 3:
                break

    return {"supplement_exercises": normalized}


def normalize_targeted_practice_result(
    payload: dict[str, Any],
    subject: str,
    difficulty_level: str,
    weak_points: list[str],
    max_count: int,
) -> dict[str, Any]:
    """统一薄弱点补练题输出，数量限制在 1-2。"""

    base = normalize_supplement_exercises_result(
        payload=payload,
        subject=subject,
        difficulty_level=difficulty_level,
        core_knowledge_points=weak_points,
    )
    items = list(base.get("supplement_exercises", []))
    if not items:
        items = [_build_fallback_choice(subject, difficulty_level, _pick_knowledge_point(weak_points, 0), 1)]

    limit = max(1, min(2, int(max_count)))
    return {"supplement_exercises": items[:limit]}


def _normalize_choice_answer(answer: str) -> str:
    value = answer.strip().upper()
    if not value:
        return "A"
    first = value[0]
    return first if first in {"A", "B", "C", "D"} else "A"


def _default_options_by_answer(answer: str) -> list[str]:
    normalized = _normalize_choice_answer(answer)
    options = ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"]
    if normalized == "B":
        options[1] = "B. 正确选项"
    elif normalized == "C":
        options[2] = "C. 正确选项"
    elif normalized == "D":
        options[3] = "D. 正确选项"
    else:
        options[0] = "A. 正确选项"
    return options


def _pick_knowledge_point(core_knowledge_points: list[str], index: int) -> str:
    if not core_knowledge_points:
        return "核心知识点"
    return core_knowledge_points[index % len(core_knowledge_points)]


def _build_fallback_choice(subject: str, difficulty_level: str, knowledge_point: str, index: int) -> dict[str, Any]:
    return {
        "question_type": "single_choice",
        "question_text": f"（{subject}/{difficulty_level}）第{index}题：下列关于“{knowledge_point}”的说法，哪一项最准确？",
        "options": ["A. 符合定义并可应用", "B. 只在少数场景成立", "C. 与知识点无关", "D. 完全错误表述"],
        "answer": "A",
        "analysis": "题目用于检测对核心概念的理解与应用能力。",
        "knowledge_point": knowledge_point,
    }
