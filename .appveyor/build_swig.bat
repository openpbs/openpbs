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

if not defined SWIG_VERSION (
    echo "Please set SWIG_VERSION to Swig version!"
    exit /b 1
)

if exist "%BINARIESDIR%\swig" (
    echo "%BINARIESDIR%\swig exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\swigwin-%SWIG_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\swigwin-%SWIG_VERSION%.zip" http://prdownloads.sourceforge.net/swig/swigwin-%SWIG_VERSION%.zip
    if not exist "%BINARIESDIR%\swigwin-%SWIG_VERSION%.zip" (
        echo "Failed to download swig"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\swigwin-%SWIG_VERSION%"
7z x -y "%BINARIESDIR%\swigwin-%SWIG_VERSION%.zip" -o"%BINARIESDIR%"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\swigwin-%SWIG_VERSION%.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\swigwin-%SWIG_VERSION%" (
    echo "Could not find %BINARIESDIR%\swigwin-%SWIG_VERSION%"
    exit /b 1
)

cd "%BINARIESDIR%"
ren "swigwin-%SWIG_VERSION%" swig
if not %ERRORLEVEL% == 0 (
    echo "Failed to rename swigwin-%SWIG_VERSION% to swig"
    exit /b 1
)
exit /b 0
