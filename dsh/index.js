// 公文全流程处理专家 - DSH plugin bridge (gongwen-skill, v2.17.0+)
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 兼容目标：DSH 0.1.2+ ~ 0.2.3+（含预发布线）
// 设计要点（0.2.x 适配）：
// 1) 设置双路径（能力探测，不做版本判断）
//    - 0.2.x：Config(schemastery, volatile) 即设置文档数据源 + ctx.settings.configure({auto:false})
//    - 0.1.x：ctx.settings.register(ns, schema) + scope.watch
//    两条路径都把值镜像到 ~/.gongwen-skill/dsh-config.json（CLI 侧兼容，派生缓存）
// 2) SDK 惰性解析：defineTool / schemastery 缺失时降级，不让整个插件加载失败
// 3) 子进程硬化：解释器探测 / 超时 / 输出上限 / 进程树终止
// 4) 参数归一化：camelCase → kebab-case（修 call() 传 docType 会拼成 --docType）
//
// 不影响其他 Agent 运行：本文件只被 DSH 加载；不改变 CLI 参数、输出与 SKILL.md。

import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, readFileSync, writeFileSync, mkdirSync, copyFileSync, renameSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require_ = createRequire(import.meta.url);

// ── SDK 惰性解析（optional peer 不应导致插件加载失败）────────────────────────
let defineTool = (def) => def;
let Schema = null;
try {
  const tools = require_("@deepseek-ai/dsh-tools");
  if (typeof tools?.defineTool === "function") defineTool = tools.defineTool;
} catch {
  // 宿主未提供：原生定义对象同样可被 ctx.tools.register 接受
}
try {
  const sm = require_("@deepseek-ai/schemastery");
  Schema = sm?.default ?? sm ?? null;
  if (!Schema?.object) Schema = null;
} catch {
  Schema = null;
}

// DSH 插件配置文件路径（CLI 侧事实缓存；settings 命名空间是 DSH 侧编辑入口）
// GONGWEN_CONFIG_DIR 可重定向（测试隔离 / 多环境共存）
const APP_DATA_DIR = process.env.GONGWEN_CONFIG_DIR || join(homedir(), ".gongwen-skill");
const CONFIG_FILE = join(APP_DATA_DIR, "dsh-config.json");
const DEFAULTS_FILE = join(resolve(__dirname, ".."), "etc", "dsh-config-defaults.json");

// settings 命名空间（官方要求小写 kebab-case；与客户端设置页同名配对）
const SETTINGS_NS = "gongwen-skill";

// 系统提示段落名（官方约定 plugin:<name>，重复注册会抛错）
const SECTION_NAME = "plugin:gongwen-skill";
const SECTION_ORDER = 100;

// AI 工作指引（模型可见的能力说明；工具 schema 由注册表自动注入）
const GONGWEN_GUIDANCE = `本机已安装公文全流程处理专家 插件（gongwen-skill）。能力：.docx 公文全流程——列出公文类型（list-types）、解析文档（parse）、格式检查（check）、自动修复（optimize）、内容修订对比版（optimize-content）、模板生成（template）、样式学习（style-learn/style-list）、全面诊断（doctor）、自动修复（repair）、Markdown 转公文（md2docx）、JSON 模型生成（generate）、版头/版记/页码注入（header/footer/pagenum）、首句加粗（bold-first）、一键格式修复（fix-common）、桌签生成（table-signs）、审稿流转单（review）、完整审校（full-review）、文档审计（audit）、规则管理（rule-export/import/list）、版本自检（check-update）、会话交接（handoff）、字体管理（font）。覆盖通知/请示/报告/函/会议纪要等 25 类公文。完全自包含，无需数据库或后端服务。用户提到「公文 / 红头文件 / 版式 / 排版 / 格式检查 / 公文模板 / 样式学习 / 自定义模板 / 党政机关公文」时即指本插件。DSH 插件支持配置化排版参数（页边距/行距/字体等）：在 系统设置 → 文档样式配置 中调整，写入官方 settings 命名空间并同步到 ~/.gongwen-skill/dsh-config.json。`;

// ── Config：0.2.x 设置文档数据源 ─────────────────────────────────────────────
// volatile() 在 0.1.x 的 schemastery 上不存在，这里做无操作降级。
const _vol = (node) => (typeof node?.volatile === "function" ? node.volatile() : node);

