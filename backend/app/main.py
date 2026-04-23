from fastapi import FastAPI

from app.api import config, notifications, recipients, status
from app.config import settings
from app.dashboard import routes as dashboard_routes

app = FastAPI(title="Notify", version="0.1.0")

# JSON API
app.include_router(recipients.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(config.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")

# Dashboard (server-rendered)
app.include_router(dashboard_routes.router)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.app_env}
