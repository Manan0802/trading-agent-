from loguru import logger
from app.config import get_settings


def send_whatsapp_message(to_number: str, message: str) -> str | None:
    s = get_settings()
    if not (s.twilio_account_sid and s.twilio_auth_token):
        logger.warning("Twilio creds missing; skipping WhatsApp send")
        return None
    from twilio.rest import Client

    client = Client(s.twilio_account_sid, s.twilio_auth_token)
    msg = client.messages.create(
        from_=s.twilio_whatsapp_number, body=message, to=f"whatsapp:{to_number}"
    )
    return msg.sid
