<!--
(c) 2026 Jose AI (https://www.linhut.cn)
Licensed under the MIT License. See the LICENSE file for details.
-->

# gongwen-skill 工作流梳理

本文档梳理项目的完整工作流体系，涵盖**数据处理流水线**、**CLI 调用流程**、**规则加载流程**、**开发工作流**四个维度。

---

## 一、数据处理流水线（核心架构）

```
                      ┌─────────────────┐
                      │   .docx 输入文件  │
                      └────────┬────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │    parse_docx    │  ← parser.py
                     │  (docx → Model)  │
                     └────────┬────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │  DocumentModel   │  ← models.py (Pydantic)
                     │  (JSON 中间表示)  │
                     │                  │
                     │ paragraphs[]     │
                     │ tables[]         │
                     │ page_setup       │
                     │ headers/footers  │
                     └──┬────┬────┬─────┘
                        │    │    │
              ┌─────────┘    │    └──────────┐
              ▼              ▼               ▼
      ┌────────────┐ ┌────────────┐ ┌──────────────┐
      │ check_doc  │ │ fix_model  │ │ generate_docx│
      │ (只读)      │ │ (修改 Model)│ │ (Model→docx) │
      └─────┬──────┘ └─────┬──────┘ └──────┬───────┘
            │              │               │
            ▼              ▼               ▼
      ┌──────────┐  ┌──────────┐   ┌──────────────┐
      │CheckIssue│  │Fixed Doc│   │ .docx 输出文件 │
      │  列表     │  │  Model   │   └──────────────┘
      └──────────┘  └──────────┘
```

**关键设计原则**：
- 所有操作经过 **DocumentModel（Pydantic）** 中间表示——无模块直接操作 python-docx 对象
- parse/generate 是唯二与 python-docx 打交道的模块
- check/fix 只操作 JSON Model，纯逻辑无 I/O

---

## 二、CLI 调用流程（用户视角）

```
gongwen.py
  │
  ├── 信息类（只读）
  │   ├── list-types        → 列出 22 种公文类型
  │   ├── --version         → 显示版本号
  │   └── rule-list         → 列出三层规则文件
  │
  ├── 输入类（docx → Model）
  │   ├── parse             → docx → JSON (DocumentModel)
  │   └── check             → docx → 解析 → 检查问题列表（只读，安全）
  │
  ├── 转换类（中间→输出）
  │   ├── md2docx           → Markdown(FrontMatter) → 格式化 .docx
  │   └── generate          → DocumentModel JSON → .docx
  │
  ├── 修复类（Model → Model → docx）
  │   ├── optimize          → check + fix + generate（预览模式默认，--apply 执行）
  │   ├── optimize-content  → 内容优化差异对比（--changes JSON + --apply）
  │   └── bold-first        → 正文段落首句加粗
  │
  ├── 模板类
  │   └── template          → 按类型生成标准空白模板
  │
  ├── 版式注入类（直接修改 .docx）
  │   ├── header            → 注入版头（发文机关标志 + 文号 + 红色反线）
  │   ├── footer            → 注入版记（抄送 + 印发机关 + 日期 + 分隔线）
  │   └── pagenum           → 注入 Word PAGE 域动态页码
  │
  └── 规则管理类
      ├── rule-export       → 导出合并后的 YAML 规则
      ├── rule-list         → 列出所有规则源
      └── rule-import       → 导入自定义规则 YAML
```

### 三条路径（AI Agent 路由）

| 路径 | 用途 | CLI 入口 | 输出特征 |
|------|------|----------|----------|
| **A** 格式修复 | 不改文字，只修排版 | `optimize` | 无标记成品文档 |
| **B** 内容优化 | 润色文字，出对比版 | `optimize-content` | 红色标注+删除线+修改说明 |
| **C** 生成公文 | 从零生成新公文 | `template` + `md2docx` + `optimize` | 四步流程 |

---

## 三、规则加载流程（三层优先级）

```
load_rules_merged(doc_type)
  │
  ├── Layer 1: official/        ← 仓库内 rules/official/*.yaml（只读）
  │   ├── _common.yaml          ← 所有类型共享（字体/页边距/行距）
  │   └── {doc_type}.yaml       ← 类型特化规则（覆盖/补充 common）
  │
  ├── Layer 2: custom/          ← ~/.gongwen-skill/custom_rules/*.yaml
  │   └── {doc_type}.yaml       ← 同名字段覆盖 official
  │
  └── Layer 3: user/            ← ~/.gongwen-skill/user_rules/*.yaml
      └── {doc_type}.yaml       ← 最高优先级，覆盖前两层
```

**合并语义**：
- `check_rules` 按 `field` 去重→覆盖
- `fix_rules` 按 `(target, action)` 去重→覆盖
- 普通字典递归合并（override > base）
- 可写目录可用 `GONGWEN_DATA_DIR` 环境变量覆盖

---

## 四、开发工作流

### 前置条件
```bash
# 1. 克隆
git clone https://github.com/linhut/gongwen-skill.git
cd gongwen-skill

# 2. 安装依赖
pip install -r requirements.txt
pip install pytest          # 测试需要
```

### 常用命令
```bash
# 运行全部测试
make test
# 等价于：python -m pytest tests/ -v --tb=short

# 快速验证 CLI
python gongwen.py --version
python gongwen.py list-types
python gongwen.py template notice -o /tmp/test.docx

# 完整管道验证
python gongwen.py check /tmp/test.docx
python gongwen.py optimize /tmp/test.docx -o /tmp/out.docx --apply

# 清理缓存
make clean
```

### 测试体系（新增于 v1.11.0）
```
tests/
├── test_models.py      # Pydantic 模型创建、序列化/反序列化
├── test_rules.py       # 规则合并逻辑、验证函数、所有类型加载
├── test_font_utils.py  # CJK 检测、字体回退
└── test_pipeline.py    # parse→generate 冒烟测试（需 python-docx）
```

运行：`make test` 或 `python -m pytest tests/ -v`

### 提交与合并
```bash
# 提交前必须通过测试
python -m pytest tests/ --tb=short

# 代码审查维度
# - P0: 功能正确性（parse/fix/generate 不崩溃）
# - P1: 字体/字号/页边距合规
# - P2: 文档整洁度
```

---

## 五、数据流中的隔离边界

```
┌─────────────────────────────────────────────────────────┐
│                    CLI 层 (gongwen.py)                    │
│  argparse + 13个子命令 + 输出格式化（print/JSON）          │
├─────────────────────────────────────────────────────────┤
│                    引擎接口层                              │
│  RuleEngine (engine/core/rules/engine.py)                │
│  create_diff_document (engine/optimizer.py)              │
│  inject_header/footer/page_number (engine/inject.py)     │
├─────────────────────────────────────────────────────────┤
│                   核心数据层                              │
│  DocumentModel (Pydantic) — 唯一中间表示                  │
│  Paragraph / Run / ParagraphFormat / RunFormat           │
├──────────────────┬──────────────────┬───────────────────┤
│  解析层           │  生成层           │  规则层            │
│  parser.py       │  generator.py    │  checker.py       │
│  parser_format.py│  font_utils.py   │  fixer.py         │
│                  │                   │  loader.py        │
│                  │                   │  manager.py       │
└──────────────────┴──────────────────┴───────────────────┘
```

---

## 六、版本历史工作流

| 版本 | 日期 | 关键变更 |
|------|------|----------|
| v1.0 | 2026-07-24 | 初始版本 |
| v1.9.3 | 2026-07-28 | 修复命令名、添加测试框架、添加 --version、添加 Makefile |
| v1.10.0 | 2026-07-28 | 桌签模板对齐、字号自适应、全面架构文档、清理父项目残留 |
| v1.11.0 | 2026-07-29 | 审稿机制融入路径B/C流程、ARCHITECTURE.md 审稿增强JSON格式 |

---

## 七、工作流改进路线图

| 优先级 | 改进项 | 说明 |
|--------|--------|------|
| P0 | 补齐更多类型 fix_rules | 当前仅 _common.yaml 有 fix_rules，各类型特化规则只有 check 无 fix |
| P0 | 集成 CI（GitHub Actions） | 每次 push 自动运行 pytest |
| P1 | 覆盖率提升 | 当前 ~34 个测试，目标覆盖 parser/generator 边界情况 |
| P1 | 重构 cmd_md2docx | 当前 156 行，可拆分为 FrontMatter 解析 + 模型构建 + 文件生成 |
| P2 | CLI 管道链式调用 | 支持 `gongwen check file.docx | gongwen optimize ...` |
| P2 | 批量处理 | 支持 glob 模式一次处理多个 .docx |
