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

set numberofarguments=0
set args=

call :command_to_run %*

REM subtract 1 from numberofarguments, for us to know how many to process.
set /a numberofarguments-=1

:process_arguments
if %numberofarguments% == 0 goto end_process_arguments
set /a numberofarguments-=1
set args=%args% %1%
shift
goto process_arguments
:end_process_arguments

goto :eof

REM This subroutine gets the last command-line argument by
REM using SHIFT. It also counts the number of arguments.
:command_to_run
set /a numberofarguments+=1
set lastArg=%~1
shift
if not "%~1"=="" goto command_to_run

mpiexec %args%  -env PBS_CONF_FILE "%PBS_CONF_FILE%" -env PBS_JOBID %PBS_JOBID%  pbs_attach %lastArg%

goto :eof
