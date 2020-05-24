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

if not defined OPENSSL_VERSION (
    echo "Please set OPENSSL_VERSION to OpenSSL version!"
    exit /b 1
)

set OPENSSL_DIR_NAME=openssl
if %DO_DEBUG_BUILD% EQU 1 (
    set OPENSSL_DIR_NAME=openssl_debug
)

if exist "%BINARIESDIR%\%OPENSSL_DIR_NAME%" (
    echo "%BINARIESDIR%\%OPENSSL_DIR_NAME% exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\OpenSSL_%OPENSSL_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\OpenSSL_%OPENSSL_VERSION%.zip" https://github.com/openssl/openssl/archive/OpenSSL_%OPENSSL_VERSION%.zip
    if not exist "%BINARIESDIR%\OpenSSL_%OPENSSL_VERSION%.zip" (
        echo "Failed to download openssl"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"

"%ENV_7Z_BIN%" x -y "%BINARIESDIR%\OpenSSL_%OPENSSL_VERSION%.zip" -o"%BINARIESDIR%"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"
    exit /b 1
)
if not exist "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%" (
    echo "Could not find %BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"
    exit /b 1
)

cd "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"

call "%VS150COMNTOOLS%VsDevCmd.bat"

if %DO_DEBUG_BUILD% EQU 1 (
    "%PERL_BIN%" "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%\Configure" --prefix="%BINARIESDIR%\%OPENSSL_DIR_NAME%" --debug VC-WIN32 no-asm no-shared
) else (
    "%PERL_BIN%" "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%\Configure" --prefix="%BINARIESDIR%\%OPENSSL_DIR_NAME%" VC-WIN32 no-asm no-shared
)

if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for openssl"
    exit /b 1
)

nmake install_dev
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile and install libcrypto.lib from openssl"
    exit /b 1
)

cd "%BINARIESDIR%"
2>nul rd /S /Q "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"

exit /b 0
