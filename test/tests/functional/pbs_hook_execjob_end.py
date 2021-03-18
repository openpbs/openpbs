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

import textwrap

from ptl.utils.pbs_logutils import PBSLogUtils
from tests.functional import *


def get_hook_body(sleep_time):
    """
    method to return hook body
    :param sleep_time: sleep time added in the hook
    :type sleep_time: int
    """
    hook_body = """
    import pbs
    import time
    e = pbs.event()

    if e.type == pbs.EXECJOB_EPILOGUE:
        hook_type = "EXECJOB_EPILOGUE"
    elif e.type == pbs.EXECJOB_END:
        hook_type = "EXECJOB_END"
    pbs.logjobmsg(e.job.id, "starting hook event " + hook_type)
    time.sleep(%s)
    pbs.logjobmsg(e.job.id, "ending hook event " + hook_type)
    """ % sleep_time
    hook_body = textwrap.dedent(hook_body)
    return hook_body


class TestPbsExecjobEnd(TestFunctional):
    """
    This tests the feature in PBS that allows
    execjob_end hook to execute such that
    pbs_mom is not blocked upon execution.
    """
    logutils = PBSLogUtils()
    job_list = []

    def setUp(self):
        TestFunctional.setUp(self)
        self.attr = {'event': 'execjob_end', 'enabled': 'True', 'alarm': '50'}
        self.hook_body = ("import pbs\n"
                          "import time\n"
                          "e = pbs.event()\n"
                          "pbs.logjobmsg(e.job.id, \
                                         'executed execjob_end hook')\n"
                          "time.sleep(10)\n"
                          "pbs.logjobmsg(e.job.id, \
                                         'execjob_end hook ended')\n"
                          "e.accept()\n")

    def test_execjob_end_non_blocking(self):
        """
        Test to make sure that mom is unblocked and running
        exechost_periodic hook while it's child process is executing
        execjob_end hook.
        """
        hook_name = "execjob_end_logmsg"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)
        hook_name = "exechost_periodic_logmsg"
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "pbs.logmsg(pbs.LOG_DEBUG, \
                                 'executed exechost_periodic hook')\n"
                     "e.accept()\n")
        attr = {'event': 'exechost_periodic', 'freq': '3', 'enabled': 'True'}
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        self.server.create_import_hook(hook_name, attr, hook_body)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        # need to verify hook messages in the below mentioned order to
        # confirm mom is not blocked on execjob_end hook execution.
        # The order is verified with the use of starttime and endtime
        # parameters.
        (_, str1) = self.mom.log_match("Job;%s;executed execjob_end hook" %
                                       jid, n=100, max_attempts=10, interval=2)
        date_time1 = str1.split(";")[0]
        epoch1 = self.logutils.convert_date_time(date_time1)
        # following message should be logged while execjob_end hook is in sleep
        (_, str1) = self.mom.log_match("executed exechost_periodic hook",
                                       starttime=epoch1 - 1,
                                       endtime=epoch1 + 10,
                                       n=100, max_attempts=10, interval=1)
        date_time2 = str1.split(";")[0]
        epoch2 = self.logutils.convert_date_time(date_time2)
        (_, str1) = self.mom.log_match(
            "Job;%s;execjob_end hook ended" %
            jid, starttime=epoch2 - 1, n=100,
            max_attempts=10, interval=2)
        date_time3 = str1.split(";")[0]
        self.logger.info(
            "execjob_end hook executed at: %s,"
            "exechost_periodic at: %s and execjob_end hook ended at: %s" %
            (date_time1, date_time2, date_time3))

    def test_execjob_end_hook_order_and_reject(self):
        """
        Test with multiple execjob_end hooks having different order
        with one of the hooks rejecting the job.
        """
        hook_name1 = "execjob_end_logmsg1"
        hook_body_accept = ("import pbs\n"
                            "e = pbs.event()\n"
                            "pbs.logjobmsg(e.job.id, \
                                  'executed %s hook' % e.hook_name)\n"
                            "e.accept()\n")
        attr = {'event': 'execjob_end', 'order': '1', 'enabled': 'True'}
        self.server.create_import_hook(hook_name1, attr, hook_body_accept)
        hook_name = "execjob_end_logmsg2"
        hook_body_reject = (
            "import pbs\n"
            "e = pbs.event()\n"
            "pbs.logjobmsg(e.job.id, 'executed execjob_end hook')\n"
            "e.reject('Job is rejected')\n")
        attr = {'event': 'execjob_end', 'order': '2', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body_reject)
        hook_name2 = "execjob_end_logmsg3"
        attr = {'event': 'execjob_end', 'order': '170', 'enabled': 'True'}
        self.server.create_import_hook(hook_name2, attr, hook_body_accept)
        j = Job(TEST_USER)
        j.set_sleep_time(1)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        self.mom.log_match("Job;%s;executed %s hook" % (jid, hook_name1),
                           n=100, max_attempts=10, interval=2)
        self.mom.log_match("Job;%s;Job is rejected" % jid,
                           n=100, max_attempts=10, interval=2)
        self.mom.log_match("Job;%s;executed %s hook" % (jid, hook_name2),
                           n=100, max_attempts=10, interval=2, existence=False)

    def test_execjob_end_multi_job(self):
        """
        Test to make sure that mom is unblocked with
        execjob_end hook with mutiple jobs
        """
        if self.mom.is_cpuset_mom():
            status = self.server.status(NODE,
                                        id=self.server.status(NODE)[1]['id'])
            if status[0]["resources_available.ncpus"] < "2":
                self.skip_test(reason="need 2 or more available ncpus")
        else:
            a = {'resources_available.ncpus': 2}
            self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        hook_name = "execjob_end_logmsg4"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)
        # jobs need to land on the same host even in a multi-node setup
        a = {'Resource_List.select': '1:ncpus=1:host=%s' % self.mom.shortname}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1)
        jid1 = self.server.submit(j)
        self.job_list.append(jid1)
        # jid1 should be in E state, in sleep of execjob_end hook for
        # jid2 submmision.
        self.server.expect(JOB, {'job_state': 'E'}, id=jid1)
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1)
        jid2 = self.server.submit(j)
        self.job_list.append(jid2)
        # hook message of jid2 should be logged after the message of jid1 and
        # before completion of sleep in hook for jid1 inorder to prove mom
        # is not in blocked state.
        (_, str1) = self.mom.log_match("Job;%s;executed execjob_end hook" %
                                       jid1, n=100, max_attempts=10,
                                       interval=2)
        date_time1 = str1.split(";")[0]
        epoch1 = self.logutils.convert_date_time(date_time1)
        # hook message for jid2 should appear while hook is in sleep for jid1
        (_, str1) = self.mom.log_match("Job;%s;executed execjob_end hook" %
                                       jid2, starttime=epoch1 - 1,
                                       endtime=epoch1 + 10,
                                       n=100, max_attempts=10, interval=1)
        date_time1 = str1.split(";")[0]
        epoch1 = self.logutils.convert_date_time(date_time1)
        (_, str1) = self.mom.log_match("Job;%s;execjob_end hook ended" % jid1,
                                       starttime=epoch1 - 1,
                                       n=100, max_attempts=10, interval=2)
        self.mom.log_match("Job;%s;execjob_end hook ended" % jid2,
                           n=100, max_attempts=10, interval=2)

    @requirements(num_moms=2)
    def test_execjob_end_non_blocking_multi_node(self):
        """
        Test to make sure sister mom is unblocked
        when execjob_end hook is running on sister mom
        """
        if len(self.moms) != 2:
            self.skip_test(reason="need 2 mom hosts: -p moms=<m1>:<m2>")
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        hook_name = "execjob_end_logmsg5"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)
        hook_name = "exechost_periodic_logmsg2"
        hook_body = ("import pbs\n"
                     "e = pbs.event()\n"
                     "pbs.logmsg(pbs.LOG_DEBUG, \
                                 'executed exechost_periodic hook')\n"
                     "e.accept()\n")
        attr = {'event': 'exechost_periodic', 'freq': '3', 'enabled': 'True'}
        a = {'Resource_List.select': '1:ncpus=1:host=%s+1:ncpus=1:host=%s' %
             (self.momA.shortname, self.momB.shortname)}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1)
        self.server.create_import_hook(hook_name, attr, hook_body)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        for host, mom in self.moms.items():
            (_, str1) = mom.log_match("Job;%s;executed execjob_end hook" %
                                      jid, n=100, max_attempts=10,
                                      interval=2)
            date_time1 = str1.split(";")[0]
            epoch1 = self.logutils.convert_date_time(date_time1)
            (_, str1) = mom.log_match("executed exechost_periodic hook",
                                      starttime=epoch1 - 1,
                                      endtime=epoch1 + 10,
                                      n=100, max_attempts=10, interval=1)
            date_time2 = str1.split(";")[0]
            epoch2 = self.logutils.convert_date_time(date_time2)
            (_, str1) = mom.log_match(
                "Job;%s;execjob_end hook ended" %
                jid, starttime=epoch2 - 1, n=100,
                max_attempts=10, interval=2)
            date_time3 = str1.split(";")[0]
            msg = "Got expected log_msg on host:%s" % host
            self.logger.info(msg)
            self.logger.info(
                "execjob_end hook executed at: %s,"
                "exechost_periodic at: %s and execjob_end hook ended at: %s" %
                (date_time1, date_time2, date_time3))

    @requirements(num_moms=2)
    def test_execjob_end_delete_request(self):
        """
        Test to make sure execjob_end hook is running
        after job force deletion request(IS_DISCARD_JOB) when
        mom is unblocked.
        """
        hook_name = "execjob_end_logmsg6"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)
        if len(self.moms) == 2:
            self.momA = self.moms.values()[0]
            self.momB = self.moms.values()[1]
            a = {'Resource_List.select':
                 '1:ncpus=1:host=%s+1:ncpus=1:host=%s' %
                 (self.momA.shortname, self.momB.shortname)}
            j = Job(TEST_USER, attrs=a)
        elif len(self.moms) == 1:
            j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.deljob(id=jid, wait=True, attr_W="force")
        for host, mom in self.moms.items():
            mom.log_match("Job;%s;executed execjob_end hook" %
                          jid, n=100, max_attempts=10,
                          interval=2)
            mom.log_match("Job;%s;execjob_end hook ended" %
                          jid, n=100, max_attempts=10,
                          interval=2)
            msg = "Got expected log_msg on host:%s" % host
            self.logger.info(msg)

    @requirements(num_moms=2)
    def test_execjob_end_reject_request(self):
        """
        Test to make sure hook job reject message should appear in mom log
        in case sister mom went down before executing execjob_end hook
        """

        if len(self.moms) != 2:
            self.skip_test(reason="need 2 mom hosts: -p moms=<m1>:<m2>")
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]

        # Create hook
        hook_name = "execjob_end_logmsg7"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)

        # Submit a multi-node job
        a = {'Resource_List.select':
             '1:ncpus=1:host=%s+1:ncpus=1:host=%s' %
             (self.momA.shortname, self.momB.shortname)}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(60)
        jid = self.server.submit(j)
        self.job_list.append(jid)

        # Verify job spawn on sisterm mom
        self.momB.log_match("Job;%s;JOIN_JOB as node" % jid, n=100,
                            max_attempts=10, interval=2)

        # When the job run approx 5 sec, bring sister mom down
        self.server.expect(JOB, {'job_state': 'R'}, id=jid, offset=5)
        msg = 'mom is not down'
        self.assertTrue(self.momB.stop(), msg)

        # Verify momB is down and job is running
        a = {'state': (MATCH_RE, "down")}
        self.server.expect(
            NODE, a, id=self.momB.shortname)
        self.server.expect(JOB, {'job_state': "R"}, id=jid)

        hook_execution_time = time.time()
        self.server.expect(JOB, {'job_state': "E"}, id=jid, max_attempts=300)

        # Following message should be logged on momA after job delete request
        # received
        msg = "%s;Unable to send delete job request to one or more" % jid
        msg += " sisters"

        self.momA.log_match(msg, interval=2, starttime=hook_execution_time)

        # Following message should be logged on momA while execjob_end hook is
        # in sleep
        self.momA.log_match("Job;%s;executed execjob_end hook" % jid,
                            starttime=hook_execution_time, max_attempts=10,
                            interval=2)

        self.momA.log_match("Job;%s;execjob_end hook ended" % jid,
                            starttime=hook_execution_time, max_attempts=10,
                            interval=2)

        # Verify  reject reply code 15059 for hook job logged in mother
        # superior(momA)
        self.momA.log_match("Req;req_reject;Reject reply code=15059,",
                            starttime=hook_execution_time, max_attempts=10,
                            interval=2)

        # Start pbs on MomA
        self.server.pi.restart(hostname=self.server.hostname)
        # Verify mother superior is not down
        self.assertTrue(self.momA.isUp())

        # Start pbs on MomB
        self.momB.start()
        # Verify sister mom is not down
        self.assertTrue(self.momB.isUp())

    def test_rerun_on_epilogue_hook(self):
        """
        Test force qrerun when epilogue hook is running
        """

        hook_name = "epiend_hook"
        hook_body = get_hook_body(5)
        attr = {'event': 'execjob_epilogue,execjob_end', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        self.mom.log_match("starting hook event EXECJOB_EPILOGUE")
        # Force rerun job
        self.server.rerunjob(jid, extend='force')
        self.mom.log_match("starting hook event EXECJOB_END")
        self.server.expect(JOB, {'job_state': 'R'}, jid)
        self.mom.log_match("ending hook event EXECJOB_END")

    def common_steps(self, jid, host):
        """
        Function to run common steps for test job on mom breakdown
        and restarts
        """

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        host.signal('-KILL')
        self.logger.info(
            "Successfully killed mom process on %s" %
            host.shortname)

        # set scheduling false
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        # check for the job's state after the node_fail_requeue time hits
        self.logger.info("Waiting for 30s so that node_fail_requeue time hits")
        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid, offset=30)

        host.start()
        self.logger.info(
            "Successfully started mom process on %s" %
            host.shortname)
        self.server.expect(NODE, {'state': 'free'}, id=host.shortname)

        self.server.expect(JOB, {ATTR_state: 'Q'}, id=jid)
        # run job
        try:
            now = time.time()
            # qrun will fail as it is discarding the job
            self.server.runjob(jid)
        except PbsRunError as e:
            self.logger.info("Runjob throws error: " + e.msg[0])
            self.assertTrue(
                'qrun: Request invalid for state of job'
                in e.msg[0])
            self.mom.log_match("ending hook event EXECJOB_END",
                               starttime=now, interval=2)
            time.sleep(5)
            self.server.runjob(jid)
            self.server.expect(JOB, {'job_state': 'R'}, jid)
            now = time.time()
            self.mom.log_match(
                "starting hook event EXECJOB_END",
                starttime=now, interval=2)
            time.sleep(5)
            self.mom.log_match("ending hook event EXECJOB_END",
                               starttime=now, interval=2)

    def test_qrun_on_mom_breakdown(self):
        """
        Test qrun when mom breaksdown and restarts
        """

        hook_name = "end_hook"
        hook_body = get_hook_body(5)
        attr = {'event': 'execjob_end', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        attrib = {ATTR_nodefailrq: 30}
        self.server.manager(MGR_CMD_SET, SERVER, attrib=attrib)
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        self.common_steps(jid, self.mom)

    def test_qrun_arrayjob_on_mom_breakdown(self):
        """
        Test qrun array job when mom breaksdown and restarts
        """

        hook_name = "end_hook"
        hook_body = get_hook_body(5)
        attr = {'event': 'execjob_end', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        attrib = {ATTR_nodefailrq: 30}
        self.server.manager(MGR_CMD_SET, SERVER, attrib=attrib)
        j = Job(TEST_USER, attrs={
            ATTR_J: '1-2', ATTR_k: 'oe',
            'Resource_List.select': 'ncpus=1'
        })
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        # check job array has begun
        self.server.expect(JOB, {'job_state': 'B'}, jid)
        subjid_1 = j.create_subjob_id(jid, 1)
        self.common_steps(subjid_1, self.mom)

    def test_mom_restart(self):
        """
        Test to restart mom while execjob_end hook is running
        """
        hook_name = "end_hook"
        hook_body = get_hook_body(20)
        attr = {'event': 'execjob_end', 'enabled': 'True', 'alarm': '40'}
        self.server.create_import_hook(hook_name, attr, hook_body)
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.job_list.append(jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.mom.log_match("Job;%s;starting hook event EXECJOB_END" %
                           jid, n=100, interval=2)
        self.mom.restart()
        self.mom.log_match("Job;%s;ending hook event EXECJOB_END" %
                           jid, n=100, interval=2)
        self.server.log_match(jid + ";Exit_status=0", interval=4)

    def tearDown(self):
        for mom_val in self.moms.values():
            if mom_val.is_cpuset_mom():
                mom_val.restart()
        self.job_list.clear()
