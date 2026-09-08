// 公文全流程处理工具 - DSH plugin bridge (gongwen-skill, v2.12.0+)
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 分层架构：
// - Python CLI：纯工具层，通过 --config-overrides 接收规则覆盖 JSON
// - DSH 插件 Host (本文件)：配置管理者 + AI 工作指引 + 模型工具 + 系统设置
//   * inject: ['tools'] — 官方 ctx.tools.register(defineTool(...)) 注册模型工具，
//     schema 自动流入系统提示词组装（无需手动拼接工具 schema）
//   * ctx.systemPrompt.section 注入 AI 工作指引（可选服务，缺失不阻塞）
//   * ctx.settings.register('gongwen-skill') 官方设置命名空间（schemastery schema），
//     scope.watch 回写 ~/.gongwen-skill/dsh-config.json 保持 CLI 兼容
//   * ctx.skills.register 运行时注册 SKILL.md（可选服务）
//   * call() 透传 Python CLI（向后兼容旧调用方）
//
// 官方依据：DeepSeek Harness Bluebook Developer Guide
//   - Host Services & Events：inject 硬依赖 / ctx.get 可选依赖 / ctx.effect 可逆副作用
//   - Registering Tools：defineTool + ctx.tools.register
//   - User Guide · Skills：ctx.skills.register(SkillRegistration)
// 纯 CLI 用户完全不受影响（不使用 DSH 插件时不会读取 dsh-config.json）

import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir, tmpdir } from "node:os";
import { defineTool } from "@deepseek-ai/dsh-tools";
import Schema from "@deepseek-ai/schemastery";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// DSH 插件配置文件路径（CLI 侧事实源；settings 命名空间是 DSH 侧编辑入口）
const APP_DATA_DIR = join(homedir(), ".gongwen-skill");
const CONFIG_FILE = join(APP_DATA_DIR, "dsh-config.json");
const DEFAULTS_FILE = join(resolve(__dirname, ".."), "etc", "dsh-config-defaults.json");

// settings 命名空间（官方要求小写 kebab-case；与浏览器卡片同名配对）
const SETTINGS_NS = "gongwen-skill";

// 系统提示段落名（官方约定 plugin:<name>，重复注册会抛错）
const SECTION_NAME = "plugin:gongwen-skill";
const SECTION_ORDER = 100;

// AI 工作指引（模型可见的能力说明；工具 schema 由 defineTool 自动注入）
const GONGWEN_GUIDANCE = `本机已安装公文全流程处理工具插件（gongwen-skill）。能力：.docx 公文全流程——列出公文类型（list-types）、解析文档（parse）、格式检查（check）、自动修复（optimize）、内容修订对比版（optimize-content）、模板生成（template）、样式学习（style-learn/style-list，从标准文档学习排版样式）、全面诊断（doctor）、自动修复（repair）、Markdown 转公文（md2docx）、JSON 模型生成（generate）、版头/版记/页码注入（header/footer/pagenum）、首句加粗（bold-first）、一键格式修复（fix-common）、桌签生成（table-signs）、审稿流转单（review）、完整审校（full-review）、文档审计（audit）、规则管理（rule-export/import/list）、版本自检（check-update）、会话交接（handoff）、字体管理（font）。覆盖通知/请示/报告/函/会议纪要等 25 类公文。完全自包含，克隆即用，无需数据库或后端服务。用户提到「公文 / 红头文件 / 版式 / 排版 / 格式检查 / 公文模板 / 样式学习 / 自定义模板 / 党政机关公文」时即指本插件。DSH 插件支持配置化排版参数（页边距/行距/字体等）：在系统设置 → 文档样式配置 中调整，写入官方 settings 命名空间并同步到 ~/.gongwen-skill/dsh-config.json。`;

// 定位 gongwen CLI 真实安装根目录
function _resolve_gongwen_root() {
  const projectRoot = resolve(__dirname, "..");
  if (existsSync(join(projectRoot, "gongwen", "__init__.py")) || existsSync(join(projectRoot, "pyproject.toml"))) {
    return projectRoot;
  }
  throw new Error(`\
gongwen-skill plugin bridge 无法定位 gongwen 包 \
(projectRoot=${projectRoot} 未找到 gongwen/__init__.py 或 pyproject.toml). \
请确认插件正确安装在 ~/.dsh/profiles/web/node_modules/gongwen-skill`);
}

