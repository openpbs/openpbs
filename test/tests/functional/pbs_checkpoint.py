# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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
from ptl.utils.pbs_crayutils import CrayUtils


class TestCheckpoint(TestFunctional):
    """
    This test suite targets Checkpoint functionality.
    """
    abort_file = ''
    cu = CrayUtils()

    def test_checkpoint_abort_with_preempt(self):
        """
        This test verifies that checkpoint_abort works as expected when
        a job is preempted via checkpoint. It does so by submitting a job
        in express queue which preempts a running job in the default queue.
        """
        abort_script = """#!/bin/bash
kill $1
exit 0
"""
        self.abort_file = self.du.create_temp_file(body=abort_script)
        self.du.chmod(path=self.abort_file, mode=0755)
        c = {'$action': 'checkpoint_abort 30 !' + self.abort_file + ' %sid'}
        self.mom.add_config(c)

        self.scheduler.set_sched_config({'preempt_order': 'C'})

        a = {'queue_type': 'e',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")

        self.platform = self.du.get_platform()
        if self.platform != 'cray' and self.platform != 'craysim':
            attrs = {ATTR_l + '.select': '1:ncpus=1',
                     ATTR_l + '.place': 'excl'}
        else:
            nv = self.cu.num_compute_vnodes(self.server)
            attrs = {ATTR_l + '.select': '%d:ncpus=1' % nv,
                     ATTR_l + '.place': 'scatter'}

        j1 = Job(TEST_USER, attrs)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        attrs['queue'] = 'expressq'
        j2 = Job(TEST_USER, attrs)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)

        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        ck_dir = os.path.join(self.server.pbs_conf['PBS_HOME'], 'checkpoint',
                              jid1 + '.CK')
        self.assertTrue(os.path.isdir(ck_dir),
                        msg="Checkpoint directory for job not found")
        self.mom.log_match(msg=jid1 + ';req_holdjob: Checkpoint initiated.')
        self.mom.log_match(msg=jid1 + ';checkpoint_abort script ' +
                           self.abort_file + ': exit code 0')
        self.mom.log_match(msg=jid1 + ';checkpointed to ' + ck_dir)
        self.mom.log_match(msg=jid1 + ';task 00000001 terminated')

    def tearDown(self):
        TestFunctional.tearDown(self)
        try:
            os.remove(self.abort_file)
        except OSError:
            pass
