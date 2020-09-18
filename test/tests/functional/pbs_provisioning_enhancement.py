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


@requirements(num_moms=2)
class TestProvisioningJob_Enh(TestFunctional):
    """
    This testsuite tests newly introduced provisioining capabilities.
    With this enhacement, PBS will be able to run job requesting aoe
    in subchunks, just like any other custom non consumable resource.

    PRE: Have a cluster of PBS with two MOM's installed, with one MOM
    on a node other than PBS server host. Pass the provisionable mom
    first in pbs_bencpress.
    Eg. pbs_bencpress -p moms=second_node:server_node ...
    """

    fake_prov_hook = """
import pbs
import time
e = pbs.event()

vnode = e.vnode
aoe = e.aoe
if aoe == 'App1':
    pbs.logmsg(pbs.LOG_DEBUG, "fake application provisioning script")
    e.accept(1)
pbs.logmsg(pbs.LOG_DEBUG, "aoe=%s,vnode=%s" % (aoe,vnode))
pbs.logmsg(pbs.LOG_DEBUG, "fake os provisioning script")
e.accept(0)
"""
    reject_runjob_hook = """
import pbs
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG, "job " + str(j) + " solution " + str(j.exec_vnode))
e.reject()
"""

    def setUp(self):

        if self.du.get_platform().startswith('cray'):
            self.skipTest("Test suite only meant to run on non-Cray")
        if len(self.moms) < 2:
            self.skipTest("Provide at least 2 moms while invoking test")

        TestFunctional.setUp(self)
        # This test suite expects the the first mom given with "-p moms"
        # benchpress option to be remote mom. In case this assumption
        # is not true then it reverses the order in the setup.
        if self.moms.values()[0].shortname == self.server.shortname:
            self.momA = self.moms.values()[1]
            self.momB = self.moms.values()[0]
        else:
            self.momA = self.moms.values()[0]
            self.momB = self.moms.values()[1]

        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname

        # Remove all nodes
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")

        # Create node
        self.server.manager(MGR_CMD_CREATE, NODE, None, self.hostA)
        self.server.manager(MGR_CMD_CREATE, NODE, None, self.hostB)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostA)
        self.server.expect(NODE, {'state': 'free'}, id=self.hostB)

        # Set hostA provisioning attributes.
        a = {'provision_enable': 'true',
             'resources_available.ncpus': '2',
             'resources_available.aoe': 'App1,osimage1'}
        self.server.manager(
            MGR_CMD_SET, NODE, a, id=self.hostA)
        self.server.manager(MGR_CMD_UNSET, NODE, id=self.hostA,
                            attrib='current_aoe')

        # Set hostB ncpus to 12
        a = {'resources_available.ncpus': '12'}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.hostB)

        # Setup provisioning hook.
        a = {'event': 'provision', 'enabled': 'True', 'alarm': '300'}
        rv = self.server.create_import_hook(
            'fake_prov_hook', a, self.fake_prov_hook, overwrite=True)
        self.assertTrue(rv)

        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})

    @skipOnCpuSet
    def test_app_provisioning(self):
        """
        Test application provisioning
        """
        j = Job(TEST_USER1)
        j.set_sleep_time(5)
        j.set_attributes({'Resource_List.select': '1:aoe=App1'})
        jid = self.server.submit(j)

        # Job should start running after provisioining script finish
        # executing.
        # Since this is application provisioining, mom restart is
        # not needed.
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'App1'}, id=self.hostA)

        self.server.log_match(
            "fake application provisioning script",
            max_attempts=20,
            interval=1)

    @skipOnCpuSet
    def test_os_provisioning(self):
        """
        Test os provisioning
        """

        j = Job(TEST_USER1)
        j.set_sleep_time(10)
        j.set_attributes({'Resource_List.select': '1:aoe=osimage1'})
        jid = self.server.submit(j)

        # Job will start and wait for provisioning to complete.
        self.server.expect(JOB, {ATTR_substate: '71'}, id=jid)
        self.server.log_match("fake os provisioning script",
                              max_attempts=60,
                              interval=1)

        # Since this is OS provisioining, mom restart is
        # required to finish provisioining. Sending SIGHUP
        # to the provisioning mom will also work, but restart
        # is more apt to simulate real world scenario.
        self.momA.restart()

        # Current aoe on momA should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'osimage1'}, id=self.hostA)

        # After mom restart job execution should start, as
        # OS provisioining completes affer mom restart.
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

    @skipOnCpuSet
    def test_subchunk_application_provisioning(self):
        """
        Test application provisioning job request consist of subchunks
        with and without aoe resource.
        """
        j = Job(TEST_USER1)
        j.set_attributes({'Resource_List.select':
                          '1:ncpus=1:aoe=App1+1:ncpus=12'})
        j.set_sleep_time(5)
        jid = self.server.submit(j)

        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)
        self.server.expect(JOB, ATTR_execvnode, id=jid, op=SET)
        nodes = j.get_vnodes(j.exec_vnode)
        self.server.log_match("fake application provisioning script",
                              max_attempts=20,
                              interval=1)
        self.assertTrue((nodes[0] == self.momA.shortname and
                         nodes[1] == self.momB.shortname) or
                        (nodes[0] == self.momB.shortname and
                         nodes[1] == self.momA.shortname))

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'App1'}, id=self.hostA)

    @skipOnCpuSet
    def test_subchunk_os_provisioning(self):
        """
        Test os provisioning job request consist of subchunks
        with and without aoe resource.
        """
        a = {'Resource_List.select': '1:aoe=osimage1+1:ncpus=12'}
        j = Job(TEST_USER1, a)
        j.set_sleep_time(10)
        jid = self.server.submit(j)
        self.server.expect(JOB, ATTR_execvnode, id=jid, op=SET)
        nodes = j.get_vnodes(j.exec_vnode)
        self.assertTrue((nodes[0] == self.momA.shortname and
                         nodes[1] == self.momB.shortname) or
                        (nodes[0] == self.momB.shortname and
                         nodes[1] == self.momA.shortname))

        self.momA.restart()

        # After mom restart job execution should start, as
        # OS provisioining completes affer mom restart.
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'osimage1'}, id=self.hostA)

    @skipOnCpuSet
    def test_job_wide_provisioining_request(self):
        """
        Test jobs with jobwide aoe resource request.
        """

        # Below job will not run, since resource requested are job-wide,
        # and no single node have all the requested resource.

        j = Job(TEST_USER1)
        j.set_sleep_time(5)
        j.set_attributes({"Resource_List.aoe": "App1",
                          "Resource_List.ncpus": 12})
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'Q',
                                 ATTR_comment:
                                 (MATCH_RE, 'Not Running: Insufficient ' +
                                  'amount of resource: .*')}, id=jid)

        j = Job(TEST_USER1)
        j.set_attributes({"Resource_List.aoe": "App1",
                          "Resource_List.ncpus": 1})
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'App1'}, id=self.hostA)

    @skipOnCpuSet
    def test_multiple_aoe_request(self):
        """
        Test jobs with multiple similar/various aoe request in subchunks.
        Job request cosisting of multiple subchunks with different aoe will
        fail submission, Whereas job request with same aoe across multiple
        subchunks should be succesful.
        """

        a1 = {'Resource_List.select':
              '1:ncpus=1:aoe=App1+1:ncpus=12:aoe=osimage1'}

        a2 = {'Resource_List.select':
              '1:ncpus=1:aoe=App1+1:ncpus=12:aoe=App1'}

        # Below job will fail submission, since different aoe's requested,
        # across multiple subchunks.

        j = Job(TEST_USER1)
        j.set_attributes(a1)
        j.set_sleep_time(5)
        jid = None
        try:
            jid = self.server.submit(j)
            self.assertTrue(jid is None, 'Job successfully submitted' +
                            'when it should have failed')
        except PbsSubmitError as e:
            self.assertTrue('Invalid provisioning request in chunk(s)'
                            in e.msg[0],
                            'Job submission failed, but due to ' +
                            'unexpected reason.\n%s' % e.msg[0])
            self.logger.info("Job submission failed, as expected")

        # Below job will get submitted, since same aoe requested,
        # across multiple subchunks.

        j = Job(TEST_USER1)
        j.set_attributes(a2)
        jid = self.server.submit(j)
        self.assertTrue(jid is not None, 'Job submission failed' +
                        'when it should have succeeded')
        self.logger.info("Job submission succeeded, as expected")

    @skipOnCpuSet
    def test_provisioning_with_placement(self):
        """
        Test provisioining job with various placement options.
        """

        # Below job will not run, since placement is set to pack.
        # and no single node have all the requested resource.

        j = Job(TEST_USER1)
        j.set_attributes({'Resource_List.select':
                          '1:ncpus=1:aoe=App1+1:ncpus=12',
                          'Resource_List.place': 'pack'})
        j.set_sleep_time(5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_state: 'Q',
                                 ATTR_comment:
                                 (MATCH_RE, 'Not Running: Insufficient ' +
                                  'amount of resource: .*')}, id=jid)

        # Below job will run with placement set to pack.
        # since there is only one node with the requested resource.

        j = Job(TEST_USER1)
        j.set_attributes({'Resource_List.select':
                          '1:ncpus=1:aoe=App1+1:ncpus=1',
                          'Resource_List.place': 'pack'})
        j.set_sleep_time(5)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(JOB, ATTR_execvnode, id=jid, op=SET)
        nodes = j.get_vnodes(j.exec_vnode)
        self.assertTrue(nodes[0] == self.momA.shortname)

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'App1'}, id=self.hostA)

        # This was needed since sometime the above job takes longer
        # to finish and release the resources. This causes delay for
        # the next job to start and can probably fail the test.
        self.server.cleanup_jobs()

        # Below job will run on two node with placement set to scatter.
        # even though single node can satisfy both the requested chunks.

        j = Job(TEST_USER1)
        j.set_attributes({'Resource_List.select':
                          '1:ncpus=1:aoe=App1+1:ncpus=1',
                          'Resource_List.place': 'scatter'})
        j.set_sleep_time(5)
        jid = self.server.submit(j)
        self.server.expect(JOB, ATTR_execvnode, id=jid, op=SET)
        nodes = j.get_vnodes(j.exec_vnode)
        self.assertTrue((nodes[0] == self.momA.shortname and
                         nodes[1] == self.momB.shortname) or
                        (nodes[0] == self.momB.shortname and
                         nodes[1] == self.momA.shortname))
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        # Current aoe on momA, should be set to the requested aoe in job.
        self.server.expect(NODE, {'current_aoe': 'App1'}, id=self.hostA)

    @skipOnCpuSet
    def test_sched_provisioning_response_with_runjob(self):
        """
        Test that if one provisioning job fails to run then scheduler
        correctly provides the node solution for the second job with aoe in
        it.
        """
        # Setup runjob hook.
        a = {'event': 'runjob', 'enabled': 'True'}
        rv = self.server.create_import_hook(
            'reject_runjob_hook', a, self.reject_runjob_hook, overwrite=True)
        self.assertTrue(rv)
        # Set current aoe to App1
        self.server.manager(MGR_CMD_SET, NODE, id=self.hostA,
                            attrib={'current_aoe': 'App1'})

        # Turn on scheduling
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'False'})

        # submit two provisioning jobs
        a = {'Resource_List.select': '1:aoe=osimage1:ncpus=1+1:ncpus=4',
             'Resource_List.place': 'vscatter'}
        j = Job(TEST_USER1, attrs=a)
        jid1 = self.server.submit(j)
        jid2 = self.server.submit(j)

        # Turn off scheduling
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'True'})

        # Job will be rejected by runjob hook and it should log
        # correct exec_vnode for each job.
        msg = "job %s " + "solution (%s:aoe=osimage1:ncpus=1)+(%s:ncpus=4)"
        job1_msg = msg % (jid1, self.hostA, self.hostB)
        job2_msg = msg % (jid2, self.hostA, self.hostB)
        self.server.log_match(job1_msg)
        self.server.log_match(job2_msg)

    @skipOnCpuSet
    def test_sched_provisioning_response(self):
        """
        Test that if scheduler could not find node solution for one
        provisioning job then it will find the correct solution for the
        second one.
        """

        # Set current aoe to osimage1
        self.server.manager(MGR_CMD_SET, NODE, id=self.hostA,
                            attrib={'current_aoe': 'osimage1'})

        # submit one job that will run on local node
        a = {'Resource_List.select': '1:ncpus=10'}
        j1 = Job(TEST_USER1, attrs=a)
        j1.set_sleep_time(200)
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)

        # Turn off scheduling
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'False'})

        # submit two provisioning jobs where first job will not be able
        # to run and second one can
        a = {'Resource_List.select': '1:aoe=App1:ncpus=1+1:ncpus=3',
             'Resource_List.place': 'vscatter'}
        j2 = Job(TEST_USER1, attrs=a)
        jid2 = self.server.submit(j2)

        a = {'Resource_List.select': '1:aoe=App1:ncpus=1+1:ncpus=2',
             'Resource_List.place': 'vscatter'}
        j3 = Job(TEST_USER1, attrs=a)
        jid3 = self.server.submit(j3)

        # Turn on scheduling
        self.server.manager(MGR_CMD_SET,
                            SERVER, {'scheduling': 'True'})

        ev_format = "(%s:aoe=App1:ncpus=1)+(%s:ncpus=2)"
        solution = ev_format % (self.hostA, self.hostB)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid3)
        job_state = self.server.status(JOB, id=jid3)
        self.assertEqual(job_state[0]['exec_vnode'], solution)

    @skipOnCpuSet
    def test_multinode_provisioning(self):
        """
        Test the effect of max_concurrent_provision
        If set to 1 and job requests a 4 node provision, the provision should
        occur 1 node at a time
        """
        # Setup provisioning hook with smaller alarm.
        a = {'event': 'provision', 'enabled': 'True', 'alarm': '5'}
        rv = self.server.create_import_hook(
            'fake_prov_hook', a, self.fake_prov_hook, overwrite=True)

        a = {'max_concurrent_provision': 1}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.aoe': 'App1,osimage1',
             'current_aoe': 'App1',
             'provision_enable': 'True',
             'resources_available.ncpus': 1}
        rv = self.momA.create_vnodes(a, 4,
                                     sharednode=False)
        self.assertTrue(rv)
        j = Job(TEST_USER,
                attrs={'Resource_List.select': '4:ncpus=1:aoe=osimage1'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R',
                                 'substate': 71}, attrop=PTL_AND, id=jid)
        exp_msg = "Provisioning vnode " + self.momA.shortname
        exp_msg += "\[[0-3]\] with AOE osimage1 started"
        logs = self.server.log_match(msg=exp_msg, regexp=True, allmatch=True)

        # since max_concurrent_provision is 1, there should be only one
        # log
        self.assertEqual(len(logs), 1)

        # A node in provisioning state cannot be deleted. In order to make
        # sure that cleanup happens properly do the following -
        # sleep for a few seconds so that provisin timesout and the node
        # is marked offline and then delete all the nodes
        time.sleep(8)
        # delete all nodes
        self.server.manager(MGR_CMD_DELETE, NODE, None, "")
