# 部署说明

本项目分前端（Vue + Vite）和后端（FastAPI + LangGraph）两部分。后端用 SQLite 存对话状态和历史记录，适合单机 / 中低并发部署。

## 架构概览

```
浏览器 ──→ Nginx ──┬─→ /        前端静态文件（npm run build 产物）
                   └─→ /api/*   反向代理到后端 FastAPI (8000)
                                  └─→ LangGraph + SQLite (checkpoints.db)
```

前端代码里 API 用相对路径 `/api/...`，**依赖 Nginx 把 `/api` 转发给后端**，所以前后端可以同域部署，前端无需配置后端地址。

推荐服务器：国内云厂商（阿里云/腾讯云）的**轻量应用服务器**，选**中国香港/新加坡**等海外节点——免 ICP 备案，支付宝/微信付款方便，2 vCPU + 2GB 内存起步足够。

---

## 零、买服务器 + 连接服务器

1. 控制台买一台轻量应用服务器：地域选香港/新加坡，镜像选 Ubuntu（22.04/24.04 均可），至少 2 vCPU 2GB 内存（1GB 跑这套 LangChain 技术栈容易 OOM）。
2. 买完先点"**设置密码**"，设一个登录密码——这一个密码同时用于网页版"远程连接"（WebShell）和后面的直连 SSH，是同一套系统账号密码。
3. 控制台"**防火墙**"页签，确认放行 `22`（SSH）、`80`（HTTP）端口，来源填 `0.0.0.0/0`。
4. 先用网页版"**远程连接**"登进去，注意登录用户名（通常是 `admin` 之类的账号，不一定是 `root`），后续所有命令需要 root 权限的都先 `sudo -i` 提权一次。

> 如果本地直连 SSH 一直失败，见文末「常见问题排查」。

---

## 一、服务器基础环境

```bash
sudo -i   # 提权到 root，后面命令都在 root 身份下执行
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx rsync sqlite3
```

（前端在本地 build 好直接传 `dist/` 产物，服务器不需要装 Node。）

---

## 二、把代码传到服务器

用 `rsync` 从本地传，配合 [backend/deploy-exclude.txt](backend/deploy-exclude.txt) 过滤掉本地开发用的文件（虚拟环境、缓存、测试、本地 `.env`/`checkpoints.db` 等）：

```bash
# 服务器上先建好目标目录，权限给登录用户（把 admin 换成你的实际用户名）
sudo mkdir -p /opt/travel-agent/backend /opt/travel-agent/frontend/dist
sudo chown -R admin:admin /opt/travel-agent

# 本地 Mac 终端执行
cd /Users/admin/AI/travel-agent
rsync -avz --exclude-from=backend/deploy-exclude.txt \
  backend/ admin@<服务器公网IP>:/opt/travel-agent/backend/
```

---

## 三、后端部署

### 1. 装依赖

```bash
cd /opt/travel-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
nano .env
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | LLM |
| `GAODE_API_KEY` | ✅ | 景点 / 酒店 POI |
| `WEATHER_API_KEY` / `WEATHER_API_HOST` | ✅ | 天气 |
| `JWT_SECRET` | ✅ | 必须换成新的强随机值，不能沿用本地开发的那份。生成：`python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `CHECKPOINTS_DB` | ⬜ | SQLite 路径。**不要留空字符串 `''`**（见下方⚠️），留空不写这一行，或者直接填绝对路径如 `/opt/travel-agent/backend/checkpoints.db` |
| `CORS_ORIGINS` | ⬜ | 改成实际访问地址，比如 `http://<公网IP>` 或 `https://your-domain.com` |
| `LOG_LEVEL` | ⬜ | 默认 `INFO` |

> ⚠️ **`CHECKPOINTS_DB=''` 是个真实踩过的坑**：`.env` 里写成空字符串会被 `python-dotenv` 解析成"变量存在但值为空"，而代码里 `os.getenv("CHECKPOINTS_DB", "checkpoints.db")` 的默认值**只在变量完全不存在时生效**，空字符串会原样传给 SQLite。SQLite 对空字符串路径的行为是"每次连接都创建一个用完即焚的独立临时数据库"——现象就是启动时建表"成功"（其实建在一个马上被丢弃的临时库里），但一请求就报 `no such table: xxx`。解法：这一行要么整行删掉，要么写清楚的路径，不能留空字符串。

### 3. systemd 常驻

```bash
cat > /etc/systemd/system/travel-agent.service <<'EOF'
[Unit]
Description=Travel Agent Backend
After=network.target

[Service]
WorkingDirectory=/opt/travel-agent/backend
ExecStart=/opt/travel-agent/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now travel-agent
systemctl status travel-agent   # 确认 active (running)
```

