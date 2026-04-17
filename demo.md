项目整体结构

travel-agent/
├── backend/                  # Python 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置（API keys、模型参数等）
│   │   ├── agents/           # 各个 Agent 定义
│   │   │   ├── __init__.py
│   │   │   ├── supervisor.py # 总协调
│   │   │   ├── weather.py    # 天气分析 Agent
│   │   │   ├── budget.py     # 预算分析 Agent
│   │   │   ├── planner.py    # 行程规划 Agent
│   │   │   ├── food.py       # 美食推荐 Agent
│   │   │   └── transport.py  # 交通建议 Agent
│   │   ├── graph/            # LangGraph 编排
│   │   │   ├── __init__.py
│   │   │   ├── state.py      # 共享 State 定义
│   │   │   ├── nodes.py      # 图节点（调用各 Agent）
│   │   │   └── workflow.py   # 构建 StateGraph，定义边和路由
│   │   ├── tools/            # Agent 可调用的工具
│   │   │   ├── __init__.py
│   │   │   ├── weather_api.py
│   │   │   ├── map_api.py
│   │   │   └── price_api.py
│   │   ├── schemas/          # Pydantic 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── request.py
│   │   │   └── response.py
│   │   └── api/              # API 路由
│   │       ├── __init__.py
│   │       └── routes.py     # /chat, /stream 等端点
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                 # Vue3 前端
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   ├── components/
│   │   │   ├── ChatWindow.vue      # 聊天主窗口
│   │   │   ├── MessageBubble.vue   # 单条消息气泡
│   │   │   ├── InputBar.vue        # 输入框
│   │   │   ├── TripCard.vue        # 行程卡片展示
│   │   │   └── AgentStatus.vue     # 显示当前哪个Agent在工作
│   │   ├── views/
│   │   │   ├── HomeView.vue
│   │   │   └── ChatView.vue
│   │   ├── stores/           # Pinia 状态管理
│   │   │   └── chat.ts
│   │   ├── api/              # 请求封装
│   │   │   └── client.ts
│   │   ├── types/            # TypeScript 类型
│   │   │   └── index.ts
│   │   └── router/
│   │       └── index.ts
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   ├── Dockerfile
│   └── tsconfig.json
├── docker-compose.yml        # 一键启动前后端
├── .env.example
└── README.md