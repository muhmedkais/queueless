import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).parent.parent / "queue.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Business Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS business_settings (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        avg_service_mins INTEGER NOT NULL DEFAULT 10,
        notify_threshold INTEGER NOT NULL DEFAULT 1,
        location_address TEXT DEFAULT '120 Market Street, Suite 4B',
        phone TEXT DEFAULT '(555) 234-5678',
        banner_message TEXT DEFAULT 'Relax nearby! Join from your phone and we will text you when it is your turn.'
    )
    """)

    # Tickets Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT NOT NULL UNIQUE,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        service_type TEXT NOT NULL DEFAULT 'General Service',
        party_size INTEGER NOT NULL DEFAULT 1,
        notes TEXT DEFAULT '',
        is_remote INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'WAITING',
        has_arrived INTEGER NOT NULL DEFAULT 0,
        arrived_at TEXT,
        nearly_next_notified INTEGER NOT NULL DEFAULT 0,
        called_notified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        called_at TEXT,
        served_at TEXT
    )
    """)

    # Notification History Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL,
        ticket_number TEXT NOT NULL,
        phone TEXT NOT NULL,
        notification_type TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'DELIVERED',
        created_at TEXT NOT NULL,
        FOREIGN KEY (ticket_id) REFERENCES tickets (id)
    )
    """)

    # Default business settings seed if empty
    cursor.execute("SELECT COUNT(*) as cnt FROM business_settings")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("""
        INSERT INTO business_settings (id, name, slug, status, avg_service_mins, notify_threshold, location_address, phone, banner_message)
        VALUES (1, 'Nova Health & Wellness Clinic', 'nova-clinic', 'open', 10, 1, '120 Market Street, Suite 4B', '(555) 234-5678', 'Skip the waiting room! Check in remotely and head over when your turn is close.')
        """)

    conn.commit()
    conn.close()

def get_settings() -> Dict[str, Any]:
    conn = get_db()
    row = conn.execute("SELECT * FROM business_settings WHERE id = 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "id": 1,
        "name": "Nova Health & Wellness Clinic",
        "slug": "nova-clinic",
        "status": "open",
        "avg_service_mins": 10,
        "notify_threshold": 1,
        "location_address": "120 Market Street, Suite 4B",
        "phone": "(555) 234-5678",
        "banner_message": "Skip the waiting room! Check in remotely and head over when your turn is close."
    }

def update_settings(name: str, status: str, avg_service_mins: int, notify_threshold: int, location_address: str, phone: str, banner_message: str):
    conn = get_db()
    conn.execute("""
    UPDATE business_settings
    SET name = ?, status = ?, avg_service_mins = ?, notify_threshold = ?, location_address = ?, phone = ?, banner_message = ?
    WHERE id = 1
    """, (name, status, avg_service_mins, notify_threshold, location_address, phone, banner_message))
    conn.commit()
    conn.close()

def generate_ticket_number() -> str:
    conn = get_db()
    today = datetime.date.today().strftime("%Y-%m-%d")
    row = conn.execute("SELECT COUNT(*) as count FROM tickets WHERE created_at LIKE ?", (f"{today}%",)).fetchone()
    conn.close()
    count = row["count"] + 1
    return f"A-{count:03d}"

def create_ticket(customer_name: str, phone: str, service_type: str = "General Service",
                  party_size: int = 1, notes: str = "", is_remote: bool = True) -> Dict[str, Any]:
    conn = get_db()
    ticket_num = generate_ticket_number()
    now_str = datetime.datetime.now().isoformat()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tickets (ticket_number, customer_name, phone, service_type, party_size, notes, is_remote, status, has_arrived, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'WAITING', ?, ?)
    """, (ticket_num, customer_name, phone, service_type, party_size, notes, 1 if is_remote else 0, 0 if is_remote else 1, now_str))
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def get_ticket_by_id(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_ticket_by_number(ticket_number: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("SELECT * FROM tickets WHERE ticket_number = ?", (ticket_number.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_active_queue() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
    SELECT * FROM tickets 
    WHERE status IN ('WAITING', 'CALLED')
    ORDER BY CASE status WHEN 'CALLED' THEN 0 ELSE 1 END, id ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_waiting_tickets() -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
    SELECT * FROM tickets 
    WHERE status = 'WAITING'
    ORDER BY id ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_currently_serving() -> Optional[Dict[str, Any]]:
    conn = get_db()
    row = conn.execute("""
    SELECT * FROM tickets 
    WHERE status = 'CALLED'
    ORDER BY called_at DESC LIMIT 1
    """).fetchone()
    conn.close()
    return dict(row) if row else None

def mark_ticket_arrived(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    now_str = datetime.datetime.now().isoformat()
    conn.execute("""
    UPDATE tickets 
    SET has_arrived = 1, arrived_at = ?
    WHERE id = ?
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def call_next_ticket() -> Optional[Dict[str, Any]]:
    conn = get_db()
    # Find first waiting ticket
    row = conn.execute("""
    SELECT * FROM tickets 
    WHERE status = 'WAITING' 
    ORDER BY id ASC LIMIT 1
    """).fetchone()
    
    if not row:
        conn.close()
        return None

    now_str = datetime.datetime.now().isoformat()
    ticket_id = row["id"]
    conn.execute("""
    UPDATE tickets 
    SET status = 'CALLED', called_at = ?
    WHERE id = ?
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def call_specific_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    now_str = datetime.datetime.now().isoformat()
    conn.execute("""
    UPDATE tickets 
    SET status = 'CALLED', called_at = ?
    WHERE id = ?
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def complete_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    now_str = datetime.datetime.now().isoformat()
    conn.execute("""
    UPDATE tickets 
    SET status = 'SERVED', served_at = ?
    WHERE id = ?
    """, (now_str, ticket_id))
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def cancel_ticket(ticket_id: int, reason: str = "CANCELLED") -> Optional[Dict[str, Any]]:
    conn = get_db()
    conn.execute("""
    UPDATE tickets 
    SET status = ?
    WHERE id = ?
    """, (reason, ticket_id))
    conn.commit()
    conn.close()
    return get_ticket_by_id(ticket_id)

def log_notification(ticket_id: int, ticket_number: str, phone: str, notification_type: str, message: str):
    conn = get_db()
    now_str = datetime.datetime.now().isoformat()
    conn.execute("""
    INSERT INTO notifications (ticket_id, ticket_number, phone, notification_type, message, status, created_at)
    VALUES (?, ?, ?, ?, ?, 'DELIVERED', ?)
    """, (ticket_id, ticket_number, phone, notification_type, message, now_str))
    conn.commit()
    conn.close()

def mark_notification_sent(ticket_id: int, notify_type: str):
    conn = get_db()
    if notify_type == "NEARLY_NEXT":
        conn.execute("UPDATE tickets SET nearly_next_notified = 1 WHERE id = ?", (ticket_id,))
    elif notify_type == "CALLED":
        conn.execute("UPDATE tickets SET called_notified = 1 WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()

def get_recent_notifications(limit: int = 25) -> List[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute("""
    SELECT * FROM notifications 
    ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_queue_metrics() -> Dict[str, Any]:
    conn = get_db()
    settings = get_settings()
    avg_service = settings["avg_service_mins"]

    # Current queue state
    waiting_count = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = 'WAITING'").fetchone()["cnt"]
    called_count = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = 'CALLED'").fetchone()["cnt"]
    total_active = waiting_count + called_count
    estimated_wait_total = waiting_count * avg_service

    # Historical stats
    total_today = conn.execute("SELECT COUNT(*) as cnt FROM tickets").fetchone()["cnt"]
    served_today = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = 'SERVED'").fetchone()["cnt"]
    no_shows_today = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = 'NO_SHOW'").fetchone()["cnt"]
    
    # Remote vs Walk-in breakdown
    remote_total = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE is_remote = 1").fetchone()["cnt"]
    walkin_total = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE is_remote = 0").fetchone()["cnt"]
    
    # Arrival tracking: remote users who marked arrived
    remote_arrived = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE is_remote = 1 AND has_arrived = 1").fetchone()["cnt"]
    remote_arrival_rate = round((remote_arrived / remote_total * 100), 1) if remote_total > 0 else 0.0
    remote_percentage = round((remote_total / total_today * 100), 1) if total_today > 0 else 0.0

    conn.close()

    return {
        "waiting_count": waiting_count,
        "called_count": called_count,
        "total_active": total_active,
        "avg_service_mins": avg_service,
        "estimated_wait_minutes": estimated_wait_total,
        "total_today": total_today,
        "served_today": served_today,
        "no_shows_today": no_shows_today,
        "remote_total": remote_total,
        "walkin_total": walkin_total,
        "remote_arrived": remote_arrived,
        "remote_arrival_rate": remote_arrival_rate,
        "remote_percentage": remote_percentage,
    }

def get_customer_position(ticket_id: int) -> Dict[str, Any]:
    """Calculates people ahead and wait estimate for a specific ticket."""
    ticket = get_ticket_by_id(ticket_id)
    if not ticket:
        return {"found": False}
    
    settings = get_settings()
    avg_service = settings["avg_service_mins"]
    
    if ticket["status"] == "CALLED":
        return {
            "found": True,
            "ticket": ticket,
            "status": "CALLED",
            "people_ahead": 0,
            "estimated_wait_minutes": 0,
            "message": "It's your turn! Please step up to the desk / enter."
        }
    elif ticket["status"] in ("SERVED", "NO_SHOW", "CANCELLED"):
        return {
            "found": True,
            "ticket": ticket,
            "status": ticket["status"],
            "people_ahead": 0,
            "estimated_wait_minutes": 0,
            "message": f"Your ticket is {ticket['status'].lower()}."
        }
    
    # WAITING status: count tickets with status 'WAITING' and id < this ticket's id
    conn = get_db()
    # Also check if someone is currently called
    currently_serving = conn.execute("SELECT COUNT(*) as cnt FROM tickets WHERE status = 'CALLED'").fetchone()["cnt"]
    
    row = conn.execute("""
    SELECT COUNT(*) as cnt FROM tickets 
    WHERE status = 'WAITING' AND id < ?
    """, (ticket_id,)).fetchone()
    conn.close()

    people_ahead = row["cnt"] + currently_serving
    estimated_wait = max(0, people_ahead * avg_service)

    return {
        "found": True,
        "ticket": ticket,
        "status": "WAITING",
        "people_ahead": people_ahead,
        "estimated_wait_minutes": estimated_wait,
        "is_nearly_next": people_ahead <= settings.get("notify_threshold", 1)
    }
