@echo off
REM this genereates the pbs_ifl_wrap.c file.

if exist "C:\Program Files\swigwin-2.0.4\swig.exe" (
	if not exist "pbs_ifl_wrap.c" (
		echo %%module pbs_ifl > pbs_ifl.i
		echo %%{ >> pbs_ifl.i
		echo #include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		echo %%} >> pbs_ifl.i
		echo %%include "..\..\src\include\pbs_ifl.h" >> pbs_ifl.i
		"C:\Program Files\swigwin-2.0.4\swig" -python pbs_ifl.i
	)
) else (
	copy  ..\..\src\lib\Libifl\pbs_ifl_wrap.c .
	copy  ..\..\src\lib\Libifl\pbs_ifl.py .
)
