from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    aimlapi_key: str = ""
    db_path: Path = Path("./seedeval.db")
    artifacts_dir: Path = Path("./artifacts")
    log_level: str = "INFO"
    max_runs_per_day: int = 20


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        aimlapi_key=os.environ.get("AIMLAPI_KEY", ""),
        db_path=Path(os.environ.get("SEEDEVAL_DB_PATH", "./seedeval.db")),
        artifacts_dir=Path(os.environ.get("SEEDEVAL_ARTIFACTS_DIR", "./artifacts")),
        log_level=os.environ.get("SEEDEVAL_LOG_LEVEL", "INFO"),
        max_runs_per_day=int(os.environ.get("SEEDEVAL_MAX_RUNS_PER_DAY", "20")),
    )


def configure_logging() -> None:
    settings = get_settings()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def require_aimlapi_key() -> str:
    key = get_settings().aimlapi_key or os.environ.get("AIMLAPI_KEY", "")
    if not key:
        raise RuntimeError("AIMLAPI_KEY is required. Add it to .env or the environment.")
    return key
