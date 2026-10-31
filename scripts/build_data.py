"""Synthetic oil palm estate -> yield model -> root-cause diagnosis -> web/data/estate.json.

Everything here is simulated. The method is the one used with the client's
agronomists: per block, join land, planting material, spraying, rainfall, pest
and fertiliser records to the yield; fit a model of what drives yield; turn the
model into a loss per cause for every block; walk the experts' checklist to name
the cause the field team should fix first; then act and measure again.

Only numpy is needed. Run from the repo root:  python scripts/build_data.py
"""
import json
from pathlib import Path

import numpy as np

rng = np.random.default_rng(11)
OUT = Path(__file__).resolve().parents[1] / "web" / "data" / "estate.json"

COLS, ROWS, SIZE = 30, 20, 500          # blocks of 500 m x 500 m (25 ha)
YEAR = 2025
CAUSES = ["land", "pesticide", "species", "management", "weather", "pests"]
CAUSE_LABEL = {
    "land": "Land", "pesticide": "Pesticide", "species": "Species",
    "management": "Fertiliser", "weather": "Weather", "pests": "Pests and disease",
}


def smooth_field(scale, n=6):
    """A smooth random surface over the estate, roughly in [-1, 1]."""
    x = np.arange(COLS)[None, :] / COLS
    y = np.arange(ROWS)[:, None] / ROWS
    f = np.zeros((ROWS, COLS))
    for _ in range(n):
        kx, ky = rng.uniform(0.5, scale, 2)
        f += np.sin(2 * np.pi * (kx * x + rng.random())) * np.cos(2 * np.pi * (ky * y + rng.random()))
    return f / np.abs(f).max()


