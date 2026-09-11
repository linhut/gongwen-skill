#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""渲染验收命令（render）：docx → 逐页图片，供版面可视化检查。

复用 engine/docx_to_image（已存在的完整链路）：
  docx → PDF（LibreOffice 优先 / docx2pdf 降级）→ 图片（pdftoppm / PyMuPDF 降级）

用途：
  - 公文交付前渲染成图，检查分页、表格劈裂、签章区等仅"看了才知道"的版面问题
  - agent 场景推荐 --json 输出图片路径列表，由模型查看图片核验版面

只读命令，不修改原文档。
"""
from __future__ import annotations

import json
import logging

_logger = logging.getLogger(__name__)

_DEFAULT_OUTDIR = "render"
_DEFAULT_DPI = 150


def cmd_render(args):
    """render：docx → 逐页图片（只读，供版面可视化检查）。"""
    import sys
    import time
    from pathlib import Path

    t0 = time.time()
    input_path = getattr(args, "input", "")
    outdir = getattr(args, "output", "") or _DEFAULT_OUTDIR
    dpi = int(getattr(args, "dpi", _DEFAULT_DPI) or _DEFAULT_DPI)
    fmt = getattr(args, "format", "jpeg") or "jpeg"
    pages = getattr(args, "pages", "") or ""

    if not input_path:
        print("错误：请提供输入 .docx 路径，例如：python -m gongwen render 公文.docx", file=sys.stderr)
        return 2

    try:
        from engine.docx_to_image import docx_to_image
    except Exception as e:
        print(f"错误：docx_to_image 导入失败: {e}", file=sys.stderr)
        return 1

    try:
        images = docx_to_image(
            input_path, outdir, dpi=dpi, fmt=fmt, pages=pages,
        )
    except FileNotFoundError as e:
        print(f"错误：文件不存在 - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"错误：渲染失败 - {e}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps({
            "input": input_path,
            "outdir": str(Path(outdir)),
            "dpi": dpi,
            "format": fmt,
            "pages": pages,
            "count": len(images),
            "images": [str(p) for p in images],
        }, ensure_ascii=False, indent=2))
        return 0 if images else 1

    if not images:
        print("⚠️ 渲染失败：无法将 docx 转为图片。")
        print("  需要 LibreOffice（soffice）或 docx2pdf 提供 docx→PDF 链路。")
        print("  提示：Windows 可 `pip install docx2pdf`（依赖 Word）；或安装 LibreOffice。")
        return 1

    print(f"🖼️ 渲染完成: {len(images)} 页（{time.time() - t0:.1f}s）→ {Path(outdir)}/")
    for p in images:
        print(f"  {p}")
    print("提示：请查看图片核验版面（分页/表格劈裂/签章区等）。")
    return 0


def add_render_args(parser):
    """argparse 子命令注册（供 app.py 调用）。"""
    parser.add_argument("input", nargs="?", default="", help="输入 .docx 路径")
    parser.add_argument("-o", "--output", default="", help=f"输出目录（默认 {_DEFAULT_OUTDIR}/）")
    parser.add_argument("--dpi", type=int, default=_DEFAULT_DPI, help=f"渲染分辨率（默认 {_DEFAULT_DPI}）")
    parser.add_argument("--format", choices=["jpeg", "png"], default="jpeg", help="图片格式（默认 jpeg）")
    parser.add_argument("--pages", default="", help="页码范围，如 1-3（默认全部页）")
    parser.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
