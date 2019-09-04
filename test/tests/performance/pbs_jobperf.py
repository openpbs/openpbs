# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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

import os
import subprocess
import multiprocessing
from threading import Thread
from tests.performance import *
from ptl.utils.pbs_logutils import PBSLogAnalyzer


class TestJobPerf(TestPerformance):
    """
    Performance Testsuite for job related tests
    """

    def setUp(self):
        TestPerformance.setUp(self)

    def set_test_config(self, config):
        """
        Sets test level configuration
        """
        testconfig = {}
        for key, value in config.iteritems():
            if isinstance(value, int):
                testconfig[key] = int(
                    self.conf[key]) if key in self.conf else value
            else:
                testconfig[key] = self.conf[key] if key in self.conf else value
        self.set_test_measurements({"test_config": testconfig})
        return testconfig

    def submit_jobs(self, user, num_jobs, qsub_exec=None,
                    qsub_exec_arg=None):
        """
        Submit jobs with provided arguments and job
        """
        job = 'sudo -u ' + str(user) + ' ' + \
              str(os.path.join(
                  self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub'))
        if qsub_exec_arg is None:
            job += ' -koe -o /dev/null -e /dev/null'
        else:
            job += ' ' + qsub_exec_arg
        if qsub_exec is None:
            job += ' -- /bin/true'
        else:
            job += ' ' + qsub_exec
        for _ in range(num_jobs):
            subprocess.call(job, shell=True)

    def wait_for_job_finish(self, jobiter=True):
        """
        Wait for jobs to get finished
        """
        total_jobs = self.config['No_of_jobs_per_user']
        total_jobs *= self.config['No_of_users']
        if jobiter:
            total_jobs *= self.config['No_of_iterations']
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
    def test_job_performance_sched_off(self):
        """
        Test Job subission from multiple users with scheduler off
        and submit jobs which can run within a single cycle
        Test Params:  'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qsub_exec': '-- /bin/true',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48
        """
        testconfig = {'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qsub_exec': '-- /bin/true',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48}
        config = self.set_test_config(testconfig)

        avg_sub_time = []
        avg_run_rate = []
        sub_rate = []
        run_rate = []
        j = 0
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < config['No_of_moms']:
            a = {'resources_available.ncpus': config['No_of_ncpus_per_node']}
            self.server.create_moms(
                'mom', a,
                config['No_of_moms'] - counts['state=free'], self.mom)
        sclg = PBSLogAnalyzer()
        while j < config['No_of_tries']:
            i = 0
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            while i < config['No_of_iterations']:
                start = time.time()
                os.chdir('/tmp')
                thrds = []
                for u in range(0, config['No_of_users']):
                    t = multiprocessing.Process(target=self.submit_jobs, args=(
                                                users[u],
                                                config['No_of_jobs_per_user'],
                                                config['qsub_exec'],
                                                config['qsub_exec_arg']))
                    t.start()
                    thrds.append(t)
                for t in thrds:
                    t.join()
                stop = time.time()
                res = stop - start
                resps = (config['No_of_jobs_per_user']
                         * config['No_of_users']) / res
                sub_rate.append(resps)
                i += 1
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
            md = sclg.analyze_scheduler_log(
                filename=self.scheduler.logfile, start=int(start))
            rr = md['summary']['job_run_rate']
            value = rr.strip().split('/', 1)
            rr = float(value[0])
            run_rate.append(rr)
            avg_sub_time.extend(sub_rate)
            avg_run_rate.extend(run_rate)
            j = j + 1
        self.perf_test_result(avg_sub_time, "job_submission", "jobs/sec")
        self.perf_test_result(avg_run_rate, "job_run_rate", "jobs/sec")

    @timeout(6000)
    def test_job_performance_sched_on(self):
        """
        Test job completion performance from multiple users with scheduler on
        Test Params: 'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qsub_exec': '-- /bin/true',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48
        """
        testconfig = {'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qsub_exec': '-- /bin/true',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48}
        self.config = self.set_test_config(testconfig)
        num_ncpus = self.config['No_of_ncpus_per_node']
        avg_sub_time = []
        avg_run_rate = []
        avg_throughput = []
        sub_time = []
        run_rate = []
        throughput = []
        j = 0
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < self.config['No_of_moms']:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                self.config['No_of_moms'] - counts['state=free'], self.mom)

        while j < self.config['No_of_tries']:
            i = 0
            log_start = time.time()
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': self.config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'job_history_enable': True}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            while i < self.config['No_of_iterations']:
                os.chdir('/tmp')
                thrds = []
                start = time.time()
                for u in range(0, self.config['No_of_users']):
                    t = multiprocessing.Process(target=self.submit_jobs, args=(
                        users[u], self.config['No_of_jobs_per_user'],
                        self.config['qsub_exec'],
                        self.config['qsub_exec_arg']))
                    t.start()
                    thrds.append(t)
                for t in thrds:
                    t.join()
                i = i + 1
                stop = time.time()
                res = stop - start
                resps = (self.config['No_of_jobs_per_user']
                         * self.config['No_of_users']) / res
                sub_time.append(resps)
            j += 1
            self.wait_for_job_finish()
            a = {'job_history_enable': False}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            sclg = PBSLogAnalyzer()
            md = sclg.analyze_scheduler_log(
                filename=self.scheduler.logfile, start=int(log_start))
            rr = md['summary']['job_run_rate']
            value = rr.strip().split('/', 1)
            rr = float(value[0])
            run_rate.append(rr)
            md = sclg.analyze_server_log(
                filename=self.server.logfile, start=int(log_start))
            jobs_ended = md['num_jobs_ended']
            if jobs_ended:
                jtr = md['job_throughput']
                value = jtr.strip().split('/', 1)
                jtr = float(value[0])
                throughput.append(jtr)
            else:
                throughput.append(0)
            avg_run_rate.extend(run_rate)
            avg_sub_time.extend(sub_time)
            avg_throughput.extend(throughput)
        self.perf_test_result(avg_sub_time, "job_submission", "jobs/sec")
        self.perf_test_result(avg_run_rate, "job_run_rate", "jobs/sec")
        self.perf_test_result(avg_throughput, "job_throughput", "jobs/sec")

    def qstat_jobs(self, user, num_stats, qstat_arg=None):
        for _ in range(num_stats):
            qstat = 'sudo -u ' + user + ' ' + \
                str(os.path.join(
                    self.server.pbs_conf['PBS_EXEC'], 'bin', 'qstat'))
            if qstat_arg:
                qstat = qstat + ' ' + qstat_arg
            self.logger.info(qstat)
            subprocess.call(qstat, shell=True)

    @timeout(3600)
    def test_qstat_perf(self):
        """
        Test qstat performance with huge number of jobs in queue
        Test Params: 'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_qstats': 100,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qstat_args': '-f',
                      'qsub_exec_arg': None
        """
        testconfig = {'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_qstats': 10,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qstat_args': '-f',
                      'qsub_exec_arg': None}
        config = self.set_test_config(testconfig)

        avg_stat_time = []
        stat_time = []
        j = 0
        while j < config['No_of_tries']:
            i = 0
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            thrds = []
            for u in range(0, config['No_of_users']):
                t = Thread(target=self.submit_jobs, args=(
                    users[u], config['No_of_jobs_per_user'], None,
                    config['qsub_exec_arg']))
                t.start()
                thrds.append(t)
            for t in thrds:
                t.join()

            while i < config['No_of_iterations']:
                os.chdir('/tmp')
                start = time.time()
                thrds = []
                for u in range(0, config['No_of_users']):
                    t = Thread(target=self.qstat_jobs, args=(
                        users[u], config['No_of_users'],
                        config['qsub_exec_arg']))
                    t.start()
                    thrds.append(t)
                for t in thrds:
                    t.join()
                stop = time.time()
                res = stop - start
                i = i + 1
                stat_time.append(res)
            j = j + 1
            avg_stat_time.extend(stat_time)
        self.delete_jobs_per_user(users, config['No_of_users'])
        self.perf_test_result(avg_stat_time, "job_stats", "secs")

    @timeout(3600)
    def test_qstat_hist_perf(self):
        """
        Test qstat performance with huge number of jobs in history
        Test Params: 'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_qstats': 100,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qstat_args': '-fx',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48
        """
        testconfig = {'No_of_jobs_per_user': 100,
                      'No_of_tries': 1,
                      'No_of_iterations': 10,
                      'No_of_qstats': 10,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qstat_args': '-fx',
                      'qsub_exec_arg': None,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48}
        self.config = self.set_test_config(testconfig)

        avg_stat_time = []
        stat_time = []
        j = 0
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < self.config['No_of_moms']:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                self.config['No_of_moms'] - counts['state=free'], self.mom)
        while j < self.config['No_of_tries']:
            i = 0
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': self.config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            thrds = []
            for u in range(0, self.config['No_of_users']):
                t = Thread(target=self.submit_jobs, args=(
                    users[u], self.config['No_of_jobs_per_user'], None,
                    self.config['qsub_exec_arg']))
                t.start()
                thrds.append(t)
            for t in thrds:
                t.join()
            a = {'job_history_enable': 'True'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'True'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            self.wait_for_job_finish(jobiter=False)
            while i < self.config['No_of_iterations']:
                os.chdir('/tmp')
                start = time.time()
                thrds = []
                for u in range(0, self.config['No_of_users']):
                    t = Thread(target=self.qstat_jobs, args=(
                        users[u], self.config['No_of_qstats'],
                        self.config['qstat_args']))
                    t.start()
                    thrds.append(t)
                for t in thrds:
                    t.join()
                stop = time.time()
                res = stop - start
                i = i + 1
                stat_time.append(res)
            j = j + 1
            avg_stat_time.extend(stat_time)
            a = {'job_history_enable': False}
            self.server.manager(MGR_CMD_SET, SERVER, a)
        self.perf_test_result(avg_stat_time, "job_stats_history", "secs")

    @timeout(3600)
    def common_server_restart(self, option=None):
        """
        Test server restart performance with huge number of jobs in queue
        """
        testconfig = {'No_of_jobs_per_user': 10000,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511}
        config = self.set_test_config(testconfig)

        avg_result = []
        result = []
        j = 0
        while j < config['No_of_tries']:
            i = 0
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            thrds = []
            for u in range(0, config['No_of_users']):
                t = Thread(target=self.submit_jobs,
                           args=(users[u], config['No_of_jobs_per_user']))
                t.start()
                thrds.append(t)
            for t in thrds:
                t.join()
            while i < config['No_of_iterations']:
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
            j = j + 1
            avg_result.extend(result)
            self.delete_jobs_per_user(users, config['No_of_users'])
        self.perf_test_result(avg_result, "server_restart_perf", "secs")

    @timeout(3600)
    def test_server_restart_kill(self):
        """
        Test server kill and restart performance with huge
        number of jobs in queue
        Test Params: 'No_of_jobs_per_user': 10000,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511
        """
        self.common_server_restart(option='kill')

    @timeout(3600)
    def test_server_restart(self):
        """
        Test server restart performance with huge number
        of jobs in queue
        Test Params: 'No_of_jobs_per_user': 10000,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511
        """
        self.common_server_restart()

    @timeout(3600)
    def test_qdel_perf(self):
        """
        Test job deletion performance for queued jobs
        Test Params: 'No_of_jobs_per_user': 1000,
                      'No_of_tries': 1,
                      'No_of_iterations': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511
        """
        testconfig = {'No_of_jobs_per_user': 1000,
                      'No_of_tries': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'qdel_exec_args': None}
        config = self.set_test_config(testconfig)

        avg_qdel_time = []
        qdel_time = []
        j = 0
        while j < config['No_of_tries']:
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            thrds = []
            for u in range(0, config['No_of_users']):
                t = Thread(target=self.submit_jobs,
                           args=(users[u], config['No_of_jobs_per_user']))
                t.start()
                thrds.append(t)
            for t in thrds:
                t.join()

            start = time.time()
            bin_path = str(os.path.join(
                self.server.pbs_conf['PBS_EXEC'], 'bin'))
            qdel = str(os.path.join(bin_path, 'qdel'))
            if config['qdel_exec_args']:
                qdel = qdel + ' -W force'
            cmd = qdel + " `" + str(os.path.join(bin_path, 'qselect')) + "`"
            subprocess.call(cmd, shell=True)
            stop = time.time()
            res = stop - start
            qdel_time.append(res)
            j = j + 1
            avg_qdel_time.extend(qdel_time)
        self.perf_test_result(avg_qdel_time, "job_deletion", "secs")

    @timeout(3600)
    def test_qdel_hist_perf(self):
        """
        Test job deletion performance for history jobs
        Test Params: 'No_of_jobs_per_user': 1000,
                      'No_of_tries': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48
        """
        testconfig = {'No_of_jobs_per_user': 1000,
                      'No_of_tries': 1,
                      'No_of_users': 10,
                      'svr_log_level': 511,
                      'No_of_moms': 21,
                      'No_of_ncpus_per_node': 48}
        self.config = self.set_test_config(testconfig)
        num_ncpus = self.config['No_of_ncpus_per_node']
        avg_qdel_time = []
        qdel_time = []
        j = 0
        counts = self.server.counter(NODE, {'state': 'free'})
        if counts['state=free'] < self.config['No_of_moms']:
            a = {'resources_available.ncpus': num_ncpus}
            self.server.create_moms(
                'mom', a,
                self.config['No_of_moms'] - counts['state=free'], self.mom)
        while j < self.config['No_of_tries']:
            users = [TEST_USER1, TEST_USER2, TEST_USER3, TEST_USER4,
                     TEST_USER5, TEST_USER6, TEST_USER7, TEST_USER,
                     ROOT_USER, ADMIN_USER]
            a = {'log_events': self.config['svr_log_level']}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            a = {'scheduling': 'False'}
            self.server.manager(MGR_CMD_SET, SERVER, a)
            thrds = []
            for u in range(0, self.config['No_of_users']):
                t = Thread(target=self.submit_jobs,
                           args=(users[u], self.config['No_of_jobs_per_user']))
                t.start()
                thrds.append(t)
            for t in thrds:
                t.join()
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
            self.logger.info(cmd)
            subprocess.call(cmd, shell=True)
            stop = time.time()
            res = stop - start
            qdel_time.append(res)
            j = j + 1
            avg_qdel_time.extend(qdel_time)
        self.perf_test_result(avg_qdel_time, "job_deletion_history", 'secs')
