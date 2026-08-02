# Family Dinners 🍽️

A dead-simple weekly dinner planner. It reads **live Coles prices**, finds what's on
special (especially half-price), picks a week of dinners whose ingredients are cheapest
right now, and prints **one combined shopping list**.

Built meal-first on purpose: no "what should we buy?" — just this week's meals and a list.
Large text, high contrast, big buttons, works on a phone (Add to Home Screen).

## How it works
- **`collector.py`** — fetches live Coles prices for every ingredient in `meals.json`
  (public `_next/data` endpoint, no login). Half-price = `now ≤ 50% of was`. Saves a
  snapshot to `prices/` each run — this history is what powers "next half-price" prediction later.
- **`build_site.py`** — picks a varied week (max 2 per theme, favouring specials) and builds
  the accessible page in `docs/` (one shopping list, print button, one-tap meal swaps).
- **`deploy.ps1`** — what this PC runs every Wednesday morning via a Scheduled Task
  (register it with `deploy/setup_task.ps1`): refresh → rebuild → commit → push. GitHub Pages
  serves `docs/`. (`deploy.sh` is the same job for a \*nix host.)

Coles changes specials Tuesday night (live Wednesday), so the refresh runs Wednesday AM.

> **Why this PC and not a server?** Coles blocks datacenter IPs — a VPS or CI runner gets a
> ~212-byte Incapsula bot-challenge instead of the page. The fetch has to come from a
> residential AU connection, so the weekly job runs on a home PC and just pushes the result up.

## Run it yourself
No dependencies — just Python 3:

    python3 collector.py      # fetch live prices -> prices/latest.json
    python3 build_site.py     # build docs/index.html
    # open docs/index.html

## Desktop app
`app.py` is a native window (pywebview) that shows the current week's plan, with
**Refresh prices** (re-pull live Coles + rebuild) and **Send to family** (publish to
GitHub Pages so the parents' page updates). It reuses the exact `collector.py` +
`build_site.py` the weekly job runs — the app is just a friendly front door.

    python app.py            # open the window
    python app.py --refresh  # headless pull + rebuild
    python build.py          # package -> dist/FamilyDinners.exe

## Edit the meals
`meals.json` — add/remove meals, tweak ingredient wording to match what you actually buy.
Pantry staples (oil, salt, spices) are listed separately so they don't clutter the shop.

## Honest notes
- Prices are **indicative**: it takes the cheapest relevant match per ingredient, which can
  occasionally pick an odd pack size. Good enough for "what's cheap this week".
- Quantities assume one of each item.
- "Next half-price" prediction needs a few weeks of snapshots before it can appear.
- Coles only for now; Woolworths can be added if it's reachable from the collector's host.
