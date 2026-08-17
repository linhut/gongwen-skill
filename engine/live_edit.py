# -*- coding: utf-8 -*-
"""
LiveEdit —— 内存级 DocumentModel 编辑会话。

允许在一次解析后多次增量修改段落文本（不写文件），
所有修改在内存中累积，最后一次性调用 generate_docx 输出成品。
避免在连续对话优化场景中反复 parse → generate 的性能开销。

用法：
  with LiveEditSession("原稿.docx") as session:
      session.edit_text(5, "优化后文字", reason="措辞更规范")
      session.edit_text(8, "更多修改", reason="【文字校对】术语统一")
      session.finalize("成品.docx")  # 仅一次 generate

注（P2-7 审计结论）：截至 v1.12.58，本模块尚未被任何 CLI 子命令或 engine
其他模块 import 引用（仅为 chat_review.py 注释中提及）。当前保留为面向未来
Agent 交互式编辑场景的预留 API；若计划删除需先评估"无 CLI 入口"的语义。
"""
from __future__ import annotations
from engine.utils.logger import logger
from engine.core.document.modifier import replace_paragraph_text
from engine.core.document.generator import generate_docx
from engine.core.document.parser import parse_docx
from engine.core.document.models import DocumentModel
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import List

# ARCH-03 修复：engine/ 自身就是搜索路径根，模块内 from core... import 已生效
# 不再需要 sys.path.insert（engine/ 已通过 _bootstrap 或 __init__.py 正确注册）


