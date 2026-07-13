import pytest
from app.rag import store
import numpy as np

@pytest.fixture
def tmp_db(tmp_path,monkeypatch):
    """给每个测试一个全新的临时数据库，不污染真实checkpoints.db
    monkeypatch把store模块里的DB_PATH偷偷换成临时路径。
    """
    db = str(tmp_path/"test_knowledge.db")
    monkeypatch.setattr(store,"DB_PATH",db)
    return db

async def test_add_and_list(tmp_db):
    """上传一批chunk后，list_uploads能查到这一批(含chunk数量)。"""
    await store.init_knowledge_table()
    chunks = ["南京鸡鸣寺是南朝名刹","春季樱花大道很美"]
    embeddings = np.random.rand(2,512).astype(np.float32)
    upload_id = await store.add_knowledge("u1","南京","小红书攻略",chunks,embeddings)

    uploads = await store.list_uploads("u1")
    assert len(uploads) == 1
    assert uploads[0]["upload_id"] == upload_id
    assert uploads[0]["city"] == "南京"
    assert uploads[0]["source"] == "小红书攻略"
    assert uploads[0]["chunk_count"] == 2

async def test_fetch_city_chunks_roundtrip(tmp_db):
    """存进去的向量，取出来能用frombuffer完整还原。"""
    await store.init_knowledge_table()
    embeddings = np.random.rand(1,512).astype(np.float32)
    await store.add_knowledge("u1","南京","攻略",["玄武湖畔风光好"],embeddings)

    results = await store.fetch_city_chunks("u1","南京")
    assert len(results) == 1
    assert results[0]["content"] == "玄武湖畔风光好"
    vec = np.frombuffer(results[0]["embedding"], dtype=np.float32)
    assert vec.shape == (512,)
    np.testing.assert_allclose(vec, embeddings[0], atol=1e-6)   # 数值一致


async def test_isolation_by_user(tmp_db):
    """不同用户的数据互相隔离。"""
    await store.init_knowledge_table()
    emb = np.random.rand(1,512).astype(np.float32)
    await store.add_knowledge("u1", "南京", "攻略", ["内容"], emb)
    await store.add_knowledge("u2", "南京", "攻略", ["内容"], emb)

    assert len(await store.fetch_city_chunks("u1", "南京")) == 1
    assert len(await store.fetch_city_chunks("u2", "南京")) == 1

async def test_delete_upload(tmp_db):
    """按upload_id删除，该批chunk全部清除。"""
    await store.init_knowledge_table()
    emb = np.random.rand(2,512).astype(np.float32)
    upload_id = await store.add_knowledge("u1","南京","攻略",["a","b"],emb)

    deleted = await store.delete_upload("u1",upload_id)
    assert deleted == 2
    assert await store.list_uploads("u1") == []

async def test_delete_only_own(tmp_db):
    """不能删别人的上传：u2删u1的批次，删除数为0"""
    await store.init_knowledge_table()
    emb = np.random.rand(1,512).astype(np.float32)
    upload_id = await store.add_knowledge("u1","南京","攻略",["x"],emb)

    deleted = await store.delete_upload("u2",upload_id)
    assert deleted == 0
    assert len(await store.list_uploads("u1")) == 1