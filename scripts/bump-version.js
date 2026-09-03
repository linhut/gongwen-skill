#!/usr/bin/env node
// gongwen-skill 版本号一键 bump 脚本
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 用法:
//   node scripts/bump-version.js <X.Y.Z> [--dry-run]   指定目标版本
//   node scripts/bump-version.js --patch [--dry-run]   递增 PATCH
//   node scripts/bump-version.js --minor [--dry-run]   递增 MINOR
//   node scripts/bump-version.js --major [--dry-run]   递增 MAJOR
//
// 行为:
//   - 同步 4 处代码版本: pyproject.toml / gongwen/__init__.py /
//     gongwen/_legacy.py / package.json
//   - 同步文档版本: prompts/usage-prompts.md (Skill 版本: vX.Y.Z) /
//     dsh/index.js 注释 (vX.Y.Z+)
//   - CHANGELOG.md 顶部插入新版本条目 (草稿, Added 占位)
//   - 写后校验 4 处代码版本一致
//   - 默认不自动 git commit/tag/push (保留人工确认)
//   - --dry-run 只打印将改动的文件, 不写盘

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const SEMVER = /^\d+\.\d+\.\d+$/;

function read(p) { return readFileSync(join(ROOT, p), "utf8"); }
function write(p, s) { writeFileSync(join(ROOT, p), s, "utf8"); }
function readVersion(file, re) {
  const m = read(file).match(re);
  if (!m) throw new Error("无法在 " + file + " 中读取版本号");
  return m[1];
}
function cmp(a, b) {
  const A = a.split(".").map(Number), B = b.split(".").map(Number);
  return (A[0] - B[0]) || (A[1] - B[1]) || (A[2] - B[2]);
}

// ---- 参数解析 ----
const argv = process.argv.slice(2);
const dryRun = argv.includes("--dry-run");
const hasHelp = argv.includes("--help") || argv.includes("-h");
if (hasHelp) {
  console.log("用法: node scripts/bump-version.js <X.Y.Z> | --patch|--minor|--major [--dry-run]");
  process.exit(0);
}

let nextVer = null;
const positional = argv.filter(a => !a.startsWith("--"));
if (positional.length) {
  nextVer = positional[0];
} else if (argv.includes("--patch") || argv.includes("--minor") || argv.includes("--major")) {
  const cur = readVersion("pyproject.toml", /version\s*=\s*"(\d+\.\d+\.\d+)"/);
  const [ma, mi, pa] = cur.split(".").map(Number);
  nextVer = argv.includes("--major") ? (ma + 1) + ".0.0"
    : argv.includes("--minor") ? ma + "." + (mi + 1) + ".0"
    : ma + "." + mi + "." + (pa + 1);
} else {
  console.error("用法: node scripts/bump-version.js <X.Y.Z> | --patch|--minor|--major [--dry-run]");
  process.exit(1);
}
if (!SEMVER.test(nextVer)) {
  console.error("版本号格式错误: " + nextVer + "（应为 X.Y.Z）");
  process.exit(1);
}

// ---- 当前版本与降级防护 ----
let current;
try { current = readVersion("pyproject.toml", /version\s*=\s*"(\d+\.\d+\.\d+)"/); }
catch (e) { console.error(e.message); process.exit(1); }
if (cmp(nextVer, current) < 0) {
  console.error("拒绝降级: 当前 " + current + " -> 目标 " + nextVer);
  process.exit(1);
}
if (nextVer === current) {
  console.log("当前版本已是 " + current + "，无变更");
  process.exit(0);
}

