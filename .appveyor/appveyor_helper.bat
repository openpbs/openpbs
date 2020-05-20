@echo off

REM Copyright (C) 1994-2020 Altair Engineering, Inc.
REM For more information, contact Altair at www.altair.com.
REM
REM This file is part of both the OpenPBS software ("OpenPBS")
REM and the PBS Professional ("PBS Pro") software.
REM
REM Open Source License Information:
REM
REM OpenPBS is free software. You can redistribute it and/or modify it under
REM the terms of the GNU Affero General Public License as published by the
REM Free Software Foundation, either version 3 of the License, or (at your
REM option) any later version.
REM
REM OpenPBS is distributed in the hope that it will be useful, but WITHOUT
REM ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
REM FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
REM License for more details.
REM
REM You should have received a copy of the GNU Affero General Public License
REM along with this program.  If not, see <http://www.gnu.org/licenses/>.
REM
REM Commercial License Information:
REM
REM PBS Pro is commercially licensed software that shares a common core with
REM the OpenPBS software.  For a copy of the commercial license terms and
REM conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
REM Altair Legal Department.
REM
REM Altair's dual-license business model allows companies, individuals, and
REM organizations to create proprietary derivative works of OpenPBS and
REM distribute them - whether embedded or bundled with other software -
REM under a commercial license agreement.
REM
REM Use of Altair's trademarks, including but not limited to "PBS™",
REM "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
REM subject to Altair's trademark licensing policies.


REM this script is just helper script to build PBS deps in parallel to reduce
REM time of building all PBS deps.
REM
REM 1. it will list all build_*.bat file in .appveyor directory
REM 2. one by one it will execute each batch file in background while
REM    capturing output and error or batchfile in <batch file name>.bat.out
REM    file in current directory
REM 3. while executing batch file it will limit number of started background
REM    process to number of processors available in system.
REM 4. once it started background process reached limit it goes to wait loop
REM    where it will wait for atleast one background process to complete by
REM    looking at exclusive lock on <batch file name>.bat.out created by start
REM    of process and that lock will be released as soon as process ends
REM 5. as soon as one processor ends it checks for <batch file name>.bat.passed
REM    file if it exists that means background process completed successfully
REM    else some error occurred. Now in case of error this script will show
REM    contents of <batch file name>.bat.out to console and exit with error
REM    (which will stop all other background scrips also) else it will just put
REM    one line saying \<batch file name>.bat finished.
REM 6. Now since one process if finished we have one room to start new process
REM    so it will go back to main loop to start new background process for building
REM    next PBS deps and main loop again goes to wait loop and this goes on till
REM    end of all batch file in .appveyor directory

setlocal enableDelayedExpansion
cd "%~dp0\.."
set /a "started=0, ended=0"
set hasmore=1
set BUILD_TYPE=Release
if "%~1"=="debug" (
    set BUILD_TYPE=Debug
)
if "%~1"=="Debug" (
    set BUILD_TYPE=Debug
)
for /f "usebackq" %%A in (`dir /b C:\__withoutspace_*dir_* 2^>nul`) do rd /Q C:\%%A

call "%~dp0set_paths.bat"
1>nul 2>nul del /Q /F %BINARIESDIR%\*.bat.out %BINARIESDIR%\*.passed

for /f "usebackq" %%A in (`dir /on /b .appveyor ^| findstr /B /R "^build_.*\.bat$"`) do (
    if !started! lss %NUMBER_OF_PROCESSORS% (
        set /a "started+=1, next=started"
    ) else (
        call :Wait
    )
    set out!next!=%%A.out
    echo !time! - %%A - %BUILD_TYPE% version: started
    start /b "" "cmd /c 1>%BINARIESDIR%\%%A.out 2>&1 .appveyor\%%A %BUILD_TYPE% && echo > %BINARIESDIR%\%%A.passed"
    REM Introduce 2 sec delay to get different RANDOM value
    1>nul 2>nul ping /n 2 ::1
)
set hasmore=

:Wait
for /l %%N in (1 1 %started%) do 2>nul (
    if not defined ended%%N if exist "%BINARIESDIR%\!out%%N!" 9>>"%BINARIESDIR%\!out%%N!" (
        if not exist "%BINARIESDIR%\!out%%N:out=passed!" (
            type "%BINARIESDIR%\!out%%N!"
            exit 1
        ) else (
            echo !time! - !out%%N:.out=! - %BUILD_TYPE% version: finished
        )
        if defined hasmore (
            set /a "next=%%N"
            exit /b
        )
        set /a "ended+=1, ended%%N=1"
    )
)
if %ended% lss %started% (
    1>nul 2>nul ping /n 5 ::1
    goto :Wait
)

1>nul 2>nul del /Q /F %BINARIESDIR%\*.bat.out %BINARIESDIR%\*.passed
