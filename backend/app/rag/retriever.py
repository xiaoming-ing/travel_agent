"""
混合检索：为每个候选景点名，从用户该城市的chunk里找最相关的几段。

打分 = 余弦相似度+子串命中加权。
- 余弦相似度：语义匹配（向量已归一化，点积即余弦）。
- 子串加权：chunk里出现了景点名，+BONUDS，因为专有名词字面命中是强信号。
取超过 threshold的Top-k。任何异常都降级为空结果，绝不阻断行程生成。
"""
import logging
from app.rag import store
import numpy as np
from app.rag.embedding import embed_texts


logger = logging.getLogger(__name__)

BONUS = 0.3  # 子串命中的加权分
THRESHOLD = 0.35 # 低于此分视为不相关，丢弃
TOP_K = 3  # 每个景点最多保留几段

async def retrieve_for_attractions(
    user_id: str,
    city: str,
    names: list[str],
    top_k: int = TOP_K,
    threshold:float = THRESHOLD,
) -> dict[str,list[str]]:
    """
    为每个景点检索相关段落。
    Returns:
        {景点名：[命中段落，...]}；无命中的景点名不会出现在结果里面。
        任何异常 -> 返回{}(降级)。
    """
    try:
        # 1.取出该用户在该城市的全部chunk(数据量小，全局加载)
        rows = await store.fetch_city_chunks(user_id,city)
        if not rows:
            return {}
        
        contents = [r["content"] for r in rows]
        # 把每条chunk的embedding 字节还原成向量，堆成矩阵[N,512]
        chunk_vecs = np.array(
            [np.frombuffer(r["embedding"],dtype=np.float32) for r in rows]
        )

        # 2.一次性批量编码所有景点名[M,512]
        name_vecs = embed_texts(names)

        result:dict[str,list[str]] = {}
        for name,name_vec in zip(names,name_vecs):
            # 3.余弦相似度 = 点积(向量已归一化)。
            # chunk_vecs @ name_vec 得到[N]个分数，一个chunk 一个分。@是矩阵乘法
            scores = chunk_vecs @ name_vec

            # 4.子串命中加权：chunk里出现景点名就+BONUS
            for i,content in enumerate(contents):
                if name in content:
                    scores[i] += BONUS
            
            # 5.过滤低分+取Top-K
            # argsort 默认升序，[::-1]翻转成降序，取前top_k个下标
            ranked_idx = np.argsort(scores)[::-1][:top_k]
            hits = [contents[i] for i in ranked_idx if scores[i] >= threshold]

            if hits:
                result[name] = hits
        
        return result
    
    except Exception :
        logger.warning("RAG检索失败,降级为无参考资料",exc_info=True)
        return {}
