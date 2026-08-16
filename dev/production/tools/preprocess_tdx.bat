@echo off
rem ------------------------------------------------------------------
rem  STEP 2 of 4 - PREPARE THE PHONE FILE FOR cSURVEY
rem  Raw TopoDroid .csx  ->  import-ready _pp.csx (renames symbols so
rem  they survive the import). No typing needed.
rem
rem    * Double-click: prepares every raw TopoDroid .csx in this folder
rem    * ...or drag one or more raw .csx files onto this icon
rem
rem  YOU GET: <name>_pp.csx next to each input -> IMPORT THAT ONE in
rem  cSurvey (that is STEP 3). Files already ending in _pp and any saved
rem  cSurvey files are skipped automatically.
rem
rem  Canonical copy: dev\production\tools\preprocess_tdx.bat (this is a copy).
rem ------------------------------------------------------------------
set "TOOLS=C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\production\tools"

echo ==================================================================
echo  STEP 2 - preparing phone files for import
echo ==================================================================
echo.
if "%~1"=="" (
    python "%TOOLS%\preprocess_tdx_csx.py" "%~dp0." --force
) else (
    python "%TOOLS%\preprocess_tdx_csx.py" %* --force
)
echo.
echo ------------------------------------------------------------------
echo  NEXT (STEP 3): open the _pp.csx file in cSurvey, then File ^> Save As.
echo                 Then run STEP 4 by dragging that saved file onto
echo                 fix_tdx.bat.  Read any WARNING lines above first.
echo ------------------------------------------------------------------
pause
