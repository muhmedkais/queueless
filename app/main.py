from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional, List
import datetime
import asyncio

from . import database
from .notifier import notifier

app = FastAPI(title="WaitLess - Smart Remote Queue")

# Setup Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize Database on Startup
@app.on_event("startup")
def on_startup():
    database.init_db()

# WebSocket Manager for Real-Time Queue Updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            if dead in self.active_connections:
                self.active_connections.remove(dead)

manager = ConnectionManager()

def get_full_base_url(request: Request) -> str:
    return str(request.base_url).rstrip('/')

# ==========================================================
# PUBLIC BUSINESS QUEUE PAGE
# ==========================================================
@app.get("/", response_class=HTMLResponse)
async def view_business_queue(request: Request):
    settings = database.get_settings()
    metrics = database.get_queue_metrics()
    active_queue = database.get_active_queue()
    currently_serving = database.get_currently_serving()
    
    return templates.TemplateResponse(request, "business.html", {
        "settings": settings,
        "metrics": metrics,
        "active_queue": active_queue,
        "currently_serving": currently_serving,
        "base_url": get_full_base_url(request)
    })

# ==========================================================
# JOIN QUEUE PAGE & API
# ==========================================================
@app.get("/join", response_class=HTMLResponse)
async def view_join_form(request: Request):
    settings = database.get_settings()
    metrics = database.get_queue_metrics()
    return templates.TemplateResponse(request, "join.html", {
        "settings": settings,
        "metrics": metrics,
        "base_url": get_full_base_url(request)
    })

@app.post("/api/join")
async def handle_join_queue(
    request: Request,
    customer_name: str = Form(...),
    phone: str = Form(...),
    service_type: str = Form("General Consultation"),
    party_size: int = Form(1),
    notes: str = Form("")
):
    settings = database.get_settings()
    if settings.get("status") == "closed":
        return JSONResponse(status_code=400, content={"error": "The queue is currently closed."})

    ticket = database.create_ticket(
        customer_name=customer_name.strip(),
        phone=phone.strip(),
        service_type=service_type.strip(),
        party_size=party_size,
        notes=notes.strip(),
        is_remote=True
    )

    base_url = get_full_base_url(request)
    # Send confirmation SMS
    notifier.notify_joined(ticket, base_url)

    # Check if they are nearly next immediately (e.g. 1st or 2nd in line)
    notifier.check_and_send_turn_alerts(base_url)

    # Notify all connected clients (staff & customer boards)
    await manager.broadcast({
        "event": "queue_updated",
        "action": "customer_joined",
        "ticket_number": ticket["ticket_number"]
    })

    return {
        "success": True,
        "ticket_id": ticket["id"],
        "ticket_number": ticket["ticket_number"],
        "redirect_url": f"/ticket/{ticket['id']}"
    }

