# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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
# Altair's dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair's trademarks, including but not limited to "PBS.",
# "PBS Professional®", and "PBS Pro." and Altair's logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *
import socket


@tags('comm')
class TestTPP(TestFunctional):
    """
    Test suite consists of tests to check the functionality of pbs_comm daemon
    """
    node_list = []
    default_client = None

    def setUp(self):
        TestFunctional.setUp(self)
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.pbs_conf_path = self.du.get_pbs_conf_file(
            hostname=self.server.hostname)
        msg = "Unable to retrieve pbs.conf file path"
        self.assertNotEqual(self.pbs_conf_path, None, msg)

        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        if not self.default_client:
            self.default_client = self.server.client

    def pbs_restart(self, host_name):
        """
        This function starts PBS daemons
        :param host_name: Name of the host on which PBS
                          has to be restarted
        :type host_name: String
        """
        pi = PBSInitServices(hostname=host_name)
        pi.restart()

    def set_pbs_conf(self, host_name, conf_param):
        """
        This function sets attributes in pbs.conf file
        :param host_name: Name of the host on which pbs.conf
                          has to be updated
        :type host_name: String
        :param conf_param: Parameters to be updated in pbs.conf
        :type conf_param: Dictionary
        """
        pbsconfpath = self.du.get_pbs_conf_file(hostname=host_name)
        self.du.set_pbs_config(hostname=host_name, fin=pbsconfpath,
                               confs=conf_param)
        self.pbs_restart(host_name)

    def unset_pbs_conf(self, host_name, conf_param):
        """
        This function unsets parameters in pbs.conf file
        :param host_name: Name of the host on which pbs.conf
                          has to be updated
        :type host_name: String
        :param conf_param: Parameters to be removed from pbs.conf
        :type conf_param: List
        """
        pbsconfpath = self.du.get_pbs_conf_file(hostname=host_name)
        self.du.unset_pbs_config(hostname=host_name,
                                 fin=pbsconfpath, confs=conf_param)
        self.pbs_restart(host_name)

    def submit_resv(self, resv_set_attr=None, resv_exp_attr=None):
        """
        Submits reservation and check for the reservation attributes
        :param resv_set_attr: Reservation attributes to set
        :type resv_set_attr: Dictionary. Defaults to None
        :param resv_exp_attrib: Reservation attributes to verify
        :type resv_exp_attrib: Dictionary. Defaults to None
        """
        r = Reservation(TEST_USER)
        if resv_set_attr is None:
            resv_set_attr = {'Resource_List.select': '2:ncpus=1',
                             ATTR_l + '.place': 'scatter',
                             'reserve_start': int(time.time() + 10),
                             'reserve_end': int(time.time() + 120)}
        r.set_attributes(resv_set_attr)
        rid = self.server.submit(r)
        if not resv_exp_attr:
            resv_exp_attr = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, resv_exp_attr, id=rid)
        return rid

    def submit_job(self, set_attr=None, exp_attr=None, job=False,
                   job_script=False, interactive=False, rid=None,
                   resv_job=False, sleep=10):
        """
        Submits job and check for the job attributes
        :param set_attr: Job attributes to set
        :type set_attr: Dictionary. Defaults to None
        :param exp_attr: Job attributes to verify
        :type exp_attr: Dictionary. Defaults to None
        :param job: Whether to submit a multi chunk job
        :type job: Bool. Defaults to False
        :param job_script: Whether to submit a job using job script
        :type job_script: Bool. Defaults to False
        :param interactive: Whether to submit a interactive job
        :type interactive: Bool. Defaults to False
        :param rid: Reservation id
        :type rid: String
        :param resv_job: Whether to submit job into reservation.
        :type resv_job: Bool. Defaults to False
        :param sleep: Job's sleep time
        :type sleep: Integer. Defaults to 10s
        """
        j = Job(TEST_USER)
        if set_attr is None:
            set_attr = {'Resource_List.select': '2:ncpus=1',
                        ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        if job:
            j.set_attributes(set_attr)

        if interactive:
            set_attr[ATTR_inter] = ''
            j.set_attributes(set_attr)
            j.interactive_script = [('hostname', '.*'),
                                    ('export PATH=$PATH:%s' %
                                     self.exec_path, '.*'),
                                    ('qstat', '.*')]
        if resv_job:
            if 'ATTR_inter' in set_attr:
                del set_attr[ATTR_inter]
            resv_que = rid.split('.')[0]
            set_attr[ATTR_q] = resv_que
            j.set_attributes(set_attr)

        if job_script:
            pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                       "bin", "pbsdsh")
            script = "#!/bin/sh\n%s sleep %s" % (pbsdsh_path, sleep)
            j.create_script(script, hostname=self.server.client)
        else:
            j.set_sleep_time(sleep)

        jid = self.server.submit(j)
        if exp_attr is None:
            exp_attr = {'job_state': 'R'}
        if resv_job:
            offset = 10
        else:
            offset = 1
        self.server.expect(JOB, exp_attr, offset=offset, id=jid)
        return jid

    def common_steps(self, set_attr=None, exp_attr=None, job=False,
                     interactive=False, resv=False,
                     resv_set_attr=None, resv_exp_attr=None,
                     resv_job=False, client=None):
        """
        This function contains common steps of submitting
        different kind of jobs.
        Submits job and check for the job attributes
        :param set_attr: Job attributes to set
        :type set_attr: Dictionary. Defaults to None
        :param exp_attr: Job attributes to verify
        :type exp_attr: Dictionary. Defaults to None
        :param job: Whether to submit a multi chunk job
        :type job: Bool. Defaults to False
        :param interactive: Whether to submit a interactive job
        :type interactive: Bool. Defaults to False
        :param resv: Whether to submit reservation.
        :type resv: Bool. Defaults to False
        :param resv_set_attr: Reservation attributes to set
        :type resv_set_attr: Dictionary. Defaults to None
        :param resv_exp_attrib: Reservation attributes to verify
        :type resv_exp_attrib: Dictionary. Defaults to None
        :param resv_job: Whether to submit job into reservation.
        :type resv_job: Bool. Defaults to False
        :param client: Name of the client
        :type client: String. Defaults to None
        """
        if client is None:
            self.server.client = self.server.hostname
        else:
            self.server.client = client
        if job:
            jid = self.submit_job(
                set_attr, exp_attr, job=True, job_script=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
            self.server.log_match("%s;Exit_status=0" % jid)
        if interactive:
            # Submit Interactive Job
            jid = self.submit_job(set_attr, exp_attr, interactive=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET)
        if resv:
            # Submit reservation
            rid = self.submit_resv(resv_set_attr, resv_exp_attr)
            jid = self.submit_job(set_attr, exp_attr, resv_job=True,
                                  rid=rid, job_script=True)
            # Wait for reservation to start
            a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.server.expect(RESV, a, rid, offset=10)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
            self.server.log_match("%s;Exit_status=0" % jid)

    @requirements(num_moms=2)
    def test_comm_with_mom(self):
        """
        This test verifies communication between server-mom and
        between moms through pbs_comm
        Configuration:
        Node 1 : Server, Mom, Sched, Comm
        Node 2 : Mom
        """
        log_msgs = ["TPP initialization done",
                    "Single pbs_comm configured, " +
                    "TPP Fault tolerant mode disabled",
                    "Connected to pbs_comm %s.*:17001" % self.server.shortname]
        for msg in log_msgs:
            self.server.log_match(msg, regexp=True)
            self.scheduler.log_match(msg, regexp=True)
            for mom in self.moms.values():
                self.mom.log_match(msg, regexp=True)
        server_ip = socket.gethostbyname(self.server.hostname)
        msg = "Registering address %s:15001 to pbs_comm" % server_ip
        self.server.log_match(msg)
        msg = "Registering address %s:15004 to pbs_comm" % server_ip
        self.scheduler.log_match(msg)
        for mom in self.moms.values():
            ip = socket.gethostbyname(mom.shortname)
            msg1 = "Registering address %s:15003 to pbs_comm" % ip
            msg2 = "Leaf registered address %s:15003" % ip
            mom.log_match(msg1)
            self.comm.log_match(msg2)
        self.common_steps(job=True, interactive=True, resv=True,
                          resv_job=True)

    @skip(reason="Run this through cmd-line by removing this decorator")
    @requirements(num_moms=2, num_clients=1)
    def test_client_with_mom(self):
        """
        This test verifies communication between server-mom,
        server-client and between moms through pbs_comm
        Configuration:
        Node 1 : Server, Mom, Sched, Comm
        Node 2 : Mom
        Node 3 : Client
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.server.client
        nodes = [self.hostA, self.hostB, self.hostC]
        self.node_list.extend(nodes)
        self.server.manager(MGR_CMD_SET, SERVER, {'flatuid': True})
        self.common_steps(job=True, interactive=True)
        self.common_steps(resv=True, resv_job=True, client=self.hostB)

    @skip(reason="Run this through cmd-line by removing this decorator")
    @requirements(num_moms=2, num_clients=1, num_comms=1)
    def test_comm_non_server_host(self):
        """
        This test verifies communication between server-mom,
        server-client and between moms through pbs_comm which
        is running on non server host
        Configuration:
        Node 1 : Server, Mom, Sched
        Node 2 : Client
        Node 3 : Mom
        Node 4 : Comm
        """
        msg = "Need atleast 2 moms and a comm installed on host"
        msg += " other than server host"
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.comm1 = self.comms.values()[0]
        self.hostA = self.momA.shortname
        self.hostB = self.server.client
        self.hostC = self.momB.shortname
        self.hostD = self.comm1.shortname
        nodes = [self.hostA, self.hostB, self.hostC, self.hostD]
        self.node_list.extend(nodes)
        a = {'PBS_START_COMM': '0', 'PBS_START_MOM': '1',
             'PBS_LEAF_ROUTERS': self.hostD}
        b = {'PBS_LEAF_ROUTERS': self.hostD}
        hosts = [self.hostA, self.hostB, self.hostC]
        moms = [self.hostA, self.hostC]
        if self.server.shortname not in hosts:
            hosts.append(self.server.shortname)
        for host in hosts:
            if host == self.server.shortname and host in moms:
                self.set_pbs_conf(host_name=host, conf_param=a)
            elif host == self.server.shortname and \
                    host not in self.moms.values():
                a['PBS_START_MOM'] = "0"
                self.set_pbs_conf(host_name=host, conf_param=a)
            else:
                self.set_pbs_conf(host_name=host, conf_param=b)
        self.common_steps(job=True, resv=True, resv_job=True)
        self.common_steps(interactive=True, client=self.hostB)

    @requirements(num_moms=2, no_mom_on_server=True)
    def test_mom_non_server_host(self):
        """
        This test verifies communication between server-mom,
        between moms which are running on non server host
        through pbs_comm.
        Configuration:
        Node 1 : Server, Sched, Comm
        Node 2 : Mom
        Node 3 : Mom
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        nodes = [self.hostA, self.hostB]
        self.node_list.extend(nodes)
        msg = "Requires mom which is running on non server host"
        self.common_steps(job=True, resv=True,
                          resv_job=True, client=self.hostA)
        self.common_steps(job=True, interactive=True,
                          client=self.hostB)

    def test_comm_with_vnode_insertion(self):
        """
        Test for verifying vnode insertion when using TPP
        """
        if not self.mom.is_cpuset_mom():
            a = {'resources_available.ncpus': 1}
            self.server.create_vnodes('vn', a, 2, self.mom)
            vnode_val = "vnode=vn[0]:ncpus=1+vnode=vn[1]:ncpus=1"
        else:
            vnode_val = "vnode=%s:ncpus=1" % self.server.status(NODE)[1]['id']
            vnode_val += "+vnode=%s:ncpus=1" % self.server.status(NODE)[
                2]['id']
        set_attr = {'Resource_List.select': vnode_val,
                    ATTR_k: 'oe'}
        self.common_steps(job=True, set_attr=set_attr)
        self.comm.stop('KILL')
        if self.mom.is_cpuset_mom():
            vnode_list = [self.server.status(NODE)[1]['id'],
                          self.server.status(NODE)[2]['id']]
        else:
            vnode_list = ["vn[0]", "vn[1]"]
        for vnode in vnode_list:
            self.server.expect(VNODE, {
                'state': 'state-unknown,down'}, id=vnode)

    @requirements(num_moms=2, num_comms=2)
    def test_multiple_comm_with_mom(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        Configuration:
        Node 1 : Server, Sched, Comm
        Node 2 : Mom
        Node 3 : Mom
        Node 4 : Comm
        """
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.comm1 = self.comms.values()[0]
        self.comm2 = self.comms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.comm1.shortname
        self.hostD = self.comm2.shortname
        nodes = [self.hostA, self.hostB, self.hostC, self.hostD]
        self.node_list.extend(nodes)
        hosts = [self.hostA, self.hostB]
        if self.server.shortname not in hosts:
            hosts.append(self.server.shortname)
        a = {'PBS_COMM_ROUTERS': self.hostA}
        b = {'PBS_LEAF_ROUTERS': self.hostD}
        self.set_pbs_conf(host_name=self.hostD, conf_param=a)
        for host in hosts:
            self.set_pbs_conf(host_name=host, conf_param=b)
        self.common_steps(job=True, interactive=True, resv=True,
                          resv_job=True)

    def tearDown(self):
        TestFunctional.tearDown(self)
        conf_param = ['PBS_LEAF_ROUTERS', 'PBS_COMM_ROUTERS']
        for host in self.node_list:
            self.unset_pbs_conf(host, conf_param)
        self.node_list.clear()
        self.server.client = self.default_client
