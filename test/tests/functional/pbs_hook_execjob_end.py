# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.
from tests.functional import *
from ptl.utils.pbs_logutils import PBSLogUtils


class TestPbsExecjobEnd(TestFunctional):
    """
    This tests the feature in PBS that allows
    execjob_end hook to execute such that
    pbs_mom is not blocked upon execution.
    """
    logutils = PBSLogUtils()

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
        status = self.server.status(NODE, id=self.mom.shortname)
        if status[0]["resources_available.ncpus"] < "2":
            self.skip_test(reason="need 2 or more available ncpus")
        hook_name = "execjob_end_logmsg4"
        self.server.create_import_hook(hook_name, self.attr, self.hook_body)
        # jobs need to land on the same host even in a multi-node setup
        a = {'Resource_List.select': '1:ncpus=1:host=%s' % self.mom.shortname}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1)
        jid1 = self.server.submit(j)
        # jid1 should be in E state, in sleep of execjob_end hook for
        # jid2 submmision.
        self.server.expect(JOB, {'job_state': 'E'}, id=jid1)
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(1)
        jid2 = self.server.submit(j)
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
        for host, mom in self.moms.iteritems():
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
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.deljob(id=jid, wait=True, attr_W="force")
        for host, mom in self.moms.iteritems():
            mom.log_match("Job;%s;executed execjob_end hook" %
                          jid, n=100, max_attempts=10,
                          interval=2)
            mom.log_match("Job;%s;execjob_end hook ended" %
                          jid, n=100, max_attempts=10,
                          interval=2)
            msg = "Got expected log_msg on host:%s" % host
            self.logger.info(msg)