export const Config = Schema
  ? Schema.object({
    default_doc_type: _vol(Schema.string().default("notice").description("默认公文类型")),
    page_setup: Schema.object({
      margins: Schema.object({
        top: _vol(Schema.string().default("2.8cm").description("上边距")),
        bottom: _vol(Schema.string().default("2.8cm").description("下边距")),
        left: _vol(Schema.string().default("2.7cm").description("左边距")),
        right: _vol(Schema.string().default("2.7cm").description("右边距")),
      }).description("页边距"),
    }).description("页面设置"),
    output: Schema.object({
      overwrite: _vol(Schema.boolean().default(false).description("允许覆盖已有输出文件")),
      keep_backup: _vol(Schema.boolean().default(true).description("覆盖前保留 .bak 备份")),
    }).description("输出行为"),
  })
  : undefined;

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

// camelCase / snake_case → kebab-case（CLI 参数名唯一形态）
function _kebab(key) {
  return String(key)
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/_/g, "-")
    .toLowerCase();
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
  for (const [rawKey, v] of Object.entries(args)) {
    if (posSet.has(rawKey) || rawKey === "extra") continue;
    if (v === undefined || v === null || v === false) continue;
    const key = _kebab(rawKey);
    if (key.startsWith("_")) continue;
    if (v === true) {
      cliArgs.push(`--${key}`);
    } else {
      cliArgs.push(`--${key}`, String(v));
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
  "template", "check", "optimize", "md2docx", "draft", "full-review",
]);

