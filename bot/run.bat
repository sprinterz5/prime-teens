@echo off
rem ============================================================
rem  Start the bot(s). Double-click for the mentor bot, or:
rem
rem    run.bat            - mentor bot only (default)
rem    run.bat kids        - kids bot only
rem    run.bat both         - both, each in its own window
rem
rem  Why not launch app\main.py directly:
rem    1) On this machine .py is associated with
rem       C:\Python27\ArcGIS10.8\python.exe (Python 2.7 from ArcGIS).
rem       It dies on Cyrillic in sources: "Non-ASCII character ...
rem       no encoding declared".
rem    2) app\main.py must be started as a package (-m app.main) from the
rem       project root, otherwise "No module named 'app'".
rem
rem  This file is deliberately ASCII-only: cmd.exe reads .bat in the OEM
rem  codepage, and UTF-8 Cyrillic here breaks parsing of the script itself.
rem
rem  This file is also deliberately written WITHOUT multi-line parenthesized
rem  if (...) blocks below - only flat "if ... goto label" branches. Reason,
rem  found the hard way: two multi-line parenthesized if-blocks in the same
rem  label (:check_kids originally had two) trips a genuine, poorly
rem  documented cmd.exe parser bug. It throws "in was unexpected at this
rem  time" on the SECOND block, then silently runs the wrong branch
rem  regardless of the real errorlevel - reproduced and confirmed in
rem  isolation. Flat goto control flow sidesteps the whole bug class.
rem ============================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" goto no_env

set MODE=%1
if "%MODE%"=="" set MODE=mentor

if /i "%MODE%"=="mentor" goto run_mentor
if /i "%MODE%"=="kids" goto run_kids
if /i "%MODE%"=="both" goto run_both

echo [!] Unknown argument: %MODE%
echo     Use: run.bat  /  run.bat kids  /  run.bat both
pause
exit /b 1

:no_venv
echo [!] No virtualenv found.
echo     Create it and install dependencies:
echo.
echo       python -m venv .venv
echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1

:no_env
echo [!] No .env file. Copy .env.example to .env and put the token in.
echo.
pause
exit /b 1

:run_mentor
echo Starting the mentor bot. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" -m app.main
set CODE=%ERRORLEVEL%
goto report

:run_kids
call :check_kids
if errorlevel 1 goto run_kids_blocked
echo Starting the kids bot. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" -m app.kids.main
set CODE=%ERRORLEVEL%
goto report

:run_kids_blocked
pause
exit /b 1

:run_both
call :check_kids
if errorlevel 1 goto run_both_fallback
echo Starting both bots, each in its own window.
rem /D sets the new window's starting directory directly - avoids nesting a
rem second pair of quotes inside an already-quoted "cmd /k ..." string,
rem which cmd.exe cannot parse ("in was unexpected at this time").
start "PrimeTeens - mentor bot" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m app.main"
start "PrimeTeens - kids bot" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m app.kids.main"
echo.
echo Two windows opened. Close this one whenever you like.
pause
exit /b 0

:run_both_fallback
echo     Starting the mentor bot only.
echo.
goto run_mentor

:report
echo.
if not "%CODE%"=="0" goto report_failed
echo Bot stopped.
pause
exit /b %CODE%

:report_failed
echo [!] Bot exited with code %CODE% - see the error above.
pause
exit /b %CODE%

rem ------------------------------------------------------------
rem  :check_kids - sets errorlevel 1 and prints why if the kids bot
rem  cannot run yet (module not written, or KIDS_BOT_TOKEN not set).
rem ------------------------------------------------------------
:check_kids
if exist "app\kids\main.py" goto check_kids_module_ok
echo [!] Kids bot module not found: app\kids\main.py
echo     It has not been written yet - nothing to run.
exit /b 1

:check_kids_module_ok
findstr /r /c:"^KIDS_BOT_TOKEN=..*" ".env" >nul
if errorlevel 1 goto check_kids_no_token
exit /b 0

:check_kids_no_token
echo [!] KIDS_BOT_TOKEN is empty (or missing) in .env.
echo     Set it before running the kids bot.
exit /b 1
