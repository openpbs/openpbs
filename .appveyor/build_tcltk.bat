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

if not defined TCL_VERSION (
    echo "Please set TCL_VERSION to Tcl version!"
    exit /b 1
)
if not defined TK_VERSION (
    echo "Please set TK_VERSION to Tk version!"
    exit /b 1
)

set TCLTK_DIR_NAME=tcltk
if %DO_DEBUG_BUILD% EQU 1 (
    set TCLTK_DIR_NAME=tcltk_debug
)
set PGSQL_DIR_NAME=pgsql
if %DO_DEBUG_BUILD% EQU 1 (
    set PGSQL_DIR_NAME=pgsql_debug
)

if exist "%BINARIESDIR%\%TCLTK_DIR_NAME%" (
    echo "%BINARIESDIR%\%TCLTK_DIR_NAME% exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\tcl%TCL_VERSION:.=%-src.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\tcl%TCL_VERSION:.=%-src.zip" https://sourceforge.net/projects/tcl/files/Tcl/%TCL_VERSION%/tcl%TCL_VERSION:.=%-src.zip/download
    if not exist "%BINARIESDIR%\tcl%TCL_VERSION:.=%-src.zip" (
        echo "Failed to download tcl"
        exit /b 1
    )
)
if not exist "%BINARIESDIR%\tk%TK_VERSION:.=%-src.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\tk%TK_VERSION:.=%-src.zip" https://sourceforge.net/projects/tcl/files/Tcl/%TK_VERSION%/tk%TK_VERSION:.=%-src.zip/download
    if not exist "%BINARIESDIR%\tk%TK_VERSION:.=%-src.zip" (
        echo "Failed to download tk"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\tcl%TCL_VERSION%"
"%UNZIP_BIN%" -q "%BINARIESDIR%\tcl%TCL_VERSION:.=%-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\tcl%TCL_VERSION:.=%-src.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\tcl%TCL_VERSION%" (
    echo "Could not find %BINARIESDIR%\tcl%TCL_VERSION%"
    exit /b 1
)
if not exist "%BINARIESDIR%\tcl%TCL_VERSION%\win" (
    echo "Could not find %BINARIESDIR%\tcl%TCL_VERSION%\win"
    exit /b 1
)

2>nul rd /S /Q "%BINARIESDIR%\tk%TK_VERSION%"
"%UNZIP_BIN%" -q "%BINARIESDIR%\tk%TK_VERSION:.=%-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\tk%TK_VERSION:.=%-src.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\tk%TK_VERSION%" (
    echo "Could not find %BINARIESDIR%\tk%TK_VERSION%"
    exit /b 1
)
if not exist "%BINARIESDIR%\tk%TK_VERSION%\win" (
    echo "Could not find %BINARIESDIR%\tk%TK_VERSION%\win"
    exit /b 1
)

call "%VS90COMNTOOLS%vsvars32.bat"

cd  "%BINARIESDIR%\tcl%TCL_VERSION%\win"
if %DO_DEBUG_BUILD% EQU 1 (
    nmake /f "%BINARIESDIR%\tcl%TCL_VERSION%\win\makefile.vc" OPTS=symbols
) else (
    nmake /f "%BINARIESDIR%\tcl%TCL_VERSION%\win\makefile.vc"
)
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tcl"
    exit /b 1
)
if %DO_DEBUG_BUILD% EQU 1 (
    nmake /f "%BINARIESDIR%\tcl%TCL_VERSION%\win\makefile.vc" install OPTS=symbols INSTALLDIR="%BINARIESDIR%\%TCLTK_DIR_NAME%"
) else (
    nmake /f "%BINARIESDIR%\tcl%TCL_VERSION%\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\%TCLTK_DIR_NAME%"
)
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tcl"
    exit /b 1
)

cd "%BINARIESDIR%\tk%TK_VERSION%\win"
set TCLDIR=%BINARIESDIR%\tcl%TCL_VERSION%
if %DO_DEBUG_BUILD% EQU 1 (
    nmake /f "%BINARIESDIR%\tk%TK_VERSION%\win\makefile.vc" OPTS=symbols
) else (
    nmake /f "%BINARIESDIR%\tk%TK_VERSION%\win\makefile.vc"
)
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tk"
    exit /b 1
)
if %DO_DEBUG_BUILD% EQU 1 (
    nmake /f "%BINARIESDIR%\tk%TK_VERSION%\win\makefile.vc" install OPTS=symbols INSTALLDIR="%BINARIESDIR%\%TCLTK_DIR_NAME%"
) else (
    nmake /f "%BINARIESDIR%\tk%TK_VERSION%\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\%TCLTK_DIR_NAME%"
)
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tk"
    exit /b 1
)

cd "%BINARIESDIR%"
2>nul rd /S /Q "%BINARIESDIR%\tcl%TCL_VERSION%"
2>nul rd /S /Q "%BINARIESDIR%\tk%TK_VERSION%"

exit /b 0
