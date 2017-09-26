@echo off

REM Copyright (C) 1994-2017 Altair Engineering, Inc.
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
REM WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
REM PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
REM  
REM You should have received a copy of the GNU Affero General Public License along 
REM with this program.  If not, see <http://www.gnu.org/licenses/>.
REM  
REM Commercial License Information: 
REM 
REM The PBS Pro software is licensed under the terms of the GNU Affero General 
REM Public License agreement ("AGPL"), except where a separate commercial license 
REM agreement for PBS Pro version 14 or later has been executed in writing with Altair.
REM  
REM Altair’s dual-license business model allows companies, individuals, and 
REM organizations to create proprietary derivative works of PBS Pro and distribute 
REM them - whether embedded or bundled with other software - under a commercial 
REM license agreement.
REM 
REM Use of Altair’s trademarks, including but not limited to "PBS™", 
REM "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
REM trademark licensing policies.

REM This script will generate the componentgroup directory structure

REM parsing command line arguments
set argC=0
for %%x in (%*) do set /A argC+=1

if %argC% LSS 1 (
	echo 'Usage %0 "binaries_path=path_to_binaries_dir"'
	exit /b 1
) else (
	set %1
	echo %binaries_path%
)

REM parsing the absolute path of this file to find PBS prefix directory
set PBS_prefix=''
@setlocal enableextensions enabledelayedexpansion
set variable=%~dp0
if "x!variable:~-29!"=="xpbspro\win_configure\msi\wix\" (
	set variable=!variable:~0,-29!
) else (
	echo "Failed to parse PBS prefix location"
	goto theend
)
set PBS_prefix=!variable!

REM Defining needed variables 
set WINBUILDDIR="%PBS_prefix%win_build"
set TOPDIR="%PBS_prefix%PBS"
set SRCDIR="%PBS_prefix%pbspro"
set HOMEDIR="%TOPDIR%\home"
set EXECDIR="%TOPDIR%\exec"

if exist %TOPDIR% (
	echo %TOPDIR% already available.. Deleting...
	rmdir /s /q %TOPDIR%
	if NOT %ERRORLEVEL% == 0 goto theend
)

echo Creating toplevel directories...
mkdir %TOPDIR% %HOMEDIR% %EXECDIR%
if NOT %ERRORLEVEL% == 0 goto theend
echo done

echo Creating bin directory and moving necessory files...
mkdir %EXECDIR%\bin
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%WINBUILDDIR%\src\cmds\Release\*.exe"
		"%WINBUILDDIR%\src\lib\Libpbspthread\Release\Libpbspthread.dll"
		"%SRCDIR%\src\cmds\scripts\*.bat"
		"%WINBUILDDIR%\src\tools\Release\*.exe"
		"%binaries_path%\tcltk\bin\*.dll"
	) do (
		xcopy /s /d "%%~a" "%EXECDIR%\bin" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
	REM Exclude list of files from bin directory
	For %%b in (
		"%EXECDIR%\bin\pbs_dataservice.bat"
		"%EXECDIR%\bin\pbs_ds_monitor.exe"
		"%EXECDIR%\bin\pbs_ds_password.exe"
	) do (
		del /s "%%~b" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %EXECDIR%\bin directory.
	goto theend
)

echo Creating sbin directory and moving necessory files...
mkdir %EXECDIR%\sbin
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%WINBUILDDIR%\src\server\Release\pbs_comm.exe"
		"%WINBUILDDIR%\src\iff\Release\*.exe"
		"%WINBUILDDIR%\src\tools\Release\pbs_ds_monitor.exe"
		"%WINBUILDDIR%\src\resmom\Release\*.exe*"
		"%WINBUILDDIR%\src\mom_rcp\Release\*.exe*"
		"%SRCDIR%\src\cmds\scripts\pbs_dataservice.bat"
		"%WINBUILDDIR%\src\mom_rshd\Release\*.exe"
		"%WINBUILDDIR%\src\cmds\Release\pbs_ds_password.exe"
		"%WINBUILDDIR%\src\scheduler\Release\*.exe"
		"%WINBUILDDIR%\src\send_job\Release\*.exe*"
		"%WINBUILDDIR%\src\send_hooks\Release\*.exe*"
		"%WINBUILDDIR%\src\server\Release\*.exe*"
		"%WINBUILDDIR%\src\start_provision\Release\*.exe*"
	) do (
		xcopy /s /d "%%~a" "%EXECDIR%\sbin" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %EXECDIR%\sbin directory.
	goto theend
)

