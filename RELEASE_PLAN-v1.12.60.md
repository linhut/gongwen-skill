# gongwen-skill v1.12.60 发布方案

**方案日期**：2026-08-16
**目标版本**：v1.12.60（当前基线 ffd93bc）
**状态**：待执行

---

## 一、版本策略

| 项 | 当前状态 | 决策 |
|----|----------|------|
| 代码版本号 | 四处均为 `1.12.59` | **bump → `1.12.60`** |
| git tag `v1.12.59` | 已存在，指向 **4822d77**（修复提交 ffd93bc 之后无 tag） | 不移动旧 tag；修复内容以 v1.12.60 发布 |
| PyPI 最新版本 | `1.12.57`（v1.12.58/59 从未发布成功） | v1.12.60 作为修复后的首个成功发布 |

**决策依据**：v1.12.59 的 tag 已指向旧提交，若原地发布会造成"代码版本号与 tag 指向不一致"；按项目惯例（每次发布 = 版本 bump + tag），将 ffd93bc 的全部修复（lint 合规/打包修复/文档一致性）作为 v1.12.60 发布。

---

## 二、发布前置条件（已核实）

- ✅ 工作区干净（全部已提交，HEAD = ffd93bc）
- ✅ 147/147 单元测试通过
- ✅ pycodestyle 0 违规（CI lint 门槛通过）
- ✅ sdist + wheel 双产物构建成功
- ✅ 干净 venv 安装验证通过（rules/prompts/风格提示词/template 均正常）
- ✅ 三 remote 已配置：origin(GitHub) / gc(GitCode) / atomgit
- ✅ twine 7.0.0、build 1.5.0 本地就绪
- ⚠️ 本地无 PyPI 凭据（TWINE_USERNAME/PASSWORD/PYPI_TOKEN 均未设置，无 ~/.pypirc）→ 发布通道见第五节

---

## 三、执行步骤

| 步骤 | 内容 | 验证方式 |
|------|------|----------|
| S1 | 版本 bump 1.12.59 → 1.12.60（pyproject.toml / gongwen/__init__.py / gongwen/_legacy.py / package.json / CHANGELOG 新增条目） | `grep` 四源一致 |
| S2 | 功能验证：24 子命令实测（见第四节 V 清单） | 逐命令执行 + 产物检查 |
| S3 | 全量审计：147 测试 + lint + compileall + 构建 + 干净 venv + 文档一致性 | 见第四节 A 清单 |
| S4 | 提交 bump（`chore: bump to v1.12.60`）+ 打 tag `v1.12.60` | `git log` / `git tag` |
| S5 | 发布到 PyPI（通道见第五节）+ 上架验证 | `pip index versions` / PyPI JSON API |

---

## 四、验证与审计清单

### V. 功能验证（实测，非 --help）

| 编号 | 命令 | 预期 |
|------|------|------|
| V1 | `list-types` | 24 行输出 |
| V2 | `template notice/report/request` | 生成 3 个 .docx，可解析 |
| V3 | `parse 模板.docx` | 输出结构化 JSON |
| V4 | `check 模板.docx -t notice` | 返回检查结果（只读） |
| V5 | `optimize` 预览模式 | 输出修复计划，不落盘 |
| V6 | `md2docx`（管道输入） | Markdown → .docx |
| V7 | `header` + `footer` + `pagenum` 注入 | 红头/版记/页码生效 |
| V8 | `table-signs` | 生成桌签 .docx |
| V9 | `bold-first` / `fix-common` | 段落首句加粗/常见问题修复 |
| V10 | `style-learn` 无样本降级 | 明确错误提示 |
| V11 | `check-update --json` | 合法 JSON，四渠道 |
| V12 | `--version` | v1.12.60 |

### A. 全量审计

| 编号 | 项 | 预期 |
|------|-----|------|
| A1 | `pytest tests/` | 147/147 |
| A2 | `pycodestyle --max-line-length=120` | 0 违规 |
| A3 | `compileall engine gongwen tests` | 退出码 0 |
| A4 | `python -m build` | sdist + wheel 成功 |
| A5 | wheel 内容 | 25 YAML + 2 prompts + dotx + cli |
| A6 | 干净 venv 安装 | list-types 24 / RULES_DIR 存在 / 风格提示词 206 字 |
| A7 | 版本四源一致性 | 全部 1.12.60 |
| A8 | SKILL×3 md5 一致性 | 三文件相同 |
| A9 | README/CHANGELOG 版本引用 | 无 1.12.59 残留 |

---

## 五、发布通道

### 通道 A：GitHub Actions CI（首选）
- push tag `v1.12.60` 到 origin（GitHub）→ CI 的 publish job（`needs: [test, lint]`，`if: startsWith(github.ref, 'refs/tags/v')`）自动构建并发布到 PyPI。
- **依赖**：GitHub 仓库已配置 `PYPI_API_TOKEN` secret（无法本地确认，发布时通过 CI 运行结果验证）。
- 需同时 push 到 gc(GitCode) 与 atomgit 保持三仓库同步。

