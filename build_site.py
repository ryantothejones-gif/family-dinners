"""
Build the parent-facing static page from the latest price snapshot.

Reads meals.json + prices/latest.json, picks a varied weekly plan that favours
meals with ingredients on special, and emits a self-contained docs/index.html
(inline CSS/JS) served by GitHub Pages from /docs.

Design targets: large text, high contrast, big tap targets, one combined shopping
list that shows the exact product + size to grab (quantity-aware, "x2"), a Print
button, and one-tap swaps.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_SIZE = 6
MAX_PER_THEME = 2


def qty_of(ing):
    parts = ing.rsplit(" x", 1)
    return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1


def term_of(ing):
    parts = ing.rsplit(" x", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else ing


def load():
    meals = json.load(open(os.path.join(HERE, "meals.json"), encoding="utf-8"))["meals"]
    snap = json.load(open(os.path.join(HERE, "prices", "latest.json"), encoding="utf-8"))
    prices = snap["prices"]

    out = []
    for m in meals:
        ings, cost = [], 0.0
        for ing in m["ingredients"]:
            term, qty = term_of(ing), qty_of(ing)
            p = prices.get(term, {})
            if not p.get("found"):
                continue
            ings.append({"term": term, "now": p["now"], "qty": qty,
                         "name": p.get("name") or "", "size": p.get("size") or "",
                         "image": p.get("image") or "",
                         "special": bool(p.get("on_special")), "half": bool(p.get("half_price"))})
            cost += p["now"] * qty
        out.append({
            "id": m["id"], "name": m["name"], "emoji": m.get("emoji", ""),
            "theme": m["theme"], "cost": round(cost, 2), "ingredients": ings,
            "n_half": sum(i["half"] for i in ings),
            "n_special": sum(i["special"] or i["half"] for i in ings),
        })
    return out, snap.get("date", "")


def pick_plan(meals):
    ranked = sorted(meals, key=lambda m: (m["n_half"], m["n_special"], -m["cost"]), reverse=True)
    plan, theme_count = [], {}
    for m in ranked:
        if len(plan) >= PLAN_SIZE:
            break
        if theme_count.get(m["theme"], 0) < MAX_PER_THEME:
            plan.append(m["id"])
            theme_count[m["theme"]] = theme_count.get(m["theme"], 0) + 1
    return plan


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#e8241c">
<title>This Week's Dinners</title>
<link rel="apple-touch-icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E%F0%9F%8D%BD%EF%B8%8F%3C/text%3E%3C/svg%3E">
<style>
  :root { --ink:#1a1a1a; --bg:#fff; --line:#d9d9d9; --red:#e8241c;
          --green:#0a7d33; --green-bg:#e3f5e8; --half:#b3000f; --half-bg:#ffe3e3; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;
         color:var(--ink); background:#f4f4f4; font-size:20px; line-height:1.4; }
  .wrap { max-width:860px; margin:0 auto; padding:18px 16px 60px; }
  header { text-align:center; margin:8px 0 20px; }
  h1 { font-size:2.1rem; margin:.2em 0; }
  .sub { color:#555; font-size:1rem; }
  h2 { font-size:1.5rem; border-bottom:3px solid var(--line); padding-bottom:6px; margin-top:34px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:14px; }
  .card { background:var(--bg); border:2px solid var(--line); border-radius:16px;
          padding:18px 16px; text-align:center; display:flex; flex-direction:column; }
  .mname { font-weight:700; font-size:1.25rem; margin:0 0 6px; }
  .mname .e { font-size:1.5rem; margin-right:4px; }
  .mcost { color:#444; }
  .pill { display:inline-block; margin-top:8px; padding:4px 12px; border-radius:999px;
          font-size:.9rem; font-weight:700; background:var(--green-bg); color:var(--green); }
  .pill.half { background:var(--half-bg); color:var(--half); }
  .swap { margin-top:auto; padding-top:12px; }
  button { font-size:1rem; font-weight:700; border-radius:12px; border:2px solid var(--line);
           background:#fafafa; color:var(--ink); padding:12px 14px; cursor:pointer; min-height:52px; width:100%; }
  button:hover { background:#eee; }
  .primary { background:var(--red); color:#fff; border-color:var(--red); font-size:1.15rem; }
  .list { background:var(--bg); border:2px solid var(--line); border-radius:16px; padding:8px 6px; }
  .row { display:flex; align-items:center; gap:14px; padding:14px 12px; border-bottom:1px solid #eee; }
  .row:last-child { border-bottom:0; }
  .row input { width:30px; height:30px; flex:0 0 auto; }
  .row.done .item { text-decoration:line-through; color:#999; }
  .thumb { width:52px; height:52px; flex:0 0 auto; object-fit:contain;
           background:#fff; border:1px solid #eee; border-radius:8px; }
  .thumb.noimg { border-style:dashed; background:#fafafa; }
  .item { flex:1; }
  .line { font-size:1.15rem; }
  .qty { font-weight:700; color:var(--red); }
  .brand { display:block; font-size:.82rem; color:#777; margin-top:2px; }
  .price { color:#444; font-variant-numeric:tabular-nums; font-weight:600; }
  .tag { font-size:.8rem; font-weight:700; padding:2px 8px; border-radius:999px; background:var(--green-bg); color:var(--green); }
  .tag.half { background:var(--half-bg); color:var(--half); }
  .total { text-align:right; font-size:1.2rem; font-weight:700; padding:12px; }
  .actions { position:sticky; bottom:0; background:#f4f4f4; padding:14px 0 4px; }
  @media print {
    body { background:#fff; font-size:14pt; }
    .grid, .swap, .actions, .sub, .noprint, .thumb { display:none !important; }
    h2 { margin-top:0; }
    .row input { width:16px; height:16px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>🍽️ This Week's Dinners</h1>
    <div class="sub">Prices from Coles · updated __DATE__ · tap <b>Swap</b> to change a meal</div>
  </header>

  <div id="cards" class="grid"></div>

  <h2>🛒 Your Shopping List</h2>
  <div id="list" class="list"></div>
  <div id="total" class="total"></div>

  <div class="actions">
    <button class="primary" onclick="window.print()">🖨️ Print this list</button>
  </div>
</div>

<script>
const MEALS = __MEALS__;
let plan = __PLAN__;
const byId = Object.fromEntries(MEALS.map(m => [m.id, m]));

function render() {
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  plan.forEach((id, i) => {
    const m = byId[id];
    const pill = m.n_half ? `<span class="pill half">½ price: ${m.n_half}</span>`
              : m.n_special ? `<span class="pill">${m.n_special} on special</span>` : '';
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `<div class="mname"><span class="e">${m.emoji}</span>${m.name}</div>
      <div class="mcost">about $${m.cost.toFixed(2)}</div>
      ${pill}
      <div class="swap"><button onclick="swap(${i})">🔁 Swap</button></div>`;
    cards.appendChild(el);
  });
  renderList();
}

function renderList() {
  const seen = {};
  plan.forEach(id => byId[id].ingredients.forEach(ing => {
    if (seen[ing.term]) seen[ing.term].qty += ing.qty;
    else seen[ing.term] = {...ing};
  }));
  const items = Object.values(seen).sort((a, b) =>
    (b.half - a.half) || (b.special - a.special) || a.term.localeCompare(b.term));

  const list = document.getElementById('list');
  list.innerHTML = '';
  let total = 0;
  items.forEach((ing, n) => {
    total += ing.now * ing.qty;
    const tag = ing.half ? '<span class="tag half">½ PRICE</span>'
             : ing.special ? '<span class="tag">SPECIAL</span>' : '';
    const q = ing.qty > 1 ? `<span class="qty">×${ing.qty}</span> ` : '';
    const brand = ing.name ? `<span class="brand">${ing.name}${ing.size ? ' · ' + ing.size : ''}</span>` : '';
    const thumb = ing.image
      ? `<img class="thumb" src="${ing.image}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`
      : `<span class="thumb noimg"></span>`;
    const row = document.createElement('div');
    row.className = 'row';
    const id = 'c' + n;
    row.innerHTML = `<input type="checkbox" id="${id}" onchange="this.closest('.row').classList.toggle('done', this.checked)">
      ${thumb}
      <label class="item" for="${id}"><span class="line">${q}${ing.term} ${tag}</span>${brand}</label>
      <span class="price">$${(ing.now * ing.qty).toFixed(2)}</span>`;
    list.appendChild(row);
  });
  document.getElementById('total').textContent =
    `Estimated total: $${total.toFixed(2)}  (${items.length} items)`;
}

function swap(i) {
  const cur = byId[plan[i]];
  const options = MEALS.filter(m => m.theme === cur.theme && !plan.includes(m.id));
  if (!options.length) return;
  options.sort((a, b) => (b.n_half - a.n_half) || (b.n_special - a.n_special));
  plan[i] = options[0].id;
  render();
}

render();
</script>
</body>
</html>
"""


def main():
    meals, date = load()
    plan = pick_plan(meals)
    if not date:
        date = datetime.date.today().isoformat()
    html = (HTML.replace("__MEALS__", json.dumps(meals, ensure_ascii=False))
                .replace("__PLAN__", json.dumps(plan))
                .replace("__DATE__", date))
    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    path = os.path.join(HERE, "docs", "index.html")
    open(path, "w", encoding="utf-8").write(html)
    idx = {m["id"]: m for m in meals}
    print(f"Built {path}")
    print("This week's plan:", ", ".join(idx[i]["name"] for i in plan))


if __name__ == "__main__":
    main()
