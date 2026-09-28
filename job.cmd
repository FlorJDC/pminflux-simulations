@echo off
rem agent-team launcher for this project (Windows cmd / PowerShell):  .\job.cmd <verb> ...
rem Runs the vendored tool in agent-team\ with this folder as the project root, and puts Git
rem Bash on PATH for this process only (check spines and acceptance gates are sh scripts).
setlocal
set "AT_ROOT=%~dp0"
set "AT_ROOT=%AT_ROOT:~0,-1%"
if not defined AGENT_TEAM_PROJECT set "AGENT_TEAM_PROJECT=%AT_ROOT%"

set "AT_GITBIN="
for /f "delims=" %%G in ('where git 2^>nul') do if not defined AT_GITBIN if exist "%%~dpG..\bin\bash.exe" set "AT_GITBIN=%%~dpG..\bin"
if not defined AT_GITBIN if exist "%ProgramFiles%\Git\bin\bash.exe" set "AT_GITBIN=%ProgramFiles%\Git\bin"
if defined AT_GITBIN (set "PATH=%AT_GITBIN%;%PATH%") else (echo job: Git Bash not found - check spines need it. Install Git for Windows. 1>&2)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 "%AT_ROOT%\agent-team\bin\job" %*
) else (
    python "%AT_ROOT%\agent-team\bin\job" %*
)
exit /b %ERRORLEVEL%
