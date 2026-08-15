# npm 发布完整教程

## 前置准备

### 1. 注册 npm 账号

1. 打开 https://www.npmjs.com/signup
2. 填写用户名、邮箱、密码
3. 验证邮箱（npm 会发送验证邮件）
4. 登录 npm

### 2. 本地登录 npm

```bash
# 登录 npm（需要输入用户名、密码、邮箱）
npm login

# 验证登录状态
npm whoami
```

### 3. 配置 npm 2FA（推荐，提高安全性）

```bash
npm profile enable-2fa auth-and-writes
```

---

## 包名选择

### 方案一：直接发布 `gongwen-skill`

```bash
# 检查包名是否可用
npm search gongwen-skill
# 或
npm view gongwen-skill
# 如果返回 404 说明可用
```

### 方案二：使用作用域包（推荐，避免命名冲突）

将 `package.json` 中的 `name` 改为：

```json
{
  "name": "@linhut/gongwen-skill",
  "publishConfig": {
    "access": "public"
  }
}
```

作用域包的好处：
- 命名空间隔离，不会被别人占用
- 明确归属
- 可设置为私有（付费功能）

---

## 首次手动发布

### 第1步：检查 package.json

确保 `package.json` 包含必要字段：

```json
{
  "name": "gongwen-skill",
  "version": "1.12.57",
  "description": "中文公文全流程处理工具 - GB/T 9704 格式检查/修复/内容优化/模板生成/版式注入",
  "type": "module",
  "main": "dsh/index.js",
  "exports": {
    ".": "./dsh/index.js",
    "./dsh": "./dsh/index.js",
    "./package.json": "./package.json"
  },
  "files": [
    "dsh/",
    "skills/",
    "cordis.patch.yml",
    "SKILL.md",
    "README.md",
    "LICENSE"
  ],
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  },
  "keywords": ["chinese", "document", "government", "GB/T 9704", "dsh"],
  "author": "Jose AI",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "git+https://github.com/linhut/gongwen-skill.git"
  }
}
```

### 第2步：构建测试

```bash
# 进入项目目录
cd C:\Users\Administrator\Documents\document-skills\gongwen-skill

# 打包测试（dry-run，不会实际发布）
npm pack --dry-run
```

这会列出将要包含在包中的所有文件。确认包含：
- `dsh/index.js`
- `skills/gongwen-skill/SKILL.md`
- `cordis.patch.yml`
- `README.md`
- `LICENSE`

### 第3步：发布到 npm

```bash
# 方式一：直接发布（公开包）
npm publish

# 方式二：作用域包需要加 --access public
npm publish --access public
```

### 第4步：验证发布

```bash
# 查看包信息
npm view gongwen-skill

# 在一个新目录安装测试
mkdir test_npm && cd test_npm
npm init -y
npm install gongwen-skill

# 检查安装后的文件结构
dir node_modules/gongwen-skill/
# 应该包含: dsh/  skills/  cordis.patch.yml  SKILL.md  README.md  LICENSE
```

---

## 安装到 DSH

### 手动安装

```bash
# 进入 DSH web profile 目录
cd ~/.dsh/profiles/web

# 安装 gongwen-skill
npm install gongwen-skill

# 查看 package.json 确认依赖已添加
type package.json
# 应该看到: "gongwen-skill": "^1.12.57"
```

### 注册到 cordis.patch.yml

检查 `~/.dsh/profiles/web/cordis.patch.yml` 是否包含：

```yaml
- insert:
    - id: gongwen-skill
      name: gongwen-skill
```

如果不存在，手动添加（与 modlens 的配置同级）：

```yaml
- insert:
    - id: modlens
      name: '@liustack/modlens'
- insert:
    - id: gongwen-skill
      name: gongwen-skill
```

### 注册技能到 DSH

```bash
# 复制技能文件到 DSH 发现目录
mkdir -p ~/.dsh/skills/gongwen-skill
cp node_modules/gongwen-skill/SKILL.md ~/.dsh/skills/gongwen-skill/SKILL.md

# 或者创建单文件技能
cp node_modules/gongwen-skill/SKILL.md ~/.dsh/skills/gongwen-skill.md
```

---

## 版本更新

### 更新流程

```bash
# 1. 更新版本号（推荐使用 npm version）
npm version patch   # 1.12.57 -> 1.12.58 (bug fix)
npm version minor   # 1.12.57 -> 1.13.0  (新功能)
npm version major   # 1.12.57 -> 2.0.0   (破坏性变更)

# 这会自动:
#   - 更新 package.json 中的 version
#   - 创建 git commit
#   - 创建 git tag

# 2. 推送 tag
git push origin master --tags

# 3. 发布到 npm
npm publish
```

### 如果使用手动版本号

```bash
# 手动更新 package.json 中的 version 字段
# 然后提交并发布
git add -A
git commit -m "chore: bump to v1.12.58"
git tag v1.12.58
git push origin master --tags
npm publish
```

---

## 配置 GitHub Actions 自动发布

### 第1步：创建 npm Token

1. 登录 https://www.npmjs.com/
2. 点击头像 -> "Access Tokens"
3. 点击 "Generate New Token" -> "Classic Token"
4. Type: "Automation"（不需要 2FA）
5. 点击 "Generate"
6. **复制并保存 Token**

### 第2步：添加到 GitHub Secrets

1. 打开 https://github.com/linhut/gongwen-skill/settings/secrets/actions
2. 点击 "New repository secret"
3. Name: `NPM_TOKEN`
4. Value: 粘贴 npm Token
5. 点击 "Add secret"

### 第3步：添加 npm 发布 Job 到 CI

编辑 `.github/workflows/ci.yml`，在 `publish` job 中添加 npm 发布步骤：

```yaml
publish-npm:
  name: Publish to npm
  needs: [test, lint]
  if: startsWith(github.ref, 'refs/tags/v')
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '22'
        registry-url: 'https://registry.npmjs.org'
    - run: npm publish
      env:
        NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

---

## 常见问题

### Q: `npm publish` 报错 "403 Forbidden"
A: 可能的原因：
- 包名已被占用，改为作用域包 `@linhut/gongwen-skill`
- 未登录：运行 `npm login`
- Token 权限不足：使用 Automation 类型 Token

### Q: `npm publish` 报错 "402 Payment Required"
A: 免费账号只能发布公开包。如果使用作用域包，需要加 `--access public`

### Q: 如何废弃旧版本？
A: ```bash
npm deprecate gongwen-skill@1.12.56 "请升级到 1.12.57"
```

### Q: 如何删除已发布的版本？
A: ```bash
# 删除 24 小时内发布的版本
npm unpublish gongwen-skill@1.12.56
```

### Q: 包安装后启动报错？
A: `dsh/index.js` 是 DSH 插件桥接代码，不是直接运行的 CLI。
CLI 入口在 Python 端（`pip install gongwen-skill` 后的 `gongwen` 命令）。

---

## 完整发布流程速查

### PyPI 发布

```bash
# 首次
pip install build twine
python -m build
twine upload dist/* -u __token__ -p pypi-xxxxxxxxxx

# 更新版本
# 1. 改 gongwen.py 中的 __version__
# 2. 改 pyproject.toml 中的 version
# 3. 改 CHANGELOG.md
# 4. 提交 + tag + push
# 5. GitHub Actions 自动发布
```

### npm 发布

```bash
# 首次
npm login
npm publish

# 更新版本
npm version patch
git push origin master --tags
npm publish

# 或者手动
# 1. 改 package.json 中的 version
# 2. 提交 + tag
# 3. npm publish
```
