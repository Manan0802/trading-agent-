from app.services.alerts.templates import WhatsAppTemplates
from app.services.alerts.whatsapp import send_whatsapp_message


def test_rebalancing_template():
    msg = WhatsAppTemplates.rebalancing_alert(
        [{"asset": "equity", "action": "SELL", "drift": 10.0, "target_pct": 75}]
    )
    assert "EQUITY" in msg and "SELL" in msg


def test_send_without_creds_returns_none():
    assert send_whatsapp_message("+910000000000", "hi") is None
