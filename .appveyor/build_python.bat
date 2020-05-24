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

if not defined PYTHON_VERSION (
    echo "Please set PYTHON_VERSION to Python version!"
    exit /b 1
)

if exist "%BINARIESDIR%\python" (
    echo "%BINARIESDIR%\python exist already!"
    goto :Do64
)
if exist C:\Python36 (
    xcopy /Y /V /J /S /Q C:\Python36 "%BINARIESDIR%\python\"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to copy Python 32bit from C:\Python36"
        exit /b 1
    )
) else if exist "%BINARIESDIR%\python.zip" (
    "%ENV_7Z_BIN%" x -y "%BINARIESDIR%\python.zip" -o"%BINARIESDIR%"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to extract %BINARIESDIR%\python.zip"
        exit /b 1
    )
    if not exist "%BINARIESDIR%\python" (
        echo "Could not find %BINARIESDIR%\python"
        exit /b 1
    )
) else (
    if not exist "%BINARIESDIR%\python-%PYTHON_VERSION%.exe" (
        "%CURL_BIN%" -qkL -o "%BINARIESDIR%\python-%PYTHON_VERSION%.exe" https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%.exe
        if not exist "%BINARIESDIR%\python-%PYTHON_VERSION%.exe" (
            echo "Failed to download python 32bit installer"
            exit /b 1
        )
    )
    start "" /b /wait "%BINARIESDIR%\python-%PYTHON_VERSION%.exe" /quiet InstallAllUsers=0 TargetDir="%BINARIESDIR%\python_install"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to install Python 32 bit"
        exit /b 1
    )
    1>nul xcopy /Y /V /J /S /Q "%BINARIESDIR%\python_install" "%BINARIESDIR%\python\"
    if not %ERRORLEVEL% == 0 (
        echo Failed to copy files from "%BINARIESDIR%\python_install" to "%BINARIESDIR%\python\"
        exit /b 1
    )
    start "" /b /wait "%BINARIESDIR%\python-%PYTHON_VERSION%.exe" /uninstall /quiet
    if not %ERRORLEVEL% == 0 (
        echo "Failed to uninstall Python 32 bit"
        exit /b 1
    )
)

set PIP_EXTRA_ARGS=
if exist "%BINARIESDIR%\pywin32-224-cp36-cp36m-win32.whl" (
    set PIP_EXTRA_ARGS=--no-index --find-links="%BINARIESDIR%" --no-cache-dir
)
"%BINARIESDIR%\python\python.exe" -m pip install %PIP_EXTRA_ARGS% pywin32==224
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pywin32 in %BINARIESDIR%\python for Python 32bit"
    exit /b 1
)

:Do64
REM Skip Python 64bit for Appveyor
if "%APPVEYOR%"=="True" (
    goto :DoDebug
)

if exist "%BINARIESDIR%\python_x64" (
    echo "%BINARIESDIR%\python_x64 exist already!"
    goto :DoDebug
)

if exist C:\Python36-x64 (
    xcopy /Y /V /J /S /Q C:\Python36-x64 "%BINARIESDIR%\python_x64\"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to copy Python 64bit from C:\Python36-x64"
        exit /b 1
    )
) else if exist "%BINARIESDIR%\python_x64.zip" (
    "%ENV_7Z_BIN%" x -y "%BINARIESDIR%\python_x64.zip" -o"%BINARIESDIR%"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to extract %BINARIESDIR%\python_x64.zip"
        exit /b 1
    )
    if not exist "%BINARIESDIR%\python_x64" (
        echo "Could not find %BINARIESDIR%\python_x64"
        exit /b 1
    )
) else (
    if not exist "%BINARIESDIR%\python-%PYTHON_VERSION%-amd64.exe" (
        "%CURL_BIN%" -qkL -o "%BINARIESDIR%\python-%PYTHON_VERSION%-amd64.exe" https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe
        if not exist "%BINARIESDIR%\python-%PYTHON_VERSION%-amd64.exe" (
            echo "Failed to download python 64bit installer"
            exit /b 1
        )
    )
    start "" /b /wait "%BINARIESDIR%\python-%PYTHON_VERSION%-amd64.exe" /quiet InstallAllUsers=0 TargetDir="%BINARIESDIR%\python_install"
    if not %ERRORLEVEL% == 0 (
        echo "Failed to install Python 64 bit"
        exit /b 1
    )
    1>nul xcopy /Y /V /J /S /Q "%BINARIESDIR%\python_install" "%BINARIESDIR%\python_x64\"
    if not %ERRORLEVEL% == 0 (
        echo Failed to copy files from "%BINARIESDIR%\python_install" to "%BINARIESDIR%\python_x64\"
        exit /b 1
    )
    start "" /b /wait "%BINARIESDIR%\python-%PYTHON_VERSION%-amd64.exe" /uninstall /quiet
    if not %ERRORLEVEL% == 0 (
        echo "Failed to uninstall Python 64 bit"
        exit /b 1
    )
)

set PIP_EXTRA_ARGS=
if exist "%BINARIESDIR%\pywin32-224-cp36-cp36m-win_amd64.whl" (
    set PIP_EXTRA_ARGS=--no-index --find-links="%BINARIESDIR%" --no-cache-dir
)
"%BINARIESDIR%\python_x64\python.exe" -m pip install %PIP_EXTRA_ARGS% pywin32==224
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pywin32 in %BINARIESDIR%\python_x64 for Python 64bit"
    exit /b 1
)

:DoDebug
if %DO_DEBUG_BUILD% EQU 0 (
    echo "You are in Release mode so no need of Python debug build, skipping Python debug build"
    exit /b 0
)
if exist "%BINARIESDIR%\python_debug" (
    echo "%BINARIESDIR%\python_debug exist already!"
    exit /b 0
)

if not exist "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" (
    "%CURL_BIN%" -qkL -o "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" https://github.com/python/cpython/archive/v%PYTHON_VERSION%.zip
    if not exist "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" (
        echo "Failed to download python"
        exit /b 1
    )
)
2>nul rd /S /Q "%BINARIESDIR%\cpython-%PYTHON_VERSION%"

"%ENV_7Z_BIN%" x -y "%BINARIESDIR%\cpython-%PYTHON_VERSION%.zip" -o"%BINARIESDIR%"
cd "%BINARIESDIR%\cpython-%PYTHON_VERSION%"

REM dirty hack to make python build faster as we only want pythoncore project's output
1>nul copy /B /Y "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj" "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj.back"
1>nul copy /B /Y "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pythoncode.vcxproj" "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj"

set IncludeExternals=false
call "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\build.bat" -d --no-tkinter --no-ssl
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile Python debug version"
    exit /b 1
)

REM restore pcbuild.proj file
1>nul copy /B /Y "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj.back" "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj"
1>nul 2>nul del /Q /F "%BINARIESDIR%\cpython-%PYTHON_VERSION%\PCbuild\pcbuild.proj.back"

cd "%BINARIESDIR%"
ren "cpython-%PYTHON_VERSION%" python_debug
if not %ERRORLEVEL% == 0 (
    echo "Failed to rename %BINARIESDIR%\cpython-%PYTHON_VERSION% to python_debug"
    exit /b 1
)

exit /b 0
