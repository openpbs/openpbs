PbsTestLab: PBS Unit Testing and Benchmarking Framework
=======================================================

.. contents:: 

Version
=======
0.2r150729

Summary
=======

A unit testing and benchmarking framework to write, execute, and catalog 
PBS Pro tests.

Contents
========

.. image:: doc/arch_overview.png
   :width: 600px 

A core library (see ptl/lib/):
------------------------------
 
* Provides PBS IFL operations through either SWIG-wrappers or PBS CLI
* Encapsulated PBS entities: Server, Scheduler, MoM, Comm, Queue, Job, 
  Reservation, Hook, Resource
* Utility class to convert batch status and attributes to Python lists, strings 
  and dictionaries
* High-level PBS operations to operate on PBS entities including nodes, queues,
  jobs, reservations, resources, and server

A set of utilities (see ptl/utils/):
------------------------------------

* Logging to parse and report metrics from server/scheduler/MoM/Accounting logs. 
  Metrics include number of jobs queued/run/ended, cycle duration, in-scheduler 
  duration (time spent strictly in scheduler code).
* Distributed tools to transparently run commands locally or remotely, including 
  file copying.
* Package management tools to list, install, uninstall, and init PBS packages 
  and services

A set of tests (see ptl/tests/):
--------------------------------
      
* Each test uses the core library to perform operations on PBS Entities.
* ptl/utils/pbs_testsuite.py is a test wrapper that provides generic operations 
  for test setup and teardown; whenever possible, tests should derive from 
  PBSTestSuite 

A set of command-line tools (see bin/)
--------------------------------------

* pbs_pkgmgr to install, uninstall, and init PBS packages and services.
* pbs_loganalyzer to analyze PBS logs
* pbs_benchpress to run unit tests
* pbs_swigify to build IFL swig wrappers and copy them over to the library
* pbs_as used by the library to impersonate a user for API job submission
* pbs_stat to filter PBS objects based on select properties
* pbs_snapshot to capture diagnostics (and optionally anonymized) data. 
* pbs_config to configure services, e.g., create vnodes
* pbs_dsh distributed shell operations on a group of hostnames
* pbs_dcp distributed file copy operations on a group of hostnames
* pbs_cov to generate lcov/ltp (gcov) coverage analys. Requires instrumented
  source files.

Documentation (see doc/)
------------------------

* API documentation describing the capabilities of the framework
* For the command-line tools under bin/ use the -h option for help

Installation
============

Package uses pip, as root run:

  cd <path/to/ptl/dir/>
  pip install -r requirements.txt .

To uninstall package, as root run:
  pip uninstall PbsTestLab

To update package, as root run:
  pip update PbsTestLab

By default, if the library is not able to load the IFL wrappers, it defaults
to using PBS CLI tools.

When depending on the IFL API:

  To build the SWIG IFL library, first ensure that PBS is installed, and as 
  root run:
  pbs_swigify  -I/path/to/python/include -f [-s /path/to/swig/binary/to/use]

  The path to Python include must correspond to the include directory of the
  Python version that is used to run PTL tools.
 
  A swig binary is required in order to SWIG'ify pbs_ifl.h. On some platforms,
  such as RHEL/CentOS, swig is part of the distribution, on others, such as SLES
  it isn't and needs to be built/installed independently. 

  SWIG depends on the PCRE package and on Python's development package, Python.h 
  and python libraries. 

Dependencies 
============

Assumptions
-----------

The library and utility functions make several assumptions about the
environment:

* Unix, Linux
* The following commands are called by the utilities:
  * cat
  * tar
  * scp
  * sudo
  * ssh
  * cp
  * kill
  * tail
  * rpm
  * mkdir
  * useradd
  * ps
  * rm

* For fully automated runs, passwordless authentication should be setup on all
  systems
* Some usernames are expected to exist: pbsuser, pbsuser1, pbsuser2, pbsuser3.
  These can be edited in pbs_testsuite.py. Tests deriving from PBSTestSuite
  can customize test-users by passing along -p test-users=<user1>:<user2>...
* The package should be installed on all systems 

The library can use either PBS's CLI tools (qsub, qstat, qmgr, qdel, etc...)
or SWIG-wrapped IFL API. When using the API, SWIG wrapping capability must be available 
on the system and calls for:
 
  * swig version 2.0.4 or greater
  * libpbs.h
  * libpbs.a
  * gcc
  * Python development package, Python.h and libraries

Brief Tutorial
==============

Most of the examples below show specific calls to the library functions,
there are typically many more derivations possible, check the full API 
under doc for details.

See ptl/tests/pbs_smoketest.py for examples on testing some of the core features of PBS.

Core Library
------------

Importing the library. Because the library may leverage SWIG-wrappers it is 
preferred to import all so that the pbs_ifl module imports all IFL symbols

  from ptl.lib.pbs_testlib import *

Instantiating a Server (meaning that we instantiate a Server object and
populate it's attributes values after stat'ing the PBS server)::

  server = Server('remotehost')
  OR
  server = Server() # no hostname defaults to the FQDN of the localhost

Adding a user as manager::

  server.manager(MGR_CMD_SET, SERVER, {ATTR_managers: (INCR, 'user@host')})

Reverting configuration to defaults::

  server.revert_to_defaults()

Instantiating a Job::
 
  job = Job()

Setting job attributes::

  job.set_attributes({'Resource_List.select':'2:ncpus=1','Resource_List.place':'scatter'})

Submitting a job::

  server.submit(job)

Stat'ing a server::

  server.status()

Stat'ing all jobs job_state attribute::

  server.status(JOB, 'job_state')

Counting all vnodes by state::

  server.counter(NODE, 'state')

Expecting a job to be running::

  server.expect(JOB, {'job_state':'R','substate':42}, attrop=PTL_AND, id=jid)
  where jid is the result os a server.submit(job)

  Each attribute can be given an operand, one of LT, LE, EQ, GE, GT, NE
  For example to expect a job to be in state R and substate != 41:
 
  server.expect(JOB, {'job_state':(EQ,'R'), 'substate':(NE,41)}, id=jid)

Instantiating a Scheduler object::

  sched = Scheduler('hostname')

Setting scheduler configuration::

  sched.set_sched_config({'backfill':'true  ALL'})

Reverting configuration to defaults::

  sched.revert_to_defaults()

