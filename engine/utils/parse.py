# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
统一值解析工具（跨模块#3 修复）。

消除 modifier.py / template_builder.py / style_profile.py 中的重复实现，
提供统一的值解析接口：pt / mm / indent / twips。
"""
from __future__ import annotations
from typing import Optional

import logging

logger = logging.getLogger(__name__)


def parse_pt(value: str | float | None) -> Optional[float]:
    """解析 '16pt' / 16 → pt。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("pt", "").strip())
    except (ValueError, TypeError):
        logger.warning(f"无法解析 pt 值: {value!r}")
        return None


def parse_mm(value: str | float | None) -> Optional[float]:
    """解析 '3.7cm' / '37mm' / 37 → mm。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    try:
        if "cm" in s:
            return float(s.replace("cm", "").strip()) * 10
        if "mm" in s:
            return float(s.replace("mm", "").strip())
        return float(s)
    except (ValueError, TypeError):
        logger.warning(f"无法解析 mm 值: {value!r}")
        return None


def parse_indent(value: str | float | None) -> Optional[float]:
    """解析 '2em' / '32pt' / 32 → pt（1em ≈ 16pt）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    try:
        if "em" in s:
            return float(s.replace("em", "").strip()) * 16
        return float(s.replace("pt", "").strip())
    except (ValueError, TypeError):
        logger.warning(f"无法解析缩进值: {value!r}")
        return None


def parse_twips_to_pt(val: str | int | None) -> Optional[float]:
    """缇(twips) → pt（1/20 磅）。NS14 修复：0 值返回 0.0 而非 None。"""
    if val is None:
        return None
    try:
        return round(int(val) / 20.0, 1)
    except (ValueError, TypeError):
        return None


def parse_twips_to_mm(val: str | int | None) -> Optional[float]:
    """缇(twips) → mm（1 英寸 = 1440 缇 = 25.4mm，1mm ≈ 56.6929 缇）。NS14 修复：0 值返回 0.0 而非 None。"""
    if val is None:
        return None
    try:
        return round(int(val) / 56.6929, 1)
    except (ValueError, TypeError):
        return None
