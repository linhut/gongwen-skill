# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 独立引擎配置
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本文件为独立发行版专用配置，替代原项目中依赖 PyInstaller / Electron /
# SQLite 的 backend/config.py。它只解析路径，不引入任何数据库或桌面端耦合，
# 使规则引擎可在任意环境下独立运行。
"""
路径解析（可移植）：

  BASE_DIR      —— 仓库根目录（rules/official 所在处），只读资源
  APP_DATA_DIR  —— 可写运行时数据（日志、用户/自定义规则）

可写目录默认位于用户主目录下的 ``~/.gongwen-skill``，可用环境变量
``GONGWEN_DATA_DIR`` 覆盖。这样无论从何处克隆、以何身份运行，
自定义规则与日志都能落到一个稳定、可写的位置。
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
#  BASE_DIR：仓库根目录（engine/ 的上一级），只读资源
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
#  APP_DATA_DIR：可写运行时数据目录
# ---------------------------------------------------------------------------
_env_data = os.environ.get("GONGWEN_DATA_DIR")
if _env_data:
    APP_DATA_DIR = Path(_env_data).expanduser().resolve()
else:
    APP_DATA_DIR = Path.home() / ".gongwen-skill"

# ---------------------------------------------------------------------------
#  只读规则目录（随仓库分发）
# ---------------------------------------------------------------------------
RULES_DIR = BASE_DIR / "rules" / "official"

# ---------------------------------------------------------------------------
#  可写规则目录（三层优先级：official < custom < user）
# ---------------------------------------------------------------------------
CUSTOM_RULES_DIR = APP_DATA_DIR / "custom_rules"
USER_RULES_DIR = APP_DATA_DIR / "user_rules"

LOG_DIR = APP_DATA_DIR / "logs"
SESSION_DIR = APP_DATA_DIR / "sessions"
TMP_DIR = Path(__file__).resolve().parent / "tmp"

# ---------------------------------------------------------------------------
#  自动创建可写目录
# ---------------------------------------------------------------------------
import logging

_log = logging.getLogger(__name__)

for _d in (APP_DATA_DIR, CUSTOM_RULES_DIR, USER_RULES_DIR, LOG_DIR, SESSION_DIR, TMP_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("无法创建目录 %s: %s，功能将自动降级", _d, exc)
