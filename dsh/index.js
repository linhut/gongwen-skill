// 公文全流程处理工具 - DSH plugin bridge (gongwen-skill, v2.0.0+)
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 分层架构：
// - Python CLI：纯工具层，通过 --config-overrides 接收规则覆盖 JSON
// - DSH 插件 Host (本文件)：配置管理者 + AI 工作指引 + Web API 路由 + 系统设置
//   * apply() 生命周期管理（ctx.effect 全部可逆）
//   * installSettingsSection + schemastery Schema 校验
//   * webServer 路由：/plugins/gongwen-skill/api/config (GET/POST)
//   * call() 透传 Python CLI + 自动注入 --config-overrides
//   * config 命令支持 show/set/get/reset/init
//   * systemPrompt section 注入 AI 工作指引
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

// AI 工作指引
const GONGWEN_GUIDANCE = `本机已安装公文全流程处理工具插件（gongwen-skill）。能力：.docx 公文全流程——列出公文类型（list-types）、解析文档（parse）、格式检查（check）、自动修复（optimize）、内容修订对比版（optimize-content）、模板生成（template）、样式学习（style-learn/style-list，从标准文档学习排版样式）、全面诊断（doctor，21 项自检）、自动修复（repair）、Markdown 转公文（md2docx）、JSON 模型生成（generate）、版头/版记/页码注入（header/footer/pagenum）、首句加粗（bold-first）、一键格式修复（fix-common）、桌签生成（table-signs）、审稿流转单（review）、完整审校（full-review）、文档审计（audit）、规则管理（rule-export/import/list）、版本自检（check-update）、会话交接（handoff）、字体管理（font）。覆盖通知/请示/报告/函/会议纪要等 24 类公文。完全自包含，克隆即用，无需数据库或后端服务。用户提到「公文 / 红头文件 / 版式 / 排版 / 格式检查 / 公文模板 / 样式学习 / 自定义模板 / 党政机关公文」时即指本插件。DSH 插件支持配置化排版参数（页边距/行距/字体等），配置文件位于 ~/.gongwen-skill/dsh-config.json，可通过 config 命令或 DSH 系统设置→插件配置管理。`;

// Web API 路由前缀
const API_PREFIX = "/plugins/gongwen-skill/api";

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

// 各命令的位置参数定义
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

// HTTP JSON 响应工具
function _json_response(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
  });
  res.end(body);
}

