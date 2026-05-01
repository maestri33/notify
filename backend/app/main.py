from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from app.api import baileys, config, notifications, recipients, status
from app.baileys_ws import BaileysWS
from app.config import settings
from app.dashboard import routes as dashboard_routes

SKILL_PATH = Path(__file__).resolve().parents[2] / "SKILL.md"


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
app.include_router(recipients.check_router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")
app.include_router(baileys.router, prefix="/api/v1")


# Dashboard (server-rendered)
app.include_router(dashboard_routes.router)


@app.get("/api/v1/skill", response_class=PlainTextResponse)
def skill():
    """Return SKILL.md — instructions for AI agents integrating with Notify."""
    if SKILL_PATH.exists():
        return SKILL_PATH.read_text()
    return "# SKILL.md not found"


@app.get("/health")
def health():
    ws = getattr(app.state, "baileys_ws", None)
    return {
        "status": "ok",
        "env": settings.app_env,
        "ws_connected": ws is not None and ws._running,
    }
