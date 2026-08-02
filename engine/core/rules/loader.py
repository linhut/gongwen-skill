# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
"""
YAML rule file loader. Reads rule definitions from the rules/ directory.
"""
from pathlib import Path
from typing import Any
import yaml

from config import RULES_DIR
from utils.logger import logger


def load_rule_file(file_path: Path) -> dict[str, Any]:
    """Load a single YAML rule file and return its contents."""
    if not file_path.exists():
        logger.warning(f"Rule file not found: {file_path}")
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    logger.info(f"Loaded rule: {file_path.name}")
    return data or {}


def load_common_rules() -> dict[str, Any]:
    """Load the shared base rules (_common.yaml)."""
    return load_rule_file(RULES_DIR / "_common.yaml")


def list_available_types() -> list[str]:
    """Return a list of document type identifiers that have rule files."""
    types = []
    for f in RULES_DIR.glob("*.yaml"):
        if f.stem.startswith("_"):
            continue
        types.append(f.stem)
    return sorted(types)
