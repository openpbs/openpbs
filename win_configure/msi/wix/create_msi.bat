REM Copyright (C) 1994-2018 Altair Engineering, Inc.
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
REM WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
REM FOR A PARTICULAR PURPOSE.
REM See the GNU Affero General Public License for more details.
REM
REM You should have received a copy of the GNU Affero General Public License
REM along with this program.  If not, see <http://www.gnu.org/licenses/>.
REM
REM Commercial License Information:
REM
REM For a copy of the commercial license terms and conditions,
REM go to: (http://www.pbspro.com/UserArea/agreement.html)
REM or contact the Altair Legal Department.
REM
REM Altair’s dual-license business model allows companies, individuals, and
REM organizations to create proprietary derivative works of PBS Pro and
REM distribute them - whether embedded or bundled with other software -
REM under a commercial license agreement.
REM
REM Use of Altair’s trademarks, including but not limited to "PBS™",
REM "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
REM trademark licensing policies.
setlocal
@echo on

cd "%~dp0..\..\..\..\"
set PBS_RESOURCES=%~dp0resources
set PBS_DIR=%CD%\PBS
set PBS_EXECDIR=%CD%\PBS\exec
set PBS_SPEC_FILE=%CD%\pbspro\pbspro.spec
set PBS_VERSION=""
set PBS_SHORT_VERSION=""
set PBS_PRODUCT_NAME=PBS Pro
set PBS_MSI_NAME=PBSPro
set BUILD_TYPE=Release
if not "%~1"=="" (
    set BUILD_TYPE=%~1
)
if "%BUILD_TYPE%"=="debug" (
    set BUILD_TYPE=Debug
)
cd win_build

if not exist "%PBS_EXECDIR%\etc\vcredist_x86.exe" (
    echo Could not find "%PBS_EXECDIR%\etc\vcredist_x86.exe"
    exit /b 1
)

if not exist "%CD%\msi" (
    mkdir "%CD%\msi"
)

cd "%CD%\msi"

REM Find PBSPro version from pbspro.spec file from root directory
for /F "tokens=3 USEBACKQ" %%F IN (`findstr /l /c:" pbs_version " %PBS_SPEC_FILE%`) DO (
    set PBS_VERSION=%%F
)
for /F "tokens=1-3 delims=." %%F IN ("%PBS_VERSION%") DO (
    set PBS_SHORT_VERSION=%%F.%%G.%%H
)

set PBS_PRODUCT_NAME=%PBS_PRODUCT_NAME% %PBS_VERSION%
set PBS_MSI_NAME=%PBS_MSI_NAME%_%PBS_VERSION%
if "%BUILD_TYPE%"=="Debug" (
    set PBS_PRODUCT_NAME=%PBS_PRODUCT_NAME% - Debug Version
    set PBS_MSI_NAME=%PBS_MSI_NAME%_debug_version
)

REM Clean up previouly generated files (if any)
2>nul del /Q /F %PBS_MSI_NAME%.msi
2>nul del /Q /F %PBS_MSI_NAME%.wixpdb
2>nul del /Q /F pbsproexec_%BUILD_TYPE%.wxs
2>nul del /Q /F pbsproexec_%BUILD_TYPE%.wixobj
2>nul del /Q /F Product.wixobj

REM Call Wix harvestor to generate pbsproexec.wxs
heat dir "%PBS_EXECDIR%" -ag -cg pbsproexec -sfrag -sreg -template fragment -out pbsproexec_%BUILD_TYPE%.wxs -dr "INSTALLFOLDER" -var var.pbs_execdir
if not %ERRORLEVEL% == 0 (
    echo Failed to generate pbsproexec_%BUILD_TYPE%.wxs
    exit /b 1
)

REM Call wix compiler to generate pbsproexec.wixobj and Product.wixobj
candle -ext WixUIExtension -d"pbs_execdir=%PBS_EXECDIR%" -d"pbs_product_name=%PBS_PRODUCT_NAME%" -d"pbs_short_version=%PBS_SHORT_VERSION%" -d"pbs_resources=%PBS_RESOURCES%" "%~dp0Product.wxs" pbsproexec_%BUILD_TYPE%.wxs
if not %ERRORLEVEL% == 0 (
    echo Failed to generate pbsproexec_%BUILD_TYPE%.wixobj and Product.wixobj
    exit /b 1
)

REM Call Wix linker to generate PBSPro msi
light -ext WixUIExtension -o %PBS_MSI_NAME%.msi pbsproexec_%BUILD_TYPE%.wixobj Product.wixobj
if not %ERRORLEVEL% == 0 (
    echo Failed to generate PBSPro msi
    exit /b 1
)

2>nul rd /S /Q "%PBS_DIR%"

exit /b 0