// ---- 替换计划 ----
const plans = [
  { file: "pyproject.toml", re: /(version\s*=\s*")[\d.]+(")/, rep: "$1" + nextVer + "$2", label: "代码版本" },
  { file: "gongwen/__init__.py", re: /(__version__\s*=\s*")[\d.]+(")/, rep: "$1" + nextVer + "$2", label: "代码版本" },
  { file: "gongwen/_legacy.py", re: /(__version__\s*=\s*")[\d.]+(")/, rep: "$1" + nextVer + "$2", label: "代码版本" },
  { file: "package.json", re: /("version"\s*:\s*")[\d.]+(")/, rep: "$1" + nextVer + "$2", label: "代码版本" },
  { file: "prompts/usage-prompts.md", re: /(Skill 版本:\s*v)[\d.]+/, rep: "$1" + nextVer, label: "文档版本" },
  { file: "dsh/index.js", re: /(gongwen-skill,\s*v)[\d.]+(\+)/, rep: "$1" + nextVer + "$2", label: "文档版本" },
];

const missing = [];
for (const p of plans) {
  if (!existsSync(join(ROOT, p.file))) { missing.push(p.file); continue; }
  const content = read(p.file);
  if (!p.re.test(content)) missing.push(p.file + "（未匹配到版本号模式）");
}

// ---- CHANGELOG 条目 ----
const today = new Date().toISOString().slice(0, 10);
const entry = "## v" + nextVer + " (" + today + ")\n\n### Added\n- （待补充发布条目）\n\n";

// ---- 执行 ----
if (dryRun) {
  console.log("[dry-run] 目标版本: " + current + " -> " + nextVer);
  for (const p of plans) {
    const content = read(p.file);
    const m = content.match(p.re);
    console.log("  将更新 " + p.file + "  [" + p.label + "]: " + (m ? m[0].replace(p.re, p.rep) : "未匹配") + "");
  }
  console.log("  将插入 CHANGELOG.md 顶部: ## v" + nextVer + " (" + today + ")");
  console.log("[dry-run] 未写盘。");
  process.exit(0);
}

if (missing.length) {
  console.error("以下文件缺失或版本号模式未匹配，已中止：");
  missing.forEach(f => console.error("  - " + f));
  process.exit(1);
}

const done = [];
for (const p of plans) {
  const before = read(p.file);
  const after = before.replace(p.re, p.rep);
  if (after === before) {
    console.error("替换失败: " + p.file + "（内容未变化）");
    process.exit(1);
  }
  write(p.file, after);
  done.push(p.file);
}

// CHANGELOG 插入（首个 ## v 行之前）
const clPath = join(ROOT, "CHANGELOG.md");
if (existsSync(clPath)) {
  const cl = read("CHANGELOG.md");
  const lines = cl.split("\n");
  let idx = lines.findIndex(l => /^##\s+v/.test(l));
  if (idx === -1) idx = 0;
  lines.splice(idx, 0, entry.replace(/\n$/, ""));
  write("CHANGELOG.md", lines.join("\n"));
  done.push("CHANGELOG.md");
}

// ---- 一致性校验 ----
const verify = [
  ["pyproject.toml", /version\s*=\s*"(\d+\.\d+\.\d+)"/],
  ["gongwen/__init__.py", /__version__\s*=\s*"(\d+\.\d+\.\d+)"/],
  ["gongwen/_legacy.py", /__version__\s*=\s*"(\d+\.\d+\.\d+)"/],
  ["package.json", /"version"\s*:\s*"(\d+\.\d+\.\d+)"/],
];
const got = verify.map(([f, re]) => read(f).match(re)?.[1] || "?");
const ok = got.every(v => v === nextVer);
console.log("✅ 版本已更新: " + current + " -> " + nextVer);
done.forEach(f => console.log("  更新 " + f));
if (ok) {
  console.log("✅ 4 处代码版本一致: " + got.join(" / "));
} else {
  console.error("❌ 版本一致性校验失败: " + got.join(" / "));
  process.exit(1);
}
console.log("");
console.log("提示: 请补充 CHANGELOG.md 新条目内容，检查 README/RELEASE 文档示例，");
console.log("确认后执行 git add 提交、打 tag v" + nextVer + "、推送三 remote 触发 CI 发布。");
