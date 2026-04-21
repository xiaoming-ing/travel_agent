from fastapi.middleware.cors import CORSMiddleware
from app.graph.workflow import graph
from app.schemas import TripPlan,TripRequest
from fastapi import FastAPI, HTTPException
import traceback

app = FastAPI(title="旅行智能助手")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/api/plan",response_model=TripPlan)
async def plan(req:TripRequest):
    """
    生成完整旅行计划

    - 入参 TripRequest:FastAPI 自动按schema校验，缺必填字段会返回422
    - 出参 Tripplan:response_model指定后，FastAPI会过滤多余字段、按schema序列化
    """
    # LanGraph的initial state 是dict,按 TravelState的字段名放入
    initial_state = {"request":req}

    try:
        # ainvoke:异步跑完整个图，返回最终state
        # （如果以后想要“正在查天气。。。”这种流式进度，可以换成astream)
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        # LanGraph里任何节点抛异常都会冒到这
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=f"生成行程失败：{e}")
    
    trip_plan = final_state.get("trip_plan")
    if not trip_plan:
        raise HTTPException(status_code=500,detail="行程生成结果为空")
    
    return trip_plan

@app.get("/api/health")
async def heath():
    return {"status":"ok"}