// 构建系统设置 Schema（schemastery 格式）
function _build_settings_schema() {
  // 尝试动态 import schemastery
  try {
    const z = require("schemastery");
    return z.object({
      default_doc_type: z.string().default("notice").description("默认公文类型"),
      page_setup: z.object({
        margins: z.object({
          top: z.string().default("2.8cm").description("上边距"),
          bottom: z.string().default("2.8cm").description("下边距"),
          left: z.string().default("2.7cm").description("左边距"),
          right: z.string().default("2.7cm").description("右边距"),
        }).description("页边距"),
        header_distance: z.string().default("1.5cm").description("页眉距"),
        footer_distance: z.string().default("2.3cm").description("页脚距"),
      }).description("页面设置"),
      body: z.object({
        font: z.string().default("仿宋_GB2312").description("正文字体"),
        font_fallback: z.string().default("FangSong").description("字体回退"),
        size: z.string().default("16pt").description("正文字号"),
        line_spacing: z.string().default("33pt").description("行距"),
        first_line_indent: z.string().default("2em").description("首行缩进"),
        align: z.string().default("justify").description("对齐方式"),
      }).description("正文格式"),
      doc_title: z.object({
        font: z.string().default("方正小标宋简体").description("标题字体"),
        font_fallback: z.string().default("SimSun").description("字体回退"),
        size: z.string().default("22pt").description("标题字号"),
        align: z.string().default("center").description("对齐方式"),
        bold: z.boolean().default(false).description("是否加粗"),
        line_spacing: z.string().default("33pt").description("行距"),
      }).description("公文标题"),
      heading_1: z.object({
        font: z.string().default("黑体").description("一级标题字体"),
        font_fallback: z.string().default("SimHei").description("字体回退"),
        size: z.string().default("16pt").description("字号"),
        line_spacing: z.string().default("33pt").description("行距"),
        first_line_indent: z.string().default("2em").description("首行缩进"),
      }).description("一级标题"),
      heading_2: z.object({
        font: z.string().default("楷体_GB2312").description("二级标题字体"),
        font_fallback: z.string().default("KaiTi").description("字体回退"),
        size: z.string().default("16pt").description("字号"),
        line_spacing: z.string().default("33pt").description("行距"),
        first_line_indent: z.string().default("2em").description("首行缩进"),
      }).description("二级标题"),
      heading_3: z.object({
        font: z.string().default("仿宋_GB2312").description("三级标题字体"),
        font_fallback: z.string().default("FangSong").description("字体回退"),
        size: z.string().default("16pt").description("字号"),
        bold: z.boolean().default(true).description("是否加粗"),
        line_spacing: z.string().default("33pt").description("行距"),
        first_line_indent: z.string().default("2em").description("首行缩进"),
      }).description("三级标题"),
      signature: z.object({
        font: z.string().default("仿宋_GB2312").description("署名字体"),
        font_fallback: z.string().default("FangSong").description("字体回退"),
        size: z.string().default("18pt").description("署名字号"),
        align: z.string().default("center").description("对齐方式"),
      }).description("署名格式"),
    });
  } catch {
    return null;
  }
}

export const name = "gongwen-skill";
export const description =
  "中文公文全流程处理工具 - GB/T 9704 格式检查/修复/内容优化/模板生成/版式注入";

