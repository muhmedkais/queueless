import datetime
from app import database
from app.notifier import notifier

def seed_demo():
    database.init_db()
    conn = database.get_db()
    
    # Check if tickets already exist
    count = conn.execute("SELECT COUNT(*) as cnt FROM tickets").fetchone()["cnt"]
    if count > 0:
        print("Database already has records. Seeding skipped.")
        conn.close()
        return

    print("Seeding sample business queue data...")

    # Update business settings
    database.update_settings(
        name="Nova Health & Wellness Clinic",
        status="open",
        avg_service_mins=10,
        notify_threshold=1,
        location_address="120 Market Street, Suite 4B",
        phone="(555) 234-5678",
        banner_message="Skip the waiting room! Check in remotely and head over when your turn is close."
    )

    # 1. Customer currently being served (called 5 mins ago)
    t1 = database.create_ticket(
        customer_name="Marcus Vance",
        phone="(555) 301-4492",
        service_type="Doctor Consultation",
        party_size=1,
        notes="Returning patient, regular checkup",
        is_remote=True
    )
    database.mark_ticket_arrived(t1["id"])
    database.call_specific_ticket(t1["id"])
    notifier.notify_called(t1, "http://localhost:8000")

    # 2. Customer waiting - Next in line (nearly next notified!)
    t2 = database.create_ticket(
        customer_name="Elena Rostova",
        phone="(555) 892-1204",
        service_type="Prescription Renewal",
        party_size=1,
        notes="",
        is_remote=True
    )
    database.mark_ticket_arrived(t2["id"])
    notifier.notify_nearly_next(t2, "http://localhost:8000")

    # 3. Customer waiting - Remote joiner (still waiting off-site)
    t3 = database.create_ticket(
        customer_name="David Chen",
        phone="(555) 674-8839",
        service_type="Lab Test Review",
        party_size=2,
        notes="Waiting at cafe across the street",
        is_remote=True
    )
    notifier.notify_joined(t3, "http://localhost:8000")

    # 4. Customer waiting - In-person walk-in added at front desk
    t4 = database.create_ticket(
        customer_name="Sarah Jenkins",
        phone="(555) 412-9901",
        service_type="Flu Shot / Vaccination",
        party_size=1,
        notes="Sitting in front lobby",
        is_remote=False
    )

    # 5. Customer already served earlier today
    t5 = database.create_ticket(
        customer_name="Carlos Mendez",
        phone="(555) 902-3341",
        service_type="Blood Pressure Check",
        party_size=1,
        notes="",
        is_remote=True
    )
    database.mark_ticket_arrived(t5["id"])
    database.call_specific_ticket(t5["id"])
    database.complete_ticket(t5["id"])

    print("Successfully seeded demo queue with realistic sample data!")
    conn.close()

if __name__ == "__main__":
    seed_demo()
