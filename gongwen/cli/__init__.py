#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# CLI module - lazy import to avoid circular dependency
# main() 入口已迁移至 gongwen.cli.app（整改 C）；_legacy.py 保留兼容转发

# helpers 模块可直接导入
from gongwen.cli import helpers  # noqa: F401
