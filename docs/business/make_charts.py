"""Charts for docs/BUSINESS_CASE.md. Run: python docs/business/make_charts.py

Sourced data (World Bank population projections, GBD 2019 dementia forecast, WHO risk factors) is typed in from the
research notes with its source in the document. Everything marked ESTIMATE is NeuroTwin's own planning assumption.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).parent
AED = 3.6725
SURFACE, INK, INK2, GRID, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1", "#b9b8b3"
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def save(fig, name, note):
    fig.text(0.01, 0.01, note, fontsize=8, color=INK2, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)


# 1. GCC people aged 60+ (millions), World Bank projections
years = ["2024", "2030", "2040", "2050"]
gcc60 = {"Saudi Arabia": [1.836, 2.469, 3.880, 6.122], "UAE": [0.412, 0.522, 0.559, 0.577],
         "Kuwait": [0.287, 0.345, 0.469, 0.577], "Oman": [0.228, 0.281, 0.452, 0.774],
         "Qatar": [0.099, 0.108, 0.141, 0.202], "Bahrain": [0.106, 0.133, 0.183, 0.248]}
fig, ax = plt.subplots(figsize=(8, 4.6))
bottom = [0.0] * 4
for i, (k, v) in enumerate(gcc60.items()):
    ax.bar(years, v, bottom=bottom, color=S[i], width=0.55, label=k, edgecolor=SURFACE, linewidth=2)
    bottom = [b + x for b, x in zip(bottom, v)]
for x, t in zip(years, bottom):
    ax.text(x, t + 0.12, f"{t:.1f} M", ha="center", fontweight="bold")
ax.set_title("People aged 60+ in the GCC nearly triple by 2050")
ax.set_ylabel("Millions of people aged 60+")
ax.set_ylim(0, 9.6)
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, ncol=3, loc="upper left")
save(fig, "gcc_ageing.png", "Source: World Bank Population Estimates and Projections (2026 update).")

# 2. Growth in dementia cases 2019 -> 2050 (GBD 2019 forecast, Nichols et al. 2022)
growth = [("Qatar", 1926), ("UAE", 1795), ("Bahrain", 1084), ("Oman", 943), ("Saudi Arabia", 898), ("Kuwait", 850),
          ("Middle East & N. Africa", 367), ("Singapore", 356), ("Malaysia", 249), ("Indonesia", 244),
          ("China", 197), ("India", 197), ("South Korea", 191), ("World", 166), ("Japan", 27)]
gulf = {"Qatar", "UAE", "Bahrain", "Oman", "Saudi Arabia", "Kuwait"}
fig, ax = plt.subplots(figsize=(8, 5.4))
names = [g[0] for g in growth][::-1]
vals = [g[1] for g in growth][::-1]
ax.barh(names, vals, color=[S[0] if n in gulf else MUTED for n in names], height=0.62)
for n, v in zip(names, vals):
    ax.text(v + 25, n, f"+{v:,}%", va="center", fontsize=9, fontweight="bold" if n in gulf else "normal")
ax.set_title("Dementia cases grow fastest in the Gulf (2019 to 2050)")
ax.set_xlabel("Increase in people living with dementia, %")
ax.set_xlim(0, 2250)
ax.grid(axis="y", visible=False)
save(fig, "dementia_growth.png", "Blue: GCC states. Source: GBD 2019 Dementia Forecasting Collaborators, Lancet Public Health 2022.")

# 3. Market size funnel (ESTIMATE, bottom-up from population, 2030)
PRICE_YEAR = 15 * 12 / AED          # AED 15 per person per month
tam = 9.731e6 * PRICE_YEAR          # GCC adults 50+ in 2030
sam = 1.415e6 * 0.414 * PRICE_YEAR  # UAE adults 50+ x hypertension share (vascular risk group)
som = 25_000 * PRICE_YEAR           # people enrolled by year 5 in the UAE
rows = [("GCC: everyone aged 50+ (9.7 M people)", tam), ("UAE: aged 50+ with vascular risk (0.59 M)", sam),
        ("2030 target: 25,000 people in the UAE", som)]
fig, ax = plt.subplots(figsize=(8, 3.4))
for i, (label, v) in enumerate(rows):
    ax.barh(2 - i, v / 1e6, color=S[0], alpha=[0.35, 0.65, 1][i], height=0.6)
    ax.text(v / 1e6 + 6, 2 - i, f"USD {v / 1e6:,.1f} M a year   ·   {label}", va="center", fontsize=9)
ax.set_yticks([2, 1, 0], ["TAM", "SAM", "SOM"])
ax.set_xlim(0, 900)
ax.set_xlabel("Annual subscription value at AED 15 per person per month, USD millions")
ax.set_title("Market size, 2030 (estimate)")
ax.grid(axis="y", visible=False)
save(fig, "market_funnel.png", "ESTIMATE. Population: World Bank 2030 projection. Risk share: WHO hypertension prevalence, UAE 41.4%.")

# 4. Price vs cost per active person per month (USD; cost inputs from 2026 price lists, mix is an ESTIMATE)
costs = [("WhatsApp reminders", 0.25), ("UAE hosting (at 10,000 people)", 0.06), ("Voice (speech in and out)", 0.24),
         ("Language-model summaries", 0.03), ("Support and customer success", 0.60)]
price = 15 / AED
fig, ax = plt.subplots(figsize=(8, 4.2))
left = 0.0
for i, (k, v) in enumerate(costs):
    ax.barh("Cost to serve", v, left=left, color=S[i + 1], label=f"{k}: ${v:.2f}", height=0.5, edgecolor=SURFACE, linewidth=2)
    left += v
ax.barh("Price (AED 15)", price, color=S[0], height=0.5)
ax.text(left + 0.05, "Cost to serve", f"${left:.2f}", va="center", fontweight="bold")
ax.text(price + 0.05, "Price (AED 15)", f"${price:.2f}  ·  gross margin {100 * (1 - left / price):.0f}%",
        va="center", fontweight="bold")
ax.set_xlim(0, 6)
ax.set_xlabel("USD per enrolled person per month")
ax.set_title("Each person costs about $1.2 a month to serve")
ax.grid(axis="y", visible=False)
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=8.5)
save(fig, "unit_economics.png", "Prices: Azure UAE North, Twilio/Meta, Google Gemini and Azure Speech price lists (Nov 2026). Mix and support: ESTIMATE.")

# 5. Competitive position (NeuroTwin's assessment from the competitor research)
pts = [("Cognivue", 1.5, 1.0), ("CANTAB", 2.2, 1.6), ("BrainCheck", 2.5, 0.85), ("Linus Health", 1.9, 1.35),
       ("Cogstate", 3.0, 1.5), ("Creyos", 3.1, 1.15), ("Neurotrack", 3.6, 1.0), ("Arabic MoCA (paper)", 1.2, 3.6),
       ("NeuroTwin", 4.5, 4.5)]
fig, ax = plt.subplots(figsize=(7, 5.2))
for n, x, y in pts:
    me = n == "NeuroTwin"
    ax.scatter(x, y, s=180 if me else 90, color=S[0] if me else MUTED, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.annotate(n, (x, y), xytext=(8, 6), textcoords="offset points", fontsize=10 if me else 9,
                fontweight="bold" if me else "normal")
ax.set_xlim(0.5, 5.2)
ax.set_ylim(0.5, 5.2)
ax.set_xticks([1, 5], ["One test, compared\nwith age norms", "Repeated, compared with\nthe person's own past"])
ax.set_yticks([1, 5], ["English only,\nno Gulf presence", "Arabic-first,\nGulf-ready"])
ax.axvline(2.85, color=GRID)
ax.axhline(2.85, color=GRID)
ax.grid(False)
ax.set_title("Only NeuroTwin is Arabic-first and built on change")
save(fig, "competitor_map.png", "Positions are NeuroTwin's assessment from published product information (2025-2026); not a measured score.")

# 6. Five-year plan (ESTIMATE)
plan = [  # year, avg people enrolled, price AED PMPM, new sites, operating cost USD M
    (2027, 400, 15, 1, 0.45), (2028, 3_000, 15, 5, 0.90), (2029, 10_000, 14, 12, 1.50),
    (2030, 25_000, 13, 20, 2.30), (2031, 60_000, 12, 35, 3.20), (2032, 110_000, 11, 40, 3.90)]
yrs = [str(p[0]) for p in plan]
rev = [(p[1] * p[2] * 12 + p[3] * 25_000) / AED / 1e6 for p in plan]
cost = [p[4] for p in plan]
fig, ax = plt.subplots(figsize=(8, 4.4))
ax.plot(yrs, rev, color=S[0], linewidth=2, marker="o", markersize=8, label="Revenue")
ax.plot(yrs, cost, color=S[1], linewidth=2, marker="o", markersize=8, label="Operating cost")
for x, r, p in zip(yrs, rev, plan):
    ax.annotate(f"${r:.2f} M", (x, r), xytext=(10, -4), textcoords="offset points", ha="left", va="top",
                fontsize=9, fontweight="bold")
ax.set_xticks(range(len(yrs)), [f"{y}\n{p[1]:,} people" for y, p in zip(yrs, plan)])
ax.set_ylabel("USD millions a year")
ax.set_ylim(-0.4, 6.2)
ax.set_title("Revenue passes operating cost in year 6, 2032 (estimate)")
ax.legend(frameon=False, loc="upper left")
ax.grid(axis="x", visible=False)
save(fig, "five_year_plan.png", "ESTIMATE. Abu Dhabi 2027-28, Dubai from 2028, Saudi Arabia from 2029, a second Gulf state from 2031. Setup fee AED 25,000 per new site.")

# 7. Vascular risk: Gulf vs Asia (WHO)
rk = [("UAE", 31.6, 41.4), ("Saudi Arabia", 40.1, 34.0), ("Qatar", 42.0, 40.9), ("Kuwait", 40.4, 40.5),
      ("Japan", 5.9, 31.4), ("South Korea", 8.4, 26.7), ("Singapore", 17.0, 31.5), ("India", 8.0, 31.1)]
fig, ax = plt.subplots(figsize=(8, 4.2))
xs = range(len(rk))
ax.bar([x - 0.19 for x in xs], [r[1] for r in rk], width=0.36, color=S[0], label="Obesity, adults (2024)")
ax.bar([x + 0.19 for x in xs], [r[2] for r in rk], width=0.36, color=S[1], label="Hypertension, ages 30-79 (2019)")
ax.set_xticks(list(xs), [r[0] for r in rk])
ax.set_ylabel("% of adults")
ax.set_ylim(0, 50)
ax.set_title("Gulf adults carry far more vascular risk for later cognitive decline")
ax.legend(frameon=False, ncol=2, loc="upper right")
ax.grid(axis="x", visible=False)
save(fig, "risk_factors.png", "Source: WHO Global Health Observatory.")

print("TAM %.0f SAM %.1f SOM %.2f USD M" % (tam / 1e6, sam / 1e6, som / 1e6))
for y, r, c in zip(yrs, rev, cost):
    print(y, round(r, 2), c)
