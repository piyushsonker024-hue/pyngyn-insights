# Pyngyn — AI Insights Dashboard

Takes task-level time tracking data, finds the bottlenecks in Python, has Claude
turn the numbers into plain English, and renders the result as a dashboard.

## Run it

```bash
pip install -r requirements.txt
python run.py
```

That's it. It simulates the data, analyzes it, writes the insights, builds the
page, and opens `http://localhost:8000/dashboard.html`.

The only dependency is pandas. Everything else is the Python standard library.

### Regenerating the insights live

The prototype ships with a cached insight set so it runs for you immediately with
no account or key. To have Claude write them fresh:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run.py
```

The dashboard labels which mode it ran in — look for `live` or `cached` next to
the findings and in the footer. If a live call fails, it falls back to cached
rather than breaking the build.

> **On the cached file:** `out/insights.cached.json` was produced by the prompt in
> `pipeline/insights.py`, run against the `stats.json` in this repo. It's real model
> output for this data, not hand-written filler — but if you want to watch the LLM
> step actually happen, set the key.

### Other ways to run it

```bash
python run.py --no-serve      # just build out/dashboard.html, don't serve
python run.py --keep-data     # reuse the existing CSV instead of regenerating
PYNGYN_CSV=/path/to/yours.csv python run.py --keep-data   # use your own export
PYNGYN_MODEL=claude-opus-4-8 python run.py                # different model
```

Your own CSV needs the five columns from the brief:
`task_id, assignee, estimated_hours, actual_hours, status`.

## How it works

```
generate_data.py → data/tasks.csv    160 simulated tasks with real bottlenecks buried in them
analyze.py       → out/stats.json    pandas: slip by assignee, status, task size, Pareto concentration
insights.py      → out/insights.json Claude reads the stats, writes 3–5 findings
build.py         → out/dashboard.html one self-contained file, no CDN, no backend
```

Each stage writes a file and the next one reads it, so you can run any stage
alone, inspect the intermediate JSON, or replace a stage without touching the rest.

**The LLM only sees the aggregates, never the 160 raw rows.** Python owns the
arithmetic; Claude owns the English. That keeps the prompt small, keeps the numbers
authoritative, and means the model can't quietly do bad math on the side. The
prompt tells it the stats are authoritative and every insight must cite one.

The response is parsed as strict JSON and validated for required fields before it
reaches the page — a malformed response fails loudly rather than rendering garbage.

## What the analysis looks for

A bottleneck is only visible against a baseline, so everything is a comparison:

- **Slip by task size** — do estimates hold at 2h and fall apart at 20h?
- **Slip by assignee** — a stable multiple is a calibration gap, not a speed problem
- **Slip by status** — which queue burns hours without moving work
- **Concentration** — how few tasks cause most of the overrun (this decides whether
  you fix a process or fix five tasks)
- **WIP exposure** — hours already sunk into work that hasn't shipped

The simulator plants five real patterns and then forgets about them. `analyze.py`
never sees `generate_data.py` — it rediscovers everything from the CSV alone, which
is the only way to know the analysis works.

## The dashboard

`out/dashboard.html` is one file with everything inlined — fonts, Chart.js, data,
insights. No CDN, no build step, no server needed. Double-click it, email it, drop
it behind any static host.

The centrepiece is the **slip rail**: one hard vertical baseline meaning *the
estimate*, with every cohort hanging off it — brick to the right for overrun, teal
to the left for under. Toggle it between task size, assignee, and status. The
scatter plots all 160 tasks against a parity line on log axes; anything above the
line took longer than it said it would.

The headline finding at the top is the model's own words, not copy anyone wrote by
hand. Nothing on the page is asserted by a human: Python computed it, Claude phrased it.

## Layout

```
run.py                     one command: simulate → analyze → insights → build → serve
requirements.txt           pandas
pipeline/
  generate_data.py         simulator (documents which bottlenecks it plants)
  analyze.py               pandas analysis → stats.json
  insights.py              Claude API call + prompt, cached fallback
  build.py                 inlines assets + data → dashboard.html
web/
  dashboard.template.html  markup, styles, slip rail, scatter
  vendor/                  Chart.js + fonts (MIT / OFL — see web/vendor/README.md)
data/tasks.csv             generated
out/                       stats.json, insights.json, dashboard.html
```

## If this were more than a prototype

- The CSV has no timestamps, so nothing here is a trend — every number is one
  snapshot. Sprint-over-sprint is the first thing I'd add, because "is it getting
  worse" is the actual question a lead asks.
- Insights are regenerated in full on every run. Real use wants them diffed against
  the last run so the page can say what *changed*, and cached on a stats hash so an
  unchanged dataset doesn't cost a call.
- Small-n cuts are noisy — dee.okafor has 18 tasks — and the prompt has no way to
  know that. I'd pass confidence intervals alongside the point estimates and tell
  the model to hedge cuts below a threshold.
- Naming individuals is the right call for a lead's private view and the wrong one
  for a shared dashboard. That should be a permission, not a default.
