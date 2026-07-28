# 公文格式优化助手 · 使用提示词

> 给 AI Agent 的指令模板，用于处理中文公文格式检查和优化任务。
> 基于 GB/T 9704《党政机关公文格式》国家标准。

---

## 🟢 最小可用指引（给不熟悉本工具的 LLM）

如果你记不住所有命令，只记住这 **3 条**就够了。**不确定时永远用第 1 条，绝对安全。**

```
# 1️⃣ 用户说"帮我看看/检查这个文件" → 🔍 只读，不改文件，绝对安全
python gongwen.py check 文件.docx

# 2️⃣ 用户说"修改一下内容" → ✏️ 只改内容，不改格式
python gongwen.py optimize-content 原文.docx --changes 修订内容.json --apply

# 3️⃣ 用户确认要改格式 → 🔧 先 check 展示问题，用户确认后再执行
python gongwen.py optimize 文件.docx -o 优化版.docx
```

**不记得参数也没关系**，系统会自动推断文档类型和输出文件名。
**不确定用什么命令**，就先用 `check`（绝对安全）。
**如果是对话模式（无执行权限）**，把上面命令复制给用户让他们自己执行。

### 决策速查

```
用户说"帮我看看" / "检查一下"
  → 用什么？ → check（只读，安全）

用户说"帮我改改内容" / "润色一下"
  → 用什么？ → optimize-content（只改内容不改格式）

用户说"修复格式" / "优化排版"
  → 注意！这是改格式的命令，必须先 check 展示问题 → 问用户确认 → 再 optimize

用户说"把这段文字转成公文"
  → 用什么？ → md2docx（会生成含格式的新文件）
```

---

## 📌 基础指令模板

```
请使用 gongwen-skill 帮我处理以下公文任务：

【任务类型】：检查 / 优化 / 生成模板 / Markdown 转公文 / 自定义规则
【文件路径】：xxx.docx（或 xxx.md）
【公文类型】：notice / report / request / letter / meeting / ...（见下方类型列表）
【输出要求】：优化后文件保存到 xxx.docx

【补充说明】：
- 检查时请先展示问题清单，询问我是否确认修复
- 问题按 P0（格式错误）/ P1（次要）/ P2（建议）分级展示
```

---

## 🎯 场景化 Prompt 示例

### 场景一：检查现有公文

```
请帮我检查这份公文的格式是否合规。

请按以下步骤操作：
1. 先执行 check 命令，展示 P0/P1/P2 问题分级
2. 用表格形式向我呈现主要问题
3. 询问我是否要自动修复这些问题
4. 若我确认，再执行 optimize 命令

文件：./会议纪要.docx
类型：meeting
```

### 场景二：生成模板 + 填写内容

```
请帮我生成一份通知模板，然后我填入内容后你再帮我检查格式。

步骤：
1. 先生成空白模板：template notice -o 通知模板.docx
2. 等我填写完内容后，我告诉你文件名
3. 然后帮我 check 格式
4. 展示问题后询问我是否要 optimize

通知要求：
- 类型：通知
- 主送机关：各部门、各子公司
- 落款：XX集团有限公司
- 日期：2026年7月24日
```

### 场景三：Markdown 草稿转正式公文

```
我有以下 Markdown 内容，请帮我转为正式的公文 .docx 格式。

文件：./工作报告.md
公文类型：report
落款单位：XX局办公室
日期：2026年7月24日

转好后帮我检查一遍格式，有问题的话展示给我看再决定是否修复。
```

### 场景四：自定义单位格式标准

```
我们单位有自己的一套公文格式标准，需要自定义规则。

请先帮我导出通知类型的当前规则作为参考：
- rule-export notice -o 本单位通知规范.yaml

我需要修改以下内容：
- 正文字号改为小三（15pt）
- 页边距改为上35下30左25右25

请指导我如何修改 YAML 文件，然后帮我导入自定义规则。
```

