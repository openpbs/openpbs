Introduction of PbsTestLab
==========================

Command line tools
------------------

- :ref:`pbs_benchpress <pbs_benchpress>` used to run unit tests
- :ref:`pbs_loganalyzer <pbs_loganalyzer>` used to analyze PBS logs
- :ref:`pbs_stat <pbs_stat>` used to filter PBS objects based on select properties
- :ref:`pbs_config <pbs_config>` used to configure services, e.g., create vnodes
- :ref:`pbs_py_spawn <pbs_py_spawn>` used to invoke a pbs_py_spawn action associated to a job running on a MoM
- :ref:`pbs_compare_results <pbs_compare_results>` used to compare performance test results

Library
-------

- Provides PBS IFL operations through either SWIG-wrappers or PBS CLI e.g. qstat, qsub etc.
- Encapsulated PBS entities: :py:class:`~ptl.lib.pbs_testlib.Server`, :py:class:`~ptl.lib.pbs_testlib.Scheduler`,
  :py:class:`~ptl.lib.pbs_testlib.MoM`, :py:class:`~ptl.lib.pbs_testlib.Comm`, :py:class:`~ptl.lib.pbs_testlib.Queue`,
  :py:class:`~ptl.lib.pbs_testlib.Job`, :py:class:`~ptl.lib.pbs_testlib.Reservation`, :py:class:`~ptl.lib.pbs_testlib.Hook`,
  :py:class:`~ptl.lib.pbs_testlib.Resource`
- Utility class to convert batch status and attributes to Python lists, strings and dictionaries
- High-level PBS operations to operate on PBS entities including nodes, queues, jobs, reservations, resources, and server

Utilities
---------

- Logging to parse and report metrics from :py:class:`Server <ptl.utils.pbs_logutils.PBSServerLog>`, :py:class:`Scheduler <ptl.utils.pbs_logutils.PBSSchedulerLog>`,
  :py:class:`MoM <ptl.utils.pbs_logutils.PBSMoMLog>` and :py:class:`Accounting <ptl.utils.pbs_logutils.PBSAccountingLog>` logs.
- Distributed tools to transparently run commands locally or remotely, including file copying.

Plugins
-------

- Provides utilities to load, run and get info of test cases in form of `Nose framework`_ plugins

Documentation
-------------

- API documentation describing the capabilities of the framework and utilities
- For the command-line tools use the -h option for help

Directory structure
-------------------

::

    fw
    |- bin -- Command line tools
    |- doc -- Documentation
    `- ptl -- PTL package
       |- lib -- Library
       `- utils -- Utilities
          `- plugins -- plugins of PTL for Nose framework

.. _Nose framework: http://readthedocs.org/docs/nose/
