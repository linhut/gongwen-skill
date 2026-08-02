# -*- coding: utf-8 -*-
"""
pytest 共享配置（P3-34：统一 sys.path 管理与共享 fixture）。

将 engine/ 加入模块搜索路径，使测试中的 `from core... / from utils... /
from config` 绝对导入生效，避免各测试文件重复 sys.path.insert。
"""
import sys
from pathlib import Path

import pytest

_ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

# 确保规则目录可写（config 导入时会自动创建，此处仅做一次显式导入验证）
import config  # noqa: F401


@pytest.fixture
def minimal_model():
    """构造一个最小可用的 DocumentModel（标题 + 正文 + 署名 + 日期）。"""
    from core.document.models import (
        DocumentModel, DocumentMetadata, PageSetup,
        Paragraph, ParagraphFormat, Run, RunFormat,
    )
    return DocumentModel(
        metadata=DocumentMetadata(title="测试文档"),
        page_setup=PageSetup(
            paper_width_mm=210, paper_height_mm=297,
            margin_top_mm=37, margin_bottom_mm=35,
            margin_left_mm=28, margin_right_mm=26,
        ),
        paragraphs=[
            Paragraph(index=0, text="关于测试的通知", role="title", is_heading=True, heading_level=0,
                      runs=[Run(index=0, text="关于测试的通知", format=RunFormat(font_name="方正小标宋简体", font_size_pt=22.0))],
                      format=ParagraphFormat(alignment="center")),
            Paragraph(index=1, text="各单位：", role="recipient",
                      runs=[Run(index=0, text="各单位：", format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
                      format=ParagraphFormat()),
            Paragraph(index=2, text="现将有关事项通知如下。", role="body",
                      runs=[Run(index=0, text="现将有关事项通知如下。", format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
                      format=ParagraphFormat(alignment="justify")),
            Paragraph(index=3, text="测试单位", role="signature",
                      runs=[Run(index=0, text="测试单位", format=RunFormat(font_name="仿宋_GB2312", font_size_pt=18.0))],
                      format=ParagraphFormat(alignment="center")),
            Paragraph(index=4, text="2026年8月3日", role="date",
                      runs=[Run(index=0, text="2026年8月3日", format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
                      format=ParagraphFormat(alignment="right")),
        ],
    )
