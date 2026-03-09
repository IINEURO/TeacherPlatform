"""应用配置。

本项目优先保证比赛原型可运行，因此使用简单的环境变量读取方式，
并提供合理默认值，便于开箱即用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_exists() -> None:
    """最小 .env 加载器。

    仅在变量未被系统环境显式设置时，才使用 .env 中的值覆盖，
    便于比赛演示时直接在项目根目录放置 .env 文件。
    """

    base_dir = Path(__file__).resolve().parents[1]
    env_path = base_dir / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_exists()


@dataclass(frozen=True)
class Settings:
    """运行配置。"""

    project_name: str = "AI辅助教学系统原型"
    base_dir: Path = Path(__file__).resolve().parents[1]
    data_dir: Path = base_dir / "data"
    upload_dir: Path = data_dir / "uploads"
    db_path: Path = data_dir / "app.db"

    # 外部大模型接口（默认 DeepSeek，OpenAI 兼容协议）
    llm_api_base_url: str = os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
    llm_api_key: str = os.getenv("DEEPSEEK_API_KEY", os.getenv("LLM_API_KEY", ""))
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_timeout_seconds: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


settings = Settings()

# 启动时确保目录存在
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