# ---------------------------------------------------------------- estate shape
cx, cy = (COLS - 1) / 2, (ROWS - 1) / 2
gx, gy = np.meshgrid(np.arange(COLS), np.arange(ROWS))
r = np.hypot((gx - cx) / (COLS / 2), (gy - cy) / (ROWS / 2))
inside = r + 0.22 * smooth_field(2.5) < 1.0
inside[ROWS // 2 - 1: ROWS // 2 + 1, :3] = False            # river inlet on the west side
rr, cc = np.nonzero(inside)
n = len(rr)
division = np.where(cc < COLS / 2, np.where(rr < ROWS / 2, "A", "C"), np.where(rr < ROWS / 2, "B", "D"))

# ---------------------------------------------------------------- block records
# Each field is "what the records say"; the hidden truth is how they move yield.
low = smooth_field(2.0)[rr, cc]                              # low-lying ground near the river
peat = (low < -0.45) & (cc < COLS * 0.55)
drainage = np.where(peat, "peat", np.where(low < -0.15, "poor", "good"))
slope = np.clip(6 + 9 * smooth_field(3.0)[rr, cc] + rng.normal(0, 2, n), 0, 24).round(1)
ph = np.clip(4.9 + 0.5 * smooth_field(3.0)[rr, cc] - 0.7 * peat + rng.normal(0, 0.15, n), 3.6, 6.0).round(2)

# Planting material follows the replanting history: whole rows of blocks share a year.
planted = np.zeros(n, int)
clone = np.empty(n, object)
for d, start in zip("ABCD", [2004, 2009, 2000, 2012]):
    m = division == d
    planted[m] = start + (rr[m] % 5) + rng.integers(0, 2, m.sum())
    clone[m] = rng.choice(["DxP Marihat", "DxP Socfindo", "Legacy tenera"], m.sum(),
                          p=[0.45, 0.35, 0.20] if d in "BD" else [0.3, 0.3, 0.4])
age = YEAR - planted

# Spraying: the schedule slips in some contractor zones, and a cheaper product was used in a few.
late_zone = smooth_field(4.0)[rr, cc] > 0.45
spray_late = np.clip(np.where(late_zone, rng.normal(26, 8, n), rng.normal(4, 4, n)), 0, 60).round()
wrong_product = rng.random(n) < np.where(late_zone, 0.25, 0.04)

rain_normal = 2400
rain = (rain_normal * (1 + 0.08 * smooth_field(1.5)[rr, cc]) + rng.normal(0, 60, n)).round()
dry_patch = (gx[rr, cc] > COLS * 0.72) & (gy[rr, cc] < ROWS * 0.35)
rain[dry_patch] *= 0.66                                        # a dry pocket in the north-east
rain = rain.round()

gano = np.clip(rng.gamma(1.2, 1.5, n) + 9 * (smooth_field(5.0)[rr, cc] > 0.7) * (age > 14), 0, 30).round(1)
fert = np.clip(rng.normal(0.95, 0.06, n) - 0.35 * (rng.random(n) < 0.07), 0.4, 1.1).round(2)

# ---------------------------------------------------------------- hidden yield
def age_curve(a):
    """Fresh fruit bunch potential by palm age, tonnes per hectare per year."""
    return np.where(a < 4, 6, np.where(a < 9, 6 + (a - 3) * 3.6, np.where(a < 19, 27, 27 - (a - 18) * 0.9)))


CLONE_FACTOR = {"DxP Marihat": 1.0, "DxP Socfindo": 0.98, "Legacy tenera": 0.80}
potential = age_curve(age) * np.array([CLONE_FACTOR["DxP Marihat"]] * n)
true_mult = (
    np.array([CLONE_FACTOR[c] for c in clone])
    * np.where(drainage == "peat", 0.66, np.where(drainage == "poor", 0.80, 1.0))
    * (1 - 0.06 * np.clip(4.6 - ph, 0, None) * 2) * (1 - 0.008 * np.clip(slope - 10, 0, None))
    * (1 - 0.011 * np.clip(spray_late - 7, 0, None)) * np.where(wrong_product, 0.90, 1.0)
    * (1 - 0.9 * np.clip(1 - rain / rain_normal - 0.1, 0, None))
    * (1 - 0.016 * gano)
    * (1 - 0.9 * np.clip(0.9 - fert, 0, None))
)
yield_t = (potential * true_mult * np.exp(rng.normal(0, 0.035, n))).round(2)

# ---------------------------------------------------------------- yield model
# log(yield / age potential) on the record fields. Each coefficient times the
# block's distance from good practice is that block's loss to that cause.
GOOD = {"ph": 5.0, "slope": 8.0, "spray_late": 5.0, "rain": 0.0, "gano": 1.0, "fert": 1.0}
X_cols, groups = [], []


def add(col, group):
    X_cols.append(col)
    groups.append(group)


add((drainage == "poor").astype(float), "land")
add((drainage == "peat").astype(float), "land")
add(np.clip(GOOD["ph"] - ph, 0, None), "land")
add(np.clip(slope - GOOD["slope"], 0, None), "land")
add((clone == "DxP Socfindo").astype(float), "species")
add((clone == "Legacy tenera").astype(float), "species")
add(np.clip(spray_late - GOOD["spray_late"], 0, None), "pesticide")
add(wrong_product.astype(float), "pesticide")
rain_def = np.clip(1 - rain / rain_normal, 0, None)
add(rain_def, "weather")
add(np.clip(gano - GOOD["gano"], 0, None), "pests")
add(np.clip(GOOD["fert"] - fert, 0, None), "management")
X = np.column_stack(X_cols)
target = np.log(yield_t / age_curve(age))
A = np.column_stack([np.ones(n), X])
beta, *_ = np.linalg.lstsq(A, target, rcond=None)
pred = A @ beta
r2 = 1 - ((target - pred) ** 2).sum() / ((target - target.mean()) ** 2).sum()
groups = np.array(groups)

# Loss per cause in t/ha: what the block would gain if only that cause were at good practice.
loss = {}
for g in CAUSES:
    contrib = X[:, groups == g] @ beta[1:][groups == g]
    loss[g] = np.clip(yield_t * (np.exp(-contrib) - 1), 0, None)
gap = np.clip(age_curve(age) - yield_t, 0, None)

# ---------------------------------------------------------------- expert checklist
# The order the agronomists asked for: rule out what nobody can fix, then the
# quick wins, then the slow structural causes.
def diagnose(i):
    steps = []
    ref = age_curve(age[i])

    def step(q, ok, ev, cause):
        steps.append({"q": q, "ok": bool(ok), "ev": ev, "cause": None if ok else cause,
                      "loss": round(float(loss[cause][i]), 2) if cause else None})
        return not ok

    pct = yield_t[i] / ref * 100
    steps.append({"q": "Is yield close to the age benchmark?", "ok": bool(pct >= 88), "cause": None, "loss": None,
                  "ev": f"{yield_t[i]:.1f} t/ha against {ref:.1f} t/ha expected at age {age[i]} ({pct:.0f}%)"})
    if pct >= 88:
        return steps, None
    if step("Was rainfall normal?", rain[i] >= 0.8 * rain_normal,
            f"{rain[i]:.0f} mm in the last 12 months, estate normal {rain_normal} mm", "weather"):
        return steps, "weather"
    if step("Are pests and disease under control?", gano[i] < 6,
            f"Ganoderma in {gano[i]:.1f}% of palms (threshold 6%)", "pests"):
        return steps, "pests"
    if step("Was spraying on schedule with the right product?", spray_late[i] <= 14 and not wrong_product[i],
            f"Last round {spray_late[i]:.0f} days late"
            + (", cheaper substitute product" if wrong_product[i] else ", product as specified"), "pesticide"):
        return steps, "pesticide"
    if step("Is the land in good shape?", drainage[i] == "good" and ph[i] >= 4.5 and slope[i] <= 15,
            f"Drainage {drainage[i]}, soil pH {ph[i]:.1f}, slope {slope[i]:.0f}°", "land"):
        return steps, "land"
    if step("Is the planting material a current clone?", clone[i] != "Legacy tenera",
            f"{clone[i]}, planted {planted[i]}", "species"):
        return steps, "species"
    if step("Was the full fertiliser dose applied?", fert[i] >= 0.85,
            f"{fert[i] * 100:.0f}% of the recommended dose", "management"):
        return steps, "management"
    # Nothing on the checklist explains it: hand to the agronomists with the model's top cause.
    top = max(CAUSES, key=lambda g: loss[g][i])
    steps.append({"q": "Checklist clear. Model's largest loss?", "ok": False,
                  "ev": f"{CAUSE_LABEL[top]} costs {loss[top][i]:.1f} t/ha; sent to agronomist review",
                  "cause": top, "loss": round(float(loss[top][i]), 2)})
    return steps, top


diag = [diagnose(i) for i in range(n)]
cause = np.array([d[1] or "none" for d in diag])

# Agreement between the checklist and the model's largest loss, for weak blocks.
weak = cause != "none"
model_top = np.array([max(CAUSES, key=lambda g: loss[g][i]) for i in range(n)])
agree = float((model_top[weak] == cause[weak]).mean())

# ---------------------------------------------------------------- act, then measure again
# Fix for each cause and the share of the modelled loss it recovers within a season.
FIX = {
    "pesticide": ("Spray rounds back on schedule, specified product only", 0.9),
    "land": ("Drains cleared, liming, terraces repaired", 0.75),
    "species": ("Fertiliser matched to the clone, block queued for replanting", 0.45),
    "management": ("Full fertiliser dose, application audited", 0.9),
    "pests": ("Infected palms removed, trenching", 0.6),
    "weather": ("No field fix; mulching to hold moisture", 0.15),
}
# The team acts on every cause on the block's ranked list that costs at least 0.5 t/ha.
acted = {g: (cause != "none") & (loss[g] >= 0.5) for g in CAUSES}
gain = sum(FIX[g][1] * loss[g] * acted[g] for g in CAUSES) * (age_curve(age) > 6)
# One scale on the recovery rates so the estate total lands on the real result (+18%).
k = 0.18 * yield_t.sum() / gain.sum()
after = (yield_t + k * gain).round(2)
uplift = after.sum() / yield_t.sum() - 1

# ---------------------------------------------------------------- export
blocks = []
for i in range(n):
    steps, c = diag[i]
    ranked = sorted(((g, round(float(loss[g][i]), 2)) for g in CAUSES), key=lambda t: -t[1])
    blocks.append({
        "id": f"{division[i]}{rr[i]:02d}{cc[i]:02d}",
        "x": int(cc[i]), "y": int(rr[i]), "div": str(division[i]),
        "age": int(age[i]), "planted": int(planted[i]), "clone": str(clone[i]),
        "drainage": str(drainage[i]), "ph": float(ph[i]), "slope": float(slope[i]),
        "late": int(spray_late[i]), "wrong": bool(wrong_product[i]), "rain": int(rain[i]),
        "gano": float(gano[i]), "fert": float(fert[i]),
        "bench": round(float(age_curve(age[i])), 2), "yield": float(yield_t[i]), "after": float(after[i]),
        "gap": round(float(gap[i]), 2), "cause": c or "none",
        "fix": FIX[c][0] if c else None, "steps": steps, "ranked": ranked,
    })

share = {g: float(sum(loss[g][cause != "none"])) for g in CAUSES}
tot = sum(share.values())
summary = {
    "blocks": n, "hectares": n * 25, "weak": int(weak.sum()),
    "by_cause": {g: int((cause == g).sum()) for g in CAUSES},
    "loss_share": {g: round(v / tot, 3) for g, v in share.items()},
    "r2": round(float(r2), 3), "agree": round(agree, 3),
    "before_t": round(float((yield_t * 25).sum())), "after_t": round(float((after * 25).sum())),
    "uplift": round(float(uplift), 4), "recovery_scale": round(float(k), 3),
}
data = {
    "meta": {"cols": COLS, "rows": ROWS, "size_m": SIZE, "year": YEAR, "rain_normal": rain_normal},
    "causes": [{"id": g, "label": CAUSE_LABEL[g], "fix": FIX[g][0]} for g in CAUSES],
    "summary": summary, "blocks": blocks,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, separators=(",", ":")))
print(json.dumps(summary, indent=1))
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
