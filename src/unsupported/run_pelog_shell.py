# coding: utf-8
"""

run_pelog_shell.py - PBS hook that runs the classic shell script prologue or
epilogue, if it exists, while still being able to use execjob_prologue or
execjob_epilogue hooks. Also adds the capability of running parallel prologue
or epilogue shell scripts and Torque compatibility.

Copyright (C) 1994-2019 Altair Engineering, Inc.
For more information, contact Altair at www.altair.com.

This file is part of the PBS Professional ("PBS Pro") software.

Open Source License Information:

PBS Pro is free software. You can redistribute it and/or modify it under the
terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.
See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Commercial License Information:

For a copy of the commercial license terms and conditions,
go to: (http://www.pbspro.com/UserArea/agreement.html)
or contact the Altair Legal Department.

Altair’s dual-license business model allows companies, individuals, and
organizations to create proprietary derivative works of PBS Pro and
distribute them - whether embedded or bundled with other software -
under a commercial license agreement.

Use of Altair’s trademarks, including but not limited to "PBS™",
"PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
trademark licensing policies.

"""

"""
On the primary execution host (the first host listed in PBS_NODEFILE), the
standard naming convention of 'prologue' and 'epilogue' apply. Parallel
prologues and epilogues use the naming conventions 'pprologue' and 'pepilogue',
respectively, but will only run on the secondary execution hosts. Classic
prologues and epilogues in Windows are not currently implemented.

Parallel prologues will not run until a task associated with the job (i.e. via
pbs_attach, pbs_tmrsh, pbsdsh) begins on the secondary execution hosts.

Parallel epilogues will not run unless the prologue ran successfully on the
primary execution host. Only the primary execution host will have a value for
resources_used in epilogue argument $7.

We assume the same requirements as listed in PBS Professional 13.0
Administrator's Guide 11.5.4 for running all types of prologue and epilogue
shell scripts:
    - The script must be in the PBS_HOME/mom_priv directory
    - The prologue must have the exact name "prologue" under UNIX/Linux, or
      "prologue.bat" under Windows
    - The epilogue must have the exact name "epilogue" under UNIX/Linux, or
      "epilogue.bat" under Windows
    - The script must be written to exit with one of the zero or positive exit
      values listed in section 11.5.12, "Prologue and Epilogue Exit Codes". The
      negative values are set by MOM
    - Under UNIX/Linux, the script must be owned by root, be readable and exe-
      cutable by root, and cannot be writable by anyone but root
    - Under Windows, the script's permissions must give "Full Access" to the
      local Administrators group on the local computer

The hook will kill the prologue/epilogue after the hook_alarm time - 5 has been
reached. At this point the job will be requeued/deleted depending on the value
of DEFAULT_ACTION below. If the hook_alarm time is not available, the default
value of 30 seconds is assumed, giving the prologue/epilogue approximately 25
seconds to complete.

Installation:
Technically you could create a single hook that fires on both the
execjob_prologue and the execjob_epilogue events, but to ensure execution order
we separate the two into the individual events by creating two separate hooks
that refer to the same hook script.

Edit the run_pelog_shell.ini to make configuration changes, then create and
import the hook as follows.

As root, run the following:
qmgr << EOF
create hook run_prologue_shell
set hook run_prologue_shell event = execjob_prologue
set hook run_prologue_shell enabled = true
set hook run_prologue_shell order = 1
set hook run_prologue_shell alarm = 35
import hook run_prologue_shell application/x-python default run_pelog_shell.py
import hook run_prologue_shell application/x-config default run_pelog_shell.ini

create hook run_epilogue_shell
set hook run_epilogue_shell event = execjob_epilogue
set hook run_epilogue_shell enabled = true
set hook run_epilogue_shell order = 999
set hook run_prologue_shell alarm = 35
import hook run_epilogue_shell application/x-python default run_pelog_shell.py
import hook run_epilogue_shell application/x-config default run_pelog_shell.ini
EOF

Any further configuration changes to run_pelog_shell.ini will require
re-importing the file to both hooks:
qmgr << EOF
import hook run_prologue_shell application/x-config default run_pelog_shell.ini
import hook run_epilogue_shell application/x-config default run_pelog_shell.ini
EOF

"""

