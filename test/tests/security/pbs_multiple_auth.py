# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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

from tests.security import *
import os
import errno
import socket
import re
import random
import string
import sys
import time

class TestMultipleAuthMethods(TestSecurity):
    """
    This test suite contains tests for Multiple authentication added to PBS
    """
    node_list = []
    # Regular expression that will be used to get the address and port number
    # from the output of 'netstat' or 'ss' commands
    re_addr_port = re.compile(r'(?P<addr>.*):(?P<port>\d+)')
    # Regular expression that will be used to get the second argument of write
    # system calls from the output of 'strace' command
    re_syscall = re.compile(r'.*\"(?P<write_buffer>.*)\".*')

    def setUp(self):
        TestSecurity.setUp(self)
        attrib = {'log_events': 2047}
        self.server.manager(MGR_CMD_SET, SERVER, attrib)
        self.mom.add_config({'$logevent': '4095'})
        self.server.manager(MGR_CMD_SET, SCHED, {'log_events': 4095})
        self.cur_user = self.du.get_current_user()
        self.svr_hostname = self.server.shortname
        self.node_list.append(self.svr_hostname)
        self.client_host = None

    def update_pbs_conf(self, conf_param, host_name=None,
                        restart=True, op='set', check_state=True):
        """
        This function updates pbs conf file.

        :param conf_param: PBS confs 'key/value' need to update in pbs.conf
        :type conf_param: Dictionary
        :param host_name: Name of the host on which pbs.conf
                          has to be updated
        :param restart: Restart PBS or not after update pbs.conf
        :type restart: Boolean
        :param op: Operation need to perform on pbs.conf
                   Set or Unset operation will perform.
        :type set: String
        :param check_state: Check node state to be free
        :type check_state: Bool
        """

        check_sched_log = False
        if host_name == None:
            host_name = self.svr_hostname
        pbsconfpath = self.du.get_pbs_conf_file(host_name)
        if op == 'set':
            check_sched_log = True
            self.du.set_pbs_config(hostname=host_name,
                                   fin=pbsconfpath,
                                   confs=conf_param)
        else:
            self.du.unset_pbs_config(hostname=host_name,
                                     fin=pbsconfpath,
                                     confs=conf_param)
        if restart:
            self.pbs_restart(host_name, node_state=check_state,
                             sched_log=check_sched_log)
            # Wait for Server to be ready after restart
            time.sleep(5)

    def munge_operation(self, host_name, op=None):
        """
        This function starts the munge dameon on a given host

        :param host_name: Name of the host on which munge
                          service has to be start.
        :type host_name: String
        :param op: Operation perform on munge daemon.
        :type op: String
        """
        cmd = 'service munge %s' % (op)
        status = self.du.run_cmd(hosts=host_name, cmd=cmd, sudo=True)
        if op == 'status':
            if status['rc'] == 0:
                return True
            else:
                return False
        else:
            msg = "Failed to %s Munge on %s, Error: %s" % (op, host_name,
                                                           str(status['err']))
            self.assertEquals(status['rc'], 0, msg)

    def pbs_restart(self, host_name=None, node_state=True, daemon=None,
                    sched_log=True):
        """
        This function restarts PBS on host.
        :param host_name: Name of the host on which pbs daemons
                          has to be restarted
        :type host_name: String
        :param node_state: Check node state to be free
        :type node_state: Bool
        """
        if host_name == None:
            host_name = self.mom.shortname
        if daemon == "pbs_comm":
            self.comm.restart
            pi = PBSInitServices(hostname=self.server.shortname)
            pi.restart_comm()
        else:
            start_time = time.time()
            pi = PBSInitServices(hostname=host_name)
            pi.restart()
        if node_state:
            self.server.expect(NODE, {'state': 'free'}, id=host_name)

    def perform_op(self, choice, host_name, node_state=True):
        """
        This function check if munge is installed or not installed
        based on test case. If installed then check if munge daemon
        is active or not,if not active then start it.

        param choice: which operation want to perform on host.
        type choice: String
        param host_name: Hostname on which operation want to perform.
        type host_name: String or None
        :param node_state: Check node state to be free
        :type node_state: Bool
        """
        munge_cmd = self.du.which(exe="munge", hostname=host_name)
        if choice == 'check_installed_and_run':
            if munge_cmd == 'munge':
                self.skipTest(reason='Munge is not installed')
            else:
                _msg = "Munge is installed as per test suite requirement,"
                _msg += " proceeding to check if munge is active"
                self.logger.info(_msg)
                if not self.munge_operation(host_name, op='status'):
                    _msg = "Munge daemon is not running, trying to start it..."
                    self.logger.info(_msg)
                    self.munge_operation(host_name=host_name,
                                         op='start')
                    self.logger.info(
                        "Munge started successfully, proceeding further")
                    self.pbs_restart(
                        host_name=host_name, node_state=node_state)
                else:
                    _msg = "Munge is running as per test suite requirement, "
                    _msg += "proceeding with test case execution"
                    self.logger.info(_msg)
        else:
            if munge_cmd != 'munge':
                _msg = 'Munge is installed which is not a pre-requiste'
                _msg += ' for test cases, skipping test case'
                self.skipTest(reason=_msg)
            else:
                _msg = "Munge is not installed as per test suite requirement,"
                _msg += " proceeding with test case execution"
                self.logger.info(_msg)

    def match_logs(self, exp_msg, nt_exp_msg=None):
        """
        This function verifies the expected log msgs with respect
                to authentication in daemon logs

        param exp_msg: Expected log messages in daemons log file.
        type exp_msg: Dictionary
        param nt_exp_msg: Not expected message in daemons log file.
        type exp_msg: String
        """

        st_time = self.server.ctime
        if 'mom' in exp_msg:
            self.mom.log_match(exp_msg['mom'], starttime=st_time)
        for msg in exp_msg.get('server', []):
            self.server.log_match(msg, starttime=st_time)
        for msg in exp_msg.get('comm', []):
            self.comm.log_match(msg, starttime=st_time)

        if nt_exp_msg:
            self.mom.log_match(nt_exp_msg, starttime=st_time,
                               existence=False)
            self.server.log_match(nt_exp_msg, starttime=st_time,
                                  existence=False)
            self.comm.log_match(nt_exp_msg, starttime=st_time,
                                existence=False)

    def common_commands_steps(self, set_attr=None, job_script=False,
                              resv_attr=None, client=None):
        """
        This function check all pbs commands are authenticated via
        respective auth method.

        :param set_attr: Job attributes to set
        :type set_attr: Dictionary. Defaults to None
        :param job_script: Whether to submit a job using job script
        :type job_script: Bool. Defaults to False
        :param resv_set_attr: Reservation attributes to set
        :type resv_set_attr: Dictionary. Defaults to None
        :param client: Name of the client
        :type client: String. Defaults to None
        """
        if client is None:
            self.server.client = self.svr_hostname
        else:
            self.server.client = client
        # Verify that PBS commands are authenticated
        exp_msg = "Type 95 request received"
        start_time = time.time()
        self.server.status(SERVER)
        self.server.log_match(exp_msg, starttime=start_time)

        if resv_attr is None:
            resv_attr = {'reserve_start': time.time() + 30,
                         'reserve_end': time.time() + 60}

        r = Reservation(TEST_USER, resv_attr)
        rid = self.server.submit(r)
        exp_state = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED")}
        self.server.expect(RESV, exp_state, id=rid)

        start_time = time.time()
        self.server.delete(rid)
        self.server.log_match(exp_msg, starttime=start_time)

        start_time = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.log_match(exp_msg, starttime=start_time)

        start_time = time.time()
        j = Job(TEST_USER)
        if set_attr is not None:
            j.set_attributes(set_attr)
        if job_script:
            pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                       "bin", "pbsdsh")
            script = "#!/bin/sh\n%s sleep 30" % pbsdsh_path
            j.create_script(script, hostname=self.server.client)
        else:
            j.set_sleep_time(30)
        jid = self.server.submit(j)

        self.server.log_match(exp_msg, starttime=start_time)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        start_time = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.log_match(exp_msg, starttime=start_time)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        start_time = time.time()
        self.server.alterjob(jid, {ATTR_N: 'test'})
        self.server.log_match(exp_msg, starttime=start_time)

        start_time = time.time()
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=30)
        self.server.log_match("%s;Exit_status=0" % jid)

    def common_setup(self, req_moms=2, req_comms=1):
        """
        This function sets the shortnames of server, moms, comms and
        Client in the cluster
        Server shortname : self.hostA
        Mom objects : self.momB, self.momC
        Mom shortnames : self.hostB, self.hostC
        Comm objects : self.comm2, self.comm3
        Comm shortnames : self.hostD, self.hostE
        Client name : self.hostF
        :param req_moms: No of required moms
        :type req_moms: Integer. Defaults to 2
        :param req_comms: No of required comms
        :type req_comms: Integer. Defaults to 1
        """
        num_moms = len(self.moms)
        num_comms = len(self.comms)
        if (req_moms != num_moms) and (req_comms != num_comms):
            msg = "Test requires exact %s moms and %s" % (req_moms, req_comms)
            msg += " comms as input"
            self.skipTest(msg)
        if num_moms == 2 and num_comms == 2:
            self.hostA = self.server.shortname
            self.momB = self.moms.values()[0]
            self.hostB = self.momB.shortname
            self.momC = self.moms.values()[1]
            self.hostC = self.momC.shortname
            self.comm2 = self.comms.values()[0]
            self.hostD = self.comm2.shortname
            self.comm3 = self.comms.values()[1]
            self.hostE = self.comm3.shortname
            self.hostF = self.client_host = self.server.client
            self.node_list = [self.hostA, self.hostB,
                              self.hostC, self.hostD,
                              self.hostE, self.hostF]
        elif num_moms == 2 and num_comms == 3:
            self.hostA = self.server.shortname
            self.momB = self.moms.values()[0]
            self.hostB = self.momB.shortname
            self.momC = self.moms.values()[1]
            self.hostC = self.momC.shortname
            self.comm2 = self.comms.values()[1]
            self.hostD = self.comm2.shortname
            self.comm3 = self.comms.values()[2]
            self.hostE = self.comm3.shortname
            self.hostF = self.client_host = self.server.client
            self.node_list = [self.hostA, self.hostB,
                              self.hostC, self.hostD,
                              self.hostE, self.hostF]

    def simple_interactive_job(self):
        self.svr_mode = self.server.get_op_mode()
        if self.svr_mode != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('hostname', '.*'),
                                ('sleep 100', '.*')]
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(jid)

    def test_default_auth_method(self):
        """
        Test to verify all PBS daemons and commands are authenticated
        via default authentication method
        default authentication method is resvport
        """
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047"}
        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True
        self.update_pbs_conf(conf_param, check_state=check_state)
        common_msg = 'TPP authentication method = resvport'
        common_msg1 = 'Supported authentication method: resvport'
        exp_msg = {'server': [common_msg, common_msg1],
                   'comm': [common_msg1],
                   'mom': common_msg}
        self.match_logs(exp_msg)
        self.common_commands_steps()

    def test_munge_auth_method(self):
        """
        Test to verify all PBS daemons and commands are authenticated
        via munge authentication method
        """
        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            check_state = False
        else:
            check_state = True

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=check_state)

        if self.server.shortname != self.mom.shortname:
            conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname)

        common_msg = 'TPP authentication method = munge'
        common_msg1 = 'Supported authentication method: munge'

        exp_msg = {'server': [common_msg, common_msg1],
                   'comm': [common_msg1],
                   'mom': common_msg}

        nt_exp_msg = 'TPP authentication method = resvport'
        self.match_logs(exp_msg, nt_exp_msg)
        self.common_commands_steps()

    def test_multiple_supported_auth_methods(self):
        """
        Test to verify all PBS daemons and commands are authenticated
        via multiple authentication method.
        we authenticated with resvport and munge.
        """
        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            check_state = False
        else:
            check_state = True

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=check_state)

        if self.server.shortname != self.mom.shortname:
            conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname)

        common_msg = 'TPP authentication method = munge'
        common_msg1 = 'Supported authentication method: munge'
        common_msg2 = 'Supported authentication method: resvport'

        exp_msg = {'server': [common_msg, common_msg1, common_msg2],
                   'comm': [common_msg, common_msg1, common_msg2],
                   'mom': common_msg}
        nt_exp_msg = 'TPP authentication method = resvport'
        self.match_logs(exp_msg, nt_exp_msg)
        self.common_commands_steps()

        confs = ['PBS_AUTH_METHOD']
        self.update_pbs_conf(confs, op='unset', restart=False)

        common_msg = 'TPP authentication method = resvport'
        conf_param = {'PBS_AUTH_METHOD': 'resvport'}
        for host_name in self.node_list:
            if host_name == self.svr_hostname:
                check_state = False
            else:
                check_state = True
            self.update_pbs_conf(conf_param, host_name=host_name,
                                 check_state=check_state)

        exp_msg['server'][0] = exp_msg['comm'][0] = common_msg
        exp_msg['mom'] = common_msg
        self.match_logs(exp_msg)
        self.common_commands_steps()

    def test_multiple_auth_method(self):
        """
        Test to verify getting expected error message
        with multiple PBS_AUTH_METHOD.
        """
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'resvport,MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, restart=False)

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            conf_param = {'PBS_AUTH_METHOD': 'resvport,MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname,
                                 restart=False)

        lib_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                'lib')
        msg = "/libauth_resvport,munge.so: cannot open shared object file:"
        msg += " No such file or directory"
        matchs = lib_path + msg

        # Restart PBS and it should fail with expected error message
        try:
            self.pbs_restart(self.server.shortname)
        except PbsInitServicesError as e:
            self.assertIn(matchs, e.msg)
            _msg = "PBS start up failed with logger info: " + str(e.msg)
            self.logger.info(_msg)
        else:
            err_msg = "Failed to get expected error message in PBS restart: "
            err_msg += msg
            self.fail(err_msg)

    def test_not_listed_auth_method(self):
        """
        test to verify that pbs give appropiate error message
        if we use not listed PBS_AUTH_METHOD.
        """
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'resvport',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, restart=False)

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname,
                                 restart=False)

        err_msg = ['auth: error returned: 15029',
                   'auth: Failed to send auth request',
                   'No support for requested service.',
                   f'qstat: cannot connect to server {self.server.shortname} (errno=15029)']

        try:
            self.server.status(SERVER)
        except PbsStatusError as e:
            for msg in err_msg:
                self.assertIn(msg, e.msg)
        else:
            err_msg = "Failed to get expected error message"
            err_msg += " while checking server status."
            self.fail(err_msg)

    def test_null_authentication_value(self):
        """
        Set PBS_AUTH_METHOD to NULL (empty).
        Check for error message
        """

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'resvport',
                      'PBS_AUTH_METHOD': '',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, restart=False)

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            conf_param = {'PBS_AUTH_METHOD': ''}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname,
                                 restart=False)

        comm_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                 'sbin', 'pbs_comm')
        matchs = comm_path + ": Configuration error"

        # Restart PBS and it should fail with expected error message
        _msg = "PBS start up failed with logger info: "
        try:
            self.pbs_restart(self.server.shortname)
        except PbsInitServicesError as e:
            self.assertIn(matchs, e.msg)
            self.logger.info(_msg + str(e.msg))
        else:
            err_msg = "Failed to get expected error message in PBS restart: "
            err_msg += matchs
            self.fail(err_msg)

        if self.mom.shortname != self.svr_hostname:
            try:
                self.pbs_restart()
            except PbsInitServicesError as e:
                matchs = "pbs_mom startup failed, exit 1 aborting"
                self.assertIn(matchs, e.msg)
                self.logger.info(_msg + str(e.msg))
            else:
                err_msg = "Failed to get expected error message in PBS restart: "
                err_msg += matchs
                self.fail(err_msg)

    def test_munge_not_running_state(self):
        """
        Submit a job when munge process is not running on server host.
        Job submit error should occur because of
        Munge encode failure
        """
        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            check_state = False
        else:
            check_state = True

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=check_state)

        if self.server.shortname != self.mom.shortname:
            conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname)

        common_msg = 'MUNGE user-authentication on encode failed with '
        err_msg1 = common_msg + '`Munged communication error`'
        err_msg2 = common_msg + '`Socket communication error`'

        # To stop munge process and check if successfull
        self.munge_operation(host_name=self.svr_hostname, op='stop')

        msg = f"qsub: cannot connect to server {self.server.hostname}"
        msg += " (errno=15010)"
        exp_msg = ['munge_get_auth_data: ' + err_msg1,
                    'auth: error returned: 15010',
                    'auth: ' + err_msg1,
                    msg
                    ]

        exp_msg1 = copy.copy(exp_msg)

        exp_msg1[0] = 'munge_get_auth_data: ' + err_msg2
        exp_msg1[2] = 'auth: ' + err_msg2

        # Submit a job and it should fail resulting in expected error
        j = Job(self.cur_user)
        _msg = "Trying to start munge daemon"
        try:
            j1id = self.server.submit(j)
        except PbsSubmitError as e:
            # Check if all lines of exp_msg are present in the error message
            all_in_exp_msg = all(any(s in msg for msg in e.msg)
                                 for s in exp_msg)
            # Check if all lines of exp_msg1 are present in the error message
            all_in_exp_msg1 = all(any(s in msg for msg in e.msg)
                                  for s in exp_msg1)
            self.assertTrue(all_in_exp_msg or all_in_exp_msg1,
                            f"{str(e.msg)} does not match with {str(exp_msg)} or {str(exp_msg1)}")
            self.logger.info("Job submit failed as expected with" + str(e.msg))
        else:
            err_msg = "Failed to get expected error message"
            err_msg += " while submiting job."
            self.fail(err_msg)
        # Clean Up: To start munge that was stopped in first step
        finally:
            self.logger.info(_msg)
            self.munge_operation(host_name=self.svr_hostname, op='start')
            self.logger.info("Munge started as a part of cleanup")

    def test_invalid_authentication_value(self):
        """
        Set PBS_AUTH_METHOD to invalid value.
        Check for error message on restart of daemons
        """
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'resvport',
                      'PBS_AUTH_METHOD': 'testing',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, restart=False)

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            conf_param = {'PBS_AUTH_METHOD': 'testing'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname,
                                 restart=False)

        matchs = "/opt/pbs/lib/libauth_testing.so:"
        matchs += " cannot open shared object file: No such file or directory"

        # Restart PBS and it should fail with expected error message
        _msg = "PBS restart failed as expected, error message: "
        try:
            self.pbs_restart()
        except PbsInitServicesError as e:
            self.assertIn(matchs, e.msg)
            self.logger.info(_msg + str(e.msg))
        else:
            err_msg = "Failed to get expected error message in PBS restart: "
            err_msg += matchs
            self.fail(err_msg)

    @requirements(num_moms=2)
    def test_munge_disabled_on_mom_host(self):
        """
        Test behavior when munge is stopped on Mom host
        Configuration:
        Node 1 : Server, Sched, Comm, Mom (self.hostA)
        Node 2 : Mom (self.hostB)
        """
        if len(self.moms) != 2:
            msg = "Test requires exactly 2 mom host as input"
            msg += " host as input"
            self.skipTest(msg)

        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname
        self.node_list.extend([self.hostA, self.hostB])
        for host in self.node_list:
            self.perform_op('check_installed_and_run', host, node_state=False)

        # Update pbs.conf of Server host
        conf_param = {'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'munge'}
        self.update_pbs_conf(
            conf_param,
            host_name=self.svr_hostname, check_state=False)

        # Update pbs.conf of Mom hosts
        del conf_param['PBS_COMM_LOG_EVENTS']
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        for mom in self.moms.values():
            if mom.name != self.server.hostname:
                self.update_pbs_conf(
                  conf_param,
                  host_name=mom.name)

        self.munge_operation(self.hostB, op="stop")
        self.pbs_restart(self.hostB, node_state=False)
        self.server.expect(NODE, {'state': 'down'}, id=self.hostB)
        set_attr = {ATTR_l + '.select': '2:ncpus=1',
                    ATTR_l + '.place': 'scatter'}
        j = Job(attrs=set_attr)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

    @requirements(no_mom_on_server=True, num_client=1)
    def test_munge_without_supported_auth_method_on_server(self):
        """
        Verify appropriate error msg is thrown when
        PBS_SUPPORTED_AUTH_METHODS is not added to pbs.conf on server host
        Configuration:
        Node 1 : Server, Sched, Comm (self.hostA)
        Node 2 : Mom, Client (self.hostB)
        """
        if self.server.client == self.server.hostname:
            msg = "Test requires 1 mom and 1 client which is on non server"
            msg += " host as input"
            self.skipTest(msg)

        self.hostA = self.server.shortname
        self.momA = self.moms.values()[0]
        self.hostB = self.momA.shortname

        self.node_list = [self.hostA, self.hostB]

        # Verify if munge is installed on all the hosts
        for host in self.node_list:
            self.perform_op('check_installed_and_run', host)

        conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
        for host in self.node_list:
            self.update_pbs_conf(conf_param, host_name=host, check_state=False)

        err_msg = ['auth: error returned: 15029',
                   'auth: Failed to send auth request',
                   'No support for requested service.',
                   f'qstat: cannot connect to server {self.server.shortname} (errno=15029)']

        try:
            self.server.status(SERVER)
        except PbsStatusError as e:
            for msg in err_msg:
                self.assertIn(msg, e.msg)
        else:
            err_msg = "Failed to get expected error message"
            err_msg += " while checking server status."
            self.fail(err_msg)

    def common_steps_without_munge(self, client=None):
        """
        This function contains common steps for tests which
        verify behavior when munge is not installed on one of the host
        :param client: Name of the client
        :type client: String. Defaults to None
        """
        if client is None:
            self.server.client = self.svr_hostname
        else:
            self.server.client = client

        cmd_path = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin')

        err_msg = ": cannot connect to server %s" % self.server.hostname
        err_msg += ", error=15010"

        pbsnodes_cmd = os.path.join(cmd_path, 'pbsnodes')
        msg = pbsnodes_cmd + err_msg
        exp_msgs = ['init_munge: libmunge.so not found',
                    'auth: error returned: 15010',
                    'auth: Munge lib is not loaded',
                    msg
                    ]
        try:
            self.server.status(NODE, id=self.server.client)
        except PbsStatusError as e:
            for msg in exp_msgs:
                self.assertIn(msg, e.msg)
            cmd_exp_msg = "Getting expected error message."
            self.logger.info(cmd_exp_msg)
        else:
            cmd_msg = "Failed to get expected error message "
            cmd_msg = "while checking Node status."
            self.fail(cmd_msg)

        err_msg = "qstat: cannot connect to server %s" % self.server.hostname
        err_msg += " (errno=15010)"
        exp_msgs[3] = err_msg
        try:
            self.server.status(SERVER, id=self.svr_hostname)
        except PbsStatusError as e:
            for msg in exp_msgs:
                self.assertIn(msg, e.msg)
            cmd_exp_msg = "Getting expected error message."
            self.logger.info(cmd_exp_msg)
        else:
            cmd_msg = "Failed to get expected error message "
            cmd_msg += "while checking Server status."
            self.fail(cmd_msg)

    def test_without_munge_on_server_host(self):
        """
        Munge is not installed on server host.
        Set PBS_AUTH_METHOD=munge in conf and check respective error message.
        """
        # Function call to check if munge is not installed and then proceeding
        # with test case execution
        self.perform_op(choice='check_not_installed',
                        host_name=self.svr_hostname)

        conf_attrib = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                       'PBS_AUTH_METHOD': 'MUNGE',
                       'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_attrib, check_state=False)

        if self.svr_hostname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            conf_param = {'PBS_AUTH_METHOD': 'munge'}
            self.update_pbs_conf(
                conf_param,
                host_name=self.mom.shortname,
                check_state=False)
        exp_log = "libmunge.so not found"
        self.server.log_match(exp_log)
        self.mom.log_match(exp_log)
        self.common_steps_without_munge(self.svr_hostname)

    @requirements(num_moms=2)
    def test_without_munge_on_mom_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on remote
        mom host where munge is not installed.
        Node 1: Server, Sched, Mom, Comm [self.hostA]
        Node 2: Mom [self.hostB]
        """
        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostB)
        self.node_list.extend([self.hostA, self.hostB])

        conf_attrib = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                       'PBS_AUTH_METHOD': 'MUNGE',
                       'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_attrib, check_state=False)

        conf_param = {'PBS_AUTH_METHOD': 'munge'}
        for mom in self.moms.values():
            if mom.shortname != self.svr_hostname:
                self.update_pbs_conf(
                    conf_param, host_name=mom.name, check_state=False)

        exp_log = "libmunge.so not found"
        self.momB.log_match(exp_log)
        self.common_steps_without_munge(self.hostB)

    @requirements(num_moms=1, num_comms=1, no_comm_on_server=True)
    def test_without_munge_on_comm_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on
        comm host where munge is not installed.
        when pbs_comm and client are on non-server host
        Configuration:
        Node 1: Server, Sched, Mom [self.hostA]
        Node 2: Comm [self.hostB]
        """
        if self.svr_hostname == self.comm.shortname:
            msg = "Test requires a comm host which is present on "
            msg += "non server host"
            self.skip_test(msg)

        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.hostB = self.comm.shortname

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostB)
        self.node_list.extend([self.hostA, self.hostB])

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_LEAF_ROUTERS': self.hostB}
        self.update_pbs_conf(conf_param, check_state=False)

        del conf_param['PBS_LEAF_ROUTERS']
        conf_param['PBS_COMM_LOG_EVENTS'] = 2047
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        conf_param['PBS_LEAF_ROUTERS'] = self.hostB
        for mom in self.moms.values():
            if mom.shortname != self.svr_hostname:
                self.update_pbs_conf(
                    conf_param, host_name=mom.name, check_state=False)

        self.common_steps_without_munge(self.hostB)

    @requirements(num_client=1, num_moms=1)
    def test_without_munge_on_client_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on
        comm host where munge is not installed.
        when pbs_comm and client are on non-server host
        Configuration:
        Node 1: Server, Sched, Mom, Comm [self.hostA]
        Node 2: Client [self.hostB]
        """
        if self.svr_hostname == self.server.client:
            msg = "Test requires a client host which is present on "
            msg += "non server host"
            self.skip_test(msg)

        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.hostB = self.server.client

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostB)
        self.node_list.extend([self.hostA, self.hostB])

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=False)
        del conf_param['PBS_COMM_LOG_EVENTS']
        self.update_pbs_conf(conf_param, host_name=self.hostB,
                             restart=False)
        conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
        for mom in self.moms.values():
            if mom.shortname != self.svr_hostname:
                self.update_pbs_conf(
                    conf_param, host_name=mom.name, check_state=False)

        self.common_steps_without_munge(self.hostB)

    @requirements(num_client=1)
    def test_diff_auth_method_on_client(self):
        """
        Verify all PBS daemons and commands are authenticated when
        different authentication method is on client
        Configuration:
        Node 1 : Server, Sched, Comm, Mom (self.hostA)
        Node 2 : Client (self.hostB)
        """
        if self.svr_hostname == self.server.client:
            msg = "Test requires a client host which is present on "
            msg += "non server host"
            self.skip_test(msg)

        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True

        self.hostB = self.server.client
        self.server.client = self.svr_hostname
        # Update pbs.conf on server host (self.hostA)
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=check_state)

        self.server.client = self.hostB

        msg = "auth: Unable to authenticate connection"
        msg += " (%s:15001)" % self.server.hostname
        err_msg = ['auth: error returned: -1',
                   msg,
                   'qstat: cannot connect to server %s (errno=-1)'
                   % (self.server.shortname)]
        try:
            self.server.status(SERVER)
        except PbsStatusError as e:
            for msg in err_msg:
                self.assertIn(msg, e.msg)
        else:
            err_msg = "Failed to get expected error message"
            err_msg += " while checking server status."
            self.fail(err_msg)

    @requirements(num_moms=2)
    def test_diff_auth_methods_on_moms(self):
        """
        Verify all PBS daemons and commands are authenticated when
        different authentication method are used on execution host.
        This also tests the behavior when authentication mechanism
        is different on server and execution host.
        """
        comm_list = [x.shortname for x in self.comms.values()]
        if not(len(self.moms) == 2) or self.server.shortname not in comm_list:
            msg = "Test needs 2 moms as input and a comm which is present"
            msg += " on server host"
            self.skip_test(msg)

        self.momA = self.moms.values()[0]
        self.hostA = self.momA.shortname
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname

        self.node_list.extend([self.hostA, self.hostB])
        self.perform_op('check_installed_and_run', self.hostA,
                        node_state=False)

        # Update pbs.conf of Server
        conf_param = {'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'MUNGE'
                      }
        self.update_pbs_conf(
            conf_param,
            check_state=False)

        server_ip = socket.gethostbyname(self.svr_hostname)
        mom2_ip = socket.gethostbyname(self.hostB)

        if self.hostA != self.svr_hostname:
            conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
            self.update_pbs_conf(conf_param, host_name=self.hostA)
            mom1_ip = socket.gethostbyname(self.hostA)
            self.momA = self.moms.values()[0]
            attrib = {self.server.hostname: [server_ip, 15001],
                      self.momB.hostname: [mom2_ip, 15003],
                      self.momA.hostname: [mom1_ip, 15003]}
        else:
            self.pbs_restart(host_name=self.svr_hostname)
            attrib = {self.server.hostname: [server_ip, 15001, 15003],
                      self.momB.hostname: [mom2_ip, 15003]}

        msg = "Unauthenticated connection from %s" % self.server.shortname
        self.comm.log_match(msg, existence=False, starttime=self.server.ctime)
        ip = []
        port = []
        for host, host_attribs in attrib.items():
            ip = host_attribs.pop(0)
            for port in host_attribs:
                exp_msg = "Leaf registered address %s:%s" % (ip, port)
                self.comm.log_match(exp_msg)

        # Submit a job on the execution hosts with different
        # authentication mechanism
        set_attr = {ATTR_l + '.select': '2:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_attr = {ATTR_l + '.select': '2:ncpus=1',
                     'reserve_start': time.time() + 30,
                     'reserve_end': time.time() + 60}
        self.common_commands_steps(resv_attr=resv_attr,
                                   set_attr=set_attr)

    def test_daemon_not_in_service_users_with_munge(self):
        """
        Test behavior when the daemon user is not in the PBS_AUTH_SERVICE_USERS
        list when using munge for authentication. No daemon should be able to
        establish a connection with comm.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        auth_method = 'munge'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': auth_method,
                      'PBS_AUTH_METHOD': auth_method,
                      'PBS_AUTH_SERVICE_USERS': 'random_user'}

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        common_msg = f'Connection to pbs_comm {self.server.shortname}:17001 down'
        common_msg1 = f'Supported authentication method: {auth_method}'
        common_msg2 = f'TPP authentication method = {auth_method}'

        exp_msg = {'comm': [common_msg1, common_msg2, f'User {str(ROOT_USER)} not in service users list'],
                   'mom': common_msg,
                   'server': [common_msg, common_msg1, common_msg2]
                   }
        self.update_pbs_conf(conf_param, check_state=False)
        self.match_logs(exp_msg)

    def test_daemon_not_in_service_users_with_resvport(self):
        """
        Test behavior when the daemon user is not in the PBS_AUTH_SERVICE_USERS
        list when using resvport for authentication. The daemon user name is not
        available with using resvport. Therefore we expect that the daemons will
        connect to comm successfully.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        auth_method = 'resvport'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': auth_method,
                      'PBS_AUTH_METHOD': auth_method,
                      'PBS_AUTH_SERVICE_USERS': 'random_user'}

        nt_exp_msg = f'Connection to pbs_comm {self.server.shortname}:17001 down'
        common_msg1 = f'Supported authentication method: {auth_method}'
        common_msg2 = f'TPP authentication method = {auth_method}'

        exp_msg = {'comm': [common_msg1],
                   'mom': common_msg2,
                   'server': [common_msg1, common_msg2]
                   }
        self.update_pbs_conf(conf_param, check_state=False)
        self.match_logs(exp_msg, nt_exp_msg)
        self.common_commands_steps()

    def test_default_interactive_auth_method(self):
        """
        Test that we can successfully run interactive jobs when using the default
        (resvport) interactive authentication method.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047"}
        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True

        auth_method = 'resvport'
        common_msg1 = f'TPP authentication method = {auth_method}'
        common_msg2 = f'Supported authentication method: {auth_method}'
        mom_msg = f'interactive authentication method = {auth_method}'
        exp_msg = {'server': [common_msg1, common_msg2],
                   'comm': [common_msg2]}

        self.update_pbs_conf(conf_param, check_state=check_state)
        self.match_logs(exp_msg)
        self.simple_interactive_job()
        self.match_logs({'mom': mom_msg})

    def test_interactive_job_with_resvport(self):
        """
        Test that we can successfully run interactive jobs when using resvport
        as the interactive authentication method.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        auth_method = 'resvport'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': auth_method,
                      'PBS_AUTH_METHOD': auth_method,
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True

        common_msg1 = f'TPP authentication method = {auth_method}'
        common_msg2 = f'Supported authentication method: {auth_method}'
        mom_msg = f'interactive authentication method = {auth_method}'
        exp_msg = {'server': [common_msg1, common_msg2],
                   'comm': [common_msg2]}

        self.update_pbs_conf(conf_param, check_state=check_state)
        self.match_logs(exp_msg)
        self.simple_interactive_job()
        self.match_logs({'mom': mom_msg})

    def test_interactive_job_with_munge(self):
        """
        Test that we can successfully run interactive jobs when using munge
        as the interactive authentication method.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        auth_method = 'munge'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': f"resvport,{auth_method}",
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            check_state = False
        else:
            check_state = True

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        common_msg1 = f'TPP authentication method = resvport'
        common_msg2 = f'Supported authentication method: resvport'
        common_msg3 = f'Supported authentication method: {auth_method}'
        mom_msg = f'interactive authentication method = {auth_method}'
        exp_msg = {'server': [common_msg1, common_msg2, common_msg3],
                   'comm': [common_msg2, common_msg3]}

        self.update_pbs_conf(conf_param, check_state=check_state)
        self.match_logs(exp_msg)
        self.simple_interactive_job()
        self.match_logs({'mom': mom_msg})

    def test_multiple_interactive_auth_methods(self):
        """
        Test that we can successfully run itneractive jobs when supporting
        multiple interactive auth methods.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': 'munge,resvport'}
        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)
            check_state = False
        else:
            check_state = True

        # Function call to check if munge is installed and enabled
        for host_name in self.node_list:
            self.perform_op(choice='check_installed_and_run',
                            host_name=host_name)

        common_msg1 = f'Supported authentication method: munge'
        common_msg2 = f'Supported authentication method: resvport'

        exp_msg = {'server': [common_msg1, common_msg2],
                   'comm': [common_msg1, common_msg2]}

        for auth_method in ['resvport', 'munge']:
            conf_param['PBS_INTERACTIVE_AUTH_METHOD'] = auth_method
            self.update_pbs_conf(conf_param, check_state=check_state)
            if self.server.shortname != self.mom.shortname:
                self.update_pbs_conf(conf_param, host_name=self.mom.shortname)
            self.match_logs(exp_msg)
            self.simple_interactive_job()
            self.match_logs({'mom': f'interactive authentication method = {auth_method}'})
            self.update_pbs_conf(['PBS_INTERACTIVE_AUTH_METHOD'], op='unset', restart=False)

    def test_not_listed_interactive_auth_method(self):
        """
        Test behavior when the provided interactive auth method is not in
        supported methods.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        self.svr_mode = self.server.get_op_mode()
        if self.svr_mode != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        auth_method = 'munge'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': 'resvport',
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True

        self.update_pbs_conf(conf_param, check_state=check_state)
        common_msg1 = f'Supported authentication method: resvport'

        exp_msg = {'server': [common_msg1],
                   'comm': [common_msg1]}
        self.match_logs(exp_msg)
        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('sleep 100', '.*')]
        jid = self.server.submit(j)
        self.match_logs({'mom': f'interactive authentication method {auth_method} not supported'})

    def test_invalid_interactive_auth_method(self):
        """
        Test behavior when the provided interactive auth method is invalid.

        Node 1: Server, Sched, Mom, Comm [self.hostA]
        """
        self.svr_mode = self.server.get_op_mode()
        if self.svr_mode != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        auth_method = 'testing'
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047",
                      'PBS_SUPPORTED_AUTH_METHODS': 'resvport',
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        if self.server.shortname != self.mom.shortname:
            check_state = False
        else:
            check_state = True

        self.update_pbs_conf(conf_param, check_state=check_state)
        common_msg1 = f'Supported authentication method: resvport'

        exp_msg = {'server': [common_msg1],
                   'comm': [common_msg1]}
        self.match_logs(exp_msg)
        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('sleep 100', '.*')]
        jid = self.server.submit(j)
        self.match_logs({'mom': f'interactive authentication method {auth_method} not supported'})

    def test_penetration_interactive_auth_resvport(self):
        """
        Test that qsub interactive will reject unathorized incoming connections.
        1. qsub -I starts listening for an incoming connection
        2. We connect to the qsub socket and send a random message
        3. qsub should reject the connection since it does not originate from a
        privileged port.

        Node 1: Server, Sched, Mom, Comm
        """
        auth_method = 'resvport'
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': auth_method,
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        self.helper_pentest_interactive_auth_1(conf_param)

    def test_penetration_interactive_auth_munge(self):
        """
        Test that qsub interactive will reject unathorized incoming connections.
        1. qsub -I starts listening for an incoming connection
        2. We connect to the qsub socket and send a random message
        3. qsub should reject the connection since it does not match with a valid
        root munge token.

        Node 1: Server, Sched, Mom, Comm
        """
        # Function call to check if munge is installed and enabled
        self.perform_op(choice='check_installed_and_run',
                        host_name=self.server.hostname)

        auth_method = 'munge'
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': f'resvport,{auth_method}',
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        self.helper_pentest_interactive_auth_1(conf_param)

    def helper_pentest_interactive_auth_1(self, conf_param):
        """
        Helper function for pen-testing interactive authentication.
        In this test a malicious user connects to the qsub -I socket and
        submits a random message. The connection should be refused since it
        does not match the expected credentials. When scheduling is turned on,
        a valid execution host should be able to connect to qsub -I and the
        interactive job should start running.

        :param conf_param: Configuration parameters to update in pbs.conf
        :type conf_param: dict
        """
        if self.server.get_op_mode() != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        self.update_pbs_conf(conf_param, host_name=self.svr_hostname)

        # turn off scheduling, so we can try to connect with qsub
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        # submit an interactive job
        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('sleep 100', '.*')]
        jid = self.server.submit(j)
        # Get the address and port of qsub -I
        address, port = self.get_qsub_address_port(host=self.svr_hostname)
        self.assertTrue(port and address, "Failed to get qsub -I address and port")
        family, socktype, _, _, sockaddr = socket.getaddrinfo(address, port)[0]
        # Create a TCP socket and connect to qsub
        with socket.socket(family, socktype) as sock:
            sock = socket.socket(family, socktype)
            sock.connect(sockaddr)
            with self.assertRaises(BrokenPipeError, msg='Connection was not refused'):
                for _ in range(10):
                    # Add a small delay so that MoM has the time to close the connection
                    time.sleep(5)
                    # Send the job id to qsub
                    sock.sendall(jid.encode())
        self.logger.info('Connection refused as expected')

        # the job should be still in the queue
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)
        # now turn scheduling on
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        # the job should be running
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

    def test_penetration_interactive_auth_resvport_2(self):
        """
        In this test the malicious user connects to the socket and stays idle.
        1. qsub -I starts listening for an incoming connection
        2. We connect to the qsub socket and stay idle.
        3. After a while the connection should timeout and be closed.
        4. When scheduling is turned on, a valid execution host should be able
        to connect to qsub -I.
        5. The interactive job should start running.

        Node 1: Server, Sched, Mom, Comm
        """
        auth_method = 'resvport'
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': f'{auth_method}',
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        self.helper_pentest_interactive_auth_2(conf_param=conf_param)

    def test_penetration_interactive_auth_munge_2(self):
        """
        In this test the malicious user connects to the socket and stays idle.
        1. qsub -I starts listening for an incoming connection
        2. We connect to the qsub socket and stay idle.
        3. After a while the connection should timeout and be closed.
        4. When scheduling is turned on, a valid execution host should be able
        to connect to qsub -I.
        5. The interactive job should start running.

        Node 1: Server, Sched, Mom, Comm
        """

        # Function call to check if munge is installed and enabled
        self.perform_op(choice='check_installed_and_run',
                        host_name=self.server.hostname)

        auth_method = 'munge'
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': f'resvport,{auth_method}',
                      'PBS_INTERACTIVE_AUTH_METHOD': auth_method}
        self.helper_pentest_interactive_auth_2(conf_param=conf_param)

    def helper_pentest_interactive_auth_2(self, conf_param):
        """
        Helper function for pen-testing interactive authentication.
        In this test a malicious user connects to the socket and stays idle.
        After a while the connection should timeout and be closed.
        When scheduling is turned on, a valid execution host should be able
        to connect to qsub -I and the interactive job should start running.

        :param conf_param: Configuration parameters to update in pbs.conf
        :type conf_param: dict
        """
        if self.server.get_op_mode() != PTL_CLI:
            self.server.set_op_mode(PTL_CLI)

        self.update_pbs_conf(conf_param, host_name=self.svr_hostname)

        # turn off scheduling, so we can try to connect with qsub
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # submit an interactive job
        j = Job(TEST_USER, attrs={ATTR_inter: ''})
        j.interactive_script = [('sleep 100', '.*')]
        jid = self.server.submit(j)

        # Get the address and port of qsub -I
        address, port = self.get_qsub_address_port(host=self.svr_hostname)
        self.assertTrue(port and address, "Failed to get qsub -I address and port")
        family, socktype, _, _, sockaddr = socket.getaddrinfo(address, port)[0]
        # Create a TCP socket and try to connect to qsub
        with socket.socket(family, socktype) as sock:
            sock.connect(sockaddr)
            # the job should be still in the queue
            self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)
            # now turn scheduling on
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            # the job should be running
            self.server.expect(JOB, {ATTR_state: 'R'}, id=jid, offset=30)

    def test_penetration_root_impersonation_munge(self):
        """
        Test that server will reject credentials that don't match with the
        username in the batch request.
        1. Send to the server a connect request with root as the username
        2. Then send a authenticate request with a root as the username
        3. Finally we send the TEST_USER's munge token.
        4. The server should reject the request since the username in the
        batch requests does not match with the username in the munge token.

        Node 1: Server, Sched, Mom, Comm
        """
        # Function call to check if munge is installed and enabled
        self.perform_op(choice='check_installed_and_run',
                        host_name=self.server.hostname)

        auth_method = 'munge'
        conf_param = {'PBS_AUTH_METHOD': f'{auth_method}',
                      'PBS_SUPPORTED_AUTH_METHODS': f'resvport,{auth_method}'}
        self.update_pbs_conf(conf_param, host_name=self.svr_hostname)

        packets_to_send = []
        # Need to run qstat under strace, to get all write system calls
        root_packets = self.get_qstat_write_syscalls(runas=ROOT_USER)
        self.assertGreater(len(root_packets), 2, f"Failed to get {ROOT_USER}'s write system calls for qstat")

        user_packets = self.get_qstat_write_syscalls(runas=TEST_USER)
        self.assertGreater(len(user_packets), 2, f"Failed to get {TEST_USER}'s write system calls for qstat")

        # This is the order the packets will be sent:
        # 1. PBS_BATCH_Connect as root
        # 2. PBS_BATCH_Authenticate as root
        # 3. TEST_USER's munge credentials
        packets_to_send = root_packets[:2] + [user_packets[2]]
        start_time = time.time()
        # Establish connection with server in port PBS_BATCH_SERVICE_PORT
        server_port = self.server.pbs_conf.get('PBS_BATCH_SERVICE_PORT', 15001)
        family, socktype, _, _, sockaddr = socket.getaddrinfo(self.svr_hostname, server_port)[0]
        # Create a TCP socket and try to connect to the server
        with socket.socket(family, socktype) as sock:
            sock = socket.socket(family, socktype)
            sock.connect(sockaddr)
            # Send PBS_BATCH_Connect
            sock.sendall(bytes.fromhex(packets_to_send[0].replace(r'\x', ' ')))
            # Send PBS_BATCH_Authenticate with user credentials
            sock.sendall(bytes.fromhex(packets_to_send[1].replace(r'\x', ' ')))
            sock.sendall(bytes.fromhex(packets_to_send[2].replace(r'\x', ' ')))
            reply = sock.recv(1024).decode()
            # Now match expected server logs
            self.server.log_match(f".*Type 0 request received from {ROOT_USER}.*",
                                    regexp=True, starttime=start_time)
            self.server.log_match(f".*Type 95 request received from {ROOT_USER}.*",
                                    regexp=True, starttime=start_time)
            self.server.log_match(".*;munge_validate_auth_data;MUNGE user-authentication on decode failed with `Replayed credential`.*",
                                    regexp=True, starttime=start_time)
            self.server.log_match(".*;tcp_pre_process;MUNGE user-authentication on decode failed with `Replayed credential`.*",
                                    regexp=True, starttime=start_time)

    def test_penetration_server_to_mom_over_tcp_1(self):
        """
        Test that MoM will reject unathenticated TCP requests at port 15002.
        1. We establish a TCP connection with MoM on port 15002 and submit a
        random request.
        2. MoM should reject the request since it does not contain the correct
        encrypted cipher.

        Node 1: Server, Sched, Mom, Comm
        """
        if os.getuid() != 0 or sys.platform in ('cygwin', 'win32'):
            self.skipTest("Test needs to run as root")

        packet = 'PKTV1\x00\x00\x00\x00\x00\x0d+1+1+2+5ncpus'
        # Establish connection with mom in port PBS_MANAGER_SERVICE_PORT
        mom_port = self.server.pbs_conf.get('PBS_MOM_SERVICE_PORT', 15002)
        family, socktype, _, _, sockaddr = socket.getaddrinfo(self.svr_hostname, mom_port)[0]
        start_time = time.time()
        # Create a TCP socket and connect to mom
        with socket.socket(family, socktype) as sock:
            # Bind to an available, privileged port
            self.bind_to_privileged_port(sock)
            sock.connect(sockaddr)
            # Send the packet
            sock.sendall(packet.encode())
            # Now match expected mom log
            self.mom.log_match(f".*pbs_mom;.*received incorrect auth token.*",
                               regexp=True, starttime=start_time)
            self.mom.log_match(f".*;pbs_mom;Svr;wait_request;process socket failed.*",
                               regexp=True, starttime=start_time)

    def test_penetration_server_to_mom_over_tcp_2(self):
        """
        Test that MoM will reject unathenticated TCP requests at port 15002.
        1. We establish a TCP connection with MoM on port 15002 and submit a
        request that looks similar to an encrypted cipher.
        2. MoM should reject the request since it does not match the expected
        encrypted cipher according to the authentication protocol.

        Node 1: Server, Sched, Mom, Comm
        """
        if os.getuid() != 0 or sys.platform in ('cygwin', 'win32'):
            self.skipTest("Test needs to run as root")

        random_str = ''.join(random.choices(string.ascii_letters, k=15)) +\
            ';' + ''.join(random.choices(string.ascii_letters, k=33))
        packet = 'PKTV1\x00\x01\x00\x00\x00\x31' + random_str
        # Establish connection with mom in port PBS_MANAGER_SERVICE_PORT
        mom_port = self.server.pbs_conf.get('PBS_MOM_SERVICE_PORT', 15002)
        family, socktype, _, _, sockaddr = socket.getaddrinfo(self.svr_hostname, mom_port)[0]
        start_time = time.time()
        # Create a TCP socket and connect to mom
        with socket.socket(family, socktype) as sock:
            # Bind to an available, privileged port
            self.bind_to_privileged_port(sock)
            sock.connect(sockaddr)
            # Send the packet
            sock.sendall(packet.encode())
            # Now match expected mom log
            self.mom.log_match(f".*pbs_mom;validate_hostkey, decyrpt failed, host_keylen=.*",
                               regexp=True, starttime=start_time)
            self.mom.log_match(f".*pbs_mom;.*Failed to decrypt auth data.*",
                               regexp=True, starttime=start_time)
            self.mom.log_match(f".*;pbs_mom;Svr;wait_request;process socket failed.*",
                               regexp=True, starttime=start_time)

    def bind_to_privileged_port(self, sock):
        """
        Bind to an available, privileged port

        :param sock: The socket to bind
        :type sock: socket.socket
        :return: The privileged port number that was successfully bound
        """
        port_found = False
        for local_port in range(1023, 0, -1):
            try:
                sock.bind((self.svr_hostname, local_port))
                port_found = True
                break
            except socket.error as e:
                if e.errno != errno.EADDRINUSE:
                    raise e
        self.assertTrue(port_found, "Failed to find an available privileged port")
        return local_port

    def get_qsub_address_port(self, host):
        """
        Extract the address and listenting port of a qsub interactive session

        :param host: The hostname of the host where qsub -I was run
        :type host: str
        :return: A tuple containing the address and port of the qsub session,
                    or (None, None) if not found
        """
        tool = self.du.which(hostname=host, exe='ss')
        if tool == 'ss':
            tool = self.du.which(hostname=host, exe='netstat')
        if tool == 'netstat':
            self.skipTest(f"Command ss or netstat not found on {host}")
        cmd = [tool, '-tnap']
        ret = self.du.run_cmd(hosts=host, cmd=cmd, runas=ROOT_USER)
        if ret['rc'] == 0:
            for line in ret['out']:
                if 'LISTEN' in line and 'qsub' in line:
                    # this should extract the port number from the output
                    m = self.re_addr_port.match(line.split()[3])
                    if m:
                        return m.group('addr'), m.group('port')
        self.logger.error(f"Failed to get qsub -I address and port with: {ret['err']}")
        return None, None

    def get_qstat_write_syscalls(self, runas, host=None):
        """
        Get all write system calls made by qstat

        param runas: The user to run the command as
        type runas: str
        return: A list of all write system calls made by qstat.
        """
        strace = self.du.which(hostname=host, exe='strace')
        if strace == 'strace':
            self.skipTest("Command strace not found")
        qstat = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat')
        cmd = [strace, '--trace=write', '-s1024', '-x', '-q', '--', qstat]
        ret = self.du.run_cmd(cmd=cmd, runas=runas, hosts=host, logerr=False)
        calls = []
        if ret['rc'] == 0:
            for line in ret['err']:
                m = self.re_syscall.match(line)
                if m:
                    calls.append(m.group('write_buffer'))
        else:
            self.logger.error(f"Failed to get qstat write system calls with: {ret['err']}")
        return calls

    def tearDown(self):
        conf_param = ['PBS_SUPPORTED_AUTH_METHODS',
                      'PBS_AUTH_METHOD',
                      'PBS_COMM_LOG_EVENTS',
                      'PBS_COMM_ROUTERS',
                      'PBS_LEAF_ROUTERS',
                      'PBS_INTERACTIVE_AUTH_METHOD',
                      'PBS_AUTH_SERVICE_USERS']
        restart = True
        self.node_list = set(self.node_list)
        for host_name in self.node_list:
            if host_name == self.client_host:
                restart = False
            self.update_pbs_conf(conf_param, host_name, op='unset',
                                 restart=restart, check_state=False)
        self.node_list.clear()
