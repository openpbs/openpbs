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

from tests.functional import *
from datetime import datetime, timedelta


@requirements(num_moms=2)
class TestMoMHooks(TestFunctional):
    """
    This test covers basic functionality of MoM Hooks
    """

    def setUp(self):
        TestFunctional.setUp(self)
        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        a = {'resources_available.ncpus': 8, 'resources_available.mem': '8gb'}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)
        pbsdsh_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  'bin', 'pbsdsh')
        self.job1 = Job()
        self.job1.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            "sleep 20\n")
        self.job2 = Job()
        self.job2.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            pbsdsh_cmd + " -n 1 /bin/echo hi\n" +
            pbsdsh_cmd + " -n 1 /bin/ls\n" +
            "sleep 20")
        self.job3 = Job()
        self.job3.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            "sleep 600\n")
        self.job4 = Job()
        self.job4.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            "sleep 20\n" +
            "exit 7")

    def hook_init(self, hook_name, hook_event, hook_body=None,
                  vnode_comment=None, resc_avail_file="1gb",
                  resc_avail_ncpus=2, freq=None, ignoreerror=False):
        """
        Dynamically create and import a MoM hook into the server.
        hook_name: the name of the hook to create. No default
        hook_event: the event type of the hook. No default
        hook_body: the body of the hook. If None, it is created "on-the-fly"
        based on vnode_comment, resc_avail_file, resc_avail_ncpus by calling
        customize_hook.
        resc_avail_file: the file size to set in the hook. Defaults to 1gb
        resc_avail_ncpus: the ncpus to set in the hook. Defaults to 2
        freq: The frequency of the periodic hook.
        ignoreerror: if True, ignore an error in importing the hook. This is
        needed for tests that test a hook error. Defaults to False.

        Return True on success and False otherwise.
        """
        a = {}
        if hook_event:
            a['event'] = hook_event
        if freq:
            a['freq'] = freq
        a['enabled'] = 'true'
        a['alarm'] = 5

        reject = delete = error = rerun = sister = alarm = exit = False

        if vnode_comment:
            if "reject" in vnode_comment:
                reject = True
            if "delete" in vnode_comment:
                delete = True
            if "error" in vnode_comment:
                error = True
            if "rerun" in vnode_comment:
                rerun = True
            if "sister" in vnode_comment:
                sister = True
            if "alarm" in vnode_comment:
                alarm = True
            if "end" in vnode_comment or "epi" in vnode_comment:
                exit = True

        if hook_body is None:
            hook_body = self.customize_hook(vnode_comment, alarm, sister, exit,
                                            delete, rerun, resc_avail_file,
                                            resc_avail_ncpus, reject, error)
        self.server.create_import_hook(hook_name, a, hook_body,
                                       overwrite=True)

    def get_job_exec_time(self, jid):
        """
        This function calculates the job's 'Execution_Time' by
        adding job's start_time and job's execution_time defined in the hook
        :param jid: Job Id
        :type jid: String
        """
        job_status = self.server.status(JOB, id=jid)[0]
        est_time = job_status['Execution_Time']
        start_time = job_status['stime']
        est_time = datetime.strptime(est_time, "%c")
        start_time = datetime.strptime(start_time, "%c")
        time_diff = (est_time - start_time).seconds
        msg = "Difference between observed and expected "
        msg += " 'Execution_Time' is more than 30 secs"
        self.assertAlmostEqual(time_diff, 300, delta=30, msg=msg)

    def basic_hook_accept(self, hook_name, hook_event,
                          hook_body=None, hook_job=None, vnode_comment=None,
                          resc_avail_file="1gb", resc_avail_ncpus=2):
        """
        This is a common function for the tests which accepts hook event
        :param hook_name: Name of the hook
        :type hook_name: String
        :param hook_event: Name of the hook event
        :type hook_event: String
        :param hook_body: Hook contents to import
        :type hook_body: String. Defaults to None
        :param hook_job: Job script
        :type hook_job: String. Defaults to None
        :param vnode_comment: Expected comment on Node after hook executes
        :type vnode_comment: String. Defaults to None
        :param resc_avail_file: Expected value of 'resources_available.file'
                                after hook executes
        :type resc_avail_file: String. Defaults to "1gb"
        :param resc_avail_ncpus: Expected value of 'resources_available.ncpus'
                                after hook executes
        :type resc_avail_ncpus: Integer. Defaults to 2
        """
        start_time = time.time()
        self.hook_init(hook_name, hook_event, hook_body,
                       vnode_comment, resc_avail_file, resc_avail_ncpus)
        jid = self.server.submit(hook_job)
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        if hook_event == "execjob_preterm":
            self.server.delete(jid)
        if "rerun" in vnode_comment and hook_event != "execjob_end":
            self.server.expect(JOB, {'job_state': 'H'}, jid)
            self.get_job_exec_time(jid)
            a = {'Hold_Types': 'su',
                 'Variable_List': (MATCH_RE, ".*BONJOUR=Mounsieur Shlomi.*")}
            self.server.expect(JOB, a, id=jid)
        else:
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        if hook_event == "execjob_preterm":
            exp_msg = ["Job;%s;signal job request received" % jid,
                       "Job;%s;signal job with TermJob" % jid,
                       ]
            for msg in exp_msg:
                self.momA.log_match(msg, starttime=start_time)
        m0 = {}
        if hook_event == "execjob_end":
            m00 = self.momA.log_match("Job;%s;Obit sent" % (jid),
                                      n='ALL', starttime=start_time)
            m0 = self.momA.log_match("Job;%s;delete job request received"
                                     % jid, n='ALL',
                                     starttime=start_time)
            if len(m00) > 0 and len(m0) > 0:
                last_m0 = m0[0]
                last_m00 = m00[0]
                if isinstance(m0, list):
                    last_m0 = m0[len(m0) - 1][0]
                if isinstance(m00, list):
                    last_m00 = m00[len(m00) - 1][0]
                msg = "m00 log-msg appeared after m0"
                self.assertGreater(last_m0, last_m00, msg)
        elif hook_event == "execjob_epilogue":
            m0 = self.momA.log_match("Job;%s;kill_job" % jid,
                                     n='ALL', starttime=start_time)
            m1 = self.momA.log_match("Hook;pbs_python;event is %s"
                                     % hook_event.upper(),
                                     n='ALL', starttime=start_time)
            if m0 and m1:
                last_m0 = m0[-1]
                last_m1 = m1[-1]
                msg = "m0 log-msg appeared after m1"
                self.assertGreater(last_m1, last_m0, msg)

        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;id = %s" % (jid),
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   "Hook;pbs_python;job is in_ms_mom",
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg, starttime=start_time)
        exp_msg[4] = "Hook;pbs_python;requestor_host is %s" % self.hostB
        exp_msg[5] = "Hook;pbs_python;job is NOT in_ms_mom"
        for msg in exp_msg:
            if hook_event == "execjob_end":
                self.momB.log_match(msg, starttime=start_time)
        if hook_event == "execjob_prologue":
            exp_msg = ["Job;%s;task 40000001 started, /bin/date" % jid,
                       "Job;%s;task 40000001 terminated" % jid,
                       "Job;%s;task 40000002 started, /bin/echo" % jid,
                       "Job;%s;task 40000002 terminated" % jid,
                       "Job;%s;task 40000003 started, /bin/ls" % jid,
                       "Job;%s;task 40000003 terminated" % jid
                       ]
            for msg in exp_msg:
                self.momB.log_match(msg, starttime=start_time)
        attrib = {'resources_available.file': resc_avail_file,
                  'resources_available.ncpus':
                  resc_avail_ncpus,
                  'comment': vnode_comment}
        for mom in self.moms.values():
            self.server.expect(NODE, attrib, id=mom.shortname)

    def basic_hook_reject(self, hook_name, hook_event, hook_body,
                          hook_job, vnode_comment, reject_msg,
                          acctlog_match=None,
                          resc_avail_file="1gb",
                          resc_avail_ncpus=2):
        """
        This is a common function for the tests which rejects hook event
        :param hook_name: Name of the hook
        :type hook_name: String
        :param hook_event: Name of the hook event
        :type hook_event: String
        :param hook_body: Hook contents to import
        :type hook_body: String. Defaults to None
        :param hook_job: Job script
        :type hook_job: String. Defaults to None
        :param vnode_comment: Expected comment on Node after hook executes
        :type vnode_comment: String. Defaults to None
        :param resc_avail_file: Expected value of 'resources_available.file'
                                after hook executes
        :type resc_avail_file: String. Defaults to "1gb"
        :param resc_avail_ncpus: Expected value of 'resources_available.ncpus'
                                after hook executes
        :type resc_avail_ncpus: Integer. Defaults to 2
        """
        start_time = time.time()
        self.hook_init(hook_name, hook_event, hook_body,
                       vnode_comment, resc_avail_file, resc_avail_ncpus)
        jid = self.server.submit(hook_job)
        m0 = {}
        if hook_event == "execjob_preterm":
            self.server.expect(JOB, {'job_state': 'R'}, jid)
            err_msg = "hook rejected request %s" % jid
            if "reject" not in vnode_comment:
                self.server.delete(jid)
            else:
                try:
                    self.server.delete(jid)
                except PbsDeleteError as e:
                    self.assertIn(err_msg, e.msg[0])
                    self.logger.info(
                        'As expected qdel throws error: ' + err_msg)
                else:
                    msg = "Able to delete job successfully"
                    self.fail(msg)
            m0 = self.momA.log_match("Job;%s;signal job request received"
                                     % jid, starttime=start_time,
                                     n='ALL')
            m = self.momA.log_match("Job;%s;signal job with TermJob" % jid,
                                    starttime=start_time, n='ALL')
            if "rerun" in vnode_comment:
                self.server.expect(JOB, {'job_state': 'H'}, jid)
            else:
                self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        elif hook_event == "execjob_epilogue":
            if "rerun" not in vnode_comment:
                self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
            else:
                self.server.expect(JOB, {'job_state': 'H'}, jid)
        elif hook_event == "execjob_end":
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        else:
            if "delete" in vnode_comment:
                self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
            else:
                self.server.expect(JOB, {'job_state': 'H'}, jid)

        m1 = self.momA.log_match("Hook;pbs_python;event is %s"
                                 % hook_event.upper(), n='ALL',
                                 starttime=start_time)
        if m0 and m1:
            last_m0 = m0[-1]
            last_m1 = m1[-1]
            msg = "m0 log-msg appeared after m1"
            self.assertGreater(last_m1, last_m0, msg)

        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;id = %s" % (jid),
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   "Hook;pbs_python;job is in_ms_mom",
                   "Hook;%s;%s request rejected by '%s'" % (
                       hook_name, hook_event, hook_name)
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg, starttime=start_time)

        if hook_event != "execjob_begin" and hook_event != "execjob_prologue":
            exp_msg[4] = "Hook;pbs_python;requestor_host is %s" % self.hostB
            exp_msg[5] = "Hook;pbs_python;job is NOT in_ms_mom"
            for msg in exp_msg:
                self.momB.log_match(msg, starttime=start_time)
        a = {'resources_available.file': resc_avail_file,
             'resources_available.ncpus': resc_avail_ncpus,
             'comment': vnode_comment}
        self.server.expect(NODE, a, id=self.hostA, interval=4)

        if (hook_event != "execjob_begin") and (
                hook_event != "execjob_prologue"):
            self.server.expect(NODE, a, id=self.hostB, interval=4)

        if hook_event == "execjob_begin":
            if hook_name in "delete":
                self.get_job_exec_time(jid)
                a = {'Hold_Types': 'su',
                     'comment': "Not Running: PBS Error: %s" %
                     (reject_msg),
                     'Variable_List': (MATCH_RE,
                                       ".*BONJOUR=Mounsieur Shlomi.*")}
                self.server.expect(JOB, a, id=jid)
        else:
            self.momA.tracejob_match(reject_msg, id=jid, n=100)

        if acctlog_match is not None:
            self.server.accounting_match("E;%s;.*%s.*" %
                                         (jid, acctlog_match), regexp=True,
                                         starttime=start_time)

    def basic_hook_error(self, hook_name, hook_event, hook_body,
                         hook_job, vnode_comment, reject_msg,
                         acctlog_match=None):
        """
        This is a common function for the tests where in hook returns error
        :param hook_name: Name of the hook
        :type hook_name: String
        :param hook_event: Name of the hook event
        :type hook_event: String
        :param hook_body: Hook contents to import
        :type hook_body: String. Defaults to None
        :param hook_job: Job script
        :type hook_job: String. Defaults to None
        :param vnode_comment: Expected comment on Node after hook executes
        :type vnode_comment: String. Defaults to None
        :param reject_msg: Expected hook rejected msg
        :type reject_msg: String.
        :param acctlog_match: Expected msg to search in accounting logs.
                              Defaults to None
        :type acctlog_match: String.
        """
        self.hook_init(hook_name, hook_event, hook_body,
                       vnode_comment, ignoreerror=True)
        a = {'resources_available.ncpus': 10,
             'resources_available.file': "10gb",
             'comment': 'ten'}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)
        jid = self.server.submit(hook_job)
        if hook_event == "execjob_preterm":
            self.server.expect(JOB, {'job_state': 'R'}, jid)
            err_msg = "hook rejected request %s" % jid
            try:
                self.server.delete(jid)
            except PbsDeleteError as e:
                self.assertIn(err_msg, e.msg[0])
                self.logger.info(
                    'As expected qdel throws error: ' + err_msg)
            else:
                msg = "Unexpectedly Job got deleted"
                self.fail(msg)
            exp_msg = ["Job;%s;signal job request received" % jid,
                       "Job;%s;signal job with TermJob" % jid,
                       ]
            for msg in exp_msg:
                self.momA.log_match(msg)
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        elif hook_event == "execjob_epilogue" or\
                hook_event == "execjob_end":
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        else:
            self.server.expect(JOB, {'job_state': 'H'}, jid)
        if hook_event == "execjob_prologue":
            exp_msg = ["Job;%s;JOIN_JOB as node 1" % jid,
                       "Job;%s;ABORT_JOB received" % jid,
                       ]
            for msg in exp_msg:
                self.momB.log_match(msg)
        else:
            common_msg = "pbs_python;PBS server internal error (15011) in "
            common_msg += "Error evaluating Python script,"
            msg1 = common_msg + " <class 'NameError'>"
            msg2 = common_msg + " name 'x' is not defined"
            msg3 = "Hook;%s;%s hook '%s' " % (hook_name, hook_event, hook_name)
            msg3 += "encountered an exception, request rejected"
            logmsg = [msg1, msg2, msg3]
            for msg in logmsg:
                self.momA.log_match(msg)
        a = {'resources_available.file': '10gb',
             'resources_available.ncpus': '10',
             'comment': 'ten'}
        self.server.expect(NODE, a, id=self.hostA, interval=4)

        if hook_event != "execjob_begin" and\
                hook_event != "execjob_prologue":
            self.server.expect(NODE, a, id=self.hostB, interval=4)

        if acctlog_match is not None:
            self.server.accounting_match(acctlog_match, regexp=True, n=100)

        if hook_event == "execjob_begin":
            a = {'Hold_Types': 's',
                 'comment': 'job held, too many failed attempts to run'}
            self.server.expect(JOB, a, id=jid)
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})
            self.server.runjob(jid, None)
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'true'})
        else:
            msg = "%s hook '%s' encountered an exception, request rejected" % \
                (hook_event, hook_name)
            self.momA.tracejob_match(msg, id=jid, n=100)
            if hook_event != "execjob_prologue":
                self.momB.tracejob_match(msg, id=jid, n=100)

    def basic_hook_alarm(self, hook_name, hook_event, hook_body,
                         hook_job, vnode_comment, reject_msg,
                         acctlog_match=None):
        """
        This is a common function for the tests where in hook is interrupted
        by alarm call
        :param hook_name: Name of the hook
        :type hook_name: String
        :param hook_event: Name of the hook event
        :type hook_event: String
        :param hook_body: Hook contents to import
        :type hook_body: String. Defaults to None
        :param hook_job: Job script
        :type hook_job: String. Defaults to None
        :param vnode_comment: Expected comment on Node after hook executes
        :type vnode_comment: String. Defaults to None
        :param reject_msg: Expected hook rejected msg
        :type reject_msg: String.
        :param acctlog_match: Expected msg to search in accounting logs.
                              Defaults to None
        :type acctlog_match: String.
        """
        self.hook_init(hook_name, hook_event, hook_body,
                       vnode_comment)
        a = {'resources_available.ncpus': 10,
             'resources_available.file': "10gb",
             'comment': 'ten'}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)
        jid = self.server.submit(hook_job)
        if hook_event == "execjob_preterm":
            self.server.expect(JOB, {'job_state': 'R'}, jid)
            err_msg = "hook rejected request %s" % jid
            try:
                self.server.delete(jid)
            except PbsDeleteError as e:
                self.assertIn(err_msg, e.msg[0])
                self.logger.info('As expected qdel throws error: ' + err_msg)
            else:
                msg = "Able to delete job successfully"
                self.fail(msg)
            exp_msg = ["Job;%s;signal job request received" % jid,
                       "Job;%s;signal job with TermJob" % jid,
                       ]
            for msg in exp_msg:
                self.momA.log_match(msg)
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        elif hook_event == "execjob_epilogue" or \
                hook_event == "execjob_end":
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        else:
            self.server.expect(
                JOB, {
                    'job_state': 'R', 'substate': '41'}, jid, interval=2)
        msg = "Job;%s;alarm call while running %s hook" % (jid, hook_event)
        msg += " '%s', request rejected" % hook_name
        self.momA.log_match(msg)
        a = {'resources_available.file': '10gb',
             'resources_available.ncpus': '10',
             'comment': 'ten'}
        self.server.expect(NODE, a, id=self.hostA, interval=4)

        if hook_event != "execjob_begin" and\
                hook_event != "execjob_prologue":
            self.server.expect(NODE, a, id=self.hostB, interval=4)
        elif hook_event == "execjob_prologue":
            exp_msg = ["Job;%s;JOIN_JOB as node 1" % jid,
                       "Job;%s;ABORT_JOB received" % jid,
                       ]
            for msg in exp_msg:
                self.momB.log_match(msg)
        if acctlog_match is not None:
            self.server.accounting_match(acctlog_match, regexp=True)
        if hook_event == "execjob_begin":
            self.server.expect(JOB, {'Hold_Types': 'n'}, id=jid)
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'false'})
            self.server.holdjob(jid, "s")
            self.server.expect(JOB, {'job_state': 'H'}, jid)
            self.server.runjob(jid)
            time.sleep(12)
            self.assertNotEqual(self.server.last_error, None)
            msg = "request rejected as filter hook '%s' got" % hook_name
            msg += " an alarm call. Please inform Admin"
            self.server.log_match(msg)

    def basic_hook_accept_periodic(self, hook_name, freq, hook_body):

        hook_event = "exechost_periodic"
        self.hook_init(hook_name, hook_event, hook_body, freq=freq)
        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg)
        exp_msg[3] = "Hook;pbs_python;requestor_host is %s" % self.hostB
        for msg in exp_msg:
            self.momB.log_match(msg)
        msg = "Not allowed to update vnode 'aspasia'"
        msg += ", as it is owned by a different mom"
        self.server.log_match(msg)

        a = {'state': 'offline',
             'resources_available.file': '17tb',
             'resources_available.ncpus': 17,
             'resources_available.mem': '700gb',
             'comment': "Comment update done  by %s hook @ %s" %
             (hook_name, self.hostA)}
        self.server.expect(NODE, a, id=self.hostA)
        a['comment'] = "Comment update done  by %s hook @ %s" % (
            hook_name, self.hostB)
        self.server.expect(NODE, a, id=self.hostB)
        a = {'resources_available.file': '500tb',
             'resources_available.mem': '300gb'}
        self.server.expect(NODE, a, id="aspasia")

    def basic_hook_reject_periodic(self, hook_name, freq, hook_body):

        hook_event = "exechost_periodic"
        self.hook_init(hook_name, hook_event, hook_body, freq=freq)
        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   "Hook;%s;%s request rejected by '%s'" %
                   (hook_name, hook_event, hook_name)
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg)
        exp_msg[3] = "Hook;pbs_python;requestor_host is %s" % self.hostB
        for msg in exp_msg:
            self.momB.log_match(msg)
        msg = "Not allowed to update vnode 'aspasia'"
        msg += ", as it is owned by a different mom"
        self.server.log_match(msg)
        msg = "symbolic reject!"
        for mom in self.moms.values():
            mom.log_match(msg)
        a = {'resources_available.mem': '1900gb',
             'comment': "Comment update done  by %s hook @ %s" %
             (hook_name, self.hostA)}
        self.server.expect(NODE, a, id=self.hostA)
        a['comment'] = "Comment update done  by %s hook @ %s" % (
            hook_name, self.hostB)
        self.server.expect(NODE, a, id=self.hostB)
        a = {'resources_available.file': '500tb',
             'resources_available.mem': '300gb'}
        self.server.expect(NODE, a, id="aspasia")

    def basic_hook_reject_sister(self, hook_name, hook_event,
                                 hook_body, hook_job, vnode_comment,
                                 reject_msg,
                                 acctlog_match=None):

        a = {'resources_available.ncpus': 10,
             'resources_available.file': "10gb",
             'comment': 'ten'}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)
        self.hook_init(hook_name, hook_event, hook_body, vnode_comment)
        jid = self.server.submit(hook_job)
        m0 = {}
        if hook_event == "execjob_preterm":
            self.server.expect(JOB, {'job_state': 'R'}, jid)
            self.server.delete(jid)
            if hook_name not in "preterm_reject_sister_py":
                self.assertNotEqual(self.server.last_error, None)
                self.assertNotEqual(str(self.server.last_error).find(
                                    "hook rejected request %s" % (jid)), -1)
            exp_msg = ["Job;%s;signal job request received" % jid,
                       "Job;%s;signal job with TermJob" % jid,
                       ]
            for msg in exp_msg:
                self.momA.log_match(msg)
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        elif hook_event == "execjob_end" or hook_event == "execjob_epilogue":
            self.server.expect(JOB, 'queue', jid, op=UNSET, offset=15)
        else:
            self.server.expect(JOB, {'job_state': 'H'}, jid)
        m1 = {}
        if "sister" not in vnode_comment:
            m1 = self.momA.log_match("Hook;pbs_python;event is %s" %
                                     (hook_event.upper()),
                                     allmatch=True, n="ALL")
        if m0 and m1 > 0:
            last_m0 = m0[-1]
            last_m1 = m1[-1]
            msg = "m0 log-msg appeared after m1"
            self.assertGreater(last_m1, last_m0, msg)

        pbs_version = self.server.status(NODE, id=self.hostB)[0]['pbs_version']
        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;id = %s" % (jid),
                   "Hook;pbs_python;vn[%s]" % self.hostB,
                   "Hook;pbs_python;name = %s" % self.hostB,
                   "Hook;pbs_python;requestor_host is %s" % self.hostB,
                   "Hook;pbs_python;job is NOT in_ms_mom",
                   "pbs_version = %s" % pbs_version,
                   "Hook;%s;%s request rejected by '%s'" % (
                       hook_name, hook_event, hook_name),
                   "Job;%s;%s" % (jid, reject_msg)
                   ]
        for msg in exp_msg:
            self.momB.log_match(msg)

        if hook_event == "execjob_begin":
            exp_msg = ["could not JOIN_JOB successfully",
                       "Job;%s;%s" % (jid, reject_msg)
                       ]
            for msg in exp_msg:
                self.momA.log_match(msg)
        a = {'resources_available.file': '1gb',
             'resources_available.ncpus': '2',
             'comment': vnode_comment}
        self.server.expect(NODE, a, id=self.hostB, interval=4)
        a = {
            'resources_available.file': '10gb',
            'resources_available.ncpus': 10}
        self.server.expect(NODE, a, id=self.hostA, interval=4)

        if hook_event == "execjob_begin":
            self.get_job_exec_time(jid)
            a = {'Hold_Types': 'su',
                 'Variable_List': (MATCH_RE, ".*BONJOUR=Mounsieur Shlomi.*")}
            self.server.expect(JOB, a, id=jid)

        if acctlog_match is not None:
            self.server.accounting_match("E;%s;.*%s.*" %
                                         (jid, acctlog_match), regexp=True)

    def common_steps_modify_resource(self, evnt, hook_rescused,
                                     hook_user=None):
        """
        This function create and import hook,
        then submit job and check that job is Running.

        this function having common steps for test
        'test_mom_hooks_modify_resource'
        """

        a = {'event': evnt, 'enabled': True}
        if hook_user:
            a['user'] = hook_user

        self.server.create_import_hook('testhook', a, hook_rescused)

        select_val = "vnode=" + self.hostA + "+vnode=" + self.hostB
        attrs = {'Resource_List.select': select_val}
        job = Job(TEST_USER, attrs)
        job.set_sleep_time(30)
        jid = self.server.submit(job)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        return jid

    def test_execjob_begin_with_accept(self):
        """
        Test execjob_begin which accepts the event
        """
        self.basic_hook_accept("begin", "execjob_begin",
                               None, self.job1, "In begin hook")

    def test_execjob_begin_with_del_job(self):
        """
        Test execjob_begin which accepts the event and deletes job
        """
        self.basic_hook_accept("begin", "execjob_begin",
                               None, self.job1,
                               "In begin_delete hook", "2gb", 3)

    def test_execjob_begin_with_rerun_job(self):
        """
        Test execjob_begin which accepts the event and reruns job
        """
        self.basic_hook_accept("begin", "execjob_begin",
                               None, self.job1,
                               "In begin_rerun hook", "3gb", 4)

    def test_execjob_begin_with_reject(self):
        """
        Test execjob_begin which rejects the event
        """
        self.basic_hook_reject("begin", "execjob_begin",
                               None, self.job1,
                               "In begin_reject hook", "No way Jose!")

    def test_execjob_begin_reject_del_job(self):
        """
        Test execjob_begin which rejects the event and deletes job
        """
        self.basic_hook_reject("begin", "execjob_begin",
                               None, self.job1,
                               "In begin_reject_delete hook", "No way Jose!",
                               resc_avail_file="2gb", resc_avail_ncpus=3)

    def test_execjob_begin_reject_rerun_job(self):
        """
        Test execjob_begin which rejects the event and reruns job
        """
        self.basic_hook_reject("begin", "execjob_begin",
                               None, self.job1,
                               "In begin_reject_rerun hook", "No way Jose!",
                               resc_avail_file="3gb", resc_avail_ncpus=4)

    def test_execjob_begin_with_error(self):
        """
        Test execjob_begin which returns error
        """
        self.basic_hook_error("begin", "execjob_begin",
                              None, self.job1,
                              "In begin_error hook", "No way Jose!")

    def test_execjob_begin_with_alarm(self):
        """
        Test execjob_begin with alarm interruption
        """
        self.basic_hook_alarm("begin", "execjob_begin",
                              None, self.job1,
                              "In begin_alarm hook", "No way Jose!")

    def test_execjob_prolo_accept(self):
        """
        Test execjob_prologue which accept the event
        """
        self.basic_hook_accept("prolo", "execjob_prologue",
                               None, self.job2, "In prolo hook")

    def test_execjob_prolo_del_job(self):
        """
        Test execjob_prologue with delete job
        """
        self.basic_hook_accept("prolo", "execjob_prologue",
                               None, self.job2, "In prolo_delete hook")

    def test_execjob_prolo_rerun_job(self):
        """
        Test execjob_prologue with rerun job
        """
        self.basic_hook_accept("prolo", "execjob_prologue",
                               None, self.job2,
                               "In prolo_rerun hook", "3gb", 4)

    def test_execjob_prolo_with_reject(self):
        """
        Test execjob_prologue which rejects the event
        """
        self.basic_hook_reject("prolo", "execjob_prologue",
                               None, self.job2,
                               "In prolo_reject hook", "No way Jose!")

    def test_execjob_prolo_reject_del_job(self):
        """
        Test execjob_prologue which rejects the event and deletes job
        """
        self.basic_hook_reject("prolo", "execjob_prologue",
                               None, self.job2,
                               "In prolo_reject_delete hook", "No way Jose!",
                               resc_avail_file="2gb", resc_avail_ncpus=3)

    def test_execjob_prolo_reject_rerun_job(self):
        """
        Test execjob_prologue which rejects the event and reruns job
        """
        self.basic_hook_reject("prolo", "execjob_prologue",
                               None, self.job2,
                               "In prolo_reject_rerun hook", "No way Jose!",
                               resc_avail_file="3gb", resc_avail_ncpus=4)

    def test_execjob_prolo_with_error(self):
        """
        Test execjob_begin which returns error
        """
        self.basic_hook_error("prolo", "execjob_prologue",
                              None, self.job2,
                              "In prolo_error hook", "No way Jose!")

    def test_execjob_prolo_with_alarm(self):
        """
        Test execjob_prologue with hook alarm
        """
        self.basic_hook_alarm("prolo", "execjob_prologue",
                              None, self.job2,
                              "In prolo_alarm hook", "No way Jose!")

    def test_execjob_epi_with_accept(self):
        """
        Test execjob_epilogue which accepts the event
        """
        self.basic_hook_accept("epi", "execjob_epilogue",
                               None, self.job1, "In epi hook")

    def test_execjob_epi_with_del_job(self):
        """
        Test execjob_epilogue which accepts the event and deletes job
        """

    def test_execjob_epi_with_del_job(self):
        """
        Test execjob_epilogue which accepts the event and deletes job
        """
        self.basic_hook_accept("epi", "execjob_epilogue",
                               None, self.job2,
                               "In epi_delete hook", "2gb", 3)

    def test_execjob_epi_with_rerun_job(self):
        """
        Test execjob_epilogue which accepts the event and reruns job
        """
        self.basic_hook_accept("epi", "execjob_epilogue",
                               None, self.job2,
                               "In epi_rerun hook", "3gb", 4)

    def test_execjob_epi_with_reject(self):
        """
        Test execjob_epilogue which rejects the event
        """
        self.basic_hook_reject("epi", "execjob_epilogue",
                               None, self.job4,
                               "In epi_reject hook",
                               "No way Jose!", "Exit_status=7")

    def test_execjob_epi_reject_del_job(self):
        """
        Test execjob_epilogue which rejects the event and deletes job
        """
        self.basic_hook_reject("epi", "execjob_epilogue",
                               None, self.job2,
                               "In epi_reject_delete hook", "No way Jose!",
                               resc_avail_file="2gb", resc_avail_ncpus=3)

    def test_execjob_epi_reject_rerun_job(self):
        """
        Test execjob_epilogue which rejects the event and reruns job
        """
        self.basic_hook_reject("epi", "execjob_epilogue",
                               None, self.job1,
                               "In epi_reject_rerun hook", "No way Jose!",
                               resc_avail_file="3gb", resc_avail_ncpus=4)

    def test_execjob_epi_with_error(self):
        """
        Test execjob_epilogue which returns error
        """
        self.basic_hook_error("epi", "execjob_epilogue",
                              None, self.job4,
                              "In epi_error hook", "No way Jose!",
                              "Exit_status=7")

    def test_execjob_epi_with_alarm(self):
        """
        Test execjob_epilogue with hook alarm
        """
        self.basic_hook_alarm("epi", "execjob_epilogue",
                              None, self.job1,
                              "In epi_alarm hook", "No way Jose!")

    def test_execjob_end_with_accept(self):
        """
        Test execjob_end which accepts the event
        """
        self.basic_hook_accept("end", "execjob_end",
                               None, self.job1, "In end hook")

    def test_execjob_end_with_del_job(self):
        """
        Test execjob_end which accepts the event and deletes job
        """
        self.basic_hook_accept("end", "execjob_end",
                               None, self.job2, "In end_delete hook",
                               "2gb", 3)

    def test_execjob_end_with_rerun_job(self):
        """
        Test execjob_end which accepts the event and reruns job
        """
        self.basic_hook_accept("end", "execjob_end",
                               None, self.job2, "In end_rerun hook",
                               "3gb", 4)

    def test_execjob_end_with_reject(self):
        """
        Test execjob_end which rejects the event
        """
        self.basic_hook_reject("end", "execjob_end",
                               None, self.job4, "In end_reject hook",
                               "No way Jose!")

    def test_execjob_end_reject_del_job(self):
        """
        Test execjob_end which rejects the event and deletes job
        """
        self.basic_hook_reject("end", "execjob_end",
                               None, self.job2,
                               "In end_reject_delete hook",
                               "No way Jose!",
                               resc_avail_file="2gb",
                               resc_avail_ncpus=3)

    def test_execjob_end_reject_rerun_job(self):
        """
        Test execjob_end which rejects the event and reruns job
        """
        self.basic_hook_reject("end", "execjob_end",
                               None, self.job1,
                               "In end_reject_rerun hook",
                               "No way Jose!",
                               resc_avail_file="3gb",
                               resc_avail_ncpus=4)

    def test_execjob_end_with_error(self):
        """
        Test execjob_end which returns error
        """
        self.basic_hook_error("end", "execjob_end",
                              None, self.job4,
                              "In epi_error hook",
                              "No way Jose!", "Exit_status=7")

    def test_execjob_end_with_alarm(self):
        """
        Test execjob_end with hook alarm
        """
        self.basic_hook_alarm("end", "execjob_end",
                              None, self.job1,
                              "In end_alarm hook", "No way Jose!")

    def test_execjob_preterm_with_accept(self):
        """
        Test execjob_preterm which accepts the event
        """
        self.basic_hook_accept("preterm", "execjob_preterm",
                               None, self.job1, "In preterm hook")

    def test_execjob_preterm_with_del_job(self):
        """
        Test execjob_preterm which accepts the event and deletes job
        """
        self.basic_hook_accept("preterm", "execjob_preterm",
                               None, self.job1,
                               "In preterm_delete hook", "2gb", 3)

    def test_execjob_preterm_with_rerun_job(self):
        """
        Test execjob_preterm which accepts the event and reruns job
        """
        self.basic_hook_accept("preterm", "execjob_preterm",
                               None, self.job1,
                               "In preterm_rerun hook", "3gb", 4)

    def test_execjob_preterm_with_reject(self):
        """
        Test execjob_preterm which rejects the event
        """
        self.basic_hook_reject("preterm", "execjob_preterm",
                               None, self.job4,
                               "In preterm_reject hook", "No way Jose!")

    def test_execjob_preterm_reject_del_job(self):
        """
        Test execjob_preterm which rejects the event and deletes job
        """
        self.basic_hook_reject("preterm", "execjob_preterm",
                               None, self.job1,
                               "In preterm_reject_delete hook", "No way Jose!",
                               resc_avail_file="2gb", resc_avail_ncpus=3)

    def test_execjob_preterm_reject_rerun_job(self):
        """
        Test execjob_preterm which rejects the event and reruns job
        """
        self.basic_hook_reject("preterm", "execjob_preterm",
                               None, self.job1,
                               "In preterm_reject_rerun hook", "No way Jose!",
                               resc_avail_file="3gb", resc_avail_ncpus=4)

    def test_execjob_preterm_with_error(self):
        """
        Test execjob_preterm which returns error
        """
        self.basic_hook_error("preterm", "execjob_preterm",
                              None, self.job4,
                              "In preterm_error hook",
                              "No way Jose!", "Exit_status=7")

    def test_execjob_preterm_with_alarm(self):
        """
        Test execjob_preterm with hook alarm
        """
        self.basic_hook_alarm("preterm", "execjob_preterm",
                              None, self.job4,
                              "In preterm_alarm hook",
                              "No way Jose!", "Exit_status=7")

    def test_exechost_periodic_with_accept(self):
        """
        Test exechost_periodic which accepts the event
        """
        self.basic_hook_accept_periodic("period", 5, period_py)

    def test_exechost_periodic_with_reject(self):
        """
        Test exechost_periodic which rejects the event
        """
        self.basic_hook_reject_periodic("period_reject", 30, period_reject_py)

    def test_mom_hooks_modify_resource(self):
        """
        Test for check that mom hooks can modify job resource value.
        """

        hook_rescused = """
import pbs
import os
import pwd

e = pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "Executing User=%s" % pwd.getpwuid(os.getuid())[0])

e.job.resources_used["cput"] = pbs.duration("00:07:00")
e.job.resources_used["file"] = pbs.size("3gb")
e.job.resources_used["timestamp_float"] = 3.0
"""
        r_attr = {'resources_used.file': '3gb',
                  'resources_used.timestamp_float': 3.00,
                  'resources_used.cput': '00:07:00'}

        f_attr = {'resources_used.file': '6gb',
                  'resources_used.timestamp_float': 6.00,
                  'resources_used.cput': '00:14:00'}

        self.server.manager(MGR_CMD_SET, SERVER, {'job_history_enable': True})
        attr = {ATTR_RESC_TYPE: 'float', ATTR_RESC_FLAG: 'hn'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='timestamp_float')

        hook_list = ['execjob_prologue', 'execjob_preterm',
                     'execjob_epilogue', 'execjob_end', 'execjob_begin']
        for evnt in hook_list:
            jid = self.common_steps_modify_resource(evnt, hook_rescused)

            if evnt not in ['execjob_preterm', 'execjob_epilogue',
                            'execjob_end']:
                self.server.expect(JOB, r_attr, id=jid)

            offset_val = 25
            if evnt == 'execjob_preterm':
                self.server.delete(jid)
                offset_val = 0
            self.server.expect(JOB, {'job_state': 'F'}, extend='x',
                               offset=offset_val, id=jid)

            if evnt != 'execjob_end':
                self.server.expect(JOB, f_attr, id=jid, extend='x')
            self.momA.log_match("Executing User=%s" % (ROOT_USER))
            self.momB.log_match("Executing User=%s" % (ROOT_USER))
            self.server.manager(MGR_CMD_DELETE, HOOK, id='testhook')

            err_msg = "qmgr obj=testhook svr=default: "
            err_msg += "Can't set hook user value to 'pbsuser': "
            err_msg += "hook event must contain at least "
            err_msg += "execjob_prologue,execjob_epilogue,execjob_preterm"
            exp_err = [err_msg, 'qmgr: hook error returned from server']
            f_msg = "Failed to get expected message."

            if evnt in ['execjob_begin', 'execjob_end']:
                with self.assertRaises(PbsManagerError, msg=f_msg) as e:
                    self.common_steps_modify_resource(evnt, hook_rescused,
                                                      TEST_USER)
                for msg in exp_err:
                    self.assertIn(msg, e.exception.msg)
            else:
                jid = self.common_steps_modify_resource(evnt, hook_rescused,
                                                        TEST_USER)
                if evnt not in ['execjob_preterm', 'execjob_epilogue']:
                    self.server.expect(JOB, r_attr, id=jid)

                offset_val = 25
                if evnt == 'execjob_preterm':
                    self.server.delete(jid)
                    offset_val = 0
                self.server.expect(JOB, {'job_state': 'F'}, extend='x',
                                   offset=offset_val, id=jid)
                self.momA.log_match("Executing User=%s" % (TEST_USER))
                self.momB.log_match("Executing User=%s" % (TEST_USER))
                self.server.manager(MGR_CMD_DELETE, HOOK, id='testhook')

    def test_execjob_preterm_with_suspended_job(self):
        """
        Test for execjob_preterm hook working properly with
        deletion of suspended job.
        """

        append_body = """
pbs.logmsg(pbs.LOG_DEBUG, "event is EXECJOB_PRETERM")

vn[nkey].comment = "In preterm hook"
vn[nkey].resources_available["file"] = pbs.size("1gb")
"""

        hook_body = common_hook_body + append_body
        a = {'event': 'execjob_preterm', 'enabled': True}
        self.server.create_import_hook('testhook', a, hook_body)

        jid = self.server.submit(self.job3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.sigjob(jobid=jid, signal="suspend")
        self.server.expect(JOB, {'job_state': 'S'}, id=jid)
        self.server.delete(jid, wait=True)

        exp_msg = ['Hook;pbs_python;event is EXECJOB_PRETERM',
                   'Hook;pbs_python;hook_name is testhook',
                   'Hook;pbs_python;hook_type is site',
                   'Hook;pbs_python;requestor is pbs_mom',
                   'Hook;pbs_python;requestor_host is %s' % self.hostA,
                   'Hook;pbs_python;Executing User=%s' % ROOT_USER
                   ]

        for msg in exp_msg:
            self.momA.log_match(msg)

        exp_msg[4] = 'Hook;pbs_python;requestor_host is %s' % self.hostB
        for msg in exp_msg:
            self.momB.log_match(msg)

        exp_attr = {'comment': 'In preterm hook',
                    'resources_available.file': '1gb'}
        for mom in self.moms.values():
            self.server.expect(NODE, exp_attr, id=mom.shortname)

    def test_execjob_begin_reject_on_mother_superior(self):
        """
        Test execjob_begin which rejects the event on mother_superior.
        """

        append_body = """
pbs.logmsg(pbs.LOG_DEBUG, "event is EXECJOB_BEGIN")

vn1 = pbs.server().vnode(nkey)

vn[nkey].comment = "In begin_reject hook"
vn[nkey].resources_available["file"] = pbs.size("1gb")

e.reject("No way Jose!")
"""
        hook_body = common_hook_body + append_body
        a = {'event': 'execjob_begin', 'enabled': True}
        self.server.create_import_hook('testhook', a, hook_body)

        jid = self.server.submit(self.job3)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)
        exp_msg = ["Hook;pbs_python;event is EXECJOB_BEGIN",
                   "Hook;pbs_python;hook_name is testhook",
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;requestor is pbs_mom",
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   "Hook;pbs_python;Executing User=%s" % ROOT_USER,
                   "Hook;testhook;execjob_begin request rejected by 'testhook'"
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg)

        exp_attr = {'comment': 'In begin_reject hook',
                    'resources_available.file': '1gb'}
        self.server.expect(NODE, exp_attr, id=self.momA.shortname)

        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': False})
        self.server.manager(MGR_CMD_SET, SCHED,
                            {'job_run_wait': 'execjob_hook'})
        msg = "qrun: Failed to run: No way Jose! (15169) " + jid
        f_msg = "Failed to get expected message "
        with self.assertRaises(PbsRunError, msg=f_msg+msg) as e:
            self.server.runjob(jid)
        self.assertEqual(e.exception.msg[0], msg)

    def tearDown(self):
        TestFunctional.tearDown(self)
        hooks = self.server.status(HOOK)
        for h in hooks:
            if h['id'] in ("period", "period_reject"):
                self.server.manager(MGR_CMD_DELETE, HOOK, id=h['id'])

    def customize_hook(
        self, vnode_comment, alarm=False, sister=False, exit=False,
        delete=False, rerun=False, file_size='1gb', ncpus=2,
            reject=False, error=False):

        hook_header = """import pbs
import os
import sys
import time


def print_attribs(pbs_obj):
   for a in pbs_obj.attributes:
      v = getattr(pbs_obj, a)
      if (v != None) and str(v) != "":
         pbs.logmsg(pbs.LOG_DEBUG, "%s = %s" % (a,v))

e = pbs.event()
"""
        if alarm:
            hook_header += \
                """# Configure hook's alarm to be less than 10 to force
                   # alarm exception
time.sleep(10)
"""
        if sister:
            hook_header += """ms = e.job.exec_host2.split('.')[0]

if ms and ms in pbs.get_local_nodename():
   e.accept()
"""
        hook_header += """
pbs.logmsg(pbs.LOG_DEBUG,
           "printing pbs.event() values ---------------------->")
if e.type == pbs.EXECJOB_BEGIN:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_BEGIN"))
elif e.type == pbs.EXECJOB_PROLOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PROLOGUE"))
elif e.type == pbs.EXECJOB_PRETERM:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PRETERM"))
elif e.type == pbs.EXECJOB_EPILOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_EPILOGUE"))
elif e.type == pbs.EXECJOB_END:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_END"))
elif e.type == pbs.EXECHOST_PERIODIC:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECHOST_PERIODIC"))
else:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("UNKNOWN"))


pbs.logmsg(pbs.LOG_DEBUG, "hook_name is %s" % (e.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "hook_type is %s" % (e.hook_type))
pbs.logmsg(pbs.LOG_DEBUG, "requestor is %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "requestor_host is %s" % (e.requestor_host))

pbs.logmsg(pbs.LOG_DEBUG, "printing pbs.event().job  ----------------->")
print_attribs(e.job)

pbs.logmsg(pbs.LOG_DEBUG, "Executing User=%s -------->"
           % (os.popen('whoami').read()))
"""

        if exit:
            hook_header += """
pbs.logmsg(pbs.LOG_DEBUG, "Exit_status=%d -------->" % (e.job.Exit_status)) """
        hook_header += """# Setting job attributes
e.job.Variable_List["BONJOUR"] = "Mounsieur Shlomi"
e.job.Hold_Types = pbs.hold_types("us")
e.job.Execution_Time =  time.time() + 300
# Later we get it to work with ANY resources/attributes

# extra job attributes/methods
if e.job.in_ms_mom():
        pbs.logmsg(pbs.LOG_DEBUG, "job is in_ms_mom")
else:
        pbs.logmsg(pbs.LOG_DEBUG, "job is NOT in_ms_mom")
"""

        if delete:
            hook_header += """
e.job.delete()"""
        if rerun:
            hook_header += """
e.job.rerun()"""

        hook_header += """# Getting/setting vnode_list
vn = pbs.event().vnode_list

for k in vn.keys():
   pbs.logmsg(pbs.LOG_DEBUG, "vn[%s]-------------->" % (k))
   print_attribs(vn[k])
"""
        if vnode_comment:
            hook_header += """vn[pbs.get_local_nodename()].comment = \"""" + \
                vnode_comment + "\"\n"

        hook_header += """
vn[pbs.get_local_nodename()].resources_available["file"] = pbs.size("""

        hook_header += "\"" + file_size + "\")\n"

        hook_header += \
            """vn[pbs.get_local_nodename()].resources_available["ncpus"] = """

        hook_header += str(ncpus) + "\n"

        if reject:
            hook_header += """e.reject("No way Jose!")
"""

        if error:
            hook_header += \
                """# Below is the error causing an unhandled exception
x
"""
        return hook_header


