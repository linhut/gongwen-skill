# gongwen-skill 全功能全代码审计优化报告（P8 标准）

> **审计日期**：2026-08-16
> **审计依据**：P8 全功能全代码审计要求
> **审计基线**：git HEAD `27ac9fb` / 版本 v1.12.57 / 测试 99/99 通过（3.87s）
> **代码规模**：60 个 Python 文件、约 20,800 行、760 KB
> **审计范围**：代码规范与质量、架构与模块组织、CLI 功能、规则引擎、测试覆盖、文档与工程化、安全与合规、性能与可维护性

---

## 一、审计基线与总体评分

| 维度 | 满分 | 得分 | 评级 |
|:---|:----:|:----:|:----:|
| 架构与模块组织 | 15 | 11.0 | B+ |
| 代码质量与规范 | 15 | 11.5 | B+ |
| CLI 功能完整性 | 12 | 10.5 | A- |
| 规则引擎 | 10 | 9.0 | A |
| 测试覆盖与隔离 | 15 | 7.5 | C+ |
| 文档与工程化 | 13 | 9.5 | B |
| 安全与合规 | 10 | 9.0 | A- |
| 性能与可维护性 | 10 | 8.5 | B+ |
| **总分** | **100** | **76.5** | **B+（良好）** |

**核心结论**：项目功能完整、规则引擎和安全设计扎实；但有 **1 项 P0 致命缺陷**（CI 主分支配置错误，导致 171 次提交从未触发自动测试/发布）、**若干 P1 工程债**（CLI 单文件 2400 行、测试盲点覆盖 19+ 核心模块）。

---

## 二、P0 致命问题（必须立即修复）

### P0-1 CI 主分支配置错误 —— 171 次提交自动测试/发布全部失效

**位置**：`.github/workflows/ci.yml:4-8`
**证据**：
```yaml
on:
  push:
    branches: [main]        # ← 错误
    tags: ['v*']
  pull_request:
    branches: [main]        # ← 错误
```
项目实际主分支是 `master`（`git rev-parse --abbrev-ref HEAD` = `master`，三个远程仓库 origin/gc/atomgit 的 HEAD 也都指向 master），**没有任何 main 分支**。

**后果**：
- 171 次提交中所有 `push` 事件都未匹配 `branches: [main]`，**测试 CI 从未自动运行**
- `tags: ['v*']` 触发器不依赖分之名，理论上 tag push 能触发 publish，但 `publish` job `needs: [test, lint]`，而 test/lint 在非 tag push 下也不触发，**首次打 tag 的 test job 不会跑**，发布的是**从未被 CI 验证过的代码**
- README 第 277 行宣称「打 tag 自动发布 PyPI（trusted publishing）」，但实际 `ci.yml:59` 用的是 `password: ${{ secrets.PYPI_API_TOKEN }}`——**与 README 宣称的 trusted publishing 不符**

**严重性**：P0（致命）· 整个 CI/CD 体系失效

**修复方案**：
```yaml
on:
  push:
    branches: [master]        # ← 修正
    tags: ['v*']
  pull_request:
    branches: [master]        # ← 修正
```
同时把 `publish` job 的 `password: ${{ secrets.PYPI_API_TOKEN }}` 改为 trusted publishing（OIDC）：
```yaml
publish:
  permissions:
    id-token: write  # 已配置
  steps:
    - uses: pypa/gh-action-pypi-publish@release/v1
      # 删除 with: password: ... 一行，改用 OIDC trusted publishing
```
**工时**：15 分钟

---

## 三、P1 高优先级问题（1 周内修复）

### P1-1 CLI 主入口单文件 2400 行（包拆分名不副实）

**位置**：`gongwen/_legacy.py`（实测 2398 行，132 KB）
**证据**：
- `gongwen/__init__.py`、`__main__.py`、`cli/__init__.py` 全都仅 `from gongwen._legacy import *` 或 `main`
- 重构提交 `eccb9e1` 仅完成包外壳拆分，CLI 逻辑（26 个子命令、`main()`、各 `cmd_xxx()` 处理器）**全部塞进 `_legacy.py`**
- import 链路：`_legacy.py` 一家就 import 了 11 处 `core.document.parser`、9 处 `core.rules.manager` 等多模块

