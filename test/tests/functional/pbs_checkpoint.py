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


from tests.functional import *
from ptl.utils.pbs_crayutils import CrayUtils


class TestCheckpoint(TestFunctional):
    """
    This test suite targets Checkpoint functionality.
    """
    abort_file = ''
    cu = CrayUtils()

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        abort_script = """#!/bin/bash
kill $1
exit 0
"""
        self.abort_file = self.du.create_temp_file(body=abort_script)
        self.du.chmod(path=self.abort_file, mode=0o755)
        self.du.chown(path=self.abort_file, uid=0, gid=0, runas=ROOT_USER)
        c = {'$action': 'checkpoint_abort 30 !' + self.abort_file + ' %sid'}
        self.mom.add_config(c)
        self.platform = self.du.get_platform()
        if self.platform != 'cray' and self.platform != 'craysim':
            self.attrs = {ATTR_l + '.select': '1:ncpus=1',
                          ATTR_l + '.place': 'excl'}
        else:
            nv = self.cu.num_compute_vnodes(self.server)
            self.assertNotEqual(nv, 0, "No cray_compute vnodes are present.")
            self.attrs = {ATTR_l + '.select': '%d:ncpus=1' % nv,
                          ATTR_l + '.place': 'scatter'}

    def verify_checkpoint_abort(self, jid, stime):
        """
        Verify that checkpoint and abort happened.
        """
        self.ck_dir = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                   'checkpoint', jid + '.CK')
        self.assertTrue(self.du.isdir(path=self.ck_dir, runas=ROOT_USER),
                        msg="Checkpoint directory %s not found" % self.ck_dir)
        _msg1 = "%s;req_holdjob: Checkpoint initiated." % jid
        self.mom.log_match(_msg1, starttime=stime)
        _msg2 = "%s;checkpoint_abort script %s: exit code 0" % (
            jid, self.abort_file)
        self.mom.log_match(_msg2, starttime=stime)
        _msg3 = "%s;checkpointed to %s" % (jid, self.ck_dir)
        self.mom.log_match(_msg3, starttime=stime)
        _msg4 = "%s;task 00000001 terminated" % jid
        self.mom.log_match(_msg4, starttime=stime)

    def start_server_hot(self):
        """
        Start the server with the hot option.
        """
        pbs_exec = self.server.pbs_conf['PBS_EXEC']
        svrname = self.server.pbs_server_name
        pbs_server_hot = [os.path.join(
            pbs_exec, 'sbin', 'pbs_server'), '-t', 'hot']
        self.du.run_cmd(svrname, cmd=pbs_server_hot, sudo=True)
        self.assertTrue(self.server.isUp())

    def checkpoint_abort_with_qterm_restart_hot(self, qterm_type):
        """
        Checkpointing with qterm -t <type>, hot server restart.
        """

        j1 = Job(TEST_USER, self.attrs)
        j1.set_sleep_time(20)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        start_time = int(time.time())
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        self.server.qterm(manner=qterm_type)

        self.verify_checkpoint_abort(jid1, start_time)

        self.start_server_hot()
        self.assertTrue(self.server.isUp())

        msg = "%s;Requeueing job, substate: 10 Requeued in queue: workq" % jid1
        self.server.log_match(msg, starttime=start_time)

        # wait for the server to hot start the job
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1, interval=2)
        self.server.expect(JOB, 'exec_vnode', id=jid1, op=SET)
        self.assertFalse(os.path.exists(self.ck_dir),
                         msg=self.ck_dir + " still exists")
        self.server.expect(JOB, {'job_state': 'F'},
                           jid1, extend='x', interval=5)

    def test_checkpoint_abort_with_preempt(self):
        """
        This test verifies that checkpoint_abort works as expected when
        a job is preempted via checkpoint. It does so by submitting a job
        in express queue which preempts a running job in the default queue.
        """
        self.server.manager(MGR_CMD_SET, SCHED, {'preempt_order': 'C'},
                            runas=ROOT_USER)
        a = {'queue_type': 'execution',
             'started': 'True',
             'enabled': 'True',
             'Priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "expressq")

        j1 = Job(TEST_USER, self.attrs)
        j1.set_sleep_time(20)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        self.attrs['queue'] = 'expressq'
        j2 = Job(TEST_USER, self.attrs)
        j2.set_sleep_time(20)
        start_time = int(time.time())
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)

        self.verify_checkpoint_abort(jid1, start_time)

        self.server.expect(JOB, {'job_state': 'F'},
                           jid2, extend='x', interval=5)
        self.server.expect(JOB, {'job_state': 'F'},
                           jid1, extend='x', interval=5)

    def test_checkpoint_abort_with_qhold(self):
        """
        This test uses qhold for checkpointing.
        """
        j1 = Job(TEST_USER, self.attrs)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        start_time = int(time.time())
        self.server.holdjob(jid1)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid1)

        self.verify_checkpoint_abort(jid1, start_time)

    def test_checkpoint_abort_with_qterm_immediate_restart_hot(self):
        """
        This tests checkpointing with qterm -t immediate, hot server restart.
        """
        self.checkpoint_abort_with_qterm_restart_hot("immediate")

    def test_checkpoint_abort_with_qterm_delay_restart_hot(self):
        """
        This tests checkpointing with qterm -t delay, hot server restart.
        """
        self.checkpoint_abort_with_qterm_restart_hot("delay")

    def tearDown(self):
        TestFunctional.tearDown(self)
        try:
            os.remove(self.abort_file)
        except OSError:
            pass
