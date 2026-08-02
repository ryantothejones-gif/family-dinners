"""
Generate pins.json: a stable, sensible representative Coles product per ingredient.

Run this once (and again whenever you add ingredients). It searches each ingredient
and picks the MEDIAN-priced product among the top relevance hits - which skips both
the odd cheap blends and the bulk trays, landing on a normal family pack. The result
is human-editable: pins.json shows name + size so you (Coles expert) can swap any id.

The weekly collector then tracks THAT exact product every week -> consistent prices
and reliable half-price cycle detection.

Stdlib only.  Usage:
  python pin_ingredients.py            # fill pins for any ingredient not yet pinned
  python pin_ingredients.py --all      # re-pin everything from scratch
  python pin_ingredients.py --relist "beef mince"   # show candidate products for a term
"""
import urllib.request, urllib.parse, json, sys, time, os

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TOP_N = 8


def _get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                                       "Accept-Language": "en-AU,en;q=0.9"})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(2 + 2 * i)
    raise last


def build_id():
    html = _get("https://www.coles.com.au/")
    if '"buildId":"' not in html:
        raise RuntimeError("Coles not serving real page (no buildId)")
    return html.split('"buildId":"')[1].split('"')[0]


def candidates(term, build):
    url = (f"https://www.coles.com.au/_next/data/{build}/en/search/products.json"
           f"?q={urllib.parse.quote(term)}")
    data = json.loads(_get(url))
    res = (data.get("pageProps", {}).get("searchResults", {}).get("results") or [])
    out = []
    for p in res:
        if p.get("_type") != "PRODUCT":
            continue
        pr = p.get("pricing") or {}
        if pr.get("now") is None:
            continue
        out.append({"id": str(p.get("id")), "name": p.get("name"),
                    "size": p.get("size"), "price": pr.get("now")})
    return out


def pick(cands, term):
    """Most-relevant product whose name actually contains the head noun of the term.

    Coles ranks the real staple first, but keyword search also returns tangential hits
    (dips, snacks, breads). Requiring the head noun ('onion', 'cream', 'mince') in the
    name skips those, so 'sour cream' lands on sour cream, not potato chips.
    """
    if not cands:
        return None
    head = term.split()[-1].lower().rstrip("s")  # 'onions' ~ 'onion'
    for c in cands:                               # relevance order
        if head in (c["name"] or "").lower():
            return c
    return cands[0]


def main():
    args = sys.argv[1:]
    if args and args[0] == "--relist":
        term = args[1]
        for c in candidates(term, build_id())[:TOP_N]:
            print(f"  {c['id']} | {(c['name'] or '')[:40]:40} | ${c['price']} | {c['size']}")
        return

    repin_all = "--all" in args
    meals = json.load(open(os.path.join(HERE, "meals.json"), encoding="utf-8"))["meals"]
    # strip any "xN" quantity suffix to get the search term
    def term_of(ing):
        return ing.rsplit(" x", 1)[0] if " x" in ing and ing.rsplit(" x", 1)[1].isdigit() else ing
    terms = sorted({term_of(i) for m in meals for i in m["ingredients"]})

    pins_path = os.path.join(HERE, "pins.json")
    pins = {} if repin_all or not os.path.exists(pins_path) else json.load(open(pins_path, encoding="utf-8"))

    build = build_id()
    print(f"Pinning {len(terms)} ingredients (buildId {build[:12]}...)\n")
    for n, term in enumerate(terms, 1):
        if term in pins and not repin_all:
            continue
        try:
            best = pick(candidates(term, build), term)
        except Exception as e:
            print(f"  [{n:2}] {term:26} ERROR {e}")
            continue
        if best:
            pins[term] = best
            print(f"  [{n:2}] {term:26} -> {(best['name'] or '')[:34]:34} {str(best['size'] or ''):7} ${best['price']} (id {best['id']})")
        else:
            print(f"  [{n:2}] {term:26} (no product found)")
        time.sleep(0.4)

    json.dump(pins, open(pins_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote {len(pins)} pins -> pins.json  (edit any id by hand; --relist <term> shows options)")


if __name__ == "__main__":
    main()
