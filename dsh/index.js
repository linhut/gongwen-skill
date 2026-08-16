// gongwen-skill DSH plugin bridge (v1.12.61+)
// (c) 2026 Jose AI (https://www.linhut.cn)  MIT License
//
// 分层架构：
// - Python CLI：纯工具层，通过 --config-overrides 接收规则覆盖 JSON
// - DSH 插件（本文件）：配置管理者 + AI 工作指引
//   * 读取 ~/.gongwen-skill/dsh-config.json 管理排版参数配置
//   * 每次 call() 自动注入 --config-overrides
//   * config 命令支持 show/set/get/reset/init
//   * setup() 注入 AI 工作指引（systemPrompt section）
//
// 纯 CLI 用户完全不受影响（不使用 DSH 插件时不会读取 dsh-config.json）

import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// DSH 插件配置文件路径
const APP_DATA_DIR = join(homedir(), ".gongwen-skill");
const CONFIG_FILE = join(APP_DATA_DIR, "dsh-config.json");
const DEFAULTS_FILE = join(resolve(__dirname, ".."), "etc", "dsh-config-defaults.json");

// AI 工作指引：帮助 Agent 理解 gongwen-skill 的能力和使用方式
const GONGWEN_GUIDANCE = `本机已安装 gongwen-skill 插件（中文公文全流程处理工具）。能力：.docx 公文按 GB/T 9704 国家标准做格式检查（check）、自动修复（optimize）、行内内容修订（optimize-content）、模板生成（template）、Markdown 转公文（md2docx）、版头/版记/页码注入。覆盖通知/请示/报告/函/会议纪要等 24 类公文。完全自包含，克隆即用，无需数据库或后端服务。用户提到「公文 / 红头文件 / 版式 / 排版 / 格式检查 / 公文模板 / 党政机关公文」时即指本插件。DSH 插件支持配置化排版参数（页边距/行距/字体等），配置文件位于 ~/.gongwen-skill/dsh-config.json，可通过 config 命令管理。`;

// 定位 gongwen CLI 真实安装根目录：plugin 包目录或 git clone 目录
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

// 把命令对象转为 args 数组（避免 shell 引号问题）
// positionalKeys: 该命令的位置参数名列表（如 template 的 "type"），不转为 --flag
function _to_cli_args(args, positionalKeys = []) {
  const cliArgs = [];
  const posSet = new Set(positionalKeys);
  // 先输出位置参数（按声明顺序）
  for (const pk of positionalKeys) {
    if (args[pk] !== undefined && args[pk] !== null && args[pk] !== false) {
      cliArgs.push(String(args[pk]));
    }
  }
  // 再输出 --flag 参数
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

// 各命令的位置参数定义（用于 _to_cli_args 正确处理位置参数 vs flag）
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
};

// 支持 --config-overrides 的命令列表
const CONFIG_OVERRIDE_COMMANDS = new Set([
  "template", "check", "optimize", "md2docx",
]);

// 支持 --doc-type 的命令列表（default_doc_type 仅对这些命令注入）
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

// 处理 config 命令（DSH 侧直接处理，不透传到 Python CLI）
function _handle_config(args) {
  const action = args.action || "show";

  if (action === "init") {
    // 从默认模板创建用户配置
    if (existsSync(CONFIG_FILE)) {
      return { success: false, error: `配置文件已存在: ${CONFIG_FILE}，如需重置请使用 action: 'reset'` };
    }
    const defaults = _read_defaults();
    // 移除注释字段
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
    // 尝试解析 value 为适当类型（数字、布尔、JSON 对象）
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
          parsed = value; // 保持字符串
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

export const name = "gongwen-skill";
export const description =
  "中文公文全流程处理工具 - GB/T 9704 格式检查/修复/内容优化/模板生成/版式注入";

export async function setup(ctx) {
  try {
    const projectRoot = _resolve_gongwen_root();
    if (ctx?.logger) {
      ctx.logger.info(`gongwen-skill plugin loaded (projectRoot=${projectRoot})`);
    }
    // 注入 AI 工作指引
    if (ctx?.systemPrompt?.section) {
      ctx.systemPrompt.section({
        name: "plugin:gongwen-skill",
        order: 100,
        text: GONGWEN_GUIDANCE,
      });
    }
  } catch (err) {
    if (ctx?.logger) ctx.logger.error(`gongwen-skill plugin setup failed: ${err.message}`);
  }
}

export async function call(ctx, args) {
  const { command, ...rest } = args;
  if (!command) {
    return { success: false, error: "missing required field: command" };
  }

  // config 命令由 DSH 侧直接处理，不透传到 Python CLI
  if (command === "config") {
    return _handle_config(rest);
  }

  let projectRoot;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch (err) {
    return { success: false, error: err.message };
  }

  // 读取 DSH 配置
  const config = _read_config();

  // 仅对支持 --config-overrides 的命令注入规则覆盖
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

  // 如果用户已经传了 --config-overrides，合并 DSH 配置（用户值优先级更高）
  if (configOverrides && rest["config-overrides"]) {
    try {
      const userOverrides = JSON.parse(rest["config-overrides"]);
      // 浅合并（用户值覆盖 DSH 配置的顶层键）
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
    // 用户传了 overrides 但没有 DSH 配置，直接用用户的
    configOverrides = null; // 已经在 rest 中
  }

  if (configOverrides) {
    rest["config-overrides"] = JSON.stringify(configOverrides);
  }

  // 支持 default_doc_type：当用户未指定 -t/--doc-type 时使用配置中的默认值
  // 仅对支持 --doc-type 的命令注入
  if (config?.default_doc_type && DOC_TYPE_COMMANDS.has(command) && !rest["doc-type"] && !rest["t"]) {
    rest["doc-type"] = config.default_doc_type;
  }

  const positionalKeys = POSITIONAL_ARGS[command] || [];
  const cliArgs = ["-m", "gongwen", command, ..._to_cli_args(rest, positionalKeys)];

  // 调用尊重 ctx.cwd（如果 DSH 传入会话工作目录），
  // 否则回退到项目根（用于 list-types 等只读命令）
  const cwd = ctx?.cwd || projectRoot;

  return await new Promise((resolve) => {
    const child = spawn("python", cliArgs, {
      cwd,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      windowsHide: true,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk.toString("utf-8")));
    child.stderr.on("data", (chunk) => (stderr += chunk.toString("utf-8")));
    child.on("error", (err) =>
      resolve({
        success: false,
        error: `python spawn failed: ${err.message}`,
        cli: `python ${cliArgs.join(" ")}`,
        cwd,
      }),
    );
    child.on("close", (code) => {
      if (code === 0) {
        // 尝试解析 JSON 输出
        const trimmed = stdout.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try {
            resolve({ success: true, data: JSON.parse(trimmed), stderr: stderr.trim() });
            return;
          } catch {
            // 非 JSON，保持原样
          }
        }
        resolve({ success: true, output: trimmed, stderr: stderr.trim() });
      } else {
        resolve({
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
