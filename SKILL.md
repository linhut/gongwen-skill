---
name: gongwen-skill
description: 中文公文文档格式化与语言风格助手。当用户需要处理 .docx 公文（通知/请示/报告/函/会议纪要/意见/纪要等 22 类），按 GB/T 9704 国家标准做格式检查、自动修复、生成标准模板、注入版头版记页码，或需要公文语言风格改写（庄重规范、简明扼要）时使用。完全自包含，克隆即用，无需数据库或后端服务。
---

<!--
公文文档格式化 Skill
(c) 2026 Jose AI (https://www.linhut.cn)
项目出处：AI 公文智能优化助手
Licensed under the MIT License. See the LICENSE file for details.
-->

# 公文文档格式化 Skill（GB/T 9704）

把 `.docx` 公文按 **GB/T 9704《党政机关公文格式》** 国家标准检查、修复、生成。完全自包含，`pip install -r requirements.txt` 后 `python gongwen.py <命令>` 即可用。

## 第一步：先判断用户属于哪种场景

| 用户想做的事 | 走这条流程 |
|--------------|-----------|
| **有一份 .docx，想让格式合规** | → 流程 A（检查修复） |
| **有文字/Markdown 内容，想生成公文** | → 流程 B（内容成文） |
| **要一份空白公文模板** | → 流程 C（一条命令） |

先确认场景，再按对应流程走。不要一次把所有命令列给用户。

---

## 流程 A：已有公文 → 格式合规（最常用）

```bash
# 1. 先检查，把问题清单讲给用户（P0=必须改 / P1=次要 / P2=建议）
python gongwen.py check 用户文件.docx -t notice --json

# 2. 用户确认后一键修复生成
python gongwen.py optimize 用户文件.docx -o 成品.docx -t notice
```

`-t` 是公文类型（见下方类型表，默认 notice）。若用户只想改部分问题，加 `--selected-rules FIX-N001,FIX-N002`。

**需要红头/版记/页码时**，写一个 `版式.json` 让 optimize 一步到位：

```bash
python gongwen.py optimize 用户文件.docx -o 成品.docx --layout 版式.json
```

`版式.json` 格式（三块都可选）：
```json
{
  "header": {"org_name": "国家民委办公厅", "doc_number": "民委办发〔2026〕1号", "signer": "张三"},
  "footer": {"cc": "各省民委", "printer": "国家民委办公厅", "print_date": "2026年7月23日"},
  "page_number": {"format": "— {PAGE} —", "alignment": "center"}
}
```

---

## 流程 B：文字内容 → 公文（先写文字，再排版）

```bash
# 把 Markdown/纯文本内容直接排成公文（# 标题、** 加粗、| 表格 自动识别）
python gongwen.py md2docx 草稿.md -o 公文.docx -t notice --signer 某某单位 --date 2026年7月23日

# 也支持管道
cat 草稿.md | python gongwen.py md2docx - -o 公文.docx
```

若用户内容口语化、不像公文，**先用 `prompts/style-prompts.md` 里的风格提示词改写文字**，再 md2docx 成文，最后可选 optimize 走一遍格式。这样「语言」和「排版」双合规。

`prompts/style-prompts.md` 含 6 套风格：庄重严谨 / 平实简洁 / 宏观概括 / 请示商洽 / 法规条文 / 会议主持词（有高度有重点）。

---

## 流程 C：要空白模板 → 一条命令

```bash
python gongwen.py template notice -o 通知模板.docx
```

---

## 单独注入版式要素（进阶，通常用流程 A 的 --layout 即可）

```bash
python gongwen.py header  in.docx --org-name 国家民委办公厅 --doc-number "民委办发〔2026〕1号"   # 版头
python gongwen.py footer  in.docx --cc 各省民委 --printer 国家民委办公厅 --print-date 2026年7月23日  # 版记
python gongwen.py pagenum in.docx --alignment center                                          # 页码
```

## 22 种公文类型（`-t` 参数取值）

`notice`(通知) `request`(请示) `report`(报告) `letter`(函) `meeting`(会议纪要)
`minutes`(纪要) `decision`(决定) `announcement`(通告) `notice_public`(公告)
`command`(命令) `bulletin`(通报) `bill`(议案) `reply`(批复) `instruction`(指示)
`regulation`(制度) `communique`(公报) `opinion`(意见) `summary`(总结)
`work_plan`(方案/计划) `table_sign`(桌签) `technical_proposal`(技术方案) `resolution`(决议)

不确定类型时先跑 `python gongwen.py list-types` 查看。

## 标准格式（GB/T 9704，引擎自动套用）

| 位置 | 字体 | 字号 |
|------|------|------|
| 标题 | 方正小标宋简体 | 二号（22pt） |
| 正文 | 仿宋_GB2312 | 三号（16pt） |
| 西文/数字 | Times New Roman | — |
| 页边距 | 上37 下35 左28 右26 (mm) | — |

## 按单位定制格式（可选）

三层规则优先级 **official < custom < user**。在 `~/.gongwen-skill/user_rules/` 放同名 YAML 即可覆盖官方字体/字号，无需改代码。相关命令：`rule-export`（导出参考）、`rule-import`（导入）、`rule-list`（查看）。详见 `REFERENCE.md`。

## ⚠️ 使用红线

- 不伪造、冒用真实机关正式发文；生成物仅为草稿，正式发文须走审核流程
- 不编造政策依据、数据、结论；缺失信息用 `XXX` 占位
- 涉密材料先脱敏再处理

---

**版权与出处**：本 Skill 源自开源项目「AI 公文智能优化助手」，(c) 2026 Jose AI（https://www.linhut.cn），MIT 许可证。完整命令与架构见 `REFERENCE.md`。
