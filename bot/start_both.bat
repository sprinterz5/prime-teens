@echo off
rem ============================================================
rem  Double-click this to start BOTH bots (mentor + kids), each in
rem  its own window - no typing needed. Just delegates to run.bat both.
rem
rem  ASCII-only, same reason as run.bat: cmd.exe reads .bat files in the
rem  OEM codepage, and Cyrillic here would break parsing of the script.
rem ============================================================
cd /d "%~dp0"
call run.bat both