echo Creating etc directory and moving necessory files...

mkdir %EXECDIR%\etc
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%SRCDIR%\src\scheduler\pbs_holidays.*"
		"%SRCDIR%\src\scheduler\pbs_dedicated"
		"%SRCDIR%\src\scheduler\pbs_holidays"
		"%SRCDIR%\src\scheduler\pbs_resource_group"
		"%SRCDIR%\src\scheduler\pbs_sched_config"
		"%SRCDIR%\src\cmds\scripts\pbs_db_schema.sql"
		"%SRCDIR%\src\cmds\scripts\win_postinstall.py"
	) do (
		xcopy /s /d "%%~a" "%EXECDIR%\etc" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %EXECDIR%\etc directory.
	goto theend
)

echo Creating include directory and moving necessory files...
mkdir %EXECDIR%\include
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%SRCDIR%\src\include\pbs_error.h"
		"%SRCDIR%\src\include\pbs_ifl.h"
		"%SRCDIR%\src\include\rm.h"
		"%SRCDIR%\src\include\tm_.h"
		"%SRCDIR%\src\include\tm.h"
		"%SRCDIR%\src\include\win.h"
	) do (
	xcopy /s /d "%%~a" "%EXECDIR%\include" > NUL
	if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %EXECDIR%\include directory.
	goto theend
)

echo Creating pgsql directory and moving necessory files...
mkdir %EXECDIR%\pgsql
if %ERRORLEVEL% == 0 (
	xcopy /s /d "%binaries_path%\pgsql\*" "%EXECDIR%\pgsql" > NUL
	if NOT %ERRORLEVEL% == 0 goto theend
) else (
	echo Failed to create %EXECDIR%\pgsql directory.
	goto theend
)

echo Creating python_x64 directory and moving necessory files...
mkdir %EXECDIR%\python_x64
if %ERRORLEVEL% == 0 (
	xcopy /s /d "%binaries_path%\python_x64\*.*" "%EXECDIR%\python_x64" > NUL
	if NOT %ERRORLEVEL% == 0 goto theend
) else (
	echo Failed to create %EXECDIR%\python_x64 directory.
	goto theend
)

echo Creating python directory and moving necessory files...
mkdir %EXECDIR%\python
if %ERRORLEVEL% == 0 (
	xcopy /s /d "%binaries_path%\python\*" "%EXECDIR%\python" > NUL
	if NOT %ERRORLEVEL% == 0 goto theend
) else (
	echo Failed to create %EXECDIR%\python directory.
	goto theend
)

echo Creating unsupported directory and moving necessory files...
mkdir %EXECDIR%\unsupported
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%WINBUILDDIR%\src\unsupported\Release\*.exe"
		"%SRCDIR%\src\unsupported\README"
		"%SRCDIR%\src\unsupported\*.pl"
		"%SRCDIR%\src\unsupported\*.py"
	) do (
		xcopy /s /d "%%~a" "%EXECDIR%\unsupported" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %EXECDIR%\unsupported directory.
	goto theend
)

