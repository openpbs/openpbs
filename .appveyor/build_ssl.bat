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
"%UNZIP_BIN%" -q "%BINARIESDIR%\OpenSSL_%OPENSSL_VERSION%.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"
    exit /b 1
)
if not exist "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%" (
    echo "Could not find %BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"
    exit /b 1
)

cd "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"

call "%VS90COMNTOOLS%vsvars32.bat

if %DO_DEBUG_BUILD% EQU 1 (
    "%PERL_BIN%" "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%\Configure" --prefix="%BINARIESDIR%\%OPENSSL_DIR_NAME%" --debug VC-WIN32 no-asm no-shared
) else (
    "%PERL_BIN%" "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%\Configure" --prefix="%BINARIESDIR%\%OPENSSL_DIR_NAME%" VC-WIN32 no-asm no-shared
)
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for openssl"
    exit /b 1
)

nmake
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile openssl"
    exit /b 1
)

nmake install
if not %ERRORLEVEL% == 0 (
    echo "Failed to install openssl"
    exit /b 1
)

cd "%BINARIESDIR%"
2>nul rd /S /Q "%BINARIESDIR%\openssl-OpenSSL_%OPENSSL_VERSION%"

exit /b 0

