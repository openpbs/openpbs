@echo off
set pbs_exec_dir=
for /F "tokens=2 delims==" %%i in ('findstr /i "PBS_EXEC" "%PBS_CONF_FILE%"') do set pbs_exec_dir=%%i

set PREV_PBS_CONF_FILE=%PBS_CONF_FILE%
set backupdir=%pbs_exec_dir%\lib\
set backupcmd=xcopy
IF %1==/b GOTO Backup
IF %1==/r GOTO Revert
echo Invalid Option
GOTO :EOF

:Backup
echo off
SETX /m PBS_CONF_FILE "%WINDIR%\Temp\PBS Pro Backup\pbs.conf"
echo In Backup Mode...
echo ### Backing up Files...
%backupcmd% "%pbs_exec_dir%\lib\liblmx-altair.dll" "%backupdir%MyDLLBackUp"
IF %ERRORLEVEL% NEQ 0 GOTO ERR 
%backupcmd% "%pbs_exec_dir%\lib\liblmx-altair.lib" "%backupdir%MyDLLBackUp"
IF %ERRORLEVEL% NEQ 0 GOTO ERR 
echo Backup Complete !
echo Continue copying the files...
xcopy  "%WINDIR%\Temp\PBS Pro Backup\exec\lib\liblmx-altair.dll" "%backupdir%"
IF %ERRORLEVEL% NEQ 0 GOTO ERR  
xcopy  "%WINDIR%\Temp\PBS Pro Backup\exec\lib\liblmx-altair.lib" "%backupdir%"
IF %ERRORLEVEL% NEQ 0 GOTO ERR 
echo Copied the liblmx files from PBS backup folder to current working folder...
GOTO :EOF

:Revert
echo off
setx /m PBS_CONF_FILE "%PREV_PBS_CONF_FILE%"
echo In Revert Mode...
echo Reverting the Files Back...
%backupcmd% "%backupdir%MyDLLBackUp\liblmx-altair.dll" "%backupdir%"
IF %ERRORLEVEL% NEQ 0 GOTO ERR 
%backupcmd% "%backupdir%MyDLLBackUp\liblmx-altair.lib" "%backupdir%"
IF %ERRORLEVEL% NEQ 0 GOTO ERR 
echo Backup Revert Complete !
GOTO :EOF

:ERR
echo Error encountered in xcopy
GOTO :EOF
