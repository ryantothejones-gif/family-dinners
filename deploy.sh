#!/usr/bin/env bash
# Weekly job (runs on the VPS via family-dinners.timer, Wednesday morning AWST):
#   pull -> refresh live Coles prices -> rebuild the site -> commit & push.
# GitHub Pages then redeploys docs/ automatically.
set -euo pipefail
cd "$(dirname "$0")"

git pull --ff-only --quiet || true

python3 collector.py
python3 build_site.py

git add prices docs
if git diff --cached --quiet; then
  echo "no changes this run"
else
  git commit -q -m "weekly refresh $(date +%F)" -m "Automated Coles price snapshot + rebuilt plan."
  git push --quiet
  echo "pushed update"
fi