echo Creating scheduler privilage in home directory...
mkdir %HOMEDIR%\sched_priv
if %ERRORLEVEL% == 0 (
	For %%a in (
		"%SRCDIR%\src\scheduler\pbs_dedicated"
		"%SRCDIR%\src\scheduler\pbs_holidays"
		"%SRCDIR%\src\scheduler\pbs_resource_group"
		"%SRCDIR%\src\scheduler\pbs_sched_config"
	) do (
		xcopy /s /d "%%~a" "%HOMEDIR%\sched_priv" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	)
) else (
	echo Failed to create %HOMEDIR%\sched_priv directory.
	goto theend
)

echo Creating lib in exec directory...
mkdir %EXECDIR%\lib
if %ERRORLEVEL% == 0 (
	mkdir %EXECDIR%\lib\python\altair\pbs
	if %ERRORLEVEL% == 0 (
		For %%a in (
			"%SRCDIR%\src\modules\python\pbs\*.py"
			"%SRCDIR%\src\modules\python\pbs\*.pyo"
			"%SRCDIR%\src\modules\python\pbs\*.pyc"			
		) do (
			xcopy /s /d "%%~a" "%EXECDIR%\lib\python\altair\pbs" > NUL
			if NOT %ERRORLEVEL% == 0 goto theend
		)
	) else (
		echo Failed to create %EXECDIR%\lib\python\altair\pbs directory.
		goto theend
	)
	
	mkdir %EXECDIR%\lib\python\altair\pbs\v1
	if %ERRORLEVEL% == 0 (
		For %%a in (
			"%SRCDIR%\src\modules\python\pbs\v1\*.py"
			"%SRCDIR%\src\modules\python\pbs\v1\*.pyo"
			"%SRCDIR%\src\modules\python\pbs\v1\*.pyc"	
			"%SRCDIR%\win_configure\projects.VS2008\*.py"
		) do (
			xcopy /s /d "%%~a" "%EXECDIR%\lib\python\altair\pbs\v1" > NUL
			if NOT %ERRORLEVEL% == 0 goto theend
		)
	) else (
		echo Failed to create %EXECDIR%\lib\python\altair\pbs\v1 directory.
		goto theend
	)

	mkdir %EXECDIR%\lib\python\python2.7
	if %ERRORLEVEL% == 0 (	
		For %%a in (
			"%binaries_path%\python\Lib\*.*"			
		) do (
			xcopy /d "%%~a" "%EXECDIR%\lib\python\python2.7\" > NUL
			if NOT %ERRORLEVEL% == 0 goto theend
		)	
	) else (
		echo Failed to create %EXECDIR%\lib\python\python2.7 directory.
		goto theend
	)
	
	For %%a in (
			"%WINBUILDDIR%\src\lib\Libattr\Release\Libattr.lib"
			"%WINBUILDDIR%\src\lib\Liblog\Release\Liblog.lib"
			"%WINBUILDDIR%\src\lib\Libnet\Release\Libnet.lib"
			"%WINBUILDDIR%\src\lib\Libpbs\Release\Libpbs.lib"
			"%WINBUILDDIR%\src\lib\Libsite\Release\Libsite.lib"
			"%WINBUILDDIR%\src\lib\Libwin\Release\Libwin.lib"
			"%binaries_path%\libical\bin\*.dll"
		) do (
			xcopy /s /d "%%~a" "%EXECDIR%\lib" > NUL
			if NOT %ERRORLEVEL% == 0 goto theend
		)
		
	mkdir %EXECDIR%\lib\ical\zoneinfo
	if %ERRORLEVEL% == 0 (
		xcopy /s /d "%binaries_path%\libical\share\libical\zoneinfo\*.*" "%EXECDIR%\lib\ical\zoneinfo" > NUL
		if NOT %ERRORLEVEL% == 0 goto theend
	) else (
		echo Failed to create %EXECDIR%\lib\ical\zoneinfo directory.
		goto theend
	)

) else (
	echo Failed to create %EXECDIR%\lib directory.
	goto theend
)

echo "Finished successfully"
exit /b

:theend
echo "Error: while preparing directory structure" 
exit /b
