# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class TestRunJobHook(TestFunctional):
    """
    This test suite tests the runjob hook
    """
    index_hook_script = """
import pbs
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG, "job_id=%s" % j.id)
pbs.logmsg(pbs.LOG_DEBUG, "sub_job_array_index=%s"
           % j.array_index)
e.accept()
"""

    reject_hook_script = """
import pbs
pbs.event().reject("runjob hook rejected the job")
"""

    new_res_in_hook_script = """
import pbs
e = pbs.event()
e.job.Resource_List['site'] = 'site_value'
"""

    rerun_hook_script = """
import pbs
e = pbs.event()
j = e.job
if not j.run_version is None:
    pbs.logmsg(pbs.LOG_DEBUG,
        "rerun_job_hook %s(%s): Resource_List.foo_str=%s" %
        (j.id,j.run_version,j.Resource_List['foo_str']))
else:
    j.Resource_List['foo_str'] = "foo_value"
"""

    def test_array_sub_job_index(self):
        """
        Submit a job array. Check the array sub-job index value
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.index_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        lower = 1
        upper = 3
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        self.server.submit(j1)
        for i in range(lower, upper + 1):
            self.server.log_match("sub_job_array_index=%d" % (i),
                                  starttime=self.server.ctime)

    def test_array_sub_new_res_in_hook(self):
        """
        Insert site resource in runjob hook. Submit a job array.
        Check if site resource set for all subjobs
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.new_res_in_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        lower = 1
        upper = 3
        j1 = Job(TEST_USER)
        j1.set_sleep_time(3)
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        jid = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        time.sleep(5)
        self.server.expect(JOB, ATTR_state, op=UNSET, id=jid)
        for i in range(lower, upper + 1):
            sid = j1.create_subjob_id(jid, i)
            m = "'runjob_hook' hook set job's Resource_List.site = site_value"
            self.server.tracejob_match(m, id=sid, n='ALL', tail=False)
            m = 'E;' + re.escape(sid) + ';.*Resource_List.site=site_value'
            self.server.accounting_match(m, regexp=True)

    def test_array_sub_res_persist_in_hook_forcereque(self):
        """
        set custom resource in runjob hook. Submit a job array.
        Check if custom resource set persists after force requeue due to
        node fail requeue
        """
        # configure node fail requeue to lower value
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'node_fail_requeue': 5})
        # set three cpu for three subjobs
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        # create custom non-consumable string server resource
        attr = {'type': 'string'}
        r = 'foo_str'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, logerr=False)
        # create and import hook
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.rerun_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        # create and submit job array
        lower = 1
        upper = 3
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        jid = self.server.submit(j1)
        # check if running
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})
        # kill mom
        self.mom.stop('-KILL')
        m = "'runjob_hook' hook set job's Resource_List.foo_str = foo_value"
        sid = {}
        for i in range(lower, upper + 1):
            sid[i] = j1.create_subjob_id(jid, i)
            self.server.tracejob_match(m, id=sid[i], n='ALL', tail=False)
        # check subjob state change from R->Q
        self.server.expect(JOB, {'job_state=Q': 3}, count=True,
                           id=jid, extend='t')
        # bring back mom
        self.mom.start()
        start_time = int(time.time())
        self.mom.isUp()
        # let subjobs get rerun from sched Q->R
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')
        # log match from hook log for custom res value
        m = "rerun_job_hook %s(1): Resource_List.foo_str=foo_value"
        for i in range(lower, upper + 1):
            self.server.log_match(m % (sid[i]), start_time)

    def test_array_sub_res_persist_in_hook_qrerun(self):
        """
        set custom resource in runjob hook. Submit a job array.
        Check if custom resource set persists after a qrerun
        """
        # set three cpu for three subjobs
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        # create custom non-consumable string server resource
        attr = {'type': 'string'}
        r = 'foo_str'
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id=r, logerr=False)
        # create and import hook
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.rerun_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        # create and submit job array
        lower = 1
        upper = 3
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
        jid = self.server.submit(j1)
        # check if running
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')
        m = "'runjob_hook' hook set job's Resource_List.foo_str = foo_value"
        sid = {}
        for i in range(lower, upper + 1):
            sid[i] = j1.create_subjob_id(jid, i)
            self.server.tracejob_match(m, id=sid[i], n='ALL', tail=False)
        start_time = int(time.time())
        # rerun the array job
        self.server.rerunjob(jobid=jid, runas=ROOT_USER)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')
        # log match from hook log for custom res value
        m = "rerun_job_hook %s(1): Resource_List.foo_str=foo_value"
        for i in range(lower, upper + 1):
            self.server.log_match(m % (sid[i]), start_time)
        start_time = int(time.time())
        # rerun a single subjob
        self.server.rerunjob(jobid=sid[2], runas=ROOT_USER)
        self.server.expect(JOB, {'job_state': 'R'}, id=sid[2])
        # log match from hook log for custom res value
        m = "rerun_job_hook %s(2): Resource_List.foo_str=foo_value"
        self.server.log_match(m % (sid[2]), start_time)

    def test_normal_job_index(self):
        """
        Submit a normal job. Check the job index value which should be None
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.index_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        j1 = Job(TEST_USER)
        self.server.submit(j1)
        self.server.log_match("sub_job_array_index=None",
                              starttime=self.server.ctime)

    def test_reject_array_sub_job(self):
        """
        Test to check array subjobs,
        jobs should run after runjob hook enabled set to false.
        """
        hook_name = "runjob_hook"
        attrs = {'event': "runjob"}
        rv = self.server.create_import_hook(hook_name, attrs,
                                            self.reject_hook_script,
                                            overwrite=True)
        self.assertTrue(rv)
        a = {'resources_available.ncpus': 3}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j1 = Job(TEST_USER)
        j1.set_attributes({ATTR_J: '1-3'})
        jid = self.server.submit(j1)
        msg = "Not Running: PBS Error: runjob hook rejected the job"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': msg}, id=jid)
        a = {'enabled': 'false'}
        self.server.manager(MGR_CMD_SET, HOOK, a, id=hook_name, sudo=True)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'B'}, id=jid)
        self.server.expect(JOB, {'job_state=R': 3}, count=True,
                           id=jid, extend='t')
