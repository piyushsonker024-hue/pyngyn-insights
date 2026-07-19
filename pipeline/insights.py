"""
Turn raw stats into plain-English insights using Claude.

Reads  : out/stats.json
Writes : out/insights.json

Runs in one of two modes:

  live   -- ANTHROPIC_API_KEY is set. Calls the Messages API and regenerates
            insights from whatever is currently in stats.json.
  cached -- no key. Falls back to out/insights.cached.json so the dashboard
            still builds and runs. The cached file was produced by this exact
            prompt against this exact stats.json.

Only the aggregates go to the model, never the raw task rows: it keeps the
prompt small, keeps the numbers authoritative, and means the model is writing
*about* the analysis rather than redoing it.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "out" / "stats.json"
OUT = ROOT / "out" / "insights.json"
CACHE = ROOT / "out" / "insights.cached.json"

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("PYNGYN_MODEL", "claude-sonnet-5")

SYSTEM = """You are an analyst embedded in a delivery team. You are given \
pre-computed statistics from a task-level time tracking dataset. Your job is to \
write 3-5 insights a team lead can act on in their next planning meeting.

Rules:
- The statistics are authoritative. Never invent, recompute, or contradict a number.
- Every insight must cite at least one specific number from the stats.
- Find the bottleneck, don't just restate the total. Prefer comparisons (this cohort
  vs that one) over standalone facts. "Estimates slipped 48%" is a number; "estimates
  hold under 8h and collapse above 16h" is an insight.
- Be concrete about people only where the data is unambiguous, and describe the
  pattern (an estimation-calibration gap), not the person's competence.
- No hedging, no filler, no restating the question. Plain English, short sentences.

Return ONLY a JSON array, no prose and no markdown fences. Each element:
{
  "headline": "under 60 chars, the finding itself, sentence case",
  "body": "2-3 sentences: what the data shows, why it matters",
  "metric": "the single number that proves it, under 18 chars",
  "metric_label": "what that number is, under 30 chars",
  "severity": "critical" | "warning" | "watch",
  "action": "one sentence, imperative, something doable this sprint"
}
Order by severity, most severe first."""


def build_prompt(stats):
    # Drop the per-task scatter -- the model doesn't need 160 rows to see a pattern.
    payload = {k: v for k, v in stats.items() if k != "scatter"}
    return (
        "Task time tracking statistics for the current period.\n"
        "Slip percentages are (actual / estimated - 1) * 100. Positive means over estimate.\n"
        "'on_target' means within +/-10% of estimate.\n\n"
        f"{json.dumps(payload, indent=2)}\n\n"
        "Write the insights."
    )


def call_claude(stats, api_key):
    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 2000,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": build_prompt(stats)}],
        }
    ).encode()

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read())

    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return parse(text)


def parse(text):
    """The model is told to return bare JSON. Tolerate fences anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in model response")
    insights = json.loads(text[start : end + 1])
    if not isinstance(insights, list) or not insights:
        raise ValueError("model returned an empty insight list")
    required = {"headline", "body", "metric", "metric_label", "severity", "action"}
    for i in insights:
        missing = required - set(i)
        if missing:
            raise ValueError(f"insight missing fields: {sorted(missing)}")
    return insights[:5]


def main():
    stats = json.loads(STATS.read_text())
    key = os.environ.get("ANTHROPIC_API_KEY")

    if key:
        try:
            insights = call_claude(stats, key)
            source = f"live: {MODEL}"
        except (urllib.error.URLError, ValueError, json.JSONDecodeError) as e:
            print(f"  ! live call failed ({e}); falling back to cached insights",
                  file=sys.stderr)
            insights, source = json.loads(CACHE.read_text()), "cached (live call failed)"
    else:
        if not CACHE.exists():
            raise SystemExit("no ANTHROPIC_API_KEY and no cached insights to fall back on")
        insights, source = json.loads(CACHE.read_text()), "cached"

    OUT.write_text(json.dumps({"source": source, "insights": insights}, indent=2))
    print(f"wrote {len(insights)} insights ({source}) -> {OUT}")


if __name__ == "__main__":
    main()
