import os
import urllib.request
import urllib.parse
import json
import logging
from typing import Dict, Any, Optional
from . import database

logger = logging.getLogger("queue_notifier")

class NotificationService:
    def __init__(self):
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_from = os.getenv("TWILIO_FROM_PHONE")
        self.webhook_url = os.getenv("SMS_WEBHOOK_URL")

    def send_sms(self, to_phone: str, message: str, ticket: Dict[str, Any], notification_type: str) -> Dict[str, Any]:
        """
        Sends SMS either via Twilio API, a generic SMS webhook, or simulated local delivery.
        Always records the dispatched notification into the database log for staff visibility.
        """
        success = True
        provider = "SIMULATED_LOCAL"

        # Check if Twilio credentials are configured
        if self.twilio_sid and self.twilio_token and self.twilio_from:
            try:
                provider = "TWILIO"
                url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
                data = urllib.parse.urlencode({
                    "To": to_phone,
                    "From": self.twilio_from,
                    "Body": message
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=data, method="POST")
                import base64
                auth_str = f"{self.twilio_sid}:{self.twilio_token}"
                b64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
                req.add_header("Authorization", f"Basic {b64_auth}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    logger.info(f"Twilio SMS sent successfully to {to_phone}")
            except Exception as e:
                logger.error(f"Twilio SMS error: {e}")
                provider = "TWILIO_FALLBACK_SIMULATED"
        elif self.webhook_url:
            try:
                provider = "WEBHOOK"
                req_data = json.dumps({"to": to_phone, "message": message, "ticket": ticket["ticket_number"]}).encode('utf-8')
                req = urllib.request.Request(self.webhook_url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:
                logger.error(f"Webhook SMS error: {e}")
                provider = "WEBHOOK_FALLBACK_SIMULATED"

        # Log notification in database
        database.log_notification(
            ticket_id=ticket["id"],
            ticket_number=ticket["ticket_number"],
            phone=to_phone,
            notification_type=notification_type,
            message=message
        )

        return {
            "success": success,
            "provider": provider,
            "to": to_phone,
            "type": notification_type,
            "message": message
        }

    def notify_joined(self, ticket: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        settings = database.get_settings()
        pos = database.get_customer_position(ticket["id"])
        people_ahead = pos.get("people_ahead", 0)
        est_wait = pos.get("estimated_wait_minutes", 0)
        track_url = f"{base_url}/ticket/{ticket['id']}"

        msg = (
            f"Hi {ticket['customer_name']}! You're in line at {settings['name']} (Ticket #{ticket['ticket_number']}). "
            f"People ahead: {people_ahead} (~{est_wait} min wait). "
            f"Track your turn live & tap 'I'm Here' when arriving: {track_url}"
        )
        return self.send_sms(ticket["phone"], msg, ticket, "JOIN_CONFIRMATION")

    def notify_nearly_next(self, ticket: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        settings = database.get_settings()
        track_url = f"{base_url}/ticket/{ticket['id']}"
        pos = database.get_customer_position(ticket["id"])
        ahead = pos.get("people_ahead", 1)

        msg = (
            f"⏳ Heads up {ticket['customer_name']}! You are nearly next in line at {settings['name']} "
            f"({ahead} person ahead). Please start heading over to the location now: {settings.get('location_address', '')}. "
            f"View live ticket: {track_url}"
        )
        res = self.send_sms(ticket["phone"], msg, ticket, "NEARLY_NEXT")
        database.mark_notification_sent(ticket["id"], "NEARLY_NEXT")
        return res

    def notify_called(self, ticket: Dict[str, Any], base_url: str) -> Dict[str, Any]:
        settings = database.get_settings()
        track_url = f"{base_url}/ticket/{ticket['id']}"

        msg = (
            f"🔔 It's your turn, {ticket['customer_name']}! Ticket #{ticket['ticket_number']} is being called right now at {settings['name']}. "
            f"Please come directly to the service desk. Live ticket: {track_url}"
        )
        res = self.send_sms(ticket["phone"], msg, ticket, "CALLED")
        database.mark_notification_sent(ticket["id"], "CALLED")
        return res

    def check_and_send_turn_alerts(self, base_url: str):
        """
        Scans waiting tickets. If a ticket is within the notify threshold and hasn't received
        a NEARLY_NEXT alert, sends it immediately.
        """
        settings = database.get_settings()
        threshold = settings.get("notify_threshold", 1)
        waiting = database.get_waiting_tickets()

        for t in waiting:
            pos = database.get_customer_position(t["id"])
            if pos.get("people_ahead", 999) <= threshold and t.get("nearly_next_notified") == 0:
                self.notify_nearly_next(t, base_url)

notifier = NotificationService()
