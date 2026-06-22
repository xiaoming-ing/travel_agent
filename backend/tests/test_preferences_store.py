import pytest
from app.graph import perferences_store as ps
from datetime import date
import aiosqlite

@pytest.fixture # pytest测试夹具，给测试提供一个临时的、隔离的数据库，避免污染真实数据
# tmp_path pytest内置，每个测试都给一个全新的、空的临时目录。跑完自动清掉
def tmp_db(tmp_path,monkeypatch):
    db = str(tmp_path / "test_prefs.db") # 在临时目录拼一个db文件路径
    monkeypatch.setattr(ps,"DB_PATH",db) # 把模块里的 DB_PATH 偷偷换成这个临时路径
    return db


async def test_save_then_get_roundtrip(tmp_db):
    await ps.init_pref_table()
    await ps.save_preferences("u1",["历史文化","美食"],"豪华型酒店","自驾")
    got = await ps.get_preferences("u1")
    assert got == {
        "preferences": ["历史文化", "美食"],
        "accommodation": "豪华型酒店",
        "transport": "自驾",
    }

async def test_get_miss_returns_none(tmp_db):
    await ps.init_pref_table()
    assert await ps.get_preferences("nobody") is None


async def test_save_is_upsert_no_duplicate(tmp_db):
    await ps.init_pref_table()
    await ps.save_preferences("u1", ["美食"], "经济型酒店", "公共交通")
    await ps.save_preferences("u1", ["艺术"], "民宿", "步行")
    got = await ps.get_preferences("u1")
    assert got["preferences"] == ["艺术"]
    assert got["accommodation"] == "民宿"
    async with aiosqlite.connect(tmp_db) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM user_preferences WHERE user_id='u1'"
        ) as cur:
            (count,) = await cur.fetchone()
    assert count == 1


def test_pref_fields_from_request_handles_dict():
    f = ps.pref_fields_from_request(
        {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}
    )
    assert f == {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}


def test_pref_fields_from_request_handles_object():
    from app.schemas import TripRequest
    req = TripRequest(
        destination="南京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        preferences=["历史文化"],
        accommodation="豪华型酒店",
        transport="自驾",
    )
    f = ps.pref_fields_from_request(req)
    assert f == {
        "preferences": ["历史文化"],
        "accommodation": "豪华型酒店",
        "transport": "自驾",
    }