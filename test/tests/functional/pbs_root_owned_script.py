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

import os
from tests.functional import *


class Test_RootOwnedScript(TestFunctional):
    """
    Test suite to test whether the root owned script is getting rejected
    and the comment is getting updated when root_reject_scripts set to true.
    """

    def setUp(self):
        """
        Set up the parameters required for Test_RootOwnedScript
        """
        if os.getuid() != 0 or sys.platform in ('cygwin', 'win32'):
            self.skipTest("Test need to run as root")
        TestFunctional.setUp(self)
        mom_conf_attr = {'$reject_root_scripts': 'true'}
        qmgr_attr = {'acl_roots': ROOT_USER}
        self.mom.add_config(mom_conf_attr)
        self.mom.restart()
        self.server.manager(MGR_CMD_SET, SERVER, qmgr_attr)
        self.sleep_5 = """#!/bin/bash
        sleep 5
        """
        self.qsub_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'qsub')
        # Make sure local mom is ready to run jobs
        a = {'state': 'free', 'resources_available.ncpus': (GE, 1)}
        self.server.expect(VNODE, a, max_attempts=10, interval=2)

    def test_root_owned_script(self):
        """
        Edit the mom config to reject root script
        submit a script as root and observe the job comment.
        """
        j = Job(ROOT_USER)
        j.create_script(self.sleep_5)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        jid = self.server.submit(j)
        self.server.runjob(jid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=2)
        _comment = 'Not Running: PBS Error: Execution server rejected request'
        self.server.expect(JOB, {'comment': _comment}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)
        _comment = 'job held, too many failed attempts to run'
        self.server.expect(JOB, {'comment': _comment}, id=jid)

    def test_root_owned_job_array_script(self):
        """
        Like test_root_owned_script, except job array is used.
        """
        a = {ATTR_J: '1-3'}
        j = Job(ROOT_USER, a)
        j.create_script(self.sleep_5)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        jid = self.server.submit(j)
        sjid = j.create_subjob_id(jid, 1)
        self.server.runjob(sjid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=2)
        _comment = 'Not Running: PBS Error: Execution server rejected request'
        self.server.expect(JOB, {'comment': _comment}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)
        _comment = 'job held, too many failed attempts to run'
        self.server.expect(JOB, {'comment': _comment}, id=sjid)
        ja_comment = "Job Array Held, too many failed attempts to run subjob"
        self.server.expect(JOB, {ATTR_state: "H", ATTR_comment: (MATCH_RE,
                           ja_comment)}, attrop=PTL_AND, id=jid)

    def test_non_root_script(self):
        """
        Edit the mom config to reject root script
        submit a script as TEST_USER and observe the job comment.
        """
        j = Job(TEST_USER)
        j.create_script(self.sleep_5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_root_owned_executable(self):
        """
        Edit the mom config to reject root script
        submit a job as root with the -- <executable> option.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        cmd = [self.qsub_cmd, '--', '/usr/bin/id']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')
        jid = rv['out'][0]
        self.server.runjob(jid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=2)
        _comment = 'Not Running: PBS Error: Execution server rejected request'
        self.server.expect(JOB, {'comment': _comment}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)
        _comment = 'job held, too many failed attempts to run'
        self.server.expect(JOB, {'comment': _comment}, id=jid)

    def test_root_owned_job_array_executable(self):
        """
        Like test_root_owned_executable, except job array is used.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        cmd = [self.qsub_cmd, '-J', '1-3', '--', '/usr/bin/id']
        rv = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEquals(rv['rc'], 0, 'qsub failed')
        jid = rv['out'][0]
        sjid = Job().create_subjob_id(jid, 1)
        self.server.runjob(sjid)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid, offset=2)
        _comment = 'Not Running: PBS Error: Execution server rejected request'
        self.server.expect(JOB, {'comment': _comment}, id=jid)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'H'}, id=jid)
        _comment = 'job held, too many failed attempts to run'
        self.server.expect(JOB, {'comment': _comment}, id=sjid)
        ja_comment = "Job Array Held, too many failed attempts to run subjob"
        self.server.expect(JOB, {ATTR_state: "H", ATTR_comment: (MATCH_RE,
                           ja_comment)}, attrop=PTL_AND, id=jid)

    def test_root_owned_job_pbs_attach(self):
        """
        submit a job as root and test pbs_attach feature.
        """
        mom_conf_attr = {'$reject_root_scripts': 'false'}
        self.mom.add_config(mom_conf_attr)
        self.mom.restart()
        qmgr_attr = {'acl_roots': ROOT_USER}
        self.server.manager(MGR_CMD_SET, SERVER, qmgr_attr)
        pbs_attach = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  'bin', 'pbs_attach')

        # Job script
        test = []
        test += ['#PBS -l select=ncpus=1\n']
        test += ['%s -j $PBS_JOBID -P -s %s 30\n' %
                 (pbs_attach, self.mom.sleep_cmd)]

        # Submit a job
        j = Job(ROOT_USER)
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        msg_expected = ".+%s;pid.+attached as task.+" % jid
        s = self.mom.log_match(msg_expected, regexp=True, max_attempts=10)

    def test_user_owned_job_pbs_attach(self):
        """
        submit a job as user and test pbs_attach feature.
        """
        pbs_attach = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  'bin', 'pbs_attach')

        # Job script
        test = []
        test += ['#PBS -l select=ncpus=1\n']
        test += ['%s -j $PBS_JOBID -P -s %s 30\n' %
                 (pbs_attach, self.mom.sleep_cmd)]

        # Submit a job
        j = Job(TEST_USER)
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        msg_expected = ".+%s;pid.+attached as task.+" % jid
        s = self.mom.log_match(msg_expected, regexp=True, max_attempts=10)
