@echo off
rem Upload local changes (e.g. config.yaml edits) to GitHub. The next scheduled scan uses them.
cd /d "%~dp0"
rem safe.directory: the exFAT drive can't record file owners, which Git otherwise refuses.
set GIT="%~dp0tools\git\cmd\git.exe" -c safe.directory=*
%GIT% add -A
%GIT% diff --cached --quiet && (echo Nothing changed.) || %GIT% commit -q -m "Update from laptop"
%GIT% push -q origin main && echo Pushed to GitHub.
pause
