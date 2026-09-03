# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
"""
Rule Manager: unified rule loading with priority layering.

Priority: user > custom > official
"""
from __future__ import annotations
import copy
import re
import yaml
from pathlib import Path
from typing import Any

from engine.config import RULES_DIR, CUSTOM_RULES_DIR, USER_RULES_DIR
from engine.utils.logger import logger

# Rule source directories
OFFICIAL_RULES_DIR = RULES_DIR  # rules/official（只读，捆绑在安装目录）

# ---- O5：进程级规则缓存（跨命令/跨 RuleEngine 实例共享，mtime 自动失效） ----
# 缓存键：doc_type；缓存值：(最新规则文件 mtime, 合并后规则字典)
# 注意：返回时必须 deepcopy——调用方（apply_config_overrides / _extract_content_rules /
# apply_fixes 等）会就地修改返回的规则字典，直接返回缓存对象会污染缓存。
_RULES_CACHE: dict[str, tuple[float, dict]] = {}


def _rules_mtime() -> float:
    """扫描三层规则目录所有 yaml 的最新 mtime（缓存失效依据）。

    与 RuleEngine.load_rules 的失效策略一致：official + custom + user 三层。
    """
    newest = 0.0
    for d in (OFFICIAL_RULES_DIR, CUSTOM_RULES_DIR, USER_RULES_DIR):
        try:
            for p in d.glob("*.yaml"):
                try:
                    if p.stat().st_size > 0:
                        newest = max(newest, p.stat().st_mtime)
                except OSError:
                    continue
        except Exception:
            continue
    return newest


def clear_rules_cache() -> None:
    """清空进程级规则缓存（用户/模板规则变更后立即生效时调用）。"""
    _RULES_CACHE.clear()


def _ensure_dirs() -> None:
    CUSTOM_RULES_DIR.mkdir(parents=True, exist_ok=True)
    USER_RULES_DIR.mkdir(parents=True, exist_ok=True)


def list_rule_files(source: str = "all") -> list[dict]:
    """List rule files from given source: official, custom, user, all."""
    _ensure_dirs()
    result = []
    dirs = {
        "official": OFFICIAL_RULES_DIR,
        "custom": CUSTOM_RULES_DIR,
        "user": USER_RULES_DIR,
    }
    for source_type, d in dirs.items():
        if source != "all" and source != source_type:
            continue
        for f in sorted(d.glob("*.yaml")):
            if f.stem.startswith("_"):
                continue
            result.append({
                "key": f.stem,
                "name": f.stem,
                "source_type": source_type,
                "path": str(f),
                "size": f.stat().st_size,
                "enabled": True,
            })
    return result


def _load_merged_uncached(doc_type: str = "") -> dict[str, Any]:
    """
    Load and merge rules for a document type with priority:
    official < custom < user（无缓存版本，供 load_rules_merged 填充缓存）。
    """
    _ensure_dirs()
    merged: dict[str, Any] = {}

    layers = [
        ("official", OFFICIAL_RULES_DIR),
        ("custom", CUSTOM_RULES_DIR),
        ("user", USER_RULES_DIR),
    ]
    for _source, dir_path in layers:
        # Load common
        common_file = dir_path / "_common.yaml"
        if common_file.exists():
            _deep_merge(merged, _load_yaml(common_file))

        # Load type-specific
        if doc_type:
            type_file = dir_path / f"{doc_type}.yaml"
            if type_file.exists():
                _deep_merge(merged, _load_yaml(type_file))

    # Merge fix_rules and check_rules as distinct lists, not overwritten
    merged.setdefault("fix_rules", [])
    merged.setdefault("check_rules", [])
    # 配置段 → 规则期望值同步：使模板/用户规则覆盖配置段后 check/optimize 自动跟随
    _sync_style_expected(merged)
    return merged


def load_rules_merged(doc_type: str = "") -> dict[str, Any]:
    """
    Load and merge rules for a document type with priority:
    official < custom < user.

    O5：进程级缓存——同一 doc_type 的重复加载直接命中（YAML 解析 + 深合并
    只执行一次）；规则文件 mtime 变化时自动失效重载。返回深拷贝，
    调用方就地修改（apply_config_overrides / 规则提取等）不会污染缓存。
    """
    _ensure_dirs()
    newest = _rules_mtime()
    cached = _RULES_CACHE.get(doc_type)
    if cached is None or cached[0] < newest:
        merged = _load_merged_uncached(doc_type)
        _RULES_CACHE[doc_type] = (newest, merged)
    return copy.deepcopy(_RULES_CACHE[doc_type][1])


