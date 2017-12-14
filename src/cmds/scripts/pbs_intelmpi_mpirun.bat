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
