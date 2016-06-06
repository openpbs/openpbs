Brief tutorial about common library API
=======================================

Most of the examples below show specific calls to the library functions,
there are typically many more derivations possible, check the :ref:`full API documentation <full-api>`
for details.

Importing the library
---------------------
Because the library may leverage SWIG-wrappers it is preferred to import all so that the pbs_ifl module imports all IFL symbols as shown below:

::

  from ptl.lib.pbs_testlib import *

Instantiating a Server
----------------------
Instantiate a Server object and populate it's attributes values after stat'ing the PBS server.

::

  server = Server('remotehost')
  OR
  server = Server() # no hostname defaults to the FQDN of the current host

Adding a user as manager
------------------------

::

  server.manager(MGR_CMD_SET, SERVER, {ATTR_managers: (INCR, 'user@host')})

Reverting server's configuration to defaults
--------------------------------------------

::

  server.revert_to_defaults()


Instantiating a Job
-------------------

::

  job = Job()

Setting job attributes
----------------------

::

  job.set_attributes({'Resource_List.select':'2:ncpus=1','Resource_List.place':'scatter'})

Submitting a job
----------------

::

  server.submit(job)

Stat'ing a server
-----------------

::

  server.status()

Stat'ing all jobs job_state attribute
-------------------------------------

::

  server.status(JOB, 'job_state')

Counting all vnodes by state
----------------------------

::

  server.counter(NODE, 'state')

Expecting a job to be running
-----------------------------

::

  server.expect(JOB, {'job_state':'R','substate':42}, attrop=PTL_AND, id=jid)

where `jid` is the result of a server.submit(job)

Each attribute can be given an operand, one of LT, LE, EQ, GE, GT, NE
For example to expect a job to be in state R and substate != 41::

  server.expect(JOB, {'job_state':(EQ,'R'), 'substate':(NE,41)}, id=jid)

Instantiating a Scheduler object
--------------------------------

::

  sched = Scheduler('hostname')
  OR
  sched = Scheduler() # no hostname defaults to the FQDN of the current host

Setting scheduler configuration
-------------------------------

::

  sched.set_sched_config({'backfill':'true  ALL'})

Reverting scheduler's configuration to defaults
-----------------------------------------------

::

  sched.revert_to_defaults()


Instantiating a MoM
-------------------

::

  mom = MoM('hostname')

Creating a vnode definition file
--------------------------------

::

  attrs = {'resources_available.ncpus':8,'resources_available.mem':'8gb'}
  vdef = node.create_vnode_def('vn', attrs, 10)

Inserting a vnode definition to a MoM
-------------------------------------

::

  mom.insert_vnode_def(vdef)

Reverting mom's configuration to defaults
-----------------------------------------

::

  mom.revert_to_defaults()