period_py = """import pbs
import os
import sys
import time

local_node = pbs.get_local_nodename()
other_node = local_node
other_node2 = "aspasia"

def print_attribs(pbs_obj):
   for a in pbs_obj.attributes:
      v = getattr(pbs_obj, a)
      if (v != None) and str(v) != "":
         pbs.logmsg(pbs.LOG_DEBUG, "%s = %s" % (a,v))

s = pbs.server()

jobs = pbs.server().jobs()
for j in jobs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found job %s" % (j.id))
   print_attribs(j)

queues = s.queues()
for q in queues:
   pbs.logmsg(pbs.LOG_DEBUG, "Found queue %s" % (q.name))
   for k in q.jobs():
     pbs.logmsg(pbs.LOG_DEBUG, "Found job %s in queue %s" % (k.id, q.name))

resvs = s.resvs()
for r in resvs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found resv %s" % (r.id))

vnodes = s.vnodes()
for v in vnodes:
   pbs.logmsg(pbs.LOG_DEBUG, "Found vnode %s" % (v.name))

e = pbs.event()

pbs.logmsg(pbs.LOG_DEBUG,
           "printing pbs.event() values ---------------------->")
if e.type == pbs.EXECJOB_BEGIN:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_BEGIN"))
elif e.type == pbs.EXECJOB_PROLOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PROLOGUE"))
elif e.type == pbs.EXECJOB_PRETERM:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PRETERM"))
elif e.type == pbs.EXECJOB_EPILOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_EPILOGUE"))
elif e.type == pbs.EXECJOB_END:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_END"))
elif e.type == pbs.EXECHOST_PERIODIC:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECHOST_PERIODIC"))
else:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("UNKNOWN"))


pbs.logmsg(pbs.LOG_DEBUG, "hook_name is %s" % (e.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "hook_type is %s" % (e.hook_type))
pbs.logmsg(pbs.LOG_DEBUG, "requestor is %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "requestor_host is %s" % (e.requestor_host))

vn = pbs.event().vnode_list

pbs.logmsg(pbs.LOG_DEBUG, "vn is %s type is %s" % (str(vn), type(vn)))
for k in pbs.event().vnode_list.keys():

   if k == local_node:
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pcpus=%d" % (k, vn[k].pcpus));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pbs_version=%s" % (k, vn[k].pbs_version));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%d" % (k,
                "ncpus", vn[k].resources_available["ncpus"]));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s type=%s" % (k,
                "mem", vn[k].resources_available["mem"],
                type(vn[k].resources_available["mem"])));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s" % (k, "arch",
                    vn[k].resources_available["arch"]));


if other_node not in vn:
   vn[other_node] = pbs.vnode(other_node)

vn[other_node].pcpus = 7
vn[other_node].ntype = pbs.ND_PBS
vn[other_node].state = pbs.ND_OFFLINE
vn[other_node].sharing = pbs.ND_FORCE_EXCL
vn[other_node].resources_available["ncpus"] = 17
vn[other_node].resources_available["file"] = pbs.size("17tb")
vn[other_node].resources_available["mem"] = pbs.size("700gb")
vn[other_node].comment = "Comment update done  by period hook "
vn[other_node].comment += "@ %s" % (local_node)

if other_node2 not in vn:
   vn[other_node2] = pbs.vnode(other_node2)

vn[other_node2].resources_available["file"] = pbs.size("500tb")
vn[other_node2].resources_available["mem"] = pbs.size("300gb")
"""

