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

## 何时使用

- 用户提供 `.docx` 公文，要求检查格式是否合规
- 用户要求自动修复公文排版（字体、字号、页边距、行距、缩进、页码）
- 用户要求生成某类公文的标准空白模板
- 用户询问某种公文类型的格式规范
- 用户要求按公文语言风格改写内容（见 `prompts/style-prompts.md`）

## 前置条件

```bash
pip install -r requirements.txt      # python-docx / pydantic / pyyaml
```

## 核心命令

统一入口 `gongwen.py`，所有子命令：

```bash
python gongwen.py list-types                          # 列出 22 种公文类型
python gongwen.py template notice -o 通知模板.docx     # 生成标准模板
python gongwen.py parse    input.docx -o model.json    # 解析为结构化 JSON
python gongwen.py check    input.docx -t notice --json # 只读检查（分级 P0/P1/P2）
python gongwen.py optimize input.docx -o out.docx -t report  # 检查+修复+生成
python gongwen.py generate model.json -o out.docx      # 从 JSON 生成 docx
python gongwen.py md2docx  input.md -o 公文.docx       # Markdown 转公文（支持管道输入）
python gongwen.py rule-export notice -o notice.yaml    # 导出合并规则（用于规则化定制）
python gongwen.py rule-list                            # 列出三层规则
python gongwen.py rule-import my_rules -f rules.yaml   # 导入自定义规则
```

## 支持的公文类型（22 种）

`notice`(通知) `request`(请示) `report`(报告) `letter`(函) `meeting`(会议纪要)
`minutes`(纪要) `decision`(决定) `announcement`(通告) `notice_public`(公告)
`command`(命令) `bulletin`(通报) `bill`(议案) `reply`(批复) `instruction`(指示)
`regulation`(制度) `communique`(公报) `opinion`(意见) `summary`(总结)
`work_plan`(方案/计划) `table_sign`(桌签) `technical_proposal`(技术方案) `resolution`(决议)

## 标准格式（GB/T 9704）

| 位置 | 字体 | 字号 |
|------|------|------|
| 标题 | 方正小标宋简体 | 二号（22pt） |
| 正文 | 仿宋_GB2312 | 三号（16pt） |
| 西文/数字 | Times New Roman | — |
| 页边距 | 上37 下35 左28 右26 (mm) | — |

## 语言风格改写

公文语言风格提示词见 `prompts/style-prompts.md`，含通用底座 + 6 套可直接调用的风格规则（庄重严谨、平实简洁、宏观概括、请示商洽、法规条文、会议主持词/领导讲话）。其中"会议主持词/领导讲话"专门强化"有高度、有重点、有条理、有力度"。改写内容后，可再用 `optimize` 走一遍格式修复，实现「内容风格 + 排版格式」双合规。

## 规则化 / 二次定制

三层规则优先级：**official < custom < user**。用户可在 `~/.gongwen-skill/user_rules/` 放置同名 YAML 覆盖官方规则，实现按单位要求定制格式，无需改代码。详见 `REFERENCE.md`。

## 工作流建议

1. 先 `check --json` 拿到问题清单，向用户说明 P0/P1/P2 问题
2. 若涉及语言风格，参考 `prompts/style-prompts.md` 改写内容
3. 用户确认后 `optimize` 生成修复文件
4. 只修部分问题时用 `--selected-rules` 指定规则 ID

详细架构、修复动作、编程调用方式见 `REFERENCE.md`。

---

**版权与出处**：本 Skill 源自开源项目「AI 公文智能优化助手」，(c) 2026 Jose AI（https://www.linhut.cn），MIT 许可证。
