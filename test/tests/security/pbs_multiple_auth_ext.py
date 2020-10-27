# coding: utf-8
# Copyright (C) 2003-2020 Altair Engineering, Inc. All rights reserved.
# Copyright notice does not imply publication.
#
# ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
# Information. Not for use or disclosure outside of Licensee's organization.
# The software and information contained herein may only be used internally and
# is provided on a non-exclusive, non-transferable basis. License may not
# sublicense, sell, lend, assign, rent, distribute, publicly display or
# publicly perform the software or other information provided herein,
# nor is Licensee permitted to decompile, reverse engineer, or
# disassemble the software. Usage of the software and other information
# provided by Altair(or its resellers) is only as explicitly stated in the
# applicable end user license agreement between Altair and Licensee.
# In the absence of such agreement, the Altair standard end user
# license agreement terms shall govern.

from tests.security import *


class TestMultipleAuthMethods_ext(TestSecurity):
    """
    This test suite contains tests for Multiple authentication added to PBS
    """
    node_list = []
    default_client = None

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
        if host_name is None:
            host_name = self.svr_hostname
        pbsconfpath = self.du.get_pbs_conf_file(host_name)
        if op == 'set':
            self.du.set_pbs_config(hostname=host_name,
                                   fin=pbsconfpath,
                                   confs=conf_param)
        else:
            self.du.unset_pbs_config(hostname=host_name,
                                     fin=pbsconfpath,
                                     confs=conf_param)
        if restart:
            self.pbs_restart(host_name, node_state=check_state)

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

    def pbs_restart(self, host_name=None, node_state=True):
        """
        This function restarts PBS on host.
        :param host_name: Name of the host on which pbs daemons
                          has to be restarted
        :type host_name: String
        :param node_state: Check node state to be free
        :type node_state: Bool
        """
        if host_name is None:
            host_name = self.mom.shortname
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
        munge_cmd = self.du.which(exe="munge",hostname=host_name)
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
        self.mom.log_match(exp_msg['mom'], starttime=st_time)
        for msg in exp_msg['server']:
            self.server.log_match(msg, starttime=st_time)
        for msg in exp_msg['comm']:
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

        r = Reservation(self.cur_user, resv_attr)
        rid = self.server.submit(r)
        self.server.log_match(exp_msg, starttime=self.server.ctime)

        start_time = time.time()
        exp_state = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED")}
        self.server.expect(RESV, exp_state, id=rid)

        start_time = time.time()
        self.server.delete(rid)
        self.server.log_match(exp_msg, starttime=start_time)

        start_time = time.time()
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.log_match(exp_msg, starttime=start_time)

        start_time = time.time()
        j = Job(self.cur_user)
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

    def test_default_auth_method(self):
        """
        Test to verify all PBS daemons and commands are authenticated
        via default authentication method
        default authentication method is resvport
        """
        conf_param = {'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param)
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
            self.update_pbs_conf(conf_param, host_name=host_name)

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
                   'qstat: cannot connect to server %s (errno=15029)'
                   % (self.server.hostname)]

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

        try:
            self.pbs_restart()
        except PbsInitServicesError as e:
            matchs = "pbs_mom startup failed, exit 1 aborting"
            self.assertIn(matchs, e.msg)
            self.logger.info(_msg + str(e.msg))
        else:
            err_msg = "Failed to get expected error message in PBS restart: "
            err_msg += matchs

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

        common_mssg = 'MUNGE user-authentication on encode failed with '
        common_mssg += '`Socket communication error`'

        # To stop munge process and check if successfull
        self.munge_operation(host_name=self.svr_hostname, op='stop')

        exp_msgs = ['munge_get_auth_data: ' + common_mssg,
                    'auth: error returned: 15010',
                    'auth: ' + common_mssg,
                    'System call failure.',
                    'qsub: cannot connect to server %s (errno=15010)'
                    % self.svr_hostname
                    ]

        # Submit a job and it should fail resulting in expected error
        j = Job(self.cur_user)
        _msg = "Trying to start munge daemon"
        try:
            j1id = self.server.submit(j)
        except PbsSubmitError as e:
            for mssg in exp_msgs:
                self.assertIn(mssg, e.msg)
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

        cmn_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin')
        cmn_msg = ': cannot connect to server %s, error=15010' % self.svr_hostname

        pbsnodes_cmd = os.path.join(cmn_cmd, 'pbsnodes')
        msg = pbsnodes_cmd + cmn_msg
        exp_msgs = ['init_munge: libmunge.so not found',
                    'auth: error returned: 15010',
                    'auth: Munge lib is not loaded',
                    'System call failure.',
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

        qstat_cmd = os.path.join(cmn_cmd, 'qstat')
        msg = qstat_cmd + cmn_msg
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
        hostname = self.server.hostname
        # Function call to check if munge is not installed and then proceeding
        # with test case execution
        self.perform_op(choice='check_not_installed',
                        host_name=self.svr_hostname)

        conf_attrib = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                       'PBS_AUTH_METHOD': 'MUNGE',
                       'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_attrib, check_state=False)

        if self.server.shortname != self.mom.shortname:
            self.node_list.append(self.mom.shortname)      
            conf_param = {'PBS_AUTH_METHOD': 'munge'}
            self.update_pbs_conf(conf_param, host_name=self.mom.shortname,check_state=False)

        exp_log = "libmunge.so not found"

        # Check Daemons log message for error message
        self.server.log_match(exp_log)
        self.mom.log_match(exp_log)
        err_msg = '.*Received authentication error from router'
        err_msg += r' \(%s\)\d+\.\d+\.\d+\.\d+:17001, ' % (self.comm)
        err_msg += r'err=\d+, msg="tfd=\d+ connection from '
        err_msg += r'\(%s|\d+\.\d+\.\d+\.\d+\)' % (self.mom)
        err_msg += r'\d+\.\d+\.\d+\.\d+:\d+ '
        err_msg += 'failed authentication. libmunge.so not found'
        self.mom.log_match(err_msg)

        self.common_steps_without_munge()

    @requirements(num_moms=2)
    def test_without_munge_on_mom_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on remote
        mom host where munge is not installed.
        Node 1: Server, Sched, Mom, Comm [self.hostA]
        Node 2: Mom [self.hostB]
        """
        mom_list = [x.shortname for x in self.moms.values()]
        self.momB = self.moms.values()[1]
        self.hostB = mom_list[1]
        self.node_list.append(self.hostB)
        if self.server.shortname not in mom_list:
            self.hostA = mom_list[0]
            self.node_list.append(self.hostA)

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostB)

        conf_attrib = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                       'PBS_AUTH_METHOD': 'MUNGE',
                       'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_attrib, check_state=False)

        conf_param = {'PBS_AUTH_METHOD': 'munge'}
        for mom in mom_list:
            if mom != self.server.shortname:
                self.update_pbs_conf(conf_param, host_name=mom, check_state=False)

        exp_log = "libmunge.so not found"
        self.momB.log_match(exp_log)
        self.common_steps_without_munge(self.hostB)
        

    @requirements(num_moms=2, num_comms=1, no_comm_on_server=True)
    def test_without_munge_on_comm_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on
        comm host where munge is not installed.
        when pbs_comm and client are on non-server host
        Configuration:
        Node 1: Server, Sched, Mom [self.hostA]
        Node 2: Mom [self.hostB]
        Node 3: Comm [self.hostC]
        """
        mom_list = [x.shortname for x in self.moms.values()]
        self.momB = self.moms.values()[1]
        self.hostB = mom_list[1]
        self.hostC = self.comm.shortname
        self.node_list.append(self.hostB)
        self.node_list.append(self.hostC)
        if self.server.shortname not in mom_list:
            self.hostA = mom_list[0]
            self.node_list.append(self.hostA)

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostC)

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_LEAF_ROUTERS': self.hostC}
        self.update_pbs_conf(conf_param, check_state=False)

        del conf_param['PBS_LEAF_ROUTERS']
        conf_param['PBS_COMM_LOG_EVENTS'] = 2047
        self.update_pbs_conf(conf_param, host_name=self.hostC, check_state=False)

        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        conf_param['PBS_LEAF_ROUTERS'] = self.hostC
        for mom in mom_list:
            if mom != self.server.shortname:
                self.update_pbs_conf(conf_param, host_name=mom, check_state=False)

        self.common_steps_without_munge(self.hostC)


    @requirements(num_client=1, num_moms=2)
    def test_without_munge_on_client_host(self):
        """
        Test behavior when PBS_AUTH_METHOD is set to munge on
        comm host where munge is not installed.
        when pbs_comm and client are on non-server host
        Configuration:
        Node 1: Server, Sched, Mom, Comm [self.hostA]
        Node 2: Mom [self.hostB]
        Node 3: Client [self.hostC]
        """
        mom_list = [x.shortname for x in self.moms.values()]
        self.momB = self.moms.values()[1]
        self.hostB = mom_list[1]
        self.hostC = self.server.client
        self.node_list.append(self.hostB)
        self.node_list.append(self.hostC)
        if self.server.shortname not in mom_list:
            self.hostA = mom_list[0]
            self.node_list.append(self.hostA)

        self.perform_op(choice='check_not_installed',
                        host_name=self.hostC)

        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(conf_param, check_state=False)
        del conf_param['PBS_COMM_LOG_EVENTS']
        self.update_pbs_conf(conf_param, host_name=self.hostC,
                             restart=False)
        conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
        for mom in mom_list:
            if mom != self.server.shortname:
                self.update_pbs_conf(conf_param, host_name=mom, check_state=False)

        self.common_steps_without_munge(self.hostC)

    @requirements(num_client=1, no_mom_on_server=True,
                  no_comm_on_server=True)
    def test_munge_with_mom_comm_on_nonserver_host(self):
        """
        Verify all PBS daemons and commands are authenticated via Munge
        when pbs_comm and client are on non-server host
        Configuration:
        Node 1: Server, Sched [self.hostA]
        Node 2: mom [self.hostB]
        Node 3: comm [self.hostC]
        Node 4: client [self.hostD]
        """
        self.hostA = self.server.shortname
        self.momA = self.moms.values()[0]
        self.hostB = self.momA.shortname
        self.comm1 = self.comms.values()[0]
        self.hostC = self.comm1.shortname
        self.hostD = self.client_host = self.server.client
        hosts = [self.hostA, self.hostB, self.hostC, self.hostD]
        self.node_list = hosts

        # Check if munge is installed on all the hosts in the cluster
        node_state = False
        for host in self.node_list:
            self.perform_op('check_installed_and_run', host_name=host,
                            node_state=node_state)

        # Update pbs.conf of comm node (self.hostC)
        conf_param = {'PBS_SUPPORTED_AUTH_METHODS': "munge",
                      'PBS_AUTH_METHOD': 'munge',
                      'PBS_COMM_LOG_EVENTS': "2047"}
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostC,
            check_state=False)

        # Update pbs.conf of Server node (self.hostA)
        del conf_param['PBS_COMM_LOG_EVENTS']
        conf_param['PBS_LEAF_ROUTERS'] = self.hostC
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostA,
            check_state=False)

        # Update pbs.conf of Mom node (self.hostB)
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        # Update pbs.conf of client node (self.hostD)
        del conf_param['PBS_LEAF_ROUTERS']
        self.update_pbs_conf(conf_param, host_name=self.hostD, restart=False,
                             check_state=False)

        exp_msg = "TPP authentication method = munge"

        common_msg = 'TPP authentication method = munge'
        common_msg1 = 'Supported authentication method: munge'
        exp_msg = {'server': [common_msg],
                   'comm': [common_msg1],
                   'mom': common_msg}

        nt_exp_msg = 'TPP authentication method = resvport'
        self.match_logs(exp_msg, nt_exp_msg)
        self.common_commands_steps(client=self.hostD)

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
        if num_moms == 2 and num_comms == 1:
            self.hostA = self.server.shortname
            self.momB = self.moms.values()[1]
            self.hostB = self.momB.shortname
            self.comm = self.comms.values()[0]
            self.hostC = self.comm.shortname
            self.hostD = self.server.client
            self.node_list = [self.hostA, self.hostB, self.hostC, self.hostD]
            mom_list = [x.shortname for x in self.moms.values()]
            if self.server.shortname not in mom_list:
                self.momA = self.moms.values()[0]
                self.hostE = self.momA.shortname
                self.node_list.append(self.hostE)
        elif num_moms == 2 and num_comms == 2:
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

    @requirements(num_comms=3, num_moms=2, no_mom_on_server=True,
                  num_client=1)
    def test_munge_with_multiple_comms(self):
        """
        Verify all PBS daemons and commands are authenticated via Munge
        when multiple pbs_comm's are present in cluster
        Configuration:
        Node 1 : Server, Sched, Comm (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Comm (self.hostD)
        Node 4 : Mom (self.hostC)
        Node 5 : Comm (self.hostE)
        Node 6 : Client (self.hostF)
        """
        self.common_setup(req_moms=2, req_comms=3)

        mom_list = [x.shortname for x in self.moms.values()]

        for host in self.node_list:
            if host in mom_list:
                node_state = True
            else:
                node_state = False
            self.perform_op('check_installed_and_run', host_name=host,
                            node_state=node_state)

        # Update pbs.conf file on comm nodes [self.hostC, self.hostE]
        hosts = [self.hostD, self.hostE]
        conf_param = {'PBS_COMM_ROUTERS': self.hostA,
                      'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE',
                      'PBS_AUTH_METHOD': 'MUNGE'}
        for host_name in hosts:
            self.update_pbs_conf(
                conf_param,
                host_name=host_name,
                check_state=False)

        # Update pbs.conf on server node
        del conf_param['PBS_COMM_ROUTERS']
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostA,
            check_state=False)

        # Update pbs.conf file on client node
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        del conf_param['PBS_COMM_LOG_EVENTS']
        self.update_pbs_conf(conf_param, host_name=self.hostF, restart=False,
                             check_state=False)

        # Update pbs.conf file on mom1 node
        conf_param['PBS_LEAF_ROUTERS'] = self.hostD
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        # Update pbs.conf file on mom2 node
        conf_param['PBS_LEAF_ROUTERS'] = self.hostE
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostC,
            check_state=False)
        del conf_param['PBS_LEAF_ROUTERS']

        exp_msg = ["TPP authentication method = munge"]
        non_existent_msg = "TPP authentication method = resvport"
        for mom in self.moms.values():
            mom.log_match(exp_msg[0])
            mom.log_match(non_existent_msg, existence=False)

        self.server.log_match(exp_msg[0])
        self.server.log_match(non_existent_msg, existence=False)

        exp_msg.append("Supported authentication method: munge")
        for comm in self.comms.values():
            for msg in exp_msg:
                comm.log_match(msg)
            comm.log_match(non_existent_msg, existence=False)

        self.common_commands_steps(client=self.hostF)

    @requirements(num_comms=3, num_moms=2, no_mom_on_server=True,
                  num_client=1)
    def test_multiple_supported_auth_methods_with_multi_comm(self):
        """
        Verify all PBS daemons and commands are authenticated via mechanism
        specifed in both PBS_SUPPORTED_AUTH_METHODS and PBS_AUTH_METHOD
        Configuration:
        Node 1 : Server, Sched, Comm (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Comm (self.hostD)
        Node 4 : Mom (self.hostC)
        Node 5 : Comm (self.hostE)
        Node 6 : Client (self.hostF)
        """
        self.common_setup(req_moms=2, req_comms=3)

        # Update pbs.conf of second comm (self.hostD)
        conf_param = {'PBS_COMM_ROUTERS': self.hostA,
                      'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'resvport'}
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostD,
            check_state=False)

        # Update pbs.conf of Server node (self.hostA)
        del conf_param['PBS_COMM_ROUTERS']
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostA,
            check_state=False)

        # Copy conf_param dict to use it in updating third comms pbs.conf
        conf_param1 = conf_param.copy()

        # Update pbs.conf of Client node (self.hostF)
        del conf_param['PBS_COMM_LOG_EVENTS']
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        self.update_pbs_conf(conf_param, host_name=self.hostF, restart=False,
                             check_state=False)

        # Update pbs.conf of first mom (self.hostB)
        conf_param['PBS_LEAF_ROUTERS'] = self.hostD
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        # Update pbs.conf of second mom (self.hostC)
        conf_param['PBS_LEAF_ROUTERS'] = self.hostE
        conf_param['PBS_AUTH_METHOD'] = 'munge'
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostC,
            check_state=False)

        exp_msg = ["TPP authentication method = resvport"]
        self.momB.log_match(exp_msg[0])
        exp_msg.append("Supported authentication method: munge")
        exp_msg.append("Supported authentication method: resvport")
        for msg in exp_msg:
            self.server.log_match(msg)
            self.comm.log_match(msg)
            self.comm2.log_match(msg)

        non_existent_msg = "TPP authentication method = munge"
        self.momB.log_match(non_existent_msg, existence=False)
        self.server.log_match(non_existent_msg, existence=False)
        self.comm.log_match(non_existent_msg, existence=False)
        self.comm2.log_match(non_existent_msg, existence=False)

        self.common_commands_steps(client=self.hostF)

        # Update pbs.conf of third comm (self.hostE) to use only munge as
        # supported authentication method
        conf_param1['PBS_SUPPORTED_AUTH_METHODS'] = 'munge'
        conf_param1['PBS_AUTH_METHOD'] = 'munge'
        self.update_pbs_conf(
            conf_param1,
            host_name=self.hostE,
            check_state=False)

        # Update pbs.conf of second mom (self.hostC) to use munge as
        # authentication mechanism
        conf_param['PBS_LEAF_ROUTERS'] = self.hostE
        conf_param['PBS_AUTH_METHOD'] = 'munge'
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostC,
            check_state=False)

        exp_msg[0] = "TPP authentication method = munge"
        self.momC.log_match(exp_msg[0])
        for msg in exp_msg:
            self.comm3.log_match(msg)

        non_existent_msg = "TPP authentication method = resvport"
        self.momC.log_match(non_existent_msg, existence=False)
        self.comm3.log_match(non_existent_msg, existence=False)

        self.server.expect(NODE, {'state': 'down'}, id=self.hostC)

    @requirements(num_comms=1, num_moms=2, num_client=1,
                  no_comm_on_server=True)
    def test_multiple_supported_auth_methods_multinode(self):
        """
        Verify all PBS daemons and commands are authenticated via Munge in
        when pbs_comm and client is on non-server host
        Configuration:
        Node 1 : Server, Sched, Mom (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Comm (self.hostC)
        Node 4 : Client (self.hostD)
        """
        self.common_setup()

        hosts = self.node_list
        hosts.remove(self.hostB)
        for host in hosts:
            self.perform_op('check_installed_and_run', host, node_state=False)

        # Update pbs.conf of comm (self.hostC)
        conf_param = {'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport'}
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostC,
            check_state=False)

        # Update pbs.conf of Server (self.hostA)
        del conf_param['PBS_COMM_LOG_EVENTS']
        conf_param['PBS_AUTH_METHOD'] = "munge"
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostA,
            check_state=False)

        # Update pbs.conf of Client (self.hostD)
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostD,
            check_state=False, restart=False)

        # set PBS_LEAF_ROUTERS param on all the moms
        del conf_param['PBS_AUTH_METHOD']
        conf_param['PBS_LEAF_ROUTERS'] = self.hostC
        for mom in self.moms.values():
            self.update_pbs_conf(conf_param, host_name=mom.name,
                                 check_state=False)
        server_ip = socket.gethostbyname(self.hostA)
        mom2_ip = socket.gethostbyname(self.hostB)
        msg = "Unauthenticated connection from %s" % self.server.shortname
        self.comm.log_match(msg, existence=False, starttime=self.server.ctime)
        attrib = {self.server.hostname: [server_ip, 15001, 15003, 15004],
                  self.momB.hostname: [mom2_ip, 15003]}
        ip = []
        port = []
        for host, host_attribs in attrib.items():
            ip = host_attribs.pop(0)
            for port in host_attribs:
                exp_msg = "Leaf registered address (%s)%s:%s" % (
                    host, ip, port)
                self.comm.log_match(exp_msg)

        set_attr = {ATTR_l + '.select': '2:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_set_attr = {ATTR_l + '.select': '2:ncpus=1',
                         ATTR_l + '.place': 'scatter',
                         'reserve_start': time.time() + 30,
                         'reserve_end': time.time() + 60}
        self.common_commands_steps(resv_attr=resv_set_attr,
                                   set_attr=set_attr,
                                   job_script=True, client=self.hostD)

    @requirements(num_moms=2)
    def test_munge_disabled_on_mom_host(self):
        """
        Test behavior when munge is stopped on Client host
        Configuration:
        Node 1 : Server, Sched, Comm, Mom (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Client (self.hostC)
        """
        if len(self.moms) != 2 and self.server.client == self.server.hostname:
            msg = "Test requires 2 moms and 1 client which is on non server"
            msg += " host as input"
            self.skipTest(msg)
        self.hostA = self.server.shortname
        self.momB = self.moms.values()[1]
        self.hostB = self.momB.shortname
        self.hostC = self.server.client
        nodes = [self.hostA, self.hostB, self.hostC]
        self.node_list = nodes
        for host in self.node_list:
            self.perform_op('check_installed_and_run', host, node_state=False)

        # Update pbs.conf of Server host
        conf_param = {'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'munge'}
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostA)

        # Update pbs.conf of Mom and Client host
        del conf_param['PBS_COMM_LOG_EVENTS']
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        hosts = [self.hostB, self.hostC]
        for node_name in hosts:
            if node_name == self.hostC:
                check_state = False
            else:
                check_state = True
            self.update_pbs_conf(
                conf_param,
                host_name=node_name, check_state=check_state)
        self.munge_operation(self.hostB, op="stop")
        self.pbs_restart(self.hostB, node_state=False)
        self.server.expect(NODE, {'state': 'down'}, id=self.hostB)
        set_attr = {ATTR_l + '.select': '2:ncpus=1',
                    ATTR_l + '.place': 'scatter'}
        j = Job()
        j.set_attributes(set_attr)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

    @requirements(no_mom_on_server=True, num_client=1)
    def test_munge_without_supported_auth_method_on_server(self):
        """
        Verify appropriate error msg is thrown when
        PBS_SUPPORTED_AUTH_METHODS is not added to pbs.conf on server host
        Configuration:
        Node 1 : Server, Sched, Comm (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Client (self.hostC)
        """
        if len(self.moms) != 2 and self.server.client == self.server.hostname:
            msg = "Test requires 2 moms and 1 client which is on non server"
            msg += " host as input"
            self.skipTest(msg)
        self.hostA = self.server.shortname
        self.momA = self.moms.values()[0]
        self.hostB = self.momA.shortname
        self.hostC = self.server.client

        nodes = [self.hostA, self.hostB, self.hostC]
        self.node_list = nodes

        # Verify if munge is installed on all the hosts
        for host in self.node_list:
            self.perform_op('check_installed_and_run', host)

        conf_param = {'PBS_AUTH_METHOD': 'MUNGE'}
        for host in self.node_list:
            self.update_pbs_conf(conf_param, host_name=host, check_state=False)

        err_msg = ['auth: error returned: 15029',
                   'auth: Failed to send auth request',
                   'No support for requested service.',
                   'qstat: cannot connect to server %s (errno=15029)'
                   % (self.server.hostname)]

        try:
            self.server.status(SERVER)
        except PbsStatusError as e:
            for msg in err_msg:
                self.assertIn(msg, e.msg)
        else:
            err_msg = "Failed to get expected error message"
            err_msg += " while checking server status."
            self.fail(err_msg)

    @requirements(num_comms=2, num_moms=2, no_mom_on_server=True,
                  num_client=1, no_comm_on_server=True)
    def test_multiple_supported_auth_methods_with_head_child_comm(self):
        """
        Verify all PBS daemons and commands are authenticated via mechanism
        specifed in both PBS_SUPPORTED_AUTH_METHODS and PBS_AUTH_METHOD
        when head and child comm are present in cluster
        Configuration:
        Node 1 : Server, Sched (self.hostA)
        Node 2 : Mom (self.hostB)
        Node 3 : Comm (self.hostD)
        Node 4 : Mom (self.hostC)
        Node 5 : Comm (self.hostE)
        Node 6 : Client (self.hostF)
        """
        self.common_setup(req_moms=2, req_comms=2)

        # Update pbs.conf of second comm (self.hostE)
        conf_param = {'PBS_COMM_ROUTERS': self.hostD,
                      'PBS_COMM_LOG_EVENTS': '2047',
                      'PBS_SUPPORTED_AUTH_METHODS': 'MUNGE,resvport',
                      'PBS_AUTH_METHOD': 'munge'}
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostE,
            check_state=False)

        # Update pbs.conf of first comm (self.hostD)
        del conf_param['PBS_COMM_ROUTERS']
        del conf_param['PBS_AUTH_METHOD']
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostD,
            check_state=False)

        # Update pbs.conf of first mom (self.hostB)
        del conf_param['PBS_COMM_LOG_EVENTS']
        del conf_param['PBS_SUPPORTED_AUTH_METHODS']
        conf_param['PBS_LEAF_ROUTERS'] = self.hostD
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        # Update pbs.conf of second mom (self.hostC)
        conf_param['PBS_LEAF_ROUTERS'] = self.hostE
        self.update_pbs_conf(
            conf_param,
            host_name=self.hostB,
            check_state=False)

        set_attr = {ATTR_l + '.select': '2:ncpus=1',
                    ATTR_l + '.place': 'scatter'}
        j = Job()
        j.set_attributes(set_attr)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        self.server.delete(jid)

        if self.momC.is_cpuset_mom():
            host = self.server.status(NODE)[2]['id']
        else:
            host = self.momC.shortname

        select = "vnode=" + host
        resv_attr = {'Resource_List.select': select,
                     'reserve_start': time.time() + 30,
                     'reserve_end': time.time() + 60}

        set_attr = {'Resource_List.select': select}
        self.common_commands_steps(resv_attr=resv_attr,
                                   set_attr=set_attr,
                                   client=self.hostF)

    def tearDown(self):
        conf_param = ['PBS_SUPPORTED_AUTH_METHODS',
                      'PBS_AUTH_METHOD',
                      'PBS_COMM_LOG_EVENTS']
        if len(self.node_list) == 0:
            self.update_pbs_conf(conf_param, op='unset')
        else:
            restart = True
            for host_name in self.node_list:
                temp_lst = ['PBS_COMM_ROUTERS', 'PBS_LEAF_ROUTERS']
                conf_param.extend(temp_lst)
                if host_name == self.client_host:
                    restart = False
                self.update_pbs_conf(conf_param, host_name, op='unset',
                                     restart=restart, check_state=False)
        self.server.client = self.default_client
        self.node_list.clear()
