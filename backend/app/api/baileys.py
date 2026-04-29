"""API endpoints that read directly from the shared Baileys SQLite database."""

from fastapi import APIRouter, Query

from app.baileys_db import (
    count_contacts,
    count_messages,
    get_contact,
    get_message,
    list_contacts,
    list_messages,
    recent_messages,
    search_contacts,
)

router = APIRouter(prefix="/baileys", tags=["baileys"])


@router.get("/contacts")
def api_list_contacts(
    q: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    if q:
        return {"contacts": search_contacts(q, limit, offset)}
    return {"contacts": list_contacts(limit, offset), "total": count_contacts()}


@router.get("/contacts/{jid}")
def api_get_contact(jid: str):
    c = get_contact(jid)
    if not c:
        return {"error": "not found"}, 404
    return c


@router.get("/messages")
def api_list_messages(
    jid: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    if jid:
        return {"messages": list_messages(jid, limit, offset)}
    return {"messages": recent_messages(limit), "total": count_messages()}


@router.get("/messages/{msg_id}")
def api_get_message(msg_id: str):
    m = get_message(msg_id)
    if not m:
        return {"error": "not found"}, 404
    return m


@router.get("/stats")
def api_stats():
    return {
        "contacts": count_contacts(),
        "messages": count_messages(),
    }