// 把命令对象转为 args 数组
function _to_cli_args(args, positionalKeys = []) {
  const cliArgs = [];
  const posSet = new Set(positionalKeys);
  for (const pk of positionalKeys) {
    if (args[pk] !== undefined && args[pk] !== null && args[pk] !== false) {
      cliArgs.push(String(args[pk]));
    }
  }
  for (const [k, v] of Object.entries(args)) {
    if (posSet.has(k)) continue;
    if (v === undefined || v === null || v === false) continue;
    if (v === true) {
      cliArgs.push(`--${k}`);
    } else {
      cliArgs.push(`--${k}`, String(v));
    }
  }
  return cliArgs;
}

// 各命令的位置参数定义（CLI 是唯一业务入口，此处仅转发）
const POSITIONAL_ARGS = {
  template: ["type"],
  parse: ["input"],
  check: ["input"],
  optimize: ["input"],
  generate: ["input"],
  header: ["input"],
  footer: ["input"],
  pagenum: ["input"],
  md2docx: ["input"],
  "optimize-content": ["input"],
  "bold-first": ["input"],
  "fix-common": ["input"],
  "table-signs": ["input"],
  "full-review": ["input"],
  "style-learn": ["input"],
  audit: ["input"],
  review: ["doc_type"],
  "rule-export": ["type"],
  draft: ["input"],
  "rule-import": ["key"],
  font: ["action"],
};

// 支持 --config-overrides 的命令列表
const CONFIG_OVERRIDE_COMMANDS = new Set([
  "template", "check", "optimize", "md2docx",
]);

// 支持 --doc-type 的命令列表
const DOC_TYPE_COMMANDS = new Set([
  "check", "optimize", "md2docx", "full-review",
]);