**评估**：单文件 2400 行、132 KB 是明显的可维护性反模式。新增/修改命令时定位成本极高，合并冲突频繁。

**修复方案**：按职责分组拆为 `gongwen/cli/{format,content,generate,layout,utils}/` 5 个子包，main() 仅做 argparse 分发：
- `cli/format_cmds.py`：check / optimize / fix-common / bold-first
- `cli/content_cmds.py`：optimize-content / full-review / review
- `cli/generate_cmds.py`：template / md2docx / generate / parse / list-types
- `cli/layout_cmds.py`：header / footer / pagenum
- `cli/utils_cmds.py`：table-signs / audit / style-learn / style-list / check-update / handoff / rule-{export,import,list}
- `cli/main.py`：仅 argparse 注册 + set_defaults
- `cli/io.py`：抽出 223 处 print() → `print_vinfo()` / `print_warn()` 统一封装（可路由 logging）

**工时**：2-3 天

### P1-2 CLI 输出依赖 print() 而非 logging（223 处）

**位置**：`gongwen/_legacy.py` 220+ 处、`engine/docx_to_image.py` 4 处、`engine/core/document/tracked_annotator.py` 1 处
**评估**：
- 99% 的 print 是 CLI 用户输出，不是调试残留（这是写代码时 `print(...)` 替代 `click.echo`
- 但用裸 print **无法被重定向到 stderr/file、无 verbosity 控制、无单元测试 mock 入口**
- `--json` 等结构化输出会与 print 信息混杂到 stdout，破坏 JSON 流

**修复方案**：
1. 用户可见的成功信息走 `print()` → `sys.stdout` 是合理的
2. 警告/错误走 `logging.getLogger("gongwen").warning()` 或 `print(..., file=sys.stderr)`（部分已用 stderr ✓）
3. 加 `--verbose/--quiet` 控制日志级别
4. 关键统计字段（`修复 X 项 / 批注 Y 条`）抽出为返回 dict，便于 `--json` 模式和测试断言

**工时**：1 天

### P1-3 测试覆盖关键盲点 —— 19+ 核心模块 0 用例

**位置**：`tests/`（99 用例但分布极不均衡）
**证据**（grep `\bmod\b` 在 tests/ 全量匹配）：

| 状态 | 模块 | 行数 | 角色 | 风险 |
|:---|:---|:---:|:---|:---|
| ✅ COVERED | core/document/parser | 705 | 解析核心 | OK |
| ✅ COVERED | core/document/generator | 963 | 生成核心 | OK |
| ✅ COVERED | core/document/modifier | 1354 | 修改器 | OK（被 test_modifier_cleanup 覆盖） |
| ✅ COVERED | core/document/reviewer_comments | 322 | 批注/角色 | OK |
| ✅ COVERED | core/rules/engine | — | 规则引擎 | OK |
| ✅ COVERED | core/rules/loader、manager | — | 规则加载 | OK |
| ❌ **UNCHED** | **engine/optimizer.py** | **670** | **格式优化器（`optimize` 命令内核）** | 高 |
| ❌ **UNCHED** | **engine/inject.py** | **592** | **版头/版记/页码注入** | 高 |
| ❌ **UNCHED** | **engine/core/rules/checker.py** | **698** | **`check` 命令内核** | 高 |
| ❌ **UNCHED** | **engine/core/rules/fixer.py** | 235 | fix 引擎 | 中 |
| ❌ **UNCHED** | **engine/core/document/tracked_annotator.py** | **669** | **`optimize-content` 核心（修订+批注注入）** | **高** |
| ❌ **UNCHED** | engine/core/document/annotator.py | 359 | 旧批注器 | 中 |
| ❌ **UNCHED** | engine/core/document/editor.py | 483 | 编辑器 | 中 |
| ❌ **UNCHED** | engine/core/document/ooxml_parser.py | — | OOXML 解析 | 中 |
| ❌ **UNCHED** | engine/core/document/tracked_changes.py | 276 | 修订标记 | 中 |
| ❌ **UNCHED** | engine/core/document/structure_analyzer.py | 264 | 结构分析 | 中 |
| ❌ **UNCHED** | engine/core/document/ai_structure_analyzer.py | 236 | AI 结构分析 | 低 |
| ❌ **UNCHED** | engine/fact_check.py | 577 | 事实核验 | 中 |
| ❌ **UNCHED** | engine/template_builder.py | 355 | 模板生成器 | 中 |
| ❌ **UNCHED** | engine/structure_checker.py | — | 结构检查 | 中 |
| ❌ **UNCHED** | engine/focus_checker.py | — | 焦点检查 | 中 |
| ❌ **UNCHED** | engine/style_profile.py | 312 | 样式学习 | 低 |
| ❌ **UNCHED** | engine/live_edit.py | 287 | 在线编辑（疑似未使用） | 待评估 |
| ❌ **UNCHED** | gongwen/_legacy.py | 2398 | **CLI main + 26 命令** | **高（建议至少做 argparse smoke）** |

