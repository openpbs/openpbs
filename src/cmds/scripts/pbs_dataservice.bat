@echo off

rem
rem Copyright (C) 1994-2018 Altair Engineering, Inc.
rem For more information, contact Altair at www.altair.com.
rem
rem This file is part of the PBS Professional ("PBS Pro") software.
rem
rem Open Source License Information:
rem
rem PBS Pro is free software. You can redistribute it and/or modify it under the
rem terms of the GNU Affero General Public License as published by the Free
rem Software Foundation, either version 3 of the License, or (at your option) any
rem later version.
rem
rem PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
rem WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
rem FOR A PARTICULAR PURPOSE.
rem See the GNU Affero General Public License for more details.
rem
rem You should have received a copy of the GNU Affero General Public License
rem along with this program.  If not, see <http://www.gnu.org/licenses/>.
rem
rem Commercial License Information:
rem
rem For a copy of the commercial license terms and conditions,
rem go to: (http://www.pbspro.com/UserArea/agreement.html)
rem or contact the Altair Legal Department.
rem
rem Altair’s dual-license business model allows companies, individuals, and
rem organizations to create proprietary derivative works of PBS Pro and
rem distribute them - whether embedded or bundled with other software -
rem under a commercial license agreement.
rem
rem Use of Altair’s trademarks, including but not limited to "PBS™",
rem "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
rem trademark licensing policies.
rem

Setlocal EnableDelayedExpansion

if not "%PBS_CONF_FILE%" == "" GOTO CONT0
echo "PBS_CONF_FILE not set"
exit /b 1

:CONT0
if not "%TEMP%" == "" GOTO CONT1
echo "TEMP not set"
exit /b 1

:CONT1
if exist "%PBS_CONF_FILE%" goto CONT2
echo "PBS configurtion file "%PBS_CONF_FILE%" not found"
exit /b 1

:CONT2
pushd "%CD%"
cd "%TEMP%"



set /A cnt=0

:AGAIN
set /A cnt=cnt+1
set outfl=%TEMP%\pbs_dataservice.out.%username%.%cnt%
if exist %outfl% GOTO AGAIN

if "%PROCESSOR_ARCHITECTURE%" == "x86" (
	set SYSTEMFOLDERPATH=%SYSTEMROOT%\system32
) else (
	set SYSTEMFOLDERPATH=%SYSTEMROOT%\syswow64
)
if exist "%SYSTEMFOLDERPATH%\find.exe" (
	set FIND_COMMAND="%SYSTEMFOLDERPATH%\find.exe"
) else (
	set FIND_COMMAND="find.exe" 
)

rem Setting PBS_DATA_SERVICE_PORT based on availability  in following order:
rem 1. Set PBS_DATA_SERVICE_PORT to port provided by pbs 
rem 2. Set PBS_DATA_SERVICE_PORT to port provided by pbs.conf
rem 3. Set PBS_DATA_SERVICE_PORT to port provided by /etc/services
rem 4. Set PBS_DATA_SERVICE_PORT to default port

set PBS_DATA_SERVICE_PORT=
set PBS_DATA_SERVICE_PROTOCOL=


set PBS_DATA_SERVICE_PORT=%3

if  "!PBS_DATA_SERVICE_PORT!"=="" (
    %FIND_COMMAND% "PBS_DATA_SERVICE_PORT" < "%PBS_CONF_FILE%" > %outfl%
    for /F "eol=# tokens=2 delims==" %%i in (%outfl%) do set PBS_DATA_SERVICE_PORT=%%i
    del %outfl%
)

if  "!PBS_DATA_SERVICE_PORT!"=="" (
	%FIND_COMMAND% "pbs_dataservice" < "%SYSTEMROOT%\system32\drivers\etc\services" > %outfl%
	for /F "tokens=2" %%i in (%outfl%) do echo %%i > %outfl%
	for /F "tokens=1* delims=/" %%a in (%outfl%) do (
		set PBS_DATA_SERVICE_PORT=%%a 
		set PBS_DATA_SERVICE_PROTOCOL=%%b
	)
	if not "!PBS_DATA_SERVICE_PROTOCOL!" == "tcp " set PBS_DATA_SERVICE_PORT=
	del %outfl%
)

if  "%PBS_DATA_SERVICE_PORT%"=="" (
	set PBS_DATA_SERVICE_PORT=15007
)

set PBS_HOME=""
%FIND_COMMAND% "PBS_HOME" < "%PBS_CONF_FILE%" > %outfl%
for /F "eol=# tokens=2 delims==" %%i in (%outfl%) do set PBS_HOME=%%i
del %outfl%

set PBS_EXEC=""
%FIND_COMMAND% "PBS_EXEC" < "%PBS_CONF_FILE%" > %outfl%
for /F "eol=# tokens=2 delims==" %%i in (%outfl%) do set PBS_EXEC=%%i
del %outfl%

if not "%PBS_HOME%" == "" GOTO CONT3
echo "Environment variable PBS_HOME not set"
popd
exit /b 1

:CONT3
if not "%PBS_EXEC%" == "" GOTO CONT4
echo "Environment variable PBS_EXEC not set"
popd
exit /b 1


:CONT4

REM All work with temporary files done, pop back to original directory
popd

set PG_CTL="%PBS_EXEC%\pgsql\bin\pg_ctl" -D "%PBS_HOME%\datastore" -o "-p %PBS_DATA_SERVICE_PORT%"

REM 
REM If second parameter is specified as "PBS" it means this was called from the PBS daemons
REM In such a case we do not want to be very verbose (as we only need the error code and msg)
REM Windows code calls this via cmd.exe and does not pass the proper error status if exit /b is used
REM Thus when called from PBS we use exit without /b and when called from commandline we use exit /b
REM Also, when stop is called from command line we do a regular postgres stop, but when called from PBS
REM we do a "fast" stop of postgres. The "fast" stop disconnects any existing clients to ensure that
REM the postgres daemons are indeed stopped when PBS is stopped
REM 

set cmd=%1
set caller=CL

if "%2" == "PBS" set caller=PBS

if "%1" == "start" goto START
if "%1" == "stop" goto STOP
if "%1" == "stopasync" goto STOPASYNC
if "%1" == "status" goto STATUS
if "%1" == "startasync" goto STARTASYNC
goto ERR

:statpbs
	"%PBS_EXEC%"\bin\qstat > nul 2>&1
	set ret=%ERRORLEVEL%
	GOTO :EOF


REM Return code values:
REM       0  - Data service running on local host
REM       1  - Data service definitely NOT running
REM       2  - Failed to obtain exclusive lock

:statds
	set msg=
	set ret=
	%PG_CTL% -w status > nul 2>&1
	set ret=%ERRORLEVEL%
	if %ret% == 0 (
		set msg=PBS data service running locally
		GOTO :EOF
	)
	
	set msg=PBS data service not running
	set ret=1	
	
	"%PBS_EXEC%"\sbin\pbs_ds_monitor check > %outfl% 2>&1
	if not %ERRORLEVEL% == 0 (
		set /p msg=<%outfl%
		set ret=2
	)
	del %outfl%
	GOTO :EOF

:START
:STARTASYNC
	REM we can start dataservice only if it is not running
	call :statds
	if not %ret% == 1 (
		REM PBS data service already running, we want errmsg even for nonCL
		echo %msg% - cannot start
		if "%caller%" == "CL" (
			exit /b %ret%
		)
		exit %ret%
	)
	
	"%PBS_EXEC%"\sbin\pbs_ds_monitor monitor > %outfl% 2>&1
	set ret=%ERRORLEVEL%
	set /p msg=<%outfl%
	del %outfl%
	if not %ret% == 0 (
		REM Monitor failed to aquire lock, probably lost a race, err even for nonCL
		echo %msg% - cannot start
		if "%caller%" == "CL" (
			exit /b %ret%
		)
		exit %ret%
	)
	REM We got a lock and monitor is established, nobody else can start DB
	
	if "%caller%" == "CL" (
		echo Starting PBS Data Service..
	)
	
	if "%cmd%" == "startasync" (%PG_CTL% -W start)
	if "%cmd%" == "start" (%PG_CTL% -w start)
	
	set ret=%ERRORLEVEL%
	if "%caller%" == "CL" (
		if not %ret% == 0 (
			echo Failed to start PBS Data Service
		)
		exit /b %ret%
	)
	exit %ret%

:STOP
:STOPASYNC
	call :statds
	if not %ret% == 0 echo %msg% - cannot stop  & exit /b 0
	
	REM If called from PBS dont stat for PBS being up
	if not "%caller%" == "CL" goto stopdb
	
	call :statpbs
	if %ret% == 0 echo PBS server is running. Cannot stop PBS Data Service now. & exit /b 1

:stopdb
	if "%caller%" == "CL" echo Stopping PBS Data Service..
	%PG_CTL% -w stop
	set ret=%ERRORLEVEL%
	if "%caller%" == "CL" (
		if not %ret% == 0 (
			echo Failed to stop PBS Data Service
			echo (Check if there are active connections to the data service)
		)
		exit /b %ret%
	)
	exit %ret%

:STATUS
	call :statds
	if "%caller%" == "CL" (
		echo %msg%
		exit /b %ret%
	)
	exit %ret%
	
:ERR
	popd
	echo "Usage: %0% {start|stop|status}"
	exit /b 1
