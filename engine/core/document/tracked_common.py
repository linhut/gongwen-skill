# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
tracked 修订公共工具（P2-10 修复：消除 tracked_changes / tracked_annotator 重复代码）。

两个模块此前各自定义了完全相同的 `_rev_id_counter` / `_next_rev_id` / `_reset_*`。
Word 修订标记的 w:id 要求全文档唯一，两个模块本就应共享同一计数器——提取到公共模块，
避免维护两份拷贝导致计数不同步。
"""
from __future__ import annotations

# 全局修订 ID 计数器（w:id 全文档唯一）
_rev_id_counter = [0]


def _next_rev_id() -> str:
    """生成下一个全局唯一修订 ID（w:id 全文档唯一）。"""
    _rev_id_counter[0] += 1
    return str(_rev_id_counter[0])


def _reset_rev_counter() -> None:
    """重置修订 ID 计数器（新文档会话开始时调用）。"""
    _rev_id_counter[0] = 0
