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

@echo on
setlocal

call "%~dp0set_paths.bat" %~1

cd "%BINARIESDIR%"

if not defined LIBEDIT_VERSION (
    echo "Please set LIBEDIT_VERSION to editline version!"
    exit /b 1
)

set LIBEDIT_DIR_NAME=libedit
set BUILD_TYPE=Release
if %DO_DEBUG_BUILD% EQU 1 (
    set LIBEDIT_DIR_NAME=libedit_debug
    set BUILD_TYPE=Debug
)

if exist "%BINARIESDIR%\%LIBEDIT_DIR_NAME%" (
    echo "%BINARIESDIR%\%LIBEDIT_DIR_NAME% exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%.zip" https://sourceforge.net/projects/mingweditline/files/wineditline-%LIBEDIT_VERSION%.zip/download
    if not exist "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%.zip" (
        echo "Failed to download libedit"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%"

"%ENV_7Z_BIN%" x -y "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%.zip" -o"%BINARIESDIR%"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\wineditline-%LIBEDIT_VERSION%.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%" (
    echo "Could not find %BINARIESDIR%\wineditline-%LIBEDIT_VERSION%"
    exit /b 1
)

2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\build"
2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\bin32"
2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\lib32"
2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\include"
mkdir "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\build"

call "%VS150COMNTOOLS%VsDevCmd.bat"

cd "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%\build" && %CMAKE_BIN% -DLIB_SUFFIX=32 -DMSVC_USE_STATIC_RUNTIME=OFF -DCMAKE_BUILD_TYPE=%BUILD_TYPE% -G "NMake Makefiles" ..
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for libedit"
    exit /b 1
)

nmake
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile libedit"
    exit /b 1
)

nmake install
if not %ERRORLEVEL% == 0 (
    echo "Failed to install libedit"
    exit /b 1
)

2>nul mkdir "%BINARIESDIR%\%LIBEDIT_DIR_NAME%" && cd "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%"
if %ERRORLEVEL% == 0 (
    for %%f in (bin32 include lib32) do (
        robocopy /S %%f "%BINARIESDIR%\%LIBEDIT_DIR_NAME%\%%f"
        if %ERRORLEVEL% GTR 1 (
            goto exitloop
        ) else (
           set ERRORLEVEL=0
        )
    )
)
:exitloop
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy bin32, include and lib32 from %BINARIESDIR%\wineditline-%LIBEDIT_VERSION% to %BINARIESDIR%\%LIBEDIT_DIR_NAME%"
    exit /b 1
)

cd "%BINARIESDIR%"
2>nul rd /S /Q "%BINARIESDIR%\wineditline-%LIBEDIT_VERSION%"

exit /b 0
