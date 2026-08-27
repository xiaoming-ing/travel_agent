# asyncio 并发调用100个API，最大并发调用5

# 协程：是一个特殊的函数，可以在执行过程中暂停和恢复。使用async def 关键字定义，通过await关键字暂停执行（await把当前协程注册到事件循环的等待名单上，交出CPU）
# 事件循环：负责调度和执行协程，不断检查是否有任务需要执行，并在任务完成后调用相应的回调函数。
# 任务：是对协程的封装，表示一个正在执行或事将要执行的协程。可以通过asyncio.create_task()创建任务，并将其添加到事件循环中。
# Future: 表示异步操作结果的对象。表示尚未完成的操作。
import asyncio
import random
async def fetch_api(sem):
    async with sem:
        await asyncio.sleep(random.uniform(0.5,1.5))
        return "API call completed"

async def main():
    sem = asyncio.Semaphore(5)
    tasks = [fetch_api(sem) for _ in range(100)]
    results = await asyncio.gather(*tasks)