// apply() — Cordis 生命周期管理（ctx.effect 全部可逆）
export function apply(ctx) {
  const disposers = [];

  try {
    const projectRoot = _resolve_gongwen_root();

    // 1. 注入 AI 工作指引
    if (ctx?.systemPrompt?.section) {
      const d = ctx.systemPrompt.section({
        name: "plugin:gongwen-skill",
        order: 100,
        text: GONGWEN_GUIDANCE,
      });
      if (d) disposers.push(d);
    }

    // 2. 注册系统设置（installSettingsSection）
    const settings = ctx.get("settings");
    if (settings && typeof settings.register === "function") {
      try {
        const schema = _build_settings_schema();
        if (schema) {
          const scope = settings.register("gongwen-skill", schema, {
            description: "公文排版参数配置（页边距/字体/行距等）",
          });
          if (scope) {
            // 同步：settings → dsh-config.json
            if (scope.onChange) {
              scope.onChange((val) => {
                try {
                  const config = {};
                  for (const [k, v] of Object.entries(val)) {
                    if (!k.startsWith("_")) config[k] = v;
                  }
                  _write_config(config);
                } catch (e) {
                  console.error("[gongwen-skill] settings sync failed:", e);
                }
              });
            }
            // setSource：从 dsh-config.json 读取初始值
            if (scope.setSource) {
              const config = _read_config();
              if (config) scope.setSource(() => config);
            }
          }
        }
      } catch (e) {
        console.error("[gongwen-skill] settings registration failed:", e);
      }
    }

    // 3. 注册 Web API 路由
    const webServer = ctx.get("webServer");
    if (webServer && typeof webServer.register === "function") {
      try {
        // GET /plugins/gongwen-skill/api/config — 获取当前配置
        const d1 = webServer.register({
          kind: "exact",
          path: `${API_PREFIX}/config`,
          method: "GET",
          handler: (req, res) => {
            const config = _read_config();
            const defaults = _read_defaults();
            _json_response(res, 200, {
              ok: true,
              config: config || defaults,
              config_file: CONFIG_FILE,
              defaults_file: DEFAULTS_FILE,
            });
          },
        });
        if (d1) disposers.push(d1);

        // POST /plugins/gongwen-skill/api/config — 更新配置
        const d2 = webServer.register({
          kind: "exact",
          path: `${API_PREFIX}/config`,
          method: "POST",
          handler: (req, res) => {
            let body = "";
            req.on("data", (chunk) => (body += chunk));
            req.on("end", () => {
              try {
                const patch = JSON.parse(body);
                let config = _read_config() || {};
                // 浅合并顶层 + 深合并嵌套对象
                for (const [k, v] of Object.entries(patch)) {
                  if (typeof v === "object" && !Array.isArray(v) && typeof config[k] === "object") {
                    config[k] = { ...config[k], ...v };
                  } else {
                    config[k] = v;
                  }
                }
                _write_config(config);
                _json_response(res, 200, { ok: true, config });
              } catch (e) {
                _json_response(res, 400, { ok: false, error: e.message });
              }
            });
          },
        });
        if (d2) disposers.push(d2);

        // GET /plugins/gongwen-skill/api/defaults — 获取默认配置
        const d3 = webServer.register({
          kind: "exact",
          path: `${API_PREFIX}/defaults`,
          method: "GET",
          handler: (req, res) => {
            _json_response(res, 200, { ok: true, defaults: _read_defaults() });
          },
        });
        if (d3) disposers.push(d3);

        // GET /plugins/gongwen-skill/api/version — 获取版本信息
        const d4 = webServer.register({
          kind: "exact",
          path: `${API_PREFIX}/version`,
          method: "GET",
          handler: (req, res) => {
            try {
              const root = _resolve_gongwen_root();
              const pyproject = readFileSync(join(root, "pyproject.toml"), "utf-8");
              const m = pyproject.match(/version\s*=\s*"([^"]+)"/);
              _json_response(res, 200, {
                ok: true,
                version: m ? m[1] : "unknown",
                package: "gongwen-skill",
              });
            } catch (e) {
              _json_response(res, 500, { ok: false, error: e.message });
            }
          },
        });
        if (d4) disposers.push(d4);
      } catch (e) {
        console.error("[gongwen-skill] webServer route registration failed:", e);
      }
    }

    // 4. 注册 runtime skill（自动激活，使 AI 可在安装后自动发现并使用）
    if (ctx?.skills?.register) {
      try {
        const skillPath = join(resolve(__dirname, ".."), "SKILL.md");
        if (existsSync(skillPath)) {
          const skillContent = readFileSync(skillPath, "utf-8");
          const skillD = ctx.skills.register({
            name: "gongwen-skill",
            description: "中文公文全流程处理：格式检查/自动修复/content润色/模板生成/样式学习/Markdown转公文/版头版记注入",
            content: skillContent,
            resourceBase: { kind: "directory", path: resolve(__dirname, "..") },
            invocation: { modelInvocable: true, userInvocable: true },
          });
          if (skillD) disposers.push(skillD);
          if (ctx?.logger) ctx.logger.info("gongwen-skill: runtime skill registered");
        }
      } catch (e) {
        if (ctx?.logger) ctx.logger.warn(`gongwen-skill: runtime skill registration skipped: ${e.message}`);
      }
    }

    if (ctx?.logger) {
      ctx.logger.info(`gongwen-skill plugin loaded (projectRoot=${projectRoot})`);
    }
  } catch (err) {
    if (ctx?.logger) ctx.logger.error(`gongwen-skill plugin apply failed: ${err.message}`);
  }

  // 注册全部 disposer 到 ctx.effect（确保可逆）
  ctx.effect(() => {
    return () => {
      for (const d of disposers) {
        try { if (typeof d === "function") d(); } catch {}
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
        const trimmed = stdout.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try {
            resolve({ success: true, data: JSON.parse(trimmed), stderr: stderr.trim() });
            return;
          } catch {
            // 非 JSON
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