Instantiating a MoM::

  mom = MoM('hostname')

Creating a vnode definition file 10 vnodes prefixed 'vn' with 8 cpus and 8gb
of memory::

  attrs = {'resources_available.ncpus':8,'resources_available.mem':'8gb'}
  vdef = node.create_vnode_def('vn', attrs, 10)

Inserting a vnode definition to a MoM::

  mom.insert_vnode_def(vdef)

Reverting configuration to defaults::

  mom.revert_to_defaults()

Naming conventions, recommended practices, and guidelines 
---------------------------------------------------------

Write the test in a filename prefixed by ``pbs_`` 
followed by either the issue number, for example pbs_1234.py or by a 
descriptive name, for example pbs_non_preemptive_soft_limits.py, (strongly
favor the issue number format).

Name the Test class prefixed by ``Test`` followed by either the issue number from 
which it originates, for example Test1234, if the test is not from a issue,
consider using a descriptive short name, for example TestNonPreemptiveSoftLimits.

Whenever applicable name the test cases using a descriptive name, noting that
PTL will run the methods that start with ``test_``. The test cases running
sequence is unordered (some claim that it is lexicographic ordering but it is
best to not write your test suites based on such assumptions).

Put every functionality that is common to all test cases in its own method,
and consider adding it to the core library if it is a generic interface to
PBS.

Run the autopep8 tools on your code before circulating it for 
review. autopep8 info at https://pypi.python.org/pypi/autopep8
PEP8 Python coding style at http://www.python.org/dev/peps/pep-0008/

Writing a test suite
--------------------

See ptl/tests/pbs_smoketest.py for some basic examples that inherit from 
PBSTestSuite

Test Suites added to the ptl/tests directory are automatically discovered by
the test harness (pbs_benchpress).

Whenever possible consider making the test class inherit from PBSTestSuite, it
is a generic setup and teardown class that delete all jobs and reservations,
reverts server and scheduler configuration to defaults and ensures that there
is at least one cpu to schedule work on.

Some info about PBSTestSuite
---------------------------------------------------------

Tests that inherit functionality from a parent class such as PBSTestSuite have
available to them predefined functionality for setUp, tearDown, or whatever
capability they make available in the parent class.

When creating a new category of tests, such as benchmarking, load tests, or
say performance analysis, it is recommended to create a parent class that
all test suites in that category should inherit. 

PBSTestSuite offers the following:

setUp:

  * Parse custom parameters that are passed in to the Class variable 'param'
    The built-in parameters are: servers, server, moms, mom, mode.
    servers: list of hosts that act as servers (e.g., in peering environments)
    server: the first server in the servers list
    moms: list of hosts that act as MoM
    mom: the first mom in the moms list
    mode: one of api, or cli
  * Check that server and scheduler services are up
  * Add the current user to the list of managers, i.e. equivalent to::
       qmgr -c "s s managers += current_user@*
  * Revert server and scheduler configurations
     * Bring scheduler config back to out-of-box defaults
     * Unset server attributes that are not set out-of-box
     * Disable non default queues and revert queues to default configuration
     * Disable all hooks
     * Note that resources in the resourcedef file are left untouched, queues
       and hooks are not deleted but disabled instead. 
  * Initializes the PBS messages middleware that is used to map messages
       emitted to stdout, stderr, and logs to their value across PBS releases
  * Cleanup jobs and reservations
  * If no nodes are defined in the system, a single 8 cpu node is defined. 
  * Check that the server attribute FLicenses for floating licenses is > 0

tearDown:

  * Check that PBS services are up
  * Cleanup jobs and reservations

analyze_logs:
  * Analyzes scheduler and accounting logs and reports back summary

The summary of the log analysis is then used by pbs_benchpress to write
information about the test run into either a SQLite DB or to file.

It can be useful, when writing a standalone test, to use PBSTestSuite as
guideline for checks and definitions that a standalone test may offer or
extend.

You can take advantage of PBSTestSuite's setUp and tearDown methods and extend
their functionality by overriding the setUp and/or tearDown methods in your
own class, for example::

    class MyTest(PBSTestSuite):

        def setUp(self):
            PBSTestSuite.setUp(self)
            # create custom nodes, server/sched config, etc...

Overview of reverting to defaults
----------------------------------

Server, scheduler, MoM, and queue each have a method to revert to defaults,
here is a description of what each one does:

Server defaults:

  * Unset all qmgr options that are different from out of the box PBS options
  * Delete all non-default queues that the test may have created. Options 
    exist to not delete the queues and instead to disable non-default queues. 
  * Delete all hooks that a test may have created. Options exist to instead 
    disable hooks.
  * Option exists to delete resourcedef file. Default is to not delete 
    resourcedef
  
Queue defaults:

  * Unset queue attributes that are different from out of the box queue 
    attributes

Scheduler defaults:

  * Clear any dedicated time that may have been set
  * Reset out-of-box sched_config options by copying over the file at 
    $PBS_EXEC/etc/pbs_sched_config
  * Send a HUP signal to the scheduler to reconfigure
 
MoM defaults:

  * Remove prologue and epilogue (if any)
  * Reset mom_priv/config to out-of-box defaults
  * Optionally delete vnode definitions that may have been defined by test.
    Restart or send signal to HUP MoM. If vnodes are deleted, MoM is restarted.
    Default is to HUP. Note that nodes are not deleted from the server object,
    it is the responsibility of the test writer to delete/create nodes as 
    needed at the beginning of their test.
   
How to mark a test as skipped
------------------------------

The unittest module in Python versions less than 2.7 do not support
registering skipping tests. PTL offers a mechanism to count the number of
tests skipped, it is however up to the test writer to ensure that a test is
not run if it needs to be skipped.
Tests that inherit from PBSTestSuite inherit a method called skip_test that
increments the number of tests skipped, whenever a test is to be skipped, that
method should be called and the test should return. This is commonly needed
when, for example, a test case verifies that the PBS version installed is not
what one expected by the test, instead of treating this as a failure, the test
writer can choose to skip the test instead.

PBSTestSuite defines a decorator function called checkPbsVersion(op, version)
that takes two string parameters, an arithmetic operator and a version number,
the arithmetic operator can be one of <, <=, =, >=. >. When decorating a 
unit test with for example @checkPbsVersion('>=', '12') the test will be skipped
whenever the version of PBS is less than 12.

