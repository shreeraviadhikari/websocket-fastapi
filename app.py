import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

app = FastAPI()

from redis import asyncio as aioredis

redis = aioredis.from_url("redis://localhost", decode_responses=True)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@app.on_event("startup")
async def startup():
    asyncio.create_task(redis_listener())


async def redis_listener():
    pubsub = redis.pubsub()
    await pubsub.subscribe("chat_channel")
    async for message in pubsub.listen():
        if message["type"] == "message":
            await manager.broadcast(message["data"])


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await redis.publish("chat_channel", data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


from fastapi.responses import HTMLResponse


@app.get("/")
async def index():
    return HTMLResponse(Path("client.html").read_text())
