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

