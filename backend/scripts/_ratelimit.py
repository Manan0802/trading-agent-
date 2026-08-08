"""An HTTP client that waits out this app's own rate limiter.

Every harness in `./check.sh` runs from one machine, and anonymous calls are
counted per IP — so by the third harness the minute's budget is often already
spent by the first two, and endpoints start answering 429. The heavy tier is
20 a minute, which `edge_cases.py` alone can clear.

**Two harnesses were quietly broken by this and neither said so.**

- `isolation.py` asserted `status in (401, 403)`. A 429 is neither, so it
  recorded a failure under the heading "LEAKED" — the most alarming words in
  the suite, for a request that was refused correctly and simply never tested
  the thing it meant to test.
- `consistency.py` did `plan["regime"]["saving"]` on the response. The
  limiter's body is `{"detail": ...}`, so it died with a `KeyError` mid-run.

Both were invisible for as long as they existed, because `check.sh` piped each
harness into `tail` and read `tail`'s exit code. The gate printed "All clear"
over a stack trace.

The limiter already answers the only question worth asking here — it sends
`Retry-After`. So wait exactly that long, then ask again, rather than guess a
sleep or weaken an assertion to make the red go away.
"""

from __future__ import annotations

import time

import httpx

# One extra second so a boundary-rounded Retry-After does not land us back in
# the same window we were told to wait out.
_GRACE_SECONDS = 1

# The limiter's longest window is a minute; anything past this is not the
# limiter and should surface as a 429 the caller has to deal with.
_MAX_WAIT_SECONDS = 90


class PatientClient(httpx.Client):
    """`httpx.Client`, except a 429 is waited out once instead of returned.

    Only once: a second 429 after an honest wait means something other than our
    own harness traffic is in play, and silently looping would turn a real
    problem into a hang.
    """

    def request(self, *args, **kwargs) -> httpx.Response:
        response = super().request(*args, **kwargs)
        if response.status_code != 429:
            return response

        try:
            wait = int(response.headers.get("Retry-After", 60)) + _GRACE_SECONDS
        except ValueError:
            wait = 60
        if wait > _MAX_WAIT_SECONDS:
            return response

        print(f"  rate limited, waiting {wait}s so this check actually runs")
        time.sleep(wait)
        return super().request(*args, **kwargs)
