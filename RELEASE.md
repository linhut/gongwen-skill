# 发布流程（Release Process）

本文档定义 **gongwen-skill** 的版本规范、发布流程与构建流程。所有发布操作遵循本流程，保证 Release 整洁、版本可追溯、构建可复现。

## 1. 版本规范（SemVer）

遵循 [语义化版本 2.0.0](https://semver.org/)：

| 版本段 | 含义 | 示例 |
|--------|------|------|
| `MAJOR` | 不兼容的重大变更 / 正式里程碑 | `1.0.0` |
| `MINOR` | 向后兼容的新功能 | `1.1.0` |
| `PATCH` | 向后兼容的缺陷修复 | `1.1.1` |
| 预发布后缀 | 测试版（不用于正式 Release） | `1.2.0-rc.1` |

**规则**：
- 新增功能 → `MINOR+1`（如 `1.0.0` → `1.1.0`）
- 缺陷修复 → `PATCH+1`（如 `1.1.0` → `1.1.1`）
- 代码重构/架构优化（不改变功能也不修 bug）→ `PATCH+1`（归为修复性质）
- 每次发布必须递增版本号，禁止重复使用同一版本号
- 版本号同时更新在 **2 处**（见 §3 检查清单），保持一致

## 2. 发布流程（标准操作）

### 2.1 流程图

```text
  确认代码就绪
       │
       ▼
  全局检查（§4 检查清单）
       │
       ▼
  更新版本号（§3 两处一致）
       │
       ▼
  更新 CHANGELOG.md
       │
       ▼
  提交版本更新
       │
       ▼
  更新 codegraph 索引
       │
       ▼
  打 tag（git tag -a vX.Y.Z -m "release: vX.Y.Z"）
       │
       ▼
  推送代码与 tag
       │
       ├──→ GitHub Actions CI 自动测试 + 发布到 PyPI + 发布到 npm
       │
       ├──→ 手动同步到 GitCode / AtomGit（三仓同步）
       │
       ▼
  验证 Release（§5）
```

### 2.2 详细步骤

```bash
# ① 确认工作区干净
git status

# ② 全局检查（见 §4）
pytest tests/ -v --tb=short --cov=gongwen --cov=engine   # 本地全量测试
pycodestyle --max-line-length=120 --exclude=__pycache__,.git,dist,build .  # 代码风格

# ③ 更新版本号（2 处一致，见 §3）
# 编辑 package.json 和 pyproject.toml 中的 version 字段

# ④ 更新 CHANGELOG.md
# 在文件顶部新增条目，格式见 §6

# ⑤ 提交
git add -A
git commit -m "chore: bump version to X.Y.Z"

# ⑥ 更新 codegraph 索引（增量更新，供 AI 工具索引）
codegraph sync --quiet

# ⑦ 打注解 tag
git tag -a v1.2.0 -m "release: v1.2.0"

# ⑧ 推送（GitHub 自动触发 CI 测试 + PyPI 发布 + npm 发布）
git push origin master
git push origin v1.2.0

# ⑨ 三仓同步（手动）
git push gc master
git push gc v1.2.0
git push atomgit master
git push atomgit v1.2.0

# ⑩ 验证 Release（见 §5）
gh release list
gh release view v1.2.0 --json assets
```

### 2.3 分支策略

- **主分支**：`master`（非 `main`）
- 日常开发直接推送到 `master` 或从功能分支 PR 合并
- 标签触发（`v*`）自动走 CI 发布流程
- 无独立 `develop` 或 `release` 分支

## 3. 版本号更新点（2 处必须一致）

| # | 文件 | 位置 |
|---|------|------|
| 1 | `package.json` | `"version": "X.Y.Z"` |
| 2 | `pyproject.toml` | `version = "X.Y.Z"` |

> **注意**：`dist/` 中的构建产物（.whl / .tar.gz）在发布前已存在旧版本，推送 tag 后 CI 自动构建新版本覆盖，无需手动更新。

## 4. 发布前检查清单

- [ ] `git status` 干净（无未提交改动）
- [ ] 2 处版本号一致且已递增（§3）
- [ ] CHANGELOG.md 已更新（§6 格式）
- [ ] 全量测试通过：`pytest tests/ -v --tb=short`（本地测试不推送，参见 4.1）
- [ ] 代码风格检查通过：`pycodestyle --max-line-length=120 --exclude=__pycache__,.git,dist,build .`
- [ ] DSH 插件检查：`dsh` 目录下 `index.js` 和 `client.js` 无语法错误
- [ ] 三仓库远程配置正确（origin / gc / atomgit）
- [ ] GitHub Actions CI 配置正确（`.github/workflows/ci.yml`）
- [ ] PyPI API Token 有效（`PYPI_API_TOKEN` secrets 存在）
- [ ] npm Token 有效（`NPM_TOKEN` secrets 存在，见 §5.2）
- [ ] 本地构建验证：`python -m build` 成功
- [ ] codegraph 索引已更新：`codegraph sync --quiet`

### 4.1 关于测试用例

> 自 v1.12.69 起，测试用例（`tests/`）**仅本地保留，不推送远程仓库**。GitHub CI 中测试步骤通过 `hashFiles('tests/**')` 条件判断，若不存在则优雅跳过，**不阻断发布**。本地开发时需确保测试通过后再推送。

## 5. 发布与构建（CI 自动完成）

推送 `v*` tag 后，[.github/workflows/ci.yml](.github/workflows/ci.yml) 自动执行：

| 步骤 | 作业 | 说明 |
|------|------|------|
| 测试 | `test` | Python 3.10–3.14 矩阵，`pytest --cov-fail-under=20` |
| 代码风格 | `lint` | `pycodestyle --max-line-length=120` |
| 发布到 PyPI | `publish` | 依赖 `test` + `lint`，推送 `v*` tag 时触发；使用 `pypa/gh-action-pypi-publish` 上传 wheel + sdist |
| 发布到 npm | `publish-npm` | 依赖 `test` + `lint`，推送 `v*` tag 时触发；使用 `npm publish --access public` 发布 DSH 插件包 |

**CI 产物**：
- `dist/gongwen_skill-X.Y.Z-py3-none-any.whl`（纯 Python wheel）
- `dist/gongwen_skill-X.Y.Z.tar.gz`（源码包）

> **OIDC 说明**：README 中提及 OIDC trusted publishing，但当前 CI 实际使用 `PYPI_API_TOKEN` secrets 认证。如需切换，需在 PyPI 项目设置页面配置 publisher，并修改 CI 配置。

### 5.2 npm 发布说明

CI 自动将 DSH 插件包发布到 npm（包名 `gongwen-skill`），版本号取自 `package.json`。

**前置条件**：

1. 在 [npmjs.com](https://www.npmjs.com/settings/linhut/tokens) 生成 **Automation token**（`npm profile create-token --read-only=false`）
2. 将 token 添加到 GitHub 仓库 Secrets：**Settings → Secrets and variables → Actions → New repository secret**
   - Name: `NPM_TOKEN`
   - Value: 粘贴生成的 token
3. 确保 npm 包名未被占用（已注册 `gongwen-skill`）

> **注意**：npm 版本与 PyPI 版本**同步递增**，均来自同一版本号（`package.json`）。CI 中 `publish-npm` 与 `publish` 并行执行，互不依赖。

### 5.1 本地构建（PyPI）

```bash
# 本地构建 wheel 和 sdist
pip install build
python -m build

# 产物在 dist/ 目录下
ls dist/
```

## 6. 发布后验证

```bash
# 验证 GitHub Release
gh release list                              # 确认 vX.Y.Z 出现
gh release view vX.Y.Z --json assets         # 确认 CI 自动创建了 Release

# 验证 PyPI
pip install gongwen-skill==X.Y.Z             # 安装新版本
python -m gongwen --version                  # 确认版本号正确

# 验证 npm
npm view gongwen-skill versions --json        # 确认新版本在列表中
npm install gongwen-skill@latest              # 安装最新版

# 验证 DSH 集成
dsh skill list                               # 确认 gongwen-skill 可发现

# 验证三仓同步
git push gc master && git push gc vX.Y.Z
git push atomgit master && git push atomgit vX.Y.Z
```

**Release 规范**：
- 名称由 CI 自动生成（基于 tag 名）
- 仅保留正式 Release，**删除 Draft 草稿**（避免列表重复）
- 最新版本自动标记 `Latest`

## 7. CHANGELOG 格式规范

CHANGELOG.md 条目格式：

```markdown
## vX.Y.Z (YYYY-MM-DD)

### Added
- 新功能描述

### Changed
- 变更描述

### Fixed
- 缺陷修复描述

### Removed
- 移除内容描述
```

**规则**：
- 每次发布前在文件**顶部**新增条目
- 日期格式 `YYYY-MM-DD`
- 按 `Added` / `Changed` / `Fixed` / `Removed` 分类（无对应内容则省略该分类）
- 每个变更点一行，必要时可附注引用的 Issue 或 PR 编号

## 8. 三仓库同步策略

项目同时维护三个远程仓库：

| 远程名 | 平台 | URL |
|--------|------|-----|
| `origin` | GitHub | `https://github.com/linhut/gongwen-skill.git` |
| `gc` | GitCode | `https://gitcode.com/linhut/gongwen-skill.git` |
| `atomgit` | AtomGit | `https://atomgit.com/linhut/gongwen-skill.git` |

**发布时同步策略**：
1. **先推 GitHub**（触发 CI 自动发布到 PyPI 和 GitHub Release）
2. **再推 GitCode 和 AtomGit**（代码镜像，不触发 CI）

```bash
# 一键推送三仓
git push origin master && git push origin vX.Y.Z
git push gc master && git push gc vX.Y.Z
git push atomgit master && git push atomgit vX.Y.Z
```

## 9. codegraph 索引管理

项目使用 [codegraph](https://github.com/linhut/codegraph) 维护代码索引，供 AI 工具（如 DSH 代码理解）查询。

### 9.1 索引更新时机

| 时机 | 命令 | 说明 |
|------|------|------|
| 每次提交后 | `codegraph sync --quiet` | 增量更新索引，记录最新代码结构 |
| 发布前（§2 步骤⑥） | `codegraph sync --quiet` | 确保发布时的索引是最新的 |
| 日常开发按需 | `codegraph sync` | 不带 `--quiet` 可查看同步进度 |

### 9.2 自动同步：post-commit hook

项目已内置 post-commit hook（`.githooks/post-commit`），每次 `git commit` 后自动增量更新 codegraph 索引，无需手动操作。

**首次使用**（也可以不做，git 已自动配置为使用 `.githooks/`）：

```bash
# 确保 git 使用 .githooks/ 目录（已通过 git config 配置，克隆后可能需要重新激活）
git config core.hooksPath .githooks
```

**验证生效**：

```bash
# 查看 hook 内容
cat .githooks/post-commit
# 输出：#!/bin/sh\ncodegraph sync --quiet

# 或直接提交一次测试
git commit --allow-empty -m "test: verify post-commit hook"
# 如果无报错，说明 hook 已生效
```

## 10. 常见问题

| 问题 | 处理 |
|------|------|
| `gh release create` 报 tag 已存在 | 说明 CI 已自动创建 Release，直接验证即可，勿重复创建 |
| PyPI 发布失败（401 Unauthorized） | 检查 `PYPI_API_TOKEN` secrets 是否有效或过期，在 GitHub 仓库 Settings → Secrets → Actions 中更新 |
| CI test job 被跳过 | 正常现象——v1.12.69 起 `tests/` 不推送仓库，CI 通过 `hashFiles` 检测后优雅跳过，不影响发布 |
| 本地 `python -m build` 失败 | 检查 `pyproject.toml` 语法，确认 setuptools 已安装 |
| 三仓同步推送失败 | 检查各远程仓库的认证凭据（GitCode/AtomGit 使用 oauth2 token），必要时更新 remote URL |
| Release list 有 Draft 重复条目 | `gh api -X DELETE repos/<owner>/<repo>/releases/<id>` 删除草稿 |
| 构建产物版本号不对 | 检查 §3 的 2 处版本号是否一致 |
| 测试覆盖率低于门槛 | CI 覆盖率门槛为 20%，本地开发时需确保不低于此值；若确实因测试不在仓库而跳过，CI 不阻断 |
| `codegraph sync` 命令不存在 | 确认已安装 codegraph：`npm install -g @liustack/codegraph`（或项目级依赖） |
| npm 发布失败（403 Unauthorized） | 检查 `NPM_TOKEN` secrets 是否有效，在 npmjs.com 重新生成 Automation token 后更新 GitHub Secrets |
| npm 发布失败（404 Not Found） | 确认包名 `gongwen-skill` 已在 npmjs.com 注册，且 `package.json` 中 `name` 字段正确 |
| npm 与 PyPI 版本号不一致 | 检查 `package.json` 和 `pyproject.toml` 的版本号是否一致（§3） |
| npm 发布后版本未更新 | 检查 CI 中 `publish-npm` job 是否运行成功（GitHub Actions 日志），确认 tag 格式为 `vX.Y.Z` |

## 11. 快速参考（速查表）

```bash
# 完整发布流程（一行执行）
git status && \
  # 手动更新 package.json + pyproject.toml 版本号 + CHANGELOG.md 后 && \
  git add -A && \
  git commit -m "chore: bump version to X.Y.Z" && \
  codegraph sync --quiet && \
  git tag -a vX.Y.Z -m "release: vX.Y.Z" && \
  git push origin master && \
  git push origin vX.Y.Z && \
  git push gc master && \
  git push gc vX.Y.Z && \
  git push atomgit master && \
  git push atomgit vX.Y.Z && \
  echo "✅ 发布完成，等待 CI 构建并验证"
```