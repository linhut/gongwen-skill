<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# 参考手册 · gongwen-skill

本文档面向需要深入定制或以编程方式调用引擎的用户。基础用法见 [README.md](./README.md)。

## 目录结构

```
gongwen-skill/
├── gongwen.py              # 统一 CLI 入口（13 个子命令）
├── SKILL.md                # AI Skill 声明（frontmatter + 触发场景）
├── README.md               # GitHub 首页
├── REFERENCE.md            # 本文档
├── LICENSE                 # MIT
├── requirements.txt        # python-docx / pydantic / pyyaml
├── prompts/
│   └── style-prompts.md    # 通用底座 + 6 套公文语言风格提示词
├── rules/official/         # 23 份规则 YAML（_common + 22 类型）
└── engine/                 # 自包含引擎（从原项目抽取）
    ├── config.py           # 独立路径解析（无数据库/桌面端耦合）
    ├── template_builder.py # 模板生成（剥离 FastAPI）
    ├── inject.py           # 版头 / 版记 / 页码注入（剥离 FastAPI）
    ├── core/
    │   ├── document/       # parser / generator / modifier / models / font_utils ...
    │   └── rules/          # loader / manager / checker / fixer / engine
    └── utils/logger.py
```

## 核心流水线

```
Parse → Model → Manipulate → Generate
```

所有处理都经过 **DocumentModel**（Pydantic 中间表示），任何模块都不直接操作 python-docx 对象。

```
parse_docx(path)          → DocumentModel
RuleEngine.check(model)   → list[CheckIssue]
RuleEngine.check_and_fix()→ (issues, fixed_model)
generate_docx(model, out) → .docx
```

## 编程调用

```python
import sys
sys.path.insert(0, "engine")   # 关键：让 engine 内部绝对导入生效

from core.document.parser import parse_docx
from core.document.generator import generate_docx
from core.rules.engine import RuleEngine

model = parse_docx("input.docx")
engine = RuleEngine()
issues, fixed = engine.check_and_fix(model, "notice")
generate_docx(fixed, "output.docx")

for i in issues:
    print(i.severity, i.rule_id, i.name, i.location)
```

## 版式要素注入（版头 / 版记 / 页码）

三个注入函数直接在 `.docx` 文件上原地操作，输入输出均为文件路径。剥离自原项目 `optimize.py`，无 FastAPI 依赖。

### 版头注入 `inject_header`

```python
from inject import inject_header

inject_header("文件.docx", {
    "org_name": "国家民委办公厅",       # 发文机关标志（红色30pt，居中）
    "doc_number": "民委办发〔2026〕1号",  # 发文字号（三号仿宋，居中）
    "signer": "张三",                  # 签发人姓名（与发文号同行右对齐，上行文）
})
```

版头顺序：发文机关标志 → 空二行 → 发文字号/签发人 → 红色反线（0.35mm 红色实线，`#E00000`）。

### 版记注入 `inject_footer`

```python
from inject import inject_footer

inject_footer("文件.docx", {
    "cc": "各省、自治区、直辖市民委",      # 抄送机关
    "printer": "国家民委办公厅",          # 印发机关
    "print_date": "2026年7月23日",        # 印发日期
})
```

版记顺序：上分隔线（0.35mm 黑色）→ 抄送行（左空一字，悬挂缩进）→ 细分隔线 → 印发机关+日期（左右空一字，日期制表位右对齐）→ 下分隔线。

版记自动计算末页剩余空间，不足 30mm 时强制分页。

### 页码注入 `inject_page_number`

```python
from inject import inject_page_number

# 居中
inject_page_number("文件.docx", {
    "format": "— {PAGE} —",
    "font": "宋体", "size": 14, "alignment": "center",
})

# 单右双左奇偶排版（右对齐，偶数页自动左对齐）
inject_page_number("文件.docx", {
    "alignment": "right",
})
```

使用 Word PAGE 域代码实现动态页码，支持 `{PAGE}` / `{NUMPAGES}` 占位符。`alignment="right"` 启动单右双左奇偶排版（直接操作 ZIP 添加偶数页页脚）。

### 一键注入（CLI）

```bash
# 单独命令
python gongwen.py header  in.docx --org-name "国家民委办公厅" --doc-number "民委办发〔2026〕1号"
python gongwen.py footer  in.docx --cc "各省民委" --printer "国家民委办公厅" --print-date "2026年7月23日"
python gongwen.py pagenum in.docx --alignment center --format "— {PAGE} —"

# optimize 一步到位（修复 + 注入）
python gongwen.py optimize in.docx -o out.docx --layout layout.json
```

