from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.fastapi_users_app import current_active_user
from app.models import User
from app.services.alerts.whatsapp import send_whatsapp_message

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class TestAlert(BaseModel):
    message: str = "NexTrade test alert ✅"


@router.post("/test")
def test_alert(
    body: TestAlert,
    user: User = Depends(current_active_user),
):
    """Send yourself a test message, to check WhatsApp delivery works.

    **The destination is the caller's own profile number and cannot be passed
    in.** This endpoint originally took `to_number` from the request body and
    required no login, which made it a free WhatsApp relay: with Twilio
    configured, any stranger could send any text to any number in the world on
    this account. Nothing failed, because the credentials were empty — the bug
    would have arrived with the first real deployment, as a bill.

    Authentication alone would not have been enough. A logged-in relay is still
    a relay, so the number comes from the profile, which the account owner is
    the only person who can set.
    """
    if not user.phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Add a phone number to your profile first — a test alert is only "
            "ever sent to your own number, never to one supplied in the request.",
        )
    sid = send_whatsapp_message(user.phone, body.message)
    return {"sent": sid is not None, "sid": sid}
