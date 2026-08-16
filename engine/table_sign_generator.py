# -*- coding: utf-8 -*-
"""
桌签批量生成器 —— 基于模板文件的桌签生成。

直接从用户提供的 .dotx 桌签模板出发，在 ZIP/XML 级别替换占位文本，
确保生成的桌签与模板布局完全一致（Drawing→TextBox→Table 结构）。

用法（CLI）：
  python gongwen.py table-signs 名单.txt -o ./桌签/
  python gongwen.py table-signs 名单.txt --combined -o 桌签-合并.docx

输入名单格式：每行一个人名，支持逗号/空格/顿号分隔，空行或 # 开头被忽略。
"""
from __future__ import annotations
import os
import copy
import re
import zipfile
import io
from pathlib import Path
from typing import List, Optional
from lxml import etree

from utils.logger import logger

# ---------------------------------------------------------------------------
#  桌签模板路径（方案六 P2-2：内置默认模板；调用者可用 template_path 覆盖）
# ---------------------------------------------------------------------------


def _get_default_template():
    """返回内置默认模板路径；不存在则构建（table_sign_template.py）。"""
    from table_sign_template import ensure_default_template
    return ensure_default_template()


DEFAULT_TEMPLATE = _get_default_template()  # 内置默认模板（engine/templates/table_sign.dotx）

# XML 命名空间
NSMAP = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
    'wpg': 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
    'wpi': 'http://schemas.microsoft.com/office/word/2010/wordprocessingInk',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'wp14': 'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
}
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def _load_xml_from_zip(zip_path: Path, xml_path: str = "word/document.xml") -> bytes:
    """从 ZIP 中读取 XML 文件。"""
    with zipfile.ZipFile(zip_path, 'r') as z:
        return z.read(xml_path)


def _write_xml_to_zip(zip_path: Path, xml_bytes: bytes, xml_path: str = "word/document.xml") -> None:
    """将修改后的 XML 写回 ZIP 文件。"""
    # 读取全部内容到内存
    with zipfile.ZipFile(zip_path, 'r') as z:
        entries = {}
        for name in z.namelist():
            entries[name] = z.read(name)
    # 替换目标 XML
    entries[xml_path] = xml_bytes
    # 重写 ZIP
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)


def _calc_font_size(name_len: int) -> int:
    """
    根据名字字符数计算适宜的字号（w:sz 值，半磅单位）。

    基于 WPS 座签模板实测值（方案三修正，对齐模板 2字156pt/4字100pt）：
    | 字符数 | sz (半磅) | pt   |
    |--------|-----------|------|
    | 1~2    | 312       | 156  |
    | 3      | 240       | 120  |
    | 4      | 200       | 100  |
    | 5+     | 160       |  80  |

    如需微调各长度字号，修改此函数即可。
    """
    sizes = {1: 312, 2: 312, 3: 240, 4: 200}
    if name_len >= 5:
        return 160
    return sizes.get(name_len, 312)


def _format_name(name: str) -> str:
    """
    格式化名字用于桌签竖排显示。

    两字姓名（如"张三"）在字间加 2 个空格，使其在 tbRl/btLr 竖排布局中
    视觉上均匀填满单元格；三字及以上保持原样。

    规则（方案三修正：与 WPS 模板一致，2 个空格）：
    - len(显示字符) == 2 → "张  三"（2个空格）
    - 其他 → 原样
    """
    # 去掉潜在空格再判断（FIX-B001 L3：深层剥离残留 BOM 字符）
    cleaned = name.replace(' ', '').replace('\ufeff', '').strip()
    if len(cleaned) == 2:
        # 在两个字之间插入 2 个空格
        return cleaned[0] + '  ' + cleaned[1]
    return cleaned


