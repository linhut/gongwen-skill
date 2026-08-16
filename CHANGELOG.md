# Changelog

## v1.12.59 (2026-08-16)

### Fixed (P0)
- **DSH 插件桥接真实 bug**：`dsh/index.js` 调用入口从 `python gongwen.py`（已不存在的旧入口）改为 `python -m gongwen`（v1.12.57 重构后的正确入口）
- **DSH 插件桥接安全/健壮性**：用 `node:child_process.spawn` 数组参数替代 `execSync` 字符串拼接，避免 shell 引号注入；加 `PYTHONIOENCODING=utf-8`/`PYTHONUTF8=1` 防 Windows GBK 乱码；尊重 `ctx.cwd` 让 DSH Agent 调用走当前工作目录

### Changed
- **package.json 配置修复**：版本号同步 1.12.57→1.12.59；`files` 数组从失效的 `skills/` 改为 `.dsh/` + `engine/` + `gongwen/` + `rules/` + `prompts/` + `pyproject.toml` + `requirements.txt`；`keywords` 新增 `skill` 和 `cordis`
- **README/SKILL.md/usage-prompts.md/kdocs-integration.md 全量 CLI 入口同步**：18+47+47+47+22+22 = 203 处 `python gongwen.py` → `python -m gongwen`，消除 v1.12.57 重构遗留的文档失效

### Added
- **README DSH 集成章节重大补全**：参考 dsh-archive-manager 项目风格，加入四种 DSH 安装方式（方式零：纯 CLI；方式一：Skill 文件系统；方式二：npm Cordis 插件 bundle；方式三：本地 link 开发模式）
- 明确告知 DSH Cordis 模块化架构与 `~/.dsh/profiles/web/package.json` 中 `dsh.profile.bundles` 配置点
- 给出"DSH Web Profile 一键安装命令" `dsh plugin --profile web add -w gongwen-skill`
- 新增"适用场景对照表"帮助用户按需求选择安装方式
- README `DSH 兼容性自查表`：补 `Cordis 插件包` 和 `PyPI 上架` 一行，并把过时的 `CLI: python gongwen.py` 修正为 `python -m gongwen`

## v1.12.58 (2026-08-16)

### Fixed (P0)
- **CI 监测失效修复**：`.github/workflows/ci.yml` 主分支触发器从 `main` 改为 `master`（项目实际主分支是 `master`，原配置导致 171 次提交从未触发自动测试/发布）
- PyPI 发布从 `PYPI_API_TOKEN` 改为 **OIDC trusted publishing**（PEP 740），与 README 宣称一致；无需手动管理 token

### Added (P1)
- **测试覆盖扩展 +48 用例**：99 → 147（+48 个）全绿
  - `tests/test_commands_smoke.py`：24 个 `argparse --help` 入口 + 7 个关键参数断言（锁住所有子命令注册，防止重构 silently 丢命令）
  - `tests/test_optimize_e2e.py`：`check --json` / `optimize --apply` / `fix-common` / `bold-first` / `audit` 端到端
  - `tests/test_inject_e2e.py`：`header` / `footer` / `pagenum` 端到端 + 必填参数缺失校验
  - `tests/test_optimize_content_e2e.py`：tracked / inline 模式 + 缺 --changes 报错 + 无效 --mode reject
- **PEP 561 类型标记**：新增空 `engine/py.typed` 和 `gongwen/py.typed`，pyproject + MANIFEST 同步包含，下游 IDE/mypy 可识别为 typed package
- CI Python 矩阵补 3.14（与 pyproject classifier 一致）
- CI 加 `pytest --cov=gongwen --cov=engine --cov-fail-under=50` 覆盖率门槛

### Changed (P1)
- **logger 输出从 stdout 改到 stderr**：修复 `logger.py` 把 INFO 日志喷到 stdout 污染 `--json` / 管道输出的问题；`check --json` 等结构化输出现在是纯净 JSON

### Docs (P2)
- README 能力一览表补齐 `fix-common`（路径 D 一键修复）和 `handoff`（会话交接）两行
- AUDIT_REPORT.md：新增完整 P8 标准审计报告（340 行，22 KB），含 P0/P1/P2 优先级清单
- requirements.txt 加注释化交叉引用说明（依赖以 pyproject.toml 为权威，避免版本下限漂移）

### Notes
- P1-1 (`_legacy.py` 2400 行按 5 子包拆分) + P2-2 (≥500 行单文件拆分) 推迟到 v1.12.59 单独 PR 处理，避免此次改动量过大难 review；测试覆盖已就位，回归网完整
- P1-4 (42 处 `except+pass`) 核查后确认均为合理容错（字段读取兜底/临时文件清理/`raise` 配对），不引入噪声日志
- P2-7 (`live_edit.py` 当前无 CLI 入口) 添加 docstring 注释保留为 Agent 交互编辑预留 API

