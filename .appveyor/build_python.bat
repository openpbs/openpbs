@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\python" (
    echo "%BINARIESDIR%\python exist already!"
    exit /b 0
)

if not exist "%BUILDDIR%\cpython-2.7.13.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\cpython-2.7.13.zip" https://github.com/python/cpython/archive/v2.7.13.zip
    if not exist "%BUILDDIR%\cpython-2.7.13.zip" (
        echo "Failed to download python"
        exit /b 1
    )
)
2>nul rd /S /Q "%BUILDDIR%\cpython-2.7.13"
"%UNZIP_BIN%" -q "%BUILDDIR%\cpython-2.7.13.zip"
cd "%BUILDDIR%\cpython-2.7.13"

REM Restore externals directory if python_externals.tar.gz exists
if exist "%BUILDDIR%\python_externals.tar.gz" (
    if not exist "%BUILDDIR%\cpython-2.7.13\externals" (
        "%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/cpython-2.7.13 && tar -xf $BUILDDIR_M/python_externals.tar.gz"
    )
)

call "%BUILDDIR%\cpython-2.7.13\PCbuild\env.bat" x86

call "%BUILDDIR%\cpython-2.7.13\PC\VS9.0\build.bat" -e
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile Python 32bit"
    exit /b 1
)

REM Workaround for cabarc.exe, required by msi.py
if not exist "%BUILDDIR%\cabarc.exe" (
    if not exist "%BUILDDIR%\supporttools.exe" (
        "%CURL_BIN%" -qkL -o "%BUILDDIR%\supporttools.exe" http://download.microsoft.com/download/d/3/8/d38066aa-4e37-4ae8-bce3-a4ce662b2024/WindowsXP-KB838079-SupportTools-ENU.exe
        if not exist "%BUILDDIR%\supporttools.exe" (
            echo "Failed to download supporttools.exe"
            exit /b 1
        )
    )
    2>nul rd /S /Q "%BUILDDIR%\cpython-2.7.13\cabarc_temp"
    mkdir "%BUILDDIR%\cpython-2.7.13\cabarc_temp"
    "%BUILDDIR%\supporttools.exe" /C /T:"%BUILDDIR%\cpython-2.7.13\cabarc_temp"
    expand "%BUILDDIR%\cpython-2.7.13\cabarc_temp\support.cab" -F:cabarc.exe "%BUILDDIR%"
)
set PATH=%BUILDDIR%;%PATH%

REM Workaround for python2713.chm
mkdir "%BUILDDIR%\cpython-2.7.13\Doc\build\htmlhelp"
echo "dummy chm file to make msi.py happy" > "%BUILDDIR%\cpython-2.7.13\Doc\build\htmlhelp\python2713.chm"

cd PC
nmake /f "%BUILDDIR%\cpython-2.7.13\PC\icons.mak"
if not %ERRORLEVEL% == 0 (
    echo "Failed to build icons for Python 32bit"
    exit /b 1
)

cd "%BUILDDIR%\cpython-2.7.13\Tools\msi"
set PCBUILD=PC\VS9.0
set SNAPSHOT=0
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" -m ensurepip -U --default-pip
if not %ERRORLEVEL% == 0 (
    echo "Failed to run ensurepip for Python 32bit"
    exit /b 1
)
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" -m pip install pypiwin32
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pypiwin32 for Python 32bit"
    exit /b 1
)
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" msi.py
if not exist "%BUILDDIR%\cpython-2.7.13\Tools\msi\python-2.7.13150.msi" (
    echo "Failed to generate msi Python 32bit"
    exit /b 1
)

start /wait msiexec /qn /a "%BUILDDIR%\cpython-2.7.13\Tools\msi\python-2.7.13150.msi" TARGETDIR="%BINARIESDIR%\python"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract msi Python 32bit to %BINARIESDIR%\python"
    exit /b 1
)
"%BINARIESDIR%\python\python.exe" -Wi "%BINARIESDIR%\python\Lib\compileall.py" -q -f -x "bad_coding|badsyntax|site-packages|py3_" "%BINARIESDIR%\python\Lib"
"%BINARIESDIR%\python\python.exe" -O -Wi "%BINARIESDIR%\python\Lib\compileall.py" -q -f -x "bad_coding|badsyntax|site-packages|py3_" "%BINARIESDIR%\python\Lib"
"%BINARIESDIR%\python\python.exe" -c "import lib2to3.pygram, lib2to3.patcomp;lib2to3.patcomp.PatternCompiler()"
"%BINARIESDIR%\python\python.exe" -m ensurepip -U --default-pip
if not %ERRORLEVEL% == 0 (
    echo "Failed to run ensurepip in %BINARIESDIR%\python for Python 32bit"
    exit /b 1
)
"%BINARIESDIR%\python\python.exe" -m pip install pypiwin32
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pypiwin32 in %BINARIESDIR%\python for Python 32bit"
    exit /b 1
)
copy /B /Y "%VS90COMNTOOLS%..\..\VC\redist\amd64\Microsoft.VC90.CRT\msvcr90.dll" "%BINARIESDIR%\python\"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy msvcr90.dll in %BINARIESDIR%\python for Python 32bit"
    exit /b 1
)
copy /B /Y "%VS90COMNTOOLS%..\..\VC\redist\amd64\Microsoft.VC90.CRT\Microsoft.VC90.CRT.manifest" "%BINARIESDIR%\python\"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy Microsoft.VC90.CRT.manifest in %BINARIESDIR%\python for Python 32bit"
    exit /b 1
)


REM Start of build for Python 64 bit
cd "%BUILDDIR%"

if exist "%BINARIESDIR%\python_x64" (
    echo "%BINARIESDIR%\python_x64 exist already!"
    exit /b 0
)

