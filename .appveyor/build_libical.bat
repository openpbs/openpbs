@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\libical" (
    echo "%BINARIESDIR%\libical exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\libical-1.0.1.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\libical-1.0.1.zip" https://github.com/libical/libical/archive/v1.0.1.zip
    if not exist "%BUILDDIR%\libical-1.0.1.zip" (
        echo "Failed to download libical"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\libical-1.0.1"
"%UNZIP_BIN%" -q "%BUILDDIR%\libical-1.0.1.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\libical-1.0.1.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\libical-1.0.1" (
    echo "Could not find %BUILDDIR%\libical-1.0.1"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\libical-1.0.1\build"
mkdir "%BUILDDIR%\libical-1.0.1\build"
cd "%BUILDDIR%\libical-1.0.1\build"

call "%VS90COMNTOOLS%vsvars32.bat"

"%CMAKE_BIN%" -DCMAKE_INSTALL_PREFIX="%BINARIESDIR%\libical" -G "NMake Makefiles" ..
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for libical"
    exit /b 1
)
nmake
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile libical"
    exit /b 1
)
nmake install
if not %ERRORLEVEL% == 0 (
    echo "Failed to install libical"
    exit /b 1
)

exit /b 0

