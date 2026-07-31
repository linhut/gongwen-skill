# -*- coding: utf-8 -*-
"""
OOXML 解包-编辑-打包工作流。

依据「公文技能提质方案」4.5 设计：
将 .docx 解包到临时目录 → 编辑 XML → 打包回 .docx，对用户透明。

用法：
  with OOXMLWorkflow("输入.docx") as wf:
      # wf.unpack_dir 是解包目录，直接编辑里面的 XML 文件
      ...
  # 退出后 wf.pack("输出.docx") 自动执行（或显式调用）
"""
from __future__ import annotations
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional


class OOXMLWorkflow:
    """OOXML 解包-编辑-打包工作流（上下文管理器）。"""

    def __init__(self, doc_path: str | Path):
        self.doc_path = Path(doc_path)
        self.unpack_dir: Optional[Path] = None
        self._entered = False

    def unpack(self) -> Path:
        """解包 .docx 到临时目录。"""
        if self.unpack_dir is None:
            self.unpack_dir = Path(tempfile.mkdtemp(prefix="gongwen_ooxml_"))
        with zipfile.ZipFile(self.doc_path) as z:
            z.extractall(str(self.unpack_dir))
        return self.unpack_dir

    def pack(self, output_path: str | Path) -> Path:
        """打包回 .docx。"""
        if self.unpack_dir is None:
            raise RuntimeError("尚未解包，无法打包")
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(self.unpack_dir.rglob('*')):
                if f.is_file():
                    z.write(f, f.relative_to(self.unpack_dir).as_posix())
        return out

    def read_xml(self, rel_path: str) -> bytes:
        """读取解包目录中的 XML 文件。"""
        self._ensure_unpacked()
        p = self.unpack_dir / rel_path
        return p.read_bytes() if p.exists() else b''

    def write_xml(self, rel_path: str, data: bytes) -> None:
        """写入解包目录中的 XML 文件。"""
        self._ensure_unpacked()
        p = self.unpack_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def _ensure_unpacked(self) -> None:
        if self.unpack_dir is None:
            self.unpack()

    def __enter__(self) -> "OOXMLWorkflow":
        self._entered = True
        self.unpack()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # S5 修复：异常时保留临时目录便于调试；正常结束才清理
        if self.unpack_dir is not None and exc_type is None:
            shutil.rmtree(self.unpack_dir, ignore_errors=True)
            self.unpack_dir = None
