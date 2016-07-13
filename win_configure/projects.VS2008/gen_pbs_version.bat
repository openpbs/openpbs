@echo off
REM this genereates the pbs_version.h file.


REM exit if pbs_version.h exists
if exist "..\..\src\include\pbs_version.h" (
goto :eof
)

if exist "..\..\src\include\pbs_version.h.in" ( 

copy "..\..\src\include\pbs_version.h.in" "..\..\src\include\pbs_version.h" 

)

REM find pbs_version from pbspro.spec
set pbs_specfile= ..\..\pbspro.spec
for /F "tokens=3 USEBACKQ" %%F IN (`findstr /l /c:" pbs_version " %pbs_specfile%`) DO (
set var=%%F
set pbs_ver=PBSPro_%var%
)
REM replace PBS_VERSION placeholder value(PBSPro_10.0) 
REM defined in pbs_version_win.h with pbs_ver
set oldfile="..\include\pbs_version_win.h"
set searchstr=PBSPro_10.0
set repstr=PBSPro_%var%
if exist "..\include\temp_pbs_version_win.h" (
del /f /q "..\include\temp_pbs_version_win.h"
)
for /f "tokens=1,* delims=]" %%A in ('"type %oldfile%|find /n /v """') do (
    set "line=%%B"
    if defined line (
        call set "line=echo.%%line:%searchstr%=%repstr%%%"
        for /f "delims=" %%X in ('"echo."%%line%%""') do %%~X >> ..\include\temp_pbs_version_win.h"
    ) ELSE echo.
)
copy "..\include\temp_pbs_version_win.h" "..\include\pbs_version_win.h"
del /f /q "..\include\temp_pbs_version_win.h"