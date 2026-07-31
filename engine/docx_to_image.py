# -*- coding: utf-8 -*-
"""
docx 转图片可视化验证（借鉴 docx-skill 的文档转图片思路）。

流程：docx → PDF（LibreOffice）→ JPEG（Poppler pdftoppm）
主链路不可用时的降级：
  1. docx2pdf（Windows Word COM）→ PDF → PyMuPDF 渲染图片
  2. 纯 PyMuPDF 直接渲染（若 pymupdf 可用）
  3. mammoth → HTML → 无图片，仅报告"无法渲染"（最后兜底）

用法：
  python docx_to_image.py <document.docx> --outdir <dir> [--dpi 150] [--format jpeg|png] [--pages 1-3]
"""
from __future__ import annotations
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_TMP_PDF = Path(__file__).resolve().parent / "tmp" / "_render_tmp.pdf"


def _find_command(*names) -> Optional[str]:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _convert_with_soffice(docx_path: Path, pdf_path: Path, soffice: str) -> bool:
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(docx_path)],
            capture_output=True, timeout=120,
        )
        produced = pdf_path.parent / f"{docx_path.stem}.pdf"
        if produced.exists():
            produced.rename(pdf_path)
            return True
    except Exception:
        pass
    return False


def _convert_with_docx2pdf(docx_path: Path, pdf_path: Path) -> bool:
    try:
        import docx2pdf
        docx2pdf.convert(str(docx_path), str(pdf_path))
        return pdf_path.exists()
    except Exception:
        return False


def _render_pdf_to_images(pdf_path: Path, outdir: Path, dpi: int, fmt: str, pages: str) -> list[Path]:
    """用 pdftoppm（优先）或 PyMuPDF（降级）将 PDF 渲染为图片。"""
    outdir.mkdir(parents=True, exist_ok=True)
    images: list[Path] = []

    pdftoppm = _find_command("pdftoppm")
    if pdftoppm:
        prefix = outdir / "page"
        cmd = [pdftoppm, "-jpeg" if fmt == "jpeg" else "-png", "-r", str(dpi)]
        if pages:
            try:
                start, end = pages.split("-", 1)
                cmd += ["-f", str(int(start)), "-l", str(int(end))]
            except Exception:
                pass
        cmd += [str(pdf_path), str(prefix)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=120)
            images = sorted(outdir.glob(f"page-*.{fmt}"))
            if images:
                return images
        except Exception:
            pass

    # 降级：PyMuPDF 渲染
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(pdf_path))
        page_nums = list(range(len(doc)))
        if pages:
            try:
                start, end = pages.split("-", 1)
                page_nums = list(range(int(start) - 1, min(int(end), len(doc))))
            except Exception:
                pass
        for i in page_nums:
            pix = doc[i].get_pixmap(dpi=dpi)
            out = outdir / f"page-{i + 1}.{fmt}"
            pix.save(str(out))
            images.append(out)
    except Exception:
        pass

    return images


def docx_to_image(docx_path: str | Path, outdir: str | Path,
                  dpi: int = 150, fmt: str = "jpeg", pages: str = "") -> list[Path]:
    """主入口：docx → 图片列表。任一链路成功即返回。"""
    docx_path = Path(docx_path)
    outdir = Path(outdir)

    if not docx_path.exists():
        raise FileNotFoundError(f"文档不存在: {docx_path}")

    # 1. docx → PDF
    pdf_path = _TMP_PDF
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()

    soffice = _find_command("soffice", "libreoffice")
    pdf_ok = False
    if soffice:
        pdf_ok = _convert_with_soffice(docx_path, pdf_path, soffice)
    if not pdf_ok:
        pdf_ok = _convert_with_docx2pdf(docx_path, pdf_path)
    if not pdf_ok or not pdf_path.exists():
        # 最后兜底：mammoth 无法渲染图片，报告原因
        print("⚠️ 无法将 docx 转为 PDF（需要 LibreOffice 或 docx2pdf），跳过图片渲染")
        return []

    # 2. PDF → 图片
    images = _render_pdf_to_images(pdf_path, outdir, dpi, fmt, pages)
    try:
        pdf_path.unlink(missing_ok=True)
    except Exception:
        pass
    return images


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="docx 转图片可视化验证")
    ap.add_argument("input", help="输入 .docx 路径")
    ap.add_argument("--outdir", default=".", help="输出图片目录（默认当前目录）")
    ap.add_argument("--dpi", type=int, default=150, help="分辨率（默认150）")
    ap.add_argument("--format", choices=["jpeg", "png"], default="jpeg", help="图片格式")
    ap.add_argument("--pages", default="", help="页码范围，如 1-3")
    args = ap.parse_args()

    result = docx_to_image(args.input, args.outdir, args.dpi, args.format, args.pages)
    if result:
        print(f"✅ 已生成 {len(result)} 张图片:")
        for r in result:
            print(f"   - {r}")
    else:
        print("❌ 图片渲染失败")
        sys.exit(1)