def _replace_placeholder_in_xml(xml_bytes: bytes, placeholder: str, new_text: str) -> bytes:
    """
    在 XML 字节流中替换占位文本，并调整字号。
    找到所有 w:t 元素替换文本；同时找到 w:sz 元素按名字长度调整字号。
    """
    root = etree.fromstring(xml_bytes)
    formatted = _format_name(new_text)
    # 计算目标字号
    target_sz = _calc_font_size(len(new_text.replace(' ', '').strip()))
    for t_elem in root.iter(f'{{{W}}}t'):
        if t_elem.text and t_elem.text.strip() == placeholder:
            t_elem.text = formatted
    # 调整所有 w:sz 字号（表格内所有 run 统一改）
    for sz_elem in root.iter(f'{{{W}}}sz'):
        sz_elem.set(f'{{{W}}}val', str(target_sz))
    for szCs_elem in root.iter(f'{{{W}}}szCs'):
        szCs_elem.set(f'{{{W}}}val', str(target_sz))
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def _duplicate_body_for_combined(xml_bytes: bytes, names: List[str], placeholder: str = "Jose AI") -> bytes:
    """
    合并模式：复制 body 内容 N 次，每次替换占位文本。
    即 body 中含有 N 个人的桌签，每个占 2 页。

    方案五（P2-3）：占位符参数化，不再硬编码。
    """
    root = etree.fromstring(xml_bytes)
    body = root.find(f'{{{W}}}body')

    # P0-2 修复：lxml Element 的布尔值为 True（即使无子元素），`if not body:` 恒为 False，
    # 空 body 文档会静默跳过。改为显式判空。
    if body is None or len(body) == 0:
        return xml_bytes

    # 获取第一个人的完整内容（整个 body）
    # 我们需要复制 body 中除了 sectPr 之外的所有内容
    children = list(body)
    sectPr = None
    content_elements = []
    for child in children:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'sectPr':
            sectPr = copy.deepcopy(child)
        else:
            content_elements.append(child)

    if not content_elements:
        return xml_bytes

    # 清空 body
    for child in list(body):
        body.remove(child)

    # 为每个人复制一份内容
    for idx, name in enumerate(names):
        if idx > 0:
            # 加分页符
            pb = etree.SubElement(body, f'{{{W}}}p')
            pb_r = etree.SubElement(pb, f'{{{W}}}r')
            pb_br = etree.SubElement(pb_r, f'{{{W}}}br')
            pb_br.set(f'{{{W}}}type', 'page')

        for elem in content_elements:
            elem_copy = copy.deepcopy(elem)
            # 替换该副本中的占位文本并调整字号
            target_sz = _calc_font_size(len(name.replace(' ', '').strip()))
            for t_elem in elem_copy.iter(f'{{{W}}}t'):
                if t_elem.text and t_elem.text.strip() == placeholder:
                    t_elem.text = _format_name(name)
            for sz_elem in elem_copy.iter(f'{{{W}}}sz'):
                sz_elem.set(f'{{{W}}}val', str(target_sz))
            for szCs_elem in elem_copy.iter(f'{{{W}}}szCs'):
                szCs_elem.set(f'{{{W}}}val', str(target_sz))
            body.append(elem_copy)

    # 恢复 sectPr
    if sectPr is not None:
        body.append(sectPr)

    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def _prepare_docx_from_template(names: List[str], output_path: Path,
                                template_path: Path, combined: bool = False,
                                placeholder: str = "Jose AI") -> Path:
    """
    核心函数：从模板生成桌签。

    流程：
    1. 复制模板到目标路径
    2. 修改 ZIP 中的 document.xml
       - 独立模式：每人一个文件，直接替换占位文本
       - 合并模式：复制 body 内容 N 次并替换占位文本

    方案五（P2-3）：占位符参数化，不再硬编码。
    """
    if not combined:
        # 每人独立文件：复制模板，替换占位文本
        import shutil
        shutil.copy2(str(template_path), str(output_path))

        xml_bytes = _load_xml_from_zip(output_path)
        xml_bytes = _replace_placeholder_in_xml(xml_bytes, placeholder, names[0])
        _write_xml_to_zip(output_path, xml_bytes)

    else:
        # 合并模式：复制模板，复制 body N 次
        import shutil
        shutil.copy2(str(template_path), str(output_path))

        xml_bytes = _load_xml_from_zip(output_path)
        xml_bytes = _duplicate_body_for_combined(xml_bytes, names, placeholder)
        _write_xml_to_zip(output_path, xml_bytes)

    return output_path


