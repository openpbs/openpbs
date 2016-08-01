if exist "../../src/lib/Libecl/ecl_job_attr_def.c" (
echo "File present removing earlier generated file!"
del /F /Q "../../src/lib/Libecl/ecl_job_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_job_attr_def.c"
)
	
if exist "../../src/server/job_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/job_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/job_attr_def.c"
)
echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_job_attr_def.xml" -s "../../src/server/job_attr_def.c" -e "../../src/lib/Libecl/ecl_job_attr_def.c" -a job
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_svr_attr_def.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_svr_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_svr_attr_def.c"
)

if exist "../../src/server/svr_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/svr_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/svr_attr_def.c"
)
echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_svr_attr_def.xml" -s "../../src/server/svr_attr_def.c" -e "../../src/lib/Libecl/ecl_svr_attr_def.c" -a server
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_node_attr_def.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_node_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_node_attr_def.c"
)

if exist "../../src/server/node_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/node_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/node_attr_def.c"
)
echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_node_attr_def.xml" -s "../../src/server/node_attr_def.c" -e "../../src/lib/Libecl/ecl_node_attr_def.c" -a node
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_resc_def_all.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_resc_def_all.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_resc_def_all.c"
)
 
if exist "../../src/server/resc_def_all.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/resc_def_all.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/resc_def_all.c"
)

echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_resc_def_all.xml" -s "../../src/server/resc_def_all.c" -e "../../src/lib/Libecl/ecl_resc_def_all.c" -a resc
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_queue_attr_def.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_queue_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_queue_attr_def.c"
)

if exist "../../src/server/queue_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/queue_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/queue_attr_def.c"
)

echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_queue_attr_def.xml" -s "../../src/server/queue_attr_def.c" -e "../../src/lib/Libecl/ecl_queue_attr_def.c" -a queue
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_resv_attr_def.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_resv_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_resv_attr_def.c"
)

if exist "../../src/server/resv_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/resv_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/resv_attr_def.c"
)

echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_resv_attr_def.xml" -s "../../src/server/resv_attr_def.c" -e "../../src/lib/Libecl/ecl_resv_attr_def.c" -a resv
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
if exist "../../src/lib/Libecl/ecl_sched_attr_def.c" (
echo "File present removing earlier generated file!"
del "../../src/lib/Libecl/ecl_sched_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/lib/Libecl/ecl_sched_attr_def.c"
) 

if exist "../../src/server/sched_attr_def.c" (
echo "Server file present removing earlier generated file!"
del "../../src/server/sched_attr_def.c"
if %errorlevel% NEQ 0 (
echo "delete file not a success"
)
echo. >  "../../src/server/sched_attr_def.c"
)

echo "Parsing the Master file for server and ecl"
"C:\Program Files\Python27\python.exe" "../../buildutils/attr_parser.py" -m "../../src/server/master_sched_attr_def.xml" -s "../../src/server/sched_attr_def.c" -e "../../src/lib/Libecl/ecl_sched_attr_def.c" -a sched
if %errorlevel% NEQ 0 (
echo "generation of file not a success"
exit 1
)
