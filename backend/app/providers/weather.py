import os
import requests

API_KEY=os.getenv("WEATHER_API_KEY")
API_HOST=os.getenv("WEATHER_API_HOST")
SUPPORT_DAYS = [3, 7, 10, 15, 30] # 和风支持的天数


def lookup_location_id(city:str) -> str:
    """根据城市名称查询locationID"""
    url = f"https://{API_HOST}/geo/v2/city/lookup"
    params = {"location":city,"key":API_KEY}
    resp = requests.get(url,params=params,timeout=10)
    data=resp.json()
    if data.get("code") == '200' and data.get("location"):
        return data["location"][0]["id"]
    return None

def pick_endpoint_days(trip_days:int) -> int:
    """根据出行天数选最合适的端点（向上取最近的支持值）"""
    for d in SUPPORT_DAYS:
        if trip_days <= d:
            return d
    return 30 # 超过三十天也只能查三十天

def fetch_weather(location_id:str,days:int=7) -> list[dict]:
    """查未来N天天气"""
    url = f"https://{API_HOST}/v7/weather/{days}d"
    params = {"location":location_id,"key":API_KEY}
    resp = requests.get(url,params=params,timeout=10)
    data = resp.json()
    if data.get("code") != "200":
        return []
    
    return [
        {
            "date": d["fxDate"],
            "day_weather": d["textDay"],
            "night_weather": d["textNight"],
            "max_temp": d["tempMax"],
            "min_temp": d["tempMin"],
            "wind": d["windDirDay"],
        }
        for d in data.get("daily", [])
    ]

    