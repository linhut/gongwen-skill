#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
gongwen._bootstrap —— 统一的引擎路径引导和编码设置。

ARCH-03 已修复：engine/ 下所有模块已改为 `from engine.xxx import` 正规包导入，
不再依赖 sys.path.insert。保留此处仅为向后兼容（旧代码或外部脚本可能仍
通过 `from core... import` 访问 engine 内部模块）。

所有 CLI 入口点从此模块导入编码设置。
"""
import sys
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

# ARCH-03 修复后：engine/ 已改为正规包导入（from engine.xxx import），
# 此 sys.path.insert 仅作为向后兼容回退（旧脚本/外部代码的 from core... import）
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
