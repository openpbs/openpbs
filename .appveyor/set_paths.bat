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

@echo off
set __OLD_DIR="%CD%"
cd "%~dp0..\.."

if not defined CURL_BIN (
    set CURL_BIN=curl
)
if not defined PERL_BIN (
    set PERL_BIN=perl
)
if not defined CMAKE_BIN (
    set CMAKE_BIN=cmake
)

if not defined ENV_7Z_BIN (
    set ENV_7Z_BIN=7z
)

if not defined __BINARIESDIR (
    set __BINARIESDIR=%CD%\binaries
)

if not defined APPVEYOR (
    set APPVEYOR=False
)

if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\Professional" (
    set "VS150COMNTOOLS=C:\Program Files (x86)\Microsoft Visual Studio\2017\Professional\Common7\Tools\"
) else if exist "C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise" (
    set "VS150COMNTOOLS=C:\Program Files (x86)\Microsoft Visual Studio\2017\Enterprise\Common7\Tools\"
) else (
    set "VS150COMNTOOLS=C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\Common7\Tools\"
)

if not exist "%VS150COMNTOOLS%" (
    echo "Could not find VS2017 common tools"
    exit 1
)

set __RANDOM_VAL=%RANDOM::=_%
set __RANDOM_VAL-%RANDOM_VAL:.=%
set __BINARIESJUNCTION=%__BINARIESDIR:~0,2%\__withoutspace_binariesdir_%__RANDOM_VAL%
if not exist "%__BINARIESDIR%" (
    mkdir "%__BINARIESDIR%"
)
if not "%__BINARIESDIR: =%"=="%__BINARIESDIR%" (
    mklink /J %__BINARIESJUNCTION% "%__BINARIESDIR%"
    if not %ERRORLEVEL% == 0 (
        echo "Could not create junction to %__BINARIESJUNCTION% to %__BINARIESDIR% which contains space"
        exit 1
    )
    cd %__BINARIESJUNCTION%
) else (
    cd %__BINARIESDIR%
)
set BINARIESDIR=%CD%

if not defined LIBEDIT_VERSION (
    set LIBEDIT_VERSION=2.205
)
if not defined PYTHON_VERSION (
    set PYTHON_VERSION=3.6.8
)
if not defined OPENSSL_VERSION (
    set OPENSSL_VERSION=1_1_0j
)
if not defined ZLIB_VERSION (
    set ZLIB_VERSION=1.2.11
)
if not defined SWIG_VERSION (
    set SWIG_VERSION=4.0.1
)

set DO_DEBUG_BUILD=0
if "%~1"=="debug" (
    set DO_DEBUG_BUILD=1
)
if "%~1"=="Debug" (
    set DO_DEBUG_BUILD=1
)

cd %__OLD_DIR%
