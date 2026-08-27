# async timeout
import asyncio
async def fetchApi():
    # 模拟一个异步请求
    await asyncio.sleep(2)  # 模拟网络延迟
    return "API response"

async def main():
    try:
        await asyncio.wait_for(fetchApi(),timeout=1)
    except asyncio.TimeoutError:
        print("请求超时")

if __name__ == "__main__":
    asyncio.run(main())