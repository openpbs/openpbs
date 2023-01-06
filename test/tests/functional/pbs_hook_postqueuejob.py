# coding: utf-8

# Copyright (C) 1994-2022 Altair Engineering, Inc.
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


from tests.functional import *

hook_body = """
import pbs

hook_events = ['queuejob', 'postqueuejob', 'runjob']
hook_event = {}

for he in hook_events:
    if hasattr(pbs, he.upper()):
        event_code = eval('pbs.'+he.upper())
        hook_event[event_code] = he
        hook_event[he] = event_code
        hook_event[he.upper()] = event_code
        del event_code
    else:
        del hook_events[hook_events.index(he)]


pbs_event = pbs.event()
job = pbs_event.job

pbs.logmsg(pbs.LOG_DEBUG, "Starting... %s" % (hook_event[pbs_event.type]))
if hook_event[pbs_event.type] == "postqueuejob":
    myjob = pbs.server().job(job.id)
    pbs.logmsg(pbs.LOG_DEBUG, "my jobid=> %s" % (myjob.id))
    pbs.logmsg(pbs.LOG_DEBUG, "my job queue=> %s" % (myjob.queue))


pbs.logmsg(pbs.LOG_DEBUG, "hook name=> %s" % (pbs_event.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "Ending... %s" % (hook_event[pbs_event.type]))

pbs_event.accept()
"""


