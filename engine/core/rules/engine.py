# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
"""
Rule engine: orchestrates loading, checking, and fixing using the rule system.
Supports priority layering: user > custom > official.
"""
from __future__ import annotations
from typing import Any

from engine.core.document.models import DocumentModel
from engine.core.rules.manager import load_rules_merged, apply_config_overrides
from engine.core.rules.checker import check_document, CheckIssue
from engine.core.rules.fixer import apply_fixes
from engine.utils.logger import logger


class RuleEngine:
    """
    Central rule engine that coordinates rule loading, checking, and fixing.
    """

    def __init__(self):
        self._rules_cache: dict[str, dict[str, Any]] = {}
        # P3-9：记录每个 doc_type 加载时的规则文件 mtime，文件变更后自动重载
        self._rules_mtime: dict[str, float] = {}
        # DSH 配置覆盖（优先级最高，在 YAML 三层合并之后应用）
        self._config_overrides: dict[str, Any] | None = None

    def set_config_overrides(self, overrides: dict[str, Any] | None) -> None:
        """设置 DSH 配置覆盖，会清空规则缓存以使下次 load_rules 时生效。"""
        self._config_overrides = overrides if isinstance(overrides, dict) else None
        self.clear_cache()

    def load_rules(self, doc_type: str) -> dict[str, Any]:
        """
        Load rules for a document type (with priority: user > custom > official).

        P3-9 修复：缓存感知规则文件变更——若规则文件 mtime 已变化则自动重载，
        无需手动调用 clear_cache。
        P2-10 修复：mtime 扫描扩展到 official + custom + user 三层目录。
        DSH 配置覆盖在 YAML 合并之后应用（优先级最高）。
        """
        newest = 0.0
        try:
            from engine.config import RULES_DIR, CUSTOM_RULES_DIR, USER_RULES_DIR
            for d in (RULES_DIR, CUSTOM_RULES_DIR, USER_RULES_DIR):
                try:
                    for p in d.glob("*.yaml"):
                        if p.stat().st_size > 0:
                            m = p.stat().st_mtime
                            if m > newest:
                                newest = m
                except Exception as e:
                    logger.warning(f"规则文件扫描失败: {e}")
        except Exception:
            newest = 0.0
        if doc_type not in self._rules_cache or self._rules_mtime.get(doc_type, -1) < newest:
            rules = load_rules_merged(doc_type)
            if self._config_overrides:
                apply_config_overrides(rules, self._config_overrides)
            self._rules_cache[doc_type] = rules
            self._rules_mtime[doc_type] = newest
            logger.info(f"Loaded and cached rules for type: {doc_type}"
                        f"{' (with config overrides)' if self._config_overrides else ''}")
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
        from engine.core.rules.loader import list_available_types
        return list_available_types()
