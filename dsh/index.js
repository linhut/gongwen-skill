// gongwen-skill DSH plugin bridge
// (c) 2026 Jose AI (https://www.linhut.cn)  MIT License
//
// This plugin bridges the gongwen-skill Python CLI into DSH's runtime.
// It provides the model-facing tool interface that DSH agents use to
// call gongwen-skill commands.

export const name = "gongwen-skill";
export const description = "中文公文全流程处理工具 - GB/T 9704 格式检查/修复/内容优化/模板生成";

export async function setup(ctx) {
  ctx.logger.info("gongwen-skill plugin loaded");
}

export async function call(ctx, args) {
  // Bridge to Python CLI
  const { command, ...rest } = args;
  const cmdArgs = Object.entries(rest)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `--${k} "${v}"`)
    .join(" ");

  const { execSync } = await import("node:child_process");
  try {
    const output = execSync(`python gongwen.py ${command} ${cmdArgs}`, {
      encoding: "utf-8",
      timeout: 30000,
    });
    return { success: true, output: output.trim() };
  } catch (error) {
    return { success: false, error: error.message, stderr: error.stderr };
  }
}
