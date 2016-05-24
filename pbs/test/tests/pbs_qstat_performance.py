# coding: utf-8
import commands
import os

from ptl.utils.pbs_testsuite import *
from gtk import FALSE


class TestQstatPerformance(PBSTestSuite):

    """
    Testing Qstat Performance
    """

    __author__ = " <none@pbspro.com>"

    def submit_simple_jobs(self, user ,num_jobs, qsub_exec, qsub_exec_arg):
        job = Job(user)
        job.set_execargs(qsub_exec, qsub_exec_arg)
        jobidList = []
        for _ in range(num_jobs):
            jobidList.append(self.server.submit(job))

        return jobidList
    
    def performce_measurement(self, num_jobs):          
        s = self.server        
        qsub_exec = '/bin/true'
        qsub_exec_arg = ''
        elapsedTime = 0
        
        a = {'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)

        jobidList=self.submit_simple_jobs(ADMIN_USER, num_jobs, qsub_exec, qsub_exec_arg)
        jobIds = ' '. join(jobidList)
        
        pcmd = os.path.join(self.server.client_conf['PBS_EXEC'], 'bin', 'qstat ') + jobIds
        
        startTime = time.time()        
        ret = self.du.run_cmd(socket.gethostname(), pcmd, runas=ADMIN_USER, as_script=False, level=logging.INFOCLI, logerr=True)
        if ret['rc'] != 0:
            self.logger.error('Error in executing the command ' + pcmd + 'rc =' + str(ret['rc']))
            return elapsedTime
        # FIXME self.server.status doesnt support multiple job ids  
        # qstat = self.server.status(JOB, id=jobIds)
        endTime = time.time()
        elapsedTime = endTime - startTime    
        return elapsedTime    
        
    def test_with_10_jobs(self):
        """
        Submit 10 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(10)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            print "Elapsed time for qstat command for 10 job ids is " + str(time_taken)
            self.assertTrue(time_taken)

    def test_with_100_jobs(self):
        """
        Submit 100 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(100)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            print "Elapsed time for qstat command for 100 job ids is " + str(time_taken)
            self.assertTrue(time_taken)

    def test_with_1000_jobs(self):
        """
        Submit 1000 job and compute performace of qstat
        """
        time_taken = self.performce_measurement(1000)
        if time_taken == 0:
            self.assertTrue(time_taken)
        else:
            print "Elapsed time for qstat command for 1000 job ids is " + str(time_taken)
            self.assertTrue(time_taken)
