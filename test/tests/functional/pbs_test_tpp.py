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
            resv_set_attr = {ATTR_l + '.select': '2:ncpus=1',
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
        offset = 1
        if set_attr is None:
            set_attr = {ATTR_l + '.select': '2:ncpus=1',
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
            if ATTR_inter in set_attr:
                del set_attr[ATTR_inter]
            resv_que = rid.split('.')[0]
            set_attr[ATTR_q] = resv_que
            j.set_attributes(set_attr)
            offset = 10

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
            self.server.expect(RESV, a, rid)
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
        set_attr = {ATTR_l + '.select': vnode_val,
                    ATTR_k: 'oe'}
        self.common_steps(job=True, set_attr=set_attr)
        self.comm.stop('-KILL')
        if self.mom.is_cpuset_mom():
            vnode_list = [self.server.status(NODE)[1]['id'],
                          self.server.status(NODE)[2]['id']]
        else:
            vnode_list = ["vn[0]", "vn[1]"]
        a = {'state': (MATCH_RE, "down")}
        for vnode in vnode_list:
            self.server.expect(VNODE, a, id=vnode)

    def common_setup(self):
        """
        This function sets the shortnames of moms and comms in the cluster
        accordingly.
        Mom objects : self.momA, self.momB, self.momC
        Mom shortnames : self.hostA, self.hostB, self.hostC
        comm objects : self.comm2, self.comm3
        comm shortnames : self.hostD, self.hostE
        """
        mom_list = [x.shortname for x in self.moms.values()]
        comm_list = [y.shortname for y in self.comms.values()]
        if self.server.shortname not in mom_list or \
           self.server.shortname not in comm_list:
            self.skipTest("Mom and comm should be on server host")
        if len(self.moms.values()) == 2 and len(self.comms.values()) == 2:
            self.hostA = self.server.shortname
            self.momB = self.moms.values()[1]
            self.hostB = self.momB.shortname
            self.comm2 = self.comms.values()[1]
            self.hostC = self.comm2.shortname
            nodes = [self.hostA, self.hostB, self.hostC]
        elif len(self.moms.values()) == 3 and len(self.comms.values()) == 3:
            self.hostA = self.server.shortname
            self.momB = self.moms.values()[1]
            self.hostB = self.momB.shortname
            self.momC = self.moms.values()[2]
            self.hostC = self.momC.shortname
            self.comm2 = self.comms.values()[1]
            self.hostD = self.comm2.shortname
            self.comm3 = self.comms.values()[2]
            self.hostE = self.comm3.shortname
            nodes = [
                self.hostA,
                self.hostB,
                self.hostC,
                self.hostD,
                self.hostE]
        self.node_list.extend(nodes)

    @requirements(num_moms=2, num_comms=2)
    def test_multiple_comm_with_mom(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        b = {'PBS_LEAF_ROUTERS': self.hostC}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.common_steps(job=True, interactive=True, resv=True,
                          resv_job=True)

    def common_steps_for_comm_failover(self):
        """
        This function has common steps for comm failover used in
        diff tests
        """
        self.common_steps(job=True, interactive=True)
        rid = self.submit_resv()
        jid = self.submit_job(rid=rid, resv_job=True, sleep=60)
        resv_exp_attrib = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|5')}
        self.server.expect(RESV, resv_exp_attrib, rid, offset=10)
        job_exp_attrib = {'job_state': 'R'}
        self.server.expect(JOB, job_exp_attrib, id=jid)
        self.comm2.stop('-KILL')
        for mom in self.moms.values():
            self.server.expect(NODE, {'state': 'free'}, id=mom.shortname)
        self.server.expect(RESV, resv_exp_attrib, rid)
        self.server.expect(JOB, job_exp_attrib, id=jid)
        self.comm2.start()
        self.comm.stop('-KILL')
        for mom in self.moms.values():
            self.server.expect(NODE, {'state': 'free'}, id=mom.shortname)
        self.server.expect(RESV, resv_exp_attrib, rid)
        self.server.expect(JOB, job_exp_attrib, id=jid)

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        leaf_val = self.hostA + "," + self.hostC
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + self.hostA
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.common_steps_for_comm_failover()

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover_with_invalid_values(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when values of PBS_LEAF_ROUTERS
        in pbs.conf are invalid
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        # set a valid hostname but invalid PBS_LEAF_ROUTERS value
        param = {'PBS_LEAF_ROUTERS': self.hostB}
        self.set_pbs_conf(host_name=self.hostB, conf_param=param)
        self.server.expect(NODE, {'state': 'down'}, id=self.hostB)
        # set a invalid PBS_LEAF_ROUTERS value for secondary comm
        invalid_val = self.hostA + "XXXX"
        leaf_val = self.hostC + "," + invalid_val
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.comm2.stop('-KILL')
        self.server.expect(NODE, {'state': 'down'}, id=self.hostB)
        exp_msg = ["Error 99 while connecting to %s:17001" % invalid_val,
                   "Error -2 resolving %s" % invalid_val
                   ]
        for msg in exp_msg:
            self.momB.log_match(msg)
        # set a invalid PBS_LEAF_ROUTERS value for primary comm
        leaf_val = invalid_val + "," + self.hostC
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        self.comm.stop('-KILL')
        self.server.expect(NODE,
                           {'state': 'state-unknown,down'},
                           id=self.hostA)
        for msg in exp_msg:
            self.momB.log_match(msg)
        # set a invalid port value for PBS_LEAF_ROUTERS
        invalid_val = self.hostA + ":1700"
        leaf_val = self.hostC + "," + invalid_val
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.comm2.stop('-KILL')
        self.server.expect(NODE,
                           {'state': 'state-unknown,down'},
                           id=self.hostB)

        # set same value for secondary comm as primary in PBS_LEAF_ROUTERS
        leaf_val = self.hostC + "," + self.hostC
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.comm2.stop('-KILL')
        self.server.expect(NODE,
                           {'state': 'state-unknown,down'},
                           id=self.hostB)

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover_with_ipaddress(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when PBS_LEAF_ROUTERS has ipaddress as value
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        hostC_ip = socket.gethostbyname(self.hostC)
        a = {'PBS_COMM_ROUTERS': hostA_ip}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        leaf_val = hostA_ip + "," + hostC_ip
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = hostC_ip + "," + hostA_ip
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.common_steps_for_comm_failover()

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover_with_ipaddress_hostnames(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when PBS_LEAF_ROUTERS has ipaddress
        and hostname as values
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        hostC_ip = socket.gethostbyname(self.hostC)
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        leaf_val = self.hostA + "," + hostC_ip
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + hostA_ip
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.common_steps_for_comm_failover()

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover_with_ipaddress_hostnames_port(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when PBS_LEAF_ROUTERS has ipaddress,
        port number and hostname as its values
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        hostC_ip = socket.gethostbyname(self.hostC)
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        leaf_val = self.hostA + ":17001" + "," + self.hostC
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = hostC_ip + "," + self.hostA + ":17001"
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.common_steps_for_comm_failover()

    def copy_pbs_conf_to_non_default_path(self):
        """
        This function copies the pbs.conf from default location
        to non default location
        """
        # Retrieve temporary directory
        tmp_dir = self.du.get_tempdir(hostname=self.server.hostname)
        msg = "Unable to get temp_dir"
        self.assertNotEqual(tmp_dir, None, msg)
        self.new_conf_path = os.path.join(tmp_dir, "pbs.conf")

        # Copy pbs.conf file to temporary location
        rc = self.du.run_copy(src=self.pbs_conf_path, dest=self.new_conf_path)
        msg = "Cannot copy %s " % self.pbs_conf_path
        msg += "%s, error: %s" % (self.new_conf_path, rc['err'])
        self.assertEqual(rc['rc'], 0, msg)

        # Set the PBS_CONF_FILE variable to the temp location
        os.environ['PBS_CONF_FILE'] = self.new_conf_path
        self.logger.info("Successfully exported PBS_CONF_FILE variable")

        self.server.pi.conf_file = self.new_conf_path
        self.pbs_restart(self.server.hostname)
        self.logger.info("PBS services started successfully")

    @requirements(num_moms=2, num_comms=2)
    def test_comm_failover_with_nondefault_pbs_conf(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when PBS_LEAF_ROUTERS has ipaddress,
        port number and hostname as values and pbs.conf is in
        non default location
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        hostC_ip = socket.gethostbyname(self.hostC)
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        leaf_val = self.hostA + ":17001" + "," + self.hostC
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = hostC_ip + "," + self.hostA + ":17001"
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        self.copy_pbs_conf_to_non_default_path()
        self.common_steps_for_comm_failover()

    @requirements(num_moms=3, num_comms=3)
    def test_PBS_COMM_ROUTERS_with_hostname(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when multiple hostname values for
        PBS_COMM_ROUTERS are set.
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        Node 4 : Mom
        Node 5 : Comm
        Node 6 : Mom
        """
        self.common_setup()
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        comm_val = self.hostA + "," + self.hostC
        a = {'PBS_COMM_ROUTERS': comm_val}
        self.set_pbs_conf(host_name=self.hostE, conf_param=a)
        leaf_val = self.hostA + "," + self.hostC + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + self.hostA + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        leaf_val = self.hostE + "," + self.hostC + "," + self.hostA
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostD, conf_param=b)
        set_attr = {ATTR_l + '.select': '3:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_set_attr = {ATTR_l + '.select': '3:ncpus=1',
                         ATTR_l + '.place': 'scatter',
                         'reserve_start': int(time.time()) + 30,
                         'reserve_end': int(time.time()) + 120}
        self.common_steps(set_attr=set_attr, resv_set_attr=resv_set_attr,
                          job=True, interactive=True, resv=True,
                          resv_job=True)

    @requirements(num_moms=3, num_comms=3)
    def test_PBS_COMM_ROUTERS_with_ipaddress(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when multiple ipadress for
        PBS_COMM_ROUTERS are set.
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        Node 4 : Mom
        Node 5 : Comm
        Node 6 : Mom
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        hostC_ip = socket.gethostbyname(self.hostC)
        a = {'PBS_COMM_ROUTERS': hostA_ip}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        comm_val = hostA_ip + "," + hostC_ip
        a = {'PBS_COMM_ROUTERS': comm_val}
        self.set_pbs_conf(host_name=self.hostE, conf_param=a)
        leaf_val = self.hostA + "," + self.hostC + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + self.hostA + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        leaf_val = self.hostE + "," + self.hostC + "," + self.hostA
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostD, conf_param=b)
        set_attr = {ATTR_l + '.select': '3:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_set_attr = {ATTR_l + '.select': '3:ncpus=1',
                         ATTR_l + '.place': 'scatter',
                         'reserve_start': int(time.time()) + 30,
                         'reserve_end': int(time.time()) + 120}
        self.common_steps(set_attr=set_attr, resv_set_attr=resv_set_attr,
                          job=True, interactive=True, resv=True,
                          resv_job=True)

    @requirements(num_moms=3, num_comms=3)
    def test_PBS_COMM_ROUTERS_with_ipaddress_hostnames_port(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        with pbs_comm failover when PBS_COMM_ROUTERS has ipaddress,
        port number and hostname as its values
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        Node 4 : Mom
        Node 5 : Comm
        Node 6 : Mom
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        comm_val = self.hostA + ":17001"
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        comm_val = hostA_ip + ":17001" + "," + self.hostC
        a = {'PBS_COMM_ROUTERS': comm_val}
        self.set_pbs_conf(host_name=self.hostE, conf_param=a)
        leaf_val = self.hostA + "," + self.hostC + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + self.hostA + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        leaf_val = self.hostE + "," + self.hostC + "," + self.hostA
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostD, conf_param=b)
        set_attr = {ATTR_l + '.select': '3:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_set_attr = {ATTR_l + '.select': '3:ncpus=1',
                         ATTR_l + '.place': 'scatter',
                         'reserve_start': int(time.time()) + 30,
                         'reserve_end': int(time.time()) + 120}
        self.common_steps(set_attr=set_attr, resv_set_attr=resv_set_attr,
                          job=True, interactive=True, resv=True,
                          resv_job=True)

    @requirements(num_moms=3, num_comms=3)
    def test_COMM_ROUTERS_with_nondefault_pbs_conf(self):
        """
        This test verifies communication between server-mom and
        between mom when multiple pbs_comm are present in cluster
        when PBS_COMM_ROUTERS has ipaddress, port number and hostname
        as values and pbs.conf is in non default location
        Configuration:
        Node 1 : Server, Sched, Mom, Comm
        Node 2 : Mom
        Node 3 : Comm
        """
        self.common_setup()
        hostA_ip = socket.gethostbyname(self.hostA)
        comm_val = self.hostA + ":17001"
        a = {'PBS_COMM_ROUTERS': self.hostA}
        self.set_pbs_conf(host_name=self.hostC, conf_param=a)
        comm_val = hostA_ip + ":17001" + "," + self.hostC
        a = {'PBS_COMM_ROUTERS': comm_val}
        self.set_pbs_conf(host_name=self.hostE, conf_param=a)
        leaf_val = self.hostA + "," + self.hostC + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostA, conf_param=b)
        leaf_val = self.hostC + "," + self.hostA + "," + self.hostE
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostB, conf_param=b)
        leaf_val = self.hostE + "," + self.hostC + "," + self.hostA
        b = {'PBS_LEAF_ROUTERS': leaf_val}
        self.set_pbs_conf(host_name=self.hostD, conf_param=b)
        self.copy_pbs_conf_to_non_default_path()
        set_attr = {ATTR_l + '.select': '3:ncpus=1',
                    ATTR_l + '.place': 'scatter', ATTR_k: 'oe'}
        resv_set_attr = {ATTR_l + '.select': '3:ncpus=1',
                         ATTR_l + '.place': 'scatter',
                         'reserve_start': int(time.time()) + 30,
                         'reserve_end': int(time.time()) + 120}
        self.common_steps(set_attr=set_attr, resv_set_attr=resv_set_attr,
                          job=True, interactive=True, resv=True,
                          resv_job=True)

    def tearDown(self):
        os.environ['PBS_CONF_FILE'] = self.pbs_conf_path
        self.logger.info("Successfully exported PBS_CONF_FILE variable")
        conf_param = ['PBS_LEAF_ROUTERS', 'PBS_COMM_ROUTERS']
        for host in self.node_list:
            self.unset_pbs_conf(host, conf_param)
        self.node_list.clear()
        self.server.client = self.default_client
        TestFunctional.tearDown(self)
