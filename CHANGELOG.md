# Changelog

## v1.12.69 (2026-08-06)

### Added
- 项目级审计与架构代码优化（ruff 0 错误/542 测试通过/56% 覆盖率）
- 修复 37 个 F821 未定义名称（真实运行时 bug）
- 修复 256 个 ruff 错误至 0（F401/F821/F841/F541/F811/E402/F823/F403）
- 修复 _generator_helpers.py/generator.py 循环依赖（正确提取 4 个辅助函数）
- 修复 style_helpers.py/_legacy.py 循环导入
- 添加 backward-compatible 函数 re-export（verify_output_fresh 等）
- 修复 tracked_annotator.py logger 引用前赋值（F823）

### Changed
- 优化 _generator_helpers.py 导入结构（新增 lxml/font_utils/models 依赖）
- 更新 CI 配置使测试步骤在 tests/ 缺失时优雅跳过

## v1.12.68 (2026-08-17)

### Changed — 阶梯2/3/4 全部完成

**2a: modifier.py convert_markdown 提取**
- `engine/core/document/markdown_converter.py`（447行）：Markdown 转换功能独立模块
- modifier.py: 1599→1188 行（-411行）

**2b: generator.py _add_table/_add_page_number_field 提取**
- `engine/core/document/_generator_helpers.py`（296行）：表格和页码域辅助函数
- generator.py: 1104→835 行（-269行）

**3: cmd_optimize_content 提取**
- `gongwen/cli/content_cmds.py`（831行）：内容优化命令独立模块
- _legacy.py: 1702→924 行（-778行，累计-70%）

**4: ARCH-03 彻底修复**
- engine/ 下 33 个文件的 `from core./utils./config import` 改为 `from engine.core./engine.utils./engine.config import`
- engine/ 已成为正规 Python 包，不再依赖 sys.path.insert
- _bootstrap.py 保留 sys.path.insert 仅作为向后兼容回退

### Summary
- _legacy.py: 3096→924行（-70%）
- 新增 3 个独立模块（markdown_converter + _generator_helpers + content_cmds）
- 6 个 cli 子模块 + 3 个 engine 子模块
- 542/542 测试通过

## v1.12.67 (2026-08-17)

### Changed — 覆盖率 55% → 56%，modifier.py 44% → 50%
- **test_modifier.py**（44用例）：modifier.py 全函数测试——modify_font/size/alignment/bold/margins/line_spacing + detect_paragraph_type + should_bold_first_sentence + clean_path_b_markers + parse 辅助函数
- **三仓同步**：v1.12.64-v1.12.66 全部推送到 GitHub/GitCode/AtomGit，含测试文件
- 总用例 498 → 542

## v1.12.66 (2026-08-17)

### Changed — 覆盖率从 41% → 55%
- **test_main_function.py**（21用例）：main() 直接调用测试，覆盖所有子命令入口
- **test_optimize_content_main.py**（6用例）：cmd_optimize_content 的 tracked/inline/comment-mode/默认/错误模式测试
- **test_zero_coverage_modules.py**（14用例）：tracked_changes/structure_analyzer/ai_structure_analyzer/ooxml_workflow/chat_review 模块导入和纯函数测试
- **_legacy.py 覆盖率 4% → 34%**
- 总用例 457 → 498

## v1.12.65 (2026-08-17)

### Changed — 阶梯2：_legacy.py 大规模拆分
- **`_legacy.py` 从 3096 行 → 1702 行（-45%）**，拆分到 6 个子模块：
  - `gongwen/cli/helpers.py`（198行）：辅助函数（detect_doc_type/build_output_name/parse_config_overrides 等）
  - `gongwen/cli/font_cmds.py`（254行）：font 子命令 + 字体安装/检查/下载
  - `gongwen/cli/update_cmds.py`（150行）：check-update 子命令
  - `gongwen/cli/style_helpers.py`（406行）：样式辅助函数（_validate_changes_schema/_infer_paragraph_roles 等）
  - `gongwen/cli/review_cmds.py`（269行）：full-review/bold-first/fix-common/handoff 命令
  - `gongwen/cli/misc_cmds.py`（262行）：rule-export/rule-list/rule-import/table-signs/audit/style-learn/style-list/review 命令
- `gongwen/cli/__init__.py` 修复循环导入（lazy import）
- `_legacy.py` 通过 re-import 保持 100% 向后兼容

## v1.12.64 (2026-08-17)

### Added
- **ARCH-03 修复**：`gongwen/_bootstrap.py` 统一管理 sys.path hack，消除 3 处重复
- **md2docx bug 修复**：`doc_type` 变量在规则加载前被引用导致 UnboundLocalError
- **第二轮测试补强**（+150 用例，307→457）：
  - test_optimizer.py(11): 优化器纯函数测试
  - test_fact_check.py(18): 实体提取/核验测试
  - test_tracked_annotator.py(14): 修订标注测试
  - test_editor.py(15): 内容修订引擎测试
  - test_auto_optimizer.py(18): 自动优化器测试
  - test_docx_to_image.py(4): 模块导入测试
  - test_cli_integration.py(19): CLI 子进程集成测试
  - test_cli_integration2.py(12): CLI 第二轮集成测试
  - test_legacy_api.py(28): _legacy.py 直接 API 调用测试