**评估**：核心 CLI 命令（`optimize` / `check` / `inject` / `optimize-content` / `header` 等）的端到端没有任何测试用例，仅 `test_pipeline.py` 测了 `parse → generate` round-trip。v1.12.51-57 大量修 complex  bug（FIX-A001~A003 / B01-B10 / C0xx）但**没有用例锁住回归**，未来重构风险高。

**修复方案**：按「关键路径优先」补用例：
1. `test_commands_smoke.py`：对 24 个子命令做 `argparse --help` 返回 0 的 smoke 测试（参照 `test_table_signs.py:227` 已有的 `python -m gongwen table-signs --help` 模式）
2. `test_optimize_e2e.py`：构造简短 docx → `optimize --apply` → `check` 通过 → assert 文件存在/输出 stats dict
3. `test_inject_e2e.py`：header/footer/pagenum 三个注入命令的端到端
4. `test_optimize_content_e2e.py`：`optimize-content --changes sample.json --apply --mode tracked` → assert 修订+批注 byte 大小
5. 加 `pytest-cov` 到 dev deps，CI 跑 `pytest --cov=gongwen --cov=engine --cov-fail-under=50`
6. 在 `tests/` 强制每条端到端使用 `tmp_path` fixture（已 OK ✓）

**工时**：2-3 天

### P1-4 异常静默吞咽 42 处 `except + pass`

**扫描结果**：`engine/` 与 `gongwen/` 共 42 处 `except X: pass` 的 2 行组合，分布：

| 模块 | 数量 | 性质 |
|:---|:----:|:---|
| `engine/core/document/parser.py` | 7 | 容错继续解析（合理但无日志） |
| `gongwen/_legacy.py` | 4 | 含我们已修复的 `register_cleanup` 残留 + 1 处 zgong utf-8（合理） + 2 处未知 |
| `engine/core/document/tracked_annotator.py` | 3 | OOXML 元素容错 |
| `engine/docx_to_image.py` | 6 | LibreOffice 命令行容错（合理） |
| `engine/core/document/ai_structure_analyzer.py` | 5 | LLM 调用容错 |
| `engine/core/document/parser_format.py` | 3 | 字段提取容错 |
| 其它（含 inject/annotator/style_profile 等 17 处） | 各 1-2 | 多为字段级容错 |

**评估**：
- 必要的容错（如 OOXML 字段缺失、`docx_to_image` LibreOffice 不存在）：合理但**应加 logger.warning**
- 真正吞异常位置（如 `parser.py:218/281`）：**应该 raise 或转为 Issue 让上层决策**
- `except+pass` 与 `except Exception` 总数 104 处对比，silent 占 40%

**修复方案**：
1. batch 把每处 `pass` 换成 `logger.warning(f"...")` 或 `raise ValueError(f"具体字段: ...")`
2. 对真正需要 fallback 的（字体/LibreOffice 等）保留 except 但记录 `logger.info`
3. `_legacy.py:1812/1854/1928/1962` 4 处需逐一评估是否实际是死分支