How to add a new attribute to the library
-----------------------------------------

This section is targeted to PBS developers who may be adding a new job, queue,
server, or node attribute and need to write tests that depend on such a new
attribute.
PTL does not automatically generate mappings from API to CLI, so when adding 
new attributes, it is the responsibility of the test writer to define the
attribute conversion in ptl/lib/pbs_api_to_cli.py. The new attribute must also
be defined ptl/lib/pbs_ifl_mock.py so that the attribute name can be
dereferenced if the SWIG wrapping was not performed. 
Here is an example, let's assume we are introducing a new job attribute called
ATTR_geometry that maps to the string "job_geometry", in order to be able to 
set the attribute on a job, we need to define it in pbs_api_to_cli.py as:
ATTR_geometry: "Wjob_geometry=" 
and add it to ptl/lib/pbs_ifl_mock.py as:
ATTR_geometry: "job_geometry".
In order to get the API to take the new attribute into consideration,
pbs_swigify must be rerun so that symbols from pbs_ifl.h are read in. 

PbsType objects
----------------

PTL does not dynamically type the attributes that are queried from PBS. 
Instead, it offers a handful of type objects that can be used to facilitate
access to data, here is a description of those types:

PbsTypeSize(str) 
~~~~~~~~~~~~~~~~

Representation of a size in bytes, kb, mg, gb, etc...

Attributes:
  * unit - The unit associated to the size, one of b, kb, mb, gb...
  * value - The numeric value of the size object

PbsTypeDuration(str)
~~~~~~~~~~~~~~~~~~~~

Representation of a duration in seconds

Attributes:
  * as_seconds - HH:MM:SS represented in seconds
  * as_str - duration represented in HH:MM:SS

PbsTypeArray(list)
~~~~~~~~~~~~~~~~~~

Representation of a separated list as array (e.g., String array)

Attributes:
  * value - The value passed in to the descriptor class
  * separator - The separator delimiting each entry in the list. Defaults to ','

PbsTypeList(dict)
~~~~~~~~~~~~~~~~~

Dictionary representation of a list, e.g. k1=v1,k2=v2 gets mapped to 
{k1:v1, k2,v2}

Attributes:
  * kvsep - The key/value separator character
  * separator - The separator used to split the list
  * as_list - Representation of the value as a Python list
  
PbsTypeLicenseCount(PbsTypeList)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Representation of license count as dictionary. Inherits from PbsTypeList, which
it calls using ' ' as separator and ':' as a key/value separator

PbsTypeVariableList(PbsTypeList)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Representation of variable list as dictionary. Inherits from PbsTypeList, which
 it calls using ',' as separator and '=' as a key/value separator.

PbsTypeSelect(list)
~~~~~~~~~~~~~~~~~~~

PBS select/schedselect specification. 

Attributes:
  * num_chunks - The total number of chunks in the select
  * resources - A dictionary of all resource counts in the select 

PbsTypeChunk(dict)
~~~~~~~~~~~~~~~~~~

PBS chunk associated to a PbsTypeExecVnode.
This type of chunk corresponds to a node solution to a resource request, not to
the select specification

Attributes:
  * vnode - the vnode name corresponding to the chunk
  * resources - the key:value pair of resources in dictionary form
  * vchunk - a list of virtual chunks needed to solve the select-chunk, vchunk 
    is only set if more than one vchunk are required to solve the select-chunk 

PbsTypeExecVnode(list)
~~~~~~~~~~~~~~~~~~~~~~

Execvnode representation, expressed as a list of PbsTypeChunk

Attributes:
  * vchunk - List of virtual chunks, only set when more than one vnode is 
    allocated to a host satisfy a chunk requested
  * num_chunks - The number of chunks satisfied by this execvnode
  * vnodes - List of vnode names allocated to the execvnode
  * resource - method to return the amount of a named resource satisfied by 
    this execvnode

PbsTypeFGCLimit(object)
~~~~~~~~~~~~~~~~~~~~~~~

Finer-Granularity Control Limit representation. The constructor takes an 
attribute name (e.g., max_run_res.ncpus), and a value (e.g., [u:PBS_GENERIC=2])

Attributes:
  * entity_type: The type of the entity limited, one of u, g, p, or o
  * entity_name: The name of the entity being limited, either PBS_GENERIC, 
    PBS_ALL, or the name of a user, group or project
  * limit_type: Whether a max_run, max_run_res, max_run_soft, or  
    max_run_res_soft
  * limit_value: The amount the entity is limited to
  
Exceptions and errors
---------------------

A handful of exceptions are raised whenever an error is encountered. There is
an exception for each IFL error case, each error inherits from a generic 
exception called PtlException that has three variables:

  * rc: return code 
  * rv: return value
  * msg: message that describes the error

Whenever a call is expected to produce an error it must be enclosed in a 
try/except block. For example, when submitting a job that is expected to 
fail to be submitted to PBS one would write::

  server = Server()
  j = Job(attrs={'bogus_attribute': 2})

  try:
    jid = server.submit(j)
  except PbsSubmitError, e:
    # where e has rc, rv, and msg variables that describe the error
    
See test_exceptions in ptl/tests/pbs_examples.py for some usage examples.

The exception classes are:

PbsConnectError
~~~~~~~~~~~~~~~

Raised when a connection to a server can not be established

PbsServiceError
~~~~~~~~~~~~~~~

Raised when a service fails to start or stop

PbsStatusError
~~~~~~~~~~~~~~

Raised upon failure to issue a stat call to PBS

PbsSubmitError
~~~~~~~~~~~~~~

Raised upon failure to submit a job to PBS

PbsManagerError
~~~~~~~~~~~~~~~

Raised upon a failure to issue a manager call to PBS

Other IFL Errors
~~~~~~~~~~~~~~~~

All other IFL calls raise corresponding errors, those are listed below rather 
than comprehensively described here for brevity:

PbsAlterError, PbsHoldError, PbsReleaseError, PbsSignalError, PbsMessageError,
PbsMoveError, PbsRunError, PbsRerunError, PbsOrderError, PbsSelectError

PtlExceptError
~~~~~~~~~~~~~~~

Raised when a call to Server.expect does not yeild the expected value.

PbsSchedConfigError
~~~~~~~~~~~~~~~~~~~

Raised when reconfiguration of the scheduler fails, which is detected by 
searching for an error in the scheduler log.

