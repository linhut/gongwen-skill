---
name: gongwen-skill
description: 中文公文文档格式化与语言风格助手。当用户需要处理 .docx 公文（通知/请示/报告/函/会议纪要/意见/纪要等 22 类），按 GB/T 9704 国家标准做格式检查、自动修复、生成标准模板、注入版头版记页码、内容优化差异对比，或需要公文语言风格改写时使用。完全自包含，克隆即用，无需数据库或后端服务。
---

<!--
公文文档格式化 Skill
(c) 2026 Jose AI (https://www.linhut.cn)
项目出处：AI 公文智能优化助手（https://github.com/linhut/document-ai-assistant）
Licensed under the MIT License. See the LICENSE file for details.
-->

# 公文文档格式化 Skill（GB/T 9704）

---

## 快速开始

这个 Skill 做三件事：**格式修复**（不改文字）、**内容优化**（润色文字出对比版）、**生成模板**（直接出空白公文）。

```
我有 .docx 文件          → 路径 A：格式修复（排版标准化）
我要润色文字看到改动     → 路径 B：内容优化（出对比版）
我还没有文档             → 路径 C：生成模板（直接填空）
```

---

## 用户交互指引（Agent 必须遵守）

### 第一步：确认路径（必须）

用通俗语言问用户走哪条路，**不允许跳过**：

> 这个工具支持三种处理方式：
> - **格式优化**：不改文字，只修排版（字体/字号/页边距/行距/缩进），按国标标准化
> - **内容优化**：润色文字表达，生成带标记的对比文档——原文灰色删除线、修改处红色高亮、每段附修改说明
> - **生成模板**：直接生成一份空白公文模板，按国标设好版式

若用户说「帮我优化一下」，必须追问是改格式还是改内容。

### 第二步：告知输出物

执行前明确说会生成什么文件、包含什么标记。

### 第三步：执行后验证

执行完告诉用户：改了几处、标记是否到位、格式是否合规。

---

## 执行标准总则

### 所有路径通用

| 标准项 | 要求 |
|--------|------|
| 格式基准 | GB/T 9704：上 3.7cm / 下 3.5cm / 左 2.8cm / 右 2.6cm |
| 正文字体 | 仿宋_GB2312 三号 16pt |
| 标题字体 | 宋体 二号 22pt 或 楷体 |
| 行距 | 28 磅固定值 |
| 首行缩进 | 2 字符 |
| 对齐 | 两端对齐 |

### 路径 B 特有：格式继承原则

**只改文字，不改格式。** 差异对比文档必须完整继承原文档的字体、字号、行距、缩进、对齐、页边距。

`optimize-content` 内部自动从原文档段落读取格式并继承。Agent **不可**在路径 B 前后跑 `optimize`（格式修复），会覆盖原文档格式。

### 路径 B 特有：无原文档时

1. 确认公文类型（report / notice / request 等 22 种之一）
2. `md2docx` 生成初稿（必须指定 `-t`）
3. `optimize` 套 GB/T 9704 规范格式
4. 最终交付经过标准化后的文档

---

## 路径 A：格式修复

**不改内容，只修排版。** 输出无标记的成品文档。

```bash
# 三步走
python gongwen.py check 文件.docx -t <类型> --json     # 第1步：检查问题
python gongwen.py optimize 文件.docx -o 成品.docx -t <类型> --apply  # 第2步：修复
python gongwen.py check 成品.docx -t <类型> --json    # 第3步：验证
```

### 检查结果分级

| 级别 | 含义 | 处理 |
|------|------|------|
| P0 | 必须修复（字体/字号/页边距不符国标） | `optimize` 自动修 |
| P1 | 建议修复（缩进/对齐问题） | `optimize` 自动修 |
| P2 | 可选修复（多余空行等） | `optimize` 自动修 |

### 可选增强

```bash
# 正文首句加粗
python gongwen.py bold-first 文件.docx -o 成品.docx

# 注入版头版记页码
python gongwen.py optimize 文件.docx -o 成品.docx --layout 版式.json

# 单独补版式要素
python gongwen.py header 文件.docx --org-name 单位全称 --doc-number "发文编号"
python gongwen.py footer 文件.docx --cc 抄送单位 --printer 印发单位 --print-date 印发日期
python gongwen.py pagenum 文件.docx --alignment center
```

---

## 路径 B：内容优化（当前文档场景已全部使用此路径）

**润色文字，保留格式。** 输出带修改标记的差异对比文档。

### 完整流程

```
第0步：读取原文档格式（字体/字号/行距/缩进/对齐/边距）
第1步：LLM 逐段分析 → changes.json
第2步：gongwen.py optimize-content → 差异对比文档（自动继承原文档格式 + 声明文字）
第3步（可选）：校对确认后 optimize 生成无标记成品
```

### 第0步：读取原文档格式

在生成 changes.json 前，读取原文档的格式属性，作为 LLM 优化文本时的参考约束。

```python
import docx
doc = docx.Document("原文档.docx")
# 读取：每段字体/字号/行距/缩进/对齐方式
# 读取：页边距
```

这些数据仅供 LLM 参考，`optimize-content` 内部会自动从原文档继承格式，Agent 无需手动传递。

### 第1步：变更 JSON

`changes.json` 格式：

```json
{
  "changes": [
    {
      "paragraph_index": 5,
      "original_text": "原段落文字",
      "optimized_text": "优化后的文字",
      "reason": "修改说明：为什么改、改了什么",
      "reference": "依据：国标条款、政策文件、规范等"
    }
  ]
}
```

**修改原则**：
- 每部分修改点控制在 3 处以内
- 优先级：笔误 > 语病 > 措辞润色 > 结构优化
- 不编造数据、不替换事实信息、缺失用 XXX 占位
- 优化后文字必须能独立成段，保持原段落信息完整

### 第2步：生成差异对比文档

```bash
python gongwen.py optimize-content 原文档.docx -o 对比文档.docx --changes changes.json --apply
```

**标记规则**：
- 原文被修改/删除：灰色（#999999）+ 删除线
- 新增/修改后：红色（#E00000）高亮
- 未改动：黑色正常格式
- 每段末尾：楷体_GB2312 五号（10.5pt）灰色 `（【修改说明】xxx 【依据】xxx）`
- 文档末尾：自动追加 `（内容由GongWen-skills AI生成，仅供参考）` 灰色小字

**自定义声明文字**（可选）：

```bash
# 覆盖默认声明
python gongwen.py optimize-content 原文.docx --changes changes.json --apply --disclaimer "（本稿经AI辅助生成，请人工复核）"

# 不使用声明
python gongwen.py optimize-content 原文.docx --changes changes.json --apply --disclaimer ""
```

### 第3步（可选）：生成无标记成品

用户确认对比版无误后：

```bash
python gongwen.py optimize 对比文档.docx -o 最终成品.docx -t <类型> --apply
```

### 表格和图片处理

当原文档包含表格或图片时：

- **表格**：`optimize-content` 在生成差异文档时会自动保留表格在原位置，不参与 diff 标注；表格内的段落不会被内容优化处理
- **图片**：`_replace_paragraph_content` 自动保留含图片（w:drawing / w:pict）的 run，不参与 diff
- **定位**：表格和图片均通过 `insert_after_index` 机制保持在原文档中的相对位置

若需要对表格内容做优化，建议先将表格数据提取为文本，走路径 B 优化后再手动回填。

### 从零生成（无原文档）

```bash
# 第1步
python gongwen.py md2docx 草稿.md -o 初稿.docx -t <类型> --signer 落款单位 --date 日期

# 第2步
python gongwen.py optimize 初稿.docx -o 成品.docx -t <类型> --apply
```

两次都要指定同一 `-t` 类型。

---

## 路径 C：生成模板

```bash
python gongwen.py template <类型> -o 模板.docx
```

自动按 GB/T 9704 设置页边距、字体、字号、行距、页码。类型必填。

---

## 跨平台调用说明

本 Skill 支持两种调用方式，在 CLI 和 AI 对话（如豆包 / Marvis / Coze）中均可用。

### 方式一：CLI 直接调用

适用于本地命令行或脚本自动化：

```bash
cd engine
python ../gongwen.py optimize 文件.docx -o 成品.docx -t report --apply
python ../gongwen.py optimize-content 文件.docx --changes changes.json --apply
```

### 方式二：Agent 对话调用

适用于 AI 对话助手（豆包、Marvis 等），Agent 应：

1. 先走「用户交互指引」三步确认路径
2. 用 `shell_executor` 执行 CLI 命令（路径 A/C）或按路径 B 流程逐步处理
3. 路径 B 时：先用 python-docx 读格式 → LLM 分析 → 写 changes.json → 调 `optimize-content` → 告知用户产物路径
4. 执行后验证产物并展示关键指标（修复数、变更数、格式问题）

### 路径 B 对话流程示例

```
用户: 帮我优化这个公文的表达
Agent: [确认是格式优化还是内容优化]
用户: 内容优化
Agent: [读取原文档格式 → LLM 分析生成 changes.json → 执行 optimize-content]
Agent: 已生成对比版 v5.docx，共 6 处变更，字体/行距均继承原文档。
      文件路径：C:\...\对比版_v5.docx
      文档末尾已标注 AI 生成声明。
```

---

## 22 种公文类型（`-t` 参数）

| 类型值 | 中文名 | 类型值 | 中文名 |
|--------|--------|--------|--------|
| `notice` | 通知 | `request` | 请示 |
| `report` | 报告 | `letter` | 函 |
| `meeting` | 会议纪要 | `minutes` | 纪要 |
| `decision` | 决定 | `announcement` | 通告 |
| `notice_public` | 公告 | `command` | 命令 |
| `bulletin` | 通报 | `bill` | 议案 |
| `reply` | 批复 | `instruction` | 指示 |
| `regulation` | 制度 | `communique` | 公报 |
| `opinion` | 意见 | `summary` | 总结 |
| `work_plan` | 方案/计划 | `table_sign` | 桌签 |
| `technical_proposal` | 技术方案 | `resolution` | 决议 |

不确定类型先 `python gongwen.py list-types`。

---

## 常见问题与排错

| 问题 | 原因 | 解决 |
|------|------|------|
| 对比文档字体/行距与原文档不一致 | `get_effective_font` 回退到了 ASCII 字体 | 检查 `parser_format.py` 的 `_safe_pt2` 和行距解析 |
| 删除线不生效 | `RunFormat` 缺少 `strikethrough` 字段或 pipeline 未传递 | 确保 models.py → generator.py → optimizer.py 三处都处理了 strikethrough |
| changes.json JSON 解析失败 | 中文引号/特殊字符未正确转义 | 用 `json.dump` 写入，确保 `ensure_ascii=False` |
| 对比文档末尾无声明 | CLI 传了 `--disclaimer ""` 或 None 覆盖默认值 | 不传 `--disclaimer` 即使用默认声明 |

---

## 使用红线

- 不伪造、冒用真实机关正式发文；生成物仅为草稿，正式发文须走审核流程
- 不编造政策依据、数据、结论；缺失信息用 `XXX` 占位
- 涉密材料先脱敏再处理
- 内容优化必须逐段标注修改说明和依据，不允许无痕覆盖

---

## 项目仓库

- **父项目**（桌面应用 + 完整引擎）：https://github.com/linhut/document-ai-assistant
- **本 Skill**（精简 CLI 版）：嵌入在 `document-skills/gongwen-skill/` 目录
- 引擎核心目录：`engine/core/document/`（parser / generator / modifier / models / font_utils）

**版权**：(c) 2026 Jose AI（https://www.linhut.cn），MIT 许可证。完整命令与架构见 `REFERENCE.md`。

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-07-25 | 新增交互指引、格式继承原则、表格/图片处理说明 |
| v1.0 | 2026-07-24 | 初始版本，支持路径 A/B/C |
