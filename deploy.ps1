<#
  Deploy the Solar Pi dashboard from this Windows machine.

  Pushes local commits to GitHub, then SSHes into the Pi to pull them and
  restart the service. Requires passwordless (key-based) SSH to the Pi.

  Usage:
    .\deploy.ps1                              # default host: antarctica@solarpi
    .\deploy.ps1 -PiHost antarctica@192.168.3.50
    .\deploy.ps1 -Pip                         # also run pip install (when requirements.txt changed)
#>
param(
  [string]$PiHost = "antarctica@solarpi",
  [string]$PiDir  = "~/solardash",
  [switch]$Pip
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Pushing to GitHub (origin/main)..." -ForegroundColor Cyan
git push origin main

# systemctl --user over a non-interactive SSH needs XDG_RUNTIME_DIR pointed at the user bus.
$pipStep = if ($Pip) { ".venv/bin/pip install -q -r requirements.txt && " } else { "" }
$remote  = "cd $PiDir && git pull --ff-only && ${pipStep}export XDG_RUNTIME_DIR=/run/user/`$(id -u) && systemctl --user restart solardash && sleep 1 && systemctl --user is-active solardash"

Write-Host "==> Deploying on $PiHost ..." -ForegroundColor Cyan
ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 $PiHost $remote
if ($LASTEXITCODE -eq 0) {
  Write-Host "==> Done. Hard-refresh the dashboard in your browser for UI changes." -ForegroundColor Green
} else {
  Write-Error "Remote deploy step failed (exit $LASTEXITCODE)."
}
