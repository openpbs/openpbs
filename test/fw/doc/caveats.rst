Caveats
=======

Standing reservation PBS_TZID
-----------------------------

Standing reservations cannot be submitted using the API interface alone due
to the need to set the PBS_TZID environment variable, such reservations are
always submitted using a CLI.

qmgr operations for hooks and formula
-------------------------------------

Qmgr operations for hooks and for the job_sort_formula must be done as root,
they are performed over the CLI.

CLI and API differences
-----------------------

PTL redefines the PBS IFL such that it can dynamically call them via either
the API or the CLI. The methods are typically named after their PBS IFL
counterpart omitting the `pbs_` prefix, for example pbs_manager() becomes
manager() in PTL. Each method will typically either return the return code
of its API/CLI counterpart, or raise a specific PTL exception. In some cases
(e.g. manager) the return value may be that of the call to the expect() method.

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

 - reserve_state
 - all times: ctime, mtime, qtime, reserve_start, reserve_end, estimated.start_time, Execution_Time

Creating temp files
-------------------

When creating temp files, favor the use of DshUtils().mkstemp

Unsetting attributes
--------------------

To unset attributes in alterjob, set the attribute value to '' (two single
quotes) in order to escape special quote handling in Popen.

Example::

 obj.unset_attributes([ATTR_Arglist])

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
the vanilla file that ships with PBS.

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

.. topic:: Implementation details:

  The submission of an interactive job requires passing in job attributes,
  the command to execute (i.e. path to qsub -I), the hostname and a
  user-to-password map, details follow:

  On Linux/Unix:

    - when not impersonating:

      pexpect spawns the qsub -I command and expects a prompt back, for each
      tuple in the interactive_script, it sends the command and expects to
      match the return value.

    - when impersonating:

      pexpect spawns sudo -u <user> qsub -I. The rest is as described in
      non-impersonating mode.
