import asyncio
from fastapi.testclient import TestClient
from app.db import preferences_store as ps
from app.core.security import create_access_token


def test_get_preferences_hit_and_miss(tmp_path, monkeypatch):
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(ps, "DB_PATH", db)
    asyncio.run(ps.init_pref_table())
    asyncio.run(ps.save_preferences("u1", ["美食"], "民宿", "步行"))

    from app.main import app
    client = TestClient(app)  # 不用 with：GET 接口不依赖 lifespan/图

    # user_id 不再放路径里，改由 token 解出，所以测试要带 Authorization 头
    token_u1 = create_access_token("u1")
    r = client.get("/api/preferences", headers={"Authorization": f"Bearer {token_u1}"})
    assert r.status_code == 200
    assert r.json() == {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}

    token_nobody = create_access_token("nobody")
    r2 = client.get("/api/preferences", headers={"Authorization": f"Bearer {token_nobody}"})
    assert r2.status_code == 200
    assert r2.json() == {}