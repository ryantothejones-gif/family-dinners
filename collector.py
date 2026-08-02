"""
family-dinners collector
-------------------------
Resolves every ingredient in meals.json to a live Coles price, flags specials /
half-prices, and scores which dinners are cheapest this week.

Product selection: the most-relevant search hit whose name actually contains the
ingredient's head noun (so "sour cream" -> sour cream, not potato chips; "beef mince"
-> mince, not a bulk tray). This is deterministic, so it tracks the same product each
week for honest half-price cycle detection. An optional pins.json can override the
choice for specific ingredients (see pin_ingredients.py).

Stdlib only (urllib + json) so it runs on any machine with Python, no pip install.
Coles catalogue changes Tuesday night (live Wednesday); run each Wednesday morning.
"""
import json, sys, time, urllib.request, urllib.parse, datetime, os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 safety

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
# Localise prices to the family's Coles store. 0490 = Coles Gateway, Success WA
# (region c-wa-met) — verified via the public store picker to change real prices
# (e.g. carrots $1.50 here vs $2.40 default). Override with COLES_STORE_ID.
STORE_ID = os.environ.get("COLES_STORE_ID") or "0490"
SHOPPING_METHOD = os.environ.get("COLES_SHOPPING_METHOD") or "clickAndCollect"
HALF_PRICE = 0.50        # now <= 50% of was
SPECIAL_MIN = 0.15       # >=15% off counts as "on special"


def _get(url, tries=6, store=None):
    last = None
    headers = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-AU,en;q=0.9"}
    sid = store or STORE_ID
    if sid:  # localise pricing to the given store (carried by a cookie)
        headers["Cookie"] = f"fulfillmentStoreId={sid}; shopping-method={SHOPPING_METHOD}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def get_build_id(tries=6, store=None):
    """Coles occasionally serves a bot-challenge stub even to residential IPs; retry."""
    for i in range(tries):
        html = _get("https://www.coles.com.au/", store=store)
        if '"buildId":"' in html:
            return html.split('"buildId":"')[1].split('"')[0]
        time.sleep(3 * (i + 1))
    raise RuntimeError("Coles not serving real page (no buildId after retries)")


def head_noun(term):
    return term.split()[-1].lower().rstrip("s")


def qty_of(ing):
    parts = ing.rsplit(" x", 1)
    return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1


def term_of(ing):
    parts = ing.rsplit(" x", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else ing


def search(term, build, pins, store=None):
    url = (f"https://www.coles.com.au/_next/data/{build}/en/search/products.json"
           f"?q={urllib.parse.quote(term)}")
    try:
        data = json.loads(_get(url, store=store))
    except Exception as e:
        return {"term": term, "found": False, "error": str(e)}
    results = (data.get("pageProps", {}).get("searchResults", {}).get("results") or [])
    products = [p for p in results if isinstance(p, dict) and p.get("_type") == "PRODUCT"
                and (p.get("pricing") or {}).get("now") is not None]
    if not products:
        return {"term": term, "found": False}

    chosen = None
    if term in pins:                                   # manual override by product id
        pid = str(pins[term].get("id"))
        chosen = next((p for p in products if str(p.get("id")) == pid), None)
    if chosen is None:                                 # relevance + head-noun match
        head = head_noun(term)
        chosen = next((p for p in products if head in (p.get("name") or "").lower()), None)
    if chosen is None:
        chosen = products[0]

    pr = chosen["pricing"]
    now = pr["now"]
    was = pr.get("was") if (pr.get("was") and pr["was"] > now) else None
    disc = round(1 - now / was, 3) if was else 0.0
    # exact Coles product photo = assetsUrl + the product's image uri (fail-soft)
    assets = data.get("pageProps", {}).get("assetsUrl") or ""
    uris = chosen.get("imageUris") or []
    uri = uris[0].get("uri") if (uris and isinstance(uris[0], dict)) else None
    image = (assets + uri) if (assets and uri) else None
    return {
        "term": term, "found": True, "id": str(chosen.get("id")),
        "name": chosen.get("name"), "size": chosen.get("size"), "image": image,
        "now": now, "was": was, "unit": pr.get("comparable"),
        "discount": disc,
        "on_special": (disc >= SPECIAL_MIN),           # honest: needs a real was-price
        "half_price": bool(was) and now <= HALF_PRICE * was + 1e-9,
    }


def main():
    meals = json.load(open(os.path.join(HERE, "meals.json"), encoding="utf-8"))["meals"]
    pins_path = os.path.join(HERE, "pins.json")
    pins = json.load(open(pins_path, encoding="utf-8")) if os.path.exists(pins_path) else {}

    terms = sorted({term_of(i) for m in meals for i in m["ingredients"]})
    print(f"Resolving {len(terms)} ingredients across {len(meals)} meals against live Coles...\n")

    build = get_build_id()
    print(f"Coles buildId: {build}\n")

    prices = {}
    for n, term in enumerate(terms, 1):
        prices[term] = search(term, build, pins)
        p = prices[term]
        if p.get("found"):
            tag = "HALF PRICE" if p["half_price"] else ("special" if p["on_special"] else "")
            print(f"  [{n:2}/{len(terms)}] {term:26} ${p['now']:<6} {str(p.get('size') or ''):8} {tag}")
        else:
            print(f"  [{n:2}/{len(terms)}] {term:26} (no match)")
        time.sleep(0.3)

    # ---- per-meal value scoring (quantity-aware) ----
    scored = []
    for m in meals:
        cost, specials, halves = 0.0, [], []
        for ing in m["ingredients"]:
            p = prices.get(term_of(ing), {})
            if not p.get("found"):
                continue
            cost += p["now"] * qty_of(ing)
            if p["half_price"]:
                halves.append(term_of(ing))
            elif p["on_special"]:
                specials.append(term_of(ing))
        scored.append({"id": m["id"], "name": m["name"], "emoji": m.get("emoji", ""),
                       "theme": m["theme"], "cost": round(cost, 2),
                       "n_special": len(specials) + len(halves), "n_half": len(halves),
                       "special_items": halves + specials})
    scored.sort(key=lambda s: (s["n_half"], s["n_special"], -s["cost"]), reverse=True)

    # ---- report ----
    on_special = sorted([p for p in prices.values() if p.get("found") and p["on_special"]],
                        key=lambda p: -p["discount"])
    print(f"\n{'='*60}\nON SPECIAL THIS WEEK ({len(on_special)} ingredients)\n{'='*60}")
    for p in on_special:
        flag = "  <-- HALF PRICE" if p["half_price"] else ""
        print(f"  {int(p['discount']*100):>3}% off  {p['term']:24} ${p['now']:<6} was ${p['was']}{flag}")

    print(f"\n{'='*60}\nBEST-VALUE DINNERS THIS WEEK\n{'='*60}")
    for s in scored[:8]:
        note = f"{s['n_half']} half-price, {s['n_special']} on special" if s["n_special"] else "nothing on special"
        print(f"  {s['emoji']} {s['name']:34} ~${s['cost']:<6} ({note})")

    # ---- persist snapshot (history for cycle-learning) ----
    today = datetime.date.today().isoformat()
    os.makedirs(os.path.join(HERE, "prices"), exist_ok=True)
    snapshot = {"date": today, "build": build, "prices": prices, "meals": scored}
    for path in (os.path.join(HERE, "prices", f"{today}.json"),
                 os.path.join(HERE, "prices", "latest.json")):
        json.dump(snapshot, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nSaved snapshot -> prices/{today}.json")


if __name__ == "__main__":
    main()
