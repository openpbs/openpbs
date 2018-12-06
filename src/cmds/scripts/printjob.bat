@echo off

REM
REM Copyright (C) 1994-2018 Altair Engineering, Inc.
REM For more information, contact Altair at www.altair.com.
REM
REM This file is part of the PBS Professional ("PBS Pro") software.
REM
REM Open Source License Information:
REM
REM PBS Pro is free software. You can redistribute it and/or modify it under the
REM terms of the GNU Affero General Public License as published by the Free
REM Software Foundation, either version 3 of the License, or (at your option) any
REM later version.
REM
REM PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
REM WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
REM FOR A PARTICULAR PURPOSE.
REM See the GNU Affero General Public License for more details.
REM
REM You should have received a copy of the GNU Affero General Public License
REM along with this program.  If not, see <http://www.gnu.org/licenses/>.
REM
REM Commercial License Information:
REM
REM For a copy of the commercial license terms and conditions,
REM go to: (http://www.pbspro.com/UserArea/agreement.html)
REM or contact the Altair Legal Department.
REM
REM Altair’s dual-license business model allows companies, individuals, and
REM organizations to create proprietary derivative works of PBS Pro and
REM distribute them - whether embedded or bundled with other software -
REM under a commercial license agreement.
REM
REM Use of Altair’s trademarks, including but not limited to "PBS™",
REM "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
REM trademark licensing policies.
REM

if "%PBS_CONF_FILE%" == "" (
	echo "PBS_CONF_FILE is not set"
	exit /b 1
)
if not exist "%PBS_CONF_FILE%" (
	echo "PBS configurtion file %PBS_CONF_FILE% not found"
	exit /b 1
)

for /f "delims=" %%x in (pbs.conf) do (set "%%x")

if not %PBS_START_SERVER% == "" if not %PBS_START_SERVER% == 0 (
	"%PBS_EXEC%\bin\printjob_svr.exe" %*
) else (
	"%PBS_EXEC%\bin\printjob_host.exe" %*
)

