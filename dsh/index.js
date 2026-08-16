// gongwen-skill DSH plugin bridge
// (c) 2026 Jose AI (https://www.linhut.cn)  MIT License
//
// This plugin bridges the gongwen-skill Python CLI into DSH's runtime.
// It provides the model-facing tool interface that DSH agents use to
// call gongwen-skill commands.
//
// 关键修复（v1.12.59+）：
// (1) 入口从 `python gongwen.py`（已删除）改为 `python -m gongwen`（正确入口）
// (2) 用 spawn（args 数组）替代 execSync（字符串拼接），避免 shell 引号注入
// (3) PYTHONIOENCODING=utf-8 防止 Windows GBK 控制台输出乱码
// (4) 调用走 cwd=工作目录，尊重当前会话的承载文件

import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// 定位 gongwen CLI 真实安装根目录：plugin 包目录或 git clone 目录
function _resolve_gongwen_root() {
  // dsh/index.js 所在目录的上一级就是 gongwen-skill 仓库根
  const projectRoot = resolve(__dirname, "..");

  // 当前的 gongwen 是 Python 包，入口 `python -m gongwen`
  // 优先用项目根（即本仓库的安装位置）
  if (existsSync(join(projectRoot, "gongwen", "__init__.py")) || existsSync(join(projectRoot, "pyproject.toml"))) {
    return projectRoot;
  }
  throw new Error(`\
gongwen-skill plugin bridge 无法定位 gongwen 包 \
(projectRoot=${projectRoot} 未找到 gongwen/__init__.py 或 pyproject.toml). \
请确认插件正确安装在 ~/.dsh/profiles/web/node_modules/gongwen-skill`);
}

// 把命令对象转为 args 数组（避免 shell 引号问题）
function _to_cli_args(args) {
  const cliArgs = [];
  for (const [k, v] of Object.entries(args)) {
    if (v === undefined || v === null || v === false) continue;
    if (v === true) {
      cliArgs.push(`--${k}`);
    } else {
      cliArgs.push(`--${k}`, String(v));
    }
  }
  return cliArgs;
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
  } catch (err) {
    if (ctx?.logger) ctx.logger.error(`gongwen-skill plugin setup failed: ${err.message}`);
  }
}

export async function call(ctx, args) {
  const { command, ...rest } = args;
  if (!command) {
    return { success: false, error: "missing required field: command" };
  }
  let projectRoot;
  try {
    projectRoot = _resolve_gongwen_root();
  } catch (err) {
    return { success: false, error: err.message };
  }

  const cliArgs = ["-m", "gongwen", command, ..._to_cli_args(rest)];

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
        resolve({ success: true, output: stdout.trim(), stderr: stderr.trim() });
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
