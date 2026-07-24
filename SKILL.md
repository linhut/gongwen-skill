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

## 用户交互协议（AI Agent 必读）

与用户交互时必须遵循以下协议，确保用户体验流畅、确认流程合理：

### 1. 先诊断，后操作

1. **先 `check`**：拿到问题清单后，先向用户清晰摘要问题（P0=格式错误 / P1=次要 / P2=建议）
2. **询问意愿**：展示问题分级和数量后，询问用户是否需要进行修复，绝不可以未经确认直接执行 `optimize`
3. **确认后执行**：用户明确同意后再执行 `optimize` 或特定修复

> ❌ 错误示范："我帮你优化了文件"（未展示问题、未询问）
> ✅ 正确示范："检查发现 3 个 P0 问题和 5 个 P1 问题（共 12 项），是否要自动修复这些格式问题？"

### 2. 修复前展示关键变更

执行 `optimize` 前，应至少让用户了解：
- P0 问题的数量和类型（如字体错误、页边距错误等）
- 是否会对文档布局产生明显影响
- 预计的修复范围

### 3. 提供备选方案

若用户不想全量修复，提供备选：
- **选择性修复**：`optimize --selected-rules FIX-N001,FIX-N002`（仅修复指定的规则）
- **仅检查**：用户可先看 JSON 输出自行决定
- **分步操作**：先修 P0，再修 P1，最后修 P2

### 4. 错误处理的礼貌回退

- 文件不存在或解析失败时，给出明确的下一步建议
- 类型指定错误时，列出可用类型让用户选择

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
