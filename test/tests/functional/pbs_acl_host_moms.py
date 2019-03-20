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


class Test_acl_host_moms(TestFunctional):
    """
    This test suite is for testing the server attribute acl_host_moms_enable
    and this test requires two moms.
    """

    def setUp(self):
        """
        Determine the remote host and set acl_host_enable = True
        """

        TestFunctional.setUp(self)

        usage_string = 'test requires a MoM and a client as input, ' + \
                       ' use -p moms=<mom>,client=<client>'

        # PBSTestSuite returns the moms passed in as parameters as dictionary
        # of hostname and MoM object
        self.momA = self.moms.values()[0]
        self.momA.delete_vnode_defs()

        self.hostA = self.momA.shortname
        if not self.du.is_localhost(self.server.client):
            # acl_hosts expects FQDN
            self.hostB = socket.getfqdn(self.server.client)
        else:
            self.skip_test(usage_string)

        self.remote_host = None

        if not self.du.is_localhost(self.hostA):
            self.remote_host = self.hostA
        else:
            self.skip_test(usage_string)

        self.assertTrue(self.remote_host)

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_hosts': self.hostB})
        self.server.manager(MGR_CMD_SET, SERVER, {'acl_host_enable': True})

        self.pbsnodes_cmd = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'pbsnodes') + ' -av'

        self.qstat_cmd = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin', 'qstat')

    def test_acl_host_moms_enable(self):
        """
        Set acl_host_moms_enable = True and check whether or not the remote
        host is able run pbsnodes and qstat.
        """

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': True})
        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertEqual(ret['rc'], 0)

        ret = self.du.run_cmd(self.remote_host, cmd=self.qstat_cmd)
        self.assertEqual(ret['rc'], 0)

    def test_acl_host_moms_disable(self):
        """
        Set acl_host_moms_enable = False and check whether or not the remote
        host is forbidden to run pbsnodes and qstat.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': False})

        ret = self.du.run_cmd(self.remote_host, cmd=self.pbsnodes_cmd)
        self.assertNotEqual(ret['rc'], 0)

        ret = self.du.run_cmd(self.remote_host, cmd=self.qstat_cmd)
        self.assertNotEqual(ret['rc'], 0)

    def test_acl_host_moms_hooks_and_jobs(self):
        """
        Use hooks to test whether remote host is able to run pbs.server()
        and check whether the job that is submitted goes to the 'R' state.
        """
        hook_name = "hook_acl_host_moms_t"
        hook_body = """
import pbs
e = pbs.event()
svr = pbs.server().server_state
e.accept()
"""
        try:
            self.server.manager(MGR_CMD_DELETE, HOOK, None, hook_name)
        except Exception:
            pass

        a = {'event': 'execjob_begin', 'enabled': 'True'}
        self.server.create_import_hook(
            hook_name, a, hook_body, overwrite=True)

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': False})

        j = Job()
        j.set_sleep_time(10)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'H'}, id=jid)

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': True})
        j = Job()
        j.set_sleep_time(10)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_acl_host_mom_queue_access(self):
        """
        Test that remote host cannot submit jobs to queue where
        acl_host_enable is True and acl_host_moms_enable is set
        on server, but remote host is not added in acl_hosts.
        """
        queue_n = 'tempq'
        queue_params = {'queue_type': 'Execution', 'enabled': 'True',
                        'started': 'True', 'acl_host_enable': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, queue_params, id='tempq')

        self.server.manager(MGR_CMD_SET, SERVER, {
                            'acl_host_moms_enable': True})
        # Setting acl_host_enable on queue overrides acl_host_moms_enable
        # on server and requires acl_hosts to include remote host's name.

        self.server.manager(MGR_CMD_SET, SERVER, {'flatuid': True})
        # Setting flatuid lets us submit jobs on server as a remote
        # host without creating a seperate user account there.
        qsub_cmd_on_queue = os.path.join(self.server.pbs_conf[
            'PBS_EXEC'], 'bin',
            'qsub') + ' -q ' + queue_n + ' -- /bin/sleep 10'

        j = Job(attrs={ATTR_queue: queue_n})
        j.set_sleep_time(10)
        cannot_submit = 0
        try:
            jid = self.server.submit(j)
        except PbsSubmitError:
            cannot_submit = 1
        self.assertEqual(cannot_submit, 1)
