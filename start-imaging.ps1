# Local, single-research-case preview. The selected demo account is explicitly authorized.
$ErrorActionPreference = "Stop"
$env:NEUROTWIN_IMAGING_USERS = "demo-dr-layla"
& (Join-Path $PSScriptRoot "start.ps1") -Port 8001 -Imaging
