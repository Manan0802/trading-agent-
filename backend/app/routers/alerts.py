from fastapi import APIRouter
from pydantic import BaseModel
from app.services.alerts.whatsapp import send_whatsapp_message

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


class TestAlert(BaseModel):
    to_number: str
    message: str = "NexTrade test alert ✅"


@router.post("/test")
def test_alert(body: TestAlert):
    sid = send_whatsapp_message(body.to_number, body.message)
    return {"sent": sid is not None, "sid": sid}