## v1.12.57 (2026-08-15)

### Added
- PyPI 打包支持 (`pyproject.toml` + `MANIFEST.in`)，发布到 PyPI，支持 `pip install gongwen-skill`
- GitHub Actions CI/CD (`.github/workflows/ci.yml`)，自动测试 + 自动发布到 PyPI
- 社区贡献基础 (`CONTRIBUTING.md` + `CODE_OF_CONDUCT.md` + Issue/PR 模板)
- DSH npm 插件包 (`package.json` + `dsh/index.js` + `cordis.patch.yml`)
- README 徽章更新（CI/PyPI/DSH/Downloads）
- `.gitignore` 更新（排除 `.codegraph/` 和临时报告）

## v1.12.56 (2026-08-08)

### Added
- DSH (DeepSeek Harness) 技能集成支持
  - 创建 `.dsh/skills/gongwen-skill/` 目录结构，DSH 文件系统可自动发现
  - 同时提供 **目录技能** (`.dsh/skills/gongwen-skill/SKILL.md`) 和 **单文件技能** (`.dsh/skills/gongwen-skill.md`) 双格式兼容
  - SKILL.md frontmatter 增强：增加 `whenToUse`、`user-invocable`、`metadata` 字段
  - README.md 增加 "DeepSeek Harness (DSH) 集成" 章节
  - 提供 DSH 技能发现方式说明、快速安装指南、兼容性检查表
  - 明确说明 DSH 技能市场基于本地文件系统，无中心化商店

## v1.12.55 (2026-08-07)

### Changed
- 表格虚线边框优化（dashed 表线，便于裁剪打印）
  - `generator._add_table` 显式写入 `tblBorders`（`w:val=dashed`，六边），直接格式覆盖 Table Grid 实线样式
  - 移除残留 `tblBorders`，避免实线叠加

## v1.12.54 (2026-08-05)

### Fixed
- 0 处批注时验证逻辑短路（FIX-V153-01），optimize-content tracked + full-review 两路径不再误报
- 结语检查按文种差异化（FIX-V153-02）：`_ENDING_TAIL_SIZE`（批复/函收窄为 3 段）、排除落款/日期/批注段、`original_text` 可为空

### Added
- 新增 `ending.check` 结语检查（`_check_ending` + `_infer_doc_type_from_rule`，5 文种映射，修复 CHK-RPT/CHK-RP 前缀误判）
- 新增 CHANGELOG.md（v1.12.50~v1.12.53 变更记录，FIX-V153-03）

## v1.12.53 (2026-08-05)

### Fixed
- `_atomic_save` os.replace 增加重试（FIX-A001），解决 Windows 文件锁导致 md2docx 页码注入失败
- 批注锚定增加内容段落映射（FIX-A002），跳过无文本 run 的空段，解决锚定偏移
- 批注完整性验证逻辑拆分（FIX-A003），修订/批注独立判断，避免误报
- prompts/usage-prompts.md 和 README.md 行距 28.95→33 同步（FIX-B001）

### Added
- 结语检查 `ending.check` 实现（FIX-V153-02）：5 种文种（通知/请示/报告/批复/函）结尾格式检查从"跳过"变为实际触发
- 0 处批注时验证逻辑短路（FIX-V153-01），optimize-content / full-review 不再误报

## v1.12.52 (2026-08-04)

### Fixed
- `inject.py`: `inject_page_number` 打开文件前增加重试机制（5×0.2s），解决 `generate_docx` 后文件句柄未释放导致的 `PermissionError`
- `template_builder.py`: `body_config` fallback 行距 28.95→33（与 YAML 配置一致）
- `generator.py`: 注释中 28.95pt→33pt 同步

## v1.12.51 (2026-08-04)

### Fixed
- 页边距/行距死循环修复（FIX-C003, FIX-C015）
- 批注注入失败修复（_anchor_comment 修复）
- 验证代码误报修复（W变量 f-string 修复）
- 座签 BOM 污染字号修复
- md2docx 页码注入修复
- 批注不搜 delText 修复
- md2docx BOM/#号清理
- subprocess encoding 统一

## v1.12.50 (2026-08-03)

### Added
- 省筹委会排版规范适配（页边距 2.8/2.8/2.7/2.7cm，行距 33pt）
- 8色批注/修订方案
- 事实核验独立批注作者
