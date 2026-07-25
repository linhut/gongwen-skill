# 公文文档格式化 Skill — 功能清单与调用方法

> 统一入口 `python gongwen.py <命令> [参数]`
> 共 **15 个子命令**，按场景分为两条主线路径 + 辅助工具

---

## 路径 A：格式优化（不改内容，只改排版）

### 1. `check` — 检查文档格式合规性
```
python gongwen.py check 输入.docx -t notice --json
```
- `-t, --doc-type` 公文类型（默认 notice，共 22 种）
- `-s, --severity` 仅显示指定级别（P0/P1/P2）
- `--json` JSON 结构化输出

### 2. `optimize` — 一键修复格式 + 可选版式注入
```
python gongwen.py optimize 输入.docx -o 输出.docx -t notice
python gongwen.py optimize 输入.docx -o 输出.docx --layout 版式.json
```
- `-t, --doc-type` 公文类型（默认自动检测，列出所有类型让用户确认）
- `--layout` 版式注入 JSON（header/footer/page_number 三块可选）
- `--selected-rules` 仅修复指定规则 ID（逗号分隔）

### 3. `bold-first` — 正文段落首句加粗
```
python gongwen.py bold-first 输入.docx -o 输出.docx
```
- 将每个正文段落的第一句话（遇 。！？：；为界）加粗
- 不修改标题、签名、日期段落

---

## 路径 B：内容优化（改内容，生成差异对比）

### 4. `optimize-content` — 内容优化差异对比
```
python gongwen.py optimize-content 输入.docx -o 对比文档.docx --changes changes.json
```
- `--changes` 变更 JSON 文件路径（必填）
- `--optimize-format` 同时优化格式（默认仅做差异标注，不改格式）

**changes.json 格式：**
```json
{
  "changes": [
    {
      "paragraph_index": 2,
      "original_text": "原文内容",
      "optimized_text": "优化后内容",
      "reason": "修改说明",
      "reference": "依据来源（可选）"
    }
  ]
}
```

**生成文档特点：**
- 原文为灰色 + 删除线
- 优化后内容为红色高亮
- 字体/字号从原文段落读取，不套用模板
- 每段末尾附楷体小字「修改说明」和「依据」

### 5. `md2docx` — Markdown/纯文本 → 公文 .docx
```
python gongwen.py md2docx 草稿.md -o 公文.docx -t notice --signer 某某单位 --date 2026年7月24日
cat 草稿.md | python gongwen.py md2docx - -o 公文.docx
```
- `-t, --doc-type` 公文类型
- `--recipients` 主送机关
- `--signer` 落款单位
- `--date` 成文日期
- `--attachments` 附件列表
- 支持 Front Matter 元数据（--- 包裹的 YAML 块）

---

## 版式要素注入（单独使用）

### 6. `header` — 注入版头
```
python gongwen.py header 输入.docx -o 输出.docx \
  --org-name "国家民委办公厅" \
  --doc-number "民委办发〔2026〕1号" \
  --signer "张三"
```
- `--org-name` 发文机关标志（红色大字，必填）
- `--doc-number` 发文字号
- `--signer` 签发人姓名

### 7. `footer` — 注入版记
```
python gongwen.py footer 输入.docx -o 输出.docx \
  --cc "各省民委" \
  --printer "国家民委办公厅" \
  --print-date "2026年7月24日"
```
- `--cc` 抄送机关
- `--printer` 印发机关
- `--print-date` 印发日期

### 8. `pagenum` — 注入页码
```
python gongwen.py pagenum 输入.docx -o 输出.docx \
  --font 宋体 --size 14 --alignment center \
  --format "— {PAGE} —"
```
- `--font` 页码字体（默认 宋体）
- `--size` 字号（默认 14）
- `--alignment` 对齐：center/left/right（right 表示单右双左奇偶排版）
- `--format` 格式，可用 {PAGE} / {NUMPAGES}

---

## 辅助工具

### 9. `template` — 生成空白公文模板
```
python gongwen.py template notice -o 通知模板.docx
```
- 参数：公文类型（必填）

### 10. `parse` — 解析 .docx 为结构化 JSON
```
python gongwen.py parse 输入.docx -o model.json
```
- 输出 DocumentModel 的结构化表示

### 11. `generate` — 从 JSON 重新生成 .docx
```
python gongwen.py generate model.json -o 输出.docx
```

### 12. `list-types` — 列出 22 种公文类型
```
python gongwen.py list-types [--json]
```

### 13. `rule-export` — 导出合并规则为 YAML
```
python gongwen.py rule-export notice -o notice.yaml
```

### 14. `rule-list` — 列出三层规则文件
```
python gongwen.py rule-list [--source all|official|custom|user] [--json]
```

### 15. `rule-import` — 导入自定义规则 YAML
```
python gongwen.py rule-import my_rules -f rules.yaml
python gongwen.py rule-import my_rules --text "{...inline yaml...}"
```

---

## 两条主线路径速查

| 场景 | 命令 | 说明 |
|------|------|------|
| **格式不对，想改排版** | `check` → `optimize` | 先检查问题清单，再一键修复 |
| **内容要改，想看差异** | 准备 changes.json → `optimize-content` | 原文灰色删除线，修改后红色高亮，附说明 |
| **从零生成公文** | `md2docx` 或 `template` | Markdown 成文 或 空白模板 |
| **补红头/版记/页码** | `header` / `footer` / `pagenum` | 或 `optimize --layout 版式.json` 一步到位 |
| **首句加粗** | `bold-first` | 段落点题第一句话加粗 |