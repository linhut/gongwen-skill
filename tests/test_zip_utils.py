# -*- coding: utf-8 -*-
"""engine/utils/zip_utils.py 单元测试。"""
import sys
import zipfile
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest
from utils.zip_utils import read_zip_entries, atomic_write_zip, register_content_type, register_relationship
from lxml import etree


class TestReadZipEntries:
    def test_read_simple_zip(self, tmp_path):
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, 'w') as z:
            z.writestr("file1.txt", b"hello")
            z.writestr("file2.txt", b"world")
        entries = read_zip_entries(zip_path)
        assert entries["file1.txt"] == b"hello"
        assert entries["file2.txt"] == b"world"
        assert len(entries) == 2

    def test_read_empty_zip(self, tmp_path):
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, 'w') as z:
            pass
        entries = read_zip_entries(zip_path)
        assert entries == {}


class TestAtomicWriteZip:
    def test_write_and_read_back(self, tmp_path):
        target = tmp_path / "output.zip"
        entries = {"a.txt": b"data1", "b.txt": b"data2"}
        atomic_write_zip(target, entries)
        result = read_zip_entries(target)
        assert result["a.txt"] == b"data1"
        assert result["b.txt"] == b"data2"

    def test_overwrite_existing(self, tmp_path):
        target = tmp_path / "existing.zip"
        atomic_write_zip(target, {"old.txt": b"old"})
        atomic_write_zip(target, {"new.txt": b"new"})
        result = read_zip_entries(target)
        assert "old.txt" not in result
        assert result["new.txt"] == b"new"

    def test_creates_parent_dir(self, tmp_path):
        target = tmp_path / "subdir" / "nested" / "output.zip"
        atomic_write_zip(target, {"x.txt": b"x"})
        assert target.exists()

    def test_no_tmp_file_left_on_success(self, tmp_path):
        target = tmp_path / "clean.zip"
        atomic_write_zip(target, {"a.txt": b"a"})
        tmp_files = list(tmp_path.glob(".gongwen_*"))
        assert len(tmp_files) == 0


class TestRegisterContentType:
    def test_register_new(self):
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
        result = register_content_type(xml, "/word/test.xml", "application/xml")
        root = etree.fromstring(result)
        overrides = root.findall("{http://schemas.openxmlformats.org/package/2006/content-types}Override")
        assert len(overrides) == 1
        assert overrides[0].get("PartName") == "/word/test.xml"

    def test_skip_existing(self):
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/test.xml" ContentType="application/xml"/></Types>'
        result = register_content_type(xml, "/word/test.xml", "application/xml")
        root = etree.fromstring(result)
        overrides = root.findall("{http://schemas.openxmlformats.org/package/2006/content-types}Override")
        assert len(overrides) == 1  # 不重复添加


class TestRegisterRelationship:
    def test_register_new(self):
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
        result = register_relationship(xml, "http://test/rel", "test/target")
        root = etree.fromstring(result)
        rels = root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        assert len(rels) == 1
        assert rels[0].get("Target") == "test/target"

    def test_skip_duplicate_target(self):
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://test/rel" Target="test/target"/></Relationships>'
        result = register_relationship(xml, "http://test/rel", "test/target")
        root = etree.fromstring(result)
        rels = root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        assert len(rels) == 1

    def test_rid_increments(self):
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId5" Type="http://a" Target="a"/></Relationships>'
        result = register_relationship(xml, "http://b", "b")
        root = etree.fromstring(result)
        rels = root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        assert len(rels) == 2
        new_rel = [r for r in rels if r.get("Target") == "b"][0]
        assert new_rel.get("Id") == "rId6"
