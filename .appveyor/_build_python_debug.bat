@echo off
REM Copyright (C) 1994-2019 Altair Engineering, Inc.
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

@echo on
setlocal

call "%~dp0set_paths.bat" %~1

cd "%BINARIESDIR%"

if not defined PYTHON_VERSION (
    echo "Please set PYTHON_VERSION to Python version!"
    exit /b 1
)

if %DO_DEBUG_BUILD% EQU 0 (
    echo "You are in Release mode so no need of Python debug build, skipping Python debug build"
    exit /b 0
)

if exist "%BINARIESDIR%\python_debug" (
    echo "%BINARIESDIR%\python_debug exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" https://github.com/python/cpython/archive/v%PYTHON_VERSION%.zip
    if not exist "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" (
        echo "Failed to download python"
        exit /b 1
    )
)
2>nul rd /S /Q "%BINARIESDIR%\cpython-%PYTHON_VERSION%"
"%UNZIP_BIN%" -q "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip"
cd "%BINARIESDIR%\cpython-%PYTHON_VERSION%"

REM Restore externals directory if python_externals.tar.gz exists
if exist "%BINARIESDIR%\python_externals.tar.gz" (
    if not exist "%BINARIESDIR%\cpython-%PYTHON_VERSION%\externals" (
        "%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/cpython-$PYTHON_VERSION\" && tar -xf \"$BINARIESDIR_M/python_externals.tar.gz\""
    )
)

REM Patch python source to make it purify compatible
REM this patch is same as compiling python with '--without-pymalloc' in Linux
REM but unfortunately in windows we don't have command line option like Linux
"%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/cpython-$PYTHON_VERSION\" && sed -i 's/#define WITH_PYMALLOC 1//g' PC/pyconfig.h"

call "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\env.bat" x86

call "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PC\VS9.0\build.bat" -e -d
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile Python debug version"
    exit /b 1
)

REM Since Python debug mode doesn't have msi generation part so we need to copy whole source directory
cd "%BINARIESDIR%"
ren "%BINARIESDIR%\cpython-%PYTHON_VERSION%" python_debug

exit /b 0