"""

Direct modifications to this hook are not recommended.
Proceed at your own risk.

"""

import sys
import os
import time
import pbs
RERUN = 14
DELETE = 6

# The following constants can be modified in run_pelog_shell.ini to match
# site preferences.

ENABLE_PARALLEL = False
VERBOSE_USER_OUTPUT = False
DEFAULT_ACTION = RERUN
TORQUE_COMPAT = False


# Set up a few variables
start_time = time.time()
pbs_event = pbs.event()
hook_name = pbs_event.hook_name
hook_alarm = 30  # default, we'll read it from the .HK later
DEBUG = False  # default, we'll read it from the .HK later
job = pbs_event.job

# The trace_hook function has been written to be portable between hooks.


def trace_hook(**kwargs):
    """Simple exception trace logger for PBS hooks
    loglevel=<int> (pbs.LOG_DEBUG): log level to pass to pbs.logmsg()
    reject=True: reject the job upon completion of logging trace
    trace_in_reject=<bool> (False): pass trace to pbs.event().reject()
    trace_in_reject=<str>: message to pass to pbs.event().reject() with trace
    """
    import sys

    if 'loglevel' in kwargs:
        loglevel = kwargs['loglevel']
    else:
        loglevel = pbs.LOG_ERROR
    if 'reject' in kwargs:
        reject = kwargs['reject']
    else:
        reject = True
    if 'trace_in_reject' in kwargs:
        trace_in_reject = kwargs['trace_in_reject']
    else:
        trace_in_reject = False

    # Associate hook events with the appropriate PBS constant. This is a list
    # of all hook events as of PBS Pro 13.0. If the event does not exist, it is
    # removed from the list.
    hook_events=['queuejob', 'modifyjob', 'movejob', 'runjob', 'execjob_begin',
                 'execjob_prologue', 'execjob_launch', 'execjob_attach', 
                 'execjob_preterm', 'execjob_epilogue', 'execjob_end', 
                 'resvsub', 'provision', 'exechost_periodic', 
                 'exechost_startup', 'execjob_resize', 'execjob_abort',
                 'execjob_postsuspend', 'execjob_preresume']

    hook_event={}
    for he in hook_events:
        # Only set available hooks for the current version of PBS.
        if hasattr(pbs, he.upper()):
            event_code = eval('pbs.' + he.upper())
            hook_event[event_code] = he
            hook_event[he] = event_code
            hook_event[he.upper()] = event_code
            del event_code
        else:
            del hook_events[hook_events.index(he)]

    trace = {
        'line': sys.exc_info()[2].tb_lineno,
        'module': sys.exc_info()[2].tb_frame.f_code.co_name,
        'exception': sys.exc_info()[0].__name__,
        'message': sys.exc_info()[1].message,
    }
    tracemsg = '%s hook %s encountered an exception: Line %s in %s %s: %s' % (
        hook_event[pbs.event().type], pbs.event().hook_name,
        trace['line'], trace['module'], trace['exception'], trace['message']
    )
    rejectmsg = "Hook Error: request rejected as filter hook '%s' encountered " \
        "an exception. Please inform Admin" % pbs.event().hook_name
    if not isinstance(loglevel, int):
        loglevel = pbs.LOG_ERROR
        tracemsg = 'trace_hook() called with invalid argument (loglevel=%s), '\
            'setting to pbs.LOG_ERROR. ' + tracemsg

    pbs.logmsg(pbs.LOG_ERROR, tracemsg)

    if reject:
        tracemsg += ', request rejected'
        if isinstance(trace_in_reject, bool):
            if trace_in_reject:
                pbs.event().reject(tracemsg)
            else:
                pbs.event().reject(rejectmsg)
        else:
            pbs.event().reject(str(trace_in_reject) + 'Line %s in %s %s:\n%s' %
                               (trace['line'], trace['module'], trace['exception'], trace['message']))