// 支持 --doc-type 的命令列表
const DOC_TYPE_COMMANDS = new Set([
  "check", "optimize", "md2docx", "full-review", "draft",
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

// 写入配置文件（原子：临时文件 + rename）
function _write_config(config) {
  mkdirSync(APP_DATA_DIR, { recursive: true });
  const body = JSON.stringify(config, null, 2);
  const tmp = `${CONFIG_FILE}.tmp-${process.pid}`;
  try {
    writeFileSync(tmp, body, "utf-8");
    renameSync(tmp, CONFIG_FILE);
  } catch {
    // 网络盘 / 被占用时退回直接覆盖
    writeFileSync(CONFIG_FILE, body, "utf-8");
  }
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

// 深度合并（只覆盖 patch 中出现的键，保留页眉距/正文格式等未管理字段）
function _deep_merge(base, patch) {
  if (patch === null || patch === undefined || typeof patch !== "object" || Array.isArray(patch)) return patch;
  const out = (base && typeof base === "object" && !Array.isArray(base)) ? { ...base } : {};
  for (const [k, v] of Object.entries(patch)) {
    if (v !== null && typeof v === "object" && !Array.isArray(v)) out[k] = _deep_merge(out[k], v);
    else out[k] = v;
  }
  return out;
}

// 把 Config 引用（volatile 的 .get()）摊平为纯 JSON
function _materialize(value, depth = 0) {
  if (value === null || value === undefined || depth > 8) return value;
  if (typeof value === "function") return undefined;
  if (typeof value === "object" && typeof value.get === "function" && typeof value.set === "function") {
    try {
      return _materialize(value.get(), depth + 1);
    } catch {
      return undefined;
    }
  }
  if (Array.isArray(value)) return value.map((v) => _materialize(v, depth + 1));
  if (typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (k.startsWith("_")) continue;
      const next = _materialize(v, depth + 1);
      if (next !== undefined) out[k] = next;
    }
    return out;
  }
  return value;
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
        message: "尚未创建配置文件。运行 config --action init 创建默认配置，或使用 --action set 设置单项。",
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
          parsed = JSON.parse(value);
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

// 0.1.x 兼容的命名空间 schema（0.2.x 用导出的 Config）
function _build_settings_schema() {
  if (!Schema) return undefined;
  return Schema.object({
    default_doc_type: Schema.string().default("notice").description("默认公文类型"),
    page_setup: Schema.object({
      margins: Schema.object({
        top: Schema.string().default("2.8cm").description("上边距"),
        bottom: Schema.string().default("2.8cm").description("下边距"),
        left: Schema.string().default("2.7cm").description("左边距"),
        right: Schema.string().default("2.7cm").description("右边距"),
      }).description("页边距"),
    }).description("页面设置"),
  });
}

// settings → dsh-config.json 镜像（派生缓存，原子写 + 去抖）
let _syncTimer = null;
let _lastSynced = null;
function _mirrorToCliConfig(config, options) {
  const writeNow = () => {
    try {
      const next = _materialize(config);
      if (!next || typeof next !== "object") return;
      const current = _read_config() || {};
      // 深合并：只覆盖面板管理的键，保留 header_distance / body / heading_* 等未管理字段
      const merged = _deep_merge(current, next);
      const { _synced_at: _ignored, ...comparable } = merged;
      const fingerprint = JSON.stringify(comparable);
      if (fingerprint === _lastSynced) return;
      merged._source = "dsh";
      merged._synced_at = new Date().toISOString();
      _write_config(merged);
      _lastSynced = fingerprint;
    } catch (e) {
      console.warn("[gongwen-skill] 配置镜像失败:", e?.message || e);
    }
  };
  // 工具调用前必须同步落盘：CLI 子进程紧接着就要读这个文件，去抖会引入竞态
  if (options && options.immediate) {
    if (_syncTimer) {
      clearTimeout(_syncTimer);
      _syncTimer = null;
    }
    writeNow();
    return;
  }
  if (_syncTimer) clearTimeout(_syncTimer);
  _syncTimer = setTimeout(() => {
    _syncTimer = null;
    writeNow();
  }, 300);
  if (typeof _syncTimer.unref === "function") _syncTimer.unref();
}

// 0.2.x：设置文档是唯一真相，启动快照 config 不会随文档更新。
// 这里保存服务引用，供「真正调用 CLI 之前」重新取有效值并同步 CLI 缓存。
let _settingsSvc = null;
function _settingsEntry(svc) {
  try {
    if (!svc || typeof svc.describe !== "function") return null;
    const list = svc.describe({ redactSecrets: true });
    if (!Array.isArray(list)) return null;
    return list.find((d) => d && d.ns === SETTINGS_NS) || null;
  } catch {
    return null;
  }
}

// 把设置文档里的有效值同步到 CLI 缓存（~/.gongwen-skill/dsh-config.json）
function _syncCliFromSettings(reason, options) {
  if (!_settingsSvc) return;
  const desc = _settingsEntry(_settingsSvc);
  if (!desc) return;
  const user = desc.user;
  // 文档里没有用户覆盖时不动 CLI 缓存，避免默认值冲掉用户手改的 dsh-config.json
  if (!user || typeof user !== "object" || Object.keys(user).length === 0) return;
  const effective = desc.value && typeof desc.value === "object" ? desc.value : user;
  _mirrorToCliConfig(effective, options);
  if (reason) _lastMirrorReason = reason;
}
let _lastMirrorReason = null;

// 设置安装：0.2.x 与 0.1.x 能力探测（不做版本判断）
function _install_settings(ctx, config) {
  const attach = (c) => {
    const svc = c.settings;
    if (!svc) return;

      // 0.2.x：Config 即数据源；声明本插件不使用自动生成页
      if (typeof svc.configure === "function") {
        _settingsSvc = svc;
        try {
          const off = svc.configure({ auto: false }, c.fiber);
          if (typeof off === "function") c.effect(() => off, "gongwen-skill: settings configure");
        } catch (e) {
          c.logger?.warn?.(`gongwen-skill: settings.configure 失败: ${e.message}`);
        }
        // 启动时同步一次（仅当文档已有用户覆盖）
        _syncCliFromSettings("boot");
        // 文档变更后同步：settings/document-updated 是 0.2.x 的权威信号；
        // volatile-update 作为旧版本兜底。两者都只做「重新 describe」。
        const onChange = (ns) => {
          if (ns !== undefined && ns !== SETTINGS_NS) return;
          _syncCliFromSettings("document");
        };
        for (const evt of ["settings/document-updated", "loader/volatile-update"]) {
          try {
            c.effect(() => c.on(evt, onChange), `gongwen-skill: mirror on ${evt}`);
          } catch {
            // 事件名不存在时忽略（低版本）
          }
        }
        c.logger?.info?.("gongwen-skill: settings=config(0.2.x)");
        return;
      }

    // 0.1.x：注册命名空间 + watch 回写
    if (typeof svc.register === "function") {
      try {
        const schema = _build_settings_schema();
        const scope = svc.register(SETTINGS_NS, schema, { applies: "live" });

        // 一次性迁移：旧 dsh-config.json → settings（仅当用户层为空）
        try {
          const describe = typeof svc.describe === "function" ? svc.describe({ redactSecrets: true }) : [];
          const desc = Array.isArray(describe) ? describe.find((d) => d.ns === SETTINGS_NS) : null;
          const userEmpty = !desc || !desc.user || Object.keys(desc.user).length === 0;
          const legacy = _read_config();
          if (legacy && userEmpty) void scope.update(legacy);
        } catch {
          // 迁移失败不影响注册
        }

        const off = scope.watch((next) => _mirrorToCliConfig(next));
        if (typeof off === "function") c.effect(() => off, "gongwen-skill: settings watch");
        c.logger?.info?.("gongwen-skill: settings=register(0.1.x)");
      } catch (e) {
        c.logger?.warn?.(`gongwen-skill: settings.register 失败: ${e.message}`);
      }
      return;
    }

    c.logger?.warn?.("gongwen-skill: 未找到可用的 settings API，设置页将只读");
  };

  try {
    ctx.inject(["settings"], attach);
  } catch (e) {
    ctx.logger?.warn?.(`gongwen-skill: settings 注入失败: ${e.message}`);
  }
}

// ── Python 解释器探测（缓存）────────────────────────────────────────────────
let _PY = null;
function _detect_python() {
  if (_PY) return _PY;
  const candidates = [];
  if (process.env.GONGWEN_PYTHON) candidates.push({ cmd: process.env.GONGWEN_PYTHON, args: [] });
  if (process.platform === "win32") candidates.push({ cmd: "py", args: ["-3"] });
  candidates.push({ cmd: "python3", args: [] }, { cmd: "python", args: [] });

  for (const c of candidates) {
    try {
      const r = spawnSync(c.cmd, [...c.args, "-c", "import sys;print(sys.version_info[0])"], {
        encoding: "utf-8", timeout: 5000, windowsHide: true,
      });
      if (r.status === 0 && Number.parseInt(String(r.stdout).trim(), 10) >= 3) {
        _PY = c;
        return c;
      }
    } catch {
      // 试下一个
    }
  }
  _PY = { cmd: "python", args: [] };
  return _PY;
}

// 终止子进程树（Windows 需要 taskkill /T）
function _kill_tree(child) {
  if (!child || child.killed) return;
  try {
    if (process.platform === "win32" && child.pid) {
      spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true });
    } else {
      child.kill("SIGTERM");
      const t = setTimeout(() => {
        try {
          child.kill("SIGKILL");
        } catch {}
      }, 2000);
      if (typeof t.unref === "function") t.unref();
    }
  } catch {
    try {
      child.kill();
    } catch {}
  }
}

// 运行一条 gongwen CLI 命令（call() 与模型工具 execute 共用）
async function runCli(command, args = {}, options = {}) {
  let projectRoot;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch (err) {
    return { success: false, error: err.message };
  }

  const { cwd = projectRoot, signal } = options;
  const rest = { ...args };
  delete rest.command;

  // extra 兼容：对象直接合并，字符串按 JSON 解析后合并
  if (rest.extra) {
    if (typeof rest.extra === "object") {
      Object.assign(rest, rest.extra);
    } else if (typeof rest.extra === "string") {
      try {
        const parsed = JSON.parse(rest.extra);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) Object.assign(rest, parsed);
      } catch {
        // 非 JSON 忽略
      }
    }
    delete rest.extra;
  }

  // 读取 DSH 配置并注入 --config-overrides（仅支持的命令）
  const config = _read_config();
  let configOverrides = null;
  if (config && CONFIG_OVERRIDE_COMMANDS.has(command)) {
    configOverrides = {};
    for (const [k, v] of Object.entries(config)) {
      if (!k.startsWith("_") && k !== "default_doc_type") configOverrides[k] = v;
    }
    if (Object.keys(configOverrides).length === 0) configOverrides = null;
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
  }

  if (configOverrides) rest["config-overrides"] = JSON.stringify(configOverrides);

  // 支持 default_doc_type
  if (config?.default_doc_type && DOC_TYPE_COMMANDS.has(command) && !rest["doc-type"] && !rest.docType && !rest.t) {
    rest["doc-type"] = config.default_doc_type;
  }

  const positionalKeys = POSITIONAL_ARGS[command] || [];
  const cliArgs = ["-m", "gongwen", command, ..._to_cli_args(rest, positionalKeys)];
  const py = _detect_python();
  const timeoutMs = Number(process.env.GONGWEN_TIMEOUT_MS) || 300_000;
  const MAX_OUT = 8 * 1024 * 1024;

  return await new Promise((resolvePromise) => {
    let settled = false;
    let timer = null;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      resolvePromise(value);
    };

    const child = spawn(py.cmd, [...py.args, ...cliArgs], {
      cwd,
      env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    let truncated = false;
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString("utf-8");
      if (stdout.length + text.length > MAX_OUT) {
        stdout = stdout.slice(0, 256 * 1024) + "\n…[truncated]\n" + text.slice(-64 * 1024);
        truncated = true;
      } else {
        stdout += text;
      }
    });
    child.stderr.on("data", (chunk) => {
      if (stderr.length < 2 * 1024 * 1024) stderr += chunk.toString("utf-8");
    });

    const onAbort = () => _kill_tree(child);
    signal?.addEventListener("abort", onAbort, { once: true });

    timer = setTimeout(() => {
      _kill_tree(child);
      finish({
        success: false,
        error: `命令超时（${timeoutMs}ms）：${command}。可用环境变量 GONGWEN_TIMEOUT_MS 调大。`,
        cli: `${py.cmd} ${py.args.concat(cliArgs).join(" ")}`,
        hint: "大文档建议在 CLI 中直接运行，或调大超时",
      });
    }, timeoutMs);
    if (typeof timer.unref === "function") timer.unref();

    child.on("error", (err) => {
      finish({
        success: false,
        error: `python spawn failed: ${err.message}（解释器: ${py.cmd}）`,
        cli: `${py.cmd} ${py.args.concat(cliArgs).join(" ")}`,
        cwd,
        hint: "可用环境变量 GONGWEN_PYTHON 指定解释器路径",
      });
    });

    child.on("close", (code) => {
      if (code === 0) {
        const trimmed = stdout.trim();
        if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
          try {
            finish({ success: true, data: JSON.parse(trimmed), stderr: stderr.trim(), truncated });
            return;
          } catch {
            // 非 JSON
          }
        }
        finish({ success: true, output: trimmed, stderr: stderr.trim(), truncated });
      } else {
        finish({
          success: false,
          exit_code: code,
          output: stdout.trim(),
          stderr: stderr.trim(),
          cli: `${py.cmd} ${py.args.concat(cliArgs).join(" ")}`,
          cwd,
        });
      }
    });
  });
}