def generate_table_signs(
    names: List[str],
    output_dir: str | Path = ".",
    prefix: str = "桌签",
    template_path: Optional[Path] = None,
    placeholder: str = "Jose AI",
) -> List[Path]:
    """
    批量生成桌签文档，每人一个独立文件。

    Args:
        names: 人员姓名列表
        output_dir: 输出目录
        prefix: 文件名前缀
        template_path: 桌签模板 .dotx 路径
        placeholder: 模板中占位文本（方案五 P2-3：参数化）

    Returns:
        生成的 .docx 文件路径列表
    """
    tmpl = template_path or DEFAULT_TEMPLATE
    if tmpl is None:
        raise ValueError("缺少桌签模板：请通过 --template 参数指定桌签模板 .dotx 路径（如 F:/.../桌签.dotx）")
    if not tmpl.exists():
        raise FileNotFoundError(f"桌签模板不存在: {tmpl}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: List[Path] = []
    for i, name in enumerate(names, 1):
        filename = f"{prefix}-{i:02d}-{name}.docx"
        out_path = out_dir / filename
        _prepare_docx_from_template([name], out_path, tmpl, combined=False, placeholder=placeholder)
        logger.info(f"桌签已生成: {out_path}")
        results.append(out_path)

    return results


def generate_table_signs_combined(
    names: List[str],
    output_path: str | Path,
    template_path: Optional[Path] = None,
    placeholder: str = "Jose AI",
) -> Path:
    """
    生成合并的多页桌签文档（每个姓名占正反 2 页，适合批量打印）。

    Args:
        names: 人员姓名列表
        output_path: 输出 .docx 文件路径
        template_path: 桌签模板 .dotx 路径
        placeholder: 模板中占位文本（方案五 P2-3：参数化）

    Returns:
        生成的 .docx 文件路径
    """
    tmpl = template_path or DEFAULT_TEMPLATE
    if tmpl is None:
        raise ValueError("缺少桌签模板：请通过 --template 参数指定桌签模板 .dotx 路径（如 F:/.../桌签.dotx）")
    if not tmpl.exists():
        raise FileNotFoundError(f"桌签模板不存在: {tmpl}")

    out = Path(output_path)
    _prepare_docx_from_template(names, out, tmpl, combined=True, placeholder=placeholder)
    logger.info(f"合并桌签已生成: {out} ({len(names)} 人)")
    return out


def parse_name_list(text: str) -> List[str]:
    """
    解析名单文本。支持格式：
    - 每行一个人名
    - 逗号/空格/顿号分隔的多个人名（在同一行）
    - 空行和 # 注释被忽略

    FIX-B001 L2（防御）：入口剥离 UTF-8 BOM（\ufeff 的 isspace() 为 False，
    strip()/正则 \\s 均无法去除），防止首个名字长度 +1 导致字号降档。
    """
    if text and text[0] == '\ufeff':
        text = text[1:]
    names: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 尝试用分隔符拆分
        parts = re.split(r'[,，、\s]+', line)
        for p in parts:
            p = p.strip()
            if p and not p.startswith("#"):
                names.append(p)
    return names


def validate_page_setup(docx_path: Path, expected: dict | None = None) -> List[str]:
    """校验生成座签的页面布局参数（方案八 P2-1）。

    Args:
        docx_path: 生成的 .docx 路径
        expected: 期望参数（默认从 table_sign.yaml 的 page_setup 读取）

    Returns:
        不合规项列表（空列表表示全部合规）
    """
    issues: List[str] = []
    if expected is None:
        try:
            from core.rules.manager import load_rules_merged
            rules = load_rules_merged("table_sign")
            expected = rules.get("page_setup", {})
        except Exception:
            expected = {}
    if not expected:
        return ["未获取到期望页面参数（table_sign.yaml page_setup）"]

    from docx import Document
    from docx.shared import Mm

    doc = Document(str(docx_path))
    section = doc.sections[0] if doc.sections else None
    if section is None:
        return ["文档无节（section）"]

    # 1. 纸张尺寸
    paper = expected.get("paper_size", "A4").upper()
    if paper == "A4":
        width_ok = 190 <= (section.page_width.mm or 0) <= 215
        height_ok = 290 <= (section.page_height.mm or 0) <= 305
        if not (width_ok and height_ok):
            issues.append(f"纸张非 A4（{section.page_width.mm:.1f}x{section.page_height.mm:.1f}mm）")

    # 2. 页边距（容差 0.2cm）
    margins = {
        "top": expected.get("top_margin", ""),
        "bottom": expected.get("bottom_margin", ""),
        "left": expected.get("left_margin", ""),
        "right": expected.get("right_margin", ""),
    }
    actual_margins = {
        "top": section.top_margin.mm / 10,
        "bottom": section.bottom_margin.mm / 10,
        "left": section.left_margin.mm / 10,
        "right": section.right_margin.mm / 10,
    }
    for key, exp_str in margins.items():
        exp_cm = float(str(exp_str).replace("cm", "").strip()) if exp_str else None
        if exp_cm is not None and abs(actual_margins[key] - exp_cm) > 0.2:
            issues.append(f"边距 {key}: 实际 {actual_margins[key]:.2f}cm ≠ 期望 {exp_cm}cm")

    # 3. 页眉/页脚距离（容差 0.2cm）
    for key, attr in (("header_distance", "header_distance"),
                      ("footer_distance", "footer_distance")):
        exp_str = expected.get(key, "")
        exp_cm = float(str(exp_str).replace("cm", "").strip()) if exp_str else None
        if exp_cm is not None:
            try:
                actual_cm = getattr(section, attr).cm
            except Exception:
                actual_cm = None
            if actual_cm is not None and abs(actual_cm - exp_cm) > 0.2:
                issues.append(f"{key}: 实际 {actual_cm:.2f}cm ≠ 期望 {exp_cm}cm")

    return issues
