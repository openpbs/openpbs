
# coding: utf-8
# Copyright (C) 2023 Altair Engineering, Inc. All rights reserved.
# Copyright notice does not imply publication.
#
# ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
# Information. Not for use or disclosure outside of Licensee's organization.
# The software and information contained herein may only be used internally and
# is provided on a non-exclusive, non-transferable basis. License may not
# sublicense, sell, lend, assign, rent, distribute, publicly display or
# publicly perform the software or other information provided herein,
# nor is Licensee permitted to decompile, reverse engineer, or
# disassemble the software. Usage of the software and other information
# provided by Altair(or its resellers) is only as explicitly stated in the
# applicable end user license agreement between Altair and Licensee.
# In the absence of such agreement, the Altair standard end user
# license agreement terms shall govern.

from tests.security import *


class Test_job_security(TestSecurity):
    """
    This test suite is for testing job security
    """

    def setUp(self):
        TestSecurity.setUp(self)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    def test_interactive_job_env_V(self):
        """
        This test checks if the PBS job related cookies are passed on to
        the job that is submitted within the interactive job with -V.
        """
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        j = Job(TEST_USER)
        set_attr = {ATTR_inter: ''}
        j.set_attributes(set_attr)
        j.interactive_script = [('export PATH=$PATH:%s' %
                                 self.exec_path, '.*'),
                                ('qsub -V -- /bin/sleep 5', '.*'),
                                ('sleep 30', '.*')]
        jid = self.server.submit(j)
        jid2 = str(int(jid.split('.')[0]) + 1)
        self.server.expect(JOB, {'job_state=R': 2}, count=True)
        stat = self.server.status(JOB, id=jid2, extend='x')
        for s in stat:
            variable_list = s.get('Variable_List', '')
            if 'PBS_JOBCOOKIE' in variable_list or \
                    'PBS_INTERACTIVE_COOKIE' in variable_list:
                self.fail("Job Cookie(s) passed on to the inner job.")

    def test_interactive_job_env_v(self):
        """
        This test checks if the PBS job related cookies are passed on to
        the job that is submitted within the interactive job
        with -v PBS_JOBCOOKIE.
        """
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        j = Job(TEST_USER)
        set_attr = {ATTR_inter: ''}
        j.set_attributes(set_attr)
        j.interactive_script = [('export PATH=$PATH:%s' %
                                 self.exec_path, '.*'),
                                ('qsub -v PBS_JOBCOOKIE -- \
                                    /bin/sleep 5', '.*'),
                                ('sleep 30', '.*')]
        jid = self.server.submit(j)
        jid2 = str(int(jid.split('.')[0]) + 1)
        self.server.expect(JOB, {'job_state=R': 2}, count=True)
        stat = self.server.status(JOB, id=jid2, extend='x')
        for s in stat:
            variable_list = s.get('Variable_List', '')
            if 'PBS_JOBCOOKIE' in variable_list or \
                    'PBS_INTERACTIVE_COOKIE' in variable_list:
                self.fail("Job Cookie(s) passed on to the inner job.")

    def tearDown(self):
        TestSecurity.tearDown(self)
