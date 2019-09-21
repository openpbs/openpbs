@echo off
setlocal enableDelayedExpansion
REM this genereates the pbs_ifl_wrap.c file.

if exist "..\..\..\binaries\swig\swig.exe" (
	if not exist "pbs_ifl_wrap.c" (
		echo %%module pbs_ifl > pbs_ifl.i
		echo %%{ >> pbs_ifl.i
		echo #include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		echo %%} >> pbs_ifl.i
		echo %%include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		..\..\..\binaries\swig\swig.exe -python pbs_ifl.i
		if not %ERRORLEVEL% == 0 (
			echo "Failed to generate SWIG-Wrapped IFL"
			exit /b 1
		)
	)
) else (
	copy  ..\..\src\lib\Libifl\pbs_ifl_wrap.c .
	copy  ..\..\src\lib\Libifl\pbs_ifl.py .
)
