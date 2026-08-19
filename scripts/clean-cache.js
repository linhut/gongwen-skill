// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.

// 打包前清理 __pycache__ 目录（prepack 钩子使用）
// 单独文件避免 package.json 内联转义问题
import { readdirSync, rmSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

function clean(dir) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const name of entries) {
    const p = join(dir, name);
    let st;
    try {
      st = statSync(p);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      if (name === "__pycache__") {
        rmSync(p, { recursive: true, force: true });
        console.log(`removed ${p}`);
      } else {
        clean(p);
      }
    }
  }
}

clean(process.cwd());
console.log("prepack: __pycache__ cleanup done");