**工时**：1 天

### P1-5 类型标注覆盖率仅 57.8%，缺 `py.typed`

**证据**：
- 510 个函数中 295 个有 `->` 返回标注，覆盖 57.8%
- 无 `py.typed` marker —— PEP 561 未启用，下游 IDE/mypy 无法识别为 typed package
- `pyproject.toml` 也未声明 `py.typed` 入包

**修复方案**：
1. 新增空文件 `engine/py.typed` 和 `gongwen/py.typed`
2. `pyproject.toml` 加 `[tool.setuptools.package-data]` 或 `include-package-data = true`
3. 统一为所有 public API 函数补 `-> type` 标注（建议 PR 模板加 type check）
4. 加可选 dev 依赖 `mypy`，CI lint job 加 `mypy engine/`（可选）

**工时**：2 天

---

## 四、P2 中等优先级问题（1 个月内修复）

### P2-1 测试用例分布不均衡 + 总数对不上宣传

**证据**：
- `test_table_signs.py` 21 个、`test_rules.py` 19 个、`test_models.py` 16 个、`test_handoff.py` 13 个、`test_font_utils.py` 12 个、`test_modifier_cleanup.py` 8 个、`test_role_resolution.py` 7 个、`test_pipeline.py` 仅 **3 个**
- 桌签用例（21）超过优化器+注入+内容优化（0 用例）的总和
- README「99/99 通过」属实，但**99 个用例覆盖的核心模块数量仅 7 个** vs 60 个 Python 文件

### P2-2 单文件过大（≥500 行）

| 文件 | 行数 | 评估 | 拆分建议 |
|:---|:---:|:---|:---|
| `gongwen/_legacy.py` | 2398 | 见 P1-1 | 拆为 CLI 子包 |
| `engine/core/document/modifier.py` | 1354 | 高 | 按「段格式/首句/编号/清理」4 维拆 |
| `engine/core/document/generator.py` | 963 | 中高 | 按「页面/标题/正文/页码」拆 |
| `engine/core/document/parser.py` | 705 | 中 | 按「OOXML 提取/字段解析/Role 推断」拆 |
| `engine/core/rules/checker.py` | 698 | 中 | 按「font/margin/spacing/structure」拆 |
| `engine/optimizer.py` | 670 | 中 | 按「优化管线/修改应用/统计」拆 |
| `engine/core/document/tracked_annotator.py` | 669 | 中 | 按「people/comments/人物映射」拆 |
| `engine/inject.py` | 592 | 中 | 按「header/footer/pagenum」拆 |
| `engine/fact_check.py` | 577 | 中 | 按「实体提取/网络核验/批注生成」拆 |

### P2-3 PyPI 发布机制不合规

- `ci.yml:59`：仍用 `password: ${{ secrets.PYPI_API_TOKEN }}`，**未使用 PyPI 官方推荐的 OIDC trusted publishing**（`permissions.id-token: write` 已配置，仅差行）
- README 第 277 行宣称「trusted publishing」与实际不符 → 误导用户

### P2-4 CI 矩阵不全 + 无覆盖率门槛

- `python-version: ['3.10', '3.11', '3.12', '3.13']` 缺 `3.14`（pyproject 的 classifier 声明到 3.14）
- `pytest tests/ -v --tb=short` 无 `--cov`，无 `--cov-fail-under`

### P2-5 requirements.txt 与 pyproject.toml 依赖易漂移

- `requirements.txt` 与 `pyproject.toml [project.dependencies]` 重复声明，且没有 `constraints.txt`/`-r` 锁定

### P2-6 README 能力表与代码不完全对齐

- README 能力一览表（第 29-49 行）列 22 项，代码实际 24 项（多出 `fix-common`、`handoff`）
- 能力一览表未列入 `parse`、`generate` 已合并到模板/转写描述

**修复方案**：补全 README 第 29-49 行表格，增加 `fix-common` 和 `handoff` 行

