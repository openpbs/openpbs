Overview of commands
=====================

Here is an overview of the most common usage of the PTL commands, there are many
more options to control the commands, see the --help option of each command for
details.

.. _pbs_benchpress:

How to use pbs_benchpress
-------------------------

pbs_benchpress is PTL's test harness, it is used to drive testing, logging
and reporting of test suites and test cases.

To list information about a test suite::

  pbs_benchpress -t <TestSuiteName> -i

To check for compilation errors use below command::

  python -m py_compile /path/to/your/test/file.py

Before running any test we have to export below 2 paths::

  export PYTHONPATH=</path/to/install/location>/lib/python<python version>/site-packages

::

  export PATH=</path/to/install/location>/bin

To Run a test suite and/or a test case

   1. To run the entire test suite::

        pbs_benchpress -t <TestSuiteName>

    where `TestSuiteName` is the name of the class in the .py file you created

   2. To run a test case part of a test suite::

        pbs_benchpress -t <TestSuiteName>.<test_case_name>

    where `TestSuiteName` is as described above and `test_case_name` is the name
    of the test method in the class

   3. You can run the under various logging levels using the -l option::

        pbs_benchpress -t <TestSuiteName> -l DEBUG

    To see various logging levels see :ref:`log_levels`

   4. To run all tests that inherit from a parent test suite class run the
      parent test suite passing the `--follow-child` param to pbs_benchpress::

        pbs_benchpress -t <TestSuite> --follow-child

   5. To exclude specific testsuites, use the --excluding option as such::

        pbs_benchpress -t <TestSuite> --follow-child --exclude=<SomeTest>

   6. To run the test by the name of the test file, for example, if a test
      class is defined in a file named pbs_XYZ.py then you an run it using::

        pbs_benchpress -f ./path/to/pbs_XYZ.py

   7. To pass custom parameters to a test suite::

        pbs_benchpress -t <TestSuite> -p "<key1>=<val1>,<key2>=<val2>,..."

    Alternatively you can pass --param-file pointing to a file where parameters
    are specified. The contents of the file should be one parameter per line::

        pbs_benchpress -t <TestSuite> --param-file=</path/to/file>

        Example: take file as "param_file" then file content should be as below.

        key1=val1
        key2=val2
        .
        .

    Once params are specified, a class variable called param is set in the Test
    that can then be parsed out to be used in the test. When inheriting from
    PBSTestSuite, the key=val pairs are parsed out and made available in the
    class variable ``conf``, so the test can retrieve the information using::

        if self.conf.has_key(key1):
            ...

   8. To check that the available Python version is above a minimum::

        pbs_benchpress --min-pyver=<version>

   9. To check that the available Python version is less than a maximum::

        pbs_benchpress --max-pyver=<version>


   10. On Linux, you can generate PBS coverage data using PTL.
       To collect coverage data using LCOV/LTP, first ensure that PBS was
       compiled using --set-cflags="--coverage" and make sure that you have the lcov
       utility installed. Lcov utility can be obtained at http://ltp.sourceforge.net/coverage/lcov.php
       Then to collect PBS coverage data run pbs_benchpress as follow::

        pbs_benchpress -t <TestName> --lcov-data=</path/to/gcov/build/dir>

       By default the output data will be written to TMPDIR/pbscov-YYYMMDD_HHMMSS,
       this can be controlled using the option --lcov-out.
       By default the lcov binary is expected to be available in the environment, if
       it isn't you can set the path using the option --lcov-bin.


   11. For tests that inherit from PBSTestSuite, to collect procecess information::

        pbs_benchpress -t <TestSuite> -p "procmon=<proc name>[:<proc name>],procmon-freq=<seconds>"

       where `proc name` is a process name such as pbs_server, pbs_sched, pbs_mom.
       RSS,VSZ,PCPU info will be collected for each colon separated name.


   12. To run ptl on multinode cluster we have following two basic requirements.

         A. PTL to be installed on all the nodes.
         B. Passwordless ssh between all the nodes.

       Suppose we have a multinode cluster of three node (M1-type1, M2-type2, M3-type3)
       We can invoke pbs_benchpress command as below::

        pbs_benchpress -t <TestSuite> -p "servers=M1,moms=M1:M2:M3"


