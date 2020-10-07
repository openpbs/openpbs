# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of both the OpenPBS software ("OpenPBS")
# and the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# OpenPBS is free software. You can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# OpenPBS is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# PBS Pro is commercially licensed software that shares a common core with
# the OpenPBS software.  For a copy of the commercial license terms and
# conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
# Altair Legal Department.
#
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of OpenPBS and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS™",
# "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
# subject to Altair's trademark licensing policies.


import ast
import copy
import logging
import os
import pwd
import re
import string
import sys
import threading
import time
import traceback
from collections import OrderedDict

from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_procutils import ProcUtils
from ptl.utils.pbs_testusers import (ROOT_USER, TEST_USER, PbsUser,
                                     DAEMON_SERVICE_USER)

from ptl.lib.ptl_object import PBSObject
from ptl.lib.ptl_constants import (ATTR_N, ATTR_j, ATTR_m, ATTR_v, ATTR_k,
                                   ATTR_p, ATTR_r, ATTR_Arglist,
                                   ATTR_executable)


class ResourceResv(PBSObject):

    """
    Generic PBS resource reservation, i.e., job or
    ``advance/standing`` reservation
    """

    def execvnode(self, attr='exec_vnode'):
        """
        PBS type execution vnode
        """
        if attr in self.attributes:
            return PbsTypeExecVnode(self.attributes[attr])
        else:
            return None

    def exechost(self):
        """
        PBS type execution host
        """
        if 'exec_host' in self.attributes:
            return PbsTypeExecHost(self.attributes['exec_host'])
        else:
            return None

    def resvnodes(self):
        """
        nodes assigned to a reservation
        """
        if 'resv_nodes' in self.attributes:
            return self.attributes['resv_nodes']
        else:
            return None

    def select(self):
        if hasattr(self, '_select') and self._select is not None:
            return self._select

        if 'schedselect' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['schedselect'])

        elif 'select' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['select'])
        else:
            return None

        return self._select

    @classmethod
    def get_hosts(cls, exechost=None):
        """
        :returns: The hosts portion of the exec_host
        """
        hosts = []
        exechosts = cls.utils.parse_exechost(exechost)
        if exechosts:
            for h in exechosts:
                eh = list(h.keys())[0]
                if eh not in hosts:
                    hosts.append(eh)
        return hosts

    def get_vnodes(self, execvnode=None):
        """
        :returns: The unique vnode names of an execvnode as a list
        """
        if execvnode is None:
            if 'exec_vnode' in self.attributes:
                execvnode = self.attributes['exec_vnode']
            elif 'resv_nodes' in self.attributes:
                execvnode = self.attributes['resv_nodes']
            else:
                return []

        vnodes = []
        execvnodes = PbsTypeExecVnode(execvnode)
        if execvnodes:
            for n in execvnodes:
                ev = list(n.keys())[0]
                if ev not in vnodes:
                    vnodes.append(ev)
        return vnodes

    def walltime(self, attr='Resource_List.walltime'):
        if attr in self.attributes:
            return self.utils.convert_duration(self.attributes[attr])


class Reservation(ResourceResv):

    """
    PBS Reservation. Attributes and Resources
    :param attrs: Reservation attributes
    :type attrs: Dictionary
    :param hosts: List of hosts for maintenance
    :type hosts: List
    """

    dflt_attributes = {}

    def __init__(self, username=TEST_USER, attrs=None, hosts=None):
        self.server = {}
        self.script = None

        if attrs:
            self.attributes = attrs
        else:
            self.attributes = {}

        if hosts:
            self.hosts = hosts
        else:
            self.hosts = []

        if username is None:
            userinfo = pwd.getpwuid(os.getuid())
            self.username = userinfo[0]
        else:
            self.username = str(username)

        # These are not in dflt_attributes because of the conversion to CLI
        # options is done strictly
        if ATTR_resv_start not in self.attributes and \
           ATTR_job not in self.attributes:
            self.attributes[ATTR_resv_start] = str(int(time.time()) +
                                                   36 * 3600)

        if ATTR_resv_end not in self.attributes and \
           ATTR_job not in self.attributes:
            if ATTR_resv_duration not in self.attributes:
                self.attributes[ATTR_resv_end] = str(int(time.time()) +
                                                     72 * 3600)

        PBSObject.__init__(self, None, self.attributes, self.dflt_attributes)
        self.set_attributes()

    def __del__(self):
        del self.__dict__

    def set_variable_list(self, user, workdir=None):
        pass


