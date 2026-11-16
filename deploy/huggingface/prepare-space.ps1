# Builds the folder that is uploaded to a Hugging Face Docker Space: the project code (no secrets, no local
# databases) plus the imaging data the running app reads. Output: output\hf-space (git-ignored). Safe to run again.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$out = Join-Path $root "output\hf-space"

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null

# 1. Code: tracked files plus new, not-ignored files (so an uncommitted Dockerfile is included). Never .claude or .env.
Push-Location $root
$files = git ls-files --cached --others --exclude-standard | Where-Object {
  $_ -notmatch '^\.claude/' -and $_ -notmatch '(^|/)\.env$' -and $_ -notmatch '^docs/' -and $_ -notmatch '^backend/tests/' -and $_ -notmatch '^backend/eval/'
}
Pop-Location
foreach ($f in $files) {
  $src = Join-Path $root $f
  if (-not (Test-Path $src -PathType Leaf)) { continue }
  $dst = Join-Path $out $f
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $src $dst
}

# 2. Imaging data the app reads at run time (about 700 MB). Left out: native test imports, verification
#    screenshots, segmentation inputs and the OASIS-1 source folder.
$img = Join-Path $root "backend\imaging_data"
$dimg = Join-Path $out "backend\imaging_data"
robocopy (Join-Path $img "OAS1_0001_MR1\assets") (Join-Path $dimg "OAS1_0001_MR1\assets") /E /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy (Join-Path $img "agent_analysis") (Join-Path $dimg "agent_analysis") /E /NFL /NDL /NJH /NJS /NP | Out-Null
robocopy (Join-Path $img "oasis2") (Join-Path $dimg "oasis2") /E /XD segmentation_inputs /XF *.err *.log /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copying imaging data failed (robocopy code $LASTEXITCODE)" }

# 3. Space card (Hugging Face reads its settings from README.md) and a .gitignore that keeps the imaging data.
Copy-Item (Join-Path $PSScriptRoot "SPACE_README.md") (Join-Path $out "README.md") -Force
@"
__pycache__/
*.pyc
.env
*.db
frontend/node_modules/
frontend/dist/
"@ | Set-Content -Encoding utf8 (Join-Path $out ".gitignore")

# 4. Safety check: no secrets or databases in the folder.
$bad = Get-ChildItem -Recurse -Force $out -File | Where-Object { $_.Name -eq ".env" -or $_.Extension -eq ".db" }
if ($bad) { throw "Refusing: found $($bad.FullName -join ', ')" }

$size = (Get-ChildItem -Recurse -Force $out -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Space folder ready: {0}  ({1:N0} MB)" -f $out, $size) -ForegroundColor Cyan
exit 0   # robocopy leaves a non-zero "files copied" code behind
