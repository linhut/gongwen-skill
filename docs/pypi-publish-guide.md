# PyPI 发布完整教程

## 前置准备

### 1. 注册 PyPI 账号

1. 打开 https://pypi.org/account/register/
2. 填写用户名、邮箱、密码
3. 验证邮箱（PyPI 会发送验证邮件）
4. 登录 PyPI

### 2. 创建 API Token（推荐，无需密码）

1. 登录后访问 https://pypi.org/manage/account/token/
2. 点击 "Add API token"
3. Token name: `gongwen-skill-ci`（用于 GitHub Actions）
4. Scope: 选择 "Entire account (all projects)"
5. 点击 "Create token"
6. **复制并保存生成的 Token**（关闭页面后不可找回）

### 3. 安装发布工具

```bash
pip install build twine
```

---

## 首次手动发布

### 第1步：构建分发包

```bash
# 进入项目目录
cd C:\Users\Administrator\Documents\document-skills\gongwen-skill

# 清理旧构建
rm -rf dist/ build/ *.egg-info

# 构建源码分发包和 wheel 包
python -m build
```

输出示例：
```
Successfully built gongwen_skill-1.12.57.tar.gz
Successfully built gongwen_skill-1.12.57-py3-none-any.whl
```

### 第2步：上传到 PyPI

```bash
# 方式一：使用 API Token（推荐）
twine upload dist/* -u __token__ -p pypi-xxxxxxxxxxxxxxxxxxxx

# 方式二：使用用户名密码
twine upload dist/* -u your_username -p your_password

# 方式三：交互式输入
twine upload dist/*
# 会提示输入用户名和密码
```

### 第3步：验证发布

```bash
# 安装验证
pip install gongwen-skill

# 运行验证
gongwen --version
# 输出: gongwen-skill v1.12.57

gongwen list-types
# 输出: 25 种公文类型列表
```

### 第4步：安装测试

```bash
# 在新目录中测试纯净安装
mkdir test_install && cd test_install
pip install gongwen-skill
gongwen --version
gongwen list-types
```

---

## 配置 GitHub Actions 自动发布

### 第1步：将 API Token 添加到 GitHub Secrets

1. 打开 GitHub 仓库: https://github.com/linhut/gongwen-skill
2. 点击 `Settings` -> `Secrets and variables` -> `Actions`
3. 点击 `New repository secret`
4. Name: `PYPI_API_TOKEN`
5. Value: 粘贴之前复制的 API Token（以 `pypi-` 开头）
6. 点击 `Add secret`

### 第2步：触发自动发布

CI/CD 配置已就绪（`.github/workflows/ci.yml`），自动发布条件：

```bash
# 打 tag 即可触发自动发布到 PyPI
git tag v1.12.58
git push origin master --tags
```

GitHub Actions 会自动执行：
1. 运行测试（Python 3.10/3.11/3.12/3.13）
2. 运行代码风格检查
3. 构建分发包
4. 上传到 PyPI

---

## 发布后验证

### 检查 PyPI 页面

- 打开 https://pypi.org/project/gongwen-skill/
- 确认版本号、描述、README 正确显示
- 确认分类器（Classifiers）正确

### 测试安装

```bash
# 在全新环境安装
python -m venv test_env
test_env\Scripts\activate  # Windows
# source test_env/bin/activate  # Linux/macOS

pip install gongwen-skill
gongwen --version
gongwen template notice -o test.docx
```

### 验证 DSH 兼容性

```bash
# 安装后，SKILL.md 位于 Python 包中
# DSH 可通过 .dsh/skills/ 发现
# 或通过 pip show 查看安装位置
pip show -f gongwen-skill | findstr "SKILL.md"
```

---

## 常见问题

### Q: 上传失败 "403 Forbidden"
A: Token 权限不足，检查 scope 是否为 "Entire account"

### Q: 上传失败 "400 Invalid classifier"
A: `pyproject.toml` 中的分类器版本不存在，检查 Python 版本号

### Q: `pip install` 后找不到 `gongwen` 命令
A: 检查 PATH 是否包含 Python Scripts 目录：
```bash
python -m site --user-site
# 将输出目录的 ../Scripts 加入 PATH
```

### Q: 更新版本后旧版本还能安装
A: PyPI 允许所有版本共存，`pip install` 默认安装最新版

---

## 版本更新流程

```bash
# 1. 更新 gongwen.py 中的 __version__
# 2. 更新 CHANGELOG.md
# 3. 更新 pyproject.toml 中的 version
# 4. 提交并打 tag
git add -A
git commit -m "chore: bump to v1.12.58"
git tag v1.12.58
git push origin master --tags
git push gc master --tags
git push atomgit master --tags
# 5. GitHub Actions 自动发布到 PyPI
```

> **注意**：`pyproject.toml` 中的 version 需要与 `gongwen.py` 中的 `__version__` 保持一致。
