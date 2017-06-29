@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\openssl" (
    echo "%BINARIESDIR%\openssl exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\OpenSSL_1_1_0f.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\OpenSSL_1_1_0f.zip" https://github.com/openssl/openssl/archive/OpenSSL_1_1_0f.zip
    if not exist "%BUILDDIR%\OpenSSL_1_1_0f.zip" (
        echo "Failed to download openssl"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\openssl-OpenSSL_1_1_0f"
"%UNZIP_BIN%" -q "%BUILDDIR%\OpenSSL_1_1_0f.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\openssl-OpenSSL_1_1_0f"
    exit /b 1
)
if not exist "%BUILDDIR%\openssl-OpenSSL_1_1_0f" (
    echo "Could not find %BUILDDIR%\openssl-OpenSSL_1_1_0f"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\openssl-OpenSSL_1_1_0f\build"
mkdir "%BUILDDIR%\openssl-OpenSSL_1_1_0f\build"
cd "%BUILDDIR%\openssl-OpenSSL_1_1_0f\build"

call "%VS90COMNTOOLS%vsvars32.bat

"%PERL_BIN%" ..\Configure --prefix="%BINARIESDIR%\openssl" VC-WIN32 no-asm no-shared
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

exit /b 0

