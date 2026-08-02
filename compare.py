"""On-demand: compare the family's two Coles stores for the meal ingredients, so you
can decide where to shop. Doesn't touch the weekly page (that stays on Success) - run
this only when you want the comparison.

  python compare.py

Success (0490, Coles Gateway) is the reference: for each ingredient it takes the same
product Success uses, then looks up THAT product's price at South Lake (0333) - a fair
like-for-like compare. Most items are identical (national pricing); fresh produce is
where the two usually differ.
"""
import json
import os
import sys
import time
import urllib.parse

from collector import HERE, get_build_id, search, term_of, _get

SUCCESS = ("0490", "Success")
SOUTH_LAKE = ("0333", "South Lake")


def price_at(term, build, product_id, store):
    """Price of a specific product id at `store` (None if it isn't listed there)."""
    url = (f"https://www.coles.com.au/_next/data/{build}/en/search/products.json"
           f"?q={urllib.parse.quote(term)}")
    try:
        data = json.loads(_get(url, store=store))
    except Exception:
        return None
    for p in (data.get("pageProps", {}).get("searchResults", {}).get("results") or []):
        if p.get("_type") == "PRODUCT" and str(p.get("id")) == str(product_id):
            return (p.get("pricing") or {}).get("now")
    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    meals = json.load(open(os.path.join(HERE, "meals.json"), encoding="utf-8"))["meals"]
    pins_path = os.path.join(HERE, "pins.json")
    pins = json.load(open(pins_path, encoding="utf-8")) if os.path.exists(pins_path) else {}
    terms = sorted({term_of(i) for m in meals for i in m["ingredients"]})

    print(f"Comparing {len(terms)} ingredients: "
          f"{SUCCESS[1]} ({SUCCESS[0]}) vs {SOUTH_LAKE[1]} ({SOUTH_LAKE[0]})\n")
    build = get_build_id(store=SUCCESS[0])

    cheaper_sl, cheaper_su, same = [], [], 0
    tot_su = tot_sl = 0.0
    for n, term in enumerate(terms, 1):
        p = search(term, build, pins, store=SUCCESS[0])   # Success's chosen product
        if not p.get("found"):
            continue
        su = p["now"]
        sl = price_at(term, build, p["id"], SOUTH_LAKE[0])
        time.sleep(0.3)                                    # polite between the two stores
        if sl is None:
            continue
        tot_su += su
        tot_sl += sl
        d = round(su - sl, 2)
        row = (f"  {term:24} {(p.get('name') or '')[:28]:28} "
               f"Success ${su:<6} South Lake ${sl:<6}")
        if d > 0.009:
            cheaper_sl.append((d, row))
        elif d < -0.009:
            cheaper_su.append((-d, row))
        else:
            same += 1

    print(f"{'='*72}\nCHEAPER AT SOUTH LAKE ({len(cheaper_sl)})\n{'='*72}")
    for d, row in sorted(cheaper_sl, reverse=True):
        print(f"{row}  -> save ${d:.2f}")
    print(f"\n{'='*72}\nCHEAPER AT SUCCESS ({len(cheaper_su)})\n{'='*72}")
    for d, row in sorted(cheaper_su, reverse=True):
        print(f"{row}  -> save ${d:.2f}")

    delta = tot_su - tot_sl
    who = "South Lake" if delta > 0 else "Success"
    print(f"\n{same} items identical. Whole-basket: Success ${tot_su:.2f} vs "
          f"South Lake ${tot_sl:.2f}  ->  {who} cheaper by ${abs(delta):.2f}.")


if __name__ == "__main__":
    main()
