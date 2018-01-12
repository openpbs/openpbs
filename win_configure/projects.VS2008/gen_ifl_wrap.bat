@echo off
setlocal enableDelayedExpansion
REM this genereates the pbs_ifl_wrap.c file.

if exist "..\..\..\binaries\swig\bin\swig.exe" (
	if not exist "pbs_ifl_wrap.c" (
		set SWIG_VERSION=""
		for /F "tokens=3 USEBACKQ" %%F IN (`..\..\..\binaries\swig\bin\swig.exe -version ^| findstr /l /c:"SWIG Version "`) DO (
			set SWIG_VERSION=%%F
		)
		if "!SWIG_VERSION!"=="" (
			echo Failed to find swig version
			exit /b 1
		)
		echo %%module pbs_ifl > pbs_ifl.i
		echo %%{ >> pbs_ifl.i
		echo #include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		echo %%} >> pbs_ifl.i
		echo %%include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		"..\..\..\binaries\swig\bin\swig.exe" -I..\..\..\binaries\swig\share\swig\!SWIG_VERSION! -I..\..\..\binaries\swig\share\swig\!SWIG_VERSION!\python -python pbs_ifl.i
	)
) else (
	copy  ..\..\src\lib\Libifl\pbs_ifl_wrap.c .
	copy  ..\..\src\lib\Libifl\pbs_ifl.py .
)
