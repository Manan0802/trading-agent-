"""Rupees, written the way they are written in India.

Python's `,` format spec groups in thousands the whole way up, so a lakh comes
out as 245,700. In India that is a typo: the grouping goes in twos after the
first thousand, and the eye reads the commas to find the lakh and the crore.
₹1,54,083 and ₹154,083 are the same number and only one of them is legible to
the person the advice is for.

The frontend already did this. The backend writes rupee figures into sentences
it sends down as text — a tax saving, a monthly shortfall, a commission over
fifteen years — and those went out ungrouped, sitting next to correctly grouped
figures on the same card.
"""


def inr(amount: float) -> str:
    """`245700` -> `₹2,45,700`. Negative amounts keep the sign outside the symbol."""
    whole = f"{abs(amount):,.0f}".replace(",", "")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{'-' if amount < 0 else ''}₹{whole}"