class Job(ResourceResv):

    """
    PBS Job. Attributes and Resources

    :param username: Job username
    :type username: str or None
    :param attrs: Job attributes
    :type attrs: Dictionary
    :param jobname: Name of the PBS job
    :type jobname: str or None
    """

    dflt_attributes = {
        ATTR_N: 'STDIN',
        ATTR_j: 'n',
        ATTR_m: 'a',
        ATTR_p: '0',
        ATTR_r: 'y',
        ATTR_k: 'oe',
    }
    runtime = 100
    du = DshUtils()

    def __init__(self, username=TEST_USER, attrs={}, jobname=None):
        self.platform = self.du.get_platform()
        self.server = {}
        self.script = None
        self.script_body = None
        if username is not None:
            self.username = str(username)
        else:
            self.username = None
        self.du = None
        self.interactive_handle = None
        if self.platform == 'cray' or self.platform == 'craysim':
            if 'Resource_List.select' in attrs:
                select = attrs['Resource_List.select']
                attrs['Resource_List.select'] = self.add_cray_vntype(select)
            elif 'Resource_List.vntype' not in attrs:
                attrs['Resource_List.vntype'] = 'cray_compute'

        PBSObject.__init__(self, None, attrs, self.dflt_attributes)

        if jobname is not None:
            self.custom_attrs[ATTR_N] = jobname
            self.attributes[ATTR_N] = jobname
        self.set_variable_list(self.username)
        self.set_sleep_time(100)

    def __del__(self):
        del self.__dict__

    def add_cray_vntype(self, select=None):
        """
        Cray specific function to add vntype as ``cray_compute`` to each
        select chunk

        :param select: PBS select statement
        :type select: str or None
        """
        ra = []
        r = select.split('+')
        for i in r:
            select = PbsTypeSelect(i)
            novntype = 'vntype' not in select.resources
            nohost = 'host' not in select.resources
            novnode = 'vnode' not in select.resources
            if novntype and nohost and novnode:
                i = i + ":vntype=cray_compute"
            ra.append(i)
        select_str = ''
        for l in ra:
            select_str = select_str + "+" + l
        select_str = select_str[1:]
        return select_str

    def set_attributes(self, a={}):
        """
        set attributes and custom attributes on this job.
        custom attributes are used when converting attributes to CLI.
        In case of Cray platform if 'Resource_List.vntype' is set
        already then remove it and add vntype value to each chunk of a
        select statement.

        :param a: Attribute dictionary
        :type a: Dictionary
        """
        if isinstance(a, list):
            a = OrderedDict(a)

        self.attributes = OrderedDict(list(self.dflt_attributes.items()) +
                                      list(self.attributes.items()) +
                                      list(a.items()))

        if self.platform == 'cray' or self.platform == 'craysim':
            s = 'Resource_List.select' in a
            v = 'Resource_List.vntype' in self.custom_attrs
            if s and v:
                del self.custom_attrs['Resource_List.vntype']
                select = a['Resource_List.select']
                a['Resource_List.select'] = self.add_cray_vntype(select)

        self.custom_attrs = OrderedDict(list(self.custom_attrs.items()) +
                                        list(a.items()))

    def set_variable_list(self, user=None, workdir=None):
        """
        Customize the ``Variable_List`` job attribute to ``<user>``
        """
        if user is None:
            userinfo = pwd.getpwuid(os.getuid())
            user = userinfo[0]
            homedir = userinfo[5]
        else:
            try:
                homedir = pwd.getpwnam(user)[5]
            except:
                homedir = ""

        self.username = user

        s = ['PBS_O_HOME=' + homedir]
        s += ['PBS_O_LANG=en_US.UTF-8']
        s += ['PBS_O_LOGNAME=' + user]
        s += ['PBS_O_PATH=/usr/bin:/bin:/usr/bin:/usr/local/bin']
        s += ['PBS_O_MAIL=/var/spool/mail/' + user]
        s += ['PBS_O_SHELL=/bin/bash']
        s += ['PBS_O_SYSTEM=Linux']
        if workdir is not None:
            wd = workdir
        else:
            wd = os.getcwd()
        s += ['PBS_O_WORKDIR=' + str(wd)]

        self.attributes[ATTR_v] = ",".join(s)
        self.set_attributes()

    def set_sleep_time(self, duration):
        """
        Set the sleep duration for this job.

        :param duration: The duration, in seconds, to sleep
        :type duration: int
        """
        self.set_execargs('/bin/sleep', duration)

    def set_execargs(self, executable, arguments=None):
        """
        Set the executable and arguments to use for this job

        :param executable: path to an executable. No checks are made.
        :type executable: str
        :param arguments: arguments to executable.
        :type arguments: str or list or int
        """
        msg = ['job: executable set to ' + str(executable)]
        if arguments is not None:
            msg += [' with arguments: ' + str(arguments)]

        self.logger.info("".join(msg))
        self.attributes[ATTR_executable] = executable
        if arguments is not None:
            args = ''
            xml_beginargs = '<jsdl-hpcpa:Argument>'
            xml_endargs = '</jsdl-hpcpa:Argument>'
            if isinstance(arguments, list):
                for a in arguments:
                    args += xml_beginargs + str(a) + xml_endargs
            elif isinstance(arguments, str):
                args = xml_beginargs + arguments + xml_endargs
            elif isinstance(arguments, int):
                args = xml_beginargs + str(arguments) + xml_endargs
            self.attributes[ATTR_Arglist] = args
        else:
            self.unset_attributes([ATTR_Arglist])
        self.set_attributes()

    def create_script(self, body=None, asuser=None, hostname=None):
        """
        Create a job script from a given body of text into a
        temporary location

        :param body: the body of the script
        :type body: str or None
        :param asuser: Optionally the user to own this script,
                      defaults ot current user
        :type asuser: str or None
        :param hostname: The host on which the job script is to
                         be created
        :type hostname: str or None
        """

        if body is None:
            return None

        if isinstance(body, list):
            body = '\n'.join(body)

        if self.platform == 'cray' or self.platform == 'craysim':
            body = body.split("\n")
            for i, line in enumerate(body):
                if line.startswith("#PBS") and "select=" in line:
                    if 'Resource_List.vntype' in self.attributes:
                        self.unset_attributes(['Resource_List.vntype'])
                    line_arr = line.split(" ")
                    for j, element in enumerate(line_arr):
                        select = element.startswith("select=")
                        lselect = element.startswith("-lselect=")
                        if select or lselect:
                            if lselect:
                                sel_str = element[9:]
                            else:
                                sel_str = element[7:]
                            sel_str = self.add_cray_vntype(select=sel_str)
                            if lselect:
                                line_arr[j] = "-lselect=" + sel_str
                            else:
                                line_arr[j] = "select=" + sel_str
                    body[i] = " ".join(line_arr)
            body = '\n'.join(body)

        # If the user has a userhost, the job will run from there
        # so the script should be made there
        if self.username:
            user = PbsUser.get_user(self.username)
            if user.host:
                hostname = user.host
                asuser = user.name

        self.script_body = body
        if self.du is None:
            self.du = DshUtils()
        # First create the temporary file as current user and only change
        # its mode once the current user has written to it
        fn = self.du.create_temp_file(hostname, prefix='PtlPbsJobScript',
                                      asuser=asuser, body=body)
        self.du.chmod(hostname, fn, mode=0o755)
        self.script = fn
        return fn

    def create_subjob_id(self, job_array_id, subjob_index):
        """
        insert subjob index into the square brackets of job array id

        :param job_array_id: PBS parent array job id
        :type job_array_id: str
        :param subjob_index: index of subjob
        :type subjob_index: int
        :returns: subjob id string
        """
        idx = job_array_id.find('[]')
        return job_array_id[:idx + 1] + str(subjob_index) + \
            job_array_id[idx + 1:]

    def create_eatcpu_job(self, duration=None, hostname=None):
        """
        Create a job that eats cpu indefinitely or for the given
        duration of time

        :param duration: The duration, in seconds, to sleep
        :type duration: int
        :param hostname: hostname on which to execute the job
        :type hostname: str or None
        """
        if self.du is None:
            self.du = DshUtils()
        shebang_line = '#!' + self.du.which(hostname, exe='python3')
        body = """
import signal
import sys

x = 0


def receive_alarm(signum, stack):
    sys.exit()

signal.signal(signal.SIGALRM, receive_alarm)

if (len(sys.argv) > 1):
    input_time = sys.argv[1]
    print('Terminating after %s seconds' % input_time)
    signal.alarm(int(input_time))
else:
    print('Running indefinitely')

while True:
    x += 1
"""
        script_body = shebang_line + body
        script_path = self.du.create_temp_file(hostname=hostname,
                                               body=script_body,
                                               suffix='.py')
        if not self.du.is_localhost(hostname):
            d = pwd.getpwnam(self.username).pw_dir
            ret = self.du.run_copy(hosts=hostname, src=script_path, dest=d)
            if ret is None or ret['rc'] != 0:
                raise AssertionError("Failed to copy file %s to %s"
                                     % (script_path, hostname))
        pbs_conf = self.du.parse_pbs_config(hostname)
        shell_path = os.path.join(pbs_conf['PBS_EXEC'],
                                  'bin', 'pbs_python')
        a = {ATTR_S: shell_path}
        self.set_attributes(a)
        mode = 0o755
        if not self.du.chmod(hostname=hostname, path=script_path, mode=mode,
                             sudo=True):
            raise AssertionError("Failed to set permissions for file %s"
                                 " to %s" % (script_path, oct(mode)))
        self.set_execargs(script_path, duration)


