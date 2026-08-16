# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
"""
Rule engine: orchestrates loading, checking, and fixing using the rule system.
Supports priority layering: user > custom > official.
"""
from __future__ import annotations
from typing import Any
import copy

from core.document.models import DocumentModel
from core.rules.manager import load_rules_merged
from core.rules.checker import check_document, CheckIssue
from core.rules.fixer import apply_fixes
from utils.logger import logger


class RuleEngine:
    """
    Central rule engine that coordinates rule loading, checking, and fixing.
    """

    def __init__(self):
        self._rules_cache: dict[str, dict[str, Any]] = {}
        # P3-9：记录每个 doc_type 加载时的规则文件 mtime，文件变更后自动重载
        self._rules_mtime: dict[str, float] = {}

    def load_rules(self, doc_type: str) -> dict[str, Any]:
        """
        Load rules for a document type (with priority: user > custom > official).

        P3-9 修复：缓存感知规则文件变更——若规则文件 mtime 已变化则自动重载，
        无需手动调用 clear_cache。
        """
        try:
            from config import RULES_DIR
            newest = max((p.stat().st_mtime for p in RULES_DIR.glob("*.yaml")
                          if p.stat().st_size > 0), default=0.0)
        except Exception:
            newest = 0.0
        if doc_type not in self._rules_cache or self._rules_mtime.get(doc_type, -1) < newest:
            self._rules_cache[doc_type] = load_rules_merged(doc_type)
            self._rules_mtime[doc_type] = newest
            logger.info(f"Loaded and cached rules for type: {doc_type}")
        return self._rules_cache[doc_type]

    def clear_cache(self):
        self._rules_cache.clear()
        self._rules_mtime.clear()
        logger.info("Rules cache cleared")

    def check(self, model: DocumentModel, doc_type: str) -> list[CheckIssue]:
        rules = self.load_rules(doc_type)
        # B-01（方案二）：注入 _doc_type 供 checker 文种感知（如 CHK-C030 跳过 speech 整段加粗检查）
        rules = dict(rules)
        rules['_doc_type'] = doc_type
        issues = check_document(model, rules)
        logger.info(f"Check complete: {len(issues)} issues found")
        return issues

    def fix(self, model: DocumentModel, doc_type: str, selected_rule_ids: list[str] | None = None) -> DocumentModel:
        rules = self.load_rules(doc_type)
        fixed_model = apply_fixes(model, rules, selected_rule_ids, doc_type=doc_type)
        logger.info(f"Fixes applied for type: {doc_type}")
        return fixed_model

    def check_and_fix(self, model: DocumentModel, doc_type: str,
                      selected_rule_ids: list[str] | None = None) -> tuple[list[CheckIssue], DocumentModel]:
        rules = self.load_rules(doc_type)
        # B-01（方案二）：注入 _doc_type 供 checker 文种感知
        rules = dict(rules)
        rules['_doc_type'] = doc_type
        issues = check_document(model, rules)
        logger.info(f"Found {len(issues)} issues before fixing")
        fixed_model = apply_fixes(model, rules, selected_rule_ids, doc_type=doc_type)
        logger.info(f"Applied fixes for type: {doc_type}")
        return issues, fixed_model

    def available_types(self) -> list[str]:
        from core.rules.loader import list_available_types
        return list_available_types()
