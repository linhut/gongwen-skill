#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# 公文全流程处理专家 - gongwen-skill Python package

__version__ = "2.12.0"

# 对外展示名（单一事实来源）：面向人与模型的运行时展示文案统一引用此常量，
# 须与 SKILL.md frontmatter description 首句、.claude-plugin/plugin.json displayName、
# package.json / pyproject.toml description 保持同步（doctor 一致性检查会校验）。
DISPLAY_NAME = "公文全流程处理专家"

# Re-export everything from the legacy module for backward compatibility
# This allows: from gongwen import main, cmd_check, etc.
from gongwen._legacy import *  # noqa: F403