### P2-7 死代码扫描

- `# TODO/# FIXME/# HACK/# XXX` 标记 **0 处**（扫描结果）—— 反常，可能 git history 已被人为清理，但也可能新人ícias 记号无管理 → 建议统一用 `# TODO(author):` 格式
- `live_edit.py`（287 行）疑似未被任何 module import 调用，需核实

---

## 五、安全与合规审计

| 检查项 | 状态 | 备注 |
|:---|:---:|:---|
| 路径遍历防护 | ✅ | `manager.py:157/201` regex 校验 + `resolve().relative_to()` 双重保护 |
| `eval/exec` 危险函数 | ✅ | 0 处使用 |
| `pickle.load` 反序列化 | ✅ | 0 处使用 |
| `yaml.load` 安全加载 | ✅ | 全部使用 `yaml.safe_load` |
| `subprocess` 调用 | ✅ | `docx_to_image.py` 仅调 LibreOffice，无 shell=True，输入为内部路径 |
| bare `except:` 吞所有异常 | ✅ | 0 处使用，全是 `except Exception` 或更具体类型 |
| 硬编码路径 | ✅ | 0 处（Windows/Users/home 等都被避免） |
| API Token 硬编码 | ✅ | 0 处（仅在 ci.yml 通过 secrets.PYPI_API_TOKEN） |
| 输入校验 | ✅ | rule-import 有 `validate_rule` schema 校验 |
| 临时文件 | ✅ | 已修复（v1.12.58 commit 27ac9fb）：`engine/tmp.py` 删除，atexit 清理由 `config.py` 接管 `APP_DATA_DIR/tmp` |
| 第三方依赖 | ✅ | 仅 python-docx/pydantic/pyyaml，无供应链风险 |
| 外部网络 | ✅ | 仅 `check-update` 调 GitHub/GitCode/AtomGit 公开 tag API，且用户主动触发 `+` 有 timeout |

**安全总分**：A-（唯一改进项 `fact_check.py` 的 web_verify 可加 URL 白名单 / HTTPS-only 校验）

---

## 六、可发现性 / 文档 / 工程化

| 维度 | 现状 | 建议 |
|:---|:---|:---|
| README | 363 行功能全景，含能力表、快速开始、GB/T 9704 标准表、25 文种表、规则三层、使用红线、Agent 集成、DSH 集成 | 优秀；建议补性能/限制章节 |
| CHANGELOG | 9 个版本条目，结构清晰；已补 v1.12.52 漏记 | 优秀 |
| CONTRIBUTING | [✅] | — |
| CODE_OF_CONDUCT | [✅] | — |
| Issue/PR 模板 | [✅] | — |
| 镜像仓库 | GitHub + GitCode + AtomGit 三仓同步 | 优秀 |
| `check-update` 多渠道 | ✅ 三仓库取最新 tag | 优秀（线上有真实价值） |
| Makefile | [✅] | — |
| npm bridge | [✅] `package.json` + `dsh/index.js` | — |
| `pyproject.toml` | [✅] PEP 621 全规范 | — |
| `MANIFEST.in` | [✅] | — |
| DSH Skill | 双格式兼容（目录 + 单文件） | 优秀 |
| 文档与代码同步 | README 能力表缺 fix-common、handoff | 见 P2-6 |
| Claude Code / AtomCode 集成文档 | ✅ | — |

**工程化总分**：B（一次 CI 修正 + 一次 README 补全即可达 A）

---

## 七、性能与可维护性

- ⚠️ **OOXML 注入是 hot path**：`inject.py` 反复读写 zip 流，对几千行大公文可能 IO bound → 可考虑缓存打开的 docx 句柄
- ⚠️ **结构/焦点检查** 的 `difflib.get_close_matches` 调用是 O(N×M) —— 大文档段落数 N 约几百时 OK，建议加注释上限
- ✅ **YAML 规则一次性加载并 deep-merge**：启动开销可控
- ✅ **测试运行 3.87s** —— 快，但有 21 个 table_signs 用例占大头，核心模块缺测
- 总体**可维护性中等偏上**，最大的坑是 `_legacy.py` 2400 行单文件

