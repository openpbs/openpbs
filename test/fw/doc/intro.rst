Introduction of PbsTestLab
==========================

Command line tools
------------------

- ``pbs_benchpress`` used to run unit tests
- ``pbs_loganalyzer`` used to analyze PBS logs
- ``pbs_swigify`` used to build IFL swig wrappers and copy them over to the library
- ``pbs_as`` used by the library to impersonate a user for API operations
- ``pbs_stat`` used to filter PBS objects based on select properties
- ``pbs_config`` used to configure services, e.g., create vnodes
- ``pbs_cov`` used to generate lcov/ltp (gcov) coverage analysis

Library
-------

- Provides PBS IFL operations through either SWIG-wrappers or PBS CLI e.g. qstat, qsub etc.
- Encapsulated PBS entities: Server, Scheduler, MoM, Comm, Queue, Job, Reservation, Hook, Resource
- Utility class to convert batch status and attributes to Python lists, strings and dictionaries
- High-level PBS operations to operate on PBS entities including nodes, queues, jobs, reservations, resources, and server

Utilities
---------

- Logging to parse and report metrics from server/scheduler/MoM/Accounting logs.
- Distributed tools to transparently run commands locally or remotely, including file copying.

Plugins
-------

- Provides utilities to load, run test cases in form of Nose plugins

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
