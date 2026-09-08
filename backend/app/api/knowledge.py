"""
景点知识库API：上传攻略（分块+嵌入+入库）、列表、删除。

嵌入是CPU密集操作，用asyncio.to_thread丢线程池，避免阻塞事件循环。
所有接口经JWT鉴权，user_id从token取，前端无法伪造去操作别人数据。
"""
import logging
import asyncio
from fastapi import APIRouter,Depends,HTTPException
from app.api.deps import get_current_user_id
from app.rag import store
from app.rag.chunking import chunk_text
from app.rag.embedding import embed_texts
from app.schemas import KnowledgeUploadBody

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/api/knowledge")
async def upload_knowledge(
    body:KnowledgeUploadBody,
    user_id:str = Depends(get_current_user_id)
):
    """上传一篇攻略：分块->嵌入->入库。返回upload_id和chunk数。"""
    # 1.分块
    chunks = chunk_text(body.content)
    if not chunks:
        raise HTTPException(status_code=400,detail="内容为空，无法上传。")
    
    # 2.嵌入（CPU密集，丢线程池，不阻塞事件循环）
    try:
        embeddings = await asyncio.to_thread(embed_texts,chunks)
    except Exception:
        logger.exception("嵌入失败")
        raise HTTPException(status_code=500,detail="向量化失败，请稍后重试。")
    
    #3.入库(先嵌入成功再落库，避免写半份数据)
    upload_id = await store.add_knowledge(
        user_id,body.city,body.source,chunks,embeddings
    )
    return {"upload_id":upload_id,"chunk_count":len(chunks)}

@router.get("/api/knowledge")
async def list_knowledge(user_id:str = Depends(get_current_user_id)):
    """列出当前用户所有上传批次"""
    return await store.list_uploads(user_id)

@router.delete("/api/knowledge/{upload_id}")
async def delete_knowledge(
    upload_id:str,
    user_id:str = Depends(get_current_user_id)
):
    """删除当前用户名下指定批次。删不到(不存在或不属于自己)返回404"""
    deleted = await store.delete_upload(user_id,upload_id)
    if deleted == 0:
        raise HTTPException(status_code=404,detail="记录不存在")
    return {"deleted":deleted}
