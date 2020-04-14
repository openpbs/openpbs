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

    def setUp(self):
        TestFunctional.setUp(self)
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")

    def submit_job(self, set_attrib=None, exp_attrib=None, sleep=10,
                   job_script=False, interactive=False, client=None):
        """
        Submits job and check for the job attributes
        :param set_attrib: Job attributes to set
        :type set_attrib: Dictionary. Defaults to None
        :param exp_attrib: Job attributes to verify
        :type exp_attrib: Dictionary. Defaults to None
        :param sleep: Job's sleep time
        :type sleep: Integer. Defaults to 10s
        :param job_script: Whether to submit a job using job script
        :type job_script: Bool. Defaults to False
        :param interactive: Whether to submit a interactive job
        :type intercative: Bool. Defaults to False
        :param resv: Whether to submit reservation
        :type resv: Bool. Defaults to False
        """
        if client is None:
            client = self.server.client
        j = Job(TEST_USER)
        if set_attrib:
            j.set_attributes(set_attrib)
        if interactive:
            j.interactive_script = [('hostname', '.*'),
                                    ('export PATH=$PATH:%s' %
                                     self.exec_path, '.*'),
                                    ('qstat', '.*')]
        if job_script:
            pbsdsh_path = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                       "bin", "pbsdsh")
            script = "#!/bin/sh\n%s sleep %s" % (pbsdsh_path, sleep)
            j.create_script(script, hostname=client)
        else:
            j.set_sleep_time(sleep)
        jid = self.server.submit(j)
        if exp_attrib:
            self.server.expect(JOB, exp_attrib, id=jid)
        return jid

    def submit_resv(self, set_attrib=None, exp_attrib=None):
        """
        Submits reservation and check for the reservation attributes
        :param set_attrib: Reservation attributes to set
        :type set_attrib: Dictionary. Defaults to None
        :param exp_attrib: Reservation attributes to verify
        :type exp_attrib: Dictionary. Defaults to None
        """
        r = Reservation(TEST_USER)
        if set_attrib:
            r.set_attributes(set_attrib)
        rid = self.server.submit(r)
        if exp_attrib:
            self.server.expect(RESV, exp_attrib, id=rid)
        return rid

    def common_steps(self, job=False, interactive_job=False,
                     resv=False):
        """
        This function contains common steps of submitting
        different kind of jobs.
        :param job: Whether to submit job
        :type job: Bool. Defaults to False
        :param interactive_job: Whether to submit a interactive job
        :type intercative_job: Bool. Defaults to False
        :param resv: Whether to submit reservation
        :type resv: Bool. Defaults to False
        """
        if job:
            # Submit job
            jid = self.submit_job(set_attrib={ATTR_k: 'oe'},
                                  exp_attrib={'job_state': 'R'})
            self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
            self.server.log_match("%s;Exit_status=0" % jid)
            # Submit multi-chunk job
            set_attrib = {'Resource_List.select': '2:ncpus=1',
                          ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
            jid = self.submit_job(set_attrib, exp_attrib={'job_state': 'R'},
                                  job_script=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
            self.server.log_match("%s;Exit_status=0" % jid)
        if interactive_job:
            # Submit interactive job
            set_attrib = {'Resource_List.select': '2:ncpus=1',
                          ATTR_inter: '',
                          ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
            jid = self.submit_job(set_attrib, exp_attrib={'job_state': 'R'},
                                  interactive=True)
            self.server.expect(JOB, 'queue', id=jid, op=UNSET)
        if resv:
            # Submit reservation
            set_attrib = {'Resource_List.select': '2:ncpus=1',
                          ATTR_l + '.place': 'scatter',
                          'reserve_start': int(time.time() + 10),
                          'reserve_end': int(time.time() + 120)}
            exp_attrib = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
            rid = self.submit_resv(set_attrib, exp_attrib)
            resv_que = rid.split('.')[0]
            # Submit job into reservation
            set_attrib = {'Resource_List.select': '2:ncpus=1',
                          ATTR_q: resv_que, ATTR_k: 'oe',
                          ATTR_l + '.place': 'scatter'}
            jid = self.submit_job(set_attrib, job_script=True)
            # Wait for reservation to start
            a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
            self.server.expect(RESV, a, rid, offset=10)
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def pbs_restart(self, host_name):
        """
        This function starts PBS daemons after updating pbs.conf file
        :param host_name: Name of the host on which PBS
                          has to be restarted
        :type host_name: String
        """
        pi = PBSInitServices(hostname=host_name)
        pi.restart()

    def set_conf(self, host_name, conf_param):
        """
        This function sets attributes in pbs.conf file
        :param host_name: Name of the host on which pbs.conf
                          has to be updated
        :type host_name: String
        :param conf_param: Attributes to be updated in pbs.conf
        :type conf_param: Dictionary
        """
        pbsconfpath = self.du.get_pbs_conf_file(hostname=host_name)
        self.du.set_pbs_config(hostname=host_name, fin=pbsconfpath,
                               confs=conf_param)
        self.pbs_restart(host_name)

    def unset_pbs_conf(self, host_name, conf_param):
        """
        To functions unsets "PBS_LEAF_ROUTERS" from pbs.conf file
        """
        pbsconfpath = self.du.get_pbs_conf_file(hostname=host_name)
        self.du.unset_pbs_config(hostname=host_name,
                                 fin=pbsconfpath, confs=conf_param)
        self.pbs_restart(host_name)

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
        self.common_steps(job=True, interactive_job=True, resv=True)

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
        self.server.client = self.hostB
        self.common_steps(resv=True)

    @requirements(num_moms=2, num_comms=1, num_clients=1,
                  no_comm_on_server=True)
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
        self.set_conf(host_name=self.server.hostname, attribs=a)
        a = {'PBS_LEAF_ROUTERS': self.hostD}
        self.set_conf(host_name=self.hostC, attribs=a)
        self.common_steps(job=True, resv=True)
        self.server.client = self.hostB
        self.common_steps(interactive_job=True)

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
        if len(self.moms) < 2 or self.server.shortname in self.moms.values():
            self.skip_test(reason=msg)
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        self.server.client = self.hostA
        self.common_steps(job=True, resv=True)
        self.server.client = self.hostB
        self.common_steps(job=True, interactive_job=True)

    def tearDown(self):
        TestFunctional.tearDown(self)
        conf_param = ['PBS_LEAF_ROUTERS']
        for host in self.node_list:
            self.unset_pbs_conf(host, conf_param)
        self.node_list.clear()
