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
