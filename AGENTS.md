---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 594788b2f473f3679080da07b1915493_3948b672adda11f18039525400461939
    ReservedCode1: QQXN7DfjJFomCh/Kvmo5ok38vndecdGMG4kKZFsPf0YzBRkXkoJoUGOxHtU8m2/aike/LgYiydcg6cHyT1NuWO3+Bq2M8XblOH3SdsrfC75KXxL6fOZiMjsMLk7jccu0KbisbuD4uLLjFUcFV/o2lh90oFvPqDf1lK+11KDbXcYRNupGF1SyCJDwukM=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 594788b2f473f3679080da07b1915493_3948b672adda11f18039525400461939
    ReservedCode2: QQXN7DfjJFomCh/Kvmo5ok38vndecdGMG4kKZFsPf0YzBRkXkoJoUGOxHtU8m2/aike/LgYiydcg6cHyT1NuWO3+Bq2M8XblOH3SdsrfC75KXxL6fOZiMjsMLk7jccu0KbisbuD4uLLjFUcFV/o2lh90oFvPqDf1lK+11KDbXcYRNupGF1SyCJDwukM=
---



<!--
  (c) 2026 Jose AI (https://www.linhut.cn)
  https://github.com/linhut/gongwen-skill
  Licensed under the MIT License. See the LICENSE file for details.
-->

# 公文全流程处理专家（gongwen-skill）

> 面向中文公文（`.docx`）的 **GB/T 9704《党政机关公文格式》** 全流程处理工具链，打包为可被 AI Agent 直接调用的 Skill。
>
> - **展示名（对外名称）**：公文全流程处理专家
> - **标识名（机器标识，请勿改动）**：包名 `gongwen-skill`、命令名 `gongwen`、Skill 目录名 `gongwen-skill`
> - **仓库**：https://github.com/linhut/gongwen-skill ｜ 许可：MIT

---

## 1. 快速开始

```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt        # 需要 Python 3.10+
python -m gongwen list-types           # 验证安装（应列出 25 种公文类型）
```

也可直接安装 PyPI 包：`pip install gongwen-skill`。

---

## 2. Agent 调用约定

1. **入口唯一**：所有业务能力统一通过 CLI `python -m gongwen <命令>` 调用，不要自行拼装底层脚本。
2. **执行前声明**（硬门控，不可跳过）：先声明「当前调用环境 / 用户需求判定路径（A 格式修复、B 内容优化、C 生成公文、D 一键修复、E 其他）/ 判定依据」。
3. **写操作显式授权**：修复与生成类命令默认只预览，需 `--apply` 才落盘；覆盖已有文件前须获得用户确认。
4. **只读优先**：诊断类命令（`check` / `parse` / `audit` / `rule-list` / `doctor`）不修改用户文档，可放心执行。
5. **规则与提示词**：格式规则位于 `rules/`（官方 / 单位 / 用户三层 YAML），提示词位于 `prompts/`，可按需读取后再判断。

---

## 3. 命令速查（29 项）

> 本表仅为速查摘要，**完整操作指南以 `SKILL.md` 为准**（命令参数、示例、规则详见 skills 主文件）；新增或调整命令时同步更新两处。

| 命令 | 说明 |
|:-----|:-----|
| `list-types` | 列出 25 种支持的公文类型 |
| `template` | 按类型生成 GB/T 9704 标准空白模板 |
| `parse` | `.docx` → 结构化 DocumentModel（JSON） |
| `check` | 按国标检查格式，分级 P0/P1/P2（只读） |
| `optimize` | 检查 + 修复 + 生成（默认预览，`--apply` 执行） |
| `generate` | 从 DocumentModel JSON 生成 `.docx` |
| `header` | 注入版头：发文机关标志 + 发文字号 + 签发人 + 红色反线 |
| `footer` | 注入版记：抄送 + 印发机关 + 印发日期 + 分隔线 |
| `pagenum` | 注入 Word PAGE 域动态页码 |
| `md2docx` | Markdown 文本转格式化公文 `.docx` |
| `draft` | Markdown 草稿 → 国标成品 + 验证（四步合一） |
| `optimize-content` | 内容优化：Word 原生修订+批注，或行内差异对比版 |
| `bold-first` | 正文段落首句加粗（符合公文规范） |
| `fix-common` | 一键修复常见格式问题（段落类型 / 编号拆分 / 首句加粗 / 加粗范围） |
| `handoff` | 查看或写入会话交接文档（跨会话上下文传递） |
| `rule-export` / `rule-list` / `rule-import` | 三层规则导出 / 列出 / 导入 |
| `table-signs` | 从名单批量生成会议桌签 |
| `full-review` | 完整审校：格式修复 → 内容优化 → 批注输出 |
| `style-learn` / `style-list` | 从标准文档学习排版样式并注册为命名模板 |
| `check-update` | 版本自检（PyPI 权威判定 + GitHub 备用 + 国内镜像提示） |
| `audit` | 审计文档处理链：删除线 / 加粗 / AI 声明等合规性 |
| `review` | 生成公文审稿流转单（五角色 / 三角色模板） |
| `wizard` | 向导式交互：A/B/C/D/E 路径引导 + 一键执行 |
| `font` | 公文标准字体管理：安装 / 检查 / 列出内置字体 |
| `doctor` / `repair` | 全面自我诊断与常见问题修复 |

---

## 4. 目录结构

```
gongwen-skill/
├── SKILL.md                 # Skill 主文件（frontmatter + 全量操作指南）
├── AGENTS.md                # 本文件（面向 Codex 等指令型 Agent）
├── .claude-plugin/          # Claude Code 插件清单（plugin.json / marketplace.json）
├── dsh/                     # DeepSeek Harness 插件（index.js / client.js）
├── cordis.patch.yml         # DSH 插件注册补丁
├── presets/                 # DSH Agent 预设「公文全流程处理专家」
├── engine/                  # 格式引擎（解析 / 检查 / 修复 / 生成）
├── gongwen/                 # CLI（`python -m gongwen`）
├── rules/                   # 三层格式规则（官方 / 单位 / 用户）
└── prompts/                 # 各路径提示词
```

---

## 5. 平台适配

| 平台 | 接入方式 | 对外名称来源 |
|:-----|:---------|:-------------|
| Claude Code | `.claude-plugin/plugin.json`（`displayName`）+ `.claude-plugin/marketplace.json` | `displayName` |
| Codex 等指令型 Agent | 本文件 `AGENTS.md` | 标题名称 |
| DeepSeek Harness (DSH) | `dsh/` 插件 + `cordis.patch.yml` + `presets/` 预设 | 预设 `name` |
| WorkBuddy / 通用 Agent | 读取 `SKILL.md` | frontmatter `description` |

> 说明：SKILL.md 的 frontmatter `name` 必须保持 kebab-case（`gongwen-skill`）以符合 Agent Skill 规范，对外展示统一使用中文展示名「公文全流程处理专家」。

---

## 6. 许可

MIT License，详见 [LICENSE](./LICENSE)。
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
