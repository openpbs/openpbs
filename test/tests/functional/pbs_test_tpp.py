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
# Altair.s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair.s trademarks, including but not limited to "PBS.",
# "PBS Professional®", and "PBS Pro." and Altair.s logos is subject to Altair's
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
        self.pbs_conf_path = self.du.get_pbs_conf_file(hostname=self.server.hostname)
        msg = "Unable to retrieve pbs.conf file path"
        self.assertNotEqual(self.pbs_conf_path, None, msg)

        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")
        if not self.default_client:
            self.default_client = self.server.client

    def pbs_restart(self, host_name):
        """
        This function starts PBS daemons after updating pbs.conf file
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

    def submit_job(self, job=False, jset_attrib=None, jexp_attrib=None,
                   sleep=10, job_script=False, interactive=False,
                   iset_attrib=None, iexp_attrib=None, resv_job=False,
                   rid=None, rjset_attrib=None, rjexp_attrib=None):
        """
        Submits job and check for the job attributes
        :param job: Whether to submit a multi chunk job
        :type job: Bool. Defaults to False
        :param jset_attrib: Job attributes to set
        :type jset_attrib: Dictionary. Defaults to None
        :param jexp_attrib: Job attributes to verify
        :type jexp_attrib: Dictionary. Defaults to None
        :param sleep: Job's sleep time
        :type sleep: Integer. Defaults to 10s
        :param job_script: Whether to submit a job using job script
        :type job_script: Bool. Defaults to False
        :param interactive: Whether to submit a interactive job
        :type interactive: Bool. Defaults to False
        :param iset_attrib: Interactive Job attributes to set
        :type iset_attrib: Dictionary. Defaults to None
        :param iexp_attrib: Interactive Job attributes to verify
        :type iexp_attrib: Dictionary. Defaults to None
        :param resv_job: Whether to submit job into reservation.
        :type resv_job: Bool. Defaults to False
        :param rid: Reservation id
        :type rid: String
        :param rjset_attrib: Reservation Job attributes to set
        :type rjset_attrib: Dictionary. Defaults to None
        :param rjexp_attrib: Reservation Job attributes to verify
        :type rjexp_attrib: Dictionary. Defaults to None
        """
        j = Job(TEST_USER)
        if job:
            if not jset_attrib:
                jset_attrib = {'Resource_List.select': '2:ncpus=1',
                                 ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
            j.set_attributes(jset_attrib)
            if not jexp_attrib:
               exp_attrib = {'job_state': 'R'}
            else:
               exp_attrib = jexp_attrib

        if interactive:
            if not iset_attrib:
                iset_attrib = {'Resource_List.select': '2:ncpus=1',
                               ATTR_inter: '',
                               ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
            j.set_attributes(iset_attrib)
            j.interactive_script = [('hostname', '.*'),
                                    ('export PATH=$PATH:%s' %
                                     self.exec_path, '.*'),
                                    ('qstat', '.*')]
            if not iexp_attrib:
               exp_attrib = {'job_state': 'R'}
            else:
               exp_attrib = iexp_attrib

        if resv_job:
            resv_que = rid.split('.')[0]
            if not rjset_attrib:
                rjset_attrib = {'Resource_List.select': '2:ncpus=1',
                                ATTR_q: resv_que, ATTR_k: 'oe',
                                ATTR_l + '.place': 'scatter'}
            j.set_attributes(rjset_attrib)
            if not rjexp_attrib:
               exp_attrib = {'job_state': 'Q'}
            else:
               exp_attrib = rjexp_attrib

        if job_script:
            pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                       "bin", "pbsdsh")
            script = "#!/bin/sh\n%s sleep %s" % (pbsdsh_path, sleep)
            j.create_script(script, hostname=self.server.client)
        else:
            j.set_sleep_time(sleep)

        jid = self.server.submit(j)
        self.server.expect(JOB, exp_attrib, id=jid)
        return jid

    def submit_resv(self, rset_attrib=None, rexp_attrib=None):
        """
        Submits reservation and check for the reservation attributes
        :param rset_attrib: Reservation attributes to set
        :type rset_attrib: Dictionary. Defaults to None
        :param rexp_attrib: Reservation attributes to verify
        :type rexp_attrib: Dictionary. Defaults to None
        """
        r = Reservation(TEST_USER)
        if not rset_attrib:
            rset_attrib = {'Resource_List.select': '2:ncpus=1',
                           ATTR_l + '.place': 'scatter',
                           'reserve_start': int(time.time() + 10),
                           'reserve_end': int(time.time() + 120)}
        r.set_attributes(rset_attrib)
        rid = self.server.submit(r)
        if not rexp_attrib:
            rexp_attrib = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, rexp_attrib, id=rid)
        return rid

    def common_steps(self, jset_attrib=None, jexp_attrib=None, job=False,
                     iset_attrib=None, iexp_attrib=None, interactive_job=False,
                     rset_attrib=None, rexp_attrib=None, rjset_attrib=None,
                     rjexp_attrib=None, resv=False, resv_job=False, client=None):
        """
        This function contains common steps of submitting
        different kind of jobs.
        Submits job and check for the job attributes
        :param jset_attrib: Job attributes to set
        :type jset_attrib: Dictionary. Defaults to None
        :param jexp_attrib: Job attributes to verify
        :type jexp_attrib: Dictionary. Defaults to None
        :param job: Whether to submit a multi chunk job
        :type job: Bool. Defaults to False
        :param iset_attrib: Interactive Job attributes to set
        :type iset_attrib: Dictionary. Defaults to None
        :param iexp_attrib: Interactive Job attributes to verify
        :type iexp_attrib: Dictionary. Defaults to None
        :param interactive: Whether to submit a interactive job
        :type interactive: Bool. Defaults to False
        :param rset_attrib: Reservation attributes to set
        :type rset_attrib: Dictionary. Defaults to None
        :param rexp_attrib: Reservation attributes to verify
        :type rexp_attrib: Dictionary. Defaults to None
        :param resv: Whether to submit reservation.
        :type resv: Bool. Defaults to False
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
            jid = self.submit_job(job=True, jset_attrib=jset_attrib,
                                  jexp_attrib=jexp_attrib, job_script=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
            self.server.log_match("%s;Exit_status=0" % jid)
        if interactive_job:
            # Submit Interactive Job
            jid = self.submit_job(iset_attrib=iset_attrib,
                                  iexp_attrib=iexp_attrib, interactive=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET)
        if resv:
            # Submit reservation
            rid = self.submit_resv(rset_attrib=rset_attrib, rexp_attrib=rexp_attrib)
            jid = self.submit_job(resv_job=True, rid=rid, rjset_attrib=rjset_attrib,
                                  rjexp_attrib=rjexp_attrib, job_script=True)
            # Wait for reservation to start
            a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.server.expect(RESV, a, rid, offset=10)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
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
        msg = "Need atleast 2 moms as input. use -pmoms=<m1>:<m2>"
        if len(self.moms) < 2:
            self.skip_test(reason=msg)
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
        self.common_steps(job=True, interactive_job=True, resv=True,
                          resv_job=True)

    @requirements(num_moms=2, num_comms=1, num_clients=1)
    def test_client_with_mom(self):
        """
        This test verifies communication between server-mom,
        server-client and between moms through pbs_comm
        Configuration:
        Node 1 : Server, Mom, Sched, Comm
        Node 2 : Mom
        Node 3 : Client
        """
        msg = "Need atleast 2 moms and 1 client as input. "
        msg += "use -pmoms=<m1>:<m2>,client=<c1>"
        if len(self.moms) < 2 and self.server.client == self.server.hostname:
            self.skip_test(reason=msg)
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.server.client
        nodes = [self.hostA, self.hostB, self.hostC]
        self.node_list.extend(nodes)
        self.server.manager(MGR_CMD_SET, SERVER, {'flatuid': True})
        self.common_steps(job=True, interactive_job=True)
        self.common_steps(resv=True, resv_job=True, client=self.hostB)

    @requirements(num_moms=2, num_comms=1, num_clients=1)
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
        if len(self.moms) < 2 or len(self.comms) < 1:
            self.skip_test(reason=msg)
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
                elif host == self.server.shortname and host not in self.moms.values():
                    a['PBS_START_MOM'] = "0"
                    self.set_pbs_conf(host_name=host, conf_param=a)
                else:
                    self.set_pbs_conf(host_name=host, conf_param=b)
        self.common_steps(job=True, resv=True, resv_job=True)
        self.common_steps(interactive_job=True, client=self.hostB)

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
        msg = "Need atleast 2 moms which are running on a "
        msg += " non server host"
        if len(self.moms) < 2:
            self.skip_test(reason=msg)
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        nodes = [self.hostA, self.hostB]
        self.node_list.extend(nodes)
        msg = "Requires mom which is running on non server host"
        if self.server.shortname in nodes:
            self.skip_test(reason=msg)
        self.common_steps(job=True, resv=True,
                           resv_job=True, client=self.hostA)
        self.common_steps(job=True, interactive_job=True,
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
            vnode_val += "+vnode=%s:ncpus=1" % self.server.status(NODE)[2]['id']
        set_attrib = {'Resource_List.select': vnode_val,
                       ATTR_k: 'oe'}
        self.common_steps(job=True, jset_attrib=set_attrib)
        self.comm.stop('KILL')
        if self.mom.is_cpuset_mom():
            vnode_list = [self.server.status(NODE)[1]['id'],
                          self.server.status(NODE)[2]['id']]
        else:
            vnode_list = ["vn[0]", "vn[1]"]
        for vnode in vnode_list:
            self.server.expect(VNODE, {'state': 'state-unknown,down'}, id=vnode)
        
    @requirements(num_moms=2, num_comms=1)
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
        msg = "Need atleast 2 moms as input. use -pmoms=<m1>:<m2>"
        if len(self.moms) < 2:
            self.skip_test(reason=msg)
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.comm1 = self.comms.values()[0]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.hostC = self.comm1.shortname
        nodes = [self.hostA, self.hostB, self.hostC]
        self.node_list.extend(nodes)
        hosts = [self.hostA, self.hostB]
        if self.server.shortname not in hosts:
            hosts.append(self.server.shortname)
        a = {'PBS_START_COMM': '0', 'PBS_START_MOM': '1',
             'PBS_LEAF_ROUTERS': self.hostC}
        b = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=b)
        for host in hosts:
                if host == self.server.shortname and host not in self.moms.values():
                    a['PBS_START_MOM'] = "0"
                    self.set_pbs_conf(host_name=host, conf_param=a)
                else:
                    self.set_pbs_conf(host_name=host, conf_param=b)
        self.common_steps(job=True, interactive_job=True, resv=True,
                          resv_job=True)
 
    def tearDown(self):
        TestFunctional.tearDown(self)
        conf_param = ['PBS_LEAF_ROUTERS', 'PBS_COMM_ROUTERS']
        for host in self.node_list:
            self.unset_pbs_conf(host, conf_param)
        self.node_list.clear()
        self.server.client = self.default_client

