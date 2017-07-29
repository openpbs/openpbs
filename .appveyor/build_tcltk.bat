@echo off
REM Copyright (C) 1994-2017 Altair Engineering, Inc.
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

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if not defined TCL_VERSION (
    echo "Please set TCL_VERSION to Tcl version!"
    exit /b 1
)
if not defined TK_VERSION (
    echo "Please set TK_VERSION to Tk version!"
    exit /b 1
)

if exist "%BINARIESDIR%\tcltk" (
    echo "%BINARIESDIR%\tcltk exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\tcl%TCL_VERSION:.=%-src.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\tcl%TCL_VERSION:.=%-src.zip" https://sourceforge.net/projects/tcl/files/Tcl/%TCL_VERSION%/tcl%TCL_VERSION:.=%-src.zip/download
    if not exist "%BUILDDIR%\tcl%TCL_VERSION:.=%-src.zip" (
        echo "Failed to download tcl"
        exit /b 1
    )
)
if not exist "%BUILDDIR%\tk%TK_VERSION:.=%-src.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\tk%TK_VERSION:.=%-src.zip" https://sourceforge.net/projects/tcl/files/Tcl/%TK_VERSION%/tk%TK_VERSION:.=%-src.zip/download
    if not exist "%BUILDDIR%\tk%TK_VERSION:.=%-src.zip" (
        echo "Failed to download tk"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\tcl%TCL_VERSION%"
"%UNZIP_BIN%" -q "%BUILDDIR%\tcl%TCL_VERSION:.=%-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\tcl%TCL_VERSION:.=%-src.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\tcl%TCL_VERSION%" (
    echo "Could not find %BUILDDIR%\tcl%TCL_VERSION%"
    exit /b 1
)
if not exist "%BUILDDIR%\tcl%TCL_VERSION%\win" (
    echo "Could not find %BUILDDIR%\tcl%TCL_VERSION%\win"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\tk%TK_VERSION%"
"%UNZIP_BIN%" -q "%BUILDDIR%\tk%TK_VERSION:.=%-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\tk%TK_VERSION:.=%-src.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\tk%TK_VERSION%" (
    echo "Could not find %BUILDDIR%\tk%TK_VERSION%"
    exit /b 1
)
if not exist "%BUILDDIR%\tk%TK_VERSION%\win" (
    echo "Could not find %BUILDDIR%\tk%TK_VERSION%\win"
    exit /b 1
)

call "%VS90COMNTOOLS%vsvars32.bat"

cd  "%BUILDDIR%\tcl%TCL_VERSION%\win"
nmake /f "%BUILDDIR%\tcl%TCL_VERSION%\win\makefile.vc"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tcl"
    exit /b 1
)
nmake /f "%BUILDDIR%\tcl%TCL_VERSION%\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\tcltk"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tcl"
    exit /b 1
)

cd "%BUILDDIR%\tk%TK_VERSION%\win"
set TCLDIR=%BUILDDIR%\tcl%TCL_VERSION%
nmake /f "%BUILDDIR%\tk%TK_VERSION%\win\makefile.vc"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tk"
    exit /b 1
)
nmake /f "%BUILDDIR%\tk%TK_VERSION%\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\tcltk"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tk"
    exit /b 1
)

exit /b 0
