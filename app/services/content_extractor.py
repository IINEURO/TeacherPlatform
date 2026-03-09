"""资源文件保存与文本提取工具。"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import UploadFile

from app.config import settings


async def save_upload_and_extract_text(course_id: int, upload: UploadFile) -> tuple[str, str, str]:
    """保存上传文件并尽力提取文本内容。"""

    course_dir = settings.upload_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)

    file_name = _safe_filename(upload.filename or f"upload_{int(datetime.utcnow().timestamp())}")
    target_path = course_dir / file_name

    data = await upload.read()
    target_path.write_bytes(data)

    extracted_text = extract_text_from_file(target_path)
    return file_name, str(target_path), extracted_text


def save_text_material(course_id: int, prefix: str, text: str) -> tuple[str, str, str]:
    """将前端文本内容保存为 txt 文件，并返回存储信息。"""

    course_dir = settings.upload_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_name = f"{prefix}_{timestamp}.txt"
    target_path = course_dir / file_name

    normalized = text.strip()
    target_path.write_text(normalized, encoding="utf-8")
    return file_name, str(target_path), normalized


def extract_text_from_file(file_path: Path) -> str:
    """根据文件后缀选择文本提取策略。"""

    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".md", ".csv", ".json"}:
        return _read_text_safely(file_path)
    if suffix == ".pptx":
        return _extract_pptx_text(file_path)
    if suffix in {".ppt", ".pdf", ".doc", ".docx"}:
        # 最小版不做复杂解析，保留空字符串即可
        return ""
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        # 最小版视频仅存储文件，不抽文本
        return ""

    return _read_text_safely(file_path)


def _read_text_safely(file_path: Path) -> str:
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def _extract_pptx_text(file_path: Path) -> str:
    """从 pptx 文件中抽取幻灯片文本节点。"""

    texts: list[str] = []
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            slide_files = sorted(name for name in zf.namelist() if name.startswith("ppt/slides/slide"))
            for slide_name in slide_files:
                xml_data = zf.read(slide_name)
                root = ET.fromstring(xml_data)
                for node in root.iter():
                    if node.tag.endswith("}t") and node.text:
                        value = node.text.strip()
                        if value:
                            texts.append(value)
    except Exception:
        return ""

    return "\n".join(texts)


def _safe_filename(raw_name: str) -> str:
    """过滤高风险字符，避免路径问题。"""

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    return safe[:200] or "upload_file"


def parse_question_bank_entries(raw_text: str) -> list[dict[str, str]]:
    """解析题库文本为结构化条目。

    支持两种格式：
    1) JSON 数组：[{question, answer, knowledge_point, question_type, options, analysis}]
    2) 文本行：题目||答案||知识点
    """

    text = raw_text.strip()
    if not text:
        return []

    # 格式1：JSON
    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            parsed: list[dict[str, str]] = []
            for item in payload:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                if not question:
                    continue
                parsed.append(
                    {
                        "question": question,
                        "answer": str(item.get("answer", "")).strip(),
                        "knowledge_point": str(item.get("knowledge_point", "")).strip(),
                        "question_type": str(item.get("question_type", "")).strip(),
                        "options": json.dumps(item.get("options", []), ensure_ascii=False),
                        "analysis": str(item.get("analysis", "")).strip(),
                    }
                )
            if parsed:
                return parsed
    except json.JSONDecodeError:
        pass

    # 格式2：文本行
    result: list[dict[str, str]] = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue

        if "||" in value:
            parts = [part.strip() for part in value.split("||")]
            result.append(
                {
                    "question": parts[0] if len(parts) >= 1 else "",
                    "answer": parts[1] if len(parts) >= 2 else "",
                    "knowledge_point": parts[2] if len(parts) >= 3 else "",
                    "question_type": "single_choice",
                    "options": "[]",
                    "analysis": "",
                }
            )
            continue

        # 无分隔符时把整行作为题干
        result.append(
            {
                "question": value,
                "answer": "",
                "knowledge_point": "",
                "question_type": "single_choice",
                "options": "[]",
                "analysis": "",
            }
        )

    return [item for item in result if item["question"]]