class LiveEditSession:
    """
    内存级编辑会话。

    上下文管理器，进入时 parse_docx 一次，退出时自动 finalize。
    支持逐段编辑、批量编辑、审稿意见注入。
    """

    def __init__(self, docx_path: str | Path, output_path: str | Path | None = None):
        self.docx_path = Path(docx_path)
        self.output_path = Path(output_path) if output_path else None
        self.model: DocumentModel | None = None
        self.original_model: DocumentModel | None = None
        self.changes: List[dict] = []
        self._snapshots: List[dict] = []
        self._start_time: datetime | None = None
        self._finalized: bool = False

    def __enter__(self) -> "LiveEditSession":
        self._start_time = datetime.now()
        logger.info(f"LiveEdit 开始: {self.docx_path}")
        self.model = parse_docx(str(self.docx_path))
        self.original_model = copy.deepcopy(self.model)
        logger.info(f"  → 已解析: {len(self.model.paragraphs)} 段, {len(self.model.tables)} 表")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None and not self._finalized and self.output_path:
            self.finalize(str(self.output_path))

    # -----------------------------------------------------------------------
    #  核心编辑接口
    # -----------------------------------------------------------------------

    def edit_text(self, para_index: int, new_text: str,
                  reason: str = "", style: str = "",
                  reference: str = "") -> dict | None:
        """
        在内存中修改指定段落的文本。

        Args:
            para_index: 段落索引
            new_text: 新文本
            reason: 修改原因（可含【角色名】标注的审稿意见）
            style: 行文风格标签
            reference: 公文写作规范依据

        Returns:
            包含修改记录的 dict，若段落索引无效返回 None
        """
        if self.model is None:
            raise RuntimeError("LiveEditSession 尚未初始化，请先 parse_docx")
        if not (0 <= para_index < len(self.model.paragraphs)):
            logger.warning(f"段落索引越界: {para_index} (共 {len(self.model.paragraphs)} 段)")
            return None

        para = self.model.paragraphs[para_index]
        original_text = para.text

        if original_text == new_text:
            return None  # 无变化

        # 应用修改（内存中）
        replace_paragraph_text(self.model, para_index, new_text)

        # 记录变更
        change_record = {
            "paragraph_index": para_index,
            "original_text": original_text,
            "optimized_text": new_text,
            "reason": reason,
            "style": style or "庄重严谨",
            "reference": reference,
            "timestamp": datetime.now().isoformat(),
        }
        self.changes.append(change_record)
        logger.info(f"  → 段落 {para_index} 已修改: {original_text[:20]!r} → {new_text[:20]!r}")
        return change_record

    def edit_many(self, edits: List[dict]) -> List[dict]:
        """
        批量编辑。每个 edit 格式同 edit_text 参数。

        Args:
            edits: [{"para_index": 5, "new_text": "...", "reason": "...", ...}, ...]

        Returns:
            成功应用的修改记录列表
        """
        applied = []
        for edit in edits:
            result = self.edit_text(
                para_index=edit.get("para_index", -1),
                new_text=edit.get("new_text", ""),
                reason=edit.get("reason", ""),
                style=edit.get("style", ""),
                reference=edit.get("reference", ""),
            )
            if result:
                applied.append(result)
        logger.info(f"批量编辑: {len(applied)}/{len(edits)} 处已应用")
        return applied

    def rollback_paragraph(self, para_index: int) -> bool:
        """
        撤销对某个段落的最后一次修改（段落级回滚）。

        从 changes 记录中找到该段落的最后一条记录，恢复原文。
        """
        if not self.changes:
            return False
        # 找到该段落的最后一次修改
        para_changes = [c for c in reversed(self.changes) if c["paragraph_index"] == para_index]
        if not para_changes:
            return False
        last = para_changes[0]
        replace_paragraph_text(self.model, para_index, last["original_text"])
        # 从记录中移除
        idx = len(self.changes) - 1 - self.changes[::-1].index(last)
        reverted = self.changes.pop(idx)
        logger.info(
            f"  → 段落 {para_index} 已回滚: {reverted['optimized_text'][:20]!r} → {reverted['original_text'][:20]!r}")
        return True

    def save_snapshot(self, description: str = "") -> int:
        """
        保存当前文档状态快照（含模型深拷贝 + 变更记录）。

        S12 修复：限制快照数量（默认最多 20 个），超过时丢弃最旧快照，
        防止长会话中深拷贝导致内存线性增长。

        Args:
            description: 快照描述（如"第一次优化后"）

        Returns:
            快照序号（从 1 起）
        """
        if self.model is None:
            raise RuntimeError("LiveEditSession 尚未初始化")
        self._snapshots.append({
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "model": copy.deepcopy(self.model),
            "changes": copy.deepcopy(self.changes),
        })
        # S12：容量上限 20 个，丢弃最旧快照
        _MAX_SNAPSHOTS = 20
        if len(self._snapshots) > _MAX_SNAPSHOTS:
            dropped = self._snapshots.pop(0)
            logger.info(f"  🧹 快照超上限({_MAX_SNAPSHOTS})，已丢弃最旧: {dropped.get('description', '未命名')}")
        logger.info(f"  📸 快照 #{len(self._snapshots)} 已保存: {description or '未命名'}")
        return len(self._snapshots)

    def rollback_snapshot(self, steps: int = 1) -> bool:
        """
        回退到指定步数前的快照状态（快照级回滚）。

        与段落级 rollback_paragraph(para_index) 不同，此版本回退整个文档状态：
        - 有快照时：回退到倒数第 steps 个快照
        - 无快照时：回退所有变更（恢复原始模型）

        Args:
            steps: 回退步数（默认 1）

        Returns:
            是否回退成功
        """
        if self.model is None:
            return False

        if self._snapshots and len(self._snapshots) >= steps:
            target_idx = len(self._snapshots) - steps
            target = self._snapshots[target_idx]
            self.model = copy.deepcopy(target["model"])
            self.changes = copy.deepcopy(target["changes"])
            # NI11 修复：只丢弃目标之后的快照，保留目标本身及其之前——回退后仍可继续回退
            self._snapshots = self._snapshots[:target_idx + 1]
            logger.info(
                f"  ↩️  已回退 {steps} 步到快照: {target.get('description', '未命名')}（剩余 {len(self._snapshots)} 个快照可继续回退）")
            return True

        if steps == 1 and self.original_model is not None:
            # 无快照时回退全部：恢复原始模型
            self.model = copy.deepcopy(self.original_model)
            self.changes = []
            self._snapshots = []
            logger.info("  ↩️  无快照，已回退全部变更（恢复原稿）")
            return True

        return False

    def snapshot_count(self) -> int:
        """当前快照数量。"""
        return len(self._snapshots)

    # -----------------------------------------------------------------------
    #  输出接口
    # -----------------------------------------------------------------------

    def generate_diff_report(self) -> str:
        """生成当前所有变更的文本摘要（适合在对话中展示）。"""
        if not self.changes:
            return "暂无变更。"
        lines = []
        for c in self.changes:
            idx = c["paragraph_index"]
            orig = c["original_text"][:40]
            opt = c["optimized_text"][:40]
            reason = c.get("reason", "")
            lines.append(f"  📝 段落 {idx}:")
            lines.append(f"    原文: {orig}{'...' if len(c['original_text']) > 40 else ''}")
            lines.append(f"    优化: {opt}{'...' if len(c['optimized_text']) > 40 else ''}")
            if reason:
                lines.append(f"    说明: {reason}")
            lines.append("")
        return "\n".join(lines)

    def finalize(self, output_path: str | Path | None = None) -> Path:
        """
        结束编辑会话并输出成品。

        Args:
            output_path: 输出 .docx 路径（若未在构造时指定）

        Returns:
            生成的 .docx 文件路径
        """
        if self._finalized:
            raise RuntimeError("LiveEditSession 已结束，不能重复 finalize")
        if self.model is None:
            raise RuntimeError("LiveEditSession 尚未初始化")

        out = Path(output_path) if output_path else self.output_path
        if out is None:
            raise ValueError("请指定输出路径")

        # 生成成品
        result = generate_docx(self.model, str(out))
        self._finalized = True

        elapsed = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        logger.info(f"LiveEdit 完成: {result} ({len(self.changes)} 处修改, {elapsed:.1f}s)")

        # 保存变更日志（与成品同名同目录，.json 后缀）
        if self.changes:
            log_path = out.with_suffix(".changes.json")
            log_path.write_text(
                json.dumps({
                    "source": str(self.docx_path),
                    "output": str(out),
                    "elapsed_seconds": round(elapsed, 1),
                    "total_changes": len(self.changes),
                    "changes": self.changes,
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"变更日志已保存: {log_path}")

        return result

    def finalize_both(self, output_base: str | Path, style: str = "庄重严谨",
                      version: int = 1) -> tuple[Path, Path | None]:
        """
        用户确认无更多优化后，同时输出两份文档，文件名遵循 SKILL.md 命名规范：

        - 干净版（路径 A 规则）：修订版+{原文档名}+{日期}+v{版本号}.docx
        - 差异对比版（路径 B 规则）：{原文档名}+{内容风格}+{日期}+v{版本号}.docx

        Args:
            output_base: 文档名称基础（不含路径和扩展名），如"关于XX的通知"
            style: 内容风格标签，如"庄重严谨"（默认）
            version: 版本号，从 1 起始（默认）

        Returns:
            (clean_path, diff_path) 两个文件的路径
        """
        from datetime import date
        from optimizer import create_diff_document

        today_str = date.today().strftime("%Y-%m-%d")
        stem = str(output_base).replace(".docx", "")

        # 干净版 → 路径 A 规则：修订版+{原文档名}+{日期}+v{版本号}.docx
        clean_name = f"修订版+{stem}+{today_str}+v{version}.docx"
        clean_path = Path(self.docx_path).parent / clean_name

        # 差异对比版 → 路径 B 规则：{原文档名}+{内容风格}+{日期}+v{版本号}.docx
        diff_name = f"{stem}+{style}+{today_str}+v{version}.docx"
        diff_path = Path(self.docx_path).parent / diff_name

        # 1. 生成干净版
        clean = self.finalize(str(clean_path))

        # 2. 生成差异对比版
        if self.changes:
            create_diff_document(
                original_path=str(self.docx_path),
                output_path=str(diff_path),
                changes=self.changes,
                keep_format=True,
            )
            logger.info(f"差异对比版已生成: {diff_path} ({len(self.changes)} 处变更)")
            return clean, diff_path

        logger.info("无变更，跳过差异对比版生成")
        return clean, None

    @property
    def change_count(self) -> int:
        """当前已应用的修改数。"""
        return len(self.changes)
