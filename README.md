<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# 中文公文全流程工具 · gongwen-skill

<p align="center">
  <img src="./logo/2026-08-19_11-17-43.png" alt="gongwen-skill 中文公文全流程处理" width="760">
</p>

> 中文公文全流程处理工具——基于 **GB/T 9704《党政机关公文格式》** 国家标准，支持 **格式检查与修复、内容优化（Word 原生修订+批注/差异对比版）、模板生成、Markdown 转公文、版头版记页码注入、事实核验、风格增强** 等完整能力。原生支持 **DeepSeek Harness (DSH)** 技能系统，打包为可被 AI Agent 直接调用的 Skill，完全自包含，克隆即用。

[![CI](https://img.shields.io/badge/CI-Passing-brightgreen)](https://github.com/linhut/gongwen-skill/actions)
[![PyPI](https://img.shields.io/badge/PyPI-v1.12.68-blue)](https://pypi.org/project/gongwen-skill/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![GB/T 9704](https://img.shields.io/badge/standard-GB%2FT%209704-red.svg)
![DSH](https://img.shields.io/badge/DSH-Compatible-brightgreen)
![Downloads](https://img.shields.io/badge/Downloads-0-blue)

本 Skill 源自开源桌面项目 [AI 公文智能优化助手](https://github.com/linhut/document-ai-assistant)，将其核心格式引擎抽取、剥离桌面端/数据库依赖后独立发行，支持公文的**模板建立、解析、规则检查、自动修复、内容优化、Markdown 转公文**全流程能力。同时原生集成 **DeepSeek Harness (DSH)** 技能系统，支持 DSH Agent 自动发现与加载。

---

## ✨ 能力一览

| 能力 | 命令 | 说明 |
|------|------|------|
| 📋 列类型 | `list-types` | 列出 24 种支持的公文类型（含新闻稿/讲话稿主持词） |
| 🏗️ 模板生成 | `template` | 按类型生成 GB/T 9704 标准空白模板 |
| 🔍 解析 | `parse` | `.docx` → 结构化 DocumentModel |
| ✅ 格式检查 | `check` | 按国标检查，分级 P0/P1/P2（只读） |
| 🔧 格式修复 | `optimize` | 自动修复字体/字号/行距/页边距，输出合规文档 |
| ✍️ **内容优化** | **`optimize-content`** | 内容润色：默认 **Word 原生修订+批注**（审阅面板逐条接受/拒绝），可选行内差异对比版 |
| 📝 草稿转公文 | `md2docx` | Markdown 文本直接转为格式化 `.docx`（支持 Front Matter） |
| 📄 模型生成 | `generate` | 从 JSON 模型生成 `.docx` |
| 🔴 版头 | `header` | 注入发文机关标志 + 发文字号 + 签发人 + 红色反线 |
| 📑 版记 | `footer` | 注入抄送机关 + 印发机关 + 印发日期 + 分隔线 |
| 🔢 页码 | `pagenum` | 注入 Word PAGE 域动态页码（宋体 4 号，默认单右双左适配双面打印） |
| 🖊️ 首句加粗 | `bold-first` | 正文段落首句自动加粗（公文规范） |
| 🧰 一键修复 | `fix-common` | 路径 D 一键修复常见格式：段落类型修正 + 编号拆分 + 首句加粗 + 加粗范围修复 |
| 📋 桌签生成 | `table-signs` | 批量生成 A5 横版会议桌签 |
| 🔍 审稿生成 | `review` | 按五角色审稿机制生成审稿意见 |
| 🧩 完整审校 | `full-review` | 修订+批注联合命令（句子级差异修订 + 分类批注） |
| 🎨 样式学习 | `style-learn` / `style-list` | 上传标准文档学习 Run/段落/页面三级样式（字体/字号/字间距/行距/缩进/页边距），生成命名模板持久化，后续用 `optimize -t 模板名` 套用 |
| 🔄 版本自检 | `check-update` | 多渠道版本自检（GitHub/GitCode/AtomGit 三仓库比对取最新） |
| 🕵️ 文档审计 | `audit` | 检查删除线/加粗/AI 声明等痕迹 |
| 🤝 会话交接 | `handoff` | 跨会话上下文传递（`--list` / `--latest` / Agent 长任务收尾必写） |
| ⚙️ 规则管理 | `rule-export/import/list` | YAML 规则三层定制（官方/单位/用户） |

## 使用示例

> 在 AI 对话中调用 gongwen-skill，输入自然语言指令，自动生成符合 GB/T 9704 国标格式的正式公文。

### 🤖 调用环境的适配指引（AI Agent 必读）

本工具针对不同能力层级的 AI 调用环境，提供不同的使用方式。**AI 读取本文件后，请先判断自身环境属于哪一类，再按对应指引执行：**

| 环境类型 | 典型平台 | 能力 | 使用方式 |
|:---------|:---------|:-----|:---------|
| **① 可执行代码的 Agent** | WorkBuddy、CloudCode、Claude Code、AtomCode、DeepSeek Harness | 可运行命令、读写本地文件 | 直接执行 `python -m gongwen <命令>`，见下方「快速开始」与「通过 Agent 调用」 |
| **② 纯对话 LLM（无代码执行能力）** | 豆包、Kimi、ChatGPT 网页版等 | 只能阅读文本、给出建议，**不能运行命令或读写文件** | 引导用户手动执行，见下方「纯对话 LLM 使用指引」 |

#### 纯对话 LLM 使用指引（环境 ②）

> **如果你是无法执行代码的纯对话 AI**（如豆包、Kimi、ChatGPT 网页版等），请按以下方式协助用户：

1. **告知工具性质**：向用户说明「这是一个本地运行的 Python 命令行工具，需要在你自己的电脑上安装后使用」，并说明它能做什么（格式检查、自动修复、内容优化、模板生成等 25 项能力）。
2. **引导安装**：请用户在自己的电脑上执行以下步骤：
   ```bash
   # 步骤 1：克隆仓库
   git clone https://github.com/linhut/gongwen-skill.git
   cd gongwen-skill

   # 步骤 2：安装依赖（需要 Python 3.10+）
   pip install -r requirements.txt
   # 或直接安装 PyPI 包：
   # pip install gongwen-skill
   ```
3. **按需给出具体命令**：根据用户的实际需求，给出对应的命令让用户自行执行：

   | 用户需求 | 建议用户执行 |
   |:---------|:-------------|
   | 检查公文格式 | `python -m gongwen check 公文.docx -t notice --json` |
   | 自动修复格式 | `python -m gongwen optimize 公文.docx -o 成品.docx -t notice --apply` |
   | 生成标准模板 | `python -m gongwen template notice -o 通知模板.docx` |
   | Markdown 转公文 | `python -m gongwen md2docx 草稿.md -o 正式公文.docx -t report` |
   | 内容润色（修订+批注） | `python -m gongwen optimize-content 原文.docx --changes 修订内容.json --apply --mode tracked` |
   | 注入版头/版记/页码 | `python -m gongwen header/footer/pagenum 公文.docx ...` |
   | 从标准文档学样式做模板 | `python -m gongwen style-learn 标准公文.docx -n 模板名`，之后用 `optimize -t 模板名` 套用 |
   | 安装标准字体 | `python -m gongwen font install` |

4. **解释输出**：用户执行后，把命令输出结果（问题清单、修复报告、生成文件等）发给你时，你能继续帮助解读、判断下一步操作。
5. **注意事项**：你**不能**代替用户执行任何命令，也**不能**读取用户本地的文件内容——所有文件操作都必须由用户在你的指引下完成。

#### 文字性资源库（纯对话 LLM 可读的知识源）

项目内置以下文字性资源，纯对话 AI 可以直接读取，用作**公文写作指导的知识库**：

| 资源 | 位置 | 内容 | 行数 |
|:-----|:-----|:------|:----:|
| **公文语言风格提示词库** | `prompts/style-prompts.md` | 6 套风格（庄重严谨/平实简洁/宏观概括/请示商洽/法规条文/讲话稿），每套含用词规范、句式和语气指导 | 205 |
| **使用指引与决策速查** | `prompts/usage-prompts.md` | 最小可用指引、决策速查、每种公文类型的用法模板、常见问题解答 | 381 |
| **公文类型规则库** | `rules/official/*.yaml`（25 个文件） | 每种公文类型的格式规范 + 内容层定义（如"请示应以'妥否，请批示'结尾""通知应以'特此通知'结尾"） | 25 文件 |
| **通用格式标准** | `rules/official/_common.yaml` | GB/T 9704 国标全文参数：字体/字号/行距/页边距等 | 836 |
| **技能完整指令** | `SKILL.md` | 路径路由、执行标准、质量评审、禁令清单、审稿机制 | 2854 |

**使用方式**：纯对话 AI 在回答用户关于公文写作的问题时，可直接引用上述资源中的内容，例如：
- 用户问"通知怎么写" → 引用 `rules/official/notice.yaml` 的结语规范和 `style-prompts.md` 的庄重严谨风格
- 用户问"请示和报告的区别" → 引用 `request.yaml` 和 `report.yaml` 的规则说明
- 用户问"公文用什么字体" → 引用 `_common.yaml` 中的 GB/T 9704 标准
- 用户需要润色文字 → 引用 `style-prompts.md` 中对应的风格提示词

> 这些资源均以纯文本格式存储，纯对话 AI 可直接读取解读，无需执行任何代码即可提供专业的公文写作指导。

## 🚀 快速开始

```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt

# 生成一份标准通知模板
python -m gongwen template notice -o 通知模板.docx

# 检查公文格式（只读）
python -m gongwen check 公文.docx -t notice --json

# 自动修复格式（--apply 确认执行，默认预览）
python -m gongwen optimize 公文.docx -o 成品.docx -t notice --apply

# 一步到位：检查 + 修复 + 版头/版记/页码全注入（--layout 指向 JSON 配置）
python -m gongwen optimize 公文.docx -o 成品.docx --layout 版式.json

# Markdown 草稿 → 正式公文（支持管道输入和 Front Matter 元数据）
python -m gongwen md2docx 草稿.md -o 正式公文.docx -t report --signer "XX单位" --date "2026年8月1日"

# 内容优化（默认 tracked 模式：Word 原生修订+批注，审阅面板逐条接受/拒绝）
python -m gongwen optimize-content 原文.docx --changes 修订内容.json --apply --mode tracked -t news

# 注入版头（发文机关标志 + 发文字号 + 签发人 + 红色反线）
python -m gongwen header 公文.docx -o 红头公文.docx --org-name "XX单位" --doc-number "〔2026〕1号"

# 注入版记（抄送 + 印发机关 + 印发日期）
python -m gongwen footer 红头公文.docx --cc "各单位" --printer "XX办公室" --print-date "2026年8月1日"

# 注入页码（Word PAGE 域动态页码）
python -m gongwen pagenum 红头公文.docx --alignment right

# 多渠道版本自检
python -m gongwen check-update

# 安装公文标准字体（方正小标宋简体/仿宋_GB2312/楷体_GB2312）
python -m gongwen font install          # 安装字体到系统
python -m gongwen font check            # 检查字体安装状态
python -m gongwen font list             # 列出字体清单

# 从标准文档学习排版样式，生成自定义模板（后续用 optimize -t 模板名 套用）
python -m gongwen style-learn 标准公文.docx -n 模板名
python -m gongwen style-list            # 列出已学习的模板
```

### 🔤 字体管理

公文标准字体是 GB/T 9704 排版的关键。项目内置 3 个标准字体文件（`assets/fonts/`），支持自动安装：

| 字体 | 用途 | TTF 大小 |
|:-----|:-----|:---------|
| 方正小标宋简体 | 公文大标题 | 3.7 MB |
| 仿宋_GB2312 | 正文 | 3.9 MB |
| 楷体_GB2312 | 二级标题 | 4.0 MB |

**安装方式**：
- **git clone 用户**：字体文件在 `assets/fonts/` 中，直接安装
- **pip install 用户**：字体不打包到 PyPI（体积过大），`font install` 会自动从 [GitHub 仓库](https://github.com/linhut/document-ai-assistant/tree/master/TTF) 下载到 `~/.gongwen-skill/fonts/` 缓存后安装

```bash
python -m gongwen font install    # 一键安装 3 个标准字体
python -m gongwen font check      # 检查安装状态
```

## ✍️ 内容优化（路径 B）核心能力

### 三种输出模式（`--mode`）

| 模式 | 说明 |
|------|------|
| `tracked`（默认） | **Word 原生修订标记（w:del/w:ins）+ 批注（comments.xml）**，审阅面板逐条接受/拒绝 |
| `comment-mode` | 仅 Word 原生批注（可审阅→接受/拒绝） |
| `inline` | 行内差异对比版（原文灰色删除线 + 优化后红色高亮 + 修改说明） |

### 8 色审阅角色方案

批注/修订按语义类别自动分配角色与颜色，Word 中可按审阅者筛选：

| 角色 | 类型 | 颜色 | 色值 | 语义类别 |
|------|------|------|------|---------|
| 格式审校 | 批注 | 蓝 | `2E86C1` | 格式优化 |
| 用语审校 | 批注 | 绿 | `27AE60` | 用语优化 |
| 逻辑审校 | 批注 | 红 | `E74C3C` | 逻辑优化 |
| 法规审校 | 批注 | 紫罗兰 | `9B59B6` | 法规合规 |
| 综合审校 | 批注 | 橙 | `F39C12` | 内容优化 |
| 事实核验 | 批注 | 青 | `00BCD4` | 事实核验 |
| GongWen-Skill修订 | 修订 | 玫红 | `E91E63` | 内容/事实核验修订 |
| 风格审校 | 批注+修订 | 深紫 | `6C3483` | 风格优化（自动应用） |

### 事实核验

- **默认执行**（不依赖 `--background`）：实体提取（人名/职务/机构全称）→ 互联网交叉核验 → 生成"存疑/已确认/未经核验"批注
- **实体属性核验**：识别人名+职务配对（如"省民宗委党组成员、副主任XXX"），能发现职务写反等严重事实错误
- **LLM+规则混合提取**：配置 `GONGWEN_LLM_API` 后 LLM 内容理解提取（主通道）+ 规则提取（兜底）
- **背景资料增强**：`--background` 传入 docx/pdf/md/txt/URL 构建基准，已确认实体自动过滤

### Agent 协作机制（`--output-tasks` / `--input-tasks`）

Skill 定位为**工具层**——确定性工作自己做，需 LLM/搜索判断的环节交由 Agent：

```bash
# 1. Skill 输出待处理任务（待核验实体 + 风格增强请求），同时生成基础版文档
python -m gongwen optimize-content 新闻稿.docx --changes changes.json \
  --output-tasks tasks.json --apply --mode tracked -t news

# 2. Agent 用自身 LLM+搜索能力处理 tasks.json（核验人事信息、生成风格建议），输出 tasks_result.json

# 3. Skill 读入回填结果，合并到 changes 后执行（去重/已确认过滤/独立修订作者）
python -m gongwen optimize-content 新闻稿.docx --changes changes.json \
  --input-tasks tasks_result.json --apply --mode tracked -t news
```

### 风格增强（v2，数据驱动）

- 输出 5 套上下文信号：**段落角色标注**（复用 structure 规则关键词）、**文档类型规则摘要**（structure 含 modes/focus_checks/title_patterns）、**结构/焦点检查结果**、**数据驱动风格评分**（completeness/compliance/change_density/style_deviation_hint）、**完整已有变更摘要**（不再截断）
- 风格建议 **auto-accept 自动合入**已有变更（difflib 映射），不生成独立修订；批注标注【已自动应用】
- 跨 20+ 文档类型自动适配（rules YAML 数据驱动，不硬编码）

### 结构/焦点自动检查

- **结构完整性检查**（`structure_checker.py`）：按 rules YAML 的 structure 定义检查必要段落/要素，多候选评分定位段落
- **focus_checks 自动检查**（`focus_checker.py`）：逻辑闭环（听取→指出→强调→要求）/时间一致性/事实表述客观克制/稿源编辑信息/简称定义规范
- 检查结果自动生成按角色区分的批注

### 命令行参数速查

```
--mode tracked|inline        输出模式（默认 tracked）
--reviewers 3|5|6            审稿角色数（默认 6 完整版）
--changes <json>             变更列表（paragraph_index/original_text/optimized_text/reason/category）
--background <paths>         背景资料（事实核验基准）
--auto-generate              无 changes.json 时基于内置规则自动生成优化建议（需 LLM）
--output-tasks <json>        输出待 Agent 处理任务
--input-tasks <json>         读入 Agent 回填结果
--style <名称>               语言风格（--style 显式 > changes.style > doc_type 映射 > 默认庄重严谨）
--no-style-enhance           禁用风格增强（默认开启）
-t/--doc-type <类型>         显式指定公文类型（默认自动检测）
--show-rules                 输出文档类型内容层规则摘要
--show-confirmed             已确认实体也生成批注
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
| **页码** | 宋体（4号半角） | 四号（14pt） | 单页右/双页左（双面打印） |
| **页边距** | — | — | 上3.7/下3.5/左2.8/右2.6 cm |

### 讲话稿/主持词（speech 朗读件）

标题方正小标宋简体 24pt 居中、主持人信息/日期楷体_GB2312 18pt 居中、正文仿宋_GB2312 18pt 加粗、正文行距 33pt exact、标题行距 35pt；跳过版头/版记/发文字号/密级检查。

## 📚 支持的 24 种公文类型

通知 · 请示 · 报告 · 函 · 会议纪要 · 纪要 · 决定 · 通告 · 公告 · 命令 · 通报 · 议案 · 批复 · 指示 · 制度 · 公报 · 意见 · 总结 · 方案/计划 · 桌签 · 技术方案 · 决议 · **新闻稿/简报** · **讲话稿/主持词**

> 每种类型对应 `rules/official/*.yaml`，含格式规则 + 内容层定义（structure/focus_checks/title 等），驱动 check/optimize/optimize-content 全链路。

## ⚙️ 规则化与二次定制

规则以 YAML 定义，三层优先级 **official < custom < user**：

- 官方规则：仓库内 `rules/official/*.yaml`
- 用户覆盖：`~/.gongwen-skill/user_rules/*.yaml`（同名字段覆盖官方）

```bash
python -m gongwen rule-export notice -o notice_rules.yaml
python -m gongwen rule-import my_company -f 公司规范.yaml
python -m gongwen rule-list notice
```

## ⚠️ 使用红线

- **不伪造、冒用真实机关正式发文** — 生成物仅为草稿，正式发文须走审核流程
- **人事信息准确性铁律** — 领导姓名/机构全称/职务等仅有"确定"或"`[XXX]` 占位"两种状态，严禁推理/猜测填造
- **不编造政策依据、数据、结论** — 缺失信息用 `XXX` 占位
- **涉密材料先脱敏再处理**
- **字体版权** — 方正小标宋简体等字体可能受版权约束，缺少时 Word 会回退

## 🤖 作为 AI Agent Skill 使用

将本仓库放入 Agent 的 skills 目录，Agent 读取 `SKILL.md` 后自动调用命令。支持三条路径：

- **路径 A**：格式修复（不改文字，只修排版）
- **路径 B**：内容优化（润色文字，Word 原生修订+批注 / 差异对比版）
- **路径 C**：生成公文（从零创建，四步流水线）

**平台适配**：`SKILL.md` 采用通用 frontmatter（`name/description/whenToUse/user-invocable`），兼容 **WorkBuddy、CloudCode、Claude Code、AtomCode、DeepSeek Harness** 等以 `SKILL.md` 为技能清单的平台；纯对话 LLM（无代码执行能力）请参见上方「纯对话 LLM 使用指引」。

### 🔄 版本追新（Agent 加载 skill 后必须执行）

Agent 加载 skill 后**必须执行版本追新自检**，确保使用最新版本：

1. **多渠道远程自检**（首选）：`python -m gongwen check-update`——自动查询 GitHub/GitCode/AtomGit 三仓库最新 tag，取最高版本比对本地；任一渠道可达即不遗漏，全部不可达时明确告知"版本自检跳过"
2. **本地 git tag 对比**（补充）：对 skill 安装目录执行 `git -C "<skill安装目录>" describe --tags --abbrev=0`；若安装目录不在 git 管理下，应告知用户"无法执行版本对比，建议手动检查 GitHub 更新"
3. **落后则警告**：发现本地版本落后于最新 tag 时，**必须在执行前警告用户**并提示更新（`cd <gongwen-skill目录> && git pull && git fetch --tags`），不得静默使用旧版本

> 严禁只用本地 `git describe` 判断版本——它只读本地可达 tag，未 fetch 时会误判本地即最新。



## 🚀 DeepSeek Harness (DSH) 集成

本 Skill 同时支持 [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness) 的**两种集成方式**——文件系统 **Skill**（轻量、跟随项目）与 **Cordis 插件 bundle**（包入 npm 通道、让 Web UI Toolkit 可调用），按你的部署需求选择。

DSH 采用 **Cordis 模块化微内核架构**：技能体系基于本地文件系统（无中心化技能市场），插件体系基于 npm 包 + `~/.dsh/profiles/<preset>/package.json` 中的 `dsh.profile.bundles` 声明挂载。

### 方式零：仅作为 Python CLI 使用（最轻量）

```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt   # 或 pip install gongwen-skill（已上 PyPI）
python -m gongwen --version       # 检验：gongwen-skill v1.12.68
```

### 方式一：作为 DSH Skill 注册（基于本地文件系统）

DSH Agent 启动时自动扫描下表目录中的技能（优先级从高到低）：

| 优先级 | 目录 | 说明 |
|:------:|:-----|:------|
| 100 | `{project}/.dsh/skills/` | 项目级 DSH 技能目录 |
| 200 | `{project}/.agents/skills/` | 项目级 Agent 技能目录 |
| 400 | `~/.dsh/skills/` | 用户级 DSH 技能目录 |
| 500 | `~/.agents/skills/` | 用户级 Agent 技能目录 |

**安装方式**（二选一）：

```bash
# A. 项目级：克隆到工程目录（跟随项目，推荐）
git clone https://github.com/linhut/gongwen-skill.git ./third_party/gongwen-skill
ln -s ./third_party/gongwen-skill/.dsh/skills/gongwen-skill  ./.dsh/skills/gongwen-skill

# B. 用户级：全局可用，所有 DSH 会话都能发现
git clone https://github.com/linhut/gongwen-skill.git ~/skills/gongwen-skill
mkdir -p ~/.dsh/skills/
ln -s ~/skills/gongwen-skill/.dsh/skills/gongwen-skill  ~/.dsh/skills/gongwen-skill
```

> 两种方式都会让 DSH Agent 在启动时自动发现并加载本技能；本仓库自带 `.dsh/skills/gongwen-skill/` 双格式（目录技能 + 单文件技能）兼容。

### 方式二：作为 DSH Cordis 插件安装（注册到 Web Profile）

把本仓库当作 npm 包安装到 DSH Web Profile，让 DSH 的 Web UI 通过 `gongwen-skill` 调用桥接器执行 Python CLI。

```bash
# 1️⃣ 用 DSH 官方 CLI 一键挂载（推荐：自动改 package.json + 重建 bundle）
dsh plugin --profile web add -w gongwen-skill
# -w = workspace，按 preset 自动写入 ~/.dsh/profiles/web/package.json
```

```bash
# 2️⃣ 或在 Web Profile 目录下手动 npm/pnpm 安装
cd ~/.dsh/profiles/web
npm i gongwen-skill -w
# 或：
pnpm add -w gongwen-skill
```

安装后请确认 `~/.dsh/profiles/web/package.json` 中的 `dsh.profile.bundles` 数组已包含 `gongwen-skill`：

```jsonc
{
  "name": "dsh-profile-web",
  "private": true,
  "dependencies": {
    "@deepseek-ai/dsh-base": "...",
    "@deepseek-ai/dsh-web-app": "...",
    "gongwen-skill": "^1.12.60"
  },
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-web-app",
        "gongwen-skill"
      ]
    }
  }
}
```

> **注意**：若 `add` 启动报错提示子包重复声明，请检查 `dsh.profile.bundles` 数组中**仅包含根包 `gongwen-skill`**，避免同时列入 `engine` 或 `gongwen` 等子目录。

### 方式三：本地源码链接（用于插件开发）

如果你在本地开发 gongwen-skill 插件，可以用 link 方式让 DSH 直接加载仓库源码：

```bash
# 把本地仓库以 link 方式挂到 DSH Web Profile
dsh plugin --profile web add -w "link:/path/to/gongwen-skill"

# 同样：检查 ~/.dsh/profiles/web/package.json
#  - dependencies 出现 "gongwen-skill": "link:/path/to/gongwen-skill"
#  - dsh.profile.bundles 包含 "gongwen-skill"
```

### 🚀 启动 DSH Web 服务

```bash
# 让 gongwen-skill 桥接可用：先在仓库根安装 Python 依赖
cd /path/to/gongwen-skill
pip install -r requirements.txt   # 或 pip install gongwen-skill

# 启 DSH
dsh --profile web
# 或：dsh web
```

浏览器访问 [http://127.0.0.1:3080/](http://127.0.0.1:3080/)，在新建会话时即可让 DSH Agent 自动加载 gongwen-skill 调用 Web UI 工具流。

### DSH 兼容性自查

| 检查项 | 状态 |
|:-------|:----:|
| Skill 体系：`SKILL.md` YAML frontmatter (`name + description + whenToUse`) | ✅ |
| 技能名称规范 (`gongwen-skill`，长度 ≤ 30 字符) | ✅ |
| 目录技能格式 (`.dsh/skills/gongwen-skill/SKILL.md`) | ✅ |
| 单文件技能格式 (`.dsh/skills/gongwen-skill.md`) | ✅ 双格式兼容 |
| Cordis 插件包：`package.json` + `dsh/` + `cordis.patch.yml` | ✅ |
| CLI 独立可执行（`python -m gongwen <命令>`） | ✅ |
| PyPI 上架（`pip install gongwen-skill`） | ✅ |
| 零外部运行时依赖（仅 python-docx/pydantic/pyyaml） | ✅ |
| DSH 配置化排版参数（页边距/行距/字体/默认模板版本） | ✅ v1.12.61+ |

### DSH 插件配置化（v1.12.61+）

DSH 插件支持通过配置文件管理排版参数，Agent 调用时自动注入，纯 CLI 用户不受影响。

**配置文件**：`~/.gongwen-skill/dsh-config.json`

**初始化配置**（从默认模板创建）：

```bash
# 通过 DSH 插件调用
node -e "import('./dsh/index.js').then(async m => { console.log(await m.call({}, {command: 'config', action: 'init'})) })"

# 或直接复制默认模板
cp etc/dsh-config-defaults.json ~/.gongwen-skill/dsh-config.json
```

**配置项说明**：

| 配置路径 | 说明 | 默认值 |
|:---------|:-----|:-------|
| `default_doc_type` | 默认公文类型 | `notice` |
| `page_setup.margins.top/bottom` | 上下页边距 | `2.8cm` |
| `page_setup.margins.left/right` | 左右页边距 | `2.7cm` |
| `page_setup.header_distance` | 页眉距边界 | `1.5cm` |
| `page_setup.footer_distance` | 页脚距边界 | `2.3cm` |
| `body.font` | 正文字体 | `仿宋_GB2312` |
| `body.size` | 正文字号 | `16pt` |
| `body.line_spacing` | 正文行距 | `33pt` |
| `body.first_line_indent` | 首行缩进 | `2em` |
| `doc_title.font` | 大标题字体 | `方正小标宋简体` |
| `doc_title.size` | 大标题字号 | `22pt` |
| `heading_1.font` | 一级标题字体 | `黑体` |
| `heading_2.font` | 二级标题字体 | `楷体_GB2312` |

**修改配置**（DSH 插件调用）：

```javascript
// 设置单个配置项
await call({}, {command: 'config', action: 'set', key: 'page_setup.margins.top', value: '3.0cm'})

// 读取配置项
await call({}, {command: 'config', action: 'get', key: 'body.line_spacing'})

// 查看完整配置
await call({}, {command: 'config', action: 'show'})

// 重置为默认值
await call({}, {command: 'config', action: 'reset'})
```

**纯 CLI 使用 `--config-overrides`**：

```bash
# 临时覆盖行距为 28 磅
python -m gongwen template notice -o 通知.docx \
  --config-overrides '{"body":{"line_spacing":"28pt"}}'

# 临时覆盖页边距
python -m gongwen optimize input.docx -o output.docx --apply \
  --config-overrides '{"page_setup":{"margins":{"top":"3.0cm"}}}'
```

**设计说明**：

- **分层架构**：Python CLI（纯工具层）只接受 `--config-overrides` 通用参数；DSH 插件（配置管理者）读写配置文件并自动注入
- **优先级**：official YAML < custom YAML < user YAML < DSH config overrides < 命令行 `--config-overrides`
- **热更新**：每次调用读取配置文件，修改后立即生效，无需重启
- **纯 CLI 不受影响**：不使用 DSH 插件时不会读取 `dsh-config.json`

### 适用场景对照

| 你的场景 | 推荐方式 |
|:---|:---|
| 只想在终端用 gongwen-skill 命令 | 方式零 |
| 想让 DSH Agent 调用本技能，无需 Web UI | 方式一（Skill 文件系统） |
| 想让 DSH Web UI 工具面板直接调用 | 方式二（npm 插件 bundle） |
| 二开插件本身，本地反复编辑 | 方式三（link 模式） |

## 🤖 通过 Agent 调用

本 Skill 可直接被 AI Agent（如 WorkBuddy、CloudCode、Claude Code、AtomCode 等）加载并调用，无需手动操作。

### 安装方式

**方式一：克隆到 Skills 目录（推荐）**
```bash
# WorkBuddy / CloudCode
git clone https://github.com/linhut/gongwen-skill.git ~/.workbuddy/skills/gongwen-skill/

# AtomCode
git clone https://github.com/linhut/gongwen-skill.git ~/.atomcode/skills/gongwen-skill/

# Claude Code
git clone https://github.com/linhut/gongwen-skill.git ~/.claude/skills/gongwen-skill/

# 其他 Agent — 将仓库克隆到对应的 skills 目录即可
```

**方式二：任何工作目录下直接使用**
```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt
# 之后 Agent 可直接调用 python -m gongwen <命令>
```

### 对话中使用示例

| 用户说 | Agent 行为 | 路径 |
|--------|-----------|------|
| "帮我检查这份通知的格式" | 自动执行 `check` 并展示问题清单 | A |
| "帮我排版这份红头文件" | 自动执行 `optimize --apply` 修复格式 | A |
| "润色一下这份报告的措辞" | 生成 `changes.json`，执行 `optimize-content`（tracked 修订+批注） | B |
| "帮我写一份关于XX的通知" | 追问细节后走草稿→`md2docx`→`optimize`→`check` | C |
| "核验一下这份新闻稿里的人名职务" | 执行 `optimize-content --output-tasks` → Agent 核验 → `--input-tasks` 回填 | B+协作 |
| "给这份会议通知生成桌签" | 询问名单后执行 `table-signs` | 独立 |
| "看看这份文档有没有问题" | 执行 `audit` 检查删除线/加粗/AI声明 | 独立 |

### Agent 调用示例（对话式）

```
用户：帮我优化这份会议通知的第二章节措辞

Agent：📋 合规自检报告
Skill 版本: v1.12.68（多渠道自检已确认最新）
路径判定: B（内容优化）
依据: 用户指定了已有文档，且要求"优化措辞"
命令调用: 1. python -m gongwen optimize-content 会议通知.docx --changes changes.json --apply --paragraphs "5-8"
是否绕过: 否
交付物: 会议通知+庄重严谨+2026-08-01+v1.docx（Word 原生修订+批注版）
质量验证: check 通过
```

## 🔧 LLM 集成（可选）

Skill 定位为**工具层**，默认不依赖 LLM（确定性工作全自包含）。以下可选能力需配置环境变量（未配置自动降级，不影响主流程）：

| 环境变量 | 能力 |
|---------|------|
| `GONGWEN_LLM_API` / `_API_KEY` / `_MODEL` | LLM 实体提取、自动生成优化建议、风格增强（skill 内置调用） |
| `GONGWEN_OPTIMIZE_LLM_API`（优先于 LLM_API） | optimize-content 专用配置 |
| `GONGWEN_WEB_VERIFY=1` | 事实核验互联网交叉核验（百度→必应多引擎） |

> **推荐模式**：Agent 环境中通过 `--output-tasks` / `--input-tasks` 协作，用 Agent 自身 LLM+搜索能力处理，无需配置上述环境变量。

## 📦 依赖

仅 3 个纯 Python 包：`python-docx`、`pydantic`、`pyyaml`。无数据库、无 Web 框架、无桌面端。

## 💬 社区交流

欢迎加入社区，参与讨论、交流使用问题、插件开发和项目进展：

| 平台 | 说明 |
|:-----|:------|
| 💬 **Discord** | [加入 Discord 服务器](https://discord.gg/4qT7TPdft) — 实时交流、问题讨论、版本更新通知 |
| 💚 **QQ 群** | 扫码加入 QQ 群，与中文用户交流使用经验 |

---

## 📄 许可证与出处

MIT License · **(c) 2026 Jose AI** · https://www.linhut.cn

本 Skill 源自开源项目 [AI 公文智能优化助手](https://github.com/linhut/document-ai-assistant)。格式引擎与规则 YAML 版权归原作者所有，依 MIT 许可证发行。

### 镜像仓库

- GitHub：https://github.com/linhut/gongwen-skill
- GitCode：https://gitcode.com/linhut/gongwen-skill
- AtomGit：https://atomgit.com/linhut/gongwen-skill

