"""Family Dinners — desktop window over the weekly Coles meal planner.

GUI (default):  python app.py
CLI:
    python app.py --refresh    # headless: pull live Coles prices + rebuild the plan
    python app.py --publish    # push the current plan to GitHub Pages (parents see it)
    python app.py --open       # open the last-built plan in a browser
    python app.py --repo "C:\\path\\to\\family-dinners"

The window shows the last-built plan instantly. "Refresh prices" re-runs the repo's
own collector + build_site (live Coles), and "Send to family" publishes it. Both reuse
the exact scripts the weekly job uses - the app is just a friendly front door.

Package to a single .exe with:  python build.py
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

DEFAULT_REPO = r"C:\Users\ryant\OneDrive\Documents\Quant Trading\family-dinners"
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# --------------------------------------------------------------------------- #
# Locating the project + running its scripts
# --------------------------------------------------------------------------- #
def repo_root() -> Path:
    env = os.environ.get("FAMILY_DINNERS_ROOT")
    if env and (Path(env) / "meals.json").exists():
        return Path(env)
    here = Path(__file__).resolve().parent          # running from the repo (dev)
    if (here / "meals.json").exists():
        return here
    return Path(DEFAULT_REPO)


def docs_index() -> Path:
    return repo_root() / "docs" / "index.html"


def _run_repo_scripts(names) -> None:
    """Import the repo's stdlib scripts from disk and run their main() in-process."""
    import importlib
    root = str(repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    for name in names:
        importlib.import_module(name).main()


def refresh() -> dict:
    """Pull live Coles prices and rebuild the plan. Never raises."""
    try:
        _run_repo_scripts(["collector", "build_site"])
        return {"ok": True, "message": "Updated with this week's Coles prices."}
    except Exception as exc:  # Coles throttle / offline / etc.
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


def publish() -> dict:
    """Commit + push the current plan so the family's page updates. Never raises."""
    root = str(repo_root())

    def git(*args):
        return subprocess.run(["git", *args], cwd=root, capture_output=True,
                              text=True, creationflags=_NO_WINDOW)
    try:
        git("add", "prices", "docs")
        c = git("commit", "-m", "Manual refresh from the Family Dinners app")
        if "nothing to commit" in (c.stdout + c.stderr).lower():
            return {"ok": True, "message": "Already up to date — nothing new to send."}
        p = git("push")
        if p.returncode == 0:
            return {"ok": True, "message": "Sent to the family page \u2713"}
        return {"ok": False, "message": "Push failed: " + (p.stderr.strip()[:200] or "unknown")}
    except FileNotFoundError:
        return {"ok": False, "message": "git not found on PATH."}
    except Exception as exc:
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Family Dinners</title>
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif}
  .bar{display:flex;gap:10px;align-items:center;padding:10px 14px;background:#e8241c;color:#fff}
  .bar b{font-size:16px;margin-right:6px}
  .btn{background:#fff;color:#e8241c;border:none;border-radius:9px;padding:9px 14px;
    font:14px inherit;font-weight:700;cursor:pointer}
  .btn.ghost{background:transparent;color:#fff;border:2px solid rgba(255,255,255,.7)}
  .btn:hover{opacity:.9}
  .status{font-size:13px;opacity:.95;margin-left:auto}
  iframe{border:0;width:100%;height:calc(100vh - 52px);display:block}
</style></head>
<body>
  <div class="bar">
    <b>🍽️ Family Dinners</b>
    <button class="btn" onclick="refresh()">↻ Refresh prices</button>
    <button class="btn ghost" onclick="publish()">📤 Send to family</button>
    <span class="status" id="status">this week's plan</span>
  </div>
  <iframe id="page" src="index.html"></iframe>
<script>
  const S = t => document.getElementById('status').textContent = t;
  async function refresh(){
    S('Fetching live Coles prices… (about a minute)');
    const r = await window.pywebview.api.refresh();
    if(r.ok){ document.getElementById('page').contentWindow.location.reload(); S('Updated just now'); }
    else S('Could not refresh — ' + r.message);
  }
  async function publish(){
    S('Publishing to the family page…');
    const r = await window.pywebview.api.publish();
    S(r.message);
  }
</script>
</body></html>"""


class Api:
    def refresh(self):
        return refresh()

    def publish(self):
        return publish()


def run_gui() -> None:
    try:
        import webview
    except ImportError:
        print("pywebview is not installed:  pip install pywebview\n"
              "…or use the CLI:  python app.py --refresh")
        sys.exit(1)

    docs = repo_root() / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    # write the app shell NEXT TO index.html so the iframe is same-origin (gitignored)
    shell_path = docs / "_app.html"
    shell_path.write_text(SHELL, encoding="utf-8")

    if not (docs / "index.html").exists():
        (docs / "index.html").write_text(
            "<p style='font:20px sans-serif;padding:24px'>No plan yet — "
            "click <b>Refresh prices</b> to build this week's dinners.</p>", encoding="utf-8")

    webview.create_window("Family Dinners", url=shell_path.as_uri(), js_api=Api(),
                          width=1000, height=840, min_size=(680, 560))
    webview.start()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--refresh", action="store_true", help="pull live Coles prices + rebuild")
    p.add_argument("--publish", action="store_true", help="push the current plan to GitHub Pages")
    p.add_argument("--open", action="store_true", help="open the last-built plan in a browser")
    p.add_argument("--repo", default=None, help="override the family-dinners repo path")
    args = p.parse_args()

    if args.repo:
        os.environ["FAMILY_DINNERS_ROOT"] = args.repo

    if args.open:
        idx = docs_index()
        if not idx.exists():
            print("No plan built yet — run --refresh first.")
            return
        print(f"Opening {idx}")
        webbrowser.open(idx.resolve().as_uri())
    elif args.refresh:
        r = refresh()
        print(r["message"])
        sys.exit(0 if r["ok"] else 1)
    elif args.publish:
        r = publish()
        print(r["message"])
        sys.exit(0 if r["ok"] else 1)
    else:
        run_gui()


if __name__ == "__main__":
    main()