.. _log_levels:

Logging levels
~~~~~~~~~~~~~~

PTL uses the generic unittest log levels: INFO, WARNING, DEBUG, ERROR, FATAL

and three custom log levels: INFOCLI, INFOCLI2, DEBUG2.

INFOCLI is used to log command line calls such that the output of a test run
can be read with anyone familiar with the PBS commands.

INFOCLI2 is used to log a wider set of commands run through PTL.

DEBUG2 is a verbose debugging level. It will log commands, including return
code, stdout and stderr.

.. _pbs_loganalyzer:

How to use pbs_loganalyzer
--------------------------

To analyze scheduler logs::

  pbs_loganalyzer -l </path/to/schedlog>

To only display scheduling cycles summary::

  pbs_loganalyzer -l </path/to/schedlog> -c

To analyze server logs::

  pbs_loganalyzer -s </path/to/serverlog>

To analyze mom logs::

  pbs_loganalyzer -m </path/to/momlog>

To analyze accounting logs::

  pbs_loganalyzer -a </path/to/accountinglog>

To specify a begin and/or end time::

  pbs_loganalyzer -b "02/20/2013 21:00:00" -e "02/20/2013 22:00:00" <rest>

Note that for accounting logs, the file will be 'cat' using the sudo command,
so the tool can be run as a regular user with sudo privilege.

To compute cpu/hour utilization against a given snapshot of nodes::

  pbs_loganalyzer -U --nodes-file=/path/to/pbsnodes-av-file
                     --jobs-file=/path/to/qstat-f-file
                     -a /path/acct

A progress bar can be displayed by issuing::

  pbs_loganalyzer --show-progress ...

To analyze the scheduler's estimated start time::

  pbs_loganalyzer --estimated-info -l <path/to/sched/log>

To analyze per job scheduler performance metrics, time to run, time to discard,
time in scheduler (solver time as opposed to I/O with the server), time to
calendar::

  pbs_loganalyzer -l </path/to/schedlog> -S

In addition to a scheduler log, a server log is required to compute the time in
scheduler metric, this is due to the fact that the time in sched is measured
as the difference between a sched log "Considering job to run" and a
corresponding server log's "Job Run" message.

To output analysis to a SQLite file::

  pbs_loganalyzer --db-name=<name or path of database> --db-type=sqlite

Note that the sqlite3 module is needed to write out to the DB file.

To output to a PostgreSQL database::

  pbs_loganalyzer --db-access=</path/to/pgsql/cred/file>
                  --db-name=<name or path of database>
                  --db-type=psql

Note that the psycopg2 module is needed to write out ot the PostgreSQL database.
The cred file should specify the following::

  user=<db username> password=<user's password> dbname=<databasename> port=<val>

To analyze the time (i.e., log record time) between occurrences of a regular
expression in any log file::

  pbs_loganalyzer --re-interval=<regex expression>

This can be used, for example, to measure the interval of occurrences between
E records in an accounting log::

  pbs_loganalyzer -a <path/to/accountlog> --re-interval=";E;"

A useful extended option to the occurrences interval is to compute the number
of regular expression matches over a given period of time::

  pbs_loganalyzer --re-interval=<regex> --re-frequency=<seconds>

For example, to count how many E records are emitted over a 60 second window::

  pbs_loganalyzer -a <acctlog> --re-interval=";E;" --re-frequency=60

When using --re-interval, the -f option can be used to point to an arbitrary
log file instead of depending on -a, -l, -s, or -m, however all these log
specific options will work.

A note about the regular expression used, every Python named group, i.e.,
expressions of the (?P<name>...), will be reported out as a dictionary of
items mapped to each named group.

.. _pbs_stat:

How to use pbs_stat
-------------------

pbs_stat is a useful tool to display filtered information from querying
PBS objects. The supported objects are nodes, jobs, resvs, server, queues.
The supported operators on filtering attributes or resources are >,
<, >=, <=, and ~, the latter being for a regular expression match on the value
associated to an attribute or resource.