### 场景五：对公文内容进行修订 ✨

```
我有一份公文需要做内容修改，请帮我做行内修订。

原文：./会议纪要.docx
公文类型：meeting
修订背景：根据上级最新文件精神
修订语境：面向各区县单位发文
修订角度：庄重严谨

以下是修订后的内容（请直接在原文基础上做行内修订）：
---
各部门、各子公司：
现将2026年第二季度工作会议纪要印发给你们，请结合实际认真贯彻落实。
...

请按以下要求处理：
1. 修改处用红色字体高亮
2. 删除的内容加红色 + 删除线
3. 每处修改在段落后附完整的【修改说明】【依据】【行文风格】
   - 【修改说明】要具体：说明改了什么、为什么改，不要只写"优化措辞"
   - 【依据】要详细：引用具体的会议/文件/政策名称
   - 【行文风格】使用 prompts/style-prompts.md 中的风格：庄重严谨/平实简洁/宏观概括/请示商洽/法规条文/会议主持词
4. 不要改变原文的排版格式
5. 不要额外加粗内容
6. 生成单一版本即可，不要两个版本
```

---

## 📋 支持的公文类型速查

| 中文 | 命令名 | 说明 |
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

---

## 📐 常用命令速查

```bash
# 查看版本
python gongwen.py --version

# 列出所有类型（🔍 只读）
python gongwen.py list-types

# 检查格式（🔍 只读，推荐先执行）
python gongwen.py check 文件.docx -t notice

# 只看严重问题（🔍 只读）
python gongwen.py check 文件.docx -t notice -s P0 --json

# 一键优化（🔧 会修改字体/行距/边距等格式！默认交互确认）
python gongwen.py optimize 文件.docx -o 文件_优化版.docx -t notice

# 跳过确认（🔧 已知问题后快速修复格式）
python gongwen.py optimize 文件.docx -o 文件_优化版.docx -t notice -y

# 选择性修复（🔧 仅修改指定规则）
python gongwen.py optimize 文件.docx -o 文件_优化版.docx --selected-rules FIX-N001,FIX-N002

# 仅保留格式、不做任何修复（🔧 跳过格式规则）
python gongwen.py optimize 文件.docx -o 文件_优化版.docx --content-only

# 内容修订对比（✏️ 只改内容不改格式！）
# 先准备 修订内容.json（格式见 SKILL.md 路径B 变更JSON格式章节）
python gongwen.py optimize-content 原文.docx --changes 修订内容.json --apply -o 修订对比.docx

# 生成模板（🔧 生成新文件，含标准排版）
python gongwen.py template notice -o 通知模板.docx

# Markdown 转公文（✏️ 只改内容不改格式）
python gongwen.py md2docx 草稿.md -o 公文.docx -t report --signer "XX局" --date "2026年7月24日"

# 规则管理（🔍 只读）
python gongwen.py rule-list
python gongwen.py rule-export notice -o notice_rules.yaml
```

---

## 💬 交互确认模板（AI Agent 参考）

向用户展示检查结果时推荐的格式：

```
📋 格式检查报告（xxx.docx）
──────────────────────────────
🔴 P0（格式错误）：3 项
   · 标题字体（应为方正小标宋简体，当前为宋体）
   · 页边距（上37mm 应为 37mm，当前为 25mm）
   · 行距（应为 28.95pt，当前为单倍行距）

🟡 P1（次要问题）：5 项
   · 正文缩进（应为首行缩进 2 字符）
   · 西文字体（应为 Times New Roman）
   · ...

🟢 P2（建议项）：2 项

是否要自动修复以上所有问题？[Y/n]
（或输入 python gongwen.py optimize 文件.docx --selected-rules FIX-xxx 选择性修复）
```

---

> **项目地址**：https://github.com/linhut/gongwen-skill
> **许可证**：MIT License · (c) 2026 Jose AI
