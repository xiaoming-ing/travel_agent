import pytest
from app.db import conversation_store as cs


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test_conv.db")
    monkeypatch.setattr(cs, "DB_PATH", db)
    return db


async def test_create_conversation_stores_user_id(tmp_db):
    await cs.init_table()
    await cs.create_conversation(
        "t1", "南京", "2026-07-01", "2026-07-03", user_id="u1"
    )
    conv = await cs.get_conversation("t1")
    assert conv["user_id"] == "u1"


async def test_create_conversation_user_id_defaults_empty(tmp_db):
    await cs.init_table()
    await cs.create_conversation("t2", "成都", "2026-07-01", "2026-07-03")
    conv = await cs.get_conversation("t2")
    assert conv["user_id"] == ""