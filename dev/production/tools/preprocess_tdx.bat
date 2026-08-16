@echo off
rem ------------------------------------------------------------------
rem  Raw TopoDroid csx -> import-ready _pp.csx (no typing needed)
rem
rem    * Drag one or more raw TopoDroid .csx files onto this file
rem    * ...or just double-click it: every raw TopoDroid csx in this
rem      folder (and subfolders) is preprocessed
rem
rem  Next to each input you get <name>_pp.csx  ->  IMPORT THIS ONE.
rem  Already-preprocessed (_pp.csx) and post-import files are skipped
rem  automatically in folder mode; existing _pp outputs are refreshed.
rem
rem  Keep a copy of this .bat in the TDX handoff folder; the canonical
rem  copy lives in the repo at dev\production\tools\preprocess_tdx.bat.
rem ------------------------------------------------------------------
set "TOOLS=C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\production\tools"

if "%~1"=="" (
    python "%TOOLS%\preprocess_tdx_csx.py" "%~dp0." --force
) else (
    python "%TOOLS%\preprocess_tdx_csx.py" %* --force
)
echo.
pause
