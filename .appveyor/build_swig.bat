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

"%ENV_7Z_BIN%" x -y "%BINARIESDIR%\swigwin-%SWIG_VERSION%.zip" -o"%BINARIESDIR%"
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
