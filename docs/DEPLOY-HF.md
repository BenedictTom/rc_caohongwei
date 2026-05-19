# 部署：Hugging Face Spaces（后端） + Vercel（前端）

约束达成：保留 SQLite、不动后端代码、零成本、

## 拓扑

```
浏览器
  │
  ├─→ rc-caohongwei.vercel.app          (前端 Next.js, Vercel)
  │
  └─→ <你的用户名>-rc-caohongwei.hf.space (后端 Docker, HF Spaces)
        ├─ uvicorn :8000               ← 对外
        ├─ mock_provider :8500         ← 容器内部
        └─ /data/notifications.db      ← 容器临时存储（48h idle 后清空）
```

> **持久化权衡**：HF Spaces 免费层使用临时存储，容器若 48 小时无访问会被休眠/重启，SQLite 数据清空。这对作业演示完全够用——评审者点开看到 dashboard、能新建通知、能看到状态变化即可。

---

## 前置条件

- Hugging Face 账号：[huggingface.co/join](https://huggingface.co/join)（GitHub / 邮箱注册，**不要卡**）
- Vercel 账号：[vercel.com/signup](https://vercel.com/signup)（GitHub 一键，**不要卡**）
- 仓库已推到 GitHub

---

## 步骤 1：创建 HF Space

1. 登录 HF → 右上角 **+** → **New Space**
2. 表单填写：
   - **Owner**: 你的用户名
   - **Space name**: `rc-caohongwei`（最终 URL：`https://你的用户名-rc-caohongwei.hf.space`）
   - **License**: 任选（MIT / Apache 2.0 都行）
   - **Select the Space SDK**: 选 **Docker**（关键！）
   - **Docker template**: 选 **Blank**
   - **Hardware**: **CPU basic**（免费，2 vCPU 16GB RAM，足够）
   - **Visibility**: Public
3. **Create Space**

刚创建的 Space 是个空 git repo，已经有一个默认 `README.md`。

---

## 步骤 2：把仓库代码推到 HF Space

HF Space 有个独立的 git remote（在 HF 平台上），我们要把 GitHub 仓库的代码 push 上去。

### 2.1 登录 HF CLI（一次性）

```bash
# 装 huggingface_hub（如果还没装）
pip install -U huggingface_hub

# 登录：会让你输入 Token（在 https://huggingface.co/settings/tokens 创建一个 "write" 权限的 token）
huggingface-cli login
```

### 2.2 把 HF Space 添加为第二个 git remote

在仓库根目录：

```bash
# 替换 <你的用户名>
git remote add hf https://huggingface.co/spaces/<你的用户名>/rc-caohongwei

# 验证
git remote -v
# origin    https://github.com/<你>/rc_caohongwei.git (push)
# hf        https://huggingface.co/spaces/<你>/rc-caohongwei (push)
```

### 2.3 处理 README 冲突

HF Space 创建时给你了一个默认 README.md，本地仓库也有一份（已经加好 HF frontmatter 的）。先拉一下 HF Space 当前 main 分支：

```bash
git fetch hf
# 看下 hf/main 上的 README.md 与本地哪个更新——通常本地的更全
# 直接强推（覆盖 HF 上的默认 README）
git push hf main --force
```

或者更稳妥——拉 HF main 然后 rebase 然后推：

```bash
git pull hf main --allow-unrelated-histories
# 如果有冲突，保留本地的 README.md（它有 frontmatter + 完整文档）
# 然后
git push hf main
```

### 2.4 等 HF 自动 build

推送完之后 HF Space 会自动 build Docker 镜像。访问 `https://huggingface.co/spaces/<你>/rc-caohongwei` 看构建日志：

- 看到 `Building Docker image...`
- 然后 `Pushing image to registry...`
- 最后 `Container running` 或 `Running` 状态变绿

整个过程约 3-8 分钟（首次 build，pip install 比较慢）。

### 2.5 验证后端

构建完成后 Space 顶部会显示一个 iframe 嵌入预览——里面会 fetch `/healthz`，但 FastAPI 默认 `/` 没东西，会显示 404。这正常。直接 curl 验证：

```bash
# 你的 Space 公网 URL
SPACE_URL=https://<你的用户名>-rc-caohongwei.hf.space

curl $SPACE_URL/healthz
# → {"status":"ok","db":"ok","scheduler":"ok","failed":[]}

curl $SPACE_URL/v1/providers | head -c 300
# → 三个 provider 配置 JSON

# 提交一条通知试投递
curl -X POST $SPACE_URL/v1/notifications \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: hf-smoke-1' \
  -d '{"provider":"demo-inventory","payload":{"sku":"A","qty":1}}'

sleep 4
curl "$SPACE_URL/v1/notifications?q=hf-smoke-1"
# items[0].status 应该是 SUCCEEDED
```

### 2.6 设 CORS（先用通配，前端部完再回头收紧）

HF Space 的环境变量在 Space settings → **Variables and secrets** 配置：

1. Space 页面右上 ⚙️ Settings
2. 滚到 **Variables and secrets** → **New variable**
3. Name: `CORS_ALLOW_ORIGINS`，Value: `["*"]`，类型选 **Variable**（不是 secret，因为不敏感）
4. 保存——Space 自动 restart

---

## 步骤 3：部署前端到 Vercel

1. [vercel.com/new](https://vercel.com/new) → Import GitHub repo（选 `rc_caohongwei`）
2. **Root Directory**: 点 `Edit` 改成 `web`（关键！）
3. **Framework Preset**: 自动检测为 Next.js ✓
4. **Environment Variables** 加一条：
   - Key: `NEXT_PUBLIC_API_BASE`
   - Value: `https://<你的用户名>-rc-caohongwei.hf.space`
   - 勾上 **All environments**（Production + Preview + Development）
5. **Deploy**

约 1-2 分钟编译完，拿到 `https://rc-caohongwei-xxxx.vercel.app`。

### 验证

打开前端 URL，依次确认 5 个页面：

| 页面 | 应该看到 |
|---|---|
| `/` Dashboard | 4 个 metric card 有数字（hf-smoke-1 那条已成功，successRate=1.0） |
| `/notifications` | 至少 1 条 SUCCEEDED |
| `/notifications/new` | 走完三步提交，toast `已受理` |
| `/dead-letters` | 空 / 偶有几条（mock fail-rate=0.10 偶发触发） |
| `/providers` | 3 个 provider 卡片，breaker CLOSED |

---

## 步骤 4（可选）：收紧 CORS

回到 HF Space settings → Variables → 把 `CORS_ALLOW_ORIGINS` 改成：

```
["https://rc-caohongwei-xxxx.vercel.app"]
```

Space 自动 restart 即生效。

---

## 给评审者的链接模板

```
作业项目：API 通知中转网关 MVP
- 前端 demo:    https://rc-caohongwei-xxxx.vercel.app
- 后端 API:     https://<你的用户名>-rc-caohongwei.hf.space
- 健康检查:     https://<你的用户名>-rc-caohongwei.hf.space/healthz
- FastAPI docs: https://<你的用户名>-rc-caohongwei.hf.space/docs
- 源码:         https://github.com/<你>/rc_caohongwei

技术栈：FastAPI + SQLite + APScheduler / Next.js 15 + shadcn
设计文档与 AI 使用说明见 README.md（顶部 YAML frontmatter 是 HF Space 配置，可忽略）。
```

---

## 已知陷阱

| 现象 | 原因 | 应对 |
|---|---|---|
| `git push hf main` 报 "non-fast-forward" | HF 默认 README 与本地有冲突 | `git push hf main --force`（首次部署可以强推） |
| HF 构建失败提示 "no such file" | `.dockerignore` 排错文件 | 确认 `app/`、`tools/`、`providers.yaml`、`pyproject.toml`、`README.md` 都在 git tracked |
| 前端报 CORS 错误 | `CORS_ALLOW_ORIGINS` 格式错 | 必须严格 JSON 数组：`["*"]` 或 `["https://..."]`，注意引号 |
| 投递永远失败 / `connect_error` | 容器内 mock 没起来 | HF Space → Logs tab，搜 `mock provider listening`；没有就是 `sh -c` 后台启动失败，告诉我我改 supervisord |
| HF Space 显示 "Sleeping" | 48h 无访问被休眠 | 第一次访问会冷启动 ~30s；想保活可挂个 cron job 每 24h ping 一次 `/healthz` |
| 前端 build 失败：`turbopack` 报错 | Vercel 上 turbopack production build 偶发不稳 | `web/package.json` 把 `"build": "next build --turbopack"` 临时改成 `"build": "next build"` |

---

## 后续更新

- **后端代码改动**：`git push origin main`（GitHub）+ `git push hf main`（HF Space）
- **前端代码改动**：`git push origin main`，Vercel 自动部署，无需额外操作
- **HF Space 改 env**：在 Space settings 改完会自动 restart

---

## 替代部署路径

| 平台 | 何时考虑 | 文档 |
|---|---|---|
| Fly.io | 想要持久化 SQLite + 能绑信用卡 | 仓库根 `fly.toml` 已就绪，参考 [fly.io/docs/launch](https://fly.io/docs/launch/) |
| Zeabur | 已经有 VPS（Zeabur 现已改 BYO server 模式） | [DEPLOY-ZEABUR.md](DEPLOY-ZEABUR.md) |
