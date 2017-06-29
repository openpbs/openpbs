@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\pgsql" (
    echo "%BINARIESDIR%\pgsql exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\postgresql-9.6.3.tar.bz2" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\postgresql-9.6.3.tar.bz2" https://ftp.postgresql.org/pub/source/v9.6.3/postgresql-9.6.3.tar.bz2
    if not exist "%BUILDDIR%\postgresql-9.6.3.tar.bz2" (
        echo "Failed to download postgresql"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\postgresql-9.6.3"
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/ && tar -xf postgresql-9.6.3.tar.bz2"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\postgresql-9.6.3.tar.bz2"
    exit /b 1
)
if not exist "%BUILDDIR%\postgresql-9.6.3" (
    echo "Could not find %BUILDDIR%\postgresql-9.6.3"
    exit /b 1
)
if not exist "%BUILDDIR%\postgresql-9.6.3\src\tools\msvc" (
    echo "Could not find %BUILDDIR%\postgresql-9.6.3\src\tools\msvc"
    exit /b 1
)

call "%VS90COMNTOOLS%\vsvars32.bat"

cd "%BUILDDIR%\postgresql-9.6.3\src\tools\msvc"

call "%BUILDDIR%\postgresql-9.6.3\src\tools\msvc\build.bat"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile pgsql"
    exit /b 1
)

REM This is for Perl to find ./inc/Module/Install.pm, see header of http://cpansearch.perl.org/src/AUDREYT/Module-Install-0.64/lib/Module/Install.pm
set PERL5LIB=.
call "%BUILDDIR%\postgresql-9.6.3\src\tools\msvc\install.bat" "%BINARIESDIR%\pgsql"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pgsql"
    exit /b 1
)

exit /b 0