// Agent 预设安装：把插件包内 presets/ 同步到 ~/.dsh/.agent-presets/gongwen-skill/
// 幂等 + 不覆盖用户修改：目标目录不存在则跳过；版本相同则跳过；覆盖前备份。
function _syncPreset() {
  try {
    const presetRoot = join(homedir(), ".dsh", ".agent-presets");
    if (!existsSync(presetRoot)) return "skipped:no-preset-dir";
    if (process.env.GONGWEN_KEEP_PRESET === "1") return "skipped:env";

    let version = "0.0.0";
    try {
      version = JSON.parse(readFileSync(resolve(__dirname, "..", "package.json"), "utf-8")).version;
    } catch {}

    const target = join(presetRoot, "gongwen-skill");
    const stamp = join(target, ".gongwen-preset-version");
    if (existsSync(stamp)) {
      try {
        if (readFileSync(stamp, "utf-8").trim() === version) return "skipped:same-version";
      } catch {}
    }

    mkdirSync(target, { recursive: true });
    const pluginPresets = join(resolve(__dirname, ".."), "presets");
    for (const name of ["preset.yml", "agent.cordis.yml"]) {
      const src = join(pluginPresets, name);
      if (!existsSync(src)) continue;
      const dest = join(target, name);
      if (existsSync(dest)) {
        try {
          copyFileSync(dest, `${dest}.bak`);
        } catch {}
      }
      copyFileSync(src, dest);
    }
    writeFileSync(stamp, version, "utf-8");
    return `synced:${version}`;
  } catch (e) {
    return `failed:${e?.message || e}`;
  }
}

