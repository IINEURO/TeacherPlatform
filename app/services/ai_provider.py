"""AI 能力封装层。

目标：
- 上层业务完全不依赖具体厂商 SDK。
- 当前通过 OpenAI 兼容接口调用外部模型。
- 当环境变量未配置或请求失败时，自动回退到规则引擎，确保可演示。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class AIProvider:
    """AI 能力接口定义。"""

    def generate_course_assets(
        self,
        course_title: str,
        teaching_notes: str,
        ppt_text: str,
        uploaded_questions: list[dict[str, str]],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def grade_answer(self, question: str, reference_answer: str, student_answer: str) -> dict[str, Any]:
        raise NotImplementedError

    def generate_learning_report(
        self,
        course_title: str,
        weak_points: list[str],
        average_score: float,
    ) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class ExternalLLMProvider(AIProvider):
    """通过 OpenAI 兼容协议调用外部大模型。"""

    api_base_url: str
    api_key: str
    model: str
    timeout_seconds: int

    def generate_course_assets(
        self,
        course_title: str,
        teaching_notes: str,
        ppt_text: str,
        uploaded_questions: list[dict[str, str]],
    ) -> dict[str, Any]:
        default_payload = RuleBasedProvider().generate_course_assets(
            course_title,
            teaching_notes,
            ppt_text,
            uploaded_questions,
        )

        system_prompt = (
            "你是教学设计助手。请严格输出 JSON，对应字段："
            "outline(字符串), knowledge_summary(字符串), extra_exercises(数组，每项包含 question/answer/knowledge_point)。"
        )
        user_prompt = (
            f"课程标题：{course_title}\n"
            f"教学说明：\n{teaching_notes[:3000]}\n\n"
            f"PPT文本：\n{ppt_text[:3000]}\n\n"
            f"教师题库（可参考风格）：{json.dumps(uploaded_questions[:10], ensure_ascii=False)}"
        )
        return self._chat_json(system_prompt, user_prompt, default_payload)

    def grade_answer(self, question: str, reference_answer: str, student_answer: str) -> dict[str, Any]:
        default_payload = RuleBasedProvider().grade_answer(question, reference_answer, student_answer)

        system_prompt = (
            "你是客观评分助手。请输出 JSON，字段：score(0-100数字), feedback(字符串，简洁指出优点和改进点)。"
        )
        user_prompt = (
            f"题目：{question}\n"
            f"参考答案：{reference_answer}\n"
            f"学生答案：{student_answer}"
        )
        return self._chat_json(system_prompt, user_prompt, default_payload)

    def generate_learning_report(
        self,
        course_title: str,
        weak_points: list[str],
        average_score: float,
    ) -> dict[str, Any]:
        default_payload = RuleBasedProvider().generate_learning_report(course_title, weak_points, average_score)

        system_prompt = (
            "你是学习分析助手。请输出 JSON，字段：performance_level(字符串),"
            "suggestion(字符串), personalized_exercises(数组，每项包含 question/answer/knowledge_point)。"
        )
        user_prompt = (
            f"课程：{course_title}\n"
            f"平均分：{average_score:.1f}\n"
            f"薄弱知识点：{', '.join(weak_points) if weak_points else '暂无明显薄弱点'}"
        )
        return self._chat_json(system_prompt, user_prompt, default_payload)

    def _chat_json(self, system_prompt: str, user_prompt: str, default_payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            candidate = json.loads(content)
            return _merge_defaults(candidate, default_payload)
        except Exception:
            # 比赛演示阶段：模型请求失败时继续可用
            return default_payload


class RuleBasedProvider(AIProvider):
    """无外部依赖的兜底策略。"""

    def generate_course_assets(
        self,
        course_title: str,
        teaching_notes: str,
        ppt_text: str,
        uploaded_questions: list[dict[str, str]],
    ) -> dict[str, Any]:
        combined = f"{teaching_notes}\n{ppt_text}".strip()
        chunks = _split_sentences(combined)
        summary_points = chunks[:6] if chunks else ["本节课围绕核心概念、示例与练习展开。"]

        outline_lines = [
            f"1. 课程导入：{course_title}",
            "2. 关键概念讲解",
            "3. 示例演示与课堂互动",
            "4. 课堂练习与讲评",
            "5. 课后巩固与延伸",
        ]
        knowledge_summary = "\n".join(f"- {line}" for line in summary_points)

        extra_exercises: list[dict[str, str]] = []
        for idx, point in enumerate(summary_points[:3], start=1):
            extra_exercises.append(
                {
                    "question": f"请结合课堂内容，说明第{idx}个知识点：{point}",
                    "answer": f"围绕“{point}”给出定义、特点和应用场景。",
                    "knowledge_point": f"知识点{idx}",
                }
            )

        # 若教师已有题目，则再补 1 题迁移题
        if uploaded_questions:
            seed_question = uploaded_questions[0].get("question", "课堂核心知识")
            extra_exercises.append(
                {
                    "question": f"迁移应用：将“{seed_question}”改写为生活化案例并作答。",
                    "answer": "应包含问题重述、关键步骤、结论三部分。",
                    "knowledge_point": "迁移应用",
                }
            )

        return {
            "outline": "\n".join(outline_lines),
            "knowledge_summary": knowledge_summary,
            "extra_exercises": extra_exercises,
        }

    def grade_answer(self, question: str, reference_answer: str, student_answer: str) -> dict[str, Any]:
        reference = _normalize_text(reference_answer)
        student = _normalize_text(student_answer)

        if not student:
            return {"score": 0.0, "feedback": "答案为空，请至少给出核心观点。"}

        if reference and student == reference:
            return {"score": 98.0, "feedback": "答案与参考答案高度一致，表达清晰。"}

        # 使用词汇重合度做最小可行评分
        ref_tokens = set(reference.split()) if reference else set()
        stu_tokens = set(student.split())

        if ref_tokens:
            overlap = len(ref_tokens & stu_tokens) / max(1, len(ref_tokens))
            score = 45 + overlap * 50
        else:
            # 无参考答案时，按长度和结构给基础分
            score = min(90.0, 50 + len(student_answer.strip()) / 4)

        score = max(0.0, min(100.0, round(score, 1)))
        feedback = "回答较完整，建议补充定义、关键步骤和结论以提高准确性。"
        if score >= 85:
            feedback = "回答较好，逻辑清楚。可继续增加案例细节。"
        elif score < 60:
            feedback = "核心要点覆盖不足，建议回顾知识点后重答。"

        return {"score": score, "feedback": feedback}

    def generate_learning_report(
        self,
        course_title: str,
        weak_points: list[str],
        average_score: float,
    ) -> dict[str, Any]:
        if average_score >= 85:
            level = "优秀"
        elif average_score >= 70:
            level = "良好"
        else:
            level = "待提升"

        focus = weak_points if weak_points else ["综合应用"]
        exercises = [
            {
                "question": f"针对“{point}”，写出定义并给出一个应用示例。",
                "answer": "答案应包含概念解释、关键特征、应用场景。",
                "knowledge_point": point,
            }
            for point in focus[:3]
        ]

        suggestion = (
            f"当前水平：{level}。建议每天用 20 分钟复盘课程《{course_title}》的核心概念，"
            "先做基础题，再做迁移题。"
        )

        return {
            "performance_level": level,
            "suggestion": suggestion,
            "personalized_exercises": exercises,
        }


def get_ai_provider() -> AIProvider:
    """工厂方法：优先使用外部模型，失败可回退。"""

    if settings.llm_api_key:
        return ExternalLLMProvider(
            api_base_url=settings.llm_api_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return RuleBasedProvider()


def _merge_defaults(candidate: dict[str, Any], default_payload: dict[str, Any]) -> dict[str, Any]:
    """确保模型返回缺字段时也能满足业务结构。"""

    merged: dict[str, Any] = dict(default_payload)
    for key, value in candidate.items():
        merged[key] = value
    return merged


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    pieces = re.split(r"[。！？!?；;\n]", normalized)
    return [piece.strip() for piece in pieces if piece.strip()]


def _normalize_text(text: str) -> str:
    value = text.lower()
    value = re.sub(r"[^\w\u4e00-\u9fa5\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value
