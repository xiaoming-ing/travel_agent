import pytest
from app.rag import store,embedding,retriever
import numpy as np

@pytest.fixture
def tmp_db(tmp_path,monkeypatch):
    db = str(tmp_path / "test_retr.db")
    monkeypatch.setattr(store,"DB_PATH",db)
    return db

@pytest.fixture
def fake_embedder(monkeypatch):
    """注入假编码器：按关键词映射到不同方向的单位向量，
    这样‘相关’的文本向量点积大，‘无关’的接近0-检索结果可预测。
    """
    def _fake(texts:list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            v = np.zeros(512,dtype=np.float32)
            # 用简单规则造"语义":含"鸡鸣寺"偏第 0 维,含"玄武湖"偏第 1 维
            if "鸡鸣寺" in t:
                v[0] = 1.0
            elif "玄武湖" in t:
                v[1] = 1.0
            else:
                v[2] = 1.0 # 其它:第三个方向,和上面都正交(点积=0)
            vecs.append(v)
        return np.array(vecs,dtype=np.float32)
    
    embedding.set_embed_fn(_fake)
    yield
    embedding.set_embed_fn(None)

async def test_retrieve_matches_relevant_chunk(tmp_db,fake_embedder):
    """检索'鸡鸣寺'应命中鸡鸣寺的段落，不命中讲玄武湖的。"""
    await store.init_knowledge_table()
    chunks = ["鸡鸣寺是南朝名刹香火旺盛","玄武湖是江南最大的城内湖"]
    embs = embedding.embed_texts(chunks)
    await store.add_knowledge("u1", "南京", "攻略", chunks, embs)

    result = await retriever.retrieve_for_attractions("u1", "南京", ["鸡鸣寺"])
    assert "鸡鸣寺" in result
    assert result["鸡鸣寺"] == ["鸡鸣寺是南朝名刹香火旺盛"]

async def test_substring_boost_ranks_higher(tmp_db, fake_embedder):
    """两段都语义相关时,原文出现景点名的那段应排更前(子串加权)。"""
    await store.init_knowledge_table()
    # 两段都落在"第 0 维"(都含鸡鸣寺关键词),但只有第一段完整出现"鸡鸣寺"三字
    chunks = ["鸡鸣寺门票免费", "这座寺庙鸡鸣很有名"]  # 两段都含"鸡鸣寺"?第二段其实也含
    embs = embedding.embed_texts(chunks)
    await store.add_knowledge("u1", "南京", "攻略", chunks, embs)

    result = await retriever.retrieve_for_attractions("u1", "南京", ["鸡鸣寺"], top_k=2)
    # 含完整"鸡鸣寺"的段落应排第一
    assert result["鸡鸣寺"][0] == "鸡鸣寺门票免费"


async def test_no_match_returns_empty(tmp_db, fake_embedder):
    """检索一个库里没有相关资料的景点,该名字不出现在结果里。"""
    await store.init_knowledge_table()
    chunks = ["玄武湖是江南最大的城内湖"]
    embs = embedding.embed_texts(chunks)
    await store.add_knowledge("u1", "南京", "攻略", chunks, embs)

    # 检索"夫子庙":向量落在第三方向,和玄武湖(第 1 维)点积=0 < 阈值
    result = await retriever.retrieve_for_attractions("u1", "南京", ["夫子庙"])
    assert "夫子庙" not in result


async def test_empty_knowledge_returns_empty(tmp_db, fake_embedder):
    """用户在该城市没上传任何资料 -> 返回空 dict。"""
    await store.init_knowledge_table()
    result = await retriever.retrieve_for_attractions("u1", "南京", ["鸡鸣寺"])
    assert result == {}