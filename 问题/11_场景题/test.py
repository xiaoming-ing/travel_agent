import asyncio
async def fetchApi(sem,retryCount):
    for i in range(retryCount):
        try:
            return await asyncio.wait_for()
        except asyncio.TimeoutError:
            print(f"请求超时，重试第{i+1}次")

async def main(retryCount):
    sem = asyncio.Semaphore(5)
    tasks = [fetchApi(sem,retryCount) for _ in range(10)]
    results = await asyncio.gather(*tasks)


if __name__ == "__main__":
    retryCount = 3
    try:
        asyncio.run(main(retryCount))
    except Exception as e:
        print(e)