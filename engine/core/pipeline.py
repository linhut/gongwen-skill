#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
engine.core.pipeline -- 轻量 Pipeline 编排层（O9 试点）。

设计要点（对应设计文档 O9）：
- 一次解析（parse）-> 依次执行各阶段 -> 一次生成（generate）
- PipelineContext 全程携带 model（parse 后填充，source_path 保留），
  保证 generate_docx 的"源文档保留策略"（加载原始 .docx 作基底）始终生效
- 阶段（Stage）为普通函数：fn(ctx) -> None，就地更新 ctx；无需继承/装饰器
- 本模块与 CLI 无耦合：业务阶段定义在命令模块（如 gongwen.cli.review_cmds），
  避免 engine -> cli 反向依赖

使用示例：
    from engine.core.pipeline import Pipeline, PipelineContext

    ctx = PipelineContext(input_path=Path("a.docx"), doc_type="letter", is_json=True)
    pipe = Pipeline("full-review")
    pipe.add_stage("parse_and_fix", stage_parse_and_fix)
    pipe.add_stage("load_changes", stage_load_changes)
    pipe.add_stage("inject_comments", stage_inject_comments)
    ctx = pipe.run(ctx)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple


@dataclass
class PipelineContext:
    """贯穿管道的共享上下文。

    关键字段：
    - model：DocumentModel（parse 后填充；source_path 保留原 .docx 路径）
    - results：阶段产物与统计的收纳箱（如 fixed_issues / comments / verified）
    - args：原始 argparse.Namespace（或等价对象），阶段可读取未显式建模的参数
    """

    input_path: Path
    doc_type: Optional[str] = None
    model: Any = None
    changes: List[dict] = field(default_factory=list)
    output: Optional[Path] = None
    args: Any = None
    is_json: bool = False
    results: dict = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """写入阶段产物（results 收纳箱）。"""
        self.results[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.results.get(key, default)


class Pipeline:
    """按注册顺序执行阶段的编排器。

    阶段函数签名：fn(ctx: PipelineContext) -> None
    - 每个阶段可读取/修改 ctx（model、changes、results 等）
    - 阶段抛异常会中断管道（由调用方捕获并处理）
    - run() 返回执行完毕的 ctx，调用方据此读取产物与统计
    """

    def __init__(self, name: str = "pipeline") -> None:
        self.name = name
        self._stages: List[Tuple[str, Callable[[PipelineContext], None]]] = []

    def add_stage(
        self, name: str, fn: Callable[[PipelineContext], None]
    ) -> "Pipeline":
        """追加一个阶段（支持链式调用）。"""
        self._stages.append((name, fn))
        return self

    @property
    def stage_names(self) -> List[str]:
        return [n for n, _ in self._stages]

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """按注册顺序执行全部阶段，返回同一 ctx（含执行记录）。"""
        executed = []
        for name, fn in self._stages:
            fn(ctx)
            executed.append(name)
        ctx.results["stages"] = executed
        ctx.results["pipeline"] = self.name
        return ctx
