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


def jobobit_hook():
    import pbs
    import sys

    try:
        e = pbs.event()
        job = e.job
        pbs.logjobmsg(
            job.id, 'jobobit hook started for test %s' % (e.hook_name,))
        pbs.logjobmsg(job.id, 'jobobit hook, job starttime:%s' % (job.stime,))
        pbs.logjobmsg(
            job.id, 'jobobit hook, job obittime:%s' % (job.obittime,))
        pbs.logjobmsg(job.id, 'jobobit hook, job_state=%s' % (job.job_state,))
        pbs.logjobmsg(
            job.id, 'jobobit hook, job_substate=%s' % (job.substate,))
        state_desc = pbs.REVERSE_JOB_STATE.get(job.job_state, '(None)')
        substate_desc = pbs.REVERSE_JOB_SUBSTATE.get(job.substate, '(None)')
        pbs.logjobmsg(
            job.id, 'jobobit hook, job_state_desc=%s' % (state_desc,))
        pbs.logjobmsg(
            job.id, 'jobobit hook, job_substate_desc=%s' % (substate_desc,))
        if hasattr(job, "resv") and job.resv:
            pbs.logjobmsg(
                job.id, 'jobobit hook, resv:%s' % (job.resv.resvid,))
            pbs.logjobmsg(
                job.id,
                'jobobit hook, resv_nodes:%s' % (job.resv.resv_nodes,))
            pbs.logjobmsg(
                job.id,
                'jobobit hook, resv_state:%s' % (job.resv.reserve_state,))
        else:
            pbs.logjobmsg(job.id, 'jobobit hook, resv:(None)')
        pbs.logjobmsg(
            job.id, 'jobobit hook finished for test %s' % (e.hook_name,))
    except Exception as err:
        ty, _, tb = sys.exc_info()
        pbs.logmsg(
            pbs.LOG_DEBUG, str(ty) + str(tb.tb_frame.f_code.co_filename) +
            str(tb.tb_lineno))
        e.reject()
    else:
        e.accept()


