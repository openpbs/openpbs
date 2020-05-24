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

if not defined ZLIB_VERSION (
    echo "Please set ZLIB_VERSION to zlib version!"
    exit /b 1
)

if exist "%BINARIESDIR%\zlib" (
    echo "%BINARIESDIR%\zlib already exists!"
    exit /b 0
)

if not exist "%BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz" https://www.zlib.net/zlib-%ZLIB_VERSION%.tar.gz
    if not exist "%BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz" (
        echo "Failed to download zlib"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\zlib-%ZLIB_VERSION%"

"%ENV_7Z_BIN%" x -y "%BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz" -so | "%ENV_7Z_BIN%" x -y -aoa -si -ttar -o"%BINARIESDIR%"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz"
    exit /b 1
)
if not exist "%BINARIESDIR%\zlib-%ZLIB_VERSION%" (
    echo "Failed to extract %BINARIESDIR%\zlib-%ZLIB_VERSION%.tar"
    exit /b 1
)

call "%VS150COMNTOOLS%VsDevCmd.bat"

cd "%BINARIESDIR%\zlib-%ZLIB_VERSION%

nmake /f win32/Makefile.msc
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile zlib"
    exit /b 1
)
cd "%BINARIESDIR%"
ren "zlib-%ZLIB_VERSION%" zlib
if not %ERRORLEVEL% == 0 (
    echo "Failed to rename zlib-%ZLIB_VERSION% to zlib"
    exit /b 1
)
exit /b 0
