@echo off
REM this genereates the pbs_ifl_wrap.c file.

if exist "..\..\..\binaries\swig\bin\swig.exe" (
	if not exist "pbs_ifl_wrap.c" (
		echo %%module pbs_ifl > pbs_ifl.i
		echo %%{ >> pbs_ifl.i
		echo #include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		echo %%} >> pbs_ifl.i
		echo %%include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		"..\..\..\binaries\swig\bin\swig.exe" -python pbs_ifl.i
	)
) else (
	copy  ..\..\src\lib\Libifl\pbs_ifl_wrap.c .
	copy  ..\..\src\lib\Libifl\pbs_ifl.py .
)
