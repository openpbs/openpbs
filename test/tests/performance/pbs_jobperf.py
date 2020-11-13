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

import os
import subprocess
import statistics
from tests.performance import *
from ptl.utils.pbs_logutils import PBSLogAnalyzer
from ptl.utils.pbs_testusers import PBS_USERS


class TestJobPerf(TestPerformance):
    """
    Performance Testsuite for job related tests
    """

    def setUp(self):
        TestPerformance.setUp(self)

    def wait_for_job_finish(self, jobiter=True):
        """
        Wait for jobs to get finished
        """
        total_jobs = self.num_jobs
        total_jobs *= self.num_users
        if jobiter:
            total_jobs *= self.num_iter
        self.server.expect(JOB, {'job_state=F': total_jobs}, extend='x',
                           interval=20, trigger_sched_cycle=False)

    def delete_jobs_per_user(self, users, num_users):
        """
        Delete jobs faster by providing more job id's at once
        """
        bin_path = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin'))
        qdel = str(os.path.join(bin_path, 'qdel'))
        qdel = qdel + ' -W force'
        cmd = qdel + " `" + str(os.path.join(bin_path, 'qselect'))
        for u in range(0, num_users):
            qdel_cmd = cmd + " -u" + str(users[u]) + " `"
            subprocess.call(qdel_cmd, shell=True)

    @timeout(3600)
    @testparams(num_jobs_scof=100, num_users_scof=20,
                num_moms_scof=20, num_ncpus_scof=100)
    def test_job_performance_sched_off(self):
        """
        Test Job subission rate when scheduling is off by
        submitting 1k jobs and turn on scheduling with 2.5k ncpus.
        """
        num_moms = self.conf["TestJobPerf.num_moms_scof"]
        num_ncpus = self.conf["TestJobPerf.num_ncpus_scof"]
        num_jobs = self.conf["TestJobPerf.num_jobs_scof"]
        num_users = self.conf["TestJobPerf.num_users_scof"]

        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < num_moms:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                num_moms, self.mom)

        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        start = time.time()
        result = self.run_parallel(num_users, job, num_jobs)
        res = statistics.mean(result)
        sub_rate = (num_jobs
                    * num_users) / res
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.log_match(
            "Starting Scheduling Cycle", starttime=int(start),
            max_attempts=30)
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.scheduler.log_match("Leaving Scheduling Cycle",
                                 starttime=int(start) + 1,
                                 max_attempts=30, interval=1)
        sclg = PBSLogAnalyzer()
        md = sclg.analyze_scheduler_log(
            filename=self.scheduler.logfile, start=int(start))
        rr = md['summary']['job_run_rate']
        value = rr.strip().split('/', 1)
        run_rate = float(value[0])
        self.perf_test_result(sub_rate, "job_submission", "jobs/sec")
        self.perf_test_result(run_rate, "job_run_rate", "jobs/sec")

    @timeout(6000)
    @testparams(num_jobs_scon=100, num_users_scon=10,
                num_moms_scon=21, num_ncpus_scon=48, num_iter_scon=10)
    def test_job_performance_sched_on(self):
        """
        Test job submit_rate, run_rate, throughput by submitting 10k jobs
        when scheduling is on with 1k ncpus.
        """
        num_moms = self.conf["TestJobPerf.num_moms_scon"]
        num_ncpus = self.conf["TestJobPerf.num_ncpus_scon"]
        self.num_jobs = self.conf["TestJobPerf.num_jobs_scon"]
        self.num_users = self.conf["TestJobPerf.num_users_scon"]
        self.num_iter = self.conf["TestJobPerf.num_iter_scon"]
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < num_moms:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                num_moms, self.mom)
        sub_time = []
        i = 0
        log_start = time.time()
        a = {'job_history_enable': True}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        while i < self.num_iter:
            job = str(os.path.join(
                self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
            job += ' -koe -o /dev/null -e /dev/null'
            job += ' -- /bin/true '
            start = time.time()
            result = self.run_parallel(self.num_users, job, self.num_jobs)
            res = statistics.mean(result)
            resps = (self.num_jobs
                     * self.num_users) / res
            sub_time.append(resps)
            i += 1
        self.wait_for_job_finish()
        a = {'job_history_enable': False}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        sclg = PBSLogAnalyzer()
        md = sclg.analyze_scheduler_log(
            filename=self.scheduler.logfile, start=int(log_start))
        rr = md['summary']['job_run_rate']
        value = rr.strip().split('/', 1)
        run_rate = float(value[0])
        md = sclg.analyze_server_log(
            filename=self.server.logfile, start=int(log_start))
        jobs_ended = md['num_jobs_ended']
        if jobs_ended:
            jtr = md['job_throughput']
            value = jtr.strip().split('/', 1)
            jtr = float(value[0])
            throughput = jtr
        else:
            throughput = 0
        self.perf_test_result(sub_time, "job_submission", "jobs/sec")
        self.perf_test_result(run_rate, "job_run_rate", "jobs/sec")
        self.perf_test_result(throughput, "job_throughput", "jobs/sec")

    @timeout(3600)
    @testparams(num_jobs_qp=100, num_users_qp=10,
                num_qstats=10, num_iter_qp=10)
    def test_qstat_perf(self):
        """
        Test time taken by 100 qstat -f with 1k jobs in queue
        """
        num_jobs = self.conf["TestJobPerf.num_jobs_qp"]
        num_users = self.conf["TestJobPerf.num_users_qp"]
        num_iter = self.conf["TestJobPerf.num_iter_qp"]
        num_qstats = self.conf["TestJobPerf.num_qstats"]

        users = PBS_USERS
        i = 0
        stat_time = []
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        result = self.run_parallel(num_users, job, num_jobs)
        while i < num_iter:
            stat_cmd = str(os.path.join(
                self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat'))
            stat_cmd += ' -f'
            start = time.time()
            stat_time = self.run_parallel(num_users, stat_cmd, num_qstats)
            i = i + 1
        self.delete_jobs_per_user(users, num_users)
        self.perf_test_result(stat_time, "job_stats", "secs")

    @timeout(3600)
    @testparams(num_jobs_qhp=100, num_users_qhp=10, num_moms_qhp=21,
                num_ncpus_qhp=48, num_hqstats=10, num_iter_qhp=10)
    def test_qstat_hist_perf(self):
        """
        Test time taken by 100 qstat -fx with 1k jobs in history
        """
        num_moms = self.conf["TestJobPerf.num_moms_qhp"]
        num_ncpus = self.conf["TestJobPerf.num_ncpus_qhp"]
        self.num_jobs = self.conf["TestJobPerf.num_jobs_qhp"]
        self.num_users = self.conf["TestJobPerf.num_users_qhp"]
        self.num_iter = self.conf["TestJobPerf.num_iter_qhp"]
        num_qstats = self.conf["TestJobPerf.num_hqstats"]

        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < num_moms:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                num_moms, self.mom)
        stat_time = []
        i = 0
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        result = self.run_parallel(self.num_users, job, self.num_jobs)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.wait_for_job_finish(jobiter=False)
        while i < self.num_iter:
            stat_cmd = str(os.path.join(
                self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat'))
            stat_cmd += ' -f '
            start = time.time()
            stat_time = self.run_parallel(self.num_users, stat_cmd, num_qstats)
            i = i + 1
        a = {'job_history_enable': False}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.perf_test_result(stat_time, "job_stats_history", "secs")

    def common_server_restart(self, option=None):
        """
        Test server restart performance with huge number of jobs in queue
        """
        result = []
        i = 0
        users = PBS_USERS
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        result = self.run_parallel(self.num_users, job, self.num_jobs)
        while i < self.num_iter:
            if option == 'kill':
                self.server.stop('-KILL')
            else:
                self.server.stop()
            start = time.time()
            self.server.start()
            stop = time.time()
            res = stop - start
            i = i + 1
            result.append(res)
        self.delete_jobs_per_user(users, self.num_users)
        self.perf_test_result(result, "server_restart_perf", "secs")

    @timeout(7200)
    @testparams(num_jobs_rk=10000, num_users_rk=10,
                num_iter_rk=10)
    def test_server_restart_kill(self):
        """
        Test server kill and restart performance with 100k jobs in queue
        """
        self.num_jobs = self.conf["TestJobPerf.num_jobs_rk"]
        self.num_users = self.conf["TestJobPerf.num_users_rk"]
        self.num_iter = self.conf["TestJobPerf.num_iter_rk"]
        self.common_server_restart(option='kill')

    @timeout(7200)
    @testparams(num_jobs_r=10000, num_users_r=10,
                num_iter_r=10)
    def test_server_restart(self):
        """
        Test server restart performance 100k jobs in queue
        """
        self.num_jobs = self.conf["TestJobPerf.num_jobs_r"]
        self.num_users = self.conf["TestJobPerf.num_users_r"]
        self.num_iter = self.conf["TestJobPerf.num_iter_r"]
        self.common_server_restart()

    @timeout(7200)
    @testparams(num_jobs_qd=1000, num_users_qd=10)
    def test_qdel_perf(self):
        """
        Test job deletion performance for 10k queued jobs
        """
        num_users = self.conf["TestJobPerf.num_users_qd"]
        num_jobs = self.conf["TestJobPerf.num_jobs_qd"]

        qdel_time = []
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        result = self.run_parallel(num_users, job, num_jobs)
        start = time.time()
        bin_path = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin'))
        qdel = str(os.path.join(bin_path, 'qdel'))
        qdel = qdel + ' -W force'
        cmd = qdel + " `" + str(os.path.join(bin_path, 'qselect')) + "`"
        subprocess.call(cmd, shell=True)
        stop = time.time()
        res = stop - start
        qdel_time.append(res)
        self.perf_test_result(qdel_time, "job_deletion", "secs")

    @timeout(7200)
    @testparams(num_jobs_qdh=1000, num_users_qdh=25,
                num_moms_qdh=25, num_ncpus_qdh=100)
    def test_qdel_hist_perf(self):
        """
        Test job deletion performance for 10k history jobs
        """
        num_moms = self.conf["TestJobPerf.num_moms_qdh"]
        num_ncpus = self.conf["TestJobPerf.num_ncpus_qdh"]
        self.num_jobs = self.conf["TestJobPerf.num_jobs_qdh"]
        self.num_users = self.conf["TestJobPerf.num_users_qdh"]

        qdel_time = []
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < num_moms:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                num_moms, self.mom)
        qdel_time = []
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        job = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        job += ' -koe -o /dev/null -e /dev/null'
        job += ' -- /bin/true '
        result = self.run_parallel(self.num_users, job, self.num_jobs)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.wait_for_job_finish(jobiter=False)
        start = time.time()
        bin_path = str(os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin'))
        qdel = str(os.path.join(bin_path, 'qdel')) + ' -x'
        cmd = qdel + " `" + \
            str(os.path.join(bin_path, 'qselect')) + " -x" + "`"
        subprocess.call(cmd, shell=True)
        stop = time.time()
        res = stop - start
        qdel_time.append(res)
        self.perf_test_result(qdel_time, "job_deletion_history", 'secs')
