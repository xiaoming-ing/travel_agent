#asyncio.Queue Producer / Consumer
import asyncio
import time

async def producer(queue):
    for i in range(10):
        await queue.put(i)
    await queue.put(None)  # 发送结束信号
    await queue.put(None)  # 发送结束信号
    return "生产者完成"

async def consumer(name,queue):
    while True:
        item = await queue.get()
        if item is None:
            break
        await asyncio.sleep(1)
        print(f"消费者{name}消费了: {item}")


async def main():
    queue = asyncio.Queue()
    await asyncio.gather(producer(queue), consumer("1", queue), consumer("2", queue))

if __name__ == "__main__":
    asyncio.run(main())