In the examples below one can replace the object type by any of
those alternative ones, with the appropriate changes in attribute or resource
names.

Each command can be run by passing a -t <hostname> option to specify a
desired target hostname, the default (no -t) will query the localhost.

To list a summary of all jobs equivalence classes on Resource_List.select, use::

  pbs_stat -j -a "Resource_List.select"

To list a summary of all nodes equivalence classes::

  pbs_stat -n

Note that node equivalence classes are collected by default on
resources_available.ncpus, resources_available.mem, and state. To specify
attributes to create the equivalence class on use -a/-r.

To list all nodes that have more than 2 cpus::

  pbs_stat --nodes -a "resources_available.ncpus>2"

or equivalently (for resources)::

  pbs_stat --nodes -r "ncpus>2"

To list all jobs that request more than 2 cpus and are in state 'R'::

  pbs_stat --jobs -a "Resource_List.ncpus>2&&job_state='R'"

To filter all nodes that have a host value that start with n and end with a,
i.e., "n.*a"::

  pbs_stat --nodes -r "host~n.*a"

To display information in qselect like format use the option -s to each command
using -s the attributes selected are displayed first followed by a list of
names that match the selection criteria.

To display data with one entity per line use the --sline option::

  pbs_stat --nodes --sline

To show what is available now in the complex (a.k.a, backfill hole) use::

  pbs_stat -b

by default the backfill hole is computed based on ncpus, mem, and state, you
can specify the attributes to compute it on by passing comma-separated list of
attributes into the -a option. An alternative to compute the backfill hole is
to use pbs_sim -b.

