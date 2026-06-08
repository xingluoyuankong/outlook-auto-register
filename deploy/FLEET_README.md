# 多节点 Outlook 注册舰队

## Zo 账号（handle）

| Zo | handle | 舰队 node_id | SSH |
|----|--------|--------------|-----|
| 1 | **xzxyuan** | xzxyuan | ts10:10288（本机） |
| 2 | **user7fuda2** | zo2 | ts10:10005 |
| 3 | **reedemma** | zo3 | ts13:10037 |

## 统一 ngrok（主隧道固定）

- **公网唯一入口**: https://scientist-primary-pregnancy.ngrok-free.dev
- **舰队总览**: https://scientist-primary-pregnancy.ngrok-free.dev/fleet
- **本机实况**: https://scientist-primary-pregnancy.ngrok-free.dev/
- 仅 **xzxyuan** 跑 ngrok；zo2/zo3/gcore 只监听本机 `8765`，状态经 SSH 汇总到主域名。

## 节点

| node_id | 说明 | SSH |
|---------|------|-----|
| xzxyuan | Zo-1 本机 | — |
| zo2 | Zo-2 (user7fuda2) | ts10:10005 |
| zo3 | Zo-3 (reedemma) | ts13:10037 |
| gcore | Gcore 裸机 | **工作区未配置 SSH**，需补 `deploy/nodes.json` 后 `remote_deploy.sh gcore` |

## 代理（每台独立）

- 订阅：`邮箱注册/mihomo_runtime/subscriptions.json`（zo2/zo3 首次从 xzxyuan 复制种子）
- 启动：`outlook_launcher` / `subscription_proxy` → **mihomo :28888**，注册前 **轮询切换节点**（`ProxyRotator`）
- 环境变量：`SUB_PROXY_FAST_START=1`

## 部署

```bash
# 从 xzxyuan
bash Email-Register/deploy/remote_deploy.sh zo2
bash Email-Register/deploy/remote_deploy.sh zo3
# 启用 supervisor（若未自动）
OUTLOOK_REGISTRAR_NODE=zo2 bash Email-Register/deploy/remote_enable_supervisor.sh
```

## 汇总成果（按 node 区分）

```bash
python3 Email-Register/deploy/collect_all_nodes.py
```

输出：`runtime_outlook/fleet/fleet_latest.md` / `.json`

## 外网面板

- xzxyuan: ngrok → `outlook_daemon_with_tunnel.sh`
- zo2/zo3: 本机 `:8765`（需在各自 Zo 注册 ngrok 或 Hosting 服务）

## 修复 zo3 / gcore

```bash
bash Email-Register/deploy/apply_fix_zo3_gcore.sh
```

- **zo3 toml**: `apt install python3-toml` + `__init__.py` 懒加载
- **gcore 日志**: `chown ubuntu:ubuntu runtime_outlook`