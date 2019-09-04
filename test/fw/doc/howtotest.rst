How to write test suite/case
============================

Assumptions
-----------

The library and utility make several assumptions about the environment:

- OS should be Unix or Linux
- Password-less authentication should be setup on all systems
- Required users are available (see ``pbs_config --check-ug``)
- The PTL package should be installed on all systems
- The file system layout should be same on all systems
- PBS_CONF_FILE variable should be set on all systems

Naming conventions, recommended practices, and guidelines
---------------------------------------------------------

Write the test in a filename prefixed by ``pbs_`` followed by feature name
``pbs_<featurename>.py``

Name of the test class should be  prefixed by ``Test`` and followed by unique
explanatory name ``Test<feature>``

Each test case name should start with ``test_`` followed by lower case characters.
``test_<testname>`` Test case name should be unique, accurate & explanatory, but
concise, can have multiple words if needed. The test cases running sequence is
unordered (some claim that it is lexicographic ordering but it is best to not write
your test suites based on such assumptions).

Put every functionality that is common to all test cases in its own method,
and consider adding it to the library or utility if it is a generic interface to
PBS.

PTL strongly follows PEP8 Python coding style. so please style your code to follow
PEP8 Python codeing style. You can find PEP8 at https://www.python.org/dev/peps/pep-0008/

Some info about PBSTestSuite
----------------------------

Tests that inherit functionality from a parent class such as PBSTestSuite have
available to them predefined functionality for setUpclass, setUp, tearDownclass, tearDown,
or whatever capability they make available in the parent class.

PBSTestSuite offers the following:

.. topic:: setUpclass:

  - Parse custom parameters that are passed in to the Class variable called 'param' (i.e. -p option to pbs_benchpress).
    The built-in parameters are:

    - servers: Colon-separated list of hostnames hosting a PBS server/scheduler.
    - server: The hostname on which the PBS Server/scheduler is running
    - moms: Colon-separated list of hostnames hosting a PBS MoMs.
    - mom: The hostname on which the PBS MoM is running
    - nomom: Colon-separated list of hostnames where not to expect MoM running.
    - comms: Colon-separated list of hostnames hosting a PBS Comms.
    - comm: The hostname on which the PBS Comm is running
    - client: For CLI mode only, name of the host on which the PBS client commands are to be run from.
    - clienthost: the hostnames to set in the MoM config file
    - mode: Mode of operation to PBS server. Can be either ‘cli’ or ‘api’.
    - conn_timeout: set a timeout in seconds after which a pbs_connect IFL call is refreshed (i.e., disconnected)
    - skip-setup: Bypasses setUp of PBSTestSuite (not custom ones)
    - skip-teardown: Bypasses tearDown of PBSTestSuite (not custom ones)
    - procinfo: Enables process monitoring thread, logged into ptl_proc_info test metrics.
    - procmon: Colon-separated process name to monitor. For example to monitor server, sched, and mom use procmon=pbs_server:pbs_sched:pbs_mom
    - procmon-freq: Sets a polling frequency for the process monitoring tool. Defaults to 10 seconds.
    - revert-to-defaults=<True|False>: if False, will not revert to defaults. Defaults to True.
    - revert-hooks=<True|False>: if False, do not revert hooks to defaults. Defaults to True. revert-to-defaults set to False overrides this setting.
    - del-hooks=<True|False>: If False, do not delete hooks. Defaults to False. revert-to-defaults set to False overrides this setting.
    - revert-queues=<True|False>: If False, do not revert queues to defaults. Defaults to True. revert-to-defaults set to False overrides this setting.
    - revert-resources=<True|False>: If False, do not revert resources to defaults. Defaults to True. revert-to-defaults set to False overrides this setting.
    - del-queues=<True|False>: If False, do not delete queues. Defaults to False. revert-to-defaults set to False overrides this setting.
    - del-vnodes=<True|False>: If False, do not delete vnodes on MoM instances. Defaults to True.
    - server-revert-to-defaults=<True|False>: if False, don’t revert Server to defaults
    - comm-revert-to-defaults=<True|False>: if False, don’t revert Comm to defaults
    - mom-revert-to-defaults=<True|False>: if False, don’t revert MoM to defaults
    - sched-revert-to-defaults=<True|False>: if False, don’t revert Scheduler to defaults
    - test-users: colon-separated list of users to use as test users. The users specified override the default users in the order in which they appear in the PBS_USERS list.
    - data-users: colon-separated list of data users.
    - oper-users: colon-separated list of operator users.
    - mgr-users: colon-separated list of manager users.
    - root-users: colon-separated list of root users.
    - build-users: colon-separated list of build users.

  - Check required users are available or not
  - Creates servers, moms, schedulers and comms object

.. topic:: setUp:

  - Check that servers, schedulers, moms and comms services are up or not.
  - If any of services is down then starts that services.
  - Add the current user to the list of managers
  - Bring servers, schedulers, moms and comms configurations back to out-of-box defaults
  - Cleanup jobs and reservations
  - If no nodes are defined in the system, a single 8 cpu node is defined.
  - start process monitoring thread if process monitoring enabled

.. topic:: tearDown:

  - If process monitoring is enabled the stop process monitoring thread and collect process metrics

.. topic:: analyze_logs:

  - Analyzes all PBS daemons and accounting logs and collect logs metrics

You can take advantage of PBSTestSuite's setUp and tearDown methods and extend
their functionality by overriding the setUp and/or tearDown methods in your
own class, for example

::

      class TestMyFix(PBSTestSuite):

            def setUp(self):
                PBSTestSuite.setUp(self)
                # create custom nodes, server/sched config, etc...

For detailed test directory structure one can refer to below link:

https://pbspro.atlassian.net/wiki/display/DG/PTL+Directory+Structure+and+Naming+Conventions

Writing a test suite
--------------------

See ptl/tests/pbs_smoketest.py for some basic examples how to write test suite.

Whenever possible consider making the test class inherit from PBSTestSuite, it
is a generic setup and teardown class that delete all jobs and reservations,
reverts PBS deamons configuration to defaults and ensures that there
is at least one cpu to schedule work on.

How to mark a test as skipped
------------------------------

The unittest module in Python versions less than 2.7 do not support
registering skipping tests. PTL offers a mechanism to skip test, it
is however up to the test writer to ensure that a test is not run if
it needs to be skipped.

.. topic:: skipTest:

  Tests that inherit from PBSTestSuite inherit a method called ``skipTest`` that
  is used to skip tests, whenever a test is to be skipped, that method should be
  called and the test should return.

.. topic:: checkModule:

  Tests that inherit from PBSTestSuite inherit a method called ``checkModule`` that
  is used to skip tests if require Python module is not installed.

.. topic:: skipOnCray:

  Tests that inherit from PBSTestSuite inherit a method called ``skipOnCray`` that
  is used to skip tests on Cray platform.

.. topic:: skipOnShasta:

  Tests that inherit from PBSTestSuite inherit a method called ``skipOnShasta`` that
  is used to skip tests on Cray Shasta platform.

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
ATTR_geometry: "W job_geometry="
and add it to ptl/lib/pbs_ifl_mock.py as:
ATTR_geometry: "job_geometry".
In order to get the API to take the new attribute into consideration,
pbs_swigify must be rerun so that symbols from pbs_ifl.h are read in.
