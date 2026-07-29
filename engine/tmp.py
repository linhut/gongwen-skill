# -*- coding: utf-8 -*-
"""
临时文件管理 —— 所有临时文件统一置于 engine/tmp/，进程退出时自动清理。

用法：
  from tmp import get_tmp_path, cleanup_tmp
  path = get_tmp_path("中间稿件.docx")  # → engine/tmp/中间稿件.docx
  # 使用时...
  cleanup_tmp()  # 用完清理
"""
from __future__ import annotations
import atexit
import shutil
from pathlib import Path

TMP_DIR = Path(__file__).resolve().parent / "tmp"
_cleanup_registered = False


def ensure_tmp_dir() -> Path:
    """确保 tmp 目录存在并返回。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR


def get_tmp_path(filename: str) -> Path:
    """返回 tmp 目录下的一个文件路径（不创建文件）。"""
    return ensure_tmp_dir() / filename


def cleanup_tmp() -> None:
    """清空 tmp 目录（删除目录下所有文件，保留目录本身）。"""
    if TMP_DIR.exists():
        for item in TMP_DIR.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                pass


def register_cleanup() -> None:
    """注册进程退出时的自动清理（仅注册一次）。"""
    global _cleanup_registered
    if not _cleanup_registered:
        atexit.register(cleanup_tmp)
        _cleanup_registered = True
