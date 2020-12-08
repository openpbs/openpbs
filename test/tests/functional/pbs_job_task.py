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


from tests.functional import *


class TestJobTask(TestFunctional):
    """
    This test suite validates the job task using pbsdsh or pbs_tmrsh
    """

    def setUp(self):
        TestFunctional.setUp(self)

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'job_history_enable': 'true'})

    def check_jobs_file(self, out_file):
        """
        This function validates job's output file
        """
        ret = self.du.cat(hostname=self.server.shortname,
                          filename=out_file,
                          runas=TEST_USER)
        _msg = "cat command failed with error:%s" % ret['err']
        self.assertEqual(ret['rc'], 0, _msg)
        _msg = 'Job\'s error file has error:"%s"' % ret['out']
        self.assertEqual(ret['out'][0], "OK", _msg)
        self.logger.info("Job has executed without any error")

    def test_singlenode_pbsdsh(self):
        """
        This test case validates that task started by pbsdsh runs
        properly within a single-noded job.
        """
        a = {ATTR_S: '/bin/bash'}
        job = Job(TEST_USER, attrs=a)
        pbsdsh_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  'bin', 'pbsdsh')
        script = ['%s echo "OK"' % pbsdsh_cmd]
        job.create_script(body=script)
        jid = self.server.submit(job)
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')

        job_status = self.server.status(JOB, id=jid, extend='x')
        if job_status:
            job_output_file = job_status[0]['Output_Path'].split(':')[1]
        self.check_jobs_file(job_output_file)

    def test_singlenode_pbs_tmrsh(self):
        """
        This test case validates that task started by pbs_tmrsh runs
        properly within a single-noded job.
        """
        a = {ATTR_S: '/bin/bash'}
        job = Job(TEST_USER, attrs=a)
        pbstmrsh_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                    'bin', 'pbs_tmrsh')
        script = ['%s $(hostname -f) echo "OK"' % pbstmrsh_cmd]
        job.create_script(body=script)
        jid = self.server.submit(job)

        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')

        job_status = self.server.status(JOB, id=jid, extend='x')
        if job_status:
            job_output_file = job_status[0]['Output_Path'].split(':')[1]
        self.check_jobs_file(job_output_file)

    def test_invoke_pbs_tmrsh_from_sister_mom(self):
        """
        This test cases verifies pbs_tmrsh invoked from sister mom
        executes successfully
        """
        # Skip test if number of mom provided is not equal to three
        if not len(self.moms) == 3:
            self.skipTest("test requires three MoMs as input, " +
                          "use -p moms=<mom1:mom2:mom3>")
        mom1 = self.moms.keys()[0]
        mom2 = self.moms.keys()[1]
        mom3 = self.moms.keys()[2]
        pbstmrsh_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                    'bin', 'pbs_tmrsh')

        script_mom2 = """#!/bin/bash\n%s %s hostname""" % \
                      (pbstmrsh_cmd, mom3)
        fn = self.du.create_temp_file(hostname=mom2, body=script_mom2)
        self.du.chmod(hostname=mom2, path=fn, mode=0o755)
        a = {ATTR_S: '/bin/bash'}
        script = ['%s %s %s' % (pbstmrsh_cmd, mom2, fn)]
        job = Job(TEST_USER, attrs=a)
        job.set_attributes({'Resource_List.select': '3:ncpus=1',
                            'Resource_List.place': 'scatter'})
        job.create_script(body=script)
        jid = self.server.submit(job)

        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        job_status = self.server.status(JOB, id=jid, extend='x')
        if job_status:
            job_output_file = job_status[0]['Output_Path'].split(':')[1]

        ret = self.du.cat(hostname=mom1, filename=job_output_file,
                          runas=TEST_USER)
        self.assertEqual(ret['out'][0], mom3, "pbs_tmrsh invoked from sister"
                                              " mom did not execute "
                                              "successfully")
