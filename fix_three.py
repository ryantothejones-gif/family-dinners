"""One-off: pin better products for the 3 ingredients the auto-picker got plausibly-wrong.

Fetches candidates for each term (from that term's OWN search, so the pin is findable on
future runs), logs them all, applies a rule to choose a sensible product, writes the choice
into pins.json, and patches the current snapshot so a rebuild uses it. Gentle: 3 searches.

  beef burger patties -> a BEEF patty (not plant-based)
  chickpeas           -> CANNED chickpeas (not a salted snack)
  white pasta sauce   -> a white/cheese sauce JAR (not an 80g pasta&sauce packet)
"""
import urllib.request, urllib.parse, json, time, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*",
                                                       "Accept-Language": "en-AU,en;q=0.9"})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def build_id(tries=8):
    for i in range(tries):
        h = get("https://www.coles.com.au/")
        if '"buildId":"' in h:
            return h.split('"buildId":"')[1].split('"')[0]
        time.sleep(3 * (i + 1))
    raise RuntimeError("no buildId (throttled)")


def candidates(term, b):
    url = f"https://www.coles.com.au/_next/data/{b}/en/search/products.json?q={urllib.parse.quote(term)}"
    d = json.loads(get(url))
    res = d["pageProps"]["searchResults"]["results"]
    return [p for p in res if p.get("_type") == "PRODUCT" and (p.get("pricing") or {}).get("now") is not None]


def grams(size):
    if not size:
        return 0.0
    m = re.search(r"([\d.]+)\s*(kg|g|l|ml)", size.lower())
    if not m:
        return 0.0
    v, u = float(m.group(1)), m.group(2)
    return v * 1000 if u in ("kg", "l") else v


def record(p, term):
    pr = p["pricing"]
    now = pr["now"]
    was = pr.get("was") if (pr.get("was") and pr["was"] > now) else None
    disc = round(1 - now / was, 3) if was else 0.0
    return {"term": term, "found": True, "id": str(p.get("id")), "name": p.get("name"),
            "size": p.get("size"), "now": now, "was": was, "unit": pr.get("comparable"),
            "discount": disc, "on_special": disc >= 0.15,
            "half_price": bool(was) and now <= 0.5 * was + 1e-9}


def choose(term, cs):
    def nm(p):
        return (p.get("name") or "").lower()
    if term == "beef burger patties":
        for p in cs:
            if "beef" in nm(p) and "patt" in nm(p) and "plant" not in nm(p):
                return p
        for p in cs:
            if "patt" in nm(p) and "plant" not in nm(p):
                return p
    elif term == "chickpeas":
        bad = ("salt", "roast", "snack", "choc", "crisp", "puff", "bbq", "corn")
        for p in cs:
            if "chick" in nm(p) and not any(w in nm(p) for w in bad):
                return p
    elif term == "white pasta sauce":
        pref = ("white", "cheese", "carbonara", "bechamel", "alfredo", "cream")
        for p in cs:
            if "sauce" in nm(p) and grams(p.get("size")) >= 300 and any(w in nm(p) for w in pref):
                return p
        for p in cs:
            if "sauce" in nm(p) and grams(p.get("size")) >= 300:
                return p
    return cs[0] if cs else None


def main():
    b = build_id()
    pins_new, patches = {}, {}
    for term in ["beef burger patties", "chickpeas", "white pasta sauce"]:
        cs = candidates(term, b)
        print(f"\n=== '{term}' candidates ===")
        for p in cs[:12]:
            print(f"  id={p.get('id')} | {(p.get('name') or '')[:46]:46} | {str(p.get('size') or ''):11} | ${p['pricing']['now']}")
        chosen = choose(term, cs)
        if chosen:
            r = record(chosen, term)
            pins_new[term] = {"id": r["id"], "name": r["name"], "size": r["size"]}
            patches[term] = r
            print(f"  -> CHOSE: {chosen.get('name')} | {chosen.get('size')} | id {chosen.get('id')}")
        time.sleep(0.5)

    pins_path = os.path.join(HERE, "pins.json")
    pins = json.load(open(pins_path, encoding="utf-8")) if os.path.exists(pins_path) else {}
    pins.update(pins_new)
    json.dump(pins, open(pins_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    snap = json.load(open(os.path.join(HERE, "prices", "latest.json"), encoding="utf-8"))
    for term, r in patches.items():
        snap["prices"][term] = r
    json.dump(snap, open(os.path.join(HERE, "prices", "latest.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    day = snap.get("date")
    if day:
        json.dump(snap, open(os.path.join(HERE, "prices", f"{day}.json"), "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    print("\nDONE: pinned + patched", list(patches))


if __name__ == "__main__":
    main()
