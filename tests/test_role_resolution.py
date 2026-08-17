# -*- coding: utf-8 -*-
"""角色解析与批注语义类别过滤的单元测试（v1.12.26 优化方案 M5/P2 验证）。"""
from core.document.reviewer_comments import (
    REVIEWER_MAP,
    CATEGORY_ROLE_MAP,
    REASON_CATEGORY_HINTS,
    SEMANTIC_CATEGORIES,
    resolve_role,
    get_author,
)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))


class TestResolveRole:
    """M5 验证：resolve_role 覆盖 category 字段 / reason 提示 / 兜底三场景。"""

    def test_category_field_priority(self):
        """category 字段存在时优先使用，不依赖 reason。"""
        c = {"category": "用语优化", "style": "庄重严谨", "reason": "无提示词"}
        category, author = resolve_role(c)
        assert category == "用语优化"
        assert author == "用语审校"

    def test_reason_hint_fallback(self):
        """category 缺失时从 reason 提取（REASON_CATEGORY_HINTS 生效，非死代码）。"""
        c = {"style": "庄重严谨", "reason": "【事实核验】人员职务需确认"}
        category, author = resolve_role(c)
        assert category == "事实核验"
        assert author == "事实核验"

    def test_default_fallback(self):
        """无 category 且 reason 无提示 → 综合审校。"""
        c = {"style": "庄重严谨", "reason": "删去冗余"}
        category, author = resolve_role(c)
        assert category == "内容优化"
        assert author == "综合审校"

    def test_fact_check_role_not_truncated(self):
        """M2 验证：事实核验员在 REVIEWER_MAP 中，resolve_role 不受角色截断影响。"""
        assert "事实核验员" in REVIEWER_MAP
        c = {"category": "事实核验", "style": "庄重严谨", "reason": ""}
        category, author = resolve_role(c)
        assert author == "事实核验"


class TestSemanticCategories:
    """P2 验证：批注正文仅语义类别显示标签，风格类不显示。"""

    def test_semantic_categories_whitelist(self):
        assert "事实核验" in SEMANTIC_CATEGORIES
        assert "用语优化" in SEMANTIC_CATEGORIES
        assert "庄重严谨" not in SEMANTIC_CATEGORIES  # 风格描述不在白名单
        assert "简洁精炼" not in SEMANTIC_CATEGORIES

    def test_category_role_map_no_style_entries(self):
        """L3 验证：CATEGORY_ROLE_MAP 仅含语义类别，不含风格描述。"""
        assert "庄重严谨" not in CATEGORY_ROLE_MAP
        assert "简洁精炼" not in CATEGORY_ROLE_MAP
        assert "用语优化" in CATEGORY_ROLE_MAP
        assert "事实核验" in CATEGORY_ROLE_MAP

    def test_reviewer_map_has_fact_check_role(self):
        """D5/M2/V3 验证：REVIEWER_MAP 含 7 角色（6 批注 + 风格审校），事实核验员独立。"""
        assert len(REVIEWER_MAP) == 7
        assert get_author("事实核验员") == "事实核验"
        assert "风格审校员" in REVIEWER_MAP
        assert get_author("风格审校员") == "风格审校"
