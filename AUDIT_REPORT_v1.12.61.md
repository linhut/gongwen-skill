# gongwen-skill v1.12.61 全量审计报告

**审计日期**：2026-08-17  
**审计基线**：v1.12.61 (commit ebec186)  
**审计范围**：立项定位 → 框架架构 → 代码质量 → 功能完整性 → 逻辑正确性 → 安全性能 → 文档发布  
**代码规模**：65 个 Python 文件，~16,502 行 Python 代码，25 个 YAML 规则，164 个测试用例

---

## 一、立项与定位（评分：A）

### 1.1 项目立意

gongwen-skill 是一个**中文公文全流程处理工具**，源自桌面应用 [AI 公文智能优化助手](https://github.com/linhut/document-ai-assistant)，将其核心格式引擎抽取为独立发行版。

**核心价值**：
- 将 GB/T 9704《党政机关公文格式》国家标准编码为可执行的 YAML 规则体系
- 支持 .docx 公文的格式检查、自动修复、内容优化、模板生成、Markdown 转公文
- 完全自包含（3 个纯 Python 依赖），克隆即用，无需数据库/后端/LLM
- 原生集成 DSH（DeepSeek Harness）技能系统

**定位准确性**：项目在"公文格式自动化"这一垂直领域定位精准，24 类公文覆盖法定文种的主要类型。三渠道发布（GitHub/GitCode/AtomGit）+ PyPI 上架，面向中文用户群体。

### 1.2 适用场景

| 场景 | 覆盖 | 说明 |
|:-----|:----:|:-----|
| 终端 CLI 使用 | ✅ | `pip install gongwen-skill` 或克隆仓库 |
| DSH Agent 调用 | ✅ | Skill 文件系统 + npm bundle + link 模式 |
| 其他 AI Agent 调用 | ✅ | AtomCode/Claude Code skills 目录 |
| 纯 Python 库引用 | ✅ | `from gongwen import main, cmd_check` |

**无竞品**：目前 PyPI/GitHub 上没有同类纯 Python 公文格式化工具（多为 Word 宏或在线服务）。

---

## 二、框架与架构（评分：B+）

### 2.1 整体分层

```
gongwen/                    ← CLI 入口层（argparse 分发）
├── __init__.py             ← 版本号 + re-export
├── __main__.py             ← `python -m gongwen` 入口
├── _legacy.py (2517行)    ← 所有 CLI 命令实现（单文件巨石）
├── cli/__init__.py         ← 空壳重导出（为未来拆分预留）
└── py.typed                ← PEP 561 类型标记

engine/                     ← 核心引擎层
├── core/
│   ├── document/           ← 文档模型（models/parser/generator/modifier/editor/...）
│   └── rules/              ← 规则体系（manager/loader/checker/fixer/engine）
├── config.py               ← 路径解析 + 临时目录管理
├── inject.py               ← 版头/版记/页码注入
├── optimizer.py            ← 优化器
├── template_builder.py     ← 模板生成
├── ... (20+ 模块)
└── utils/                  ← 工具函数（logger/parse/errors/zip_utils）

rules/official/             ← YAML 规则文件（25 个：_common + 24 文种）
dsh/index.js                ← DSH 插件桥接层（配置管理 + AI 指引）
etc/dsh-config-defaults.json← DSH 默认配置模板
prompts/                    ← LLM 提示词模板
tests/                      ← 测试套件（13 文件，164 用例）
```

### 2.2 架构优点

1. **三层规则合并**（official < custom < user）+ DSH 配置覆盖（v1.12.61+），优先级清晰
2. **DocumentModel 中间层**：parse_docx → DocumentModel → generate_docx，解耦了解析和生成
3. **CLI 与引擎分离**：`gongwen/` 负责命令分发，`engine/` 负责业务逻辑
4. **DSH 集成分层**：Python CLI（纯工具层）→ DSH 插件（配置管理者）→ AI Agent（调用者）
5. **零外部运行时依赖**：仅 python-docx + pydantic + pyyaml

### 2.3 架构问题

| 编号 | 优先级 | 问题 | 影响 |
|------|--------|------|------|
| ARCH-01 | P1 | `_legacy.py` 2517 行单文件巨石 | 难以维护，所有 CLI 命令挤在一个文件中 |
| ARCH-02 | P2 | `engine/` 模块扁平无包结构 | 20+ 模块直接散落在 `engine/` 下，无 `__init__.py` 包管理 |
| ARCH-03 | P2 | `sys.path.insert` hack（3 处） | `_legacy.py`、`live_edit.py`、`conftest.py` 均硬编码 engine/ 路径 |
| ARCH-04 | P2 | `skills/` 空目录残留 | 与 `.dsh/skills/` 并行，但内容为空（仅空子目录），可能误导 |
| ARCH-05 | P2 | `gongwen/cli/` 空壳包 | 仅 `from gongwen._legacy import main`，无实际拆分，但已被 packages.find 打包 |
| ARCH-06 | P2 | `engine/sessions/` 运行时数据残留 | 27 个 JSON 会话文件在开发目录中（已被 .gitignore 忽略，但物理存在） |
| ARCH-07 | P2 | `setup.py` 冗余 | `pyproject.toml` 已完全覆盖，`setup.py` 仅 `setup()` 空调用 |
| ARCH-08 | P1 | `inject.py` 硬编码 `Pt(33)` 行距（6 处） | 不读取 YAML 规则，与配置化设计矛盾 |

### 2.4 依赖关系图

```
gongwen/_legacy.py ──→ engine/core/rules/manager.py
                   ──→ engine/core/rules/engine.py
                   ──→ engine/core/document/parser.py
                   ──→ engine/core/document/generator.py
                   ──→ engine/core/document/modifier.py
                   ──→ engine/template_builder.py
                   ──→ engine/inject.py
                   ──→ engine/handoff.py
                   ──→ engine/fact_check.py（可选 LLM）
                   ──→ engine/auto_optimizer.py（可选 LLM）
                   ──→ engine/style_profile.py
                   ──→ engine/review_generator.py
                   ──→ engine/table_sign_*.py
```

`_legacy.py` 直接引用了 engine/ 下几乎所有模块——典型的"上帝模块"反模式。

---

## 三、代码质量（评分：B）

### 3.1 代码规模分布

| 文件 | 行数 | 评级 |
|------|------|------|
| `gongwen/_legacy.py` | 2517 | 🔴 超大（应拆分） |
| `engine/core/document/modifier.py` | 1354 | 🟡 偏大 |
| `engine/core/document/generator.py` | 963 | 🟡 偏大 |
| `engine/core/document/parser.py` | 705 | 🟢 可接受 |
| `engine/core/rules/checker.py` | 698 | 🟢 可接受 |
| `engine/optimizer.py` | 671 | 🟢 可接受 |
| `engine/core/document/tracked_annotator.py` | 669 | 🟢 可接受 |

### 3.2 代码规范

- **pycodestyle**：CI 配置 `--max-line-length=120`，v1.12.60 已修复 101 处违规，当前通过
- **PEP 561 类型标记**：`engine/py.typed` + `gongwen/py.typed` ✓
- **类型标注**：engine/ 下仅 1 个公共函数缺少返回类型标注（`clear_cache()`），覆盖率 99%+
- **编码**：全项目 UTF-8，Windows 兼容处理完善（`PYTHONIOENCODING` + `sys.stdout.reconfigure`）

### 3.3 异常处理

| 问题 | 数量 | 严重度 |
|------|------|--------|
| `except Exception: pass` 吞异常 | 20 处 | 🟡 |
| `except Exception` 总计 | 105 处 | — |
| `print()` 到 stdout（可能污染 --json） | 230 处 | 🟡 |

**重点吞异常位置**：
- `auto_optimizer.py:324` — LLM 调用失败静默忽略
- `docx_to_image.py` — 6 处全部吞异常（PDF 转图片容错）
- `handoff.py:157` — 交接文档读取失败静默
- `inject.py:66, 564` — 文件操作失败静默
- `generator.py:543, 1103` — 生成时属性设置失败静默
- `ai_structure_analyzer.py` — 3 处 JSON 解析失败静默

### 3.4 代码重复

| 重复模式 | 出现位置 | 说明 |
|----------|----------|------|
| `_parse_margin()` | `template_builder.py`、`_legacy.py:449` | `engine/utils/parse.py` 已有 `parse_mm()` 统一实现，但未被使用 |
| `_parse_size()` | `template_builder.py:365` | `engine/utils/parse.py` 已有 `parse_pt()` |
| `_parse_indent()` | `template_builder.py:371`、`modifier.py:1491` | `engine/utils/parse.py` 已有 `parse_indent()` |
| `load_rules_merged` 调用模式 | `_legacy.py` 6 处 | 每次都是 `from core.rules.manager import load_rules_merged; rules = load_rules_merged(doc_type)` |
| `Pt(33)` 硬编码 | `inject.py` 6 处 | 应从规则中读取 `body.line_spacing` |

### 3.5 死代码

| 项目 | 位置 | 说明 |
|------|------|------|
| `skills/` 空目录 | 项目根 | 仅 `skills/gongwen-skill/references/` 和 `scripts/` 空子目录 |
| `gongwen/cli/__init__.py` | 仅 re-export main | 无实际拆分内容，但被 packages.find 打包 |
| `setup.py` | 项目根 | `pyproject.toml` 已完全覆盖 |
| `dist/` 旧构建产物 | `gongwen_skill-1.12.60-py3-none-any.whl` | 旧版本构建产物残留 |
| `engine/sessions/` | 27 个 JSON | 开发时会话数据残留 |

---

## 四、功能完整性（评分：A-）

### 4.1 CLI 命令覆盖

| 命令 | 功能 | 测试覆盖 | --config-overrides |
|------|------|:--------:|:------------------:|
| `list-types` | 列出 24 类公文 | ✅ | — |
| `template` | 生成标准模板 | ✅ | ✅ v1.12.61 |
| `parse` | 解析为 JSON | ✅ | — |
| `check` | 格式检查 | ✅ | ✅ v1.12.61 |
| `optimize` | 检查+修复+生成 | ✅ | ✅ v1.12.61 |
| `generate` | JSON→docx | ✅ | — |
| `md2docx` | Markdown→docx | ✅ | ✅ v1.12.61 |
| `header/footer/pagenum` | 版式注入 | ✅ | — |
| `optimize-content` | 内容修订对比 | ✅ | — |
| `bold-first` | 首句加粗 | ✅ | — |
| `fix-common` | 常见格式修复 | ✅ | — |
| `handoff` | 会话交接 | ✅ | — |
| `rule-export/list/import` | 规则管理 | ✅ | — |
| `table-signs` | 桌签批量生成 | ✅ | — |
| `full-review` | 完整审校 | ✅ | — |
| `style-learn/list` | 样式学习 | ✅ | — |
| `check-update` | 多渠道版本自检 | ✅ | — |
| `audit` | 文档审计 | ✅ | — |
| `review` | 审稿流转单 | ✅ | — |
| `config` (DSH) | DSH 配置管理 | ✅ | DSH 侧处理 |

**共 20+ 命令**，功能覆盖完整。

### 4.2 规则体系

- **25 个 YAML 规则文件**：`_common.yaml` + 24 个文种
- **三层合并**：official → custom → user，`_deep_merge` + `_dedup_extend` 实现完善
- **29 条检查规则** + **23 条修复规则**（`_common.yaml`）
- **check_rules/fix_rules 列表去重**：按 `field` / `(target, action)` 去重，避免重复

### 4.3 DSH 集成

| 能力 | 状态 | 说明 |
|------|:----:|------|
| Skill 文件系统 | ✅ | `SKILL.md` × 3 副本（MD5 一致） |
| npm bundle | ✅ | `package.json` + `cordis.patch.yml` |
| CLI 桥接 | ✅ | `dsh/index.js` v1.12.61 配置感知 |
| 配置化 | ✅ v1.12.61 | `dsh-config.json` + `--config-overrides` |
| AI 工作指引 | ✅ v1.12.61 | `setup()` 注入 systemPrompt |
| PyPI 发布 | ✅ | `pip install gongwen-skill` |

### 4.4 测试覆盖

| 指标 | 数值 |
|------|------|
| 测试文件数 | 13 |
| 测试用例数 | 164 |
| 通过率 | 164/164 (100%) |
| 执行时间 | ~23s |
| 代码覆盖率 | 24%（门槛 20%） |

**覆盖率问题**：24% 总覆盖率偏低。主要原因是 `_legacy.py`（1637 行）仅 5% 覆盖率，拖累整体。engine/ 核心模块覆盖率分布不均：

| 模块 | 覆盖率 | 说明 |
|------|--------|------|
| `handoff.py` | 90% | ✅ 良好 |
| `table_sign_template.py` | 99% | ✅ 优秀 |
| `logger.py` | 95% | ✅ 良好 |
| `engine.py` | 86% | ✅ 良好 |
| `fixer.py` | 78% | 🟡 一般 |
| `table_sign_generator.py` | 74% | 🟡 一般 |
| `checker.py` | 67% | 🟡 一般 |
| `manager.py` | 67% | 🟡 一般 |
| `_legacy.py` | 5% | 🔴 差 |
| `inject.py` | 0% | 🔴 未测试 |
| `optimizer.py` | 0% | 🔴 未测试 |
| `fact_check.py` | 0% | 🔴 未测试 |
| `template_builder.py` | 0% | 🔴 未测试 |
| `docx_to_image.py` | 0% | 🔴 未测试 |
| `live_edit.py` | 0% | 🔴 未测试 |
| `style_profile.py` | 0% | 🔴 未测试 |

**13 个模块覆盖率为 0%**，这些模块有 3,000+ 行代码完全未测试。

---

## 五、逻辑正确性（评分：B+）

### 5.1 规则合并优先级

```
official YAML < custom YAML < user YAML < DSH config overrides < 命令行 --config-overrides
```

✅ 优先级链正确，`_deep_merge` + `apply_config_overrides` 实现完善。

### 5.2 配置覆盖链（v1.12.61 新增）

```
DSH dsh-config.json → dsh/index.js 注入 --config-overrides → Python CLI 解析 → RuleEngine.set_config_overrides() → load_rules 后合并
```

✅ 链路完整，但有一个边界问题：
- `inject.py` 中的 `Pt(33)` 硬编码不读取规则，配置覆盖对版头/版记/页码注入**无效**

### 5.3 缓存机制

`RuleEngine._rules_cache` + `_rules_mtime`：
- ✅ 基于文件 mtime 自动重载
- ✅ `set_config_overrides()` 正确清空缓存
- ⚠️ mtime 检查仅扫描 `RULES_DIR`（official），不检查 `CUSTOM_RULES_DIR` 和 `USER_RULES_DIR`

### 5.4 版本号一致性

| 位置 | 版本 |
|------|------|
| `pyproject.toml` | 1.12.61 ✓ |
| `gongwen/__init__.py` | 1.12.61 ✓ |
| `gongwen/_legacy.py` | 1.12.61 ✓ |
| `package.json` | 1.12.61 ✓ |
| `README.md` badge | 1.12.61 ✓ |

✅ 五处版本号一致。

### 5.5 SKILL.md 三副本一致性

✅ MD5 完全一致（F94DBBB9ACBCA3D0383DE1389549A272）。

---

## 六、安全与性能（评分：B+）

### 6.1 安全

| 检查项 | 状态 | 说明 |
|--------|:----:|------|
| 路径遍历防护 | ✅ | `manager.py` 中 `save_rule/delete_rule` 验证 key 仅含 `[a-zA-Z0-9_-]` |
| Shell 注入 | ✅ | `dsh/index.js` 使用 `spawn` 数组参数，无 `shell=True` |
| `eval/exec` | ✅ | 无使用 |
| 符号链接防护 | ✅ | `config.py` 拒绝 `GONGWEN_DATA_DIR` 符号链接 |
| API 密钥处理 | ✅ | 从环境变量读取，不硬编码 |
| `GONGWEN_DATA_DIR` 空值检查 | ✅ | 防止空字符串路径 |
| 临时文件清理 | ✅ | `atexit.register(_cleanup_tmp_dir)` |
| `inject.py` 文件操作 | 🟡 | 使用 `tempfile.mkstemp` + 重试机制，但 `except Exception: pass` 吞异常 |

**安全风险**：低。无 SQL 注入、无 XSS、无命令注入风险。API 密钥通过环境变量管理。

### 6.2 性能

| 指标 | 状态 | 说明 |
|------|:----:|------|
| 规则缓存 | ✅ | `_rules_cache` 按类型缓存 |
| check-update 串行查询 | 🟡 | PyPI ~2s + 3×git ~15s，最差 45s |
| 大文件处理 | 🟡 | `generator.py` 逐段落处理，无流式写入 |
| 内存使用 | ✅ | DocumentModel 为内存中间结构，适合典型公文（<100 页） |

---

## 七、文档与发布（评分：B+）

### 7.1 文档质量

| 文档 | 状态 | 说明 |
|------|:----:|------|
| README.md | ✅ | 安装/使用/DSH 集成/配置化/适用场景完整 |
| SKILL.md | ✅ | 三副本一致，YAML frontmatter 规范 |
| CHANGELOG.md | ✅ | v1.12.60+ 条目完整 |
| AUDIT_REPORT.md | ✅ | v1.12.58 P8 审计报告 |
| prompts/ | ✅ | LLM 提示词模板 |
| etc/dsh-config-defaults.json | ✅ | v1.12.61 默认配置模板 |

### 7.2 CI/CD

| 检查项 | 状态 |
|--------|:----:|
| CI 触发分支 = master | ✅ v1.12.58 修复 |
| Python 矩阵 3.10-3.14 | ✅ |
| pytest + coverage 门槛 20% | ✅ |
| pycodestyle lint | ✅ |
| PyPI 自动发布（tag 触发） | ✅ |
| PyPI token 模式 | ✅（OIDC 待配置） |

### 7.3 发布问题

| 编号 | 优先级 | 问题 | 影响 |
|------|--------|------|------|
| REL-01 | P1 | `etc/` 未在 `pyproject.toml` 的 `package-data` 中声明 | `pip install gongwen-skill` 后 `etc/dsh-config-defaults.json` 不存在 |
| REL-02 | P2 | `pyproject.toml` Changelog URL 指向 `main` 分支 | 实际主分支是 `master`，URL 404 |
| REL-03 | P2 | `MANIFEST.in` 未包含 `etc/` | sdist 不含默认配置 |
| REL-04 | P2 | `dist/` 残留旧版本构建产物 | v1.12.60 的 .whl 和 .tar.gz |
| REL-05 | P2 | CHANGELOG.md 未更新 v1.12.61 条目 | 版本变更记录断档 |

---

## 八、综合评分与优先级清单

### 8.1 维度评分汇总

| 维度 | 评分 | 说明 |
|------|:----:|------|
| 立项与定位 | A | 垂直领域精准，无竞品，三渠道发布 |
| 框架与架构 | B+ | 三层规则 + DocumentModel + DSH 分层设计良好，但 _legacy.py 巨石 |
| 代码质量 | B | 类型标注完善，但吞异常多、代码重复、死代码残留 |
| 功能完整性 | A- | 20+ 命令覆盖完整，DSH 集成完善，但测试覆盖偏低 |
| 逻辑正确性 | B+ | 规则合并/配置链/缓存机制正确，但 inject.py 硬编码矛盾 |
| 安全与性能 | B+ | 安全风险低，性能可接受 |
| 文档与发布 | B+ | 文档完善，CI/CD 健全，但打包配置有遗漏 |

**总评：B+（82/100）**

### 8.2 优先级清单

#### P0（致命/阻断性）

无。当前版本无致命问题。

#### P1（应修复）

| 编号 | 问题 | 文件 | 修复建议 |
|------|------|------|----------|
| P1-1 | `_legacy.py` 2517 行巨石拆分 | `gongwen/_legacy.py` | 拆分为 `gongwen/cli/{format,content,generate,layout,utils,update}.py`（已预留 `gongwen/cli/`） |
| P1-2 | `inject.py` 硬编码 `Pt(33)` 不读规则 | `engine/inject.py` | 改为从 `load_rules_merged` 读取 `body.line_spacing` |
| P1-3 | `etc/` 未在 pyproject.toml package-data 声明 | `pyproject.toml` | 添加 `etc = ["*.json"]` 到 `[tool.setuptools.package-data]` |
| P1-4 | 13 个模块 0% 测试覆盖 | `inject.py`、`optimizer.py`、`fact_check.py` 等 | 优先补 `inject.py` 和 `template_builder.py` 的 E2E 测试 |

#### P2（建议修复）

| 编号 | 问题 | 修复建议 |
|------|------|----------|
| P2-1 | `except Exception: pass` 吞异常 20 处 | 逐个改为 `logger.warning` + 降级路径 |
| P2-2 | `_parse_margin/size/indent` 重复实现 | 统一使用 `engine/utils/parse.py` |
| P2-3 | `skills/` 空目录残留 | 删除或 .gitignore |
| P2-4 | `setup.py` 冗余 | 删除，pyproject.toml 已覆盖 |
| P2-5 | `dist/` 旧构建产物 | 清理 + .gitignore 已覆盖 |
| P2-6 | `engine/sessions/` 27 个残留文件 | 清理（.gitignore 已忽略） |
| P2-7 | `pyproject.toml` Changelog URL `main` → `master` | 修正 URL |
| P2-8 | `MANIFEST.in` 未包含 `etc/` | 添加 `recursive-include etc/ *.json` |
| P2-9 | CHANGELOG.md 未更新 v1.12.61 | 补充变更记录 |
| P2-10 | `RuleEngine._rules_mtime` 不检查 custom/user 目录 | 扩展 mtime 扫描范围 |
| P2-11 | `gongwen/cli/` 空壳包 | P1-1 拆分时填充，或暂时从 packages.find 移除 |
| P2-12 | `engine/` 无 `__init__.py` 包管理 | 补充 `__init__.py` 或改用 `pyproject.toml` 显式声明 |

---

## 九、与历次审计的继承关系

| 审计 | 版本 | 评分 | 修复状态 |
|------|------|------|----------|
| P8 全量审计 | v1.12.58 | 76.5/100 (B+) | P0 全修复，P1/P2 大部分修复 |
| v1.12.59 优化方案 | v1.12.59 | — | 5 项全部修复 |
| **v1.12.61 全量审计** | **v1.12.61** | **82/100 (B+)** | 0 P0，4 P1，12 P2 |

**趋势**：从 76.5 → 82 分，提升 5.5 分。主要提升来自 DSH 配置化、CI/CD 完善、测试补强（99→164）。

---

## 十、后续路线建议

### 短期（v1.12.62）
1. 修复 P1-3（`etc/` 打包）+ P2-7（Changelog URL）+ P2-9（CHANGELOG 补充）
2. 清理 P2-3/4/5/6（死代码/残留文件）
3. 补 `inject.py` E2E 测试（P1-4 部分）

### 中期（v1.12.63-65）
4. 拆分 `_legacy.py`（P1-1）—— 这是技术债的最大来源
5. `inject.py` 规则化（P1-2）
6. 补 `template_builder.py`、`optimizer.py` 测试

### 长期（v1.13.0）
7. `engine/` 包结构重构（ARCH-02）
8. 消除 `sys.path.insert` hack（ARCH-03）
9. 统一解析函数（P2-2）
10. 测试覆盖率目标 50%+

---

> AI生成
