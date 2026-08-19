# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
"""
engine 包：独立发行版引擎核心。

P3-4：补充模块导出，便于外部按包导入核心入口。
"""
from __future__ import annotations

# 核心文档处理入口（惰性导入，避免循环依赖）


def get_generator() -> object:
    """延迟导入并返回 document generator 模块。"""
    from engine.core.document import generator
    return generator


def get_parser() -> object:
    """延迟导入并返回 document parser 模块。"""
    from engine.core.document import parser
    return parser


__all__ = ["get_generator", "get_parser"]