class JobLog:
    """ Class for managing output to job stdout and stderr."""

    def __init__(self):
        PBS_SPOOL = os.path.join(pbs_conf()['PBS_MOM_HOME'], 'spool')
        self.stdout_log = os.path.join(PBS_SPOOL,
                                       '%s.OU' % str(pbs.event().job.id))
        self.stderr_log = os.path.join(PBS_SPOOL,
                                       '%s.ER' % str(pbs.event().job.id))

        if str(pbs.event().job.Join_Path) == 'oe':
            self.stderr_log = self.stdout_log
        elif str(pbs.event().job.Join_Path) == 'eo':
            self.stdout_log = self.stderr_log

    def stdout(self, msg):
        """Write msg to appropriate file handle for stdout"""
        import sys

        try:
            if not pbs.event().job.interactive and pbs.event().job.in_ms_mom:
                logfile = open(self.stdout_log, 'ab+')
            else:
                logfile = sys.stdout

            if DEBUG:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           '%s;%s;[DEBUG3]: writing %s to %s' %
                           (pbs.event().hook_name,
                            pbs.event().job.id,
                            repr(msg),
                            logfile.name))

            logfile.write(msg)
            logfile.flush()
            logfile.close()
        except IOError:
            trace_hook()

    def stderr(self, msg):
        """Write msg to appropriate file handle for stdout"""
        import sys

        try:
            if not pbs.event().job.interactive and pbs.event().job.in_ms_mom():
                logfile = open(self.stderr_log, 'ab+')
            else:
                logfile = sys.stderr

            if DEBUG:
                pbs.logmsg(pbs.EVENT_DEBUG3,
                           '%s;%s;[DEBUG3]: writing %s to %s' %
                           (pbs.event().hook_name,
                            pbs.event().job.id,
                            repr(msg),
                            logfile.name))

            logfile.write(msg)
            logfile.flush()
            logfile.close()
        except IOError:
            trace_hook()


# Read in pbs.conf
def pbs_conf(pbs_key=None):
    """Function to return the values from /etc/pbs.conf
    If the PBS python interpreter hasn't been recycled, it is not necessary
    to re-read and re-parse /etc/pbs.conf. This function will simply return
    the variable that exists from the first time this function ran.
    Creates a dict containing the key/value pairs in pbs.conf, accounting for
    comments in lines and empty lines.
    Returns a string representing the pbs.conf setting for pbs_key if set, or
    the dict of all pbs.conf settings if pbs_key is not set.
    """
    import os

    if hasattr(pbs_conf, 'pbs_keys'):
        return pbs_conf.pbs_keys[pbs_key] if pbs_key else pbs_conf.pbs_keys

    if 'PBS_CONF_FILE' in list(os.environ.keys()):
        pbs_conf_file = os.environ['PBS_CONF_FILE']
    elif sys.platform == 'win32':
        if 'ProgramFiles(x86)' in list(os.environ.keys()):
            program_files = os.environ['ProgramFiles(x86)']
        else:
            program_files = os.environ['ProgramFiles']
        pbs_conf_file = '%s\\PBS Pro\\pbs.conf' % program_files
    else:
        pbs_conf_file = '/etc/pbs.conf'

    pbs_conf.pbs_keys = dict([line.split('#')[0].strip().split('=')
                              for line in open(pbs_conf_file)
                              if not line.startswith('#') and '=' in line])

    if 'PBS_MOM_HOME' not in list(pbs_conf.pbs_keys.keys()):
        pbs_conf.pbs_keys['PBS_MOM_HOME'] = \
            pbs_conf.pbs_keys['PBS_HOME']

    return pbs_conf.pbs_keys[pbs_key] if pbs_key else pbs_conf.pbs_keys


