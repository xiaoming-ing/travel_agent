# asycn retry + exponential backoff
import asyncio
import random
async def call_api():
    await asyncio.sleep(0.3)
    if random.random() < 0.7:
        raise Exception("API 调用失败")
    return "成功"

async def fetchApiWithRetry(retryCount):
    for i in range(retryCount):
        try:
            # Simulate an API call
            res = await call_api()
            return res
        except Exception as e:
            await asyncio.sleep(2**i)
    raise Exception("接口请求错误")

async def main():
    try:
        result = await fetchApiWithRetry(5)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(main())