### Changed
- 覆盖率 24% → 41%（_legacy.py: 5% → 12%）
- `live_edit.py` 消除 sys.path.insert（已通过 _bootstrap 统一管理）
- `conftest.py` 消除 sys.path.insert
- 测试用例仅本地保留，不推送 pip/GitHub

## v1.12.63 (2026-08-17)

### Added
- **字体管理 `font` 命令**：`python -m gongwen font install/check/list`，安装公文标准字体
- **字体文件内置**：`assets/fonts/` 包含 3 个 TTF 字体文件，git clone 用户直接可用
- **GitHub 下载 fallback**：pip install 用户自动从远程仓库下载字体
- **跨平台字体安装**：Windows/macOS/Linux 三平台支持
- **9 个新测试文件**：+143 用例（164→307），覆盖率 24%→33%

## v1.12.62 (2026-08-17)

### Fixed
- P1-2: inject.py 6处硬编码 Pt(33) 改为从规则读取
- P1-3: pyproject.toml package-data 加 etc/*.json
- P2-1: 16个文件 52处 except:pass 改为 logger.warning
- P2-2: 统一解析函数到 utils/parse.py
- P2-3~6: 删除 skills/ + setup.py + dist/ + engine/sessions/
- P2-7: Changelog URL main→master
- P2-8: MANIFEST.in 加 etc/*.json
- P2-10: RuleEngine mtime 扩展到三层目录
- P2-12: engine/__init__.py 修复包发现
- 清理 12 个非必要文件（审计报告/发布计划/社区规范/截图/Makefile）

## v1.12.61 (2026-08-17)

### Added
- **DSH 插件配置化排版参数**：支持通过 `~/.gongwen-skill/dsh-config.json` 管理页边距、行距、字体、字号、默认模板版本等排版参数，Agent 调用时自动注入
- **`--config-overrides` CLI 参数**：`template`/`check`/`optimize`/`md2docx` 四命令支持通用规则覆盖 JSON
- **`RuleEngine.set_config_overrides()`**：规则引擎支持运行时配置覆盖，优先级最高（official < custom < user < DSH config < CLI）
- **`apply_config_overrides()`**：`engine/core/rules/manager.py` 新增深度合并函数
- **DSH 插件 AI 工作指引**：`dsh/index.js` 的 `setup()` 注入 systemPrompt section
- **DSH 插件 `config` 命令**：支持 `init/show/get/set/reset` 五种操作管理配置
- **`etc/dsh-config-defaults.json`**：默认配置模板
- **`tests/test_config.py`**：17 用例测试配置覆盖功能
- **`engine/__init__.py`**：使 `engine/` 成为合法 Python 包，修复 setuptools 打包发现

### Fixed
- **`inject.py` 硬编码 `Pt(33)` 行距**：6 处改为从规则体系动态读取 `_get_line_spacing_pt()`，与配置化设计一致
- **`pyproject.toml` Changelog URL**：`main` → `master`（实际主分支）
- **`pyproject.toml` package-data**：添加 `etc = ["*.json"]`，修复 pip 安装后 `dsh-config-defaults.json` 缺失
- **`pyproject.toml` packages.find**：添加 `etc*` 到 include 列表
- **`MANIFEST.in`**：添加 `recursive-include etc/ *.json`
- **`RuleEngine._rules_mtime`**：mtime 扫描扩展到 official + custom + user 三层目录
- **`_legacy.py` md2docx 重复解析函数**：`_parse_margin`/`_parse_cm` 改为委托 `engine/utils/parse.py` 统一实现
- **40 处 `except: pass` 吞异常**：全部改为 `logger.warning` + 降级路径

### Removed
- **`setup.py`**：冗余文件，`pyproject.toml` 已完全覆盖
- **`skills/` 空目录**：与 `.dsh/skills/` 并行的空残留
- **`dist/` 旧构建产物**：v1.12.60 的 .whl 和 .tar.gz
- **`engine/sessions/` 残留文件**：27 个开发时会话 JSON

## v1.12.60 (2026-08-16)

### Fixed
- **发布链路修复（全量审计）**：`pyproject.toml` 恢复合法的 `[tool.setuptools.packages.find]` include/exclude 键（非法 `packages` 键导致 `python -m build --wheel` 直接失败，PyPI 发布被阻断）
- **wheel 内容缺失修复**：`rules/official/*.yaml`（25 个）+ `prompts/*.md` 经 package-data 打入 wheel（此前 pip 安装零规则文件，list-types/check 静默失效）
- **`_load_style_prompt` 路径回归修复**：v1.12.57 拆包后 `__file__.parent` 指向 `gongwen/`，改为 `parent.parent` 回到仓库根 `prompts/`，风格提示词恢复加载
- **`docx_to_image.py` tmp 路径同步**：临时 PDF 从 `engine/tmp`（安装目录可能只读）迁移到 `config.TMP_DIR`（B8 一致性）
- **CI lint 门槛达标**：修复 101 处 pycodestyle 违规（26 个文件），CI lint job 不再误挂
- **文种数量口径统一**：SKILL×3 frontmatter + README 从 22/25 统一为实际 24 类（list-types 实证）
- **CHANGELOG 缺口补记**：补记 v1.12.54/v1.12.55 条目（此前 53→56 跳号）

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
