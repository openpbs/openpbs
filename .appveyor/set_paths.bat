@echo on
set old_dir="%CD%"
cd %~dp0..\..
set SVN_BIN=svn
set CURL_BIN=curl
set UNZIP_BIN=unzip
set MSYSDIR=C:\MinGW\msys\1.0
set PERL_BIN=perl
set CMAKE_BIN=cmake
set BUILDDIR=%CD%
set BINARIESDIR=%BUILDDIR%\binaries
cd "%BUILDDIR%"
for /F "usebackq tokens=*" %%i in (`""%MSYSDIR%\bin\bash.exe" -c "pwd""`) do set BUILDDIR_M=%%i
2>nul mkdir "%BINARIESDIR%"
cd "%BINARIESDIR%"
for /F "usebackq tokens=*" %%i in (`""%MSYSDIR%\bin\bash.exe" -c "pwd""`) do set BINARIESDIR_M=%%i
cd %old_dir%
set old_dir=
