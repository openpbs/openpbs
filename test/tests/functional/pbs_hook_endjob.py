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

import time

from tests.functional import *
from tests.functional import JOB, MGR_CMD_SET, SERVER, TEST_USER, ATTR_h, Job


def endjob_hook(hook_func_name):
    import pbs
    import sys

    pbs.logmsg(pbs.LOG_DEBUG, "pbs.__file__:" + pbs.__file__)

    try:
        e = pbs.event()
        job = e.job
        pbs.logjobmsg(
            job.id, 'endjob hook started for test %s' % (hook_func_name,))
        pbs.logjobmsg(job.id, 'endjob hook, job starttime:%s' % (job.stime,))
        pbs.logjobmsg(job.id, 'endjob hook, job endtime:%s' % (job.endtime,))
        # pbs.logjobmsg(job.id, 'endjob hook, job_dir=%s' % (dir(job),))
        pbs.logjobmsg(job.id, 'endjob hook, job_state=%s' % (job.job_state,))
        pbs.logjobmsg(job.id, 'endjob hook, job_substate=%s' % (job.substate,))
        state_desc = pbs.REVERSE_JOB_STATE.get(job.job_state, '(None)')
        substate_desc = pbs.REVERSE_JOB_SUBSTATE.get(job.substate, '(None)')
        pbs.logjobmsg(
            job.id, 'endjob hook, job_state_desc=%s' % (state_desc,))
        pbs.logjobmsg(
            job.id, 'endjob hook, job_substate=%s' % (substate_desc,))
        pbs.logjobmsg(job.id, 'endjob hook, job endtime:%d' % (job.endtime,))
        if hasattr(job, "resv") and job.resv:
            pbs.logjobmsg(
                job.id, 'endjob hook, resv:%s' % (job.resv.resvid,))
            pbs.logjobmsg(
                job.id,
                'endjob hook, resv_nodes:%s' % (job.resv.resv_nodes,))
            pbs.logjobmsg(
                job.id,
                'endjob hook, resv_state:%s' % (job.resv.reserve_state,))
        else:
            pbs.logjobmsg(job.id, 'endjob hook, resv:(None)')
        # pbs.logjobmsg(pbs.REVERSE_JOB_STATE.get(job.state))
        pbs.logjobmsg(
            job.id, 'endjob hook finished for test %s' % (hook_func_name,))
    except Exception as err:
        ty, _, tb = sys.exc_info()
        pbs.logmsg(
            pbs.LOG_DEBUG, str(ty) + str(tb.tb_frame.f_code.co_filename) +
            str(tb.tb_lineno))
        e.reject()
    else:
        e.accept()


