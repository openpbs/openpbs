@echo on
setlocal

call "%~dp0set_paths.bat"

cd "%BUILDDIR%"

if exist "%BINARIESDIR%\swig" (
    echo "%BINARIESDIR%\swig exist already!"
    exit /b 0
)

if exist "%BINARIESDIR%\python\python.exe" (
    echo "Found Python installation at %BINARIESDIR%\python, using it to add Python support in swig"
    set PYTHON_INSTALL_DIR=%BINARIESDIR_M%/python/python.exe
) else if exist "C:\Python27\python.exe" (
    echo "Found Python installation at C:\Python27, using it to add Python support in swig"
    set PYTHON_INSTALL_DIR=/c/Python27/python.exe
) else (
    echo "Could not find Python installation, required to add Python support in swig"
    exit /b 1
)

if not exist "%BUILDDIR%\swig-rel-3.0.12.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\swig-rel-3.0.12.zip" https://github.com/swig/swig/archive/rel-3.0.12.zip
    if not exist "%BUILDDIR%\swig-rel-3.0.12.zip" (
        echo "Failed to download swig"
        exit /b 1
    )
)
REM CCCL is Unix cc compiler to Microsoft's cl compiler wrapper
REM and it is require to generate native swig windows binary which doesn't depend on any of MinGW DLLs
if not exist "%BUILDDIR%\cccl-1.0.zip" (
    "%CURL_BIN%" -qkL -o "%BUILDDIR%\cccl-1.0.zip" https://github.com/swig/cccl/archive/cccl-1.0.zip
    if not exist "%BUILDDIR%\cccl-1.0.zip" (
        echo "Failed to download cccl"
        exit /b 1
    )
)

2>nul rd /S /Q "%BUILDDIR%\cccl-cccl-1.0"
"%UNZIP_BIN%" -q "%BUILDDIR%\cccl-1.0.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\cccl-1.0.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\cccl-cccl-1.0" (
    echo "Could not find %BUILDDIR%\cccl-cccl-1.0"
    exit /b 1
)
if not exist "%BUILDDIR%\cccl-cccl-1.0\cccl" (
    echo "Could not find %BUILDDIR%\cccl-cccl-1.0\cccl"
    exit /b 1
)

2>nul rd /S /Q "%BUILDDIR%\swig-rel-3.0.12"
"%UNZIP_BIN%" -q "%BUILDDIR%\swig-rel-3.0.12.zip"
if not %ERRORLEVEL% == 0 (
    echo "Failed to extract %BUILDDIR%\swig-rel-3.0.12.zip"
    exit /b 1
)
if not exist "%BUILDDIR%\swig-rel-3.0.12" (
    echo "Could not find %BUILDDIR%\swig-rel-3.0.12"
    exit /b 1
)

call "%VS90COMNTOOLS%\vsvars32.bat

"%MSYSDIR%\bin\bash" --login -i -c "cp -f $BUILDDIR_M/cccl-cccl-1.0/cccl /usr/bin/cccl && chmod +x /usr/bin/cccl"
if not %ERRORLEVEL% == 0 (
    echo "Failed to copy cccl from %BUILDDIR%\cccl-cccl-1.0\cccl to /usr/bin/cccl in MSYS bash"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/swig-rel-3.0.12 && ./autogen.sh"
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate configure for swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/swig-rel-3.0.12 && ./configure CC=cccl CXX=cccl CFLAGS='-O2' CXXFLAGS='-O2' LDFLAGS='--cccl-link /LTCG' --prefix=$BINARIESDIR_M/swig --without-alllang --with-python=$PYTHON_INSTALL_DIR --disable-dependency-tracking --disable-ccache --without-pcre"
if not %ERRORLEVEL% == 0 (
    echo "Failed to generate makefiles for swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/swig-rel-3.0.12 && make"
if not %ERRORLEVEL% == 0 (
    echo "Failed to compile swig"
    exit /b 1
)
"%MSYSDIR%\bin\bash" --login -i -c "cd $BUILDDIR_M/swig-rel-3.0.12 && make install"
if not %ERRORLEVEL% == 0 (
    echo "Failed to install swig"
    exit /b 1
)

exit /b 0

