import csv
import random
from pathlib import Path

SEED = 20260717
N_TASKS = 160
OUT = Path(__file__).resolve().parents[1] / "data" / "tasks.csv"

ASSIGNEES = ["priya.n", "marco.r", "dee.okafor", "sam.liang", "yuki.t", "ana.silva"]
STATUSES = ["Done", "In Progress", "In Review", "Blocked"]
STATUS_WEIGHTS = [0.58, 0.18, 0.15, 0.09]

# Per-assignee estimation bias (multiplier applied to actual hours).
# >1 means they routinely take longer than they said they would.
BIAS = {
    "priya.n": 1.52,      # planted: chronic under-estimator
    "marco.r": 0.81,      # planted: sandbagger
    "dee.okafor": 0.97,
    "sam.liang": 1.03,
    "yuki.t": 1.14,
    "ana.silva": 0.95,
}

# Status drag: work that piles up without the task closing.
STATUS_DRAG = {
    "Done": 1.00,
    "In Progress": 1.00,
    "In Review": 1.19,    # planted: review queue burns real hours
    "Blocked": 1.38,      # planted: blocked tasks bleed time
}


def estimate_hours(rng):
    """Estimates cluster on human-friendly numbers, with a long right tail."""
    roll = rng.random()
    if roll < 0.32:
        return rng.choice([0.5, 1, 1.5, 2])
    if roll < 0.70:
        return rng.choice([3, 4, 5, 6, 8])
    if roll < 0.90:
        return rng.choice([10, 12, 16])
    return rng.choice([20, 24, 32, 40])


def size_penalty(est):
    """Planted: the bigger the estimate, the worse the estimate."""
    if est <= 2:
        return 0.99
    if est <= 8:
        return 1.04
    if est <= 16:
        return 1.17
    return 1.44


def main():
    rng = random.Random(SEED)
    rows = []

    for i in range(1, N_TASKS + 1):
        assignee = rng.choice(ASSIGNEES)
        status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        est = estimate_hours(rng)

        factor = BIAS[assignee] * size_penalty(est) * STATUS_DRAG[status]
        # Log-normal-ish noise so most tasks land near the factor and a few blow out.
        noise = rng.lognormvariate(0, 0.22)
        actual = est * factor * noise

        # A handful of true disasters -- the Pareto tail.
        if rng.random() < 0.04:
            actual *= rng.uniform(1.6, 2.6)

        # Tasks that haven't started burning time yet.
        if status == "In Progress" and rng.random() < 0.25:
            actual *= rng.uniform(0.25, 0.6)

        actual = max(0.25, round(actual * 4) / 4)  # quarter-hour granularity

        rows.append(
            {
                "task_id": f"PYN-{1000 + i}",
                "assignee": assignee,
                "estimated_hours": est,
                "actual_hours": actual,
                "status": status,
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {len(rows)} tasks -> {OUT}")


if __name__ == "__main__":
    main()
