# DealerPulse AI
**Cars24 Dealer Activity & Performance Intelligence Agent**
TM: rishabh.malhotra1@cars24.com

---

## What it does
- Filters 12,000+ dealers to only those under your TM/TL
- Categorises them: **Gold / Diamond / Silver / Active-No-SI / Churned / Dormant**
- Sends a **daily Slack flash card** to `#referral-ndl-team-rishabh` at 12pm IST
- Gives you a **preview + Approve/Reject** before publishing to the team
- Generates a **downloadable Excel** with all dealers, KAM assignments, and action tags

---

## How to use (daily)

### Step 1 — Run analysis on fresh dump
```bash
python3 dealerpulse_agent.py dealer_dump.csv --excel
```

### Step 2 — Output files generated
| File | Purpose |
|---|---|
| `DealerPulse_Portfolio_Report.xlsx` | Download and share with team |
| `latest_flash_card.json` | Auto-loaded by n8n for 12pm Slack |

---

## Dealer Tiers

| Tier | Criteria | Priority |
|---|---|---|
| 🥇 Gold | L3M SI ≥ 5, has leads + insp | P1 — Protect |
| 💎 Diamond | L3M SI 2–4, has leads + insp | P1 — Grow |
| 🥈 Silver | L3M SI = 1, has leads + insp | P2 — Nurture |
| ⚠ Active-No-SI | L3M leads > 0, SI = 0 | P2 — Convert |
| 🔴 Churned | Was active, no leads last 3M | P1 — Re-engage |
| 💤 Dormant | No leads in 6M | P3 — Winback |

---

## n8n Workflows (auto-run daily)

| Workflow | Schedule | Action |
|---|---|---|
| Daily Upload Reminder | 11:00 AM IST | DM to rishabh — upload fresh CSV |
| Preview & Publish | 12:00 PM IST | DM preview → Approve → post to team channel |

---

## Files in this repo

```
dealerpulse_agent.py          ← Main analysis agent
pbi_connect.py                ← Power BI connector (future use)
DealerPulse_Portfolio_Report.xlsx  ← Latest dealer Excel report
latest_flash_card.json        ← Latest Slack flash card payload
README.md                     ← This file
```
