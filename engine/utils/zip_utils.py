# -*- coding: utf-8 -*-
"""
公共 ZIP / OOXML 工具（优化方案 v1.12.25 E3）。

消除 reviewer_comments.py / tracked_annotator.py / annotator.py 中重复的
ZIP 读写、原子写入、Content-Type / 关系注册逻辑。

用法：
  from utils.zip_utils import read_zip_entries, atomic_write_zip, register_content_type, register_relationship
"""
from __future__ import annotations
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Dict, Optional

from lxml import etree

CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PC = 'http://schemas.openxmlformats.org/package/2006/relationships'


# ---------------------------------------------------------------------------
#  ZIP 读写
# ---------------------------------------------------------------------------

def read_zip_entries(path: str | Path) -> Dict[str, bytes]:
    """读取 ZIP 全部条目到内存（entries + infos 两用）。"""
    with zipfile.ZipFile(path, 'r') as z:
        return {name: z.read(name) for name in z.namelist()}


def atomic_write_zip(target: str | Path, entries: Dict[str, bytes],
                     new_entries: Optional[list[str]] = None) -> None:
    """原子写入 ZIP：临时文件 + os.replace，崩溃不产生半写文件。

    Args:
        target: 目标 .docx 路径
        entries: 全部条目（含新增）
        new_entries: 需要确保写入的新条目名（已含在 entries 中）
    """
    p = Path(target)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix='.tmp', prefix='.gongwen_')
    os.close(tmp_fd)
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in entries.items():
                z.writestr(name, data)
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


# ---------------------------------------------------------------------------
#  Content-Type / 关系注册
# ---------------------------------------------------------------------------

def register_content_type(ct_xml: bytes, part_name: str, content_type: str) -> bytes:
    """注册 Content-Type（已存在则跳过，去重）。"""
    root = etree.fromstring(ct_xml)
    if any(ov.get('PartName') == part_name for ov in root):
        return ct_xml
    ov = etree.SubElement(root, f'{{{CT}}}Override')
    ov.set('PartName', part_name)
    ov.set('ContentType', content_type)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def register_relationship(rels_xml: bytes, rel_type: str, target: str) -> bytes:
    """注册 Relationship（按 Target 去重，rId 从最大编号+1 分配）。"""
    root = etree.fromstring(rels_xml)
    if any(r.get('Target', '') == target for r in root):
        return rels_xml
    existing_ids = {r.get('Id', '') for r in root}
    max_num = 0
    for rid in existing_ids:
        if rid.startswith('rId') and rid[3:].isdigit():
            max_num = max(max_num, int(rid[3:]))
    new_rid = f'rId{max_num + 1}'
    while new_rid in existing_ids:
        max_num += 1
        new_rid = f'rId{max_num + 1}'
    rel = etree.SubElement(root, f'{{{PC}}}Relationship')
    rel.set('Id', new_rid)
    rel.set('Type', rel_type)
    rel.set('Target', target)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