@tags('hooks')
class TestHookJobObit(TestFunctional):
    node_cpu_count = 4
    job_default_nchunks = 1
    job_default_ncpus = 1
    job_array_num_subjobs = node_cpu_count
    job_time_success = 5
    job_time_rerun = 10
    job_time_qdel = 30
    resv_default_nchunks = 1
    resv_default_ncpus = node_cpu_count
    resv_start_delay = 20
    resv_duration = 180

    node_fail_timeout = 15
    job_requeue_timeout = 5
    resv_retry_time = 5

    @property
    def is_array_job(self):
        return len(self.subjob_ids) > 0

    def run_test_func(self, test_body_func, *args, **kwargs):
        """
        Setup the environment for running jobobit hook related tests, execute
        the test function and then perform common checks and clean up.
        """
        self.job = None
        self.subjob_ids = []
        self.started_job_ids = set()
        self.ended_job_ids = set()
        self.deleted_job_ids = set()
        self.delete_failed_job_ids = set()
        self.rerun_job_ids = set()
        self.resv_id = None
        self.resv_queue = None
        self.resv_start_time = None
        self.scheduling_enabled = True
        self.moms_stopped = False
        self.node_count = len(self.server.moms)
        self.hook_name = test_body_func.__name__

        self.logger.info("***** JOBOBIT HOOK TEST START *****")

        a = {'resources_available.ncpus': self.node_cpu_count}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)

        try:
            # If hook exists from a previous test, remove it
            self.server.delete_hook(self.hook_name)
        except PtlException:
            pass

        a = {'event': 'jobobit', 'enabled': 'True'}
        ret = self.server.create_hook(self.hook_name, a)
        self.assertTrue(ret, "Could not create hook %s" % self.hook_name)

        hook_body = generate_hook_body_from_func(jobobit_hook)
        ret = self.server.import_hook(self.hook_name, hook_body)
        self.assertTrue(ret, "Could not import hook %s" % self.hook_name)

        a = {
            'job_history_enable': 'True',
            'job_requeue_timeout': self.job_requeue_timeout,
            'node_fail_requeue': self.node_fail_timeout,
            'reserve_retry_time': self.resv_retry_time,
        }
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.log_start_time = time.time()
        try:
            test_body_func(*args, **kwargs)
            self.check_log_for_jobobit_hook_messages()
        finally:
            # Make an effort to start the MoMs if they are not running
            for mom in self.moms.values():
                if not self.mom.isUp(max_attempts=3):
                    try:
                        self.mom.start()
                    except PtlException:
                        pass
            ret = self.server.delete_hook(self.hook_name)
            self.assertTrue(ret, "Could not delete hook %s" % self.hook_name)

        self.logger.info("***** JOBOBIT HOOK TEST END *****")

    def job_verify_jobobit_hook_messages(self, job_id, existence):
        """
        Look for messages logged by the jobobit hook.  This method assumes that
        a started job have been verified as terminated (ended/requeued) or
        forced deleted, thus insuring that the jobobit hook has run for the
        job.
        """
        self.server.log_match(
            '%s;jobobit hook started for test %s' % (job_id, self.hook_name),
            starttime=self.log_start_time, n='ALL', max_attempts=1,
            existence=existence)
        # TODO: Add checks for expected job state and substate
        self.server.log_match(
            '%s;jobobit hook, resv:%s' % (job_id, self.resv_queue or "(None)"),
            starttime=self.log_start_time, n='ALL', max_attempts=1,
            existence=existence)
        self.server.log_match(
            '%s;jobobit hook finished for test %s' % (job_id, self.hook_name),
            starttime=self.log_start_time, n='ALL', max_attempts=1,
            existence=existence)

    def check_log_for_jobobit_hook_messages(self):
        """
        Look for messages logged by the jobobit hook.  This method assumes that
        all started jobs have been verified as terminated or forced deleted,
        thus insuring that the jobobit hook has run for those jobs.
        """
        for jid in [self.job_id] + self.subjob_ids:
            job_ended = jid in self.ended_job_ids or jid in self.rerun_job_ids
            self.job_verify_jobobit_hook_messages(jid, job_ended)
            # Remove any jobs that ended from the list of started and deleted
            # jobs.  At this point, they should no longer exist and thus are
            # irrelevant in either set.
            if job_ended:
                self.started_job_ids.discard(jid)
                self.rerun_job_ids.discard(jid)
                self.deleted_job_ids.discard(jid)
                self.delete_failed_job_ids.discard(jid)
                self.ended_job_ids.discard(jid)
        # Reset the start time so that searches on requeued jobs don't match
        # state or log messages prior to the current search.  This assumes that
        # previous state and log messages for a test will not contain a time
        # stamp equal to or greater than the new start time.
        self.log_start_time = time.time()

    def get_job_id_set(self, job_ids):
        try:
            return set(job_ids)
        except TypeError:
            return set([job_ids]) if job_ids else set([self.job_id])

    def job_submit(
            self,
            subjob_count=0,
            user=TEST_USER,
            nchunks=job_default_nchunks,
            ncpus=job_default_ncpus,
            job_time=job_time_success,
            job_rerunnable=True,
            job_attrs=None):
        if self.scheduling_enabled:
            # Disable scheduling so that jobs won't be immediately started
            # until we've verified that they have been queued
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            self.scheduling_enabled = False
        a = {}
        a['Resource_List.select'] = str(nchunks) + ':ncpus=' + str(ncpus)
        if subjob_count == 1:
            a[ATTR_J] = '0-1:2'
        elif subjob_count > 1:
            a[ATTR_J] = '0-' + str(subjob_count - 1)
        self.job_rerunnable = job_rerunnable
        if not job_rerunnable:
            a[ATTR_r] = 'n'
        a.update(job_attrs or {})
        self.job = Job(user, attrs=a)
        self.job.set_sleep_time(job_time)
        self.job_id = self.server.submit(self.job)
        self.subjob_ids = [
            self.job.create_subjob_id(self.job_id, i)
            for i in range(subjob_count)]

    def job_rerun(self, job_ids=None, force=False, user=None):
        if self.scheduling_enabled:
            # Disable scheduling so that requeued (rerun) jobs won't be
            # immediately restarted
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            self.scheduling_enabled = False
        jids = self.get_job_id_set(job_ids)
        extend = 'force' if force else None
        try:
            self.server.rerunjob(list(jids), extend=extend, runas=user)
        except PbsRerunError:
            # A failed rerun should eventually result in the jobobit hook being
            # run and the job being requeued
            pass
        if self.is_array_job and self.job_id in jids:
            self.rerun_job_ids.update(self.started_job_ids)
            self.rerun_job_ids.remove(self.job_id)
        else:
            self.rerun_job_ids.update(jids & self.started_job_ids)

    def job_delete(self, job_ids=None, force=False, user=None):
        if self.scheduling_enabled:
            # Disable scheduling so that requeued (rerun) jobs won't be
            # immediately restarted
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            self.scheduling_enabled = False
        jids = self.get_job_id_set(job_ids)
        extend = 'force' if force else None
        try:
            self.server.delete(list(jids), extend=extend, runas=user)
        except PbsDeleteError:
            # This assumes that if deleting one job fails then the delete
            # failed for all jobs, which in our controlled testing is likely
            # true
            job_id_set = self.delete_failed_job_ids
        else:
            job_id_set = self.deleted_job_ids
        job_id_set.update(jids)
        if self.is_array_job:
            if self.job_id in jids:
                job_id_set.update(self.subjob_ids)
            # If a single subjob is deleted (TERMINATED), the substate for the
            # array job is also set to TERMINATED.
            self.deleted_job_ids.add(self.job_id)

    def job_verify_queued(self, job_ids=None):
        # Verifying that the jobs are queued should only be performed when the
        # scheduler has been disabled before submitting or rerunning the jobs.
        # If the scheduler is active, then the jobs may have been started and
        # thus may no longer be in the queued state.
        self.assertFalse(self.scheduling_enabled, "scheduling is enabled!")
        jids = self.get_job_id_set(job_ids)
        if self.is_array_job and self.job_id in jids:
            if self.job_id not in self.started_job_ids:
                self.server.expect(JOB, {'job_state': 'Q'}, id=self.job_id)
                self.server.accounting_match(
                    "Q;%s;" % (self.job_id,),
                    starttime=int(self.log_start_time),
                    n='ALL', max_attempts=1)
            else:
                self.server.expect(JOB, {'job_state': 'B'}, id=self.job_id)
            jids.update(self.subjob_ids)
            jids.remove(self.job_id)
        for jid in jids:
            self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
            if jid in self.started_job_ids:
                # Jobs/Subjobs that were started and then requeued need to be
                # added to the rerun list to indicate that output from the hook
                # should be present.
                self.rerun_job_ids.add(jid)
            if jid in self.rerun_job_ids:
                self.server.accounting_match(
                    "R;%s;" % (jid,),
                    starttime=int(self.log_start_time),
                    n='ALL', max_attempts=1)
            elif not self.is_array_job:
                self.server.accounting_match(
                    "Q;%s;" % (jid,),
                    starttime=int(self.log_start_time),
                    n='ALL', max_attempts=1)

    def job_verify_started(self, job_ids=None):
        if not self.scheduling_enabled:
            # If scheduling was previously disabled to allow time for log
            # scraping, etc. before requeued jobs were restarted, then enabling
            # scheduling again.
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            self.scheduling_enabled = True
        jids = self.get_job_id_set(job_ids)
        if self.is_array_job and self.job_id in jids:
            self.server.expect(JOB, {'job_state': 'B'}, id=self.job_id)
            if self.job_id not in self.started_job_ids:
                self.server.accounting_match(
                    "S;%s;" % (self.job_id,),
                    starttime=int(self.log_start_time),
                    n='ALL', max_attempts=1)
            jids.update(self.subjob_ids)
            jids.remove(self.job_id)
            self.started_job_ids.add(self.job_id)
        for jid in jids:
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
            self.server.accounting_match(
                "S;%s;" % (jid,),
                starttime=int(self.log_start_time),
                n='ALL', max_attempts=1)
            self.started_job_ids.add(jid)

    def job_verify_ended(self, job_ids=None):
        jids = self.get_job_id_set(job_ids)
        if self.is_array_job and self.job_id in jids:
            if self.job_id not in self.delete_failed_job_ids:
                jids.update(self.started_job_ids)
            else:
                jids.remove(self.job_id)
        for jid in jids & self.started_job_ids:
            # If the job failed, the verify that the substate is FAILED (93).
            # If the job was deleted, then verify that the substate is set to
            # TERMINATED (91).  Otherwise, verify that the substate is set to
            # FINISHED (92).
            if jid in self.delete_failed_job_ids:
                substate = 93
            elif jid in self.deleted_job_ids:
                substate = 91
            else:
                substate = 92
            self.server.expect(
                JOB, {'job_state': 'F', 'substate': substate}, extend='x',
                id=jid)
            # If the job was deleted without the force flag and the moms were
            # stopped and not restarted, then an accounting 'E' record will not
            # be immediately written.
            if not (jid in self.delete_failed_job_ids and self.moms_stopped):
                self.server.accounting_match(
                    "E;%s;" % (jid,),
                    starttime=int(self.log_start_time),
                    n='ALL', max_attempts=1)
            self.ended_job_ids.add(jid)

    def resv_submit(
            self,
            user=TEST_USER,
            nchunks=resv_default_nchunks,
            ncpus=resv_default_ncpus,
            resv_start_time=None,
            resv_end_time=None,
            resv_attrs=None):
        start_time = resv_start_time or int(time.time()) + \
            self.resv_start_delay
        end_time = resv_end_time or start_time + self.resv_duration
        a = {}
        a['Resource_List.select'] = str(nchunks) + ':ncpus=' + str(ncpus)
        a['Resource_List.place'] = 'free'
        a['reserve_start'] = start_time
        a['reserve_end'] = end_time
        a.update(resv_attrs or {})
        resv = Reservation(user, a)
        self.resv_id = self.server.submit(resv)
        self.resv_start_time = start_time

    def resv_verify_confirmed(self):
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=self.resv_id)
        self.resv_queue = self.resv_id.split('.')[0]
        self.server.status(RESV, 'resv_nodes')

    def resv_verify_started(self):
        self.logger.info('Sleeping until reservation starts')
        self.server.expect(
            RESV, {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')},
            id=self.resv_id,
            offset=self.resv_start_time - int(time.time() + 1))

    def moms_start(self, *args, **kwargs):
        for mom in self.moms.values():
            mom.start(*args, **kwargs)
        self.moms_stopped = False
        if not self.scheduling_enabled:
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            self.scheduling_enabled = True

    def moms_stop(self, *args, **kwargs):
        if self.scheduling_enabled:
            self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
            self.scheduling_enabled = False
        for mom in self.moms.values():
            mom.stop(*args, **kwargs)
        self.moms_stopped = True

    # -------------------------------------------------------------------------

    def jobobit_simple_run_job(self, subjob_count=0):
        self.job_submit(subjob_count=subjob_count)
        self.job_verify_queued()
        self.job_verify_started()
        self.job_verify_ended()

    def test_hook_jobobit_run_single_job(self):
        """
        Run a single job to completion and verify that the jobobit hook is
        executed.
        """
        self.run_test_func(
            self.jobobit_simple_run_job)

    @tags('smoke')
    def test_hook_jobobit_run_array_job(self):
        """
        Run an array of jobs to completion and verify that the jobobit hook is
        executed for all subjobs and the array job.
        """
        self.run_test_func(
            self.jobobit_simple_run_job,
            subjob_count=self.job_array_num_subjobs)

    # -------------------------------------------------------------------------

    def test_hook_jobobit_run_array_job_in_resv(self):
        """
        Run an array of jobs to completion within a reservation and verify that
        that the jobobit hook is executed for all subjobs and the array job.
        """
        def jobobit_run_array_job_in_resv():
            self.resv_submit()
            self.resv_verify_confirmed()
            a = {ATTR_queue: self.resv_queue}
            self.job_submit(
                subjob_count=2,
                ncpus=self.node_cpu_count // 2,
                job_attrs=a)
            self.job_verify_queued()
            self.resv_verify_started()
            self.job_verify_started()
            self.job_verify_ended()

        self.run_test_func(jobobit_run_array_job_in_resv)

    # -------------------------------------------------------------------------

    def jobobit_rerun_job(
            self,
            subjob_count=0,
            rerun_force=False,
            rerun_user=None,
            stop_moms=False,
            restart_moms=False):
        self.job_submit(
            subjob_count=subjob_count,
            job_time=self.job_time_rerun)
        self.job_verify_queued()
        self.job_verify_started()
        if stop_moms:
            self.moms_stop()
        self.job_rerun(force=rerun_force, user=rerun_user)
        self.job_verify_queued()
        self.check_log_for_jobobit_hook_messages()
        if restart_moms:
            self.moms_start()
        if not stop_moms or restart_moms:
            self.job_verify_started()
        self.job_verify_ended()

    def test_hook_jobobit_rerun_single_job_as_root(self):
        """
        Start a single job, issue a rerun as root, and verify that the jobobit
        hook is executed for both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job)

    def test_hook_jobobit_rerun_single_job_as_mgr(self):
        """
        Start a single job, issue a rerun as manager, and verify that the end
        job hook is executed for both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            rerun_user=MGR_USER)

    def test_hook_jobobit_force_rerun_single_job_as_root(self):
        """
        Start a single job, issue a rerun as root, and verify that the jobobit
        hook is executed for both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            rerun_force=True)

    def test_hook_jobobit_force_rerun_single_job_as_mgr(self):
        """
        Start a single job, force issue a rerun as manager, and verify that the
        jobobit hook is executed for both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            rerun_force=True,
            rerun_user=MGR_USER)

    def test_hook_jobobit_rerun_single_job_stop_moms(self):
        """
        Start a single job, issue a rerun after stopping the MoMs. Verify that
        the job is requeued and that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            stop_moms=True,
            restart_moms=False)

    def test_hook_jobobit_force_rerun_single_job_stop_moms(self):
        """
        Start a single job, issue a force rerun after stopping the MoMs. Verify
        that the job is requeued and that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            rerun_force=True,
            stop_moms=True,
            restart_moms=False)

    def test_hook_jobobit_rerun_single_job_restart_moms(self):
        """
        Start a single job, issue a rerun after stopping the MoMs, then enable
        the MoMs again, verifying that the jobobit hook is executed for both
        runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            stop_moms=True,
            restart_moms=True)

    def test_hook_jobobit_force_rerun_single_job_restart_moms(self):
        """
        Start a single job, issue a force rerun after stopping the MoMs, then
        enable the MoMs again, verifying that the jobobit hook is executed for
        both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            rerun_force=True,
            stop_moms=True,
            restart_moms=True)

    def test_hook_jobobit_rerun_array_job(self):
        """
        Start an array job, issue a rerun, and verify that the jobobit hook is
        executed for all subjob on both runs and only once for the array job.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_force_rerun_array_job(self):
        """
        Start an array job, issue a force rerun, and verify that the jobobit
        hook is executed for all subjob on both runs and only once for the
        array job.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            subjob_count=self.job_array_num_subjobs,
            rerun_force=True)

    def test_hook_jobobit_rerun_array_job_restart_moms(self):
        """
        Start an array job, issue a rerun after stopping the MoMs, then start
        the MoMs again, verifying that the jobobit hook is executed for both
        runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            subjob_count=self.job_array_num_subjobs,
            stop_moms=True,
            restart_moms=True)

    def test_hook_jobobit_force_rerun_array_job_restart_moms(self):
        """
        Start an array job, issue a force rerun after stopping the MoMs, then
        start the MoMs again, verifying that the jobobit hook is executed for
        both runs.
        """
        self.run_test_func(
            self.jobobit_rerun_job,
            subjob_count=self.job_array_num_subjobs,
            rerun_force=True,
            stop_moms=True,
            restart_moms=True)

    # -------------------------------------------------------------------------

    def jobobit_rerun_and_delete_job(
            self,
            subjob_count=0,
            delete_force=False):
        self.job_submit(
            subjob_count=subjob_count,
            job_time=self.job_time_rerun)
        self.job_verify_started()
        self.job_rerun()
        self.job_verify_queued()
        self.check_log_for_jobobit_hook_messages()
        self.job_delete(force=delete_force)
        self.job_verify_ended()

    def test_hook_jobobit_rerun_and_delete_single_job(self):
        """
        Start a single job, issue a rerun and immediately delete it.  Verify
        that the jobobit hook is only executed once.
        """
        self.run_test_func(
            self.jobobit_rerun_and_delete_job)

    def test_hook_jobobit_rerun_and_force_delete_single_job(self):
        """
        Start a single job, issue a rerun and immediately force delete it.
        Verify that the jobobit hook is only executed once.
        """
        self.run_test_func(
            self.jobobit_rerun_and_delete_job,
            delete_force=True)

    def test_hook_jobobit_rerun_and_delete_array_job(self):
        """
        Start an array job, issue a rerun and immediately delete it. Verify
        that the jobobit hook is only executed once for each subjob and the
        job array.
        """
        self.run_test_func(
            self.jobobit_rerun_and_delete_job,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_rerun_and_force_delete_array_job(self):
        """
        Start an array job, issue a rerun and immediately force delete it.
        Verify that the jobobit hook is only executed once for each subjob and
        the job array.
        """
        self.run_test_func(
            self.jobobit_rerun_and_delete_job,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True)

    # -------------------------------------------------------------------------

    def jobobit_delete_unstarted_job(
            self,
            subjob_count=0,
            delete_force=False,
            delete_user=None):
        self.job_submit(
            subjob_count=subjob_count,
            nchunks=self.node_count,
            ncpus=self.node_cpu_count * 2,
            job_time=self.job_time_qdel)
        self.job_verify_queued()
        self.job_delete(force=delete_force, user=delete_user)
        self.job_verify_ended()

    def test_hook_jobobit_delete_unstarted_single_job_as_root(self):
        """
        Queue a single job, but delete it as root before it starts.  Verify
        that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job)

    def test_hook_jobobit_delete_unstarted_single_job_as_user(self):
        """
        Queue a single job, but delete it as the user before it starts.  Verify
        that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            delete_user=TEST_USER)

    def test_hook_jobobit_force_delete_unstarted_single_job_as_root(self):
        """
        Queue a single job, but force delete it as root before it starts.
        Verify that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            delete_force=True)

    def test_hook_jobobit_force_delete_unstarted_single_job_as_user(self):
        """
        Queue a single job, but force delete it as the user before it starts.
        Verify that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            delete_force=True,
            delete_user=TEST_USER)

    def test_hook_jobobit_delete_unstarted_array_job_as_root(self):
        """
        Queue an array job, but delete it as root before it starts.  Verify
        that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_delete_unstarted_array_job_as_user(self):
        """
        Queue an array job, but delete it as the user before it starts.  Verify
        that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            subjob_count=self.job_array_num_subjobs,
            delete_user=TEST_USER)

    def test_hook_jobobit_force_delete_unstarted_array_job_as_root(self):
        """
        Queue an array job, but force delete it as root before it starts.
        Verify that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True)

    def test_hook_jobobit_force_delete_unstarted_array_job_as_user(self):
        """
        Queue an array job, but force delete it as the user before it starts.
        Verify that the jobobit hook is not executed.
        """
        self.run_test_func(
            self.jobobit_delete_unstarted_job,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True,
            delete_user=TEST_USER)

    # -------------------------------------------------------------------------

    def jobobit_delete_running_job(
            self,
            subjob_count=0,
            job_rerunnable=True,
            delete_force=False,
            delete_user=None):
        self.job_submit(
            job_rerunnable=job_rerunnable,
            subjob_count=subjob_count,
            job_time=self.job_time_qdel)
        self.job_verify_queued()
        self.job_verify_started()
        self.job_delete(force=delete_force, user=delete_user)
        self.job_verify_ended()

    def test_hook_jobobit_delete_running_single_job_as_root(self):
        """
        Run a single job, but delete as root before completion.  Verify that
        the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job)

    def test_hook_jobobit_delete_running_single_job_as_user(self):
        """
        Run a single job, but delete as the user before completion.  Verify
        that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            delete_user=TEST_USER)

    def test_hook_jobobit_force_delete_running_single_job_as_root(self):
        """
        Run a single job, but force delete as root before completion.  Verify
        that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            delete_force=True)

    def test_hook_jobobit_force_delete_running_single_job_as_user(self):
        """
        Run a single job, but force delete as the user before completion.
        Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            delete_force=True,
            delete_user=TEST_USER)

    def test_hook_jobobit_delete_running_array_job_as_root(self):
        """
        Run an array job, where all jobs are started but also deleted (by root)
        before completion.  Verify that the jobobit hook is executed for all
        subjobs and the array job.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_delete_running_array_job_as_user(self):
        """
        Run an array job, where all jobs have started but also deleted (by the
        user) before completion.  Verify that the jobobit hook is executed for
        all subjobs and the array job.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            subjob_count=self.job_array_num_subjobs,
            delete_user=TEST_USER)

    def test_hook_jobobit_force_delete_running_array_job_as_root(self):
        """
        Run an array job, where all jobs are started but also force deleted (by
        root) before completion.  Verify that the jobobit hook is executed for
        all subjobs and the array job.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            delete_force=True,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_force_delete_running_array_job_as_user(self):
        """
        Run an array job, where all jobs have started but also force deleted
        (by the user) before completion.  Verify that the jobobit hook is
        executed for all subjobs and the array job.
        """
        self.run_test_func(
            self.jobobit_delete_running_job,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True,
            delete_user=TEST_USER)

    # -------------------------------------------------------------------------

    def jobobit_delete_running_job_moms_stopped(
            self,
            subjob_count=0,
            job_rerunnable=True,
            delete_user=None,
            delete_force=False,
            restart_moms=False):
        self.job_submit(
            subjob_count=subjob_count,
            job_time=self.job_time_qdel,
            job_rerunnable=job_rerunnable)
        self.job_verify_started()
        self.moms_stop()
        self.job_delete(force=delete_force, user=delete_user)
        if job_rerunnable and not delete_force:
            self.job_verify_queued()
            self.check_log_for_jobobit_hook_messages()
            if restart_moms:
                self.moms_start()
                self.job_verify_started()
        self.job_verify_ended()

    def test_hook_jobobit_delete_running_single_job_as_root_nrr_sm(self):
        """
        Run a single non-rerunable job, but delete as root before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            job_rerunnable=False)

    def test_hook_jobobit_delete_running_single_job_as_user_nrr_sm(self):
        """
        Run a single non-rerunable job, but delete as user before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_user=TEST_USER,
            job_rerunnable=False)

    def test_hook_jobobit_force_delete_running_single_job_as_root_nrr_sm(self):
        """
        Run a single non-rerunable job, but force delete as root before
        completion after stopping the MoM. Verify that the jobobit hook is
        executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            job_rerunnable=False)

    def test_hook_jobobit_force_delete_running_single_job_as_user_nrr_sm(self):
        """
        Run a single non-rerunable job, but force delete as user before
        completion after stopping the MoM. Verify that the jobobit hook is
        executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            delete_user=TEST_USER,
            job_rerunnable=False)

    def test_hook_jobobit_delete_running_single_job_as_root_sm(self):
        """
        Run a single rerunable job, but delete as user before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            job_rerunnable=True)

    def test_hook_jobobit_delete_running_single_job_as_user_sm(self):
        """
        Run a single rerunable job, but delete as user before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_user=TEST_USER,
            job_rerunnable=True)

    def test_hook_jobobit_force_delete_running_single_job_as_root_sm(self):
        """
        Run a single rerunable job, but force delete as root before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            job_rerunnable=True)

    def test_hook_jobobit_force_delete_running_single_job_as_user_sm(self):
        """
        Run a single rerunable job, but force delete as user before completion
        after stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            delete_user=TEST_USER,
            job_rerunnable=True)

    def test_hook_jobobit_delete_running_single_job_as_root_rm(self):
        """
        Run a single rerunable job, but delete as root before completion after
        stopping the MoM. Verify that the jobobit hook is executed.  Then
        restart the mom and verify that the job is restarted and the end
        job hook is executed again.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            restart_moms=True,
            job_rerunnable=True)

    def test_hook_jobobit_delete_running_single_job_as_user_rm(self):
        """
        Run a single rerunable job, but delete as root before completion after
        stopping the MoM. Verify that the jobobit hook is executed.  Then
        restart the mom and verify that the job is restarted and the end
        job hook is executed again.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_user=TEST_USER,
            restart_moms=True,
            job_rerunnable=True)

    def test_hook_jobobit_force_delete_running_single_job_as_root_rm(self):
        """
        Run a single rerunable job, but force delete as root before completion
        after stopping the MoM. Verify that the jobobit hook is executed.  Then
        restart the mom and verify that the jobobit hook is not executed again.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            restart_moms=True,
            job_rerunnable=True)

    def test_hook_jobobit_force_delete_running_single_job_as_user_rm(self):
        """
        Run a single rerunable job, but force delete as user before completion
        after stopping the MoM. Verify that the jobobit hook is executed.  Then
        restart the mom and verify that the jobobit hook is not executed again.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            delete_force=True,
            delete_user=TEST_USER,
            restart_moms=True,
            job_rerunnable=True)

    def test_hook_jobobit_delete_running_array_job_as_root_sm(self):
        """
        Run an array job, but delete as root before completion after stopping
        the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            subjob_count=self.job_array_num_subjobs)

    def test_hook_jobobit_delete_running_array_job_as_user_sm(self):
        """
        Run an array job, but delete as user before completion after stopping
        the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            subjob_count=self.job_array_num_subjobs,
            delete_user=TEST_USER)

    def test_hook_jobobit_force_delete_running_array_job_as_root_sm(self):
        """
        Run an array job, but force delete as root before completion after
        stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True)

    def test_hook_jobobit_force_delete_running_array_job_as_user_sm(self):
        """
        Run an array job, but force delete as user before completion after
        stopping the MoM. Verify that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_delete_running_job_moms_stopped,
            subjob_count=self.job_array_num_subjobs,
            delete_force=True,
            delete_user=TEST_USER)

    # -------------------------------------------------------------------------

    def jobobit_job_running_during_mom_restart(
            self,
            subjob_count=0,
            mom_preserve_jobs=True,
            mom_restart_delayed=False):
        a = {
            'node_fail_requeue': self.job_time_rerun + 60,
        }
        if mom_preserve_jobs:
            mom_stop_kwargs = {'sig': '-INT'}
            mom_start_kwargs = {'args': ['-p']}
        else:
            mom_stop_kwargs = {}
            mom_start_kwargs = {}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.job_submit(
            subjob_count=subjob_count,
            job_time=self.job_time_rerun)
        self.job_verify_started()
        self.moms_stop(**mom_stop_kwargs)
        not mom_restart_delayed or time.sleep(self.job_time_rerun + 10)
        if not mom_preserve_jobs:
            self.rerun_job_ids.update(self.started_job_ids)
            if self.is_array_job:
                self.rerun_job_ids.remove(self.job_id)
            self.job_verify_queued()
            self.check_log_for_jobobit_hook_messages()
        self.moms_start(**mom_start_kwargs)
        if not mom_preserve_jobs:
            self.job_verify_started()
        self.job_verify_ended()

    def test_hook_jobobit_finish_single_job_during_mom_restart(self):
        """
        Run a single rerunable job and restart the MoMs.  Verify that the job
        successfully completes without being rerun and that the jobobit hook
        is executed.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart
        )

    def test_hook_jobobit_finish_single_job_during_mom_restart_delayed(self):
        """
        Run a single rerunable job.  Stop the MoMs long enough for the job to
        complete and then restart the MoMs.  Verify that the job successfully
        completes without being rerun and that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            mom_restart_delayed=True
        )

    def test_hook_jobobit_rerun_single_job_during_mom_restart(self):
        """
        Run a single rerunable job and restart the MoMs.  Verify that the job
        is requeued and successfully completes, and that the jobobit hook is
        executed twice.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            mom_preserve_jobs=False
        )

    def test_hook_jobobit_rerun_single_job_during_mom_restart_delayed(self):
        """
        Run a single rerunable job.  Stop the MoMs long enough for the job to
        complete and then restart the MoMs.  Verify that the job is requeued
        and successfully completes, and that the jobobit hook is executed
        twice.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            mom_preserve_jobs=False,
            mom_restart_delayed=True
        )

    def test_hook_jobobit_finish_array_job_during_mom_restart(self):
        """
        Run an array job and restart the MoMs.  Verify that the subjobs
        successfully complete without being rerun and that the jobobit hook
        is executed.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            subjob_count=self.job_array_num_subjobs
        )

    def test_hook_jobobit_finish_array_job_during_mom_restart_delayed(self):
        """
        Run an array job.  Stop the MoMs long enough for the job to
        complete and then restart the MoMs.  Verify that the job successfully
        completes without being rerun and that the jobobit hook is executed.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            subjob_count=self.job_array_num_subjobs,
            mom_restart_delayed=True
        )

    def test_hook_jobobit_rerun_array_job_during_mom_restart(self):
        """
        Run an array job and restart the MoMs without preserving existing jobs.
        Verify that the subjobs are successfully rerun and that the jobobit
        hook is executed twice for each subjob.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            subjob_count=self.job_array_num_subjobs,
            mom_preserve_jobs=False
        )

    def test_hook_jobobit_rerun_array_job_during_mom_restart_delayed(self):
        """
        Run an array job.  Stop the MoMs long enough for the job to complete
        and then restart the MoMs without preserving existing jobs.  Verify
        that the subjobs are successfully rerun and that the jobobit hook is
        executed twice for each subjob.
        """
        self.run_test_func(
            self.jobobit_job_running_during_mom_restart,
            subjob_count=self.job_array_num_subjobs,
            mom_preserve_jobs=False,
            mom_restart_delayed=True
        )

    # -------------------------------------------------------------------------

    # TODO: Test aborted single/array job for going over time.

    # TODO: Test deletion of individual and ranges of subjobs in an array job.

    # TODO: Test delete and rerun of an array job when a subset of the possible
    # subjobs are running.  Verify that the jobobit hooks are called for all
    # jobs/subjobs that were previously started.

    # TODO: Test various scenarios of the server being stopped and restarted,
    # insuring that the jobobit hooks are called for all jobs/subjobs that were
    # previously started.

    # TODO: Test deletion of job during provisioning to insure that the jobobit
    # hook is not run.