class InteractiveJob(threading.Thread):

    """
    An Interactive Job thread

    Interactive Jobs are submitted as a thread that sets the jobid
    as soon as it is returned by ``qsub -I``, such that the caller
    can get back to monitoring the state of PBS while the interactive
    session goes on in the thread.

    The commands to be run within an interactive session are
    specified in the job's interactive_script attribute as a list of
    tuples, where the first item in each tuple is the command to run,
    and the subsequent items are the expected returned data.

    Implementation details:

    Support for interactive jobs is currently done through the
    pexpect module which must be installed separately from PTL.
    Interactive jobs are submitted through ``CLI`` only, there is no
    API support for this operation yet.

    The submission of an interactive job requires passing in job
    attributes,the command to execute ``(i.e. path to qsub -I)``
    and the hostname

    when not impersonating:

    pexpect spawns the ``qsub -I`` command and expects a prompt
    back, for each tuple in the interactive_script, it sends the
    command and expects to match the return value.

    when impersonating:

    pexpect spawns ``sudo -u <user> qsub -I``. The rest is as
    described in non- impersonating mode.
    """

    logger = logging.getLogger(__name__)

    pexpect_timeout = 15
    pexpect_sleep_time = .1
    du = DshUtils()

    def __init__(self, job, cmd, host):
        threading.Thread.__init__(self)
        self.job = job
        self.cmd = cmd
        self.jobid = None
        self.hostname = host
        self._ru = ""
        if self.du.get_platform() == "shasta":
            self._ru = PbsUser.get_user(job.username)
            if self._ru.host:
                self.hostname = self._ru.host

    def __del__(self):
        del self.__dict__

    def run(self):
        """
        Run the interactive job
        """
        try:
            import pexpect
        except:
            self.logger.error('pexpect module is required for '
                              'interactive jobs')
            return None

        job = self.job
        cmd = self.cmd

        self.jobid = None
        self.logger.info("submit interactive job as " + job.username +
                         ": " + " ".join(cmd))
        if not hasattr(job, 'interactive_script'):
            self.logger.debug('no interactive_script attribute on job')
            return None

        try:
            # sleep to allow server to communicate with client
            # this value is set empirically so tweaking may be
            # needed
            _st = self.pexpect_sleep_time
            _to = self.pexpect_timeout
            _sc = job.interactive_script
            current_user = pwd.getpwuid(os.getuid())[0]
            if current_user != job.username:
                if hasattr(job, 'preserve_env') and job.preserve_env is True:
                    cmd = (copy.copy(self.du.sudo_cmd) +
                           ['-E', '-u', job.username] + cmd)
                else:
                    cmd = (copy.copy(self.du.sudo_cmd) +
                           ['-u', job.username] + cmd)

            self.logger.debug(cmd)
            is_local = self.du.is_localhost(self.hostname)
            _p = ""
            if is_local:
                _p = pexpect.spawn(" ".join(cmd), timeout=_to)
            else:
                self.logger.info("Submit interactive job from a remote host")
                if self.du.get_platform() == "shasta":
                    ssh_cmd = self.du.rsh_cmd + \
                        ['-p', self._ru.port,
                         self._ru.name + '@' + self.hostname]
                    _p = pexpect.spawn(" ".join(ssh_cmd), timeout=_to)
                    _p.sendline(" ".join(self.cmd))
                else:
                    ssh_cmd = self.du.rsh_cmd + [self.hostname]
                    _p = pexpect.spawn(" ".join(ssh_cmd), timeout=_to)
                    _p.sendline(" ".join(cmd))
            self.job.interactive_handle = _p
            time.sleep(_st)
            expstr = "qsub: waiting for job "
            expstr += r"(?P<jobid>\d+.[0-9A-Za-z-.]+) to start"
            _p.expect(expstr)
            if _p.match:
                self.jobid = _p.match.group('jobid').decode()
            else:
                _p.close()
                self.job.interactive_handle = None
                return None
            self.logger.debug(_p.after.decode())
            for _l in _sc:
                (cmd, out) = _l
                self.logger.info('sending: ' + cmd)
                _p.sendline(cmd)
                self.logger.info('expecting: ' + out)
                _p.expect(out)
            self.logger.info('sending exit')
            _p.sendline("exit")
            while True:
                try:
                    _p.read_nonblocking(timeout=5)
                except Exception:
                    break
            if _p.isalive():
                _p.close()
            self.job.interactive_handle = None
        except Exception:
            self.logger.error(traceback.print_exc())
            return None
        return self.jobid
