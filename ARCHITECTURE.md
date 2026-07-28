<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# gongwen-skill 项目全流梳理

本文档从**业务流**、**数据流**、**逻辑流**、**代码流**四个维度对项目进行全面梳理，是理解、使用和扩展本项目的完整参考。

---

## 目录

- [一、业务流（用户/Agent 视角）](#一业务流用户agent-视角)
  - [1.1 三种用户路径](#11-三种用户路径)
  - [1.2 Agent 三点式路由](#12-agent-三点式路由)
  - [1.3 场景 → 路径映射表](#13-场景--路径映射表)
  - [1.4 会议场景增强流程](#14-会议场景增强流程)
- [二、数据流（文档处理管线）](#二数据流文档处理管线)
  - [2.1 核心管道](#21-核心管道)
  - [2.2 DocumentModel 中间表示](#22-documentmodel-中间表示)
  - [2.3 数据隔离边界](#23-数据隔离边界)
  - [2.4 文件级操作（注入）](#24-文件级操作注入)
- [三、逻辑流（规则与决策）](#三逻辑流规则与决策)
  - [3.1 规则引擎生命周期](#31-规则引擎生命周期)
  - [3.2 三层规则优先级合并](#32-三层规则优先级合并)
  - [3.3 检查→修复管线](#33-检查修复管线)
  - [3.4 桌签批量生成逻辑](#34-桌签批量生成逻辑)
- [四、代码流（模块与依赖）](#四代码流模块与依赖)
  - [4.1 文件级模块图](#41-文件级模块图)
  - [4.2 依赖关系矩阵](#42-依赖关系矩阵)
  - [4.3 扩展点与定制入口](#43-扩展点与定制入口)
  - [4.4 测试覆盖地图](#44-测试覆盖地图)

---

## 一、业务流（用户/Agent 视角）

### 1.1 三种用户路径

本 skill 为用户（或 AI Agent）提供三条独立的操作路径，每条的产物和操作方式完全不同：

```
                                  ┌──────────────────────────────────────┐
                                  │           用户输入/文档               │
                                  │  .docx 文件 / Markdown 文本 / 口语描述 │
                                  └──────────┬───────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
            ┌──────────────┐       ┌──────────────────┐     ┌──────────────────────┐
            │ 路径 A       │       │  路径 B           │     │  路径 C              │
            │ 格式修复      │       │  内容优化          │     │  生成公文             │
            │              │       │                  │     │                      │
            │ 不改文字      │       │  润色文字+对比版   │     │  从零创建新文档        │
            │ 只修排版      │       │  红色标注+删除线   │     │  四步流水线            │
            │              │       │  每段修改说明      │     │                      │
            │ 输出：无标记   │       │  输出：修订对比    │     │  输出：新公文 .docx   │
            │ 成品 .docx   │       │  .docx            │     │                      │
            └──────┬───────┘       └────────┬─────────┘     └──────────┬───────────┘
                   │                        │                         │
                   ▼                        ▼                         ▼
            ┌──────────────┐       ┌──────────────────┐     ┌──────────────────────┐
            │ optimize     │       │ optimize-content  │     │ md2docx + optimize   │
            │ check→fix→gen│       │ changes JSON→diff │     │ 草稿→排版→成品       │
            └──────────────┘       └──────────────────┘     └──────────────────────┘
```

### 1.2 Agent 三点式路由

AI Agent 根据用户输入自动选择路径。SKILL.md 定义了三句话分流规则：

| 用户行为 | 关键提示词 | → 路径 | CLI 入口 | 产物特征 |
|----------|-----------|--------|---------|---------|
| 上传/指定了文档 | "排版"/"格式"/"红头"/"标准化" | **A 格式修复** | `optimize` | 无标记成品 |
| 上传/指定了文档 | "润色"/"优化"/"改写"/"修改措辞" | **B 内容优化** | `optimize-content` | 红删+红增+说明 |
| 没有文档 | "写一份"/"生成"/"起草" + 公文类型 | **C 生成公文** | `md2docx` → `optimize` | 新公文 |

**交互铁律**：Agent 必须先确认用户走哪条路，不得自动猜测路径。若用户说"帮我优化一下"，必须追问是改格式还是改内容。

### 1.3 场景 → 路径映射表

| 用户场景 | 推荐路径 | 命令序列 | 耗时预估 |
|----------|---------|---------|---------|
| 检查格式是否合规 | A（只读） | `check` | 2s |
| 调整字体/字号/页边距 | A | `optimize --apply` | 5s |
| 注入版头/版记/页码 | A(增强) | `optimize --layout` | 5s |
| 润色文字表达 | B | 生成 changes → `optimize-content --apply` | 30s+LLM |
| 从头写一份通知 | C | 搜集背景→写草稿→md2docx→optimize→check | 60s+LLM |
| 草稿→正式公文 | C | `md2docx` → `optimize` | 8s |
| 批量生成会议桌签 | 独立 | `table-signs 名单.txt -o ./桌签/` | 3s |
| 导出规则做二次定制 | 独立 | `rule-export notice -o my_rules.yaml` | 1s |
| 导入单位自定义规则 | 独立 | `rule-import my_company -f my_rules.yaml` | 1s |

### 1.4 会议场景增强流程

当 Agent 识别到用户正在处理**会议通知、纪要、会议方案、议题材料**等会议类文档时，业务流自动扩展为：

```
主文档生成/处理
     │
     ├── 强制：生成参会人员报名表（附件）
     │
     ├── 询问：是否需要同步生成会议桌签？
     │    ├── 用户有名单 → python gongwen.py table-signs 名单.txt -o ./桌签/
     │    ├── 用户无名但有姓名 → 索取名单后生成
     │    └── 用户不需要 → 跳过（仅问一次）
     │
     └── 完成交付
```

---

## 二、数据流（文档处理管线）

### 2.1 核心管道

所有文档处理经过统一的核心管线，分 4 个阶段：

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    核心管道（4 阶段）                       │
                    └─────────────────────────────────────────────────────────────┘

  .docx 输入
     │
     ▼
┌──────────┐      ┌──────────────────┐      ┌────────────┐      ┌──────────┐
│ 阶段 1    │      │ 阶段 2            │      │ 阶段 3      │      │ 阶段 4   │
│ PARSING   │─────▶│ INTERMEDIATE MODEL│─────▶│ CHECK/FIX  │─────▶│ GENERATE │
│           │      │                  │      │            │      │          │
│ parser.py │      │ DocumentModel    │      │ checker.py │      │ generator│
│ parser_   │      │ (Pydantic)       │      │ fixer.py   │      │ .py      │
│ format.py │      │                  │      │            │      │          │
│           │      │ paragraphs[]     │      │ modifier.py│      │ font_    │
│ font_     │      │ tables[]         │      │            │      │ utils.py │
│ utils.py  │      │ page_setup       │      │ engine.py  │      │          │
│           │      │ headers/footers  │      │ (orchestr.)│      │          │
└──────────┘      └──────────────────┘      └────────────┘      └──────────┘
     │                                                              │
     │  仅阶段 1 和阶段 4 接触 python-docx                           │
     │  阶段 2、3 只操作 Pydantic Model，纯逻辑无 I/O                 │
     ▼                                                              ▼
  .docx 输入                                                        .docx 输出
```

**管线决策树**：

```
输入 → parse  → DocumentModel  ──┬── check ──→ CheckIssue[]（只读路径）
                                  │
                                  ├── check_and_fix → (issues, fixed_model)
                                  │
                                  └── generate ──→ .docx 输出
```

### 2.2 DocumentModel 中间表示

所有模块不直接操作 python-docx 对象，全部经过 Pydantic JSON 模型。

```
DocumentModel
 ├── metadata: DocumentMetadata       ← 标题/作者/创建日期
 ├── page_setup: PageSetup            ← 纸张/页边距/方向
 ├── paragraphs: list[Paragraph]      ← 段落列表（核心数据）
 │    ├── text: str                   ← 纯文本内容
 │    ├── role: str | None            ← 段落角色（title/body/signature/date/recipient...）
 │    ├── is_heading: bool            ← 是否为标题
 │    ├── heading_level: int | None   ← 标题层级 1-9
 │    ├── runs: list[Run]             ← Run 级别样式
 │    │    ├── text: str
 │    │    └── format: RunFormat      ← font_name/font_size_pt/bold/color/strikethrough
 │    └── format: ParagraphFormat     ← 段落级样式（对齐/缩进/行距/间距）
 ├── tables: list[Table]              ← 表格
 ├── headers: list[HeaderFooter]      ← 页眉
 └── footers: list[HeaderFooter]      ← 页脚（含页码信息）
```

**关键设计原则**：Pydantic 的 `model_dump_json()` / `model_validate_json()` 支持完整的 JSON 序列化/反序列化，方便调试、缓存和跨进程传递。

### 2.3 数据隔离边界

```
┌──────────────────────────────────────────────────────────────┐
│                   CLI 边界 (gongwen.py)                       │
│  argparse 解析 → 分派到 cmd_* 函数 → 输出格式化（print/JSON） │
├──────────────────────────────────────────────────────────────┤
│                   引擎接口层                                   │
│  RuleEngine (engine.py)        ← 规则检查/修复的统一入口       │
│  create_diff_document()         ← 路径 B 差异文档生成         │
│  inject_header/footer/pagenum   ← 文件级注入操作              │
├──────────────────────────────────────────────────────────────┤
│                   核心数据层（Pydantic Model）                 │
│  所有模块不直接操作 python-docx，只操作 DocumentModel          │
├───────────────────┬────────────────────┬─────────────────────┤
│   解析层           │   生成层            │   规则层             │
│  parser.py        │  generator.py      │  checker.py         │
│  parser_format.py │  font_utils.py     │  fixer.py           │
│                   │                    │  loader.py          │
│                   │                    │  manager.py         │
│                   │                    │  engine.py          │
└───────────────────┴────────────────────┴─────────────────────┘
```

### 2.4 文件级操作（注入）

版头/版记/页码注入不走核心管道，直接在 `.docx` 文件上原地操作：

```
                  inject_header/footer/pagenum
                           │
                    .docx ZIP → 修改 XML → 保存
                           │
                    (不经过 DocumentModel)
```

**注入内容**：
- **版头**：发文机关标志（红色30pt居中）+ 发文字号 + 签发人 + 红色反线（0.35mm `#E00000`）
- **版记**：上分隔线 → 抄送行 → 细分隔线 → 印发机关+日期 → 下分隔线（自动计算末页空间，不足30mm强制分页）
- **页码**：Word PAGE 域代码 + 单右双左奇偶排版

---

## 三、逻辑流（规则与决策）

### 3.1 规则引擎生命周期

```
┌─────────┐    ┌───────────┐    ┌─────────┐    ┌────────┐
│ 初始化   │    │ 加载规则   │    │ 执行检查 │    │ 执行修复 │
│         │    │           │    │         │    │        │
│ new     │───▶│ load_     │───▶│ engine  │───▶│ engine │
│ RuleEng │    │ rules_    │    │ .check()│    │ .fix() │
│ ine()   │    │ merged()  │    │         │    │        │
└─────────┘    └───────────┘    └─────────┘    └────────┘
                    │                              │
                    ▼                              ▼
           ┌──────────────┐              ┌─────────────────┐
           │ YAML 三层合并 │              │ modifier 函数调用│
           │ (load_rules) │              │ (apply_fixes)   │
           └──────────────┘              └─────────────────┘
```

### 3.2 三层规则优先级合并

```
load_rules_merged("notice")
     │
     ├── [Layer 1] rules/official/_common.yaml     ← 所有类型共享 GB/T 9704 基准
     │   └── check_rules (29 条: 页边距/字体/字号/行距/缩进/对齐)
     │   └── fix_rules  (23 条: 对应所有 check 的修复动作)
     │
     ├── [Layer 1] rules/official/notice.yaml       ← 类型特化（覆盖/追加 common）
     │   └── check_rules (1 条: 通知结语检查)
     │   └── fix_rules  (空: 内容级检查，无自动化修复)
     │
     ├── [Layer 2] ~/.gongwen-skill/custom_rules/   ← 单位级定制
     │
     └── [Layer 3] ~/.gongwen-skill/user_rules/     ← 用户级最高优先级

合并语义:
  - check_rules: 按 field 去重（同 field 后层覆盖前层）
  - fix_rules: 按 (target, action) 去重
  - 普通字段: 递归合并（字典内递归，标量覆盖）
```

### 3.3 检查→修复管线

```
check_document(model, rules)
  │
  ├── _check_title(model, ...)         ← 公文大标题（字体/字号/对齐/行距）
  ├── _check_heading_level(model, ...)  ← 一/二/三级标题
  ├── _check_body(model, ...)           ← 正文（字体/字号/行距/缩进/对齐）
  ├── _check_page_setup(model, ...)     ← 页边距/纸张
  ├── _check_signature_area(model, ...) ← 落款/日期
  └── _check_common_issues(model)       ← 多余空行/多余空格/段落角色
       │
       ▼
  返回: list[CheckIssue] (P0/P1/P2 分级)

apply_fixes(model, rules)
  │
  ├── for each fix_rule in fix_rules:
  │    ├── get handler from _ACTION_MAP
  │    ├── handler(model, target, value, rules)
  │    └── → modify_*() / remove_*() / normalize_*()
  │
  └── 返回: fixed DocumentModel

_ACTION_MAP (当前支持 18 种 action):
  set_font / set_size / set_bold / set_alignment / set_align
  set_line_spacing / set_line_spacing_multiple
  set_first_line_indent / set_indent
  set_margins / set_page_margins
  remove_extra_spaces / remove_extra_blank_lines
  strip_markdown / convert_markdown
  fix_bold_range / normalize_punctuation / normalize_headings
  set_page_number
```

### 3.4 桌签批量生成逻辑

桌签生成是独立于核心管线的特化业务逻辑，不走 DocumentModel 管道：

```
table-signs 名单.txt
    │
    ├── parse_name_list(text)          ← 解析多行/逗号/空格/顿号分隔名单
    │
    ├── [独立模式] _prepare_docx_from_template()
    │    ├── 复制桌签.dotx → 输出文件
    │    ├── 读取 ZIP 中 word/document.xml
    │    ├── 查找 w:t 中 "Jose AI" 占位符
    │    ├── 替换为 _format_name(姓名)  ← 两字名自动加空格
    │    ├── 调整 w:sz 字号 = _calc_font_size(len)  ← 字数多自动缩小
    │    └── 写回 ZIP → 每人一份 .docx
    │
    └── [合并模式] _duplicate_body_for_combined()
         ├── 解析模板 body 结构
         ├── 为 N 人复制 N 份 body 内容
         ├── 每份替换占位符 + 调整字号
         ├── 每份之间插分页符
         └── 写回 ZIP → 单文件多页
```

---

## 四、代码流（模块与依赖）

### 4.1 文件级模块图

```
gongwen-skill/
│
├── gongwen.py                        ← CLI 入口（774 行，13+1 个子命令）
│   ├── __version__ = "1.10.0"         ← 版本号唯一来源
│   ├── _detect_doc_type()            ← 类型关键词推断
│   ├── _build_output_name()          ← 文件命名规范
│   ├── cmd_* × 13                     ← 每个子命令的处理函数
│   └── main() → argparse dispatch    ← 参数解析与路由
│
├── engine/                           ← 引擎根目录
│   ├── config.py                     ← 路径配置（BASE_DIR/APP_DATA_DIR）
│   ├── inject.py                     ← 版头/版记/页码注入（~580 行）
│   ├── optimizer.py                  ← 路径 B 差异对比文档（~678 行）
│   ├── template_builder.py           ← 模板 DocumentModel 生成（~391 行）
│   ├── table_sign_generator.py       ← 桌签批量生成（~299 行，新增）
│   │
│   ├── core/                         ← 核心子包
│   │   ├── __init__.py
│   │   │
│   │   ├── document/                 ← 文档解析/生成/修改
│   │   │   ├── __init__.py
│   │   │   ├── models.py             ← Pydantic 数据模型（8 个类）
│   │   │   ├── parser.py             ← docx → DocumentModel（~714 行）
│   │   │   ├── parser_format.py      ← 格式解析辅助（Run/Paragraph 格式化）
│   │   │   ├── generator.py          ← DocumentModel → docx（~948 行）
│   │   │   ├── modifier.py           ← DocumentModel 修改操作（~1037 行）
│   │   │   ├── font_utils.py         ← 字体设置/检测/回退（~374 行）
│   │   │   ├── editor.py             ← 文本差异对比引擎（~565 行）
│   │   │   ├── ai_structure_analyzer.py  ← AI 结构分析（父项目残留）
│   │   │   └── structure_analyzer.py ← 启发式结构分析（~323 行）
│   │   │
│   │   └── rules/                    ← 规则引擎
│   │       ├── __init__.py
│   │       ├── engine.py             ← RuleEngine 整配器（~63 行）
│   │       ├── loader.py             ← YAML 单文件加载（~69 行）
│   │       ├── manager.py            ← 三层合并/保存/验证（~287 行）
│   │       ├── checker.py            ← 检查逻辑（~490 行）
│   │       └── fixer.py              ← 修复逻辑（~179 行）
│   │
│   └── utils/
│       └── logger.py                 ← RotatingFileHandler 日志配置
│
├── rules/official/                   ← 23 份规则 YAML（_common + 22 类型）
│   ├── _common.yaml                  ← GB/T 9704 基准：check(29) + fix(23)
│   ├── notice.yaml / request.yaml    ← 类型特化：check(1-3条) + fix(0-3条)
│   └── ... (共 23 文件)
│
├── prompts/                          ← AI Agent 提示词
│   ├── style-prompts.md              ← 6 套公文语言风格 + 通用底座
│   └── usage-prompts.md              ← Agent 使用指引（最小可用命令集）
│
├── SKILL.md                          ← AI Skill 声明（1950 行，含全部路由逻辑）
├── README.md                         ← GitHub 首页文档
├── REFERENCE.md                      ← 编程调用参考手册
├── WORKFLOW.md                       ← 工作流梳理（本文档前身）
├── ARCHITECTURE.md                   ← 本文档（全流梳理）
├── Makefile                           ← 开发工作流（install/test/check/clean/version）
├── pytest.ini                        ← pytest 配置
├── tests/                            ← 测试套件（4 文件，34 用例）
│   ├── test_models.py
│   ├── test_rules.py
│   ├── test_font_utils.py
│   └── test_pipeline.py
│
├── requirements.txt                  ← python-docx + pydantic + pyyaml
├── LICENSE                           ← MIT
└── logo/                             ← 封面图片
```

### 4.2 依赖关系矩阵

| 模块 | 依赖 | 被依赖 | 说明 |
|------|------|--------|------|
| `models.py` | pydantic | **全部模块** | 无业务依赖，最底层 |
| `font_utils.py` | python-docx | parser / generator / optimizer | 字体 4 属性设置 |
| `parser_format.py` | models / font_utils | parser | 格式解析辅助 |
| `parser.py` | models / font_utils / parser_format / structure_analyzer | CLI / optimizer / editor | 外部输入唯一入口 |
| `generator.py` | models / font_utils | CLI / optimizer / editor | 外部输出唯一出口 |
| `modifier.py` | models | fixer / CLI | 所有修改操作汇聚点 |
| `checker.py` | models | engine | 只读检查 |
| `fixer.py` | models / modifier | engine | 翻译 YAML → modifier 调用 |
| `loader.py` | yaml / config | manager | YAML 读取 |
| `manager.py` | loader / config | engine / CLI (rule-*) | 三层合并 + CRUD |
| `engine.py` | manager / checker / fixer | CLI (check/optimize) | 规则编排 |
| `config.py` | 无 | loader / manager / logger | 纯路径配置 |
| `inject.py` | python-docx / font_utils | CLI (header/footer/pagenum) | 独立文件操作 |
| `optimizer.py` | models / parser / generator / font_utils | CLI (optimize-content) | 路径 B |
| `table_sign_generator.py` | lxml / zipfile | CLI (table-signs) | 独立于核心管道 |
| `template_builder.py` | models | CLI (template) | 模板生成 |
| `gongwen.py` | **全部 engine 模块** | — | CLI 入口，无被依赖 |

### 4.3 扩展点与定制入口

| 扩展点 | 位置 | 方式 | 无需改代码 |
|--------|------|------|-----------|
| **单位字体/字号定制** | `~/.gongwen-skill/user_rules/*.yaml` | 写 YAML 覆盖同名字段 | ✅ |
| **新增公文类型** | `rules/official/{type}.yaml` | 参考 notice.yaml 写规则 | ✅（需重启） |
| **新增 fix action** | `fixer.py:_ACTION_MAP` + `modifier.py` | 添加映射 + 实现函数 | ❌ |
| **文件命名规则** | `gongwen.py:_build_output_name()` | 修改函数逻辑 | ❌ |
| **桌签字号映射** | `table_sign_generator.py:_calc_font_size()` | 修改 sizes 字典 | ✅ |
| **可写目录路径** | 环境变量 `GONGWEN_DATA_DIR` | 设置环境变量 | ✅ |
| **版式注入（layout）** | `layout.json` | 写 JSON 配置文件 | ✅ |

### 4.4 测试覆盖地图

```
tests/
├── test_models.py      (10 用例)  ← models.py: RunFormat/Run/Paragraph/DocumentModel 创建+序列化
├── test_rules.py       (13 用例)  ← manager.py: 合并逻辑/验证/优先级; loader.py: 全部类型加载
├── test_font_utils.py   (7 用例)  ← font_utils.py: CJK检测/字体回退/验证
└── test_pipeline.py     (3 用例)  ← parser+generator+engine: 端到端冒烟测试
```

**当前覆盖率盲区**（建议优先补充）：

| 模块 | 行数 | 测试覆盖 | 风险 |
|------|:----:|:--------:|------|
| `inject.py` | 580 | ❌ 无 | 版头/版记/页码注入逻辑 |
| `editor.py` | 565 | ❌ 无 | 路径 B 差异对比核心 |
| `modifier.py` | 1037 | ❌ 无 | convert_markdown/bold_range 等复杂逻辑 |
| `optimizer.py` | 678 | ❌ 无 | create_diff_document 核心 |
| `generator.py` | 948 | ✅ 冒烟 | 仅测试了基本生成，未测复杂表格/页眉页脚 |
| `parser.py` | 714 | ✅ 冒烟 | 仅测试了基本解析，未测复杂文档 |
| `table_sign_generator.py` | 299 | ❌ 无 | 直接操作 ZIP/XML，需测试边界情况 |

---

## 附录：版本匹配速查

| 版本 | 日期 | 关键业务变更 | 关键数据流变更 | 关键逻辑流变更 | 关键代码流变更 |
|------|------|-------------|---------------|---------------|---------------|
| v1.0 | 2026-07-24 | 初始三路径 | 管道架构定型 | 规则引擎 v1 | 初始代码库 |
| v1.9.3 | 2026-07-28 | 桌签批量生成 | XML/ZIP 级操作 | `_format_name` + `_calc_font_size` | table_sign_generator.py |
| v1.9.3 | 2026-07-28 | CLI 添加 `--version` | — | — | gongwen.py +4 行 |
| v1.9.3 | 2026-07-28 | 测试框架 | — | 深合并/验证/冒烟 | tests/ × 4 + pytest.ini |
| v1.9.3 | 2026-07-28 | 清理父项目残留 | — | 移除全局单例 + AI 降级 | engine.py -24 行; parser.py |
| v1.10.0 | 2026-07-28 | 桌签模板对齐 + 字号自适应 + 全流梳理 | 名字加空格 + 字号自适应 | `_format_name` + `_calc_font_size` | table_sign_generator.py; ARCHITECTURE.md |
