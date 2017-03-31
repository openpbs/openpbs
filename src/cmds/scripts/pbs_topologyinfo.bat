@echo off

rem
rem  Copyright (C) 1994-2017 Altair Engineering, Inc.
rem  For more information, contact Altair at www.altair.com.
rem   
rem  This file is part of the PBS Professional ("PBS Pro") software.
rem  
rem  Open Source License Information:
rem   
rem  PBS Pro is free software. You can redistribute it and/or modify it under the
rem  terms of the GNU Affero General Public License as published by the Free 
rem  Software Foundation, either version 3 of the License, or (at your option) any 
rem  later version.
rem   
rem  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
rem  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
rem  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
rem   
rem  You should have received a copy of the GNU Affero General Public License along 
rem  with this program.  If not, see <http://www.gnu.org/licenses/>.
rem   
rem  Commercial License Information: 
rem  
rem  The PBS Pro software is licensed under the terms of the GNU Affero General 
rem  Public License agreement ("AGPL"), except where a separate commercial license 
rem  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
rem   
rem  Altair’s dual-license business model allows companies, individuals, and 
rem  organizations to create proprietary derivative works of PBS Pro and distribute 
rem  them - whether embedded or bundled with other software - under a commercial 
rem  license agreement.
rem  
rem  Use of Altair’s trademarks, including but not limited to "PBS™", 
rem  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
rem  trademark licensing policies.
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
set PBS_EXEC=""
set outfl=%TEMP%\pbs_topologyinfo.out.%username%

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

set PBS_HOME=""
for /f "delims== tokens=1,2" %%G in ('type "%PBS_CONF_FILE%"') do set %%G=%%H

cmd /C "set PBS_HOME=%PBS_HOME%&& "%PBS_EXEC%\bin\pbs_python.exe" "%PBS_EXEC%\lib\python\pbs_topologyinfo.py" %*"
