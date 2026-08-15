# 贡献指南

感谢你考虑为 gongwen-skill 做出贡献！

## 行为准则

本项目采用 [Contributor Covenant](https://www.contributor-covenant.org/) 行为准则。参与本项目即表示你同意遵守其条款。

## 如何贡献

### 报告 Bug

1. 使用 [Bug 报告模板](https://github.com/linhut/gongwen-skill/issues/new?template=bug_report.md)
2. 清晰描述问题、重现步骤和环境信息
3. 附上完整的错误日志

### 提交功能请求

1. 使用 [功能请求模板](https://github.com/linhut/gongwen-skill/issues/new?template=feature_request.md)
2. 清晰描述你想解决的问题和期望的解决方案

### 提交 Pull Request

1. Fork 本仓库
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交你的更改: `git commit -m 'feat: add amazing feature'`
4. 推送到分支: `git push origin feature/amazing-feature`
5. 提交 Pull Request

## 开发指南

### 环境准备

```bash
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill
pip install -r requirements.txt
pip install pytest
```

### 运行测试

```bash
pytest tests/ -v --tb=short
```

### 代码风格

- 遵循 PEP 8 规范
- 最大行长度: 120 字符
- 使用有意义的变量名和函数名
- 为公共函数编写 docstring

### Commit 消息规范

使用语义化 commit 消息:

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具链变更

### 版本号

本项目遵循 [Semantic Versioning](https://semver.org/)。版本号格式: `vMAJOR.MINOR.PATCH`

## 项目结构

```
gongwen-skill/
  +-- gongwen.py          # CLI 入口
  +-- engine/             # 核心引擎
  |   +-- core/           # 文档处理 + 规则引擎
  |   +-- utils/          # 工具模块
  +-- rules/official/     # 25 种公文类型规则
  +-- tests/              # 测试套件
  +-- .dsh/skills/        # DSH 技能发现目录
```
