"""
嵌入模块：把文本编码成向量。

两个设计要点：
1.懒加载单例--模型加载慢又占内存，第一次用到才加载，之后全局复用。
2.可注入-- 留set_embed_fn()后门，测试时替换成假向量，不加载真模型。
"""
import logging
from typing import Callable
import numpy as np


logger = logging.getLogger(__name__)

# 中文语义检索常用的小模型，512维，约95MB
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

# 模块级"全局变量":缓存加载好的模型 / 注入的假函数
_model = None
_custom_embed_fn: Callable[[list[str]],np.ndarray] | None = None


def set_embed_fn(fn: Callable[[list[str]],np.ndarray] | None = None) -> None:
    """注入自定义嵌入函数(测试用).传None恢复用真实模型。"""
    global _custom_embed_fn
    _custom_embed_fn = fn

def _get_model():
    """懒加载：第一次调用时才真正加载模型，之后复用同一个实例。"""
    global _model
    if _model is None:
        # 注意：import 也放在函数内，避免模块一被导入就拖入沉重的torch依赖
        from sentence_transformers import SentenceTransformer
        logger.info("正在加载嵌入模型%s...",MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("嵌入模型加载完成")
    return _model

def embed_texts(texts:list[str]) -> np.ndarray:
    """批量把文本编码成向量，返回shape[N,512]的float32数组。"""
    # 有注入的假函数就用假的（测试路径）,否则走真模型
    if _custom_embed_fn is not None:
        return _custom_embed_fn(texts)
    model = _get_model()
    # normalize_emveddings=True:把向量归一化成单位长度
    # 这样后面算"余弦相似度"直接点积就行，省一步除法。
    embeddings = model.encode(texts,normalize_embeddings=True)
    return np.array(embeddings,dtype=np.float32)

def embed_query(text:str) -> np.ndarray:
    """编码单条查询，返回shape[512]的一维向量（检索时用）。"""
    return embed_texts([text])[0]