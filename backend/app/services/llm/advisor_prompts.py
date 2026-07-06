from app.services.llm.client import call_llm, _FA_SYSTEM_PROMPT


def get_goal_explanation(goal_data: dict, sip_result: dict, allocation: dict) -> str:
    msg = (
        f"Explain this financial goal plan in 3-4 warm Hinglish sentences.\n"
        f"Goal: {goal_data['goal_name']}\n"
        f"Target: Rs {goal_data['target_amount']:,.0f} in {goal_data['years']} years\n"
        f"Projected monthly SIP: Rs {sip_result['required_monthly_sip']:,.0f}\n"
        f"Allocation: {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold\n"
        f"Projected wealth created: Rs {sip_result['wealth_created']:,.0f}\n"
        f"Remember: say projected, never guaranteed."
    )
    out = call_llm(_FA_SYSTEM_PROMPT, msg)
    if out:
        return out
    return (
        f"Aapka goal '{goal_data['goal_name']}' ke liye projected monthly SIP "
        f"Rs {sip_result['required_monthly_sip']:,.0f} hai, {goal_data['years']} saal ke liye. "
        f"Paisa {allocation['equity']}% equity, {allocation['debt']}% debt, {allocation['gold']}% gold "
        f"mein lagega. Ye projected hai, guaranteed nahi — market ke hisaab se badal sakta hai. "
        f"Disciplined raho, har mahine invest karo. 📈"
    )