2>nul rd /S /Q "%BUILDDIR%\cpython-2.7.13"
"%UNZIP_BIN%" -q "%BUILDDIR%\cpython-2.7.13.zip"
cd "%BUILDDIR%\cpython-2.7.13"

REM Restore externals directory if python_externals.tar.gz exists
if exist "%BUILDDIR%\python_externals.tar.gz" (
    if not exist "%BUILDDIR%\cpython-2.7.13\externals" (
        "%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/cpython-2.7.13 && tar -xf $BUILDDIR_M/python_externals.tar.gz"
    )
) else (
	call "%BUILDDIR%\cpython-2.7.13\PCbuild\get_externals.bat"
)

REM workaround to openssl build fail
del "%BUILDDIR%\cpython-2.7.13\externals\openssl-1.0.2j\ms\nt64.mak"

if not exist "%VS90COMNTOOLS%..\..\VC\bin\amd64\vcvarsamd64.bat" (
	if not exist "%ProgramFiles%\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" (
		echo "Could not find x64 build tools for Visual Studio"
		exit /b 1
	)
    call "%VS90COMNTOOLS%vsvars32.bat"
    call "%ProgramFiles%\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" /x64
) else (
	call "%VS90COMNTOOLS%..\..\VC\bin\amd64\vcvarsamd64.bat"
)

call "%BUILDDIR%\cpython-2.7.13\PC\VS9.0\build.bat" -e -p x64
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile Python 64bit"
    exit /b 1
)

REM Workaround for python2713.chm
mkdir "%BUILDDIR%\cpython-2.7.13\Doc\build\htmlhelp"
echo "dummy chm file to make msi.py happy" > "%BUILDDIR%\cpython-2.7.13\Doc\build\htmlhelp\python2713.chm"

cd PC
REM we need 32bit compiler as python icons does not compile in 64bit
call "%VS90COMNTOOLS%vsvars32.bat"
nmake /f "%BUILDDIR%\cpython-2.7.13\PC\icons.mak"
if not %ERRORLEVEL% == 0 (
    echo "Failed to build icons for Python 64bit"
    exit /b 1
)

REM Restore back 64 bit compiler
if not exist "%VS90COMNTOOLS%..\..\VC\bin\amd64\vcvarsamd64.bat" (
	if not exist "%ProgramFiles%\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" (
		echo "Could not find x64 build tools for Visual Studio"
		exit /b 1
	)
    call "%VS90COMNTOOLS%vsvars32.bat"
    call "%ProgramFiles%\Microsoft SDKs\Windows\v7.1\Bin\SetEnv.cmd" /x64
) else (
	call "%VS90COMNTOOLS%..\..\VC\bin\amd64\vcvarsamd64.bat"
)

cd "%BUILDDIR%\cpython-2.7.13\Tools\msi"
set PCBUILD=PC\VS9.0\amd64
set SNAPSHOT=0
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" -m ensurepip -U --default-pip
if not %ERRORLEVEL% == 0 (
    echo "Failed to run ensurepip for Python 64bit"
    exit /b 1
)
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" -m pip install pypiwin32
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pypiwin32 for Python 64bit"
    exit /b 1
)
"%BUILDDIR%\cpython-2.7.13\%PCBUILD%\python.exe" msi.py
if not exist "%BUILDDIR%\cpython-2.7.13\Tools\msi\python-2.7.13150.amd64.msi" (
    echo "Failed to generate msi Python 64bit"
    exit /b 1
)

start /wait msiexec /qn /a "%BUILDDIR%\cpython-2.7.13\Tools\msi\python-2.7.13150.amd64.msi" TARGETDIR="%BINARIESDIR%\python_x64"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract msi Python 64bit to %BINARIESDIR%\python_x64"
    exit /b 1
)
"%BINARIESDIR%\python_x64\python.exe" -Wi "%BINARIESDIR%\python_x64\Lib\compileall.py" -q -f -x "bad_coding|badsyntax|site-packages|py3_" "%BINARIESDIR%\python_x64\Lib"
"%BINARIESDIR%\python_x64\python.exe" -O -Wi "%BINARIESDIR%\python_x64\Lib\compileall.py" -q -f -x "bad_coding|badsyntax|site-packages|py3_" "%BINARIESDIR%\python_x64\Lib"
"%BINARIESDIR%\python_x64\python.exe" -c "import lib2to3.pygram, lib2to3.patcomp;lib2to3.patcomp.PatternCompiler()"
"%BINARIESDIR%\python_x64\python.exe" -m ensurepip -U --default-pip
if not %ERRORLEVEL% == 0 (
    echo "Failed to run ensurepip in %BINARIESDIR%\python_x64 for Python 64bit"
    exit /b 1
)
"%BINARIESDIR%\python_x64\python.exe" -m pip install pypiwin32
if not %ERRORLEVEL% == 0 (
    echo "Failed to install pypiwin32 in %BINARIESDIR%\python_x64 for Python 64bit"
    exit /b 1
)
copy /B /Y "%VS90COMNTOOLS%..\..\VC\redist\amd64\Microsoft.VC90.CRT\msvcr90.dll" "%BINARIESDIR%\python_x64\"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy msvcr90.dll in %BINARIESDIR%\python_x64 for Python 64bit"
    exit /b 1
)
copy /B /Y "%VS90COMNTOOLS%..\..\VC\redist\amd64\Microsoft.VC90.CRT\Microsoft.VC90.CRT.manifest" "%BINARIESDIR%\python_x64\"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy Microsoft.VC90.CRT.manifest in %BINARIESDIR%\python_x64 for Python 64bit"
    exit /b 1
)

exit /b 0

