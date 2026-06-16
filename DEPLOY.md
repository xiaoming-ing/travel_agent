# 部署说明

本项目分前端（Vue + Vite）和后端（FastAPI + LangGraph）两部分。后端用 SQLite 存对话状态和历史记录，适合单机 / 中低并发部署。

## 架构概览

```
浏览器 ──→ Nginx ──┬─→ /        前端静态文件（npm run build 产物）
                   └─→ /api/*   反向代理到后端 FastAPI (8000)
                                  └─→ LangGraph + SQLite (checkpoints.db)
```

前端代码里 API 用相对路径 `/api/...`，**依赖 Nginx 把 `/api` 转发给后端**，所以前后端可以同域部署，前端无需配置后端地址。

---

## 一、后端

### 1. 安装依赖

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入真实值：

```bash
cp .env.example .env
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | LLM |
| `GAODE_API_KEY` | ✅ | 景点 / 酒店 POI |
| `WEATHER_API_KEY` / `WEATHER_API_HOST` | ✅ | 天气 |
| `CHECKPOINTS_DB` | ⬜ | SQLite 路径，默认 `checkpoints.db`，建议指向持久化目录如 `/data/checkpoints.db` |
| `CORS_ORIGINS` | ⬜ | 允许的前端域名，逗号分隔，默认本地端口 |
| `LOG_LEVEL` | ⬜ | 默认 `INFO`，排查问题设 `DEBUG` |

### 3. 启动

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> ⚠️ **必须 `--workers 1`**。SQLite 不支持多进程并发写，多 worker 会出现 `database is locked`。
> 瓶颈是 LLM 调用的等待（IO），单 worker + 异步已能扛不少并发。
> 如需横向扩展，把 checkpointer 换成 `AsyncPostgresSaver` + Postgres（只需改 `main.py` 创建 checkpointer 那一行 + DB 连接）。

### 4. 验证

```bash
curl http://localhost:8000/api/health   # → {"status":"ok"}
```

---

## 二、前端

### 1. 配置环境变量

```bash
cd frontend
cp .env.example .env
# 填入 VITE_AMAP_KEY（高德 Web 端 JS API Key）
```

### 2. 构建

```bash
npm install
npm run build      # 产物在 dist/
```

把 `dist/` 交给 Nginx 托管即可。

---

## 三、Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/frontend/dist;
        try_files $uri $uri/ /index.html;   # SPA 路由回退
    }

    # 后端 API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 流式接口必须关闭缓冲，否则前端收不到实时进度
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

> SSE（`/api/chat/*` 流式接口）依赖 `proxy_buffering off`，这步漏了会导致"对话没反应、等很久才一次性出结果"。

部署后记得把后端 `.env` 的 `CORS_ORIGINS` 改成 `http://your-domain.com`。

---

## 四、上线检查清单

- [ ] 后端 `.env` 填好全部必填 key
- [ ] `CORS_ORIGINS` 改成前端真实域名
- [ ] `LOG_LEVEL=INFO`（关掉 DEBUG 冗余日志）
- [ ] `CHECKPOINTS_DB` 指向持久化目录（重启 / 重新部署不丢历史）
- [ ] 前端 `npm run build` 且 `VITE_AMAP_KEY` 已配置
- [ ] Nginx `/api` 反代 + `proxy_buffering off`
- [ ] `curl /api/health` 通
- [ ] `.env` 不在 git 里（已在 `.gitignore`）
