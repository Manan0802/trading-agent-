"""How often each of this app's own claims has actually been right.

## Why this exists

Fifteen Indian investing apps were surveyed while designing the decision
screens. **Not one publishes an audited track record for its own engine.** ARQ
Prime, Mojo Score, Tickertape's Entry Point, ET Money Genius all make
forward-looking calls; none says how often it was right. Even Zerodha's Nudge —
the best-regarded safety feature in Indian fintech — has no Zerodha-published
effectiveness number.

Univest comes closest and is worth beating rather than copying: under its verdict
it prints *"Price moved −196.70 (21.23%) since then"*. That is one call marked to
market, with no denominator — you cannot tell whether it is typical or the worst
one they have.

This file is the denominator.

## Why it is recomputed rather than transcribed

The numbers move. The memory notes recorded cost at 34/44 windows with rank IC
+0.184; recomputed today on a NAV store that has since grown, it is 35/44 and
+0.195. Hand-copied numbers in a codebase rot silently, and this app's whole
argument rests on them being true.

## The wobble, and why every figure here is a range

`why_not_returns.py` and its siblings fetch from mfapi at 24 threads. Which
fetches succeed varies run to run, so the sample varies with it. Five
consecutive runs of the identical script gave **37, 35, 36, 35 and 35** windows
out of 44, with rank IC from +0.192 to +0.201.

That is not noise to hide. Each measurement is therefore run `RUNS` times and
recorded as median plus observed range, and the screen quotes the range.

    python scripts/build_track_record.py

Output: app/data/track_record.json
"""

import json
import re
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "data" / "track_record.json"

# Enough to see the spread without turning a build into a coffee break. Each
# script is seconds, not minutes.
RUNS = 3

PYTHON = str(ROOT / "venv" / "bin" / "python")


def run(script: str) -> str:
    result = subprocess.run(
        [PYTHON, str(ROOT / "scripts" / script)],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"{script} exited {result.returncode}\n{result.stderr[-2000:]}")
    return result.stdout


def grab(pattern: str, text: str, script: str) -> tuple[float, ...]:
    """Pull numbers out of a validator's own output, or fail the build.

    Strict on purpose. A validator that changes its wording should break this
    loudly rather than let a stale number survive into the app — the numbers
    here are the evidence for every claim the product makes about itself.
    """
    found = re.search(pattern, text, re.MULTILINE)
    if not found:
        raise RuntimeError(
            f"could not read the result out of {script}.\n"
            f"pattern: {pattern}\n--- its output was ---\n{text[-1500:]}"
        )
    return tuple(float(g) for g in found.groups())


def spread(draws: list[tuple[float, ...]], labels: tuple[str, ...]) -> dict:
    out: dict[str, dict] = {}
    for i, label in enumerate(labels):
        values = [d[i] for d in draws]
        out[label] = {
            "median": round(statistics.median(values), 4),
            "low": round(min(values), 4),
            "high": round(max(values), 4),
        }
    return out


def runs_of(script: str) -> list[str]:
    """One validator, run `RUNS` times. Every signal it reports is parsed out of
    the SAME outputs — running the script once per signal would be four times
    the work and would compare signals measured on different samples."""
    print(f"  {script} ×{RUNS} ...", end="", flush=True)
    outputs = [run(script) for _ in range(RUNS)]
    print(" done", flush=True)
    return outputs


def measure(outputs: list[str], script: str, pattern: str, labels: tuple[str, ...]) -> dict:
    return spread([grab(pattern, text, script) for text in outputs], labels)


def _window_counts(*blocks: dict) -> str:
    """Every distinct `windows` value this run observed, low to high.

    Written so `why_ranges` reports the run it belongs to. The figure it
    replaced said "37, 35, 36, 35 and 35 out of 44" for five runs while `RUNS`
    was 3, and was reprinted unchanged every time this script ran.
    """
    seen: set[int] = set()
    for block in blocks:
        for value in block.values():
            windows = value.get("windows") if isinstance(value, dict) else None
            if isinstance(windows, dict):
                seen.update(int(windows[k]) for k in ("low", "median", "high") if k in windows)
            elif isinstance(value, dict) and "windows" in value:
                seen.add(int(value["windows"]))
    return ", ".join(str(n) for n in sorted(seen)) or "none recorded"


