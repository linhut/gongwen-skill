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

---

## 🟢 如果你不太确定怎么用（LLM 最小可用指引）

你只需要知道 **3 条最常用的命令**，其他都可以慢慢学：

| 用户说... | 你执行这个命令 | 说明 |
|-----------|--------------|------|
| "帮我看看/检查这个文件" | `check 文件.docx` 🔍 只读 | 绝对安全，不改变任何东西 |
| "修改一下这份公文的内容" | `revise 原文.docx -o 对比.docx -f 修订内容.md` ✏️ | 只改内容不改格式 |
| "修复格式/优化排版" | 先 `check` → 问用户 → 用户确认后 `optimize 文件.docx -o 新文件.docx` 🔧 | 会改字体行距边距 |

> **如果你完全不记得参数**，就直接用上面的格式，工具会自动推断文档类型和输出路径。
> **如果不确定该用哪个命令**，就用 `check`（只读、安全），然后把结果展示给用户问他们要什么。
> **犯错也没关系** — 所有写操作都生成**新文件**，不会覆盖用户原文件。

---

## 🚨 命令修改范围红线（AI Agent 必读）

⚠️ **这是本 Skill 最重要的规则——选错命令会破坏用户文档的格式或内容。**

所有命令按 **修改范围** 分为三类，Agent 必须严格按照用户意图选择：

| 范围 | 命令 | 修改内容 | 修改格式 | 安全级别 |
|------|------|---------|---------|---------|
| 🔍 **只读** | `check` / `parse` / `list-types` / `rule-list` | ❌ 不改 | ❌ 不改 | 🟢 绝对安全 |
| ✏️ **只改内容** | `revise` / `md2docx` | ✅ 改内容 | ❌ 不改格式 | 🟡 安全（保留原排版） |
| 🔧 **改格式** | `optimize` / `template` | ❌ 不改 | ✅ 改字体/边距/行距等 | 🔴 必须用户明确确认 |

### 铁律一：永远从 `check` 开始

**任何对用户文档的处理，第一步永远是 `check`（只读）。** 绝对禁止在未检查前直接执行会修改文档的命令。

> ✅ 正确：`check 文件.docx` → 展示问题 → 询问用户 → 用户确认后再操作
> ❌ 错误：`optimize 文件.docx -y`（未检查、未询问，直接破坏格式）

### 铁律二：格式修改必须经用户明确同意

以下命令**绝对不能**未经用户明确同意就执行：
- 🔴 **`optimize`** — 会修改字体、字号、行距、页边距、缩进！
- 🔴 **`template`** — 会生成新文件（但不修改现有文件，相对安全）

用户说"帮我看看"、"检查一下"、"处理这个文件"→ **只能用 `check`（只读）**

用户明确说"修复格式"、"优化排版"、"调整字体" → 先 `check` 展示问题，**再询问确认**后执行 `optimize`

### 铁律三：只改内容不改格式用 `revise`

当用户要求**修改公文内容**（措辞调整、语句优化、内容修订）但不要求改变排版时：
- ✅ 使用 **`revise`**（生成对比文档，不改原文格式）
- ❌ **绝对不要**用 `optimize`（它会修改字体/行距/边距）

### 铁律四：说"处理"永远按只读处理

当用户的指令模糊（"帮我处理下这个文件"、"你看着办"、"优化一下"），**一律默认按只读处理**：

1. 先执行 `check`（只读，安全）
2. 展示检查结果给用户
3. 询问用户具体要做什么（改内容？修格式？）
4. 用户明确指示后再执行对应命令

> ✅ 正确：用户说"帮我处理这个文件" → Agent 执行 `check` → 展示问题 → "发现 2 个格式问题，是否要修复？需要修改内容的话我也可以生成修订对比"
> ❌ 错误：用户说"帮我处理这个文件" → Agent 执行 `optimize`（擅自修改了格式！）

### 命令修改范围速查

| 命令 | 修改范围 | 典型使用场景 |
|------|---------|-------------|
| `list-types` | 🔍 只读 | 查看支持的公文类型 |
| `rule-list` | 🔍 只读 | 查看已加载的规则 |
| `check` | 🔍 只读 | 检查格式是否合规 |
| `parse` | 🔍 只读 | 导出为 JSON 中间表示 |
| `revise` | ✏️ 只改内容 | 内容修订对比（红色高亮+删除线+修改说明） |
| `md2docx` | ✏️ 只改内容 | Markdown 转公文（保留原文排版） |
| `optimize` | 🔧 改格式 | 自动修复字体/字号/行距/边距 |
| `template` | 🔧 生成新文件 | 生成空白公文模板 |

---

## 流程 A：已有公文 → 格式合规（最常用）

> ⚠️ **`optimize` 会修改字体、行距、页边距等格式**，必须经用户明确同意后才可执行

```bash
# 1. 🔍 先检查，把问题清单讲给用户（只读，不改任何东西）
python gongwen.py check 用户文件.docx -t notice --json

# 2. 用户确认后一键修复生成（🔧 会修改格式！）
python gongwen.py optimize 用户文件.docx -o 成品.docx -t notice
```

`-t` 是公文类型（见下方类型表，默认 notice，支持自动检测）。若用户只想改部分问题，加 `--selected-rules FIX-N001,FIX-N002`。

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

> ✏️ **`md2docx` 只修改内容，不修改格式**，安全