// 读取 DSH 配置（每次调用时读取，支持热更新）
function _read_config() {
  try {
    if (!existsSync(CONFIG_FILE)) return null;
    const raw = readFileSync(CONFIG_FILE, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

// 读取默认配置模板
function _read_defaults() {
  try {
    if (!existsSync(DEFAULTS_FILE)) return {};
    return JSON.parse(readFileSync(DEFAULTS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

// 写入配置文件
function _write_config(config) {
  mkdirSync(APP_DATA_DIR, { recursive: true });
  writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2), "utf-8");
}

// 深度获取嵌套属性
function _deep_get(obj, path) {
  const keys = path.split(".");
  let cur = obj;
  for (const k of keys) {
    if (cur === null || cur === undefined || typeof cur !== "object") return undefined;
    cur = cur[k];
  }
  return cur;
}

// 深度设置嵌套属性
function _deep_set(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (cur[keys[i]] === undefined || cur[keys[i]] === null || typeof cur[keys[i]] !== "object") {
      cur[keys[i]] = {};
    }
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
}

// 处理 config 命令
function _handle_config(args) {
  const action = args.action || "show";

  if (action === "init") {
    if (existsSync(CONFIG_FILE)) {
      return { success: false, error: `配置文件已存在: ${CONFIG_FILE}，如需重置请使用 action: 'reset'` };
    }
    const defaults = _read_defaults();
    const config = {};
    for (const [k, v] of Object.entries(defaults)) {
      if (!k.startsWith("_")) config[k] = v;
    }
    _write_config(config);
    return { success: true, message: `配置已初始化: ${CONFIG_FILE}`, config };
  }

  if (action === "show") {
    const config = _read_config();
    if (!config) {
      return {
        success: true,
        message: `尚未创建配置文件。运行 config --action init 创建默认配置，或使用 --action set 设置单项。`,
        config_file: CONFIG_FILE,
        config: null,
      };
    }
    return { success: true, config, config_file: CONFIG_FILE };
  }

  if (action === "get") {
    const key = args.key;
    if (!key) return { success: false, error: "缺少 key 参数" };
    const config = _read_config() || _read_defaults();
    const value = _deep_get(config, key);
    return { success: true, key, value, config_file: CONFIG_FILE };
  }

  if (action === "set") {
    const key = args.key;
    const value = args.value;
    if (!key) return { success: false, error: "缺少 key 参数" };
    let config = _read_config();
    if (!config) {
      const defaults = _read_defaults();
      config = {};
      for (const [k, v] of Object.entries(defaults)) {
        if (!k.startsWith("_")) config[k] = v;
      }
    }
    let parsed = value;
    if (typeof value === "string") {
      if (value === "true") parsed = true;
      else if (value === "false") parsed = false;
      else if (/^-?\d+(\.\d+)?$/.test(value)) parsed = parseFloat(value);
      else {
        try {
          const obj = JSON.parse(value);
          parsed = obj;
        } catch {
          parsed = value;
        }
      }
    }
    _deep_set(config, key, parsed);
    _write_config(config);
    return { success: true, message: `已设置 ${key} = ${JSON.stringify(parsed)}`, config };
  }

  if (action === "reset") {
    const defaults = _read_defaults();
    const config = {};
    for (const [k, v] of Object.entries(defaults)) {
      if (!k.startsWith("_")) config[k] = v;
    }
    _write_config(config);
    return { success: true, message: `配置已重置为默认值: ${CONFIG_FILE}`, config };
  }

  return { success: false, error: `未知的 config action: ${action}` };
}

// 构建系统设置 Schema（schemastery 官方 API：Schema.object / Schema.string ...）
function _build_settings_schema() {
  return Schema.object({
    default_doc_type: Schema.string().default("notice").description("默认公文类型"),
    page_setup: Schema.object({
      margins: Schema.object({
        top: Schema.string().default("2.8cm").description("上边距"),
        bottom: Schema.string().default("2.8cm").description("下边距"),
        left: Schema.string().default("2.7cm").description("左边距"),
        right: Schema.string().default("2.7cm").description("右边距"),
      }).description("页边距"),
      header_distance: Schema.string().default("1.5cm").description("页眉距"),
      footer_distance: Schema.string().default("2.3cm").description("页脚距"),
    }).description("页面设置"),
    body: Schema.object({
      font: Schema.string().default("仿宋_GB2312").description("正文字体"),
      font_fallback: Schema.string().default("FangSong").description("字体回退"),
      size: Schema.string().default("16pt").description("正文字号"),
      line_spacing: Schema.string().default("33pt").description("行距"),
      first_line_indent: Schema.string().default("2em").description("首行缩进"),
      align: Schema.string().default("justify").description("对齐方式"),
    }).description("正文格式"),
    doc_title: Schema.object({
      font: Schema.string().default("方正小标宋简体").description("标题字体"),
      font_fallback: Schema.string().default("SimSun").description("字体回退"),
      size: Schema.string().default("22pt").description("标题字号"),
      align: Schema.string().default("center").description("对齐方式"),
      bold: Schema.boolean().default(false).description("是否加粗"),
      line_spacing: Schema.string().default("33pt").description("行距"),
    }).description("公文标题"),
    heading_1: Schema.object({
      font: Schema.string().default("黑体").description("一级标题字体"),
      font_fallback: Schema.string().default("SimHei").description("字体回退"),
      size: Schema.string().default("16pt").description("字号"),
      line_spacing: Schema.string().default("33pt").description("行距"),
      first_line_indent: Schema.string().default("2em").description("首行缩进"),
    }).description("一级标题"),
    heading_2: Schema.object({
      font: Schema.string().default("楷体_GB2312").description("二级标题字体"),
      font_fallback: Schema.string().default("KaiTi").description("字体回退"),
      size: Schema.string().default("16pt").description("字号"),
      line_spacing: Schema.string().default("33pt").description("行距"),
      first_line_indent: Schema.string().default("2em").description("首行缩进"),
    }).description("二级标题"),
    heading_3: Schema.object({
      font: Schema.string().default("仿宋_GB2312").description("三级标题字体"),
      font_fallback: Schema.string().default("FangSong").description("字体回退"),
      size: Schema.string().default("16pt").description("字号"),
      bold: Schema.boolean().default(true).description("是否加粗"),
      line_spacing: Schema.string().default("33pt").description("行距"),
      first_line_indent: Schema.string().default("2em").description("首行缩进"),
    }).description("三级标题"),
    signature: Schema.object({
      font: Schema.string().default("仿宋_GB2312").description("署名字体"),
      font_fallback: Schema.string().default("FangSong").description("字体回退"),
      size: Schema.string().default("18pt").description("署名字号"),
      align: Schema.string().default("center").description("对齐方式"),
    }).description("署名格式"),
  });
}

// 运行一条 gongwen CLI 命令（call() 与模型工具 execute 共用）
// @param command - gongwen 命令名
// @param args - CLI 参数对象（键名即参数名，含位置参数）
// @param options - { cwd?, signal? }
async function runCli(command, args = {}, options = {}) {
  let projectRoot;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch (err) {
    return { success: false, error: err.message };
  }

  const { cwd = projectRoot, signal } = options;
  const rest = { ...args };

  // 读取 DSH 配置并注入 --config-overrides（仅支持的命令）
  const config = _read_config();
  let configOverrides = null;
  if (config && CONFIG_OVERRIDE_COMMANDS.has(command)) {
    configOverrides = {};
    for (const [k, v] of Object.entries(config)) {
      if (!k.startsWith("_") && k !== "default_doc_type") {
        configOverrides[k] = v;
      }
    }
    if (Object.keys(configOverrides).length === 0) {
      configOverrides = null;
    }
  }

  // 合并用户传的 overrides（用户值优先级更高）
  if (configOverrides && rest["config-overrides"]) {
    try {
      const userOverrides = JSON.parse(rest["config-overrides"]);
      for (const k of Object.keys(userOverrides)) {
        if (typeof configOverrides[k] === "object" && typeof userOverrides[k] === "object") {
          configOverrides[k] = { ...configOverrides[k], ...userOverrides[k] };
        } else {
          configOverrides[k] = userOverrides[k];
        }
      }
    } catch {
      // 用户传的 JSON 无效，保持 DSH 配置
    }
  } else if (rest["config-overrides"]) {
    configOverrides = null;
  }

  if (configOverrides) {
    rest["config-overrides"] = JSON.stringify(configOverrides);
  }

  // 支持 default_doc_type
  if (config?.default_doc_type && DOC_TYPE_COMMANDS.has(command) && !rest["doc-type"] && !rest["t"]) {
    rest["doc-type"] = config.default_doc_type;
  }

  const positionalKeys = POSITIONAL_ARGS[command] || [];
  const cliArgs = ["-m", "gongwen", command, ..._to_cli_args(rest, positionalKeys)];

  return await new Promise((resolvePromise) => {
    const child = spawn("python", cliArgs, {
      cwd,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      windowsHide: true,
    });
    const abort = () => child.kill();
    signal?.addEventListener("abort", abort, { once: true });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk.toString("utf-8")));
    child.stderr.on("data", (chunk) => (stderr += chunk.toString("utf-8")));
    child.on("error", (err) => {
      signal?.removeEventListener("abort", abort);
      resolvePromise({
        success: false,
        error: `python spawn failed: ${err.message}`,
        cli: `python ${cliArgs.join(" ")}`,
        cwd,
      });
    });
    child.on("close", (code) => {
      signal?.removeEventListener("abort", abort);
      if (code === 0) {
        const trimmed = stdout.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try {
            resolvePromise({ success: true, data: JSON.parse(trimmed), stderr: stderr.trim() });
            return;
          } catch {
            // 非 JSON
          }
        }
        resolvePromise({ success: true, output: trimmed, stderr: stderr.trim() });
      } else {
        resolvePromise({
          success: false,
          exit_code: code,
          output: stdout.trim(),
          stderr: stderr.trim(),
          cli: `python ${cliArgs.join(" ")}`,
          cwd,
        });
      }
    });
  });
}


// Agent 预设安装：把插件包内 presets/（preset.yml + agent.cordis.yml）同步到
// ~/.dsh/.agent-presets/gongwen-skill/，使 DSH Web 新建会话可选「公文全流程处理专家」预设。
// 参照官方插件模式（np-ppt）：每次 apply 幂等同步；用户自行修改过的预设会被插件版本覆盖，
// 如需自定义可从该预设 copy 出新预设再改。
function ensurePresetInstalled() {
  try {
    const userPresetDir = join(homedir(), ".dsh", ".agent-presets", "gongwen-skill");
    mkdirSync(userPresetDir, { recursive: true });
    const pluginPresets = join(resolve(__dirname, ".."), "presets");
    const presetYml = join(pluginPresets, "preset.yml");
    const agentYml = join(pluginPresets, "agent.cordis.yml");
    if (existsSync(presetYml)) {
      copyFileSync(presetYml, join(userPresetDir, "preset.yml"));
    }
    if (existsSync(agentYml)) {
      copyFileSync(agentYml, join(userPresetDir, "agent.cordis.yml"));
    }
  } catch {
    // 预设安装失败不阻塞插件其余能力
  }
}

// 模型工具参数 → CLI 参数对象（camel/snake → CLI kebab 映射）
function toolArgsToCli(args) {
  const out = {};
  // extra：JSON 对象字符串（模型按 description 构造），解析失败则忽略
  if (typeof args.extra === "string" && args.extra.trim() !== "") {
    try {
      const parsed = JSON.parse(args.extra);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        Object.assign(out, parsed);
      }
    } catch {
      // 非 JSON 忽略（execute 层会报告）
    }
  }
  const map = {
    input: "input",
    output: "output",
    docType: "doc-type",
    template: "template",
    style: "style",
    mode: "mode",
    changes: "changes",
    apply: "apply",
    json: "json",
  };
  for (const [key, cliKey] of Object.entries(map)) {
    const v = args[key];
    if (v !== undefined && v !== null) out[cliKey] = v;
  }
  return out;
}

// 工具输出渲染（模型可见）
function renderToolResult(_args, value) {
  if (typeof value === "string") {
    return [{ type: "text", text: value }];
  }
  return [{ type: "text", text: JSON.stringify(value, null, 2) }];
}

// 注册官方模型工具（defineTool + ctx.tools.register，schema 自动流入系统提示词）
function registerGongwenTool(ctx) {
  ctx.tools.register(defineTool({
    name: "gongwen",
    description:
      "运行公文全流程处理工具（gongwen-skill）CLI 命令：check（格式检查）、optimize（自动修复）、optimize-content（内容修订对比版）、md2docx（Markdown 转公文）、template（模板生成）、style-learn（样式学习）、list-types（列出公文类型）、doctor（全面诊断）、handoff（会话交接）等。",
    parameters: {
      command: {
        type: "string",
        required: true,
        description:
          "要执行的 gongwen 命令名，如 check、optimize、optimize-content、md2docx、template、style-learn、list-types、doctor、handoff。",
      },
      input: { type: "string", description: "输入文件路径（多数命令的位置参数）" },
      output: { type: "string", description: "输出文件路径（-o / --output）" },
      docType: {
        type: "string",
        description: "公文类型（--doc-type / -t）：notice、request、report、letter、meeting-minutes 等；运行 list-types 查看全部",
      },
      template: { type: "string", description: "样式模板名（--template，style-learn 学到的命名模板）" },
      style: { type: "string", description: "内容优化风格（--style）" },
      mode: { type: "string", description: "修订模式（--mode），如 tracked" },
      changes: { type: "string", description: "内容变更 JSON 文件路径（--changes）" },
      apply: { type: "boolean", description: "直接应用、跳过确认（--apply / -y）" },
      json: { type: "boolean", description: "输出 JSON（--json）" },
      extra: {
        type: "string",
        description:
          "其余 CLI 参数透传，JSON 对象字符串：键为参数名（不含 -- 前缀），值为字符串、数字或布尔。例如 {\"doc-type\":\"notice\",\"style\":\"庄重严谨\"}。",
      },
    },
    output: {
      schema: { type: "object", additionalProperties: true },
      render: renderToolResult,
    },
    async execute(args, exec) {
      if (!args.command) {
        return { success: false, error: "缺少必填参数：command" };
      }
      // config 命令由 DSH 侧直接处理
      if (args.command === "config") {
        return _handle_config(args.extra || {});
      }
      return await runCli(args.command, toolArgsToCli(args), { signal: exec?.signal });
    },
  }));
}

export const name = "gongwen-skill";
export const description =
  "中文公文全流程处理工具 - GB/T 9704 格式检查/修复/内容优化/模板生成/版式注入";

// 硬依赖：tools（模型工具注册需要）。systemPrompt / settings / skills 为可选服务，
// 分别用 ctx.get / ctx.inject 处理，避免在未挂载对应提供方的组合中阻塞插件加载。
export const inject = ["tools"];

// apply() — Cordis 生命周期管理（所有注册均为可逆副作用）
export function apply(ctx) {
  const disposers = [];

  // 软探测 gongwen 根目录：找不到仅记录，不阻塞插件自身注册
  // （工具/设置/skill 注册不依赖项目根；call/runCli 才需要）
  let projectRoot = null;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch {
    ctx.logger?.warn?.("gongwen-skill: gongwen 包未定位，CLI 调用将在执行时失败");
  }

  try {
    // 1. 注册官方模型工具（inject 硬依赖，fiber dispose 自动注销）
    try {
      registerGongwenTool(ctx);
    } catch (e) {
      ctx.logger?.warn?.(`gongwen-skill: tool registration failed: ${e.message}`);
    }

    // 2. 注入 AI 工作指引（可选服务 ctx.systemPrompt）
    const sp = ctx.get("systemPrompt");
    if (sp?.section) {
      try {
        const d = sp.section({
          name: SECTION_NAME,
          order: SECTION_ORDER,
          text: GONGWEN_GUIDANCE,
        });
        if (typeof d === "function") disposers.push(d);
      } catch (e) {
        ctx.logger?.warn?.(`gongwen-skill: system prompt registration failed: ${e.message}`);
      }
    }

    // 3. 注册官方设置命名空间（ctx.settings 为可选服务，延迟注入，缺失不阻塞）
    try {
      ctx.inject(["settings"], (settingsCtx) => {
        try {
          const schema = _build_settings_schema();
          const scope = settingsCtx.settings.register(SETTINGS_NS, schema, { applies: "live" });

          // 一次性迁移：dsh-config.json → settings 命名空间（仅当用户层为空）
          try {
            const legacy = _read_config();
            if (legacy) {
              const desc = settingsCtx.settings
                .describe({ redactSecrets: true })
                .find((d) => d.ns === SETTINGS_NS);
              const userEmpty = !desc || !desc.user || Object.keys(desc.user).length === 0;
              if (userEmpty) void scope.update(legacy);
            }
          } catch {
            // 迁移失败不影响注册
          }

          // watch：settings 变更 → 回写 dsh-config.json（CLI 侧事实源，保持兼容）
          const off = scope.watch((next) => {
            try {
              _write_config(next);
            } catch (e) {
              console.error("[gongwen-skill] settings sync failed:", e);
            }
          });
          disposers.push(off);
          ctx.logger?.info?.("gongwen-skill: settings namespace registered");
        } catch (e) {
          console.error("[gongwen-skill] settings registration failed:", e);
        }
      });
    } catch (e) {
      console.error("[gongwen-skill] settings inject failed:", e);
    }

    // 4. 注册 runtime skill（可选服务 ctx.skills，使 AI 安装后即可自动发现）
    const skills = ctx.get("skills");
    if (skills?.register) {
      try {
        const skillPath = join(resolve(__dirname, ".."), "SKILL.md");
        if (existsSync(skillPath)) {
          const skillContent = readFileSync(skillPath, "utf-8");
          const skillD = skills.register({
            name: "gongwen-skill",
            description:
              "中文公文全流程处理：格式检查/自动修复/content润色/模板生成/样式学习/Markdown转公文/版头版记注入",
            content: skillContent,
            resourceBase: { kind: "directory", path: resolve(__dirname, "..") },
            invocation: { modelInvocable: true, userInvocable: true },
          });
          if (typeof skillD === "function") disposers.push(skillD);
          ctx.logger?.info?.("gongwen-skill: runtime skill registered");
        }
      } catch (e) {
        ctx.logger?.warn?.(`gongwen-skill: runtime skill registration skipped: ${e.message}`);
      }
    }

    // 5. 安装 Agent 预设（presets/ → ~/.dsh/.agent-presets/gongwen-skill/，
    //    让 DSH 新建会话可选「公文全流程处理专家」；失败不影响插件其余能力）
    ensurePresetInstalled();

    ctx.logger?.info?.(`gongwen-skill plugin loaded${projectRoot ? ` (projectRoot=${projectRoot})` : "（gongwen 包未定位）"}`);
  } catch (err) {
    ctx.logger?.error?.(`gongwen-skill plugin apply failed: ${err.message}`);
  }

  // 注册全部 disposer 到 ctx.effect（确保可逆）
  ctx.effect(() => {
    return () => {
      for (const d of disposers) {
        try {
          if (typeof d === "function") d();
        } catch {}
      }
    };
  }, "gongwen-skill: apply cleanup");
}

// call() — 透传 Python CLI（保留向后兼容）
export async function call(ctx, args) {
  const { command, ...rest } = args;
  if (!command) {
    return { success: false, error: "missing required field: command" };
  }

  // config 命令由 DSH 侧直接处理
  if (command === "config") {
    return _handle_config(rest);
  }

  return await runCli(command, rest, { cwd: ctx?.cwd });
}
