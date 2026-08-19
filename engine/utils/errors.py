# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
统一错误处理策略（跨模块#4 修复）。

全局约定：
1. 边界层（CLI 入口 / 文件 I/O）：捕获并明确报告，向用户展示可操作信息
2. 内部逻辑层：失败时记日志（logger.debug/warning），可安全降级则降级
3. 规则引擎 / 修改器：不吞异常，向上抛给调用方处理，保证可追溯
4. 禁止裸 except: pass 吞掉关键错误——必须有日志或明确降级路径

提供辅助函数统一「安全执行 + 日志」模式。
"""
from __future__ import annotations
import logging
from typing import Callable, TypeVar, Optional

logger = logging.getLogger(__name__)

T = TypeVar("T")


def safe_call(fn: Callable[..., T], *args, on_error: Optional[str] = None,
              default: Optional[T] = None, log_level: int = logging.WARNING, **kwargs) -> Optional[T]:
    """
    安全执行：异常时记日志并按需降级返回默认值。

    Args:
        fn: 要执行的函数
        on_error: 错误描述（用于日志）
        default: 异常时返回的降级值
        log_level: 日志级别（默认 WARNING）
        *args, **kwargs: 透传给 fn

    Returns:
        fn 的正常返回值，或异常时的 default
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = on_error or f"执行 {getattr(fn, '__name__', fn)} 失败"
        logger.log(log_level, "%s: %s", msg, e)
        return default


def report_error(message: str, exc: Optional[Exception] = None, fatal: bool = False) -> None:
    """
    统一错误上报入口。

    Args:
        message: 面向用户的可读错误信息
        exc: 原始异常（可选，记录堆栈）
        fatal: True 时由调用方决定是否退出
    """
    if exc is not None:
        logger.error("%s: %s", message, exc)
    else:
        logger.error(message)
    # fatal 仅提示；是否 sys.exit 由调用方决定（保持职责分离）