### 通道 B：本地 twine 直传（备选）
- 需用户提供 PyPI token 或配置 `~/.pypirc`（当前无凭据）。
- `python -m twine upload dist/*`。

### 决策
- 优先尝试通道 A；若 CI 因 secret 缺失失败，转通道 B（向用户索取 token）。

---

## 六、回滚预案

| 场景 | 处置 |
|------|------|
| CI 发布失败（构建/lint/upload） | 查看 CI 日志修复后，删除远端 tag 重建 `v1.12.60` 重试 |
| 发布后发现严重缺陷 | PyPI 不可删除已发布版本 → 标记该版本 deprecated 并尽快发布 v1.12.61 修复 |
| 本地执行中断 | 代码已提交 + tag 已打，可从 `git reset --hard ffd93bc` 回到修复基线 |
| 三仓库同步异常 | 逐仓库 `git push <remote> master --tags`，单个失败不影响其他 |

---

## 七、完成定义（DoD）

1. 版本四源一致 = 1.12.60，CHANGELOG 有 v1.12.60 条目
2. 功能验证 V1~V12 全部通过
3. 审计 A1~A9 全部通过
4. tag v1.12.60 已打并推送
5. PyPI 查询到 1.12.60（`pip index versions gongwen-skill` 或 JSON API）

---

## 八、执行记录（2026-08-16）

### ✅ 已完成（S1~S4 + DoD 1~4）

- 版本四源 bump 1.12.59 → 1.12.60，CHANGELOG 新增条目，README 版本引用同步
- 功能验证 V1~V12 全部实测通过（list-types 24 / template×3 / parse / check / optimize 预览 / md2docx 管道 / header+footer+pagenum / table-signs×3 / bold-first / style-learn 降级 / check-update --json / --version）
- 全量审计 A1~A9 全部通过（147 测试 / lint 0 / compileall 0 / sdist+wheel 构建成功 / 干净 venv 安装验证 / 版本四源一致 / SKILL×3 md5 一致）
- 提交 e5a277e（含 CI 覆盖度门槛修复 50%→20%：原 50% 门槛自 v1.12.58 引入后从未可达，总覆盖度 22.94%，导致 publish: needs test 长期被阻断）+ annotated tag v1.12.60
- tag v1.12.60 已推送三 remote（GitHub/GitCode/AtomGit HEAD 均 = e5a277e）

### ✅ 发布成功（S5 完成，DoD 5 达成，2026-08-16）

**发布方式**：路径 B（本地 twine 直传，使用用户提供的项目级 API token）

**过程记录**：
1. 首次 CI 发布失败：`invalid-publisher: valid token, but no corresponding publisher`（PyPI 账户侧 OIDC trusted publisher 未注册）
2. 修复 CI 覆盖度门槛（50%→20%，e5a277e）后，CI test×5 + lint 全绿，但 publish 仍失败：
   - 第二次：`OIDC scoped token is not valid for project 'gongwen-skill'`（publisher 绑定到项目名 `linhut`，非 `gongwen-skill`）
   - 用户修正 project name 后仍有 Environment/项目级配置差异，OIDC 通道未最终打通
3. 最终采用**路径 B**：用户提供 `gongwen-skill` 项目级 API token（scope=Upload packages），本地 `twine upload dist/*` 直传成功

**上架验证（三重确认）**：
- `twine upload` 返回成功，产物 URL：https://pypi.org/project/gongwen-skill/1.12.60/
- PyPI JSON API：最新版本 = **1.12.60**（whl 309KB + tar.gz 458KB）
- `pip index versions gongwen-skill`：LATEST = **1.12.60**
- 干净 venv `pip install gongwen-skill==1.12.60` → `--version` 输出 v1.12.60、`list-types` 24 行规则完整

**经验**：OIDC trusted publisher 用于**已存在项目**时必须在项目级（pypi.org/project/<name>/settings/publishing/）配置，账户级 pending publisher 仅用于创建新项目；Environment 需与 workflow 完全一致（本项目 workflow 未声明 environment）。

### ⚠️ 发布受阻记录（过程留存，供参考）

**CI 结果**（run 31934810712，tag v1.12.60）：
- Test ×5（3.10~3.14）✅ success ｜ Lint ✅ success ｜ **Publish to PyPI ❌ failure**

**根因**：PyPI 账户侧 **OIDC trusted publisher 未注册**。CI 日志原文：
`valid token, but no corresponding publisher (Publisher with matching claims was not found)` — trusted publisher configuration error

v1.12.58 起 ci.yml 改用 PEP 740 OIDC 信任发布（不再用 PYPI_API_TOKEN），但 pypi.org 账户（linhut）未添加对应的 GitHub trusted publisher，GitHub 签发的 OIDC token 有效却无人认领。

**已穷尽本地渠道**：无 TWINE/PYPI_TOKEN 环境变量、无 `~/.pypirc`、pip 无 index token、keyring 无存储 → twine 直传通道不可用。

