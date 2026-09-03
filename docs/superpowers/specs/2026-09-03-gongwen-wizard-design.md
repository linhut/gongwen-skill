# gongwen wizard 向导式交互设计

> 日期：2026-09-03 · 状态：已批准（用户确认整体认可）· 范围：CLI + SKILL.md

## 目标

为 gongwen-skill 增加**向导式交互**：gongwen wizard 命令以 A/B/C/D 路径菜单引导用户，交互收集参数后直接执行对应现有命令；同时把 SKILL.md「用户交互指引」升级为与向导一致的向导式分步流程。

## 已确认决策

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 范围 | 新增 CLI 向导命令 + 完善 SKILL.md 交互指引（含 README/CHANGELOG 同步） |
| 2 | 产出物 | 仅路径引导（A/B/C/D 选择），不收集公文内容字段 |
| 3 | 引导后行为 | 直接执行对应命令 |
| 4 | 交互方式 | 双模式：终端 input() 交互 + --answers JSON 非交互（Agent 用） |
| 5 | 路径集合 | A=optimize ｜ B=optimize-content ｜ C=template ｜ D=fix-common |
| 6 | 修改类确认 | 沿用 CLI 默认：先预览再确认（A/B/D） |
| 7 | 架构位置 | 新建 gongwen/cli/wizard_cmds.py，_legacy.py 只注册入口 |
| 8 | --answers 格式 | 扁平化 JSON，顶层带 path 字段 |
| 9 | 执行机制 | subprocess 调用 sys.executable -m gongwen <子命令>，输出流式透传 |

## 命令定义

    python -m gongwen wizard [--answers answers.json] [--dry-run]

- --answers：非交互模式，JSON 文件路径；结构 {"path":"A","input":"a.docx","doc_type":"notice","output":"b.docx","apply":true}
- --dry-run：只打印将执行的命令，不真正执行

## 模块设计：gongwen/cli/wizard_cmds.py

| 组件 | 职责 |
|------|------|
| cmd_wizard(args) | 入口：读 --answers 或进入交互循环，分发到路径 |
| _ask(question, default, choices) | 交互提问 helper：显示默认值、校验、循环重问 |
| _ask_yes_no(question, default) | y/n 确认 |
| _ask_path() | 展示 A/B/C/D 菜单，选择路径 |
| _collect_params(path, answers) | 按路径收集参数（answers 优先，缺则交互补充） |
| _resolve_doc_type(raw, types) | 类型智能匹配：序号 / id / 中文名 |
| _build_cmd(path, params) | 拼出 [sys.executable, "-m", "gongwen", sub, ...] |
| _run(cmd, dry_run) | subprocess 执行或打印（dry-run） |
| _confirm_exec() | 预览后 y/n 确认 |

### 路径参数收集清单

| 路径 | 子命令 | 收集参数 | 确认行为 |
|------|--------|----------|----------|
| A 格式优化 | optimize | input（必填）、doc_type（可选）、output（可选） | 先跑预览（无 --apply）→ y/n → 带 --apply 执行 |
| B 内容优化 | optimize-content | input（必填）、changes（可选）、output（可选） | 先跑预览（无 --apply）→ y/n → 带 --apply 执行 |
| C 生成模板 | template | doc_type（必填）、output（可选） | 无修改风险，直接执行 |
| D 一键修复 | fix-common | input（必填）、output（可选） | 显示命令 → y/n 确认执行 |

### --answers 缺省语义

- path 缺失：非 TTY 报错；TTY 进入交互菜单
- 其他字段缺失：TTY 交互补充；非 TTY 报错列出缺失字段
- A/B/D 无 apply：非交互模式只跑预览/打印命令，提示加 apply:true 后执行（安全默认）；apply:true 跳过确认直接执行
- C 无修改风险，不受 apply 影响，直接执行

### 类型智能匹配（_resolve_doc_type）

1. 纯数字 → 类型列表序号（list_available_types 排序后 1 起）
2. 直接 id 精确匹配（如 notice）
3. 中文名匹配（复用 helpers.TYPE_KEYWORDS，如「通知」→ notice）
4. 子串匹配（输入包含中文关键词即命中）

### 错误处理

- 输入文件不存在：交互重问；--answers 直接报错退出（非零）
- Ctrl-C：优雅退出，打印提示，不留下半执行状态
- 子命令失败：透传子命令退出码
- Windows 兼容：subprocess 不 capture，stdout/stderr 继承父进程，避免编码问题

## 文档更新

1. **SKILL.md**
   - 849 行「附录：全部命令速查（24 个…）」→ 25 个，加 wizard 行（引导分类）
   - 259-279 行「用户交互指引」升级为向导式三步流程，标注终端用户可直接 gongwen wizard
   - 新增「向导式交互（wizard）」小节：何时用、交互流程、--answers 非交互用法
2. **README.md**：能力一览表加 wizard 条目；命令行参数速查补说明
3. **CHANGELOG.md**：追加 v2.7.0 变更记录（Added: wizard 向导）

## 测试与校验

- tests/ 按仓库策略仅本地保留不提交：本地 pytest 覆盖 cmd_wizard（dry-run、--answers、参数校验、类型匹配、路径分发）
- 过 ruff / pycodestyle（CI lint 门槛）
- 冒烟：python -m gongwen wizard --dry-run --answers answers.json 端到端

## 实施顺序

1. 设计文档（本文件）
2. gongwen/cli/wizard_cmds.py
3. _legacy.py 注册 wizard 子命令
4. SKILL.md / README.md / CHANGELOG.md
5. 本地冒烟 + lint + git 提交