```bash
# 把 Markdown/纯文本内容直接排成公文（# 标题、** 加粗、| 表格 自动识别）
python gongwen.py md2docx 草稿.md -o 公文.docx -t notice --signer 某某单位 --date 2026年7月23日

# 也支持管道
cat 草稿.md | python gongwen.py md2docx - -o 公文.docx
```

若用户内容口语化、不像公文，**先用 `prompts/style-prompts.md` 里的风格提示词改写文字**，再 md2docx 成文。

🔧 如需格式精修 → 最后可选 `optimize`（⚠️ 会修改格式，需用户确认）

`prompts/style-prompts.md` 含 6 套风格：庄重严谨 / 平实简洁 / 宏观概括 / 请示商洽 / 法规条文 / 会议主持词（有高度有重点）。

---

## 流程 C：要空白模板 → 一条命令

> 🔧 **`template` 会生成新文件**，包含标准公文排版格式

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

### 场景 E：用户需要对公文内容进行修订（不改变格式）✨

```
Step 1: 拿到用户提供的原文 .docx 和修订后的文本内容（Markdown / 纯文本）
Step 2: 执行 revise 生成对比文档：
        python gongwen.py revise 原文.docx -o 修订对比.docx -f 修订后.md
Step 3: 向用户解释对比标记含义：
        · 🔴 红色 = 修改后内容（首句加粗）
        · ⚪ 灰色删除线 = 原文被删除部分
        · 💡 修改说明 = 每处变更的修改理由
Step 4: 确认是否需要再次调整
Step 5: 定稿后可选执行 optimize --selected-rules 做格式精修
```

## 支持的公文类型（22 种）

| 类型 | 命令名 | 说明 |
|------|--------|------|
| 通知 | `notice` | 通用通知、事务通知 |
| 请示 | `request` | 请示、呈报 |
| 报告 | `report` | 工作报告、情况报告 |
| 函 | `letter` | 商洽函、答复函 |
| 会议纪要 | `meeting` | 会议记录整理 |
| 纪要 | `minutes` | 会议纪要（简版） |
| 决定 | `decision` | 重大事项决定 |
| 通告 | `announcement` | 社会通告 |
| 公告 | `notice_public` | 正式公告 |
| 命令 | `command` | 行政命令 |
| 通报 | `bulletin` | 情况通报 |
| 议案 | `bill` | 人大/政协议案 |
| 批复 | `reply` | 对请示的批复 |
| 指示 | `instruction` | 工作指示 |
| 制度 | `regulation` | 规章制度 |
| 公报 | `communique` | 正式公报 |
| 意见 | `opinion` | 指导意见 |
| 总结 | `summary` | 工作总结 |
| 方案/计划 | `work_plan` | 工作方案、实施计划 |
| 桌签 | `table_sign` | 会议桌签 |
| 技术方案 | `technical_proposal` | 技术建议书 |
| 决议 | `resolution` | 会议决议 |

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

## ✍️ 语言风格改写

公文语言风格提示词见 `prompts/style-prompts.md`，含通用底座 + 6 套可直接调用的风格规则：

| 风格 | 适用场景 |
|------|---------|
| 庄重严谨 | 通知、决定、意见、规定 |
| 平实简洁 | 函、事务通知、纪要 |
| 宏观概括 | 报告、总结、汇报 |
| 请示商洽 | 请示、呈报、商洽函 |
| 法规条文 | 制度、办法、章程 |
| 会议主持词/领导讲话 | 有高度、有重点、有条理、有力度 |

改写内容后，可用 `optimize` 走一遍格式修复，实现「内容风格 + 排版格式」双合规。

## ⚠️ 使用红线

- 不伪造、冒用真实机关正式发文；生成物仅为草稿，正式发文须走审核流程
- 不编造政策依据、数据、结论；缺失信息用 `XXX` 占位
- 涉密材料先脱敏再处理

## AI Agent 快速参考

### 常用命令速查

| 目标 | 命令 | 说明 |
|------|------|------|
| 检查一个文档 | `check input.docx -t notice` | 只读，安全 |
| 修复文档 | `optimize input.docx -o out.docx -t report -y` | 自动确认 |
| 内容修订对比 | `revise 原文.docx -o 对比.docx -f 修订后.md` | 红色高亮+删除线+修改说明 |
| 生成模板 | `template notice -o 模板.docx` | 空白模板 |
| Markdown 转公文 | `md2docx 草稿.md -o 公文.docx` | 含 Front Matter 支持 |
| 查看规则 | `rule-list --source official` | 三层规则可查 |
| 只看严重问题 | `check input.docx -t notice -s P0 --json` | 精确输出 |

### 确认模板

向用户展示检查结果时，推荐格式：

```
📋 格式检查报告（xxx.docx）
──────────────────────────
🔴 P0（格式错误）：3 项
   · 标题字体（应为方正小标宋简体，当前为宋体）
   · 页边距（上37mm 应为 37mm，当前为 25mm）
   · 行距（应为 28.95pt，当前为单倍行距）

🟡 P1（次要问题）：5 项
   · 正文缩进（应为首行缩进 2 字符）
   · 西文字体（应为 Times New Roman）
   · ...

🟢 P2（建议项）：2 项

是否要自动修复以上所有问题？[y/N] （或输入规则 ID 选择性修复）
```

---

**详细架构、修复动作、编程调用方式见 `REFERENCE.md`。**

**版权与出处**：本 Skill 源自开源项目「AI 公文智能优化助手」，(c) 2026 Jose AI（https://www.linhut.cn），MIT 许可证。
