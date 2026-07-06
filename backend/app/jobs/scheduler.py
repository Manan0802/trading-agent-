from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.advisor.rebalancer import check_rebalancing_needed
from app.services.alerts.whatsapp import send_whatsapp_message
from app.services.alerts.templates import WhatsAppTemplates

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def run_rebalancing_check(current: dict, target: dict, to_number: str) -> bool:
    result = check_rebalancing_needed(current, target)
    if result["needs_rebalancing"]:
        send_whatsapp_message(to_number, WhatsAppTemplates.rebalancing_alert(result["actions"]))
        return True
    return False


def start_scheduler():
    # Phase 1: stub job; real per-user logic (+ duplicate-run guard once real
    # money orders exist in Phase 3+) wired in when holdings tracking exists.
    scheduler.add_job(
        lambda: None,
        CronTrigger(day_of_week="sun", hour=10, minute=0),
        id="weekly_rebalance",
        replace_existing=True,
        max_instances=1,
    )
    if not scheduler.running:
        scheduler.start()
