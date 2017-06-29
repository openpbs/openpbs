@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\libedit" (
    echo "%BINARIESDIR%\libedit exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\wineditline-2.201.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\wineditline-2.201.zip" https://sourceforge.net/projects/mingweditline/files/wineditline-2.201.zip/download
    if not exist "%BUILDDIR%\wineditline-2.201.zip" (
        echo "Failed to download libedit"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\wineditline-2.201"
"%UNZIP_BIN%" -q "%BUILDDIR%\wineditline-2.201.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\wineditline-2.201.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\wineditline-2.201" (
    echo "Could not find %BUILDDIR%\wineditline-2.201"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\wineditline-2.201\build"
2>nul rd /S /Q "%BUILDDIR%\wineditline-2.201\bin32"
2>nul rd /S /Q "%BUILDDIR%\wineditline-2.201\lib32"
2>nul rd /S /Q "%BUILDDIR%\wineditline-2.201\include"
mkdir "%BUILDDIR%\wineditline-2.201\build"

"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/wineditline-2.201/build && $CMAKE_BIN -DLIB_SUFFIX=32 -G \"MSYS Makefiles\" .."
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for libedit"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/wineditline-2.201/build && make"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile libedit"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/wineditline-2.201/build && make install"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install libedit"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "mkdir -p $BINARIESDIR_M/libedit && cd $BUILDDIR_M/wineditline-2.201/ && cp -rfv bin32 include lib32 $BINARIESDIR_M/libedit/"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy bin32, include and lib32 from %BUILDDIR%\wineditline-2.201 to %BINARIESDIR%\libedit"
    exit /b 1
)

exit /b 0