period_reject_py = """import pbs
import os
import sys
import time

local_node = pbs.get_local_nodename()
other_node = local_node
other_node2 = "aspasia"

def print_attribs(pbs_obj):
   for a in pbs_obj.attributes:
      v = getattr(pbs_obj, a)
      if (v != None) and str(v) != "":
         pbs.logmsg(pbs.LOG_DEBUG, "%s = %s" % (a,v))

s = pbs.server()
print_attribs(s)

jobs = s.jobs()
for j in jobs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found job %s" % (j.id))

queues = s.queues()
for q in queues:
   pbs.logmsg(pbs.LOG_DEBUG, "Found queue %s" % (q.name))
   for k in q.jobs():
     pbs.logmsg(pbs.LOG_DEBUG, "Found job %s in queue %s" % (k.id, q.name))

resvs = s.resvs()
for r in resvs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found resv %s" % (r.id))

vnodes = s.vnodes()
for v in vnodes:
   pbs.logmsg(pbs.LOG_DEBUG, "Found vnode %s" % (v.name))

e = pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, "printing pbs.event() values" + \
           " ---------------------->")
if e.type == pbs.EXECJOB_BEGIN:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_BEGIN"))
elif e.type == pbs.EXECJOB_PROLOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PROLOGUE"))
elif e.type == pbs.EXECJOB_PRETERM:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_PRETERM"))
elif e.type == pbs.EXECJOB_EPILOGUE:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_EPILOGUE"))
elif e.type == pbs.EXECJOB_END:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECJOB_END"))
elif e.type == pbs.EXECHOST_PERIODIC:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECHOST_PERIODIC"))
else:
   pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("UNKNOWN"))


pbs.logmsg(pbs.LOG_DEBUG, "hook_name is %s" % (e.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "hook_type is %s" % (e.hook_type))
pbs.logmsg(pbs.LOG_DEBUG, "requestor is %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "requestor_host is %s" % (e.requestor_host))

vn = pbs.event().vnode_list

pbs.logmsg(pbs.LOG_DEBUG, "vn is %s type is %s" % (vn, type(vn)))
for k in pbs.event().vnode_list.keys():

   if k == local_node:
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pcpus=%d" % (k, vn[k].pcpus));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pbs_version=%s" % (k, vn[k].pbs_version));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%d" % (k,
                "ncpus", vn[k].resources_available["ncpus"]));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s type=%s" % (k,
                "mem", vn[k].resources_available["mem"],
                type(vn[k].resources_available["mem"])));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s" % (k, "arch",
                    vn[k].resources_available["arch"]));

vn[other_node].resources_available["mem"] = pbs.size("1900gb")
vn[other_node].comment = "Comment update done  by period_reject "
vn[other_node].comment += "hook @ %s" % (local_node)

if other_node2 not in vn:
   vn[other_node2] = pbs.vnode(other_node2)

vn[other_node2].resources_available["file"] = pbs.size("500tb")
vn[other_node2].resources_available["mem"] = pbs.size("300gb")

e.reject("symbolic reject!")
"""

common_hook_body = """
import pbs
import os
import pwd

e = pbs.event()

pbs.logmsg(pbs.LOG_DEBUG, "printing pbs.event() values --->")
pbs.logmsg(pbs.LOG_DEBUG, "hook_name is %s" % (e.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "hook_type is %s" % (e.hook_type))
pbs.logmsg(pbs.LOG_DEBUG, "requestor is %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "requestor_host is %s" % (e.requestor_host))
pbs.logmsg(pbs.LOG_DEBUG, "Executing User=%s" % (pwd.getpwuid(os.getuid())[0]))

# extra job attributes/methods
if e.job.in_ms_mom():
    pbs.logmsg(pbs.LOG_DEBUG, "job is in_ms_mom")
else:
    pbs.logmsg(pbs.LOG_DEBUG, "job is NOT in_ms_mom")

# Getting/setting vnode_list
vn = pbs.event().vnode_list
local_node = pbs.get_local_nodename()

for k in vn.keys():
   if local_node in k:
       nkey = k
       break
"""