@tags('hooks')
class TestHookEndJob(TestFunctional):
    node_cpu_count = 4
    job_array_num_subjobs = node_cpu_count
    job_time_success = 5
    job_time_qdel = 120
    resv_start_delay = 20
    resv_duration = job_time_qdel + 60

    node_fail_timeout = 10
    job_requeue_timeout = 1
    resv_retry_time = 5

    def run_test_func(self, test_body_func, *args, **kwargs):
        """
        Setup the environment for running end job hook related tests, execute
        the test function and then perform common checks and clean up.
        """
        self.job = None
        self.job_id = None
        self.subjob_count = 0
        self.subjob_ids = []
        self.started_job_ids = set()
        self.deleted_job_ids = set()
        self.failed_job_ids = set()
        self.resv_id = None
        self.resv_queue = None
        self.resv_start_time = None
        self.scheduling_enabled = True
        self.hook_name = test_body_func.__name__

        self.logger.info("**************** HOOK START ****************")

        a = {
            'resources_available.ncpus': self.node_cpu_count,
        }
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)

        attrs = {
            'event': 'endjob',
            'enabled': 'True',
        }
        ret = self.server.create_hook(self.hook_name, attrs)
        self.assertEqual(
            ret, True, "Could not create hook %s" % self.hook_name)

        hook_body = generate_hook_body_from_func(endjob_hook, self.hook_name)
        ret = self.server.import_hook(self.hook_name, hook_body)
        self.assertEqual(
            ret, True, "Could not import hook %s" % self.hook_name)

        a = {
            'job_history_enable': 'True',
            'job_requeue_timeout': self.job_requeue_timeout,
            'node_fail_requeue': self.node_fail_timeout,
            'reserve_retry_time': self.resv_retry_time,
        }
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.log_start_time = int(time.time())
        try:
            test_body_func(*args, **kwargs)
        finally:
            if not self.mom.isUp(max_attempts=3):
                self.mom.start()
        self.check_log_for_endjob_hook_messages()

        ret = self.server.delete_hook(self.hook_name)
        self.assertEqual(
            ret, True, "Could not delete hook %s" % self.hook_name)
        self.logger.info("**************** HOOK END ****************")

    def check_log_for_endjob_hook_messages(self):
        """
        Look for messages logged by the endjob hook.  This method assumes that
        all started jobs have been verified as terminated or forced deleted,
        thus insuring that the endjob hook has run for those jobs.
        """
        for jid in [self.job_id] + self.subjob_ids:
            msg_logged = jid in self.started_job_ids
            self.server.log_match(
                '%s;endjob hook started for test %s' % (jid, self.hook_name),
                starttime=self.log_start_time, n='ALL', max_attempts=1,
                existence=msg_logged)
            self.server.log_match(
                '%s;endjob hook, resv:%s' % (jid, self.resv_queue or "(None)"),
                starttime=self.log_start_time, n='ALL', max_attempts=1,
                existence=msg_logged)
            self.server.log_match(
                '%s;endjob hook finished for test %s' % (jid, self.hook_name),
                starttime=self.log_start_time, n='ALL', max_attempts=1,
                existence=msg_logged)
            # remove any jobs that didn't result in a log match failure from
            # the list of started and deleted jobs.  at this point, the should
            # no longer exist and thus are irrelevant in either set.
            self.started_job_ids.discard(jid)
            self.deleted_job_ids.discard(jid)
        # reset the start time so that searches on requeued jobs don't match
        # state or log messages prior to the current search.
        self.log_start_time = int(time.time())

    def job_submit(self, job_sleep_time=job_time_success, job_attrs={}):
        self.job = Job(TEST_USER, attrs=job_attrs)
        self.job.set_sleep_time(job_sleep_time)
        self.job_id = self.server.submit(self.job)

    def job_requeue(self, job_id=None, force=False):
        if self.scheduling_enabled:
            # disable scheduling so that requeued (rerun) jobs won't be
            # immediately restarted
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            self.scheduling_enabled = False
        jid = job_id or self.job_id
        extend = 'force' if force else None
        try:
            self.server.rerunjob(jid, extend=extend)
        except PbsRerunError:
            # a failed rerun should eventually result in the endjob hook being
            # run and the job being requeued
            pass

    def job_delete(self, job_id=None, force=False):
        jid = job_id or self.job_id
        extend = 'force' if force else None
        try:
            self.server.delete(jid, extend=extend)
        except PbsDeleteError:
            self.failed_job_ids.add(self.job_id)
        else:
            self.deleted_job_ids.add(jid)
            if self.subjob_count > 0:
                # if a single subjob is deleted (TERMINATED), the substate for
                # the array job is also set to TERMINATED.
                self.deleted_job_ids.add(self.job_id)

    def job_verify_queued(self, job_id=None):
        jid = job_id or self.job_id
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

    def job_verify_started(self, job_id=None):
        if not self.scheduling_enabled:
            # if scheduling was previously disabled to allow time for log
            # scraping, etc. before requeued jobs were restarted, then enabling
            # scheduling again.
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            self.scheduling_enabled = True
        jid = job_id or self.job_id
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.started_job_ids.add(jid)

    def job_verify_ended(self, job_id=None):
        jid = job_id or self.job_id
        # if the job failed, the verify that the substate is FAILED (93).  if
        # the job was deleted, then verify that the substate is set to
        # TERMINATED (91).  otherwise, verify that the substate is set to
        # FINISHED (92).
        if jid in self.failed_job_ids:
            substate = 93
        elif jid in self.deleted_job_ids:
            substate = 91
        else:
            substate = 92
        self.server.expect(
            JOB, {'job_state': 'F', 'substate': substate}, extend='x', id=jid)

    def job_array_submit(
            self,
            job_sleep_time=job_time_success,
            avail_ncpus=job_array_num_subjobs,
            subjob_count=job_array_num_subjobs,
            subjob_ncpus=1,
            job_attrs={}):
        a = {
            ATTR_J: '0-' + str(subjob_count - 1),
            'Resource_List.select': '1:ncpus=' + str(subjob_ncpus),
        }
        a.update(job_attrs)
        self.job_submit(job_sleep_time, job_attrs=a)

        self.subjob_count = subjob_count
        self.subjob_ids = [
            self.job.create_subjob_id(self.job_id, i)
            for i in range(self.subjob_count)]

    def job_array_requeue(self, force=False):
        self.job_requeue(force=force)
        # remove job array id from the list of started because a requeue
        # should not cause the endjob hook to be run for the array job.
        self.started_job_ids.discard(self.job_id)

    def job_array_delete(self, force=False):
        self.job_delete(force=force)
        # all subjobs should have been deleted
        self.deleted_job_ids = set([self.job_id]).union(self.subjob_ids)

    def job_array_verify_queued(self, first_subjob=0, num_subjobs=None):
        self.server.expect(JOB, {'job_state': 'B'}, self.job_id)
        jids = self.subjob_ids[first_subjob:num_subjobs]
        for jid in jids:
            self.job_verify_queued(job_id=jid)

    def job_array_verify_started(self, first_subjob=0, num_subjobs=None):
        self.server.expect(JOB, {'job_state': 'B'}, self.job_id)
        self.started_job_ids.add(self.job_id)
        jids = self.subjob_ids[first_subjob:num_subjobs]
        for jid in jids:
            self.job_verify_started(job_id=jid)

    def job_array_verify_ended(self, first_subjob=0, num_subjobs=None):
        for jid in [self.job_id] + self.subjob_ids[first_subjob:num_subjobs]:
            self.job_verify_ended(job_id=jid)

    def resv_submit(
            self, user, resources, start_time, end_time, place='free',
            resv_attrs={}):
        """
        helper method to submit a reservation
        """
        self.resv_start_time = start_time
        a = {
            'Resource_List.select': resources,
            'Resource_List.place': place,
            'reserve_start': start_time,
            'reserve_end': end_time,
        }
        a.update(resv_attrs)
        resv = Reservation(user, a)
        self.resv_id = self.server.submit(resv)

    def resv_verify_confirmed(self):
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=self.resv_id)
        self.resv_queue = self.resv_id.split('.')[0]
        self.server.status(RESV, 'resv_nodes')

    def resv_verify_started(self):
        self.logger.info('Sleeping until reservation starts')
        self.server.expect(
            RESV, {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
            id=self.resv_id, offset=self.resv_start_time-int(time.time()+1))

    @tags('hooks', 'smoke')
    def test_hook_endjob_run_single_job(self):
        """
        Run a single job to completion and verify that the end job hook is
        executed.
        """
        def endjob_run_single_job():
            self.job_submit()
            self.job_verify_started()
            self.job_verify_ended()

        self.run_test_func(endjob_run_single_job)

    def test_hook_endjob_run_array_job(self):
        """
        Run an array of jobs to completion and verify that the end job hook is
        executed for all subjobs and the array job.
        """
        def endjob_run_array_job():
            self.job_array_submit()
            self.job_array_verify_started()
            self.job_array_verify_ended()

        self.run_test_func(endjob_run_array_job)

    def test_hook_endjob_run_array_job_in_resv(self):
        """
        Run an array of jobs to completion within a reservation and verify
        that the end job hook is executed for all subjobs and the array job.
        """
        def endjob_run_array_job_in_resv():
            resources = '1:ncpus=' + str(self.node_cpu_count)
            start_time = int(time.time()) + self.resv_start_delay
            end_time = start_time + self.resv_duration
            self.resv_submit(TEST_USER, resources, start_time, end_time)
            self.resv_verify_confirmed()

            a = {ATTR_queue: self.resv_queue}
            self.job_array_submit(
                subjob_ncpus=int(self.node_cpu_count/2), job_attrs=a)

            self.resv_verify_started()

            self.job_array_verify_started()
            self.job_array_verify_ended()

        self.run_test_func(endjob_run_array_job_in_resv)

    def test_hook_endjob_rerun_single_job(self):
        """
        Start a single job, issue a rerun, and verify that the end job hook is
        executed for both runs.
        """
        def endjob_rerun_single_job():
            self.job_submit()
            self.job_verify_started()
            self.job_requeue()
            self.job_verify_queued()
            self.check_log_for_endjob_hook_messages()
            self.job_verify_started()
            self.job_verify_ended()

        self.run_test_func(endjob_rerun_single_job)

    def test_hook_endjob_force_rerun_single_job(self):
        """
        Start a single job, issue a force rerun, and verify that the end job
        hook is executed for both runs.
        """
        def endjob_rerun_single_job():
            self.job_submit()
            self.job_verify_started()
            self.job_requeue(force=True)
            self.job_verify_queued()
            self.check_log_for_endjob_hook_messages()
            self.job_verify_started()
            self.job_verify_ended()

        self.run_test_func(endjob_rerun_single_job)

    def test_hook_endjob_rerun_single_job_no_mom(self):
        """
        Start a single job, issue a rerun after disabling the MOM, then enable
        the MOM again, verifying that the end job hook is executed for both
        runs.
        """
        def endjob_rerun_single_job_no_mom():
            self.job_submit()
            self.job_verify_started()
            self.mom.stop()
            self.job_requeue()
            self.job_verify_queued()
            self.check_log_for_endjob_hook_messages()
            self.mom.start()
            self.job_verify_started()
            self.job_verify_ended()

        self.run_test_func(endjob_rerun_single_job_no_mom)

    def test_hook_endjob_rerun_array_job(self):
        """
        Start a array job, issue a rerun, and verify that the end job hook is
        executed for all subjob on both runs and only once for the array job.
        """
        def endjob_rerun_array_job():
            self.job_array_submit()
            self.job_array_verify_started()
            self.job_array_requeue()
            self.job_array_verify_queued()
            self.check_log_for_endjob_hook_messages()
            self.job_array_verify_started()
            self.job_array_verify_ended()

        self.run_test_func(endjob_rerun_array_job)

    def test_hook_endjob_force_rerun_array_job(self):
        """
        Start a array job, issue a force rerun, and verify that the end job
        hook is executed for all subjob on both runs and only once for the
        array job.
        """
        def endjob_rerun_array_job():
            self.job_array_submit()
            self.job_array_verify_started()
            self.job_array_requeue(force=True)
            self.job_array_verify_queued()
            self.check_log_for_endjob_hook_messages()
            self.job_array_verify_started()
            self.job_array_verify_ended()

        self.run_test_func(endjob_rerun_array_job)

    def test_hook_endjob_delete_running_single_job(self):
        """
        Run a single job, but delete before completion.  Verify that the end
        job hook is executed.
        """
        def endjob_delete_running_single_job():
            self.job_submit(job_sleep_time=self.job_time_qdel)
            self.job_verify_started()
            self.job_delete()
            self.job_verify_ended()

        self.run_test_func(endjob_delete_running_single_job)

    def test_hook_endjob_force_delete_running_single_job(self):
        """
        Run a single job, but force delete before completion.  Verify that the
        end job hook is executed.
        """
        def endjob_force_delete_running_single_job():
            self.job_submit(job_sleep_time=self.job_time_qdel)
            self.job_verify_started()
            self.job_delete(force=True)
            self.job_verify_ended()

        self.run_test_func(endjob_force_delete_running_single_job)

    def test_hook_endjob_delete_running_single_job_no_mom(self):
        """
        Run a single job, but delete before completion after disabling the MOM.
        Verify that the end job hook is executed.
        """
        def endjob_delete_running_single_job_no_mom():
            a = {ATTR_r: 'n'}
            self.job_submit(job_sleep_time=self.job_time_qdel, job_attrs=a)
            self.job_verify_started()
            self.mom.stop()
            self.job_delete()
            self.job_verify_ended()

        self.run_test_func(endjob_delete_running_single_job_no_mom)

    def test_hook_endjob_force_delete_running_single_job_no_mom(self):
        """
        Run a single job, but force delete before completion after disabling
        the MOM. Verify that the end job hook is executed.
        """
        def endjob_delete_running_single_job_no_mom():
            a = {ATTR_r: 'n'}
            self.job_submit(job_sleep_time=self.job_time_qdel, job_attrs=a)
            self.job_verify_started()
            self.mom.stop()
            self.job_delete(force=True)
            self.job_verify_ended()

        self.run_test_func(endjob_delete_running_single_job_no_mom)

    def test_hook_endjob_delete_running_array_job(self):
        """
        Run an array job, where all jobs get started but also deleted before
        completion.  Verify that the end job hook is executed for all
        subjobs and the array job.
        """
        def endjob_delete_running_array_job():
            self.job_array_submit(job_sleep_time=self.job_time_qdel)
            self.job_array_verify_started()
            self.job_array_delete()
            self.job_array_verify_ended()

        self.run_test_func(endjob_delete_running_array_job)

    def test_hook_endjob_delete_partial_running_array_job(self):
        """
        Run an array job, where on the first two jobs get started but also
        deleted before completion.  Verify that the end job hook is executed
        for the started subjobs and the array job.
        """
        def endjob_delete_partial_running_array_job():
            self.job_array_submit(
                subjob_count=6,
                job_sleep_time=self.job_time_qdel,
                subjob_ncpus=int(self.node_cpu_count/2))
            self.job_array_verify_started(num_subjobs=2)
            self.job_array_delete()
            self.job_array_verify_ended()

        self.run_test_func(endjob_delete_partial_running_array_job)

    def test_hook_endjob_delete_subjobs_from_running_array_job(self):
        """
        By creating an import hook, it executes a job hook.
        """
        def endjob_delete_subjobs_from_running_array_job():
            self.job_array_submit(job_sleep_time=self.job_time_qdel)
            self.job_array_verify_started()
            for jid in self.subjob_ids[0:1]:
                self.job_delete(jid)
            self.job_array_verify_ended()

        self.run_test_func(endjob_delete_subjobs_from_running_array_job)

    def test_hook_endjob_delete_unstarted_single_job(self):
        # TODO: add code and description, or remove
        pass

    def test_hook_endjob_delete_unstarted_array_job(self):
        # TODO: add code and description, or remove
        pass

    def test_hook_endjob_force_delete_array_job(self):
        # TODO: write code
        pass
