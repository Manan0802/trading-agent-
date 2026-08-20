import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.advisor.rebalancer import check_rebalancing_needed
from app.services.alerts.whatsapp import send_whatsapp_message
from app.services.alerts.templates import WhatsAppTemplates

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

_log = logging.getLogger(__name__)

# `max_instances=1` is per PROCESS. One uvicorn today, but `--workers N` or a
# second instance means N concurrent nightly runs against one NAV store. The
# pipeline has its own in-flight guard, and this switch is the outer one: set it
# on exactly one instance in a multi-instance deployment.
SCREENER_JOB_ENABLED = os.environ.get("SCREENER_JOB_ENABLED", "1") not in ("0", "false", "")


def run_rebalancing_check(current: dict, target: dict, to_number: str) -> bool:
    result = check_rebalancing_needed(current, target)
    if result["needs_rebalancing"]:
        send_whatsapp_message(to_number, WhatsAppTemplates.rebalancing_alert(result["actions"]))
        return True
    return False


def nav_refresh_job() -> None:
    """Capture today's NAVs. Never raises -- a scheduler job that raises logs a
    traceback and vanishes."""
    from app.services.screener import amfi, navstore

    try:
        navstore.ensure_schema()
        report = amfi.refresh()
        _log.info(
            "AMFI refresh: %d rows inserted, newest %s, %d catalogue codes matched",
            report.inserted, report.newest_date, report.matched_catalogue_codes,
        )
        amfi.gap_fill()
    except Exception:  # noqa: BLE001 -- must not propagate into APScheduler
        _log.exception("AMFI refresh failed")


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
    if SCREENER_JOB_ENABLED:
        from app.services.screener.pipeline import nightly_job

        # Two jobs, not one, and the split is deliberate. AMFI's file only ever
        # carries each scheme's LATEST NAV, so a missed capture is recoverable
        # only through mfapi's one-day-lagged mirror -- whereas scoring can be
        # re-run at any time from NAVs already stored. A bug in the scorer must
        # not cost a day of NAV history.
        #
        # AMFI publishes around 23:00 IST and the scheduler is already on
        # Asia/Kolkata, so the capture sits after that and the scoring pass
        # after the capture.
        scheduler.add_job(
            nav_refresh_job,
            CronTrigger(hour=23, minute=45),
            id="nav_refresh",
            replace_existing=True,
            max_instances=1,
        )
        scheduler.add_job(
            nightly_job,
            CronTrigger(hour=0, minute=15),
            id="screener_score",
            replace_existing=True,
            max_instances=1,
        )
    else:
        _log.info("SCREENER_JOB_ENABLED is off; this instance will not run the nightly screener")

    if not scheduler.running:
        scheduler.start()
