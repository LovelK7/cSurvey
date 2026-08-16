@echo off
rem ------------------------------------------------------------------
rem  TopoDroid zip -> cSurvey csx recovery (no typing needed)
rem
rem    * Drag one or more TopoDroid project .zip files onto this file
rem    * ...or just double-click it: every project zip in this folder
rem      (and subfolders) is processed
rem
rem  Next to each zip you get:
rem    <survey>_recovered.csx      raw regenerated TopoDroid csx
rem    <survey>_recovered_pp.csx   symbol-mapped -> IMPORT THIS ONE
rem
rem  Keep a copy of this .bat in the TDX handoff folder; the canonical
rem  copy lives in the repo at dev\production\tools\recover_tdx.bat.
rem ------------------------------------------------------------------
set "TOOLS=C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\production\tools"

if "%~1"=="" (
    python "%TOOLS%\tdx_zip_to_csx.py" "%~dp0."
) else (
    python "%TOOLS%\tdx_zip_to_csx.py" %*
)
echo.
pause