def build() -> dict:
    print("measuring this app's own claims...", flush=True)

    # 1. The head-to-head. The only question that can actually be settled: of
    #    the things visible on the day you choose, which predicts what follows?
    head_outputs = runs_of("why_not_returns.py")
    head = {
        signal: measure(
            head_outputs,
            "why_not_returns.py",
            rf"^{signal}\s+([\d.]+)%\s+([\d.]+)%\s+([+-][\d.]+)%\s+(\d+)/(\d+)\s+([+-][\d.]+)",
            ("top_quartile_pct", "bottom_quartile_pct", "spread_pp", "wins", "windows", "rank_ic"),
        )
        for signal in ("past_3y", "cost", "nav_level", "blend")
    }

    # 2. Cost on its own, over a longer window set.
    cost = measure(
        runs_of("validate_cost_ranking.py"),
        "validate_cost_ranking.py",
        r"cheap minus dear\s*:\s*([+-][\d.]+)% a year[\s\S]*?cheap beat dear in (\d+)/(\d+) windows = (\d+)%",
        ("spread_pp", "wins", "windows", "hit_rate_pct"),
    )

    # 3. The composite the app actually ships.
    composite = measure(
        runs_of("validate_quartiles.py"),
        "validate_quartiles.py",
        r"top minus bottom spread\s*:\s*([+-][\d.]+)% a year[\s\S]*?top beat bottom in (\d+)/(\d+) windows = (\d+)%",
        ("spread_pp", "wins", "windows", "hit_rate_pct"),
    )

    return {
        "measured_on": date.today().isoformat(),
        "runs_per_measurement": RUNS,
        # Reports THIS run, not a sentence someone typed once.
        #
        # This used to be a hardcoded string describing five runs while RUNS was
        # 3. It was re-emitted verbatim on every rebuild, so it could never be
        # wrong and never described the data beside it -- the same shape as a
        # check.sh that cannot fail. A caveat that is a constant is decoration.
        "why_ranges": (
            f"Each figure is the median of {RUNS} runs of each validator, with "
            f"the observed range. The validators fetch from mfapi at 24 threads "
            f"and which fetches succeed varies, so the sample varies with it. "
            f"Window counts actually seen in this run: "
            f"{_window_counts(head, cost, composite)}."
        ),
        "signals": head,
        "cost_alone": cost,
        "shipped_score": composite,
    }


def check(payload: dict) -> list[str]:
    """Refuse to write a track record that contradicts the product's design."""
    problems = []
    cost = payload["signals"]["cost"]
    past = payload["signals"]["past_3y"]

    if cost["rank_ic"]["median"] <= past["rank_ic"]["median"]:
        problems.append(
            f"cost rank IC {cost['rank_ic']['median']} did not beat past return's "
            f"{past['rank_ic']['median']} — the entire scoring model is built on it doing so"
        )
    if not 0.05 <= cost["rank_ic"]["median"] <= 0.45:
        problems.append(f"cost rank IC {cost['rank_ic']['median']} is outside anything plausible")
    if not -0.15 <= past["rank_ic"]["median"] <= 0.15:
        problems.append(
            f"past-return rank IC {past['rank_ic']['median']} is far from zero — "
            "if past returns started predicting, the product's premise changed"
        )
    for name, block in (("cost_alone", payload["cost_alone"]),
                        ("shipped_score", payload["shipped_score"])):
        rate = block["hit_rate_pct"]["median"]
        if not 30 <= rate <= 100:
            problems.append(f"{name} hit rate {rate}% is not a hit rate")
        if block["windows"]["median"] < 40:
            problems.append(f"{name} measured only {block['windows']['median']} windows")
    return problems


def main() -> int:
    payload = build()
    problems = check(payload)
    if problems:
        print("\nREFUSING TO WRITE — the record failed its own checks:\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    OUT.write_text(json.dumps(payload, indent=1))
    print(f"\nwrote {OUT}\n")

    def line(label: str, block: dict) -> None:
        wins, windows = block["wins"], block["windows"]
        ic = block.get("rank_ic")
        rng = "" if wins["low"] == wins["high"] else f" ({wins['low']:.0f}-{wins['high']:.0f})"
        print(
            f"  {label:<26}{wins['median']:>5.0f}/{windows['median']:<4.0f}"
            f"{wins['median'] / windows['median'] * 100:>7.0f}%{rng:<10}"
            f"{block['spread_pp']['median']:>+8.1f}pp"
            + (f"{ic['median']:>+9.3f}" if ic else "")
        )

    print(f"  {'claim':<26}{'wins':>10}{'rate':>7}{'':10}{'spread':>10}{'rank IC':>9}")
    for signal in ("cost", "blend", "nav_level", "past_3y"):
        line(signal, payload["signals"][signal])
    line("cost alone (longer set)", payload["cost_alone"])
    line("the score we ship", payload["shipped_score"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
