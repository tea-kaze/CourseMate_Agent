"""导入演示资料：将 data/demo 下的文档按文件名「课程名-主题.md」自动归入对应课程。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loguru import logger  # noqa: E402

from coursemate.app.ingestion import ingest_file  # noqa: E402
from coursemate.db.session import init_db  # noqa: E402


def course_name_from_filename(filename: str) -> str:
    """从文件名推导课程名：取「-」前的部分，如「操作系统-进程与调度.md」→ 操作系统。"""
    return Path(filename).stem.split("-", 1)[0]


def main() -> None:
    init_db()
    demo_dir = ROOT / "data" / "demo"
    for path in sorted(demo_dir.glob("*")):
        if path.suffix.lower() not in {".pdf", ".md", ".markdown", ".txt"}:
            continue
        course_name = course_name_from_filename(path.name)
        logger.info("正在入库：{}（课程：{}）", path.name, course_name)
        result = ingest_file(path.name, path.read_bytes(), course_name=course_name)
        logger.info("完成：{}", result)


if __name__ == "__main__":
    main()
