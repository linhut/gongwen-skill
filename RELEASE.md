<!--
  (c) 2026 Jose AI (https://www.linhut.cn)
  https://github.com/linhut/gongwen-skill
  Licensed under the MIT License. See the LICENSE file for details.
-->

# gongwen-skill 发布流程（Release Process）

本文档定义 gongwen-skill 的**版本规范、发布流程与验证清单**。所有发布操作遵循本流程，保证版本可追溯、构建可复现、发布可验证。

> 本流程基于 gongwen-skill 自身实际（Python 包 + PyPI 发布 + 三仓库镜像 + DSH 技能），与 dsh-manager（Electron 桌面应用 + GitHub Release）不同，请勿照搬其他项目流程。

---

## 1. 版本规范

项目当前使用 `2.1.x` 序列（**v2.0.0 大版本重置**：从 1.12.x 序列迁移至 2.x，采用标准 SemVer）：

| 段 | 含义 | 示例 |
|----|------|------|
| `MAJOR` | 重大重构 / 架构变更（不向后兼容） | `1.12.74` → `2.0.0` |
| `MINOR` | 功能迭代 / 拆分 / 修复（向后兼容） | `2.6.0` → `2.7.0` |
| `PATCH` | 紧急缺陷修复 | `2.6.0` → `2.6.1` |

**规则**：
- 每次常规发布 `MINOR+1`（当前节奏：功能/修复/拆分均走 `2.x+1`）
- **禁止重复使用同一版本号**；已发布到 PyPI 的版本不可覆盖
- **版本重置说明**：v2.0.0 从 1.12.74 迁移到 2.x 序列，作为新的大版本起点；1.12.x 历史版本仍可通过 PyPI 安装（pip 会优先选择最高版本，PyPI 上 1.12.74 仍存在，2.x 与 1.12.x 按 SemVer 排序互不冲突）
- 版本号需在 **4 处代码位置 + CHANGELOG** 保持一致（见 §3）
- 预发布后缀（`rc`/`dev`）不用于正式发布，仅内部验证

---

## 2. 发布流程（标准操作）

```text
1. 确认代码就绪（功能完成、本地检查通过）
   - ⚠️ 清理非必要文件：临时/调试脚本（tmp_*、_gw_* 等）不提交、不入库、不同步三仓库
2. 同步测试与运行（tests/ 为本地策略，见 §6）
3. 更新版本号（4 处代码 + CHANGELOG，见 §3）
4. 提交（chore: bump version to X.Y.Z）
5. 打注解 tag（git tag -a vX.Y.Z）
6. 推送 master + tag 到三 remote（触发 CI 自动发布）
7. CI 自动创建 GitHub Release（编号 = tag，见 §5.1 release job）
8. 同步 GitCode/AtomGit Release（编号与 tag 统一，见 §6.1）
9. 验证发布（PyPI / pip / 干净 venv，见 §5）
```

### 2.1 详细步骤

```bash
# ① 确认工作区干净
git status

# ② 本地验证（tests/ 仅本地存在）
python -m pytest tests/ -q --no-header
python -m pycodestyle --max-line-length=120 --exclude=__pycache__,.git,dist,build .

# ③ 更新版本号（4 处代码 + CHANGELOG，见 §3）

# ④ 提交版本更新
git add pyproject.toml gongwen/__init__.py gongwen/_legacy.py package.json CHANGELOG.md README.md
git commit -m "chore: bump version to 2.1.X"

# ⑤ 打注解 tag
git tag -a v2.1.X -m "v2.1.X - 发布说明摘要"

# ⑥ 推送（触发 CI 自动发布）
git push origin master --tags
git push gc master --tags
git push atomgit master --tags

# ⑦ 验证发布（见 §5）
```

---

## 3. 版本号更新点（9 处代码 + 文档，doctor 仅检查前 4 项）

| # | 文件 | 位置 | 类型 |
|---|------|------|------|
| 1 | `pyproject.toml` | `version = "2.1.X"`（`[project]`） | 代码版本 |
| 2 | `gongwen/__init__.py` | `__version__ = "2.1.X"` | 代码版本 |
| 3 | `gongwen/_legacy.py` | `__version__ = "2.1.X"`（须与 #2 同步） | 代码版本 |
| 4 | `package.json` | `"version": "2.1.X"` | 代码版本 |
| 5 | `CHANGELOG.md` | 顶部新增 `## v2.1.X (YYYY-MM-DD)` 条目 | 文档 |
| 6 | `README.md` | PyPI 徽章（已自动：`https://img.shields.io/pypi/v/gongwen-skill`）/ 版本示例 / `--version` 示例 | 文档 |
| 7 | `prompts/usage-prompts.md` | `Skill 版本: v2.1.X` | 文档 |
| 8 | `dsh/index.js` | 注释 `v2.1.X+`（运行时版本从 pyproject.toml 动态读取） | 文档 |
| 9 | `RELEASE.md` | 本文档中的版本示例和验证命令 | 文档 |

**⚠️ 历史教训**：曾出现 `pyproject.toml`/`package.json` 为 1.12.71 而 `__init__.py`/`_legacy.py` 停留在 1.12.69 的版本漂移，导致 `check-update` 比对错误。发布前必须逐项核对全部位置。

**快速核对命令（4 处代码版本）**：

```bash
grep -h "2\.0\.X" pyproject.toml gongwen/__init__.py gongwen/_legacy.py package.json | grep -oP "2\.0\.\d+" | sort | uniq -c
# 期望输出：4 行全部为同一版本号
```

**完整核对命令（9 处全部）**：

```bash
# 在发布前检查所有含版本号的文件
echo "=== 代码版本 ==="
grep -h "2\.0\.\(0\|1\)" pyproject.toml gongwen/__init__.py gongwen/_legacy.py package.json
echo "=== 文档版本查看（手动确认） ==="
grep -n "v2\.0\.\(0\|1\)" README.md prompts/usage-prompts.md dsh/index.js
```

**pre-commit hook 自动检查**：已配置 `.githooks/pre-commit`，提交前自动检查 4 处代码版本号一致性，不一致时提示并阻止提交。

> **提示**：README.md 的 PyPI 徽章已改为动态版本号（`https://img.shields.io/pypi/v/gongwen-skill`），自动显示 PyPI 最新版本，无需手动更新。但其他文档中的版本示例文字仍需手动同步。

---

## 4. 发布前检查清单

- [ ] `git status` 干净（无未提交改动）
- [ ] 本地测试通过：`python -m pytest tests/ -q --no-header`（tests/ 为本地目录，CI 会自动跳过缺失）
- [ ] pycodestyle 0 违规：`python -m pycodestyle --max-line-length=120 --exclude=__pycache__,.git,dist,build .`
- [ ] 4 处代码版本号一致且已递增（§3 快速核对命令）
- [ ] 文档版本号同步：README.md / prompts/usage-prompts.md / dsh/index.js（§3 完整核对命令）
- [ ] CHANGELOG 顶部已有新版本条目
- [ ] `python -m build` 本地构建成功（sdist + wheel）
- [ ] `python -m gongwen --version` 输出目标版本
- [ ] 关键命令冒烟：`list-types`（24 行）、`check-update --json`（合法 JSON）
- [ ] 全面自检通过：`python -m gongwen doctor`（20/21 OK，仅 Git 工作区因未提交文件而 FAIL 为预期）

---

## 5. 发布与验证

### 5.1 发布方式（CI 自动，首选）

推送 `v*` tag 后，[`.github/workflows/ci.yml`](.github/workflows/ci.yml) 自动执行：

| Job | 内容 | 门槛 |
|-----|------|------|
| test | Python 3.10~3.14 矩阵 + 覆盖率 | `--cov-fail-under=20`（tests/ 缺失时跳过） |
| lint | pycodestyle | 0 违规 |
| publish | `python -m build` + gh-action-pypi-publish | 仅 tag `v*` 触发；凭据 `secrets.PYPI_API_TOKEN`（token 模式） |
| publish-npm | `npm publish --access public`（DSH 插件包） | 仅 tag `v*` 触发；凭据 `secrets.NPM_TOKEN` |
| release | 创建 GitHub Release（编号 = tag，`softprops/action-gh-release`） | 仅 tag `v*` 触发；`generate_release_notes: true` |

> **📢 npm 发布现状（2026-08-20）**：npm 通道已启用，`NPM_TOKEN` secret 已配置。`publish-npm` job 自动将 DSH 插件包发布到 npmjs.com（包名 `gongwen-skill`）和 GitHub Packages（`@linhut/gongwen-skill`，仓库命名空间）。

### 5.2 npm 发布（DSH 插件包，可选）

CI 通过 `publish-npm` job 将 DSH 桥接包发布到 npm（包名 `gongwen-skill`，版本取自 `package.json`，与 PyPI 同步递增）。

**启用前置条件**：

1. 在 [npmjs.com](https://www.npmjs.com/settings/linhut/tokens) 生成 **Automation token**（`npm profile create-token --read-only=false`）
2. 将 token 添加到 GitHub 仓库 Secrets：**Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NPM_TOKEN`
   - Value: 粘贴生成的 token
3. 确认 npm 包名 `gongwen-skill` 未被他人占用

**注意**：npm 与 PyPI 版本号**同源同步**（均来自 `package.json` / `pyproject.toml`，见 §3 版本核对）。

### 5.3 发布方式（本地兜底，CI 不可用）

```bash
# 需已配置 PyPI 凭据（TWINE_USERNAME=__token__ + TWINE_PASSWORD，或 ~/.pypirc）
python -m build
python -m twine upload dist/*.whl dist/*.tar.gz
```

### 5.4 发布后验证（三重确认）

```bash
# ① PyPI JSON API
curl -s https://pypi.org/pypi/gongwen-skill/json | python -c "import sys,json;print(json.load(sys.stdin)['info']['version'])"
# 期望：2.1.X

# ② pip index（权威渠道）
pip index versions gongwen-skill
# 期望：LATEST = 2.1.X

# ③ 干净 venv 安装验证
python -m venv /tmp/verify && /tmp/verify/Scripts/pip install gongwen-skill==2.1.X
/tmp/verify/Scripts/python -m gongwen --version   # 期望 v2.1.X
/tmp/verify/Scripts/python -m gongwen list-types  # 期望 24 行（规则完整）
```

---

## 6. 仓库同步与测试策略

### 6.1 三仓库镜像

| remote | 平台 | 用途 |
|--------|------|------|
| `origin` | GitHub | **唯一触发 CI 发布**的仓库，`check-update` 备用判定渠道（PyPI 为权威） |
| `gc` | GitCode | 代码镜像 + GitHub 不可达时的国内拉取镜像（`check-update` mirrors 提示） |
| `atomgit` | AtomGit | 代码镜像 + GitHub 不可达时的国内拉取镜像（`check-update` mirrors 提示） |

**原则：非必要的代码和文件不进行仓库同步。** 每次发布前清理临时/调试残留（tmp_*、_gw_*、本地验证脚本等），仅提交并同步必要文件（核心代码、版本号 4 处、CHANGELOG/README/RELEASE、CI 配置等）。.gitignore 已覆盖 tmp_* 等模式；已跟踪的残留文件须 git rm 移除后再提交。

每次发布后执行：

```bash
for r in origin gc atomgit; do git push $r master --tags; done
git ls-remote $r HEAD  # 核对三仓库 HEAD 一致
```

**Release 统一编号**：三平台 Release 编号必须与 tag 一致（如 v2.6.0），不得出现 GitHub 停在旧版、其他平台新的错位：
- GitHub：CI 的 release job 自动创建（编号 = tag）
- GitCode：经 API POST /api/v5/repos/linhut/gongwen-skill/releases 创建/核对（token 从 git remote get-url gc 提取）
- AtomGit：与 GitCode 同源（Gitee 风格 API），核对/创建用 `GET/POST https://atomgit.com/api/v5/repos/linhut/gongwen-skill/releases`，认证头 `Authorization: Bearer <token>`（token 从 git remote get-url atomgit 提取 oauth2 段）；POST 参数 form 编码（tag_name/name/body/target_commitish）

发布后核对三平台 Release 均含最新 vX.Y.Z，GitHub 标记为 Latest。

### 6.2 tests/ 本地策略（重要）

- **tests/ 目录不随仓库发布**（release policy：保持仓库精简，测试仅本地维护）
- 本地开发/发布前必须本地跑测试；CI 检测 `tests/**` 缺失时自动跳过 test job（见 ci.yml "Skip notice" 步骤）
- 若需在 CI 跑测试，需先将 tests/ 推入仓库（破坏精简策略，需评审）

### 6.3 分支策略

- **主分支**：`master`（非 `main`）
- 日常开发直接推送 `master`，或从功能分支 PR 合并
- tag 触发（`v*`）自动走 CI 发布流程
- 无独立 `develop` / `release` 分支

### 6.4 DSH 技能与 npm 分发

- 项目同时作为 **DSH Skill** 分发（`.dsh/skills/gongwen-skill/` 目录技能 + `.dsh/skills/gongwen-skill.md` 单文件技能 + `dsh/index.js` 桥接），DSH 分发跟随 git 仓库（克隆即用）
- **npm 发布**：ci.yml 已配置 `publish-npm` job（包名 `gongwen-skill`，`dsh/index.js` + `cordis.patch.yml` 打包），推送 `v*` tag 时自动发布到 npmjs.com 和 GitHub Packages 两个通道
  - ⚠️ GitHub Packages 通道要求（2026-09-03 v2.7.0 踩坑）：job 必须声明 `permissions: packages: write`（GITHUB_TOKEN 默认无此权限），且发布步骤需单独为 `npm.pkg.github.com` 写 `_authToken` 到 .npmrc（setup-node 只配置了 npmjs registry 的认证）——两者缺失分别报 403 与 ENEEDAUTH
  - ⚠️ **GitHub Packages 通道现状（2026-09-03 v2.8.0 实测）**：上述 403/ENEEDAUTH 已修复，但 `npm publish --registry=https://npm.pkg.github.com` 仍报 `E404 PUT https://npm.pkg.github.com/gongwen-skill`——根因是 GitHub Packages registry 中**从未创建过非 scoped 包 `gongwen-skill`**（GITHUB_TOKEN 无法自动创建首包）。处置：先在 GitHub 网页端 Packages 页手动创建一次该包（或改用 scoped 命名 `@linhut/gongwen-skill`），下个版本验证；该通道失败不阻断发布（npmjs 通道正常）
- 版本号同步：SKILL.md frontmatter、`package.json`、PyPI 三处保持一致（§3 核对）

### 6.5 版本号自动检查（pre-commit hook）

- 已配置 pre-commit hook（`.githooks/pre-commit`），每次提交前自动检查 4 处代码版本号一致性
- 不一致时输出详细差异信息并阻止提交（可使用 `git commit --no-verify` 跳过）
- 检查内容：
  - `pyproject.toml`、`gongwen/__init__.py`、`gongwen/_legacy.py`、`package.json` 版本号是否一致
  - 不一致时显示各文件实际版本号

### 6.6 codegraph 索引

- 项目使用 [codegraph](https://github.com/linhut/codegraph) 维护代码索引，供 AI 工具查询
- 已配置 post-commit hook（`.githooks/post-commit`，`git config core.hooksPath .githooks`），每次 commit 自动增量同步 `codegraph sync --quiet`
- 发布前可手动执行 `codegraph sync --quiet` 确保索引最新（非发布阻断项）

---

## 7. CHANGELOG 格式规范

每次发布前在 `CHANGELOG.md` **顶部**新增条目：

```markdown
## v2.1.X (YYYY-MM-DD)

### Added
- 新功能描述

### Changed
- 变更/重构描述

### Fixed
- 缺陷修复描述

### Removed
- 移除内容描述
```

**规则**：
- 日期格式 `YYYY-MM-DD`
- 按 `Added` / `Changed` / `Fixed` / `Removed` 分类（无对应内容则省略该分类）
- 每个变更点一行，必要时附注引用的 Issue / PR 编号
- 历史版本条目不可修改（保留可追溯性）

---

## 8. 常见问题与回滚

| 问题 | 处理 |
|------|------|
| CI publish 失败（403 token） | 检查 `secrets.PYPI_API_TOKEN` 是否有效（PyPI 可重新生成同名 secret）；确认 tag 分支为 `v*` |
| CI publish-npm 失败 | 先看失败步骤：npmjs 通道失败 → 检查 `secrets.NPM_TOKEN`（npmjs Automation token）；GitHub Packages 通道失败 → 检查 job 是否声明 `permissions: packages: write` 且发布步骤已写 `_authToken` 到 .npmrc（见 §6.4）；404 则确认包名 `gongwen-skill` 已在对应 registry 注册 |
| CI test job 被跳过 | 属预期（tests/ 本地策略）；确保发布前本地测试已过 |
| 版本漂移（4 处不一致） | 用 §3 核对命令定位，逐文件修正后重新提交 |
| 发布后发现严重缺陷 | **PyPI 不可删除已发布版本** → 在 PyPI 标记该版本 deprecated（`pip index` 会提示），并尽快发布 `X+1` 修复版 |
| tag 推错 | 本地 `git tag -d vX.Y.Z` + 远端 `git push <remote> :refs/tags/vX.Y.Z` 删除，修正后重新打 tag |
| 本地 twine 401 | 确认 TWINE_USERNAME=`__token__`、TWINE_PASSWORD 为 PyPI API token |
| 三仓库 HEAD 不一致 | 逐仓库 `git push <remote> master --tags` 重推；单个失败不影响其他 |
| npm 与 PyPI 版本号不一致 | 检查 `package.json` 与 `pyproject.toml`（§3 核对命令）是否同源同步 |

---

## 9. 发布检查总表（DoD）

1. ✅ 4 处代码版本号一致且已递增，文档版本号已同步，CHANGELOG 有对应条目
2. ✅ 本地测试通过（tests/ 存在时）+ pycodestyle 0 违规
3. ✅ tag `v2.1.X` 已打并推送三 remote，三仓库 HEAD 一致
4. ✅ CI（test/lint/publish）全绿，或本地 twine 直传成功
5. ✅ PyPI 查询到 `2.1.X`（JSON API + `pip index` 双确认）
6. ✅ 干净 venv 安装后 `--version` 与 `list-types` 正常
7. ⬜ npm 发布（可选）：`NPM_TOKEN` 已配置时，`npm view gongwen-skill versions` 确认新版本（当前未启用则跳过）
