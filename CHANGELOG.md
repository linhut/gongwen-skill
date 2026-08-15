# Changelog

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
