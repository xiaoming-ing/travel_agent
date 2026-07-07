# AI 旅行智能规划助手

一个基于 FastAPI、LangGraph、LangChain 和 Vue3 的对话式旅行 Agent 项目。用户输入目的地、日期、交通方式、住宿偏好和旅行偏好后，系统会自动调用景点、天气、酒店等工具收集数据，并生成结构化旅行计划。生成后支持继续对话修改行程，例如替换某天景点、切换酒店档次等。

## 功能特性

- 对话式旅行规划：支持表单发起规划、Agent 追问缺失信息、生成后继续反馈修改。
- 两阶段 Agent 工作流：Phase 1 使用 ReAct Agent 调用工具收集数据，Phase 2 使用结构化输出生成完整行程。
- 外部数据接入：接入高德 POI、酒店搜索、天气 API，为景点、酒店、天气提供真实数据支撑。
- 行程修改 Agent：支持根据自然语言反馈替换指定天景点、重新推荐酒店，并自动补全新增景点 POI 信息。
- SSE 实时进度：前端实时展示景点搜索、天气查询、酒店推荐、AI 规划等执行进度。
- 用户体系：支持注册、登录、JWT 鉴权、bcrypt 密码哈希、接口限流。
- 历史会话：基于 LangGraph checkpoint 和 SQLite 保存对话状态与最终行程。
- 长期偏好记忆：行程完成后保存用户交通、住宿、兴趣偏好，下次自动回填。
- 配额控制：按用户统计 Token 使用量，支持月度配额和管理员免配额。
- 地图展示：前端基于高德地图展示景点 Marker、酒店 Marker 和路线连线。

## 技术栈

后端：

- Python
- FastAPI
- LangChain
- LangGraph
- DeepSeek Chat
- Pydantic
- SQLite / aiosqlite
- JWT / bcrypt
- pytest

前端：

- Vue 3
- TypeScript
- Vite
- Vue Router
- 高德地图 JS API
- SSE 流式读取

## 项目结构

```text
travel-agent
├── backend
│   ├── app
│   │   ├── agents        # Agent 工具、行程生成、修改工具
│   │   ├── api           # FastAPI 路由
│   │   ├── core          # 鉴权、限流、Token 统计等基础能力
│   │   ├── db            # SQLite 数据访问层
│   │   ├── graph         # LangGraph 工作流与 SSE streaming
│   │   └── schemas       # Pydantic 请求/响应模型
│   ├── tests             # 后端测试
│   └── requirements.txt
├── frontend
│   ├── src
│   │   ├── api           # 前端 API 和 SSE 读取
│   │   ├── components    # 行程展示组件
│   │   ├── views         # 登录、表单、聊天、结果页
│   │   └── types         # 前端类型定义
│   └── package.json
├── DEPLOY.md             # 服务器部署与二次发布流程
└── README.md
```

## 核心流程

```text
用户提交旅行需求
  -> LangGraph clarify 节点：校验日期、补充偏好
  -> Phase 1 ReAct Agent：调用景点/天气/酒店工具收集数据
  -> Phase 2 Structured Output：生成 TripPlan JSON
  -> feedback 节点：等待用户反馈
  -> revise 节点：按反馈调用修改工具
  -> 用户满意后结束并保存历史与偏好
```

## 环境变量

后端复制示例文件：

```bash
cd backend
cp .env.example .env
```

需要配置：

| 变量 | 说明 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API Key，用于 Agent 和行程生成 |
| `GAODE_API_KEY` | 高德 Web 服务 API Key，用于 POI / 酒店搜索 |
| `WEATHER_API_KEY` | 和风天气 API Key |
| `WEATHER_API_HOST` | 和风天气 API Host |
| `CHECKPOINTS_DB` | SQLite 数据库路径，默认 `checkpoints.db` |
| `CORS_ORIGINS` | 允许访问后端的前端地址 |
| `LOG_LEVEL` | 日志级别，默认 `INFO` |
| `DEFAULT_TOKEN_QUOTA` | 普通用户默认月度 Token 配额 |

前端复制示例文件：

```bash
cd frontend
cp .env.example .env
```

需要配置：

| 变量 | 说明 |
| --- | --- |
| `VITE_AMAP_KEY` | 高德 Web 端 JS API Key，用于前端地图渲染 |

## 本地运行

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:5173
```

## 测试

```bash
cd backend
pytest
```

当前测试覆盖：

- Agent 工作流失败兜底
- feedback 后的路由逻辑
- 会话存储
- 用户偏好 API
- 偏好持久化

## 构建

前端生产构建：

```bash
cd frontend
npm run build
```

构建产物位于：

```text
frontend/dist
```

## 部署

完整部署和二次发布流程见 [DEPLOY.md](DEPLOY.md)。

部署结构：

```text
浏览器
  -> Nginx
      -> /       前端 dist 静态文件
      -> /api/*  反向代理到 FastAPI
            -> LangGraph + SQLite
```

注意事项：

- 后端使用 SQLite checkpoint，生产部署建议 `uvicorn --workers 1`。
- SSE 接口需要在 Nginx 中关闭代理缓冲：`proxy_buffering off`。
- 前端修改后必须重新执行 `npm run build` 并上传 `frontend/dist/`。
- 后端代码修改后必须执行 `systemctl restart travel-agent`，只执行 `daemon-reload` 不会重启应用进程。

## 常见问题

### 页面还是旧版本

确认服务器 Nginx 实际服务目录：

```bash
sudo nginx -T | grep -n "root"
```

确认新构建产物已经上传：

```bash
grep -R "你的新文案" /opt/travel-agent/frontend/dist -n
```

如果搜不到，说明没有重新构建或没有上传正确的 `dist` 目录。

### 后端代码还是旧版本

普通代码更新后需要重启服务：

```bash
sudo systemctl restart travel-agent
sudo journalctl -u travel-agent -n 80 --no-pager
```

`systemctl daemon-reload` 只会重新加载 systemd 配置，不会重启正在运行的 Python 进程。

### 数据库报 `no such table`

检查 `.env` 里的 `CHECKPOINTS_DB`，不要写成空字符串。可以删除该配置使用默认值，或填写明确路径，例如：

```text
CHECKPOINTS_DB=/opt/travel-agent/backend/checkpoints.db
```
