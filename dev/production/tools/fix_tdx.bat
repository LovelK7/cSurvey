@echo off
rem ------------------------------------------------------------------
rem  STEP 4 of 4 - FINISH THE IMPORT
rem  Turns the file you saved in cSurvey into the finished map file.
rem  (slope/gradient/etc. lines get their arrows/ticks; sizes; water)
rem
rem  DO THIS RIGHT AFTER "Save As" IN cSURVEY, BEFORE YOU DRAW ANYTHING.
rem
rem  HOW: drag the file you just saved and drop it on this icon.
rem       (both .csz and .csx are fine - whatever you saved)
rem
rem  YOU GET: a new file next to it whose name ends in _lt
rem       -> OPEN THAT _lt FILE in cSurvey and do all your drawing there.
rem
rem  If the black window says BLOCKED, you dragged a file that has not
rem  been imported into cSurvey yet - read what it tells you to do.
rem
rem  Canonical copy: dev\production\tools\fix_tdx.bat (this is a copy).
rem ------------------------------------------------------------------
set "TOOLS=C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\production\tools"

echo ==================================================================
echo  STEP 4 - finishing the import (making decorations show)
echo ==================================================================
echo.
if "%~1"=="" (
    echo  Nothing was dragged in.
    echo.
    echo  Do this: in Windows Explorer, find the file you just saved in
    echo  cSurvey ^(after "Save As"^), drag it with the mouse, and drop it
    echo  onto this fix_tdx.bat icon.
) else (
    python "%TOOLS%\fix_imported_linetypes.py" %* --force
)
echo.
echo ------------------------------------------------------------------
echo  Done. Read the lines above:
echo    "OK ... _lt ..."   success: open the _lt file and draw in it.
echo    "BLOCKED"          wrong file/step: do what it tells you.
echo    "ERROR"            something else: read the message.
echo ------------------------------------------------------------------
pause