PbsResourceError
~~~~~~~~~~~~~~~~

Raised when a failure to operate on the resourcedef file occurs.

PbsConfigError
~~~~~~~~~~~~~~

Raised when an error to operate on the pbs.conf file occurs.


How to use the messages middleware
----------------------------------

Tests that expect PBS to emit a specific message, be it on stdout, stderr, or 
in a log file must use the PbsMessages object in order to set and retrieve 
the message. The PbsMessages class is designed to be aware of the mapping 
between a version of PBS and associated messages for that version.

As a result a test writer only needs to check for a match against the symbolic
variable associated to a message rather than the message string itself as the 
latter may change across releases.

PbsMessages is initialized in PBSTestSuite's setUp() method and can therefore 
be used in tests that inherit from PBSTestSuite through the 'messages' instance
variable. For tests that do not inherit from PBSTestSuite, a test writer must
initialize the messages middleware by simply invoking

  self.messages = PbsMessages(version=<PBS version>)
  
The PBS version can be a string representation of the version of PBS or could
directly be obtained from a Server instance through its version attribute, e.g.
self.server.version.

Once instantiated, one can retrieved the value of a message for that version 
of PBS using self.messages.<attribute> where the attribute must be a message
that was added to the Messages Middleware that defines the message string as 
well as a handful of properties associated to the message, see PbsMessages for
details. 


Overview of commands
=====================

Here is an overview of the most common usage of the PTL tools, there are many
more options to control the installation of a package, see the --help option 
of each command for details. 

Note that a handful of PTL specific configuration options can be set in a file
or in the OS environment variable, these options are:

  PTL_CONF_FILE: sets the name of the file in which ptl options are defined,
  defaults to /etc/ptl.conf

  PTL_SUDO_CMD: sets the command to use to acquire super user privilege,
  defaults to 'sudo'

  PTL_RSH_CMD: sets the remote shell command, defaults to "ssh -t"

  PTL_CP_CMD: sets the copy command, defaults to "scp -p"

  PTL_EXPECT_MAX_ATTEMPTS: sets the maximum number of attempts for expect,
  defaults to 15

  PTL_EXPECT_INTERVAL: sets the interval between expect calls, defaults to 3

Note that all these options can be overridden programmatically.

How to use pbs_benchpress
-------------------------

pbs_benchpress is PTL's test harness, it is used to drive testing, logging
and reporting of test suites and test cases.

To list information about a test suite::

  pbs_benchpress -t <TestSuiteName> -i
  
To Run a test suite and/or a test case

   1- If you created a new test suite then rerun:
      python setup.py install
      to have your test installed on the system
   2- To run the entire test suite::
      pbs_benchpress -t <TestSuiteName>  
      where TestSuiteName is the name of the class in the .py file you created
   3- To run a test case part of a test suite::
      pbs_benchpress -t <TestSuiteName> -T <test_case_name>
      where TestSuiteName is as described above and test_case_name is the name
      of the test method in the class
   4- You can run the under various logging levels using the -l option, e.g::
      pbs_benchpress -t <TestSuiteName> -l DEBUG
   5- To run all tests that inherit from a parent test suite class run the 
      parent test suite passing the --follow-child param to pbs_benchpress:
      pbs_benchpress -t <TestSuite> --follow-child
      To exclude specific testsuites, use the --excluding option as such:
      pbs_benchpress -t <TestSuite> --follow-child --exclude=<SomeTest>

An alternative to step 2 is to run the test by the name of the test file, for
example, if a test class is defined in a file named pbs_spidXYZ.py then you
can run it using::

  pbs_benchpress -f ./path/to/pbs_spidXYZ.py

To pass custom parameters to a test suite::

  pbs_benchpress -t <TestSuite> -p <key1>=<val1>,<key2>=<val2>,...

Alternatively you can pass --param-file pointint to a file where parameters
are specified. The contents of the file should be one parameter per line.

  pbs_benchpress -t <TestSuite> --param-file=</path/to/file>

Once params are specified, a class variable called param is set in the Test 
that can then be parsed out to be used in the test. When inheriting from 
PBSTestSuite, the key=val pairs are parsed out and made available in the 
class variable conf, so the test can retrieve the information using::

  if self.conf.has_key(key1):
    ...
    
To set logging level::

  pbs_benchpress -l DEBUG

To display timestamp in output log::

  pbs_benchpress -F
  
To add a comment to the database entry of a test::

  pbs_benchpress -c <comment>

To check that the available Python version is above a minimum::

  pbs_benchpress --min-pyver=<version>

To check that the available Python version is less than a maximum::

  pbs_benchpress --max-pyver=<version>

To set a remote shell command, for example to disable pseudo-tty::

  pbs_benchpress --rsh-cmd="ssh -t"
  
The default remote shell command is set to ssh.

To output all tests info to a SQLite database file::

  pbs_benchpress --info-db=<sqlitefile>
  
To query the tests metadata::

  pbs_benchpress --sql-select="<SQL SELECT STATEMENT>"
  
where the SQL SELECT statement operates on the schema of the ptl_testinfo 
table. The schema is::

  TABLE ptl_testinfo (
     'name VARCHAR(256)', 
     'author VARCHAR(256)', 
     'description TEXT');

For example to find all test cases that have the word "hook" in their 
description use::

  pbs_benchpress --sql-select="SELECT name from ptl_testinfo WHERE 
  description LIKE '%hook%';"

On Linux, to collect coverage data using LCOV/LTP, first ensure that PBS was 
compiled using --set-cflags="--coverage" and that you have the lcov utility 
installed it can be obtained at http://ltp.sourceforge.net/coverage/lcov.php::

  pbs_benchpress -t <TestName> --lcov-data=</path/to/gcov/build/dir>

By default the output data will be written to TMPDIR/pbscov-YYYMMDD_HHMMSS, 
this can be controlled using the option --lcov-out.
By default the lcov binary is expected to be available in the environment, if 
it isn't you can set the path using the option --lcov-bin.

To set a cutoff time after which no test suites are run, set the timeout 
option::

  pbs_benchpress -t <TestSuite1><TestSuite2><TestSuite3> --timeout=300
  
In this example if it takes more than 5 minutes to run test suites 1, 
then test suites 2 and 3 will not be run.