def _load_yaml(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as exc:
        logger.error(f"Failed to load rule {path}: {exc}")
        return {}


def _deep_merge(base: dict, overlay: dict) -> None:
    """Merge overlay into base in-place, with deduplication for fix_rules/check_rules."""
    # P3-14：类型 YAML 用 title: 覆盖 _common.yaml 的 doc_title: 时，统一合并进 doc_title
    # （template_builder/checker 均以 doc_title 为权威键名；仅当 base 已有 doc_title 才映射，
    # 避免破坏通用 title 键的普通合并行为）
    if "title" in overlay and isinstance(overlay.get("title"), dict) and "doc_title" in base:
        overlay = dict(overlay)
        title_cfg = overlay.pop("title")
        if isinstance(base.get("doc_title"), dict):
            _deep_merge(base["doc_title"], title_cfg)
        else:
            base["doc_title"] = copy.deepcopy(title_cfg)
    for key, val in overlay.items():
        if key in ("fix_rules", "check_rules") and isinstance(val, list):
            existing = base.setdefault(key, [])
            if key == "check_rules":
                _dedup_extend(existing, val, dedup_key=lambda r: r.get("field"))
            elif key == "fix_rules":
                _dedup_extend(existing, val, dedup_key=lambda r: (r.get("target"), r.get("action")))
        elif key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = copy.deepcopy(val)


# 字段前缀 → 配置段键（配置段是样式的权威定义）
_FIELD_CFG_SECTION = {
    'title': 'doc_title', 'doc_title': 'doc_title', 'heading_0': 'doc_title',
    'heading_1': 'heading_1', 'heading_2': 'heading_2',
    'heading_3': 'heading_3', 'heading_4': 'heading_4',
    'body': 'body', 'signature': 'signature', 'date': 'date',
    'meeting_date': 'meeting_date', 'salutation': 'salutation',
    'introduction': 'introduction', 'transition': 'transition',
}
# 可直接同名映射的样式子键
_STYLE_KEYS = {'font', 'size', 'line_spacing', 'align', 'bold',
               'first_line_indent', 'fill'}


def _resolve_style_config(rules: dict[str, Any], field: str):
    """按 field 路径取配置段的权威样式值；无法解析返回 None。

    样式配置段（doc_title/body/signature/date/heading_*/table/page_setup）
    是样式的权威定义；check_rules.expected 与 fix_rules.value 默认是它的快照副本。
    模板/用户规则覆盖配置段后，此函数负责把覆盖值回填到检查/修复规则。
    """
    if not field or '.' not in field:
        return None
    prefix, sub = field.split('.', 1)

    # table.* / page_setup.* 直接按路径取（table.header.font → table.header.font）
    if prefix in ('table', 'page_setup'):
        node = rules
        for part in field.split('.'):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        if isinstance(node, (dict, list)):
            return None
        return node

    section = _FIELD_CFG_SECTION.get(prefix)
    if section is None or sub not in _STYLE_KEYS:
        return None
    cfg = rules.get(section)
    if not isinstance(cfg, dict) or sub not in cfg:
        return None
    val = cfg[sub]
    if isinstance(val, (dict, list)):
        return None
    return val


def _sync_style_expected(rules: dict[str, Any]) -> None:
    """把配置段的权威样式值同步到 CHK expected 与 FIX value（就地修改）。

    使 style-learn 模板 / user_rules / config-overrides 覆盖配置段后，
    check 与 optimize 的期望值自动跟随，而默认配置下幂等（配置段值==快照值）。
    """
    # 1) 同步 check_rules.expected
    for rule in rules.get('check_rules', []):
        resolved = _resolve_style_config(rules, rule.get('field', ''))
        if resolved is not None:
            rule['expected'] = resolved

    # 2) 同步 fix_rules.value（经 ref_check 定位 CHK → field → 配置值）
    # 保守策略：标量 value 可直接覆盖；复合 dict value（一次修复多属性）仅合并
    # 格式一致的键（alignment/bold/fill），避免破坏 FIX-C013/C041 等复合修复。
    chk_by_id = {r.get('id'): r for r in rules.get('check_rules', []) if r.get('id')}
    for rule in rules.get('fix_rules', []):
        ref = rule.get('ref_check')
        if not ref or ref not in chk_by_id:
            continue
        resolved = _resolve_style_config(rules, chk_by_id[ref].get('field', ''))
        if resolved is None or rule.get('value') is None:
            continue
        value = rule['value']
        # 样式配置子键（如 body.align → align）→ FIX value dict 中的键名映射
        _FIX_DICT_KEY = {
            'align': 'alignment',
            'bold': 'bold',
            'fill': 'fill',
        }
        if isinstance(value, dict):
            sub_field = chk_by_id[ref].get('field', '').split('.', 1)[-1]
            dk = _FIX_DICT_KEY.get(sub_field)
            if dk and dk in value and not isinstance(resolved, (dict, list)):
                value[dk] = resolved
        else:
            rule['value'] = resolved


def _dedup_extend(base_list: list, new_items: list, dedup_key) -> None:
    """Extend base_list with new_items, replacing duplicates by dedup_key."""
    # P2-25 修复：dedup_key 返回 None 时给出 warning，避免静默追加重复项
    for item in new_items:
        if dedup_key(item) is None:
            logger.warning(
                f"_dedup_extend: 规则缺少去重键（dedup_key 返回 None），将作为新项追加: {item!r}")
    existing_keys = {dedup_key(item) for item in base_list if dedup_key(item) is not None}
    # First add items whose key is already in base (override)
    for item in new_items:
        k = dedup_key(item)
        if k is not None and k in existing_keys:
            # P2-23 修复：同 field/键去重覆盖属于隐式依赖（如 speech.yaml 覆盖 _common.yaml），
            # 覆盖发生时记录日志，避免静默覆盖导致规则丢失难以排查
            logger.debug(f"_dedup_extend: 同键覆盖 {k}（新规则覆盖基础规则）")
            # Replace existing item with same key
            for i, existing in enumerate(base_list):
                if dedup_key(existing) == k:
                    base_list[i] = copy.deepcopy(item)
                    break
    # Then add truly new items
    for item in new_items:
        k = dedup_key(item)
        if k is None or k not in existing_keys:
            base_list.append(copy.deepcopy(item))
            if k is not None:
                existing_keys.add(k)


def save_rule(key: str, content: dict, source_type: str = "user") -> bool:
    """Save a user/custom rule YAML file.

    安全措施：验证key只包含安全字符，防止路径遍历。
    """
    _ensure_dirs()

    # 验证key只包含安全字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', key):
        logger.error(f"Invalid rule key: {key}")
        return False

    if source_type == "custom":
        dir_path = CUSTOM_RULES_DIR
    else:
        dir_path = USER_RULES_DIR
    file_path = dir_path / f"{key}.yaml"

    # 验证路径在允许的目录内
    try:
        file_path.resolve().relative_to(dir_path.resolve())
    except ValueError:
        logger.error(f"Path traversal detected in rule key: {key}")
        return False

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            yaml.dump(content, fh, allow_unicode=True, default_flow_style=False)
        logger.info(f"Rule saved: {file_path}")
        return True
    except Exception as exc:
        logger.error(f"Failed to save rule {file_path}: {exc}")
        return False


def delete_rule(key: str, source_type: str = "user") -> bool:
    """Delete a user/custom rule YAML file.

    安全措施：验证key只包含安全字符，防止路径遍历。
    """
    _ensure_dirs()

    # 验证key只包含安全字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', key):
        logger.error(f"Invalid rule key: {key}")
        return False

    if source_type == "custom":
        dir_path = CUSTOM_RULES_DIR
    else:
        dir_path = USER_RULES_DIR
    file_path = dir_path / f"{key}.yaml"

    # 验证路径在允许的目录内
    try:
        file_path.resolve().relative_to(dir_path.resolve())
    except ValueError:
        logger.error(f"Path traversal detected in rule key: {key}")
        return False

    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Rule deleted: {file_path}")
            return True
        return False
    except Exception as exc:
        logger.error(f"Failed to delete rule {file_path}: {exc}")
        return False


def get_rule_content(key: str, source_type: str = "all") -> dict | None:
    """Get full content of a rule by key."""
    _ensure_dirs()
    dirs = {
        "official": OFFICIAL_RULES_DIR,
        "custom": CUSTOM_RULES_DIR,
        "user": USER_RULES_DIR,
    }
    for st, d in dirs.items():
        if source_type != "all" and source_type != st:
            continue
        f = d / f"{key}.yaml"
        if f.exists():
            return {
                "key": key,
                "source_type": st,
                "content": _load_yaml(f),
                "path": str(f),
            }
    return None


def export_rule(key: str, source_type: str = "all") -> str | None:
    """Export a rule as YAML string."""
    rule = get_rule_content(key, source_type)
    if not rule:
        return None
    return yaml.dump(rule["content"], allow_unicode=True, default_flow_style=False)


def import_rule(key: str, yaml_text: str, source_type: str = "user") -> dict:
    """Import a rule from YAML text."""
    try:
        content = yaml.safe_load(yaml_text)
        if not isinstance(content, dict):
            raise ValueError("Invalid YAML: not a dict")
        # Validate basic structure
        validate_rule(content)
        ok = save_rule(key, content, source_type)
        return {"success": ok, "key": key, "source_type": source_type}
    except Exception as exc:
        logger.error(f"Failed to import rule {key}: {exc}")
        return {"success": False, "error": str(exc)}


def validate_rule(rule: dict) -> None:
    """
    Validate rule structure.
    Raises ValueError on failure.
    """
    if not isinstance(rule, dict):
        raise ValueError("Rule must be a dictionary")

    # Must have at least some meaningful content
    has_format = any(k in rule for k in ("title", "body", "page_setup"))
    has_rules = any(k in rule for k in ("check_rules", "fix_rules"))
    if not has_format and not has_rules:
        raise ValueError(
            "Rule must have at least one of: title, body, page_setup, check_rules, fix_rules"
        )

    # Validate check_rules structure
    for cr in rule.get("check_rules", []):
        if not isinstance(cr, dict):
            raise ValueError("Each check_rule must be a dict")
        if "id" not in cr:
            raise ValueError("Each check_rule must have an 'id'")
        if "severity" not in cr:
            raise ValueError(f"check_rule '{cr.get('id', '?')}' must have 'severity'")
        # P3-8 修复：校验 check_rule 必须有 field/message（缺失会导致检查静默失效）
        if "field" not in cr:
            raise ValueError(f"check_rule '{cr.get('id', '?')}' must have 'field'")
        if "message" not in cr:
            raise ValueError(f"check_rule '{cr.get('id', '?')}' must have 'message'")

    # Validate fix_rules structure
    for fr in rule.get("fix_rules", []):
        if not isinstance(fr, dict):
            raise ValueError("Each fix_rule must be a dict")
        if "action" not in fr:
            raise ValueError(f"Each fix_rule must have an 'action', got: {fr}")
        # P3-8 修复：校验 fix_rule 必须有 target（缺失会导致修复找不到目标段落）
        if "target" not in fr:
            raise ValueError(f"fix_rule '{fr.get('id', '?')}' must have 'target'")

    # Validate check_rules and fix_rules are lists if present
    for field in ("fix_rules", "check_rules"):
        if field in rule and not isinstance(rule[field], list):
            raise ValueError(f"'{field}' must be a list")


def apply_config_overrides(rules: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """将 DSH 配置覆盖深度合并到已加载的规则字典上。

    优先级：official < custom < user < DSH config overrides（最高）。
    overrides 中只覆盖出现的键，不删除已有的 check_rules/fix_rules 列表。
    对 check_rules 和 fix_rules 列表中的条目，按 field/target+action 去重覆盖。

    Args:
        rules: 已通过 load_rules_merged 加载的规则字典（会被修改）。
        overrides: 配置覆盖字典，如
            {"page_setup": {"margins": {"top": "3.0cm"}},
             "body": {"line_spacing": "28pt"}}

    Returns:
        合并后的 rules（与传入的是同一对象）。
    """
    if not overrides or not isinstance(overrides, dict):
        return rules
    _deep_merge(rules, copy.deepcopy(overrides))
    # 配置段 → 规则期望值同步：config-overrides 覆盖后 check/optimize 自动跟随
    _sync_style_expected(rules)
    return rules


def override_priority(source_type: str) -> int:
    """Return override priority: higher value = higher priority."""
    return {"official": 0, "custom": 1, "user": 2}.get(source_type, -1)
