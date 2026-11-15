# Local, single-research-case preview. The selected demo account is explicitly authorized.
$ErrorActionPreference = "Stop"
$env:NEUROTWIN_IMAGING_USERS = "demo-dr-layla"
$env:NEUROTWIN_SEED_HISTORY = "1"   # adds six months of synthetic demonstration history to the demo people; safe to repeat
& (Join-Path $PSScriptRoot "start.ps1") -Port 8001 -Imaging