For tests that inherit from PBSTestSuite, to collect procecess information::

  pbs_benchpress -t <TestSuite> -p procmon=<proc name>[:<proc name>],
  procmon-freq=<seconds>

where proc name is a process name such as pbs_server, pbs_sched, pbs_mom.
RSS,VSZ,PCPU info will be collected for each colon separated name.

To control logging, a logging configuration file can be specified::

  pbs_benchpress --log-conf=<conf-file> ...

Logging levels
~~~~~~~~~~~~~~
 
PTL uses the generic unittest log levels: INFO, WARNING, DEBUG, ERROR, FATAL

and three custom log levels: INFOCLI, INFOCLI2, DEBUG2.

INFOCLI is used to log command line calls such that the output of a test run
can be read with anyone familiar with the PBS commands.

INFOCLI2 is used to log a wider set of commands run through PTL. 

DEBUG2 is a verbose debugging level. It will log commands, including return 
code, stdout and stderr.

PBSTestSuite custom parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests that inherit from PBSTestSuite can parametrize a test run using one of 
the following available options (which can be extended by test writers):

   * server: The hostname on which the PBS server/scheduler are running

   * client: The hostname on which the PBS client commands should be run.
     Format is <host>@<path/to/custom pbs conf>

   * mom: The hostname on which the PBS MoM is running

   * servers: Colon-separated list of hostnames hosting a PBS server.
     Servers are then accessible as a dictionary in the instance variable
     servers.

   * moms: Colon-separated list of hostnames hosting a PBS MoM. MoMs are made
     accessible as a dictionary in the instance variable moms.

   * nomom=<host1>:<host2>...: expect no MoM on given set of hosts

   * mode: Sets mode of operation to PBS server. Can be either 'cli' or 'api'.
     Defaults to API behavior.

   * conn_timeout: set a timeout in seconds after which a pbs_connect IFL call
     is refreshed (i.e., disconnected)

   * setuplog: Sets setUp logging to enabled or disabled. Defaults to enabled

   * teardownlog: Sets tearDown logging to enabled or disabled. Defaults to
     enabled

   * skip-teardown: Bypasses tearDown of PBSTestSuite (not custom ones)

   * procinfo: Enables process monitoring thread, logged into ptl_proc_info
     test metrics. The value can be set to _all_ to monitor all PBS processes,
     including pbs_server, pbs_sched, pbs_mom, or a process defined by name.

   * revert-to-defaults=<True|False>: if False, will not revert to defaults.
     True by default.
     revert-hooks=<True|False>: if False, do not revert hooks to defaults.
     Defaults to True. revert-to-defaults set to False overrides this setting.

   * del-hooks=<True|False>: If False, do not delete hooks. Defaults to False.
     revert-to-defaults set to False overrides this setting.

   * revert-queues=<True|False>: If False, do not revert queues to defaults.
     Defaults to True. revert-to-defaults set to False overrides this setting.

   * del-queues=<True|False>: If False, do not delete queues. Defaults to 
     False.
    
   * revert-to-defaults set to False overrides this setting.

   * server-revert-to-defaults: if 'False', don't revert Server to defaults

   * mom-revert-to-defaults: if 'False', don't revert MoM to defaults

   * sched-revert-to-defaults: if 'False', don't revert Scheduler to defaults

   * test-users: colon-separated list of users to use as test users. The users
     specified override the default users in the order in which they appear in
     the PBS_USERS list.

   * data-users: colon-separated list of data users.

   * oper-users: colon-separated list of operator users.

   * mgr-users: colon-separated list of manager users.

   * root-users: colon-separated list of root users.

   * build-users: colon-separated list of build users.

   * clienthost: the hostnames to set in the MoM config file

   * The following attributes are passed in through TestUtils, set through
     pbs_benchpress command-line options:

   * procmon: Enables process monitoring. Multiple values must be colon
     separated. For example to monitor server, sched, and mom use
     procmon=pbs_server:pbs_sched:pbs_mom

   * procmon-freq: Sets a polling frequency for the process monitoring tool.
     Defaults to 10 seconds.


Note that all PBS daemon parameters, such as mom, moms, server, servers, can
specify the PBS instance to refer to by specifying the local/remote
configuration file associated to the desired PBS instance on the given
hostname, for example: moms=hostA:hostA@/alternative/pbs.conf refer to two
different MoM instances, the first one is expected to be listening on hostA's
default MoM configuration file (i.e., PBS_CONF_FILE), the second is as defined
by /alternative/pbs.conf file

When running tests using the PBS command-line interface, the host on which the 
commands are to be run can be configured using the client parameter, e.g.::

  pbs_benchpress -t SmokeTest -p client=<host>@</path/to/pbs.conf.custom>

In addition to the PBSTestSuite built-in parameters, Metascheduling test suite
offers the following:

   * metamoms: colon-separated list of hostnames on which metamoms are running

   * hub: the hostname[@/pbs/conf/path] where the hub is deployed

   * branch: the hostname[@/pbs/conf/path] where a branch is deployed

   * branches: the hostnames[@/pbs/conf/path] where branches are deployed

Notes on building psycopg2 on Linux
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The psycopg2 module is required in order to write to a PostgreSQL database.
The package is availab ein the PbsTestLab/extras directory and can be found
online at http://initd.org/psycopg/download/.

psycopg2 requires PostgreSQL and Python headers and libraries, if they are not
available on your system, you may want to consider using the Python and 
PostgreSQL packages that are installed with PBS under PBS_EXEC, the following
describes the procedure to install psycopg2 using the Python and PostgreSQL 
packages provided by PBS::

  export PATH=$PBS_EXEC/python/bin/:$PATH
  untar/gz psycopg2 tarball
  cd to pyscopg2 directory
  python setup.py build_ext --pg-config=PBS_EXEC/pgsql/bin/pg_config install

Note that when using psycopg2, the pgsql libraries must be available on the 
dynamic linker search path, so make sure to::

  export LD_LIBRARY_PATH=$PBS_EXEC/pgsql/lib:$LD_LIBRARY_PATH

Once this is done, you should be able to run pbs_benchpress and use credentials
defined in --db-access to access and store results in the PostgreSQL database.

How to use pbs_pkgmgr
---------------------

pbs_pkgmgr is useful to install, uninstall, and list packages available or
installed. It is Linux centric for install/uninstall and listing installed
packages. Here are some example usages:

