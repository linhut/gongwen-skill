<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# 公文文档格式化 Skill · gongwen-skill

<p align="center">
  <img src="./logo/A_professional_skill_cover_2026-07-23T02-25-30.png" alt="gongwen-skill 公文文档格式化引擎" width="560">
</p>

> 中文公文全流程处理工具——基于 **GB/T 9704《党政机关公文格式》** 国家标准，支持 **格式检查与修复、内容润色（红色标注对比版）、模板生成、Markdown 转公文、版头版记页码注入** 等完整能力。打包为可被 AI Agent 直接调用的 Skill，完全自包含，克隆即用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![GB/T 9704](https://img.shields.io/badge/standard-GB%2FT%209704-red.svg)

本 Skill 源自开源桌面项目 [AI 公文智能优化助手](https://github.com/linhut/document-ai-assistant)，将其核心格式引擎抽取、剥离桌面端/数据库依赖后独立发行，支持公文的**模板建立、解析、规则检查、自动修复、内容优化、Markdown 转公文**全流程能力。

---
## ✨ 能力一览

<p align="center">
  <img src="logo/A_vertical_promotional_2026-07-23T02-25-30.png" alt="公文技能工作流：输入 .docx → 检查 → 修复 → 合规公文" width="420">
</p>

| 能力 | 命令 | 说明 |
|------|------|------|
| 📋 列类型 | `list-types` | 列出 22 种支持的公文类型 |
| 🏗️ 模板生成 | `template` | 按类型生成 GB/T 9704 标准空白模板 |
| 🔍 解析 | `parse` | `.docx` → 结构化 DocumentModel |
| ✅ 格式检查 | `check` | 按国标检查，分级 P0/P1/P2（只读） |
| 🔧 格式修复 | `optimize` | 自动修复字体/字号/行距/页边距，输出合规文档 |
| ✍️ **内容优化** | **`optimize-content`** | 润色文字，生成红色标注+删除线+修改说明的对比版 |
| 📝 草稿转公文 | `md2docx` | Markdown 文本直接转为格式化 `.docx`（支持 Front Matter） |
| 📄 模型生成 | `generate` | 从 JSON 模型生成 `.docx` |
| 🔴 版头 | `header` | 注入发文机关标志 + 发文字号 + 签发人 + 红色反线 |
| 📑 版记 | `footer` | 注入抄送机关 + 印发机关 + 印发日期 + 分隔线 |
| 🔢 页码 | `pagenum` | 注入 Word PAGE 域动态页码 |
| 🖊️ 首句加粗 | `bold-first` | 正文段落首句自动加粗（公文规范） |
| 📋 桌签生成 | `table-signs` | 批量生成 A5 横版会议桌签 |
| 🔍 审稿生成 | `review` | 按五角色审稿机制生成审稿意见 |
| ⚙️ 规则管理 | `rule-export/import/list` | YAML 规则三层定制（官方/单位/用户） |

## 使用示例

![GongWen-skill 使用示例](docs/example.png)

> 在 AI 对话中调用 gongwen-skill，输入自然语言指令，自动生成符合 GB/T 9704 国标格式的正式公文。

## 🚀 快速开始

```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt

# 生成一份标准通知模板
python gongwen.py template notice -o 通知模板.docx

# 检查公文格式（只读）
python gongwen.py check 公文.docx -t notice --json

# 自动修复格式（--apply 确认执行，默认预览）
python gongwen.py optimize 公文.docx -o 成品.docx -t notice --apply

# 一步到位：检查 + 修复 + 版头/版记/页码全注入（--layout 指向 JSON 配置）
python gongwen.py optimize 公文.docx -o 成品.docx --layout 版式.json

# Markdown 草稿 → 正式公文（支持管道输入和 Front Matter 元数据）
python gongwen.py md2docx 草稿.md -o 正式公文.docx -t report --signer "XX单位" --date "2026年7月29日"

# 管道输入：cat 草稿.md | python gongwen.py md2docx - -o 正式公文.docx

# 内容润色（差异对比版：原文灰色删除线 + 优化后红色高亮 + 修改说明）
python gongwen.py optimize-content 原文.docx -o 修订版.docx --changes 修订内容.json --apply

# 注入版头（发文机关标志 + 发文字号 + 签发人 + 红色反线）
python gongwen.py header 公文.docx -o 红头公文.docx --org-name "XX单位" --doc-number "〔2026〕1号"

# 注入版记（抄送 + 印发机关 + 印发日期）
python gongwen.py footer 红头公文.docx --cc "各单位" --printer "XX办公室" --print-date "2026年7月29日"

# 注入页码（Word PAGE 域动态页码）
python gongwen.py pagenum 红头公文.docx --alignment center

# 正文段落首句自动加粗
python gongwen.py bold-first 公文.docx

# 桌签批量生成（名单每行一人）
python gongwen.py table-signs 名单.txt -o ./桌签/

# 导入自定义规则
python gongwen.py rule-import my_company -f 公司规范.yaml

# 审稿生成
python gongwen.py review report -o 审稿意见.md
```

## 📐 GB/T 9704 标准格式

| 元素 | 字体 | 字号 | 对齐 |
|------|------|:----:|:----:|
| **公文标题** | 方正小标宋简体 | 二号（22pt） | 居中 |
| **一级标题**（一、二、三） | 黑体 | 三号（16pt） | 顶格 |
| **二级标题**（（一）（二）） | 楷体_GB2312 | 三号（16pt） | 首行缩进2字符 |
| **三级标题**（1. 2.） | 仿宋_GB2312 **加粗** | 三号（16pt） | 首行缩进2字符 |
| **正文** | 仿宋_GB2312 | 三号（16pt） | 首行缩进2字符 |
| **西文/数字** | Times New Roman | 与中文字号一致 | — |
| **页边距** | — | — | 上3.7/下3.5/左2.8/右2.6 cm |

## 📚 支持的 22 种公文类型

通知 · 请示 · 报告 · 函 · 会议纪要 · 纪要 · 决定 · 通告 · 公告 · 命令 · 通报 · 议案 · 批复 · 指示 · 制度 · 公报 · 意见 · 总结 · 方案/计划 · 桌签 · 技术方案 · 决议

## ⚙️ 规则化与二次定制

规则以 YAML 定义，三层优先级 **official < custom < user**：

- 官方规则：仓库内 `rules/official/*.yaml`
- 用户覆盖：`~/.gongwen-skill/user_rules/*.yaml`（同名字段覆盖官方）

```bash
python gongwen.py rule-export notice -o notice_rules.yaml
python gongwen.py rule-import my_company -f 公司规范.yaml
```

## ⚠️ 使用红线

- **不伪造、冒用真实机关正式发文** — 生成物仅为草稿，正式发文须走审核流程
- **不编造政策依据、数据、结论** — 缺失信息用 `XXX` 占位
- **涉密材料先脱敏再处理**
- **字体版权** — 方正小标宋简体等字体可能受版权约束，缺少时 Word 会回退

## 🤖 作为 AI Agent Skill 使用

将本仓库放入 Agent 的 skills 目录，Agent 读取 `SKILL.md` 后自动调用命令。支持三条路径：

- **路径 A**：格式修复（不改文字，只修排版）
- **路径 B**：内容优化（润色文字，红色标注对比版）
- **路径 C**：生成公文（从零创建，四步流水线）

## 📦 依赖

仅 3 个纯 Python 包：`python-docx`、`pydantic`、`pyyaml`。无数据库、无 Web 框架、无桌面端。

## 📄 许可证与出处

MIT License · **(c) 2026 Jose AI** · https://www.linhut.cn

本 Skill 源自开源项目 [AI 公文智能优化助手](https://github.com/linhut/document-ai-assistant)。格式引擎与规则 YAML 版权归原作者所有，依 MIT 许可证发行。

### 镜像仓库

- GitHub：https://github.com/linhut/gongwen-skill
- AtomGit：https://atomgit.com/gcw_5fI2soiE/gongwen-skill