// 注入 AI 工作指引（可选服务：就绪即注册，缺失不阻塞）
// 注意：Cordis 4.1 禁止未声明 inject 就访问 ctx.<service>，这里只用 ctx.inject 子级访问。
function _install_prompt(ctx) {
  const attach = (c) => {
    let sp;
    try {
      sp = c.systemPrompt;
    } catch {
      return;
    }
    if (!sp?.section) return;
    try {
      const d = sp.section({ name: SECTION_NAME, order: SECTION_ORDER, text: GONGWEN_GUIDANCE });
      if (typeof d === "function") c.effect(() => d, "gongwen-skill: system prompt");
    } catch (e) {
      c.logger?.warn?.(`gongwen-skill: system prompt 注册失败: ${e.message}`);
    }
  };

  try {
    ctx.inject(["systemPrompt"], attach);
  } catch {
    // 无该服务：跳过
  }
}

// ── 「公文写作模式」Agent 预设 ───────────────────────────────────────────────
// 预设 = 一份子插件清单，决定该模式下的人设与工具面。这里在运行时注册：
// 注册表用宿主 baseUrl 解析子插件，跨版本比写死 bundle patch 更稳，也不需要新增依赖。
// 0.1.x 没有 agentPresets 服务 → inject 永不满足，静默跳过，不影响其他能力。
const WRITING_PRESET_ID = "gongwen-writing";