---

## 八、规则引擎专项审计

### 8.1 25 文种覆盖率核对

| README 宣称（第 189-193 行） | rules/official YAML | 状态 |
|:---|:---|:---:|
| 通知 | `notice.yaml` + `notice_public.yaml` | ✅ 多套 |
| 请示 | `request.yaml` | ✅ |
| 报告 | `report.yaml` | ✅ |
| 函 | `letter.yaml` | ✅ |
| 会议纪要 | `meeting.yaml` | ✅ |
| 纪要 | `minutes.yaml` | ✅ |
| 决定 | `decision.yaml` | ✅ |
| 通告 | `notice_public.yaml` | ✅ |
| 公告 | `announcement.yaml` | ✅ |
| 命令 | `command.yaml` | ✅ |
| 通报 | `bulletin.yaml` | ✅ |
| 议案 | `bill.yaml` | ✅ |
| 批复 | `reply.yaml` | ✅ |
| 指示 | `instruction.yaml` | ✅ |
| 制度 | `regulation.yaml` | ✅ |
| 公报 | `communique.yaml` | ✅ |
| 意见 | `opinion.yaml` | ✅ |
| 总结 | `summary.yaml` | ✅ |
| 方案/计划 | `work_plan.yaml` | ✅ |
| 桌签 | `table_sign.yaml` | ✅ |
| 技术方案 | `technical_proposal.yaml` | ✅ |
| 决议 | `resolution.yaml` | ✅ |
| 新闻稿/简报 | `news.yaml` | ✅ |
| 讲话稿/主持词 | `speech.yaml` | ✅ |
| 其他 | `_common.yaml`（兜底） | ✅ |
| **无对应 README 条目** | `command.yaml`（命令） | README 第 191 行已列 ✓ |

**覆盖率**：**25 文种 100% 覆盖**（含兜底通用规则）✅

### 8.2 三层合并实现质量

`manager.py:_deep_merge` 实现 **良好**：
- ✅ 字段级深合并（line 95-117），不是整文件覆盖
- ✅ list 类字段（`fix_rules` / `check_rules`）专用 `dedup_extend` + 按 `field` / `target` 去重（line 108-117），避免覆盖丢失
- ✅ 同键覆盖有 logger.info（line 134）
- ✅ dedup_key None 时有 warning（line 125-126）
- ✅ 优先级严格 `official < custom < user`（line 63-83）
- ✅ `_load_yaml` 失败时 logger.error 且返回 `{}`，不静默中断

**唯一改进点**：第 100-106 行 `title` → `doc_title` 的特殊映射**仅供已有 `doc_title` 时生效**，这是兼容历史 _common.yaml 的妥协，建议补单元测试锁住该行为

---

## 九、修复优先级清单与工时估算

| 优先级 | 编号 | 问题 | 修复工时 | 责任维度 |
|:---:|:---|:---|:----:|:---|
| **P0** | P0-1 | CI 主分支配错（main → master）+ PyPI publish 机制 | **0.25 天** | 工程化 |
| P1 | P1-1 | CLI 单文件 2400 行拆分 | 2-3 天 | 架构 |
| P1 | P1-2 | print 改 logging（223 处） | 1 天 | 工程化 |
| P1 | P1-3 | 测试盲点：补 19+ 核心模块用例 + cov 门槛 | 2-3 天 | 测试 |
| P1 | P1-4 | except+pass 静默吞噬（42 处） | 1 天 | 代码质量 |
| P1 | P1-5 | 类型标注 57.8%→90% + py.typed | 2 天 | 代码质量 |
| P2 | P2-1 | 测试用例分布不均 → 已合并 P1-3 | — | — |
| P2 | P2-2 | 9 个 ≥500 行单文件拆分 | 5-7 天 | 架构 |
| P2 | P2-3 | PyPI publish → OIDC trusted publishing | 0.25 天 | 工程化 |
| P2 | P2-4 | CI 矩阵补 3.14 + cov-fail-under | 0.5 天 | 工程化 |
| P2 | P2-5 | requirements/pyproject 依赖去重 | 0.25 天 | 工程化 |
| P2 | P2-6 | README 能力表补 fix-common、handoff | 0.1 天 | 文档 |
| P2 | P2-7 | live_edit.py 死代码核实 | 0.25 天 | 代码质量 |

