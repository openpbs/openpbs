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

REM this genereates the pbs_version.h file.
cd %~dp0

REM exit if pbs_version.h exists
if exist "..\..\src\include\pbs_version.h" (
	goto :eof
)

if exist "..\..\src\include\pbs_version.h.in" (
	copy "..\..\src\include\pbs_version.h.in" "..\..\src\include\pbs_version.h"
)

REM find pbs_version from spec file
set pbs_specfile="..\..\openpbs.spec"
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