const WRITING_PERSONA =
  "You are a Chinese official-document (公文) writing agent powered by the {{model}} model. " +
  "Your output must survive a real review: correct 文种, correct GB/T 9704-2012 格式, " +
  "and wording that fits the issuing body's position. Prefer delivering a finished .docx " +
  "over describing what could be written; when the request is a draft, draft it, then state " +
  "the assumptions you filled in. This mode edits documents, not source trees.";

function _writing_preset_definition() {
  // 只保留写作必需能力：文件读写 / 一个 shell / Office 文档 / 联网查规范 / 提问 / 产出卡片 / 压缩。
  // 刻意不含 subagent、workflow、goal、plan-mode —— 工具面越小，写作越专注。
  const shell =
    process.platform === "win32"
      ? [{ id: "tool-pwsh", name: "@deepseek-ai/dsh-tool-pwsh" }]
      : [{ id: "tool-bash", name: "@deepseek-ai/dsh-tool-bash" }];

  return {
    id: WRITING_PRESET_ID,
    name: "公文写作模式",
    description: "中文公文（GB/T 9704）成稿、改稿与格式审查；直接产出 Word，不改代码。",
    order: 5,
    plugins: [
      { id: "persona", name: "@deepseek-ai/dsh-persona", config: { prefix: WRITING_PERSONA } },
      { id: "agent-instructions", name: "@deepseek-ai/dsh-agent-instructions", config: { maxBytes: 65536 } },
      { id: "time-context", name: "@deepseek-ai/dsh-time-context" },
      ...shell,
      { id: "tool-fs", name: "@deepseek-ai/dsh-tool-fs", config: { applyPatch: false } },
      {
        id: "tool-fs-search",
        name: "@deepseek-ai/dsh-tool-fs-search",
        config: { sampleOverCapGlobResults: false },
      },
      { id: "tool-office", name: "@deepseek-ai/dsh-tool-office" },
      {
        id: "tool-web",
        name: "@deepseek-ai/dsh-tool-web",
        config: { fetch: true, searchTimeoutMs: 60000 },
      },
      { id: "tool-ask-user", name: "@deepseek-ai/dsh-tool-ask-user" },
      { id: "present", name: "@deepseek-ai/dsh-tool-present" },
      {
        id: "compaction",
        name: "cordis:group",
        group: true,
        isolate: { compaction: true, toolResultPruner: true },
        config: [
          { id: "compaction-basic", name: "@deepseek-ai/dsh-compaction-basic" },
          { id: "command-compact", name: "@deepseek-ai/dsh-command-compact" },
          {
            id: "tool-result-pruner",
            name: "@deepseek-ai/dsh-compaction-tool-result-pruner",
            config: { thresholdChars: 8192, headChars: 4096, tailChars: 1024 },
          },
        ],
      },
    ],
  };
}

