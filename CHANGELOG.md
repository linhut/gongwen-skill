# Changelog

## v1.12.53 (2026-08-05)

### Fixed
- `_atomic_save` os.replace 增加重试（FIX-A001），解决 Windows 文件锁导致 md2docx 页码注入失败
- 批注锚定增加内容段落映射（FIX-A002），跳过无文本 run 的空段，解决锚定偏移
- 批注完整性验证逻辑拆分（FIX-A003），修订/批注独立判断，避免误报
- prompts/usage-prompts.md 和 README.md 行距 28.95→33 同步（FIX-B001）

### Added
- 结语检查 `ending.check` 实现（FIX-V153-02）：5 种文种（通知/请示/报告/批复/函）结尾格式检查从"跳过"变为实际触发
- 0 处批注时验证逻辑短路（FIX-V153-01），optimize-content / full-review 不再误报

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
