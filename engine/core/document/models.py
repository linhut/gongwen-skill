# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
"""
Pydantic data models for the intermediate document representation.
All operations work on this JSON model -- never directly on python-docx objects.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


# ---------------------------------------------------------------------------
#  Primitives
# ---------------------------------------------------------------------------
from pydantic import field_validator


def _validate_rgb_color(v) -> str:
    """S6 修复：校验 RGB 颜色格式（RRGGBB 或 #RRGGBB），只校验不改写值。"""
    if v is None:
        return v
    s = str(v).lstrip('#')
    if len(s) != 6 or not all(c in '0123456789ABCDEFabcdef' for c in s):
        raise ValueError(f"非法 RGB 颜色值: {v!r}（应为 6 位十六进制 RRGGBB）")
    return v  # 保持原值，不规范化（避免破坏向后兼容）


def _validate_heading_level(v) -> int | None:
    """N1 修复：heading_level 允许 0-9（0=公文大标题，1-9=Word 标题层级）。"""
    if v is None:
        return None
    v = int(v)
    if not (0 <= v <= 9):
        raise ValueError(f"heading_level 必须在 0-9 之间，实际 {v}")
    return v


class RunFormat(BaseModel):
    """Formatting information for a single text run."""
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    strikethrough: Optional[bool] = None
    color: Optional[str] = None

    # S6: RGB 颜色校验（Pydantic V2 field_validator）
    @field_validator('color')
    @classmethod
    def _check_color(cls, v):
        return _validate_rgb_color(v)


class Run(BaseModel):
    """A contiguous span of text sharing the same formatting."""
    index: int = 0
    text: str
    format: RunFormat = Field(default_factory=RunFormat)


class ParagraphFormat(BaseModel):
    """Paragraph-level formatting."""
    alignment: Optional[str] = None          # left / center / right / justify
    first_line_indent_pt: Optional[float] = None
    left_indent_pt: Optional[float] = None
    right_indent_pt: Optional[float] = None
    space_before_pt: Optional[float] = None
    space_after_pt: Optional[float] = None
    line_spacing_pt: Optional[float] = None
    line_spacing_rule: Optional[str] = None  # multiple / exact / atLeast


class Paragraph(BaseModel):
    """A single paragraph in the document."""
    index: int
    text: str
    style_name: Optional[str] = None
    is_heading: bool = False
    heading_level: Optional[int] = None      # 1-9 for Word heading levels
    role: Optional[str] = None               # 段落角色: title/recipient/body/signature/date/attachment/cc/notes
    runs: list[Run] = Field(default_factory=list)
    format: ParagraphFormat = Field(default_factory=ParagraphFormat)
    page_break: bool = False                 # 段前分页

    # S7: heading_level 范围校验（1-9）
    @field_validator('heading_level')
    @classmethod
    def _check_heading_level(cls, v):
        return _validate_heading_level(v)


class TableCell(BaseModel):
    """A single cell inside a table."""
    row: int
    col: int
    text: str
    paragraphs: list[Paragraph] = Field(default_factory=list)


class Table(BaseModel):
    """A table in the document."""
    index: int
    rows: int
    cols: int
    cells: list[TableCell] = Field(default_factory=list)
    insert_after_index: int = -1  # 表格紧跟在哪个段落索引之后（-1 表示文档开头）


class HeaderFooter(BaseModel):
    """Content in a page header or footer."""
    section_index: int = 0
    type: str = "header"                     # header / footer
    text: str = ""
    paragraphs: list[Paragraph] = Field(default_factory=list)
    has_page_number: bool = False            # 是否包含页码域


# ---------------------------------------------------------------------------
#  Page setup
# ---------------------------------------------------------------------------

class PageSetup(BaseModel):
    """Page layout settings."""
    paper_width_mm: Optional[float] = None
    paper_height_mm: Optional[float] = None
    margin_top_mm: Optional[float] = None
    margin_bottom_mm: Optional[float] = None
    margin_left_mm: Optional[float] = None
    margin_right_mm: Optional[float] = None
    orientation: str = "portrait"
    # 改动10：页眉/页脚距页边界（cm），由 _common.yaml page_setup 配置传入
    header_distance_cm: Optional[float] = None
    footer_distance_cm: Optional[float] = None


# ---------------------------------------------------------------------------
#  Metadata
# ---------------------------------------------------------------------------

class DocumentMetadata(BaseModel):
    """Document-level metadata."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    category: Optional[str] = None


# ---------------------------------------------------------------------------
#  Top-level Document Model
# ---------------------------------------------------------------------------

class DocumentModel(BaseModel):
    """
    The canonical intermediate representation of a Word document.
    All rule engine checks and modifications operate on this model.
    """
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    page_setup: PageSetup = Field(default_factory=PageSetup)
    paragraphs: list[Paragraph] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    headers: list[HeaderFooter] = Field(default_factory=list)
    footers: list[HeaderFooter] = Field(default_factory=list)

    # Source file info
    filename: Optional[str] = Field(default=None, exclude=True)
    source_path: Optional[str] = Field(default=None, exclude=True)