function _install_writing_preset(ctx) {
  const attach = (c) => {
    let svc;
    try {
      svc = c.agentPresets;
    } catch {
      return;
    }
    if (!svc || typeof svc.register !== "function") return;
    Promise.resolve()
      .then(() => svc.register(_writing_preset_definition()))
      .then((dispose) => {
        if (typeof dispose === "function") {
          c.effect(() => dispose, "gongwen-skill: writing preset");
        }
        c.logger?.info?.(`gongwen-skill: 预设 ${WRITING_PRESET_ID}（公文写作模式）已注册`);
      })
      .catch((e) => {
        c.logger?.warn?.(`gongwen-skill: 写作模式预设注册失败: ${e.message}`);
      });
  };

  try {
    ctx.inject(["agentPresets"], attach);
  } catch {
    // 无该服务：跳过
  }
}

// 模型工具参数 → CLI 参数对象（统一转 kebab-case）
function toolArgsToCli(args) {
  const out = {};
  if (typeof args.extra === "string" && args.extra.trim() !== "") {
    try {
      const parsed = JSON.parse(args.extra);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) Object.assign(out, parsed);
    } catch {
      // 非 JSON 忽略
    }
  }
  for (const [key, value] of Object.entries(args)) {
    if (key === "command" || key === "extra") continue;
    if (value === undefined || value === null) continue;
    out[_kebab(key)] = value;
  }
  return out;
}

// 工具输出渲染（模型可见；超长 JSON 截断，避免灌爆上下文）
function renderToolResult(_args, value) {
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  if (typeof text === "string" && text.length > 32 * 1024) {
    return [{ type: "text", text: text.slice(0, 32 * 1024) + "\n…[truncated]" }];
  }
  return [{ type: "text", text: typeof text === "string" ? text : String(text) }];
}

// 注册模型工具（原生定义对象；SDK 提供 defineTool 时同样兼容）
function registerGongwenTool(ctx) {
  ctx.tools.register(defineTool({
    name: "gongwen",
    description:
      "运行公文全流程处理专家（gongwen-skill）CLI 命令：check（格式检查）、optimize（自动修复）、optimize-content（内容修订对比版）、md2docx（Markdown 转公文）、template（模板生成）、style-learn（样式学习）、list-types（列出公文类型）、doctor（全面诊断）、handoff（会话交接）等。",
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
      if (!args.command) return { success: false, error: "缺少必填参数：command" };
      // 调用前把设置文档的有效值同步到 CLI 缓存，避免「面板改了但 CLI 仍读旧值」
      _syncCliFromSettings("tool", { immediate: true });
      if (args.command === "config") {
        const extra = typeof args.extra === "string"
          ? (() => { try { return JSON.parse(args.extra); } catch { return {}; } })()
          : (args.extra || {});
        return _handle_config({ ...extra, action: extra.action || "show" });
      }
      return await runCli(args.command, toolArgsToCli(args), {
        signal: exec?.signal,
        cwd: exec?.cwd,
      });
    },
  }));
}

export const name = "gongwen-skill";
export const description =
  "公文全流程处理专家（gongwen-skill）—— 中文公文 GB/T 9704 格式检查/修复/内容优化/模板生成/版式注入";

// 硬依赖：tools（模型工具注册需要）。systemPrompt / settings 为可选服务，内部探测。
export const inject = ["tools"];

// apply() — Cordis 生命周期管理（所有注册均为可逆副作用）
export function apply(ctx, config) {
  let projectRoot = null;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch {
    ctx.logger?.warn?.("gongwen-skill: gongwen 包未定位，CLI 调用将在执行时失败");
  }

  try {
    registerGongwenTool(ctx);
  } catch (e) {
    ctx.logger?.warn?.(`gongwen-skill: tool registration failed: ${e.message}`);
  }

  _install_prompt(ctx);
  _install_settings(ctx, config);
  _install_writing_preset(ctx);

  const preset = _syncPreset();
  ctx.logger?.info?.(
    `gongwen-skill plugin loaded${projectRoot ? ` (projectRoot=${projectRoot})` : "（gongwen 包未定位）"} preset=${preset}`,
  );
}

// call() — 透传 Python CLI（保留向后兼容）
export async function call(ctx, args) {
  const { command, ...rest } = args;
  if (!command) return { success: false, error: "missing required field: command" };
  if (command === "config") return _handle_config(rest);
  return await runCli(command, rest, { cwd: ctx?.cwd });
}