`layout.json` 示例：
```json
{
  "header": {"org_name": "国家民委办公厅", "doc_number": "民委办发〔2026〕1号"},
  "footer": {"cc": "各省民委", "printer": "国家民委办公厅", "print_date": "2026年7月23日"},
  "page_number": {"format": "— {PAGE} —", "alignment": "center"}
}
```

## 规则 YAML 结构

```yaml
document_type: "notice"
template_name: "通知"
check_rules:
  - id: CHK-N001          # 约定：CHK-{类型前缀}{NNN}
    severity: P0           # P0=格式错误 P1=次要 P2=建议
    field: "title.font"    # DocumentModel 的点路径
    expected: "方正小标宋简体"
    name: "标题字体"
    message: "标题应使用方正小标宋简体"
fix_rules:
  - id: FIX-N001
    action: set_font
    target: title          # title|body|signature|page_setup|all
    value: "方正小标宋简体"
```

### 支持的修复动作（action）

| action | 作用 | value 示例 |
|--------|------|-----------|
| `set_font` | 设置字体（4 属性全设） | `"仿宋_GB2312"` |
| `set_size` | 设置字号 | `"16pt"` / `16` |
| `set_bold` | 加粗 | `true` |
| `set_alignment` / `set_align` | 对齐 | `center` / `justify` / `right` |
| `set_line_spacing` | 固定行距 | `"28.95pt"` |
| `set_line_spacing_multiple` | 倍数行距 | `1.5` |
| `set_first_line_indent` / `set_indent` | 首行缩进 | `"2em"` |
| `set_margins` / `set_page_margins` | 页边距 | `{top: "3.7cm", ...}` |
| `set_page_number` | 页码域 | `{font, size, alignment, format}` |
| `remove_extra_spaces` | 去多余空格 | — |
| `remove_extra_blank_lines` | 去多余空行 | — |
| `strip_markdown` / `convert_markdown` | 清除/转换 Markdown | — |
| `fix_bold_range` | 修正整段加粗 | — |
| `normalize_punctuation` | 标点规范化 | — |
| `normalize_headings` | 标题序号规范化 | — |

### 检查字段路径（field）前缀

| 前缀 | 检查对象 |
|------|---------|
| `doc_title.` / `heading_0.` | 公文大标题（level 0） |
| `heading_1.` ~ `heading_3.` | 各级标题 |
| `title.` | 主标题 |
| `body.` | 正文段落 |
| `page_setup.` | 页面设置 |
| `signature.` / `date.` | 落款/日期 |

## 三层规则优先级

```
official（仓库内，只读）
   < custom（~/.gongwen-skill/custom_rules/）
   < user  （~/.gongwen-skill/user_rules/）
```

深合并语义：`check_rules`/`fix_rules` 列表按 `field` / `(target, action)` 去重后合并，其余字典递归合并。可写目录可用环境变量 `GONGWEN_DATA_DIR` 覆盖。

自定义示例（覆盖正文字号为小三 15pt）：

```yaml
# ~/.gongwen-skill/user_rules/notice.yaml
body:
  size: 15
fix_rules:
  - id: FIX-USER-001
    action: set_size
    target: body
    value: "15pt"
```

## 韧性设计

- **AI 结构分析**：`ai_structure_analyzer` 对数据库/AI 的依赖全部函数内懒加载，且被 `parse_docx` 用 try/except 包裹——独立环境无 AI 配置时自动降级为纯启发式标题检测，不影响主流程。
- **字体校验熔断**：`generate_docx` 生成后自动校验字体，发现 MS Gothic 等无效字体即替换为合规字体，避免 Word 端乱码。
- **路径遍历防护**：`save_rule` / `delete_rule` 校验 key 仅含安全字符并做 `relative_to` 校验。

## 已知限制

- 依赖 `python-docx`，仅支持 `.docx`（不支持旧版 `.doc` 二进制格式，需先转换）。
- 字体渲染依赖运行环境安装了对应中文字体；未安装时 XML 属性正确但预览可能回退。
- AI 辅助标题分析在独立发行版中默认关闭（无 AI 配置），复杂无排版文档的标题识别以启发式为准。

## 许可证与出处

MIT License · (c) 2026 Jose AI · https://www.linhut.cn
源自开源项目「AI 公文智能优化助手」。
