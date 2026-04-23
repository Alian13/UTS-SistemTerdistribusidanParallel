import asyncio

event_queue = asyncio.Queue(maxsize=10000)

async def get_queue():
    return event_queue

async def put_event(event):
    await event_queue.put(event)

async def get_event():
    return await event_queue.get()

def queue_size():
    return event_queue.qsize()
