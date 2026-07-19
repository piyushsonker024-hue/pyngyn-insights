import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# Point PYNGYN_CSV at a real export to run this on your own data.
CSV = Path(os.environ.get("PYNGYN_CSV", ROOT / "data" / "tasks.csv"))
OUT = ROOT / "out" / "stats.json"

# Anything within +/-10% of estimate is "on target" -- estimates aren't promises.
ON_TARGET_BAND = 0.10
SIZE_BUCKETS = [(0, 2, "0-2h"), (2, 8, "2-8h"), (8, 16, "8-16h"), (16, 1e9, "16h+")]


def bucket_for(est):
    for lo, hi, label in SIZE_BUCKETS:
        if lo < est <= hi:
            return label
    return SIZE_BUCKETS[0][2]

# abstract away rounding to avoid cluttering the main logic with it
def r(x, n=1):
    return round(float(x), n)


def load():
    df = pd.read_csv(CSV)
    required = {"task_id", "assignee", "estimated_hours", "actual_hours", "status"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"CSV is missing columns: {sorted(missing)}")

    df["estimated_hours"] = pd.to_numeric(df["estimated_hours"], errors="coerce")
    df["actual_hours"] = pd.to_numeric(df["actual_hours"], errors="coerce")
    df = df.dropna(subset=["estimated_hours", "actual_hours"])
    df = df[df["estimated_hours"] > 0]

    df["variance_hours"] = df["actual_hours"] - df["estimated_hours"]
    df["slip_ratio"] = df["actual_hours"] / df["estimated_hours"]
    df["slip_pct"] = (df["slip_ratio"] - 1) * 100
    df["size_bucket"] = df["estimated_hours"].apply(bucket_for)
    df["outcome"] = pd.cut(
        df["slip_ratio"],
        bins=[-1e9, 1 - ON_TARGET_BAND, 1 + ON_TARGET_BAND, 1e9],
        labels=["under", "on_target", "over"],
    )
    return df


def headline(df):
    est, act = df["estimated_hours"].sum(), df["actual_hours"].sum()
    counts = df["outcome"].value_counts()
    return {
        "task_count": int(len(df)),
        "estimated_hours": r(est),
        "actual_hours": r(act),
        "variance_hours": r(act - est),
        "portfolio_slip_pct": r((act / est - 1) * 100),
        "median_task_slip_pct": r(df["slip_pct"].median()),
        "tasks_over": int(counts.get("over", 0)),
        "tasks_on_target": int(counts.get("on_target", 0)),
        "tasks_under": int(counts.get("under", 0)),
        "on_target_rate_pct": r(counts.get("on_target", 0) / len(df) * 100),
    }


def by_assignee(df):
    g = df.groupby("assignee")
    out = (
        pd.DataFrame(
            {
                "tasks": g.size(),
                "estimated_hours": g["estimated_hours"].sum().round(1),
                "actual_hours": g["actual_hours"].sum().round(1),
                "median_slip_pct": g["slip_pct"].median().round(1),
                "overrun_hours": g["variance_hours"].sum().round(1),
            }
        )
        .reset_index()
        .sort_values("median_slip_pct", ascending=False)
    )
    out["slip_pct"] = ((out["actual_hours"] / out["estimated_hours"] - 1) * 100).round(1)
    return out.to_dict("records")


def by_status(df):
    g = df.groupby("status")
    out = (
        pd.DataFrame(
            {
                "tasks": g.size(),
                "actual_hours": g["actual_hours"].sum().round(1),
                "median_slip_pct": g["slip_pct"].median().round(1),
                "overrun_hours": g["variance_hours"].sum().round(1),
            }
        )
        .reset_index()
        .sort_values("median_slip_pct", ascending=False)
    )
    return out.to_dict("records")


def by_size(df):
    order = [b[2] for b in SIZE_BUCKETS]
    g = df.groupby("size_bucket")
    out = pd.DataFrame(
        {
            "tasks": g.size(),
            "median_slip_pct": g["slip_pct"].median().round(1),
            "overrun_hours": g["variance_hours"].sum().round(1),
            "on_target_rate_pct": (
                g["outcome"].apply(lambda s: (s == "on_target").mean() * 100).round(1)
            ),
        }
    ).reset_index()
    out["size_bucket"] = pd.Categorical(out["size_bucket"], categories=order, ordered=True)
    return out.sort_values("size_bucket").to_dict("records")


def concentration(df):
    """How much of the total overrun comes from the worst few tasks?"""
    over = df[df["variance_hours"] > 0].sort_values("variance_hours", ascending=False)
    total = over["variance_hours"].sum()
    top_n = max(1, int(len(df) * 0.20))
    return {
        "total_overrun_hours": r(total),
        "top_20pct_task_count": int(top_n),
        "top_20pct_share_pct": r(over.head(top_n)["variance_hours"].sum() / total * 100),
        "tasks_causing_half_of_overrun": int(
            (over["variance_hours"].cumsum() < total * 0.5).sum() + 1
        ),
    }


def wip_exposure(df):
    """Hours already sunk into work that hasn't shipped."""
    open_work = df[df["status"] != "Done"]
    blocked = df[df["status"] == "Blocked"]
    return {
        "open_tasks": int(len(open_work)),
        "hours_sunk_in_open_work": r(open_work["actual_hours"].sum()),
        "blocked_tasks": int(len(blocked)),
        "hours_sunk_in_blocked_work": r(blocked["actual_hours"].sum()),
        "blocked_share_of_open_hours_pct": r(
            blocked["actual_hours"].sum() / max(open_work["actual_hours"].sum(), 1e-9) * 100
        ),
    }


def worst_tasks(df, n=8):
    cols = ["task_id", "assignee", "status", "estimated_hours", "actual_hours",
            "variance_hours", "slip_pct"]
    out = df.sort_values("variance_hours", ascending=False).head(n)[cols].copy()
    out["slip_pct"] = out["slip_pct"].round(0)
    return out.to_dict("records")


def scatter(df):
    cols = ["task_id", "assignee", "status", "estimated_hours", "actual_hours"]
    return df[cols].to_dict("records")


def main():
    df = load()
    stats = {
        "headline": headline(df),
        "by_assignee": by_assignee(df),
        "by_status": by_status(df),
        "by_size": by_size(df),
        "concentration": concentration(df),
        "wip_exposure": wip_exposure(df),
        "worst_tasks": worst_tasks(df),
        "scatter": scatter(df),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stats, indent=2))

    h = stats["headline"]
    print(f"analyzed {h['task_count']} tasks -> {OUT}")
    print(f"  portfolio slip : {h['portfolio_slip_pct']:+.1f}%  "
          f"({h['estimated_hours']}h estimated vs {h['actual_hours']}h actual)")
    print(f"  on target      : {h['on_target_rate_pct']}% of tasks")
    print(f"  worst cohort   : {stats['by_size'][-1]['size_bucket']} at "
          f"{stats['by_size'][-1]['median_slip_pct']:+.0f}% median slip")


if __name__ == "__main__":
    main()
