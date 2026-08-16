#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen._bootstrap —— 统一的引擎路径引导和编码设置。

所有 CLI 入口点（_legacy.py、__main__.py、live_edit.py、conftest.py）
都应从此模块导入，而非各自执行 sys.path.insert，消除路径 hack 的重复。

这是 ARCH-03 的渐进式修复：保留 sys.path.insert 的同时集中管理，
未来可逐步迁移为 from engine.xxx import 的正规包导入。
"""
import sys
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

# 将 engine/ 加入模块搜索路径，使内部 `from core... / from utils... / from config`
# 的绝对导入生效——这是独立运行的关键。
_ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

# Windows 控制台中文输出保护（借鉴 docx-skill 强制 UTF-8 策略）
# 同时覆盖 stdout/stderr/stdin，确保中文路径、管道输入均无编码问题
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception as e:
    _logger.warning(f"控制台编码设置失败: {e}")
