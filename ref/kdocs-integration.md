<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# kdocs-skill 集成参考

本文档描述 gongwen-skill 与 kdocs-skill（金山文档 CLI）的协同方式。kdocs-skill 是**可选增强**，未安装时 gongwen 所有本地功能不受影响。

---

## 一、协同能力总览

| # | 协同场景 | 触发条件 | kdocs 能力 | gongwen 衔接 |
|---|----------|----------|-----------|-------------|
| 1 | 扫描件 PDF 读取 | 用户提供扫描件 PDF，无法直接提取文字 | `pdf inspect` / `pdf convert` | 提取文字 → 保存 .docx/.md → gongwen 管线 |
| 2 | 云端文档读取 | 用户给金山云文档链接或 file_id | `drive search-files` / `read_file` | 导出为本地 .docx → gongwen parse/check/optimize |
| 3 | 产物云保存 | gongwen 生成成品后用户需要云端存档 | `drive create_file_with_content` / `upload_file` | 上传成品，获取分享链接 |
| 4 | 公文转 PDF | 成品需 PDF 分发归档 | `pdf convert` | .docx → .pdf |
| 5 | 网页剪藏素材 | 公文需引用网页素材 | workflows/web-scrape | 抓取内容作为素材来源 |

---

## 二、前置条件

```bash
# 1. 确认 kdocs-cli 可用
kdocs-cli --help

# 2. 认证（Token 由 kdocs-skill 管理，gongwen 不涉及）
kdocs-cli auth login          # 交互式登录
# 或
kdocs-cli auth set-token "<token>"

# 3. 保持最新
kdocs-cli upgrade -y
```

若 `kdocs-cli` 不存在或报错，回退为纯本地流程，不影响 gongwen 功能。

---

## 三、场景实操示例

### 场景 1：扫描件 PDF → 公文

```
用户：帮我检查这份扫描件的公文格式
步骤：
1. kdocs-cli pdf inspect --file 扫描件.pdf        # 检查是否可读
2. kdocs-cli pdf convert --file 扫描件.pdf -o 提取稿.docx   # 提取文字
   # 或提取为 markdown: -o 提取稿.md
3. python gongwen.py check 提取稿.docx -t notice  # gongwen 正常处理
4. python gongwen.py optimize 提取稿.docx -o 成品.docx --apply
```

### 场景 2：金山云文档 → gongwen 处理

```
用户：帮我优化这份云文档 https://kdocs.cn/l/xxx
步骤：
1. kdocs-cli drive search-files keyword=标题          # 定位 file_id
   # 或直接从链接解析 file_id
2. kdocs-cli drive read_file file_id=xxx -o 本地稿.docx   # 导出为本地文件
3. python gongwen.py optimize-content 本地稿.docx --changes changes.json --apply
4. 交付差异对比文档
```

### 场景 3：成品 → 云端存档

```
步骤：
1. python gongwen.py optimize 原稿.docx -o 成品.docx --apply   # gongwen 生成成品
2. kdocs-cli drive create_file_with_content file_name=成品.docx content_base64=<base64> format=docx
   # 或 kdocs-cli drive upload_file path=成品.docx
3. 向用户展示返回的 link_url 分享链接
```

> **注意**：`content_base64` 可能很大（>1MB），禁止在对话中逐 token 生成，用脚本完成读取编码（遵循 kdocs-skill 规范）。

### 场景 4：成品转 PDF

```
python gongwen.py optimize 原稿.docx -o 成品.docx --apply
kdocs-cli pdf convert --file 成品.docx -o 成品.pdf
```

---

## 四、协同规则

1. **本地优先**：gongwen 所有管线（parse/check/optimize/generate）只处理本地文件，云端文档必须先落盘
2. **不跨进程传对象**：云端读取 → 本地 .docx → gongwen 管线 → 本地成品 → （可选）云端上传
3. **认证隔离**：Token 由 kdocs-cli 系统密钥链管理，gongwen 不读取、不存储、不传输
4. **产物链接**：云端保存成功后必须向用户展示可访问链接（`data.link_url` 或 `get_file_link`）
5. **降级策略**：`kdocs-cli` 不可用时，全程回退本地流程，不中断任务

---

## 五、典型链路图

```
用户提供扫描件PDF / 云文档链接
    │
    ▼
kdocs-cli 提取/导出 → 本地 .docx / .md
    │
    ▼
gongwen 管线（parse → check/optimize → generate）
    │
    ▼
本地成品 .docx
    │
    ├── （可选）kdocs-cli pdf convert → .pdf 分发
    └── （可选）kdocs-cli drive upload → 云文档 + 分享链接
```

---

## 六、kdocs-skill 参考文档索引

完整参数与约束以 kdocs-skill 自身的 `references/` 为准：

| 服务 | 参考文档 |
|------|---------|
| 文件读写 | `kdocs-skill/references/drive/read_and_download.md` |
| 文件定位 | `kdocs-skill/references/file-locating-guide.md` |
| 创建上传 | `kdocs-skill/references/drive/create_and_upload.md` |
| PDF 处理 | `kdocs-skill/references/pdf.md` |
| 网页剪藏 | `kdocs-skill/references/workflows/web-scrape.md` |
| 认证 | `kdocs-skill/references/auth.md` |
