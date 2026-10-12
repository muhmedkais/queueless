from fastapi.testclient import TestClient
from app.main import app
from app import database

client = TestClient(app)

def test_full_queue_workflow():
    print("Testing 1: Public Business Queue Page...")
    res = client.get("/")
    assert res.status_code == 200
    assert "Nova Health" in res.text
    print("  -> Passed!")

    print("Testing 2: Join Queue Form Page...")
    res = client.get("/join")
    assert res.status_code == 200
    assert "Join Virtual Queue" in res.text
    print("  -> Passed!")

    print("Testing 3: Customer Joins Queue via API...")
    res = client.post("/api/join", data={
        "customer_name": "Test Customer Alice",
        "phone": "(555) 000-1111",
        "service_type": "Consultation / Checkup",
        "party_size": 1,
        "notes": "Testing note"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    ticket_id = data["ticket_id"]
    ticket_number = data["ticket_number"]
    print(f"  -> Successfully created ticket {ticket_number} (ID: {ticket_id})")

    print("Testing 4: Customer Live Ticket Tracking...")
    res = client.get(f"/ticket/{ticket_id}")
    assert res.status_code == 200
    assert ticket_number in res.text
    print("  -> Passed!")

    print("Testing 5: Customer Arrival Check-in...")
    res = client.post(f"/api/ticket/{ticket_id}/arrived")
    assert res.status_code == 200
    ticket_data = res.json()["ticket"]
    assert ticket_data["has_arrived"] == 1
    print("  -> Passed!")

    print("Testing 6: Staff Dashboard View...")
    res = client.get("/staff")
    assert res.status_code == 200
    assert "Live Queue Operations" in res.text
    print("  -> Passed!")

    print("Testing 7: Staff Adding Walk-In...")
    res = client.post("/api/staff/walk-in", data={
        "customer_name": "Walk-in Bob",
        "phone": "(555) 999-8888",
        "service_type": "Walk-in Consultation",
        "party_size": 1,
        "notes": "Front counter"
    })
    assert res.status_code == 200
    print("  -> Passed!")

    print("Testing 8: Staff Calling Next Customer...")
    res = client.post("/api/staff/call-next")
    assert res.status_code == 200
    print(f"  -> Called next: {res.json()}")

    print("Testing 9: Staff Updating Wait Estimate Settings...")
    res = client.post("/api/staff/settings", data={
        "name": "Nova Health & Wellness Clinic",
        "status": "open",
        "avg_service_mins": 12,
        "notify_threshold": 2,
        "location_address": "120 Market Street, Suite 4B",
        "phone": "(555) 234-5678",
        "banner_message": "Skip the waiting room! Check in remotely."
    })
    assert res.status_code == 200
    settings = database.get_settings()
    assert settings["avg_service_mins"] == 12
    print("  -> Settings updated successfully!")

    print("Testing 10: Analytics & Success Measures Page...")
    res = client.get("/analytics")
    assert res.status_code == 200
    assert "Queue Adoption & Arrival Tracking" in res.text
    print("  -> Passed!")

    print("\nALL 10 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_full_queue_workflow()