# Primary hook execution begins here
try:

    def rejectjob(reason, action=DEFAULT_ACTION):
        """Log job rejection and then call pbs.event().reject()"""

        # Arguments to pbs.event().reject() do nothing in execjob events. Log a
        # warning instead, update the job comment, then reject the job.
        if action == RERUN:
            job.rerun()
            reason = 'Requeued - %s' % reason
        elif action == DELETE:
            job.delete()
            reason = 'Deleted - %s' % reason
        else:
            reason = 'Rejected - %s' % reason

        job.comment = '%s: %s' % (hook_name, reason)
        pbs.logmsg(pbs.LOG_WARNING, ';'.join([hook_name, job.id, reason]))
        pbs.logjobmsg(job.id, reason)  # Add a message that can be tracejob'd
        if VERBOSE_USER_OUTPUT:
            print(reason)
        pbs_event.reject()

    # For the path to mom_priv, we use PBS_MOM_HOME in case that is set,
    # pbs_conf() will return PBS_HOME if it is not.
    mom_priv = os.path.abspath(os.path.join(
        pbs_conf()['PBS_MOM_HOME'], 'mom_priv'))

    # Get the hook alarm time from the .HK file if it exists.
    hk_file = os.path.join(mom_priv, 'hooks', '%s.HK' % hook_name)
    if os.path.exists(hk_file):
        hook_settings = dict([l.strip().split('=') for l in
                              open(hk_file, 'r').readlines()])
        if 'alarm' in list(hook_settings.keys()):
            hook_alarm = int(hook_settings['alarm'])
        if 'debug' in list(hook_settings.keys()):
            DEBUG = True if hook_settings['debug'] == 'true' else False

    if DEBUG:
        pbs.logmsg(pbs.LOG_DEBUG, '%s;%s;[DEBUG] starting.' %
                   (hook_name, job.id))

    if 'PBS_HOOK_CONFIG_FILE' in os.environ:
        config_file = os.environ["PBS_HOOK_CONFIG_FILE"]
        config = dict([l.split('#')[0].strip().split('=')
                       for l in open(config_file, 'r').readlines() if '=' in l])

        # Set the true/false configurations
        if 'ENABLE_PARALLEL' in list(config.keys()):
            ENABLE_PARALLEL = config['ENABLE_PARALLEL'].lower()[0] in [
                't', '1']
        if 'VERBOSE_USER_OUTPUT' in list(config.keys()):
            VEROSE_USER_OUTPUT = config['VERBOSE_USER_OUTPUT'].lower()[0] in [
                't', '1']
        if 'DEFAULT_ACTION' in list(config.keys()):
            if config['DEFAULT_ACTION'].upper() == 'DELETE':
                DEFAULT_ACTION = DELETE
            elif config['DEFAULT_ACTION'].upper() == 'RERUN':
                DEFAULT_ACTION = RERUN
            else:
                pbs.logmsg(
                    pbs.LOG_WARN, '%s;%s;[ERROR] ' %
                    (hook_name, job.id) + 'DEFAULT_ACTION in %s.ini must be one ' %
                    (hook_name) + 'of DELETE or RERUN.')
        if 'TORQUE_COMPAT' in list(config.keys()):
            TORQUE_COMPAT = config['TORQUE_COMPAT'].lower()[0] in ['t', '1']

    # Skip sister mom if parallel pelogs aren't enabled.
    if not ENABLE_PARALLEL and not job.in_ms_mom():
        pbs_event.accept()

    # Prologues and epilogues have different arguments
    if pbs_event.type == pbs.EXECJOB_PROLOGUE:
        event = 'prologue'
        args = [
            job.id,                         # argv[1]
            job.euser,                      # argv[2]
            job.egroup                      # argv[3]
        ]
        if TORQUE_COMPAT:
            args.extend([
                job.Job_Name,               # argv[4]
                job.Resource_List,          # argv[5]
                job.queue.name,             # argv[6]
                job.Account_Name or ''      # argv[7]
            ])
    elif pbs_event.type == pbs.EXECJOB_EPILOGUE:
        null = 'null' if not TORQUE_COMPAT else ''
        event = 'epilogue'
        args = [
            job.id,                         # argv[1]
            job.euser,                      # argv[2]
            job.egroup,                     # argv[3]
            job.Job_Name,                   # argv[4]
            job.session_id,                 # argv[5]
            job.Resource_List,              # argv[6]
            job.resources_used,             # argv[7]
            job.queue.name,                 # argv[8]
            job.Account_Name or null,       # argv[9]
            job.Exit_status                 # argv[10]
        ]
    else:  # hook has wrong events added
        pbs.logmsg(pbs.LOG_WARNING,
                   '%s;%s;[ERROR] PBS event type %s not supported in this hook.' %
                   (hook_name, job.id, pbs_event.type))
        pbs_event.accept()

    # Handle empty arguments
    args = [str(a) if (a or a == 0) else '' for a in args]

    if DEBUG:
        pbs.logmsg(pbs.LOG_DEBUG,
                   '%s;%s;[DEBUG] %s event triggered.' %
                   (hook_name, job.id, event))

    if DEBUG:
        pbs.logmsg(pbs.LOG_DEBUG, '%s;%s;[DEBUG3] args=%s' %
                   (hook_name, job.id, repr(args)))

    # execjob_prologue and execjob_epilogue hooks can run on all nodes, so use
    # pprologue/pepilogue if available and not on primary execution node.
    p = '' if job.in_ms_mom() else 'p'

    if DEBUG:
        pbs.logmsg(pbs.LOG_DEBUG, '%s;%s;[DEBUG] %s.' %
                   (pbs_event.hook_name,
                    job.id,
                    'in sister mom' if p else 'in mother superior'))

    script = os.path.join(mom_priv, p + event)

    if sys.platform == 'win32':
        script = script + '.bat'

    if DEBUG:
        pbs.logmsg(pbs.EVENT_DEBUG3, '%s;%s;[DEBUG3] script set to %s.' % (
            pbs_event.hook_name, job.id, script))

    correct_permissions = False
    if not script:
        pbs_event.accept()

    if not os.path.exists(script):
        pbs_event.accept()

    if sys.platform == 'win32':
        # Windows support is currently not implemented.
        pbs.logmsg(pbs.LOG_WARNING,
                   '%s;%s;[ERROR] ' % (hook_name, job.id) +
                   'Classic prologues and epilogues on Windows are not ' +
                   'currently implemented in this hook.')
        pbs_event.accept()

    else:
        try:
            struct_stat = os.stat(script)
        except OSError:
            rejectjob('Could not stat the %s script (%s).' %
                      (event, script), RERUN)

        # We mask for read and execute on owner make sure no one else can write
        # with 0522 (?r?x?w??w?). With this, permissions such as 0777 masked by
        # 522 will return 522. Acceptable permissions will return 500.
        correct_permissions = bool(struct_stat.st_mode & 0o522 == 0o500 and
                                   struct_stat.st_uid == 0)

    if correct_permissions:
        import signal
        import subprocess
        import shlex

        # Correction for subprocess SIGPIPE handling courtesy of Colin Watson:
        # http://www.chiark.greenend.org.uk/~cjwatson/blog/python-sigpipe.html
        def subprocess_setup():
            """subprocess_setup corrects a known bug where python installs a
            SIGPIPE handler by default. This is usually not what non-Python
            subprocesses expect"""
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

        if DEBUG:
            pbs.logmsg(
                pbs.EVENT_DEBUG2, '%s;%s;[DEBUG2] script %s has appropriate permissions.' %
                (hook_name, job.id, script))

        # change to the correct working directory (PBS_HOME):
        os.chdir(pbs_conf()['PBS_MOM_HOME'])

        # add PBS_JOBDIR environment variable, accounting for empty job.jobdir
        os.environ['PBS_JOBDIR'] = job.jobdir or ''

        shell = ""
        if sys.platform == 'win32':  # win32 is _always_ cmd
            shell = "cmd /c"
        else:
            # check the script for the interpreter line
            shebang = open(script, 'r').readline().strip().split('#!')
            if len(shebang) == 2:
                shell = shebang[1].split()[0]
                if not os.path.exists(shell):
                    rejectjob(
                        'Interpreter specified in %s (%s) does not exist.' %
                        (p + event, shell),
                        RERUN)
            else:
                rejectjob(
                    'No interpreter specified in %s.' %
                    (p + event), RERUN)

        if DEBUG:
            pbs.logmsg(pbs.EVENT_DEBUG2,
                       '%s;%s;[DEBUG2] interpreter set to "%s".' %
                       (hook_name, job.id, shell))

        pbs.logmsg(pbs.LOG_DEBUG, '%s;%s;running %s.' %
                   (hook_name, job.id, p + event))

        # We perform a shlex.split to make sure we capture any #! arguments
        cmd = shlex.split('%s %s' % (shell, script))
        cmd.extend(args)

        if DEBUG:
            pbs.logmsg(
                pbs.EVENT_DEBUG3, '%s;%s;[DEBUG3] cmd=%s' %
                (hook_name, job.id, repr(cmd)))

        if str(job.Join_Path) in ['oe', 'eo']:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=subprocess_setup)
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=subprocess_setup)

        # Wait for the script to gracefully exit.
        while time.time() < start_time + hook_alarm - 5:
            if proc.poll() is not None:
                break
            time.sleep(1)

        # If we reach the alarm time - 5 seconds, send a SIGTERM
        if proc.poll() is None:
            pbs.logmsg(
                pbs.LOG_WARNING, '%s;%s;[WARNING] Terminating %s after %s seconds' %
                (hook_name, job.id, event, int(
                    time.time() - start_time)))
            os.kill(proc.pid, signal.SIGTERM)
            while time.time() < start_time + hook_alarm - 3:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

        # If we reach an alarm time - 3 seconds, send a SIGKILL
        if proc.poll() is None:
            pbs.logmsg(
                pbs.LOG_WARNING, '%s;%s;[WARNING] Killing %s after %s seconds' %
                (hook_name, job.id, event, int(
                    time.time() - start_time)))
            os.kill(proc.pid, signal.SIGKILL)
            while time.time() < start_time + hook_alarm - 1:
                if proc.poll() is not None:
                    break
                time.sleep(0.5)

        # If we still can't kill the script, log a warning and let pbs kill it
        if proc.poll() is None:
            pbs.logmsg(pbs.LOG_WARNING,
                       '%s;%s;[WARNING] Unable to kill %s after %s seconds' %
                       (hook_name, job.id, event, start_time - time.time()))

        # Get the stdout and stderr from the pelog
        (o, e) = proc.communicate()

        if DEBUG:
            pbs.logmsg(
                pbs.EVENT_DEBUG2,
                '%s;%s;[DEBUG2]: stdout=%s, stderr=%s.' %
                (hook_name, job.id, repr(o), repr(e)))

        joblog = JobLog()
        if o:
            joblog.stdout(o)
        if e:
            joblog.stderr(e)

        if proc.returncode:
            return_action = RERUN
            if event == 'prologue':
                return_action = RERUN
                if proc.returncode == 1:
                    return_action = DELETE
            elif event == 'epilogue':
                return_action = DELETE
                if proc.returncode == 2:
                    return_action = RERUN

            rejectjob(
                '%s exited with a status of %s.' % (
                    p + event, proc.returncode),
                return_action)
        else:
            if DEBUG:
                pbs.logmsg(pbs.LOG_DEBUG,
                           '%s;%s;[DEBUG] %s exited with a status of 0.' %
                           (hook_name, job.id, p + event))

            if pbs_event.type == pbs.EXECJOB_PROLOGUE and VERBOSE_USER_OUTPUT:
                print('%s: attached as primary execution host.' %
                      pbs.get_local_nodename())

            pbs_event.accept()
    else:
        rejectjob("The %s does not have the correct " % (p + event) +
                  'permissions. See the section entitled, ' +
                  '"Prologue and Epilogue Requirements" in the PBS Pro ' +
                  "Administrator's Guide.", RERUN)

except SystemExit:
    pass
except BaseException:
    trace_hook()