To show mapping of supported platforms to build/test host names::

  pbs_pkgmgr -o list-platforms

To list all 12.0  RHEL5 x64 packages use::

  pbs_pkgmgr -o list-available -P rhel5-64 -v 12.0

To list installed packages::

  pbs_pkgmgr -o list-installed

To install a package::
  
  pbs_pkgmgr -o install -p <remotehost:path/to/package>

To uninstall all PBS versions greater or queal than 11.1::

  pbs_pkgmgr -o uninstall -u ge -v 11.1

To control logging, a logging configuration file can be specified::

  pbs_pkgmgr --log-conf=<conf-file> ...

How to use pbs_metainstaller
----------------------------

pbs_metainstaller is useful to deploy a metascheduling environment, as well
as to deploy PTL itself.

To deploy PTL run::

  pbs_metainstaller -m ptl -o install -p <[remotehost:]/some/PbsTestLabTarBall>
   -t <hostname>

To deploy a Metascheduling environment, see details in pbs_metainstaller 

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

  pbs_loganalyzer --db-name=<name of database> [-d </output/path>]

Note that the sqlite3 module is needed to write out to the DB file. 

To output to a PostgreSQL database (see notes on how to build the required
psycopg2 module below)::

  pbs_loganalyzer --db-access=</path/to/pgsql/cred/file>
  
The file should specify the following::

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

To control logging, a logging configuration file can be specified::

  pbs_loganalyzer --log-conf=<conf-file> ...

How to use pbs_stat
-------------------

pbs_stat is a useful tool to display filtered information from querying
PBS objects. The supported objects are --nodes, --jobs, --resvs, --server,
--queues. The supported operators on filtering attributes or resources are >,
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

-or equivalently (for resources)-::

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

To count the total amount of a resource available on an object::

  pbs_stat -r <resource, e.g. ncpus> -C --nodes

Note that nodes that are not up are not counted

To count the amount of a resource on some object::
  
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
        container = server:minita.pbspro.com
        limit_type = max_run_soft
        remainder = -1
        usage/limit = 1/0


if a server soft limit is set to 0 on generic users::

    qmgr -c "set server max_run_soft=[u:PBS_GENERIC=0]"

then pbs_stat --limits-info will show::

    u:user1/PBS_GENERIC
        container = server:minita.pbspro.com
        limit_type = max_run_soft
        remainder = -1
        usage/limit = 1/0

To print a site report that summarizes some key metrics from a site::

  pbs_stat --report

optionally, use the path to a pbs_diag using the -d option to summarize that
site's information.

To show the number of privileged ports in use::

  pbs_stat --pports

To show information directly from the database (requires psycopg2 module)::
 
  pbs_stat --db-access=<path/to/dbaccess_file> --<objtype> [-a <attribs>]

where the dbaccess file is of the form::

  user=<value>
  password=<value>
  # and optionally
  [port=<value>]
  [dbname=<value>]

The Python PostgreSQL module can be obtained from 
http://initd.org/psycopg/download/
See notes on building psycopg2 above for additional details.

To control logging, a logging configuration file can be specified::

  pbs_stat --log-conf=<conf-file> ...

How to use pbs_config
---------------------

pbs_config is useful in the following cases, use:

--revert-config: to revert a configuration of PBS entities specified as one or
more of --scheduler, --server, --mom to its default configuration. Note that
for the server, non-default queues and hooks are not deleted but disabled
instead.

--save-config: save the configuration of a PBS entity, one of --scheduler,
--server, --mom to file. The server saves the resourcedef, a qmgr print
server, qmgr print sched, qmgr print hook. The scheduler saves sched_config,
resource_group, dedicated_time, holidays. The mom saves the config file.

--load-config: load configuration from file. The changes will be applied to
all PBS entities as saved in the file.

--vnodify: create a vnode definition and insert it into a given MoM. There are
many options to this command, see the help page for details.

--switch-version: swith to a version of PBS installed on the system. This
only supports modifying the PBS installed on a system that matches
PBS_CONF_FILE.

To check if the users and groups required for automated testing are defined as
expected on the system::

  pbs_config --check-users

To make users and groups as required for automated testing::

  pbs_config --make-ug

To setup, start, and add (to the server) multiple MoMs::

  pbs_config --multi-mom=<num> -a <attributes> --serverhost=<host>

The multi-mom option creates <num> pbs.conf files, prefixed by pbs.conf_m
followed by an incrementing number by default, for which each configuration
file has a unique PBS_HOME directory that is defined by default to be PBS_m
followed by the same incrementing number as the configuration file. The
configuration prefix can be changed by passing the --conf-prefix option and
the PBS_HOME prefix can be changed via --home-prefix.

To make a PBS Server/Scheduler/MoM mimic the snapshot of a pbs_diag::

  pbs_config --as-diag=<path/to/diag>
  
This will set all server and queue attributes from the diag, copy sched_config,
resource_group, holidays, resourcedef, all site hooks, and create and insert a
vnode definition that translates all of the nodes reported by pbsnodes -av.
There may be some specific attributes to adjust, such as pbs_license_info, 
or users or groups, that may prevent submission of jobs.
 
To control logging, a logging configuration file can be specified::

  pbs_config --log-conf=<conf-file> ...

How to use pbs_sim
------------------

pbs_sim is a wrapper to a scheduler unit testing engine. It uses that engine
to simulate running a scheduling cycle based on a given snapshot collected
from a pbs_diag.

In order to use the tool, the scheduler testing engine binary must be
available on the path. Note that this binary is not released with PBS Pro.

To convert information from a pbs_diag snapshot into data interpretable by the
scheduler engine::

  pbs_sim -d <path/to/diag> -s <path/to/simulation/dir>

To run a scheduling cycle with a given pbs_diag snapshot::

  pbs_sim -s <path/to/diag> -e <path/to/sched/engine> -S

  Or

  pbs_sim -d <path/to/diag> -e <path/to/sched/engine> -S


How to use pbs_aws
------------------

pbs_aws is a wrapper over the boto API to Amazon AWS SOAP services. In
order to use it, the boto module is required, it can be downloaded from
https://pypi.python.org/pypi/boto/

pbs_aws expects that your AWS_SECRET_KEY and AWS_ACCESS_KEY are defined in the
OS environment. In order to get those keys, you must have an AWS account and
can retrieve this information by logging on to your account at
http://aws.amazon.com.