# ==========================================================
# CUSTOMER TICKET TRACKING PAGE & ACTIONS
# ==========================================================
@app.get("/ticket/{ticket_id}", response_class=HTMLResponse)
async def view_ticket_tracking(request: Request, ticket_id: int):
    ticket = database.get_ticket_by_id(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    settings = database.get_settings()
    position = database.get_customer_position(ticket_id)
    currently_serving = database.get_currently_serving()

    return templates.TemplateResponse(request, "ticket.html", {
        "ticket": ticket,
        "settings": settings,
        "position": position,
        "currently_serving": currently_serving,
        "base_url": get_full_base_url(request)
    })

@app.get("/api/ticket/{ticket_id}")
async def get_ticket_status_api(ticket_id: int):
    pos = database.get_customer_position(ticket_id)
    if not pos.get("found"):
        return JSONResponse(status_code=404, content={"error": "Ticket not found"})
    return pos

@app.post("/api/ticket/{ticket_id}/arrived")
async def mark_customer_arrived(request: Request, ticket_id: int):
    ticket = database.mark_ticket_arrived(ticket_id)
    if not ticket:
        return JSONResponse(status_code=404, content={"error": "Ticket not found"})

    await manager.broadcast({
        "event": "queue_updated",
        "action": "customer_arrived",
        "ticket_id": ticket_id,
        "ticket_number": ticket["ticket_number"]
    })
    return {"success": True, "ticket": ticket}

@app.post("/api/ticket/{ticket_id}/cancel")
async def cancel_customer_ticket(request: Request, ticket_id: int):
    ticket = database.cancel_ticket(ticket_id, reason="CANCELLED")
    base_url = get_full_base_url(request)
    notifier.check_and_send_turn_alerts(base_url)

    await manager.broadcast({
        "event": "queue_updated",
        "action": "ticket_cancelled",
        "ticket_id": ticket_id
    })
    return {"success": True, "ticket": ticket}

# ==========================================================
# STAFF QUEUE MANAGER
# ==========================================================
@app.get("/staff", response_class=HTMLResponse)
async def view_staff_manager(request: Request):
    settings = database.get_settings()
    metrics = database.get_queue_metrics()
    active_queue = database.get_active_queue()
    currently_serving = database.get_currently_serving()
    recent_sms = database.get_recent_notifications(15)

    return templates.TemplateResponse(request, "staff.html", {
        "settings": settings,
        "metrics": metrics,
        "active_queue": active_queue,
        "currently_serving": currently_serving,
        "recent_sms": recent_sms,
        "base_url": get_full_base_url(request)
    })

@app.post("/api/staff/call-next")
async def staff_call_next(request: Request):
    base_url = get_full_base_url(request)
    called_ticket = database.call_next_ticket()
    if called_ticket:
        # Send CALLED alert
        notifier.notify_called(called_ticket, base_url)
        # Scan and notify the next person in line that they are nearly up!
        notifier.check_and_send_turn_alerts(base_url)

        await manager.broadcast({
            "event": "queue_updated",
            "action": "next_called",
            "ticket_number": called_ticket["ticket_number"]
        })
        return {"success": True, "ticket": called_ticket}
    return {"success": False, "message": "No waiting customers in queue"}

@app.post("/api/staff/call/{ticket_id}")
async def staff_call_specific(request: Request, ticket_id: int):
    base_url = get_full_base_url(request)
    called_ticket = database.call_specific_ticket(ticket_id)
    if called_ticket:
        notifier.notify_called(called_ticket, base_url)
        notifier.check_and_send_turn_alerts(base_url)
        await manager.broadcast({
            "event": "queue_updated",
            "action": "ticket_called",
            "ticket_number": called_ticket["ticket_number"]
        })
        return {"success": True, "ticket": called_ticket}
    return {"success": False, "message": "Ticket not found"}

@app.post("/api/staff/complete/{ticket_id}")
async def staff_complete_ticket(request: Request, ticket_id: int):
    base_url = get_full_base_url(request)
    ticket = database.complete_ticket(ticket_id)
    notifier.check_and_send_turn_alerts(base_url)

    await manager.broadcast({
        "event": "queue_updated",
        "action": "ticket_completed",
        "ticket_id": ticket_id
    })
    return {"success": True, "ticket": ticket}

@app.post("/api/staff/mark-no-show/{ticket_id}")
async def staff_mark_no_show(request: Request, ticket_id: int):
    base_url = get_full_base_url(request)
    ticket = database.cancel_ticket(ticket_id, reason="NO_SHOW")
    notifier.check_and_send_turn_alerts(base_url)

    await manager.broadcast({
        "event": "queue_updated",
        "action": "ticket_no_show",
        "ticket_id": ticket_id
    })
    return {"success": True, "ticket": ticket}

@app.post("/api/staff/walk-in")
async def staff_add_walkin(
    request: Request,
    customer_name: str = Form(...),
    phone: str = Form(""),
    service_type: str = Form("Walk-in Service"),
    party_size: int = Form(1),
    notes: str = Form("")
):
    ticket = database.create_ticket(
        customer_name=customer_name.strip(),
        phone=phone.strip() if phone else "In-Person Walk-in",
        service_type=service_type.strip(),
        party_size=party_size,
        notes=notes.strip(),
        is_remote=False  # Physical walk-in added by staff
    )

    base_url = get_full_base_url(request)
    if phone and phone != "In-Person Walk-in":
        notifier.notify_joined(ticket, base_url)

    notifier.check_and_send_turn_alerts(base_url)

    await manager.broadcast({
        "event": "queue_updated",
        "action": "walkin_added",
        "ticket_number": ticket["ticket_number"]
    })
    return {"success": True, "ticket": ticket}

@app.post("/api/staff/settings")
async def update_settings_endpoint(
    request: Request,
    name: str = Form(...),
    status: str = Form(...),
    avg_service_mins: int = Form(...),
    notify_threshold: int = Form(1),
    location_address: str = Form(""),
    phone: str = Form(""),
    banner_message: str = Form("")
):
    database.update_settings(
        name=name.strip(),
        status=status.strip(),
        avg_service_mins=avg_service_mins,
        notify_threshold=notify_threshold,
        location_address=location_address.strip(),
        phone=phone.strip(),
        banner_message=banner_message.strip()
    )

    await manager.broadcast({
        "event": "queue_updated",
        "action": "settings_updated"
    })
    return {"success": True}

@app.post("/api/staff/resend-sms/{ticket_id}")
async def staff_resend_sms(request: Request, ticket_id: int):
    base_url = get_full_base_url(request)
    ticket = database.get_ticket_by_id(ticket_id)
    if not ticket:
        return JSONResponse(status_code=404, content={"error": "Ticket not found"})

    if ticket["status"] == "CALLED":
        res = notifier.notify_called(ticket, base_url)
    else:
        res = notifier.notify_nearly_next(ticket, base_url)

    await manager.broadcast({
        "event": "sms_dispatched",
        "ticket_number": ticket["ticket_number"]
    })
    return {"success": True, "result": res}

@app.get("/api/staff/notifications")
async def get_staff_notifications():
    notifications = database.get_recent_notifications(30)
    return {"notifications": notifications}

# ==========================================================
# ANALYTICS & SUCCESS MEASURES
# ==========================================================
@app.get("/analytics", response_class=HTMLResponse)
async def view_analytics(request: Request):
    settings = database.get_settings()
    metrics = database.get_queue_metrics()
    return templates.TemplateResponse(request, "analytics.html", {
        "settings": settings,
        "metrics": metrics,
        "base_url": get_full_base_url(request)
    })

# ==========================================================
# WEBSOCKET REALTIME SYNC
# ==========================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open; receive ping or client queries
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
