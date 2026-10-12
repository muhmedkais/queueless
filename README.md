# WaitLess — Smart Remote Queue MVP

A lightweight, real-time queue management system designed for **small clinics, salons, and repair shops**. It helps customers avoid waiting in crowded physical waiting rooms by letting them join and track their place in line directly from their phone, with automatic SMS turn notifications.

---

## 🌟 Core Features

1. **Business Queue Page (`/`)**
   - Live estimated wait time (e.g., `~20 mins`) and number of people ahead.
   - Now serving ticket badge.
   - Clean scannable **QR Code** & one-click **Copy Join Link** for storefront posters, counters, or social sharing.
   - Real-time updates via WebSockets without page refreshes.

2. **Join Queue (`/join`)**
   - Customer enters their name, phone number, service requested, party size, and optional notes.
   - Immediately receives a unique ticket number (e.g., `A-102`).
   - Automatically flagged as **Remote Join** for analytics tracking.
   - Saves ticket in `localStorage` so customers never lose their spot if they navigate away.

3. **Live Customer Ticket Tracker (`/ticket/{id}`)**
   - Dynamic real-time position: *"You are #2 in line"*, with auto-updating wait estimate.
   - **"I Have Arrived" Check-in Button**: Lets customers notify staff the moment they arrive on-site.
   - **Visual & Audio Turn Alerts**: High-contrast flashing banner and audio chime synthesizer (Web Audio API) when their turn is called.
   - SMS notification history log showing dispatched alerts.
   - Voluntary "Cancel / Leave Line" option.

4. **Staff Queue Manager (`/staff`)**
   - **Call Next Customer**: One-click advance that triggers the `CALLED` turn notification.
   - **Currently Serving Card**: Shows who is at the counter, elapsed time, service details, and options to *Mark Served*, *No-Show / Skip*, or *Resend SMS*.
   - **Add Walk-In Modal**: Quickly insert in-person walk-ins into the same queue (`is_remote=False`).
   - **Configurable Settings**:
     - Adjust average service time per customer (e.g., 10 mins &rarr; dynamically recalibrates wait times).
     - Set SMS alert threshold (e.g. notify when 1, 2, or 3 people ahead).
     - Queue state toggle (Open / Paused / Closed).
   - **SMS Activity Log**: Real-time feed of all outbound SMS alerts.

5. **Turn Notifications & SMS Dispatcher**
   - **Join Confirmation SMS**: Sent right after customer joins with a live tracking link.
   - **"Nearly Next" SMS Alert**: Automatically triggered when customer reaches the alert threshold (e.g. 1 person ahead) telling them to head over.
   - **"Turn Called" SMS Alert**: Triggered when staff clicks *Call Next*.
   - Out-of-the-box simulated local SMS delivery + built-in support for **Twilio API** or generic webhooks via environment variables.

6. **Success Measures & Analytics (`/analytics`)**
   - **Remote Join Adoption Rate**: Tracks % of customers joining via phone vs front desk walk-ins.
   - **On-Time Arrival Rate**: Tracks % of remote customers who marked *"I Have Arrived"* or showed up when alerted.
   - **No-Show Rate**: Compares successfully served customers against no-shows.
   - **Lobby Time Saved**: Cumulative in-person waiting hours saved by customers waiting elsewhere.

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.10+ (Tested on Python 3.14)
- [`uv`](https://docs.astral.sh/uv/) package manager (already installed)

### 2. Run the Application
Open a terminal in `C:\Users\KAIS\.gemini\antigravity\scratch\remote-queue` and execute:

```powershell
uv run python run.py
```

- **Local URL:** [http://localhost:8000](http://localhost:8000)
- **Live Public HTTPS Tunnel:** Available via Cloudflare Tunnel (`cloudflared.exe tunnel --url http://127.0.0.1:8000`)
- **Container / Cloud Deployment:** `Dockerfile` and `Procfile` included for 1-click deployment on Render, Railway, or Fly.io.

### 3. Seed Realistic Demo Data
To populate the database with a realistic active clinic queue:
```powershell
uv run python seed_demo_data.py
```

### 4. Run Test Suite
To run the automated end-to-end test suite:
```powershell
uv run python test_app.py
```

---

## ⚙️ Configuration & Twilio Setup (Optional)

By default, the application simulates SMS dispatch and logs every outgoing text message to the SQLite database and staff activity feed.

To send real SMS messages via **Twilio**, set the following environment variables:
```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_PHONE=+1XXXXXXXXXX
```

Or configure a webhook URL for an external SMS gateway:
```bash
SMS_WEBHOOK_URL=https://your-sms-webhook.com/api/send
```

---

## 📁 Project Architecture

```
remote-queue/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI endpoints, WebSockets, routes
│   ├── database.py        # SQLite schema, queries, metrics calculation
│   ├── notifier.py        # SMS service (Twilio / Webhook / Simulated)
│   └── templates/
│       ├── base.html      # Responsive Tailwind shell, Web Audio chime, WebSockets
│       ├── business.html  # Public queue view with QR code generator
│       ├── join.html      # Remote queue join form
│       ├── ticket.html    # Customer live ticket tracking + "I've arrived" button
│       ├── staff.html     # Staff operations dashboard
│       └── analytics.html # Success metric tracking
├── queue.db               # SQLite database file
├── run.py                 # Server startup script
├── seed_demo_data.py      # Demo queue seeder
├── test_app.py            # End-to-end test suite
└── pyproject.toml         # Dependencies
```
