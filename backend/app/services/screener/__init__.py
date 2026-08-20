"""the reference implementation's fund analysis method, ported exactly.

This package is a deliberate, faithful port of the scoring pipeline in
the reference implementation -- how they source data, how they process it,
and the exact arithmetic they rank on. It is kept in its own package, apart
from `services/advisor/`, for one reason: **traa's own cost-weighted score and
this one must never be confused for each other.** They disagree, on purpose,
and the day they get blended is the day neither means anything.

What is deliberately NOT ported: `PREFERRED_AMCS`. Bachatt swaps the top pick
for one of six favoured fund houses whenever the leader is within 0.03 score of
one of them. That is distribution economics wearing a quality ranking's
clothes, and it does not belong in an analysis tool.
"""
