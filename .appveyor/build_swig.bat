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

if exist "%BINARIESDIR%\python\python.exe" (
    echo "Found Python installation at %BINARIESDIR%\python, using it to add Python support in swig"
    set PYTHON_INSTALL_DIR="%BINARIESDIR_M%/python/python.exe"
) else if exist "C:\Python27\python.exe" (
    echo "Found Python installation at C:\Python27, using it to add Python support in swig"
    set PYTHON_INSTALL_DIR=/c/Python27/python.exe
) else (
    echo "Could not find Python installation, required to add Python support in swig"
    exit /b 1
)

if not exist "%BINARIESDIR%\swig-rel-%SWIG_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\swig-rel-%SWIG_VERSION%.zip" https://github.com/swig/swig/archive/rel-%SWIG_VERSION%.zip
    if not exist "%BINARIESDIR%\swig-rel-%SWIG_VERSION%.zip" (
        echo "Failed to download swig"
        exit /b 1
    )
)
REM CCCL is Unix cc compiler to Microsoft's cl compiler wrapper
REM and it is require to generate native swig windows binary which doesn't depend on any of MinGW DLLs
if not exist "%BINARIESDIR%\cccl-1.0.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\cccl-1.0.zip" https://github.com/swig/cccl/archive/cccl-1.0.zip
    if not exist "%BINARIESDIR%\cccl-1.0.zip" (
        echo "Failed to download cccl"
        exit /b 1
    )
)

2>nul rd /S /Q "%BINARIESDIR%\cccl-cccl-1.0"
"%UNZIP_BIN%" -q "%BINARIESDIR%\cccl-1.0.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\cccl-1.0.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\cccl-cccl-1.0" (
    echo "Could not find %BINARIESDIR%\cccl-cccl-1.0"
    exit /b 1
)
if not exist "%BINARIESDIR%\cccl-cccl-1.0\cccl" (
    echo "Could not find %BINARIESDIR%\cccl-cccl-1.0\cccl"
    exit /b 1
)

2>nul rd /S /Q "%BINARIESDIR%\swig-rel-%SWIG_VERSION%"
"%UNZIP_BIN%" -q "%BINARIESDIR%\swig-rel-%SWIG_VERSION%.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BINARIESDIR%\swig-rel-%SWIG_VERSION%.zip"
    exit /b 1
)
if not exist "%BINARIESDIR%\swig-rel-%SWIG_VERSION%" (
    echo "Could not find %BINARIESDIR%\swig-rel-%SWIG_VERSION%"
    exit /b 1
)

call "%VS90COMNTOOLS%\vsvars32.bat

"%MSYSDIR%\bin\bash" --login -i -c "cp -f \"$BINARIESDIR_M/cccl-cccl-1.0/cccl\" /usr/bin/cccl && chmod +x /usr/bin/cccl"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy cccl from %BINARIESDIR%\cccl-cccl-1.0\cccl to /usr/bin/cccl in MSYS bash"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/swig-rel-$SWIG_VERSION\" && ./autogen.sh"
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate configure for swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/swig-rel-$SWIG_VERSION\" && ./configure CC=cccl CXX=cccl CFLAGS='-O2' CXXFLAGS='-O2' LDFLAGS='--cccl-link /LTCG' --prefix=\"$BINARIESDIR_M/swig\" --without-alllang --with-python=\"$PYTHON_INSTALL_DIR\" --disable-dependency-tracking --disable-ccache --without-pcre"
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/swig-rel-$SWIG_VERSION\" && make"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd \"$BINARIESDIR_M/swig-rel-$SWIG_VERSION\" && make install"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install swig"
    exit /b 1
)

cd "%BINARIESDIR%"
2>nul rd /S /Q "%BINARIESDIR%\cccl-cccl-1.0"
2>nul rd /S /Q "%BINARIESDIR%\swig-rel-%SWIG_VERSION%"

exit /b 0