To list all instances that you own::

  pbs_aws --list-instances

To list all images that you own::

  pbs_aws --list-images

To list all reservations that you own::

  pbs_aws --list-reservations

To start an instance::

  pbs_aws --instance=<instance-id> --run

TO run an image::

  pbs_aws --image=<image-id> --run

To update an instance::

  pbs_aws --instance=<instance-id> --update

To stop all instances::

  pbs_aws --stop-all

To terminate all instances::

  pbs_aws --terminate-all

To control logging, a logging configuration file can be specified::

  pbs_aws --log-conf=<conf-file> ...

How to use pbs_extend_walltime
------------------------------

pbs_extend_walltime extends the walltime of running jobs that have reached
a set walltime usage (defaults to 80%) by a certain duration (defaults to
1hr).

To extend all running jobs that have reached 80% or more of their walltime::

  pbs_extend_walltime

To change the threshold (which defaults to 80%), to 50%::

  pbs_extend_walltime -t 50

To change the duration to extend the walltime to 2hr (from default of 1hr)::

  pbs_extend_walltime -e 7200

To skip from consideration running jobs that have a given attribute, for
example, a custom resource 'do_not_extend_walltime' is on the job::

  pbs_extend_walltime -s 'Resource_List.do_not_extend_walltime'

To log output to a file::

  pbs_extend_walltime -o /tmp/pbs_walltime_extension.log

To control logging, a logging configuration file can be specified::

  pbs_extend_walltime --log-conf=<conf-file> ...

How to use pbs_jobs_at
----------------------

pbs_jobs_at shows a list of jobs that were running at a certain time in the
past. The tool works by parsing accounting logs around the time of interest.
To limit the amount of parsing done, the tool offers an option, --num-days,
that brackets the number of days to parse before and after the date and time
of interest, this option defaults to one day. To minimize the number of jobs
reported, the option should ideally be set to the longest running job
duration.

To report jobs running at 8pm on May 23rd 2013::

  pbs_jobs_at --time="05/23/2013 20:00:00"

the command above will process logs on May 22nd and May 24th.

To expand the search window to May 20th through May 26th::

  pbs_jobs_at --time="05/23/2013 20:00:00" --num-days==3

To show jobs that were running on node1 and node2 only::

  pbs_jobs_at --time="05/23/2013 20:00:00" --nodes=node1,node2

To process specific accounting files, as opposed to files implicitly derived
from the time that are processed from PBS_HOME/server_priv/accounting::

  pbs_jobs_at --time="05/23/2013 20:00:00" -a 20130523.txt,20130524.txt

If accounting logs are large, a progress bar can be shown by passing the
--show-progress option::

  pbs_jobs_at --time="05/23/2013 20:00:00" --show-progress

To control logging, a logging configuration file can be specified::

  pbs_jobs_at --log-conf=<conf-file> ...

If nodes are specified, the tool outputs for each node name, a list of jobs,
one per line, that were running on that node at that given time. If no nodes
are specified, the tool outputs a list of jobs and nodes on which they were
running, one per line.

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

How to use pbs_snapshot
-----------------------

pbs_snapshot collects server, queues, nodes, jobs, reservations, as well as
configuration information, i.e., sched_config, resource_group, holidays, 
dedicated_time.

The tool's primary purpose is to convert data into a format that is suitable 
for input to a stand-alone scheduler.

The information can be collected from a live server, as such:

  pbs_snapshot -H <hostname>
  
where hostname defaults to the PBS_SERVER value set in the pbs.conf file and 
localhost otherwise.

Information can also be collected from a pbs_diag directory, as such:

  pbs_snapshot -d <path/to/pbs_diag>
  
pbs_snapshot can anonymize data collected by obfuscating attributes and/or
resources. There are several options available to obfuscate:
 
  pbs_snapshot --obfuscate 
 
Obfuscates euser, egroup, project, account_name and deletes mail_from, 
job_owner, managers, operators, variable_list, ACLs, group_list, job name, and 
jobdir 

The mapping of obfuscated data can be stored in a file by specifying a path
and filename to pbs_snapshot as such::
 
  pbs_snapshot --obfuscate --map=</path/to/obfuscated/map>

Note that the mapping information is not collected otherwise.

The following options are available to achieve a finer control on the 
attributes and/or resources to obfuscate:

  --attr-del=<list or dict>: delete/do_not_report the attributes specified
  
  --resc-del=<list or dict>: delete/do_not_report the resources specified
   
  --obfuscate-attr-val=<list or dict>: obfuscate the value of named attributes
  
  --obfuscate-resc-val=<list or dict>: obfuscate the values of named resources. 

  --obfuscate-resc-key=<list or dict>: obfuscate the name of a resource.

  --obfuscate--attr-key=<list or dict>: obfuscate the name of an attribute (
  not expected to be a common case)
   
The values for each attribute or resource to obfuscate can be a Python list
or a dictionary. The dictionary provides a mapping of the desired substitutions
to apply as part of the obfuscation process.
  
Here are some examples:

To obfuscate the values associated to a custom resource foo:

  pbs_snapshot --obfuscate-resc-val=foo
  
To obfuscate an euser named alice to be XYZ12:

  pbs_snapshot --obfuscate-attr-val='{"euser":{"alice":"XYZ12"}'
  
Note that when obfuscating euser/egroup, the FGC limits, resource_group file 
are updated - that is, in addition to the euser/egroup attributes.

When obfuscating a custom resource name, i.e., --obfuscate-resc-key, the 
resources file, scheduling formula, schedselect and select attributes, are also
updated - in iaddition to all attributes on which this resource may be defined,
such as Resource_List, resources_available, resources_used, max_run_res, etc...


Caveats
=======

Non-Default PBS_CONF_FILE
-------------------------

When using CLI mode with a non-default PBS_CONF_FILE, operations that are run
as another user, and/or via sudo are done by creating a temporary file, writing
the command to execute in that file, and executing that file as the user. These
steps are needed to circumvent differences in sudo implementatiosn across 
systems. For example on RHEL5/CentOS5 (sudo version 1.6) it is not possible to
pass an environment variable through sudo such as `sudo ENV_VAR=ENV_VAL <cmd>`,
on most systems, sudo, by default, doesn't allow passing environment variables 
through a user's login, despite on some systems allowing sudo -E to perform 
such operations. Administrators may configure sshd_config to allow passing of 
some environment variables, but PTL does not depend on this administrative 
configuration. 

