"""
Build the parent-facing static page from the latest price snapshot.

Reads meals.json + prices/latest.json, picks a varied weekly plan that favours
meals with ingredients on special, and emits a self-contained docs/index.html
(inline CSS/JS) served by GitHub Pages from /docs.

Design targets: large text, high contrast, big tap targets, one combined shopping
list (quantity-aware, shows "x2"), a Print button, one-tap swaps. Each meal shows a
real photo if docs/img/<meal-id>.(jpg|jpeg|png|webp) exists, otherwise a big icon tile.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_SIZE = 6
MAX_PER_THEME = 2
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def qty_of(ing):
    parts = ing.rsplit(" x", 1)
    return int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 1


def term_of(ing):
    parts = ing.rsplit(" x", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else ing


def photo_for(meal_id):
    for ext in IMG_EXTS:
        if os.path.exists(os.path.join(HERE, "docs", "img", meal_id + ext)):
            return f"img/{meal_id}{ext}"
    return None


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
                         "special": bool(p.get("on_special")), "half": bool(p.get("half_price"))})
            cost += p["now"] * qty
        out.append({
            "id": m["id"], "name": m["name"], "emoji": m.get("emoji", ""),
            "theme": m["theme"], "cost": round(cost, 2), "ingredients": ings,
            "photo": photo_for(m["id"]),
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
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(240px,1fr)); gap:16px; }
  .card { background:var(--bg); border:2px solid var(--line); border-radius:18px;
          overflow:hidden; display:flex; flex-direction:column; }
  .tile { height:150px; display:flex; align-items:center; justify-content:center; }
  .tile img { width:100%; height:100%; object-fit:cover; display:block; }
  .emoji { font-size:4.4rem; line-height:1; filter:drop-shadow(0 2px 2px rgba(0,0,0,.15)); }
  .body { padding:14px 16px 16px; text-align:center; display:flex; flex-direction:column; flex:1; }
  .mname { font-weight:700; font-size:1.2rem; margin:2px 0 4px; }
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
  .row.done label { text-decoration:line-through; color:#999; }
  .item { flex:1; font-size:1.15rem; }
  .qty { font-weight:700; color:var(--red); }
  .price { color:#444; font-variant-numeric:tabular-nums; }
  .tag { font-size:.8rem; font-weight:700; padding:2px 8px; border-radius:999px; background:var(--green-bg); color:var(--green); }
  .tag.half { background:var(--half-bg); color:var(--half); }
  .total { text-align:right; font-size:1.2rem; font-weight:700; padding:12px; }
  .actions { position:sticky; bottom:0; background:#f4f4f4; padding:14px 0 4px; }
  @media print {
    body { background:#fff; font-size:14pt; }
    .grid, .swap, .actions, .sub, .noprint { display:none !important; }
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
const THEME_BG = {Pasta:'#fff1e6',Curry:'#fdeede',Pizza:'#ffeaea',Schnitzel:'#fdf6e3',
  Wraps:'#eef7ee',Stroganoff:'#f0eef8','Stir Fry':'#eaf4f7',Roast:'#f6efe8',BBQ:'#fdeeea',Soup:'#eef4ee'};

function tile(m) {
  if (m.photo) return `<div class="tile"><img src="${m.photo}" alt="${m.name}"></div>`;
  return `<div class="tile" style="background:${THEME_BG[m.theme]||'#f2efe9'}"><div class="emoji">${m.emoji}</div></div>`;
}

function render() {
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  plan.forEach((id, i) => {
    const m = byId[id];
    const pill = m.n_half ? `<span class="pill half">½ price: ${m.n_half}</span>`
              : m.n_special ? `<span class="pill">${m.n_special} on special</span>` : '';
    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = tile(m) + `<div class="body">
      <div class="mname">${m.name}</div>
      <div class="mcost">about $${m.cost.toFixed(2)}</div>
      ${pill}
      <div class="swap"><button onclick="swap(${i})">🔁 Swap</button></div></div>`;
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
    const row = document.createElement('div');
    row.className = 'row';
    const id = 'c' + n;
    row.innerHTML = `<input type="checkbox" id="${id}" onchange="this.closest('.row').classList.toggle('done', this.checked)">
      <label class="item" for="${id}">${q}${ing.term} ${tag}</label>
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
    print("Photos present:", sum(1 for m in meals if m["photo"]), "/", len(meals))


if __name__ == "__main__":
    main()
