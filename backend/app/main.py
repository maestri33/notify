from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import baileys, config, notifications, recipients, status
from app.baileys_ws import BaileysWS
from app.config import settings
from app.dashboard import routes as dashboard_routes


@asynccontextmanager
async def lifespan(ap: FastAPI):
    ws = BaileysWS(f"ws://localhost:3000/ws")
    await ws.connect()
    ap.state.baileys_ws = ws
    yield
    await ws.disconnect()


app = FastAPI(title="Notify", version="0.1.0", lifespan=lifespan)

# JSON API
app.include_router(recipients.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")
app.include_router(baileys.router, prefix="/api/v1")

# Dashboard (server-rendered)
app.include_router(dashboard_routes.router)


@app.get("/health")
def health():
    ws = getattr(app.state, "baileys_ws", None)
    return {
        "status": "ok",
        "env": settings.app_env,
        "ws_connected": ws is not None and ws._running,
    }
