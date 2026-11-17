# Builds the folder that is uploaded to a free Hugging Face Space (Gradio SDK): the project code (no secrets, no local
# databases) plus the imaging data the running app reads. Output: output\hf-space (git-ignored). Safe to run again.
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$out = Join-Path $root "output\hf-space"

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null

# 1. Code: tracked files plus new, not-ignored files (so an uncommitted Dockerfile is included). Never .claude or .env.
Push-Location $root
$files = git ls-files --cached --others --exclude-standard | Where-Object {
  $_ -notmatch '^\.claude/' -and $_ -notmatch '(^|/)\.env$' -and $_ -notmatch '^docs/' -and $_ -notmatch '^backend/tests/' -and $_ -notmatch '^backend/eval/' -and
  $_ -notmatch '^Dockerfile$' -and $_ -notmatch '^\.dockerignore$' -and $_ -notmatch '^\.github/'
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
robocopy (Join-Path $img "oasis2") (Join-Path $dimg "oasis2") /E /XD segmentation_inputs /XF *.err *.log list_part*.txt /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copying imaging data failed (robocopy code $LASTEXITCODE)" }

# 3. The web app is built here, because a Gradio Space has no Node.js. The built files go into the upload.
Push-Location (Join-Path $root "frontend")
$ErrorActionPreference = "Continue"   # npm prints notices on stderr; judge success by its exit code instead
if (-not (Test-Path "node_modules")) { npm install --no-audit --no-fund 2>&1 | Out-Host }
npm run build 2>&1 | Out-Host
$built = $LASTEXITCODE -eq 0
$ErrorActionPreference = "Stop"
Pop-Location
if (-not $built) { throw "Web app build failed" }
robocopy (Join-Path $root "frontend\dist") (Join-Path $out "frontend\dist") /E /NFL /NDL /NJH /NJS /NP | Out-Null

# 4. Space files: settings card (README.md), entry point, Python packages (same as start-imaging.ps1, without pytest),
#    and a .gitignore that keeps the imaging data and the built web app.
Copy-Item (Join-Path $PSScriptRoot "SPACE_README.md") (Join-Path $out "README.md") -Force
Copy-Item (Join-Path $PSScriptRoot "app.py") (Join-Path $out "app.py") -Force
# Written without a byte-order mark (PowerShell 5.1's "utf8" adds one). `spaces` is Hugging Face's ZeroGPU package: free
# accounts get Gradio Spaces only on ZeroGPU, and app.py uses it to pass ZeroGPU's startup check.
$noBom = New-Object System.Text.UTF8Encoding $false
$reqs = Get-Content (Join-Path $root "backend\requirements.txt"), (Join-Path $root "backend\requirements-imaging.txt") |
  Where-Object { $_ -and -not $_.StartsWith("#") -and $_ -notmatch '^pytest' }
[IO.File]::WriteAllLines((Join-Path $out "requirements.txt"), [string[]]($reqs + "spaces"), $noBom)
[IO.File]::WriteAllLines((Join-Path $out ".gitignore"), [string[]]@("__pycache__/", "*.pyc", ".env", "*.db", "data/", "frontend/node_modules/"), $noBom)

# 5. Safety check: no secrets or databases in the folder.
$bad = Get-ChildItem -Recurse -Force $out -File | Where-Object { $_.Name -eq ".env" -or $_.Extension -eq ".db" }
if ($bad) { throw "Refusing: found $($bad.FullName -join ', ')" }

$size = (Get-ChildItem -Recurse -Force $out -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Space folder ready: {0}  ({1:N0} MB)" -f $out, $size) -ForegroundColor Cyan
exit 0   # robocopy leaves a non-zero "files copied" code behind