Special handling for qmgr
-------------------------

While commands are generally run from the client host on which PTL is run, all 
manager operations are issued on the host on which the server is running.
This is a known limitation that is primarily due to the fact that getting the 
escape sequence correctly for all qmgr commands has proven more tedious than 
expected (so yes, taking the simpler route for now), for example:

disabling scheduling on a remote host with a default PBS_CONF_FILE would be::

  qmgr -c 's s scheduling=False' <remotehost>

While with a non-default PBS_CONF_FILE would be::

  PBS_CONF_FILE=<custom_conf> qmgr -c 's s scheduling=False' <remotehost>

The implementation details to get PTL to correctly escape these two commands
across all the OS flavors with and without impersonation was far too tricky, 
the framework therefore standardizes on issuing the command directly on the 
host where the PBS server is running.

Another caveat of manager operations is that all commands to list hooks, or
set job_sort_formula are executed as root using the CLI, this is due to a 
security built into PBS Pro that disallows these operations to be performed
by any other user than root and/or from a remote host.

Remote impersonation submit 
---------------------------

User impersonation for job submission requires exec'ing the pbs_as script 
as that user. pbs_as must exist on all hosts on which the framework is run,
it is run out of the PTL_EXEC directory when that environment variable is set,
otherwise, it is expected to be in the PATH of privileged users on the target
machine on which the command is to run.

Note that jobs are by default submitted using -koe so the job's output and 
error files are not copied back to the submission host unless explicitly 
requested for the job. 

Standing reservation PBS_TZID
-----------------------------

Standing reservations can not be submitted using the API interface alone due
to the need to set the PBS_TZID environment variable, such reservations are
always submitted using a CLI.

qmgr operations for hooks and formula
-------------------------------------

Qmgr operations for hooks and for the job_sort_formula must be done as root,
they are performed over the CLI.

CLI and API differences
-----------------------

PTL redefines the PBS IFL such that it can dynamically call them via either
the API or the CLI. The methods are typically named after their pbs\_ifl 
counterpart omitting the pbs\_ prefix, for example pbs_manager() becomes 
manager() in PTL. Each method will typically either return the return code
of its API/CLI counterpart, or raise a specific PTL exception (see section 
on PTL exceptions for details). In some cases (e.g. manager) the return value
may be that of the call to the expect() method.

When calling expect on an attribute value, the value may be different
depending on whether the library is operating in CLI or API mode; as an
example, when submitting a reservation, expecting it to be confirmed via the
API calls for an expect of {'reserve_state':'2'} whereas using the CLI one
would expect {'reserve_state':'RESV_CONFIRMED'}. 
This can be handled in several ways:
The preferred way is to use the MATCH_RE operation on the attribute and
check for either one of the possible values: for example to match either
RESV_CONFIRMED or 2 one can write::

   Server().expect(RESV, {'reserve_state':(MATCH_RE,"RESV_CONFIRMED|2")})

An alternative way is to set the operating mode to the one desired at the 
beginning of the test (to one of PTL_API, or PTL_CLI) and ensure it is set
accordingly by calling get_op_mode(), or handle the response in the test by 
checking if the operating mode is CLI or API, which is generally speaking 
more robust and the favored approach as the automation may be run in either 
mode on different systems.

List (non-exhaustive) of attribute type differences between CLI and API:

* reserve_state

* all times: ctime, mtime, qtime, reserve_start, reserve_end, 
  estimated.start_time, Execution_Time

Creating temp files
-------------------

When creating temp files, favor the use of DshUtils().mkstemp because it
handles paths to Cygwin correctly.

Unsetting attributes
--------------------

To unset attributes in alterjob, set the attribute value to '' (two single
quotes) in order to escape special quote handling in Popen.

Stat'ing objects via db-access
------------------------------

Not all object attributes are written to the DB, as a result, when using 
pbs_stat with db-access enabled, information may appear to be missing.

Scheduler holidays file handling
--------------------------------

When reverting scheduler's default configuration, the holidays file is
reverted only if it was specifically parsed, either by calling parse_holidays
or by calling set_prime_time, to the contents of the file first parsed. In
other words, if the contents of the file were updated outside PbsTestLab, and
edited in PbsTestLab, the file will be reverted to that version rather than
the vanilla file that ships with PBS Pro.

Interactive Jobs
----------------

Interactive jobs are only supported through CLI operations and require the 
pexpect module to be installed.

Interactive Jobs are submitted as a thread that sets the jobid as soon as it
is returned by qsub -I, such that the caller can get back to monitoring
the state of PBS while the interactive session goes on in the thread.

The commands to be run within an interactive session are specified in the
job's interactive_script attribute as a list of tuples, where the first
item in each tuple is the command to run, and the subsequent items are
the expected returned data.

Implementation details:

On Windows, cygwin, sshd (as a cygwin run service) and a terminal
emulator, winpty-0.1, are required to be installed (see Windows support 
section).

The submission of an interactive job requires passing in job attributes, 
the command to execute (i.e. path to qsub -I), the hostname (needed for Windows
ssh impersonation), and a user-to-password map, details follow:

On Linux/Unix:

* when not impersonating:

pexpect spawns the qsub -I command and expects a prompt back, for each
tuple in the interactive_script, it sends the command and expects to
match the return value.

* when impersonating:

pexpect spawns sudo -u <user> qsub -I. The rest is as described in 
non-impersonating mode.

On Windows:

* when not impersonating:

pexpect spawns qsub -I through the terminal emulator, e.g.
/path/to/console.exe /cygwin/path/to/qsub -I. The rest is as described for
Unix, with the caveat that interaction with the Windows terminal is not
working as smoothly as on Linux/Unix yet.

* when impersonating:

pexpect spawns ssh -t <user>@<host> /path/to/console.exe /cygpath/to/qsub -I
The rest is as described when not impersonating.

Process memory usage monitoring
-------------------------------

The process monitoring tools built-in to ProcUtils currently works only on 
Linux, Solaris and Windows, not on AIX and HPUX.

Note that on HPUX platforms, the environment variable UNIX95 must be set in
order to use the UNIX Standard ps tool that PbsTestLab depends on instead of 
the HP provided ps tool. 

