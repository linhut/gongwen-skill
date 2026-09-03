<!--
  (c) 2026 Jose AI (https://www.linhut.cn)
  https://github.com/linhut/gongwen-skill
  Licensed under the MIT License. See the LICENSE file for details.
-->

# DNS 污染诊断设计（v2.8.0）

## 1. 背景与动机

用户发现：本机可通过「安全 DNS（DoH，DNS over HTTPS）」无污染解析出 GitHub 等域名的真实 IP，从而解决「地址无法访问 / 超时」问题。

- 系统 DNS 常被污染（实测本机 github.com 解析为 198.18.0.64 —— IANA 保留的 Fake-IP 段，非真实地址）
- 用 DoH（如 application/dns-json 格式）可拿到真实 IP（github.com = 140.82.114.x），且该 IP 直连 TLS 握手成功（245ms，无 SNI 阻断）
- 本项目 check-update 依赖 GitHub 备用渠道判定、font install 依赖 GitHub 下载字体 —— DNS 污染直接导致这些功能在部分机器上不可用
- 现状：check-update 在 GitHub 不可达时仅提示「国内镜像 + GitHub520 hosts」，无 DNS 层诊断，用户不知道病根是 DNS 污染

## 2. 目标（Scope）

**诊断建议 + 下载失败自动兜底** —— 不修改 hosts、不改变版本判定逻辑；`font install` 下载字体 / PyPI 查询在常规请求失败（疑似 DNS 污染）时，自动用 DoH 真实 IP + TLS SNI 直连重试（零操作，证书校验不降级）。

在以下两处检测到「疑似 DNS 污染」时，输出：
1. 污染判定结论
2. 系统解析 vs DoH 真实 IP 对比表
3. 可直接粘贴的 hosts 条目
4. 国内镜像仓库提示
5. --json 结构化输出（Agent 可解析）

## 3. 已确认决策（用户逐项选定）

| 项 | 决策 |
|----|------|
| 范围 | 诊断建议 + 下载/查询失败自动 DoH 直连兜底（不改 hosts、不改版本判定；font install 与 PyPI 查询受益） |
| DoH 端点 | 内置国内公共 DoH（阿里 dns.alidns.com / 腾讯 doh.pub），支持环境变量 GONGWEN_DOH 自定义 |
| 入口 | doctor 新增「网络与 DNS 诊断」检查项 + check-update GitHub 不可达时增强提示 |
| 行为 | doctor 默认联网诊断，--offline 跳过网络检查 |
| 输出 | 完整可操作（判定 + 对比表 + hosts 条目 + 镜像提示 + --json） |

## 4. 模块设计

### 4.1 新增 gongwen/cli/netcheck.py（单一职责，可独立测试）

```
netcheck.py
├── _DOH_ENDPOINTS        # 国内公共 DoH 列表（阿里/腾讯），env GONGWEN_DOH 可覆盖
├── resolve_via_doh(host) # DoH 查真实 IP（application/dns-json，多端点降级）
├── system_resolve(host)  # socket.getaddrinfo 取系统解析 IP
├── detect_pollution(host)# → (判定, 系统IP, DoH真实IP, 说明)
├── check_hosts(hosts)    # 批量检测一组域名
└── format_hosts(entries) # 生成可粘贴 hosts 条目文本
```

**污染判定标准**（detect_pollution）：

| 系统解析 | DoH 解析 | 判定 |
|----------|----------|------|
| 成功，与 DoH 一致 | 成功 | 正常（ok=True） |
| 失败 / NXDOMAIN | 成功 | 疑似污染（ok=False, WARN） |
| 成功但 IP 落在保留/异常段（198.18.0.0/15、0.0.0.0、127.x、10/8、172.16/12、192.168/16）且与 DoH 不同 | 成功 | 疑似污染（ok=False, WARN） |
| 成功但与 DoH 不同且非保留段 | 成功 | 差异提示（ok=None, WARN） |
| 任意 | 失败（DoH 不可达） | 无法判定（ok=None, WARN，不误报） |

### 4.2 update_cmds.py 增强（check-update）

- 保持现有版本判定逻辑完全不变（PyPI 权威 + GitHub 备用）
- 当 GitHub 渠道不可达（且至少一个渠道可达）时，调用 netcheck.check_hosts() 诊断 github.com / api.github.com / raw.githubusercontent.com
- 人类可读输出：追加「🔬 DNS 诊断」区块（判定 + 对比表 + hosts 条目 + 镜像提示）
- --json 输出新增 dns_diagnosis 字段：

```
{
  "polluted": true,
  "detail": "系统 DNS 解析 github.com 为 198.18.0.64（保留段），DoH 真实 IP 为 140.82.114.3",
  "hosts_suggestions": ["140.82.114.3 github.com", "..."],
  "mirrors": {"GitCode": "https://gitcode.com/linhut/gongwen-skill.git", "AtomGit": "..."}
}
```

### 4.3 doctor_cmds.py 增强

- 新增 _check_network_dns() 检查项：
  - 默认执行（--offline 时跳过，返回 SKIP 状态）
  - 检测域名：github.com、api.github.com、raw.githubusercontent.com、pypi.org
  - 返回结构与现有检查一致：{"name", "ok", "detail", "hint"}
  - ok 三态：True=正常 / False=疑似污染（FAIL）/ None=无法判定或跳过（WARN）
- _run_all_checks() 中追加 add(_check_network_dns())
- cmd_doctor 增加 --offline 参数（在 _legacy.py parser 注册）

### 4.4 _legacy.py 注册调整

```
p = sub.add_parser("doctor", help="...")
p.add_argument("--json", action="store_true", help="...")
p.add_argument("--offline", action="store_true", help="跳过网络/DNS 诊断（离线模式）")
p.set_defaults(func=cmd_doctor)
```

## 5. 测试计划（tests/ 本地，不入库）

| 测试 | 覆盖 |
|------|------|
| test_resolve_via_doh | mock urllib 响应，验证 JSON 解析、多端点降级、超时容错 |
| test_detect_pollution | 正常 / Fake-IP 保留段 / 解析失败 / DoH 不可达 四态 |
| test_format_hosts | hosts 条目格式正确（IP + 空格 + 域名） |
| test_check_update_json | --json 输出含 dns_diagnosis 字段（mock GitHub 不可达） |
| test_doctor_network | doctor 新检查项 OK / WARN / SKIP(--offline) 分支 |

## 6. 文档更新

- README.md：新增「GitHub 不可达排查」章节（安全 DNS / DoH 思路说明 + 镜像方案）；check-update / doctor 命令描述更新
- SKILL.md：命令速查更新（check-update / doctor 描述），.dsh/skills/ 两份副本 md5 同步
- CHANGELOG.md：v2.8.0 条目

## 7. 版本号

- 2.7.0 → 2.8.0（4 处代码 + CHANGELOG + 文档同步，遵循仓库版本规范）

## 8. 边界与隐私

- DoH 查询经第三方（阿里/腾讯），仅诊断时发起少量查询；文档明示
- GONGWEN_DOH 环境变量可指向私有端点（如用户自建 oaifree 服务），开源项目不内置私有端点
- 诊断网络操作超时 ≤5s，--offline 完全离线，不阻塞主流程；下载兜底超时 30-60s（大文件需长超时）
- 不修改 hosts；自动直连仅作为下载/查询失败的兜底路径（TLS SNI 保持真实域名，证书校验不降级，YAGNI：不主动直连、不做代理）
