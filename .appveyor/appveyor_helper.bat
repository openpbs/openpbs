@echo off

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

set /a "started=0, ended=0"
set hasmore=1
1>nul 2>nul del *.out *.passed
for /f "usebackq" %%A in (`dir /on /b .appveyor ^| findstr /B /R "^build_.*\.bat$"`) do (
    if !started! lss %NUMBER_OF_PROCESSORS% (
        set /a "started+=1, next=started"
    ) else (
        call :Wait
    )
    set out!next!=%%A.out
    echo !time! - %%A: started
    start /b "" "cmd /c 1>%%A.out 2>&1 .appveyor\%%A && echo > %%A.passed"
)
set hasmore=

:Wait
for /l %%N in (1 1 %started%) do 2>nul (
    if not defined ended%%N if exist "!out%%N!" 9>>"!out%%N!" (
        if not exist "!out%%N:out=passed!" (
            type "!out%%N!"
            exit 1
        ) else (
            echo !time! - !out%%N:.out=!: finished
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
