---
name: gongwen-skill
description: 中文公文文档格式化与语言风格助手。当用户需要处理 .docx 公文（通知/请示/报告/函/会议纪要/意见/纪要等 22 类），按 GB/T 9704 国家标准做格式检查、自动修复、生成标准模板，或需要公文语言风格改写（庄重规范、简明扼要）时使用。完全自包含，克隆即用，无需数据库或后端服务。
---

<!--
公文文档格式化 Skill
(c) 2026 Jose AI (https://www.linhut.cn)
项目出处：AI 公文智能优化助手
Licensed under the MIT License. See the LICENSE file for details.
-->

# 公文文档格式化 Skill（GB/T 9704）

将 `.docx` 公文按 **GB/T 9704《党政机关公文格式》** 国家标准进行解析、检查、自动修复、模板生成，并提供公文语言风格改写提示词。

**完全自包含**：内置最小可运行引擎（parser / rule engine / generator + 23 份规则 YAML），克隆本仓库即可运行，不依赖任何桌面端、数据库或后端服务。

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

## 何时使用

- 用户提供 `.docx` 公文，要求检查格式是否合规
- 用户要求自动修复公文排版（字体、字号、页边距、行距、缩进、页码）
- 用户要求生成某类公文的标准空白模板
- 用户询问某种公文类型的格式规范
- 用户要求按公文语言风格改写内容（见 `prompts/style-prompts.md`）
- 用户提供 Markdown 文本要求转为正式公文

## 前置条件

```bash
pip install -r requirements.txt      # python-docx / pydantic / pyyaml
```

## 核心命令

统一入口 `gongwen.py`，所有子命令：

```bash
# 信息查询
python gongwen.py --version                          # 显示版本号
python gongwen.py list-types                         # 列出 22 种公文类型
python gongwen.py rule-list                          # 列出三层规则

# 模板生成
python gongwen.py template notice -o 通知模板.docx   # 生成标准模板

# 文档解析（只读）
python gongwen.py parse    input.docx -o model.json  # 解析为结构化 JSON

# 格式检查（只读，不修改文件）
python gongwen.py check    input.docx -t notice       # 文本输出（推荐）
python gongwen.py check    input.docx -t notice --json # JSON 输出
python gongwen.py check    input.docx -t notice -s P0 # 只看 P0 严重问题

# 一键优化（检查 + 修复 + 生成）
python gongwen.py optimize input.docx -o out.docx -t report -y   # 自动确认，不询问
python gongwen.py optimize input.docx -o out.docx -t report       # 交互模式（默认）

# 从 JSON 生成
python gongwen.py generate model.json -o out.docx                # 从 JSON 模型生成 docx

# Markdown 转公文（支持管道输入）
python gongwen.py md2docx  input.md -o 公文.docx                 # 文件输入
cat 草稿.md | python gongwen.py md2docx - -o 正式公文.docx       # 管道输入

# 规则管理（高级）
python gongwen.py rule-export notice -o notice.yaml              # 导出合并规则
python gongwen.py rule-import my_rules -f rules.yaml             # 导入自定义规则
```

## 标准工作流

### 场景 A：用户给了一个 .docx 公文 → 检查格式

```
Step 1: python gongwen.py check input.docx -t notice
Step 2: 向用户呈现问题摘要（P0 / P1 / P2 数量 + 主要问题）
Step 3: 询问："是否要自动修复这些问题？[y/N]"
Step 4: 若用户同意 → python gongwen.py optimize input.docx -o 修复版.docx -t notice
Step 5: 若用户想部分修复 → 使用 --selected-rules 指定规则
```

### 场景 B：用户要求生成一份公文模板

```
Step 1: 确认公文类型（若用户未指定，使用 list-types 列出可选）
Step 2: python gongwen.py template notice -o 通知模板.docx
Step 3: 告知用户模板已生成及文件路径
```

### 场景 C：用户有一段 Markdown 内容想转为正式公文

```
Step 1: 确认公文类型（默认 notice，可通过 Front Matter 指定）
Step 2: 确认落款单位、日期等元数据（若用户未提供）
Step 3: python gongwen.py md2docx input.md -o 公文.docx -t notice --signer "XX单位" --date "2026年7月24日"
Step 4: 可选：对生成的 .docx 再执行 optimize 做格式精修
```

### 场景 D：用户需要自定义规则（单位内部标准）

```
Step 1: python gongwen.py rule-export notice -o notice_current.yaml  # 导出当前规则
Step 2: 编辑 YAML 修改字体/字号/边距等
Step 3: python gongwen.py rule-import my_company -f notice_current.yaml  # 导入
Step 4: python gongwen.py rule-list  # 验证规则已加载
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

## 标准格式（GB/T 9704）

| 位置 | 字体 | 字号 |
|------|------|------|
| 标题 | 方正小标宋简体 | 二号（22pt） |
| 正文 | 仿宋_GB2312 | 三号（16pt） |
| 西文/数字 | Times New Roman | — |
| 页边距 | 上37 下35 左28 右26 (mm) | — |

## 语言风格改写

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

## 规则化 / 二次定制

三层规则优先级：**official < custom < user**。用户可在 `~/.gongwen-skill/user_rules/` 放置同名 YAML 覆盖官方规则，实现按单位要求定制格式，无需改代码。详见 `REFERENCE.md`。

## AI Agent 快速参考

### 常用命令速查

| 目标 | 命令 | 说明 |
|------|------|------|
| 检查一个文档 | `check input.docx -t notice` | 只读，安全 |
| 修复文档 | `optimize input.docx -o out.docx -t report -y` | 自动确认 |
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