---

## 十、推荐本周执行顺序

**第 1 天（P0 必修）**：
1. 修 `.github/workflows/ci.yml`：`branches: [main]` → `branches: [master]`
2. 改 publish job 为 OIDC trusted publishing，README 同步更正
3. 验证：打 v1.12.58 tag → 确认 CI 触发 + PyPI 自动发布

**第 2-3 天（P1 高优先级）**：
4. 写 `test_commands_smoke.py` 锁住 24 个 argparse 入口（修复 P1-3 一半）
5. 写 `test_optimize_e2e.py` / `test_inject_e2e.py` / `test_optimize_content_e2e.py` 锁住 3 个核心命令（P1-3 另一半）

**第 4-7 天（P1 + P2）**：
6. `_legacy.py` 按 5 子包拆分（P1-1）
7. 加 `py.typed` + 优先级补类型标注到 90%（P1-5）
8. 42 处 except+pass 加 logger.warning（P1-4）

**第 8-15 天（P2 收尾）**：
9. 大文件拆分（`modifier.py` / `generator.py` 等 9 处）
10. CI 矩阵补 3.14 + cov-fail-under
11. README 能力表补完 + requirements/pyproject 依赖去重
12. live_edit.py 死代码核实、删除或启用

---

## 十一、附录：扫描数据総括

| 项 | 数值 | 来源 |
|:---|:----:|:---|
| Python 文件 | 60 | `Get-ChildItem -Recurse -Include *.py` |
| 代码总量 | 760 KB / ~20,800 行 | 同上 |
| `gongwen/_legacy.py` | 2398 行 / 132 KB | `Measure-Object -Line` |
| `engine/core/document/modifier.py` | 1354 行 | 同上 |
| `def with ->` 类型标注 | 295/510 = 57.8% | regex 扫描 |
| `except Exception` 总数 | 104 | grep |
| `bare except:` | 0 | grep |
| `except + pass` 静默 | 42 | 2 行窗口扫描 |
| `TODO/FIXME/HACK/XXX` | 0 | grep |
| `print()` 非测试代码 | 223（`_legacy.py` 一家就 220） | grep |
| `eval/exec` | 0 | grep |
| `pickle.load` | 0 | grep |
| 硬编码路径 | 0 | regex 扫描 |
| 测试用例总数 | 99（与 README 一致） | grep `def test_` |
| `tests/` 文件 | 10 + conftest.py（46 行） | `Get-ChildItem` |
| rules/official YAML | 25 | `Get-ChildItem` |
| git 提交总数 | 171 | （上次审计报告记录） |
| git 分之名 | `master`（CI 配的是 main） | `git rev-parse --abbrev-ref HEAD` |

---

## 十二、结论

- **健康度评级：B+（76.5/100）**：项目定位清晰、功能高度完整（25 文种全覆盖 + 26 命令）、规则引擎与安全设计扎实。**最大致命问题是 CI 主分支配置错误**，导致 171 次提交从未真正经过「测试 + 发布」自动化验证，这是必须当天修复的 P0。
- 在 P0 修复后，**项目可立即升级到 A- 级**；P1 全部修复 + P2 关键项修复后，可维持稳定 A 级。
- **不推荐立即进行 `modifier.py`/`generator.py` 等大文件拆分**：在 P1-3 的测试盲点未补全前进行大重构会让 bug 无处可查（没有回归测试兜底），应**先补测试 → 后做拆分**。
- 项目 v1.12.58 已成功清理死代码（`engine/tmp.py`）并补 CHANGELOG v1.12.52（commit 27ac9fb），工程化债在持续收敛。

---

> 报告结束 · 审计依据 P8 · gongwen-skill @ 27ac9fb · 2026-08-16