@tags('hooks')
class TestHookPostQueueJob(TestFunctional):
    """
    This test suite is to test the postqueuejob hook event
    """

    def test_postqueuejob_hook_single_job(self):
        """
        Verify postqueuejob is running
        """

        hook_name = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid)
        self.server.log_match("Ending... postqueuejob")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_postqueuejob_hook_multiple_job(self):
        """
        Verify postqueuejob hook with multiple jobs
        """

        hook_name = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid1 = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid1)
        self.server.log_match("Ending... postqueuejob")
        jid2 = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid2)
        self.server.log_match("Ending... postqueuejob")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

    def test_postqueuejob_hook_multiple_hooks(self):
        """
        Verify postqueuejob event with multiple hooks
        """

        hook_name1 = "postqueuejob_hook1"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name1, attr, hook_body)

        hook_name2 = "postqueuejob_hook2"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name2, attr, hook_body)

        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid1 = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid1)
        self.server.log_match("hook name=> %s" % (hook_name1))
        self.server.log_match("hook name=> %s" % (hook_name2))
        self.server.log_match("Ending... postqueuejob")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

    def test_postqueuejob_hook_multiple_hooks_muliple_jobs(self):
        """
        Verify multiple postqueuejob hooks with multiple jobs
        """

        hook_name1 = "postqueuejob_hook1"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name1, attr, hook_body)

        hook_name2 = "postqueuejob_hook2"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_name2, attr, hook_body)

        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid1 = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid1)
        self.server.log_match("hook name=> %s" % (hook_name1))
        self.server.log_match("hook name=> %s" % (hook_name2))
        self.server.log_match("Ending... postqueuejob")
        jid2 = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid2)
        self.server.log_match("Ending... postqueuejob")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

    def test_queuejob_with_postqueuejob_hook(self):
        """
        Test postqueuejob hook along with queuejob hook
        """

        hook_queuejob = "queuejob_hook"
        attr = {'event': 'queuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_queuejob, attr, hook_body)

        hook_postqueuejob = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_postqueuejob, attr, hook_body)

        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid1 = self.server.submit(j)

        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("hook name=> %s" % (hook_queuejob))
        self.server.log_match("Ending... postqueuejob")

        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my jobid=> %s" % jid1)
        self.server.log_match("hook name=> %s" % (hook_postqueuejob))
        self.server.log_match("Ending... postqueuejob")

    def test_postqueuejob_hook_reject(self):
        """
        Test postqueuejob reject event
        """

        reject_hook_script = """
import pbs
pbs.event().reject("postqueuejob hook rejected the job")
"""
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        hook_postqueuejob = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True'}
        self.server.create_import_hook(
            hook_postqueuejob, attr, reject_hook_script)
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.log_match("postqueuejob hook rejected the job")

    def test_postqueuejob_hook_with_route_queue(self):
        """
        Verify that a routing queue routes a job into the appropriate
        execution queue and postqueuejob hook is executed all the
        time.
        """

        hook_queuejob = "queuejob_hook"
        attr = {'event': 'queuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_queuejob, attr, hook_body)

        hook_postqueuejob = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_postqueuejob, attr, hook_body)

        a = {'queue_type': 'Execution', 'resources_min.ncpus': 1,
             'enabled': 'True', 'started': 'False'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='specialq')
        dflt_q = self.server.default_queue
        a = {'queue_type': 'route',
             'route_destinations': dflt_q + ',specialq',
             'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='routeq')
        a = {'resources_min.ncpus': 4}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id=dflt_q)
        j = Job(TEST_USER, attrs={ATTR_queue: 'routeq',
                                  'Resource_List.ncpus': 1})
        jid = self.server.submit(j)
        self.server.log_match("my job queue=> %s" % 'routeq')
        self.server.expect(JOB, {ATTR_queue: 'specialq'}, id=jid)
        self.server.log_match("my job queue=> %s" % 'specialq')

    def test_postqueuejob_hook_with_movejob(self):
        """
        Verify that a job can be moved to another queue than the one it was
        originally submitted to and postqueuejob hook is executed
        """

        hook_postqueuejob = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}
        self.server.create_import_hook(hook_postqueuejob, attr, hook_body)

        a = {'queue_type': 'Execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='solverq')
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my job queue=> %s" % 'workq')
        self.server.log_match("Ending... postqueuejob")
        self.server.movejob(jid, 'solverq')
        self.server.log_match("Starting... postqueuejob")
        self.server.log_match("my job queue=> %s" % 'solverq')
        self.server.log_match("Ending... postqueuejob")
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.server.expect(JOB, {ATTR_queue: 'solverq', 'job_state': 'R'},
                           attrop=PTL_AND)

    def create_hook_and_submit_job(self, hook_script):
        """
        Helper function to create hook and submit job
        """

        hook_postqueuejob = "postqueuejob_hook"
        attr = {'event': 'postqueuejob', 'enabled': 'True', 'alarm': '50'}

        self.server.create_import_hook(hook_postqueuejob, attr, hook_script)
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        j_status = self.server.status(JOB, id=jid)[0]
        return j_status

    def test_altering_job_attribute_in_accepted_hook(self):
        """
        Verify the postqueuejob hook can update the job attribute
        (Resource_List.ncpus, Project) when hook is accepted.
        """

        req_ncpus = '2'
        req_project = 'ptl_test'
        hook_script = """
import pbs
event = pbs.event()
job = event.job
job.Resource_List["ncpus"] = %s
job.project= "%s"
event.accept()
"""
        j_status = self.create_hook_and_submit_job(
            hook_script % (req_ncpus, req_project))
        job_ncpus = j_status['Resource_List.ncpus']
        job_project = j_status['project']
        self.assertEqual(
            req_ncpus,
            job_ncpus,
            "Requested ncpus is not updated after postqueuejob "
            "hook run")
        self.assertEqual(
            req_project,
            job_project,
            "Requested project is not updated after postqueuejob "
            "hook run")

    def test_altering_job_attribute_in_rejected_hook(self):
        """
        Verify the postqueuejob hook can not update the job attribute
        (Resource_List.ncpus, Project) when hook is rejected.
        """

        req_ncpus = '2'
        req_project = 'ptl_test'
        hook_script = """
import pbs
event = pbs.event()
job = event.job
job.Resource_List["ncpus"] = %s
job.project=%s
event.reject()
"""
        j_status = self.create_hook_and_submit_job(
            hook_script % (req_ncpus, req_project))
        job_ncpus = j_status['Resource_List.ncpus']
        job_project = j_status['project']
        self.assertNotEqual(
            req_ncpus,
            job_ncpus,
            "Requested ncpus is same as job's ncpus")
        self.assertNotEqual(
            req_project,
            job_project,
            "Requested project is same as job's project")

    def test_setting_job_readonly_attr(self):
        """
        Verify postqueuejob hook can not set job's readonly attribute
        """
        req_substate = '50'
        hook_script = """
import pbs
event = pbs.event()
job = event.job
job.substate=%s
event.accept()
"""
        j_status = self.create_hook_and_submit_job(
            hook_script % (req_substate))
        log_msg = "PBS server internal error (15011) in Error " \
            "evaluating Python script, job attribute 'substate' is " \
            "readonly"
        self.server.log_match(log_msg)
        job_substate = j_status['substate']
        self.assertNotEqual(
            req_substate,
            job_substate,
            "Requested substate is not updated after postqueuejob "
            "hook run")

    def test_postqueuejob_in_list_hook(self):
        """
        Set a hook event to queuejob and postqueuejob
        and test if it is listed successfully in qmgr
        """

        hook_name = "myhook"
        a = {'event': 'queuejob,postqueuejob', 'enabled': 'True'}
        self.server.create_hook(hook_name, a)
        attrs = {'event': 'queuejob,postqueuejob'}
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)