> ⚠️ **必须 `--workers 1`**。SQLite 不支持多进程并发写，多 worker 会出现 `database is locked`。
> 瓶颈是 LLM 调用的等待（IO），单 worker + 异步已能扛不少并发。
> 如需横向扩展，把 checkpointer 换成 `AsyncPostgresSaver` + Postgres（只需改 `main.py` 创建 checkpointer 那一行 + DB 连接）。

### 4. 验证

```bash
curl http://localhost:8000/api/health   # → {"status":"ok"}
```

---

## 四、前端构建 + 上传

```bash
# 本地
cd frontend
cp .env.example .env
# 填入 VITE_AMAP_KEY（高德 Web 端 JS API Key）
npm install
npm run build      # 产物在 dist/

rsync -avz dist/ admin@<服务器公网IP>:/opt/travel-agent/frontend/dist/
```

---

## 五、Nginx 配置

```bash
cat > /etc/nginx/sites-available/travel-agent <<'EOF'
server {
    listen 80;
    server_name _;   # 有域名的话换成 your-domain.com

    location / {
        root /opt/travel-agent/frontend/dist;
        try_files $uri $uri/ /index.html;   # SPA 路由回退
    }

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
EOF

ln -sf /etc/nginx/sites-available/travel-agent /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

> SSE（`/api/chat/*` 流式接口）依赖 `proxy_buffering off`，这步漏了会导致"对话没反应、等很久才一次性出结果"。

有域名的话，用 `certbot --nginx -d your-domain.com` 签发免费证书，同时记得把 `.env` 的 `CORS_ORIGINS` 也同步改成 `https://your-domain.com`。

---

## 六、验证

浏览器打开 `http://<公网IP>`，应该能看到登录页，注册/登录走一遍确认没有 502/500。

---

## 七、把某个用户设为管理员（不限配额）

管理员没有专门的 API，直接改数据库：

```bash
# 看现有用户
sqlite3 /opt/travel-agent/backend/checkpoints.db "SELECT username, role FROM users;"

# 把目标用户改成 admin（换成实际用户名）
sqlite3 /opt/travel-agent/backend/checkpoints.db "UPDATE users SET role='admin' WHERE username='你的用户名';"
```

`role` 是每次请求实时查库（`app/api/deps.py` 的 `require_quota`），改完立即生效，不用重启服务、也不用重新登录。

---

## 八、上线检查清单

- [ ] 后端 `.env` 填好全部必填 key
- [ ] `JWT_SECRET` 是新生成的强随机值，不是本地开发那份
- [ ] `CHECKPOINTS_DB` 没有留空字符串（整行删掉或填绝对路径）
- [ ] `CORS_ORIGINS` 改成前端真实访问地址
- [ ] `LOG_LEVEL=INFO`（关掉 DEBUG 冗余日志）
- [ ] 前端 `npm run build` 且 `VITE_AMAP_KEY` 已配置
- [ ] Nginx `/api` 反代 + `proxy_buffering off`
- [ ] `systemctl status travel-agent` 是 `active (running)`
- [ ] `curl /api/health` 通，浏览器实际注册/登录一遍
- [ ] `.env` 不在 git 里（已在 `.gitignore`）
- [ ] 云控制台防火墙放行 22 / 80（有域名再加 443）

---

## 九、常见问题排查

**SSH `Permission denied (publickey,password)`，且没弹密码输入框**
服务器 SSH 配置禁用了密码登录。去服务器（网页 WebShell）执行 `grep -i passwordauthentication /etc/ssh/sshd_config`，如果是 `no`，改成 `yes` 并 `systemctl restart sshd`。

**SSH `Operation timed out`**
网络层没连上，通常是云控制台"防火墙"没放行 22 端口，或者本地网络/公司防火墙本身封了出站 22 端口（可以用 `nc -zv -w 5 <IP> 22` 和 `nc -zv -w 5 <IP> 80` 对比测试）。

**SSH 弹了密码框但提示 `Permission denied, please try again`**
纯粹密码错了。去控制台重新"设置密码"，或者直接在服务器上 `passwd <用户名>` 改一个自己确认无误的密码再试。

**浏览器请求 API 报 502 Bad Gateway**
Nginx 转发给后端时没人应答，说明 uvicorn 没在跑。`systemctl status travel-agent` 看状态，`journalctl -u travel-agent -n 50 --no-pager` 看具体报错。

**后端启动报 `ImportError: cannot import name 'ServerInfo' from 'langgraph.runtime'`（或类似 langchain/langgraph 互相导入失败）**
`requirements.txt` 里 `langchain`/`langgraph` 系列包版本没锁全，pip 解析出了互不兼容的组合。解法：去本地平时跑测试、确认没问题的 conda 环境里 `pip freeze | grep -iE "langchain|langgraph"`，把验证过的版本号原样搬到服务器的 `requirements.txt` 里再重装。

**请求返回 500，日志里是 `sqlite3.OperationalError: no such table: xxx`**
看本文档「三、后端部署」里 `CHECKPOINTS_DB` 那条 ⚠️——大概率是这个值被设成了空字符串。
