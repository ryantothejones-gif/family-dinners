# Weekly refresh for Family Dinners - runs on this PC via a Scheduled Task.
#
# Coles blocks datacenter IPs (a VPS or CI runner gets a ~212-byte Incapsula
# challenge instead of the page), so the fetch MUST come from a residential AU
# connection - i.e. this machine. This script: refresh prices -> rebuild the
# site -> commit & push. GitHub Pages then redeploys docs/.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

try { git pull --ff-only | Out-Null } catch { }

python collector.py
python build_site.py

git add prices docs
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "weekly refresh $(Get-Date -Format 'yyyy-MM-dd')" -m "Automated Coles snapshot + rebuilt plan."
    git push
    Write-Output "pushed update"
} else {
    Write-Output "no changes this run"
}
