<#
.SYNOPSIS
  Brings the agent-team methodology from this template into an EXISTING project.

.DESCRIPTION
  For a new project, just create it from the template on GitHub ("Use this template") or clone
  it. For a project that already exists, run this from a clone of the template:

      .\scripts\apply-to-existing.ps1 -Target C:\path\to\project [-Git] [-Force]

  It copies the template's files (agent-team\, .agent-team\, .claude\, job.cmd, job.sh,
  OBJECTIVE.template.md, papers\, jobs\, equipo\) without overwriting anything that exists
  (unless -Force). CLAUDE.md, AGENTS.md and .gitignore are never replaced: a marked section
  <!-- agent-team:inicio --> ... <!-- agent-team:fin --> is appended, or refreshed on re-run.
  The template's README.md is not copied. Safe to re-run.

.PARAMETER Target  Project folder (created if missing).
.PARAMETER Force   Overwrite template files that already exist in the target.
.PARAMETER Git     Run `git init` in the target if it is not a git repo (feature jobs need git).
#>
param(
    [Parameter(Mandatory = $true)][string]$Target,
    [switch]$Force,
    [switch]$Git
)
$ErrorActionPreference = "Stop"

$Template = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Ini = "<!-- agent-team:inicio (agent-team-template; no editar dentro de este bloque) -->"
$Fin = "<!-- agent-team:fin -->"
$GiIni = "# --- agent-team (agent-team-template) ---"
$GiFin = "# --- /agent-team ---"

New-Item -ItemType Directory -Force -Path $Target | Out-Null
$Target = (Resolve-Path -LiteralPath $Target).Path
if ($Target.TrimEnd('\') -eq $Template.TrimEnd('\')) { throw "Target cannot be the template itself." }

function Read-Text([string]$p) { [IO.File]::ReadAllText($p, $Utf8) }
function Write-Text([string]$p, [string]$t) { [IO.File]::WriteAllText($p, $t, $Utf8) }
function Get-Block([string]$t, [string]$a, [string]$b) {
    $i = $t.IndexOf($a); $j = $t.IndexOf($b)
    if ($i -lt 0 -or $j -lt $i) { return $null }
    return $t.Substring($i, $j + $b.Length - $i)
}
# Replace the marked block in $t with $blk, or append it. $null when nothing changes.
function Set-Block([string]$t, [string]$blk, [string]$a, [string]$b) {
    $old = Get-Block $t $a $b
    if ($null -eq $old) { return ($t.TrimEnd() + "`n`n" + $blk + "`n") }
    if ($old -eq $blk) { return $null }
    return $t.Replace($old, $blk)
}
function Merge-File([string]$name, [string]$blk, [string]$a, [string]$b, [string]$whenNew) {
    $p = Join-Path $Target $name
    if (-not (Test-Path -LiteralPath $p)) { Write-Text $p $whenNew; Write-Host "  $name created"; return }
    $new = Set-Block (Read-Text $p) $blk $a $b
    if ($null -eq $new) { Write-Host "  $name already up to date" }
    else { Write-Text $p $new; Write-Host "  $name exists: agent-team section added/updated" }
}

Write-Host "Applying agent-team-template to: $Target"

# --- 1. files -----------------------------------------------------------------------------
$merged = @("CLAUDE.md", "AGENTS.md", ".gitignore", "README.md")
$ErrorActionPreference = "Continue"
$files = & git -C $Template ls-files 2>$null
$ErrorActionPreference = "Stop"
if (-not $files) {
    $files = Get-ChildItem -LiteralPath $Template -Recurse -Force -File |
        Where-Object { $_.FullName -notmatch '\\\.git\\|\\__pycache__\\' } |
        ForEach-Object { $_.FullName.Substring($Template.Length + 1) -replace '\\', '/' }
}
$copied = 0; $kept = 0
foreach ($rel in $files) {
    if ($merged -contains $rel) { continue }
    $src = Join-Path $Template $rel
    if (-not (Test-Path -LiteralPath $src)) { continue }
    $dst = Join-Path $Target $rel
    if ((Test-Path -LiteralPath $dst) -and -not $Force) { $kept++; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
    $copied++
}
Write-Host "  files copied: $copied  (already present, left alone: $kept)"

# --- 2. CLAUDE.md / AGENTS.md / .gitignore -----------------------------------------------------
$claude = Read-Text (Join-Path $Template "CLAUDE.md")
Merge-File "CLAUDE.md" (Get-Block $claude $Ini $Fin) $Ini $Fin $claude

$agents = Read-Text (Join-Path $Template "AGENTS.md")
$agentsBlk = $Ini + "`n" + $agents.TrimEnd() + "`n" + $Fin
Merge-File "AGENTS.md" $agentsBlk $Ini $Fin ($agentsBlk + "`n")

$gi = $GiIni + "`n# agent-team job data is local state (delete these lines to version it)`n" +
      "jobs/*`n!jobs/.gitkeep`nequipo/*`n!equipo/.gitkeep`nagent-team/policy.json`n__pycache__/`n" + $GiFin
Merge-File ".gitignore" $gi $GiIni $GiFin ($gi + "`n")

# --- 3. git ---------------------------------------------------------------------------------
if (Get-Command git -ErrorAction SilentlyContinue) {
    $ErrorActionPreference = "Continue"
    $null = & git -C $Target rev-parse --is-inside-work-tree 2>&1
    $isGit = ($LASTEXITCODE -eq 0)
    if (-not $isGit -and $Git) {
        $null = & git -C $Target init 2>&1
        $isGit = ($LASTEXITCODE -eq 0)
        if ($isGit) { Write-Host "  git init done" }
    }
    $ErrorActionPreference = "Stop"
    if (-not $isGit) { Write-Host "  NOTE: target is not a git repo; 'feature' jobs need one (use -Git)." }
}

Write-Host ""
Write-Host "Next: fill in 'Sobre este proyecto' in CLAUDE.md, copy OBJECTIVE.template.md to OBJECTIVE.md,"
Write-Host "then open Claude Code there and use /equipo-nuevo (interactive) or /job-preparar (.\job.cmd)."
