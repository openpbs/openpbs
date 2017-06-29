@echo off

REM this genereates the pbs_version.h file.
cd %~dp0

REM exit if pbs_version.h exists
if exist "..\..\src\include\pbs_version.h" (
	goto :eof
)

if exist "..\..\src\include\pbs_version.h.in" ( 
	copy "..\..\src\include\pbs_version.h.in" "..\..\src\include\pbs_version.h"
)

REM find pbs_version from pbspro.spec
set pbs_specfile="..\..\pbspro.spec"
for /F "tokens=3 USEBACKQ" %%F IN (`findstr /l /c:" pbs_version " %pbs_specfile%`) DO (
	set var=%%F
	set pbs_ver=%var%
)

REM replace PBS_VERSION placeholder value(@PBS_WIN_VERSION@) 
REM defined in pbs_version.h with pbs_ver
set oldfile="..\..\src\include\pbs_version.h"
set searchstr=@PBS_WIN_VERSION@
set repstr=%var%
if exist "..\include\temp_pbs_version.h" (
	del /f /q "..\include\temp_pbs_version.h"
)
for /f "tokens=1,* delims=]" %%A in ('"type %oldfile%|find /n /v """') do (
    set "line=%%B"
    if defined line (
        call set "line=echo.%%line:%searchstr%=%repstr%%%"
        for /f "delims=" %%X in ('"echo."%%line%%""') do %%~X >> ..\include\temp_pbs_version.h"
    ) ELSE echo.
)
copy "..\include\temp_pbs_version.h" "..\..\src\include\pbs_version.h"
del /f /q "..\include\temp_pbs_version.h"

