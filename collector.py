"""
family-dinners collector
-------------------------
Resolves every ingredient in meals.json to a live Coles price, flags specials /
half-prices, and scores which dinners are cheapest this week.

Stdlib only (urllib + json) so it runs on any machine with Python, no pip install.
Coles catalogue changes Tuesday night (live Wednesday), so this is meant to run
each Wednesday morning; every run is appended to prices/ to build history.
"""
import json, sys, time, urllib.request, urllib.parse, datetime, os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 safety

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HALF_PRICE = 0.50        # now <= 50% of was
SPECIAL_MIN = 0.15       # >=15% off counts as "on special"
TOP_N = 12               # cheapest within the N most-relevant results (avoids junk matches)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def get_build_id():
    html = _get("https://www.coles.com.au/")
    key = '"buildId":"'
    i = html.find(key)
    if i == -1:
        raise RuntimeError("could not find Coles buildId on homepage")
    j = html.find('"', i + len(key))
    return html[i + len(key):j]


def search(term, build):
    """Return the cheapest relevant Coles product for `term`, with special info."""
    url = (f"https://www.coles.com.au/_next/data/{build}/en/search/products.json"
           f"?q={urllib.parse.quote(term)}")
    try:
        data = json.loads(_get(url))
    except Exception as e:
        return {"term": term, "error": str(e)}
    results = (data.get("pageProps", {}).get("searchResults", {}).get("results") or [])
    products = [p for p in results if isinstance(p, dict) and p.get("_type") == "PRODUCT"]
    products = products[:TOP_N]

    best = None
    for p in products:
        pr = p.get("pricing") or {}
        now = pr.get("now")
        if now is None:
            continue
        was = pr.get("was") or 0
        cand = {
            "name": p.get("name"),
            "now": now,
            "was": was if was and was > now else None,
            "unit": pr.get("comparable"),
            "special": bool(pr.get("specialType")),
        }
        if best is None or cand["now"] < best["now"]:
            best = cand

    if best is None:
        return {"term": term, "found": False}

    was, now = best["was"], best["now"]
    disc = round(1 - now / was, 3) if was else 0.0
    best.update({
        "term": term,
        "found": True,
        "discount": disc,
        "on_special": disc >= SPECIAL_MIN or best["special"],
        "half_price": bool(was) and now <= HALF_PRICE * was + 1e-9,
    })
    return best


def main():
    meals = json.load(open(os.path.join(HERE, "meals.json"), encoding="utf-8"))["meals"]

    # unique ingredient terms across every meal
    terms = sorted({ing for m in meals for ing in m["ingredients"]})
    print(f"Resolving {len(terms)} ingredients across {len(meals)} meals against live Coles...\n")

    build = get_build_id()
    print(f"Coles buildId: {build}\n")

    prices = {}
    for n, term in enumerate(terms, 1):
        prices[term] = search(term, build)
        p = prices[term]
        if p.get("found"):
            tag = "HALF PRICE" if p["half_price"] else ("special" if p["on_special"] else "")
            print(f"  [{n:2}/{len(terms)}] {term:28} ${p['now']:<6} {tag}")
        else:
            print(f"  [{n:2}/{len(terms)}] {term:28} (no match)")
        time.sleep(0.25)  # polite throttle

    # ---- per-meal value scoring ----
    scored = []
    for m in meals:
        ings = [prices[i] for i in m["ingredients"] if prices.get(i, {}).get("found")]
        cost = round(sum(i["now"] for i in ings), 2)
        specials = [i for i in ings if i["on_special"]]
        halves = [i for i in ings if i["half_price"]]
        scored.append({
            "id": m["id"], "name": m["name"], "emoji": m.get("emoji", ""),
            "theme": m["theme"], "cost": cost,
            "n_special": len(specials), "n_half": len(halves),
            "special_items": [i["term"] for i in specials],
        })
    scored.sort(key=lambda s: (s["n_half"], s["n_special"], -s["cost"]), reverse=True)

    # ---- report ----
    on_special = sorted([p for p in prices.values() if p.get("on_special")],
                        key=lambda p: -p["discount"])
    print(f"\n{'='*60}\nON SPECIAL THIS WEEK ({len(on_special)} ingredients)\n{'='*60}")
    for p in on_special:
        was = f"was ${p['was']}" if p["was"] else ""
        flag = "  <-- HALF PRICE" if p["half_price"] else ""
        print(f"  {int(p['discount']*100):>3}% off  {p['term']:26} ${p['now']:<6} {was}{flag}")

    print(f"\n{'='*60}\nBEST-VALUE DINNERS THIS WEEK\n{'='*60}")
    for s in scored[:8]:
        note = f"{s['n_half']} half-price, {s['n_special']} on special" if s["n_special"] else "nothing on special"
        print(f"  {s['emoji']} {s['name']:34} ~${s['cost']:<6} ({note})")
        if s["special_items"]:
            print(f"       cheap: {', '.join(s['special_items'])}")

    # ---- persist snapshot for history / cycle-learning ----
    today = datetime.date.today().isoformat()
    os.makedirs(os.path.join(HERE, "prices"), exist_ok=True)
    snapshot = {"date": today, "build": build, "prices": prices, "meals": scored}
    for path in (os.path.join(HERE, "prices", f"{today}.json"),
                 os.path.join(HERE, "prices", "latest.json")):
        json.dump(snapshot, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nSaved snapshot -> prices/{today}.json")


if __name__ == "__main__":
    main()