To show utilization of the system use::

  pbs_stat -U [-r "<resource1,resource2,...>]

resources default to ncpus, memory, and nodes

To show utilization of a specific user::

  pbs_stat -U --user=<name>

To show utilization of a specific group::

  pbs_stat -U --group=<name>

To show utilization of a specific project::

  pbs_stat -U --project=<name>

To count the grand total of a resource values in complex for the queried resource::

  pbs_stat -r <resource, e.g. ncpus> -C --nodes

Note that nodes that are not up are not counted

To count the number of resources having same values in complex for the queried resource::

  pbs_stat -r <resource e.g. ncpus>  -c --nodes

To show an evaluation of the formula for all non-running jobs::

  pbs_stat --eval-formula

To show the fairshare tree and fairshare usage::

  pbs_stat --fairshare

To read information from file use for example::

  pbs_stat -f /path/to/pbsnodes/or/qstat_f/output --nodes -r ncpus

To list all resources currently set on a given object type::

  pbs_stat --nodes --resources-set

To list all resources defined in resourcedef::

  pbs_stat --resources

To list a specific resource by name from resourcedef (if it exists)::

  pbs_stat --resource=<custom_resource>

To show limits associated to all entities::

  pbs_stat --limits-info

To show limits associated to a specific user::

  pbs_stat --limits-info --user=<name>

To show limits associated to a specific group::

  pbs_stat --limits-info --group=<name>

To show limits associated to a specific project::

  pbs_stat --limits-info --project=<name>

To show entities that are over their soft limits::

  pbs_stat --over-soft-limits

The output of limits information shows named entities associated to each
container (server or queue) to which a limit is applied. The entity's usage
as well as limit set are displayed, as well as a remainder usage value that
indicates whether an entity is over a limit (represented by a negative value)
or under a limit (represented by a positive or zero value). In the case of a
PBS_ALL or PBS_GENERIC limit setting, each entity's name is displayed using
the entity's name followed by "/PBS_ALL" or "/PBS_GENERIC" as the case may be.

Here are a few examples, if a server soft limit is set to 0::

    qmgr -c "set server max_run_soft=[u:user1=0]"

for user user1 on the server object, pbs_stat --limits-info will show::

    u:user1
        container = server:minita.pbs.com
        limit_type = max_run_soft
        remainder = -1
        usage/limit = 1/0


if a server soft limit is set to 0 on generic users::

    qmgr -c "set server max_run_soft=[u:PBS_GENERIC=0]"

then pbs_stat --limits-info will show::

    u:user1/PBS_GENERIC
        container = server:minita.pbs.com
        limit_type = max_run_soft
        remainder = -1
        usage/limit = 1/0

To print a site report that summarizes some key metrics from a site::

  pbs_stat --report

optionally, use the path to a pbs_snapshot using the -d option to summarize that
site's information.

To show the number of privileged ports in use::

  pbs_stat --pports

To show information directly from the database (requires psycopg2 module)::

  pbs_stat --db-access=<path/to/dbaccess_file> --db-type=psql
           --<objtype> [-a <attribs>]

where the dbaccess file is of the form::

  user=<value>
  password=<value>
  # and optionally
  [port=<value>]
  [dbname=<value>]

.. _pbs_config:

How to use pbs_config
---------------------

pbs_config is useful in the following cases, use:

.. option:: --revert-config

    To revert a configuration of PBS entities specified as one or
    more of --scheduler, --server, --mom to its default configuration. Note that
    for the server, non-default queues and hooks are not deleted but disabled
    instead.

.. option:: --save-config

    save the configuration of a PBS entity, one of --scheduler,
    --server, --mom to file. The server saves the resourcedef, a qmgr print
    server, qmgr print sched, qmgr print hook. The scheduler saves sched_config,
    resource_group, dedicated_time, holidays. The mom saves the config file.

.. option:: --load-config

    load configuration from file. The changes will be applied to
    all PBS entities as saved in the file.

.. option:: --vnodify

    create a vnode definition and insert it into a given MoM. There are
    many options to this command, see the help page for details.

.. option:: --switch-version

    swith to a version of PBS installed on the system. This
    only supports modifying the PBS installed on a system that matches
    PBS_CONF_FILE.

.. option:: --check-ug

    To check if the users and groups required for automated testing are defined as
    expected on the system

.. option:: --make-ug

    To make users and groups as required for automated testing.This will create
    user home directories with 755 permission.If test user is not using this command
    for user creation then he/she has to make sure that the home directories
    should have 755 permission.

To setup, start, and add (to the server) multiple MoMs::

  pbs_config --multi-mom=<num> -a <attributes> --serverhost=<host>

The multi-mom option creates <num> pbs.conf files, prefixed by pbs.conf_m
followed by an incrementing number by default, for which each configuration
file has a unique PBS_HOME directory that is defined by default to be PBS_m
followed by the same incrementing number as the configuration file. The
configuration prefix can be changed by passing the --conf-prefix option and
the PBS_HOME prefix can be changed via --home-prefix.

To make a PBS daemons mimic the snapshot of a pbs_snapshot::

  pbs_config --as-snap=<path/to/snap>

This will set all server and queue attributes from the snapshot, copy sched_config,
resource_group, holidays, resourcedef, all site hooks, and create and insert a
vnode definition that translates all of the nodes reported by pbsnodes -av.
There may be some specific attributes to adjust, such as pbs_license_info,
or users or groups, that may prevent submission of jobs.

.. _pbs_py_spawn:

How to use pbs_py_spawn
-----------------------

The pbs_py_spawn wrapper can only be used when the pbs_ifl.h API is SWIG
wrapped. The tool can be used to invoke a pbs_py_spawn action associated to a
job running on a MoM.

To call a Python script during the runtime of a job::

  pbs_py_spawn -j <jobid> <path/to/python/script/on/MoM>

To call a Python script that will detach from the job's session::

  pbs_py_spawn --detach -j <jobid> </path/to/python/script/on/MoM>

Detached scripts essentially background themselves and are attached back to
the job monitoring through pbs_attach such that they are terminated when the
job terminates. The detached script must write out its PID as its first
output.

How to use pbs_compare_results
-----------------------

The pbs_compare_results is a tool to compare performance test results by
comparing the json output generated by pbs_benchpress.

To run pbs_compare_results and generate csv only report::

  pbs_compare_results <benchmark_version>.json <tocompare_version>.json

To run pbs_compare_results and generate html report along with csv::
  
  pbs_compare_results <benchmark_version>.json <tocompare_version>.json --html-report

To run pbs_compare_results and generate reports at user defined location::

  pbs_compare_results <benchmark_version>.json <tocompare_version>.json --output-file=<path>

