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
7z x -y "%BINARIESDIR%\zlib-%ZLIB_VERSION%.tar.gz" -so | 7z x -y -aoa -si -ttar -o"%BINARIESDIR%"
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
