class WhatsAppTemplates:
    @staticmethod
    def rebalancing_alert(actions: list) -> str:
        lines = "\n".join(
            f"- {a['asset'].upper()}: {a['action']} {a['drift']:.1f}% (target {a['target_pct']}%)"
            for a in actions
        )
        return (
            "*Portfolio Rebalancing Alert*\n\n"
            "Your allocation has drifted from target:\n\n"
            f"{lines}\n\nConsider rebalancing this week.\n_NexTrade Financial Advisor_"
        )
