@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\tcltk" (
    echo "%BINARIESDIR%\tcltk exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\tcl866-src.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\tcl866-src.zip" ftp://ftp.tcl.tk/pub/tcl/tcl8_6/tcl866-src.zip
    if not exist "%BUILDDIR%\tcl866-src.zip" (
        echo "Failed to download tcl"
        exit /b 1
    )
)
if not exist "%BUILDDIR%\tk866-src.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\tk866-src.zip" ftp://ftp.tcl.tk/pub/tcl/tcl8_6/tk866-src.zip
    if not exist "%BUILDDIR%\tk866-src.zip" (
        echo "Failed to download tk"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\tcl8.6.6"
"%UNZIP_BIN%" -q "%BUILDDIR%\tcl866-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\tcl866-src.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\tcl8.6.6" (
    echo "Could not find %BUILDDIR%\tcl8.6.6"
    exit /b 1
)
if not exist "%BUILDDIR%\tcl8.6.6\win" (
    echo "Could not find %BUILDDIR%\tcl8.6.6\win"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\tk8.6.6"
"%UNZIP_BIN%" -q "%BUILDDIR%\tk866-src.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\tk866-src.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\tk8.6.6" (
    echo "Could not find %BUILDDIR%\tk8.6.6"
    exit /b 1
)
if not exist "%BUILDDIR%\tk8.6.6\win" (
    echo "Could not find %BUILDDIR%\tk8.6.6\win"
    exit /b 1
)

call "%VS90COMNTOOLS%vsvars32.bat"

cd  "%BUILDDIR%\tcl8.6.6\win"
nmake /f "%BUILDDIR%\tcl8.6.6\win\makefile.vc"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tcl"
    exit /b 1
)
nmake /f "%BUILDDIR%\tcl8.6.6\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\tcltk"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tcl"
    exit /b 1
)

cd "%BUILDDIR%\tk8.6.6\win"
set TCLDIR=%BUILDDIR%\tcl8.6.6
nmake /f "%BUILDDIR%\tk8.6.6\win\makefile.vc"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile tk"
    exit /b 1
)
nmake /f "%BUILDDIR%\tk8.6.6\win\makefile.vc" install INSTALLDIR="%BINARIESDIR%\tcltk"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install tk"
    exit /b 1
)

exit /b 0

