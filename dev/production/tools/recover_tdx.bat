@echo off
rem ------------------------------------------------------------------
rem  STEP 1b (ONLY IF NEEDED) - REBUILD A BROKEN/MISSING csx FROM THE ZIP
rem  Use this when the phone's .csx is missing, 0 bytes, or lost its
rem  sketch (TopoDroid 6.4.98+ bug). Rebuilds it from the project .zip.
rem
rem    * Double-click: processes every TopoDroid project .zip in this folder
rem    * ...or drag one or more project .zip files onto this icon
rem
rem  YOU GET, next to each zip:
rem    <survey>_recovered.csx     the rebuilt phone file
rem    <survey>_recovered_pp.csx  already prepared -> IMPORT THIS ONE (STEP 3)
rem
rem  This does STEP 2 for you, so skip straight to STEP 3 afterwards.
rem  Normal case (csx is fine): you do NOT need this - use preprocess_tdx.bat.
rem
rem  Canonical copy: dev\production\tools\recover_tdx.bat (this is a copy).
rem ------------------------------------------------------------------
set "TOOLS=C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\production\tools"

echo ==================================================================
echo  STEP 1b - rebuilding csx from the project zip (recovery)
echo ==================================================================
echo.
if "%~1"=="" (
    python "%TOOLS%\tdx_zip_to_csx.py" "%~dp0."
) else (
    python "%TOOLS%\tdx_zip_to_csx.py" %*
)
echo.
echo ------------------------------------------------------------------
echo  NEXT (STEP 3): open the _recovered_pp.csx file in cSurvey, then
echo                 File ^> Save As, then run STEP 4 (fix_tdx.bat).
echo ------------------------------------------------------------------
pause
