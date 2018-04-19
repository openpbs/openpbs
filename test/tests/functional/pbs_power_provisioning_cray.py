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
import json
from subprocess import Popen, PIPE
import time


class Test_power_provisioning_cray(TestFunctional):

    """
    Test power provisioning feature for the CRAY platform.

    """

    def setUp(self):
        """
        Use the MOM's that are already setup or define the ones passed in.
        """
        TestFunctional.setUp(self)
        pltfom = self.du.get_platform()
        if pltfom != 'cray':
            self.skipTest("%s: not a cray")
        self.mom.add_config({"logevent": "0xfffffff"})
        self.setup_cray_eoe()   # setup hook and eoe
        self.enable_power()     # enable hooks

    def setup_cray_eoe(self):
        """
        Setup a eoe list for all the nodes.
        Get possible values for pcaps using capmc command.
        """
        min_nid = 0
        max_nid = 0
        self.names = []
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.names.append(n['id'])
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"power_provisioning": True}, n['id'])
                craynid = n['resources_available.PBScraynid']
                if min_nid == 0 or craynid < min_nid:
                    min_nid = craynid
                if craynid > max_nid:
                    max_nid = craynid
        # Dividing total number of nodes by 3 and setting each part to a
        # different power profile , which will be used to submit jobs with
        # chunks matching to the number of nodes set to each profile
        self.npp = len(self.names) / 3
        for i in xrange(len(self.names)):
            if i in range(0, self.npp):
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"resources_available.eoe": 'low'},
                                    self.names[i])
            if i in range(self.npp, self.npp * 2):
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"resources_available.eoe": 'med'},
                                    self.names[i])
            if i in range(self.npp * 2, self.npp * 3):
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"resources_available.eoe": 'high'},
                                    self.names[i])

        # Find nid range for capmc command
        nids = str(min_nid) + "-" + str(max_nid)
        cmd = "/opt/cray/capmc/default/bin/capmc "
        cmd += "get_power_cap_capabilities --nids=" + nids
        p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        (o, e) = p.communicate()
        out = json.loads(o)
        low = 0
        med = 0
        high = 0
        rv = 'groups' in out
        msg = "Error while creating hook content from capmc output: " + cmd
        self.assertTrue(rv, msg)
        for group in out['groups']:
            for control in group['controls']:
                if control['name'] == 'node':
                    min_cap = control['min']
                    max_cap = control['max']
            pcap_list = {}
            for nid in group['nids']:
                pcap_list[nid] = {}
                pcap_list[nid]['min'] = min_cap
                pcap_list[nid]['max'] = max_cap
                if low == 0 or low < min_cap:
                    low = min_cap
                if high == 0 or high > max_cap:
                    high = max_cap
        # Get the med using mean of low and high
        med = (low + high) / 2

        # Now create the map_eoe hook file
        hook_content = """
import pbs
e = pbs.event()
j = e.job
profile = j.Resource_List['eoe']
if profile is None:
    res = j.Resource_List['select']
    if res is not None:
        for s in str(res).split('+')[0].split(':'):
            if s[:4] == 'eoe=':
                profile = s.partition('=')[2]
                break
pbs.logmsg(pbs.LOG_DEBUG, "got profile '%s'" % str(profile))
if profile == "low":
    j.Resource_List["pcap_node"] = LOW_PCAP
    pbs.logmsg(pbs.LOG_DEBUG, "set low")
elif profile == "med":
    j.Resource_List["pcap_node"] = MED_PCAP
    pbs.logmsg(pbs.LOG_DEBUG, "set med")
elif profile == "high":
    j.Resource_List["pcap_node"] = HIGH_PCAP
    pbs.logmsg(pbs.LOG_DEBUG, "set high")
else:
    pbs.logmsg(pbs.LOG_DEBUG, "unhandled profile '%s'" % str(profile))

e.accept()
"""

        hook_content = hook_content.replace('LOW_PCAP', str(low))
        hook_content = hook_content.replace('MED_PCAP', str(med))
        hook_content = hook_content.replace('HIGH_PCAP', str(high))
        hook_name = "map_eoe"
        a = {'event': 'queuejob', 'enabled': 'true'}
        rv = self.server.create_import_hook(hook_name, a, hook_content)
        msg = "Error while creating and importing hook contents"
        self.assertTrue(rv, msg)
        msg = "Hook %s created and " % hook_name
        msg += "hook script is imported successfully"
        self.logger.info(msg)

    def enable_power(self):
        """
        Enable power_provisioning on the server.
        """
        a = {'enabled': 'True'}
        hook_name = "PBS_power"
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_name,
                            sudo=True)

        # check that hook becomes active
        nodes = self.server.status(NODE)
        n = nodes[0]
        host = n['Mom']
        self.assertTrue(host is not None)
        mom = self.moms[host]
        mom.log_match(
            "Hook;PBS_power.HK;copy hook-related file request received",
            starttime=self.server.ctime)

    def disable_power(self):
        """
        Disable power_provisioning on the server.
        """
        a = {'enabled': 'False'}
        hook_name = "PBS_power"
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_name,
                            sudo=True)

    def submit_job(self, secs=10, a={}):
        """
        secs: sleep time for the job
        a: any job attributes
        """
        a['Keep_Files'] = 'oe'
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(secs)
        self.logger.info(str(j))
        jid = self.server.submit(j)
        self.job = j
        return jid

    def energy_check(self, jid):
        s = self.server.accounting_match("E;%s;.*" % jid,
                                         regexp=True)
        self.assertTrue(s is not None)
        # got the account record, hack it apart
        for resc in s[1].split(';')[3].split():
            if resc.partition('=')[0] == "resources_used.energy":
                return True
        return False

    def mom_logcheck(self, msg, jid=None):
        mom = self.moms[self.host]           # top mom
        if jid is not None:
            mom.log_match(msg % jid,
                          regexp=True, starttime=self.server.ctime,
                          max_attempts=10)
        else:
            mom.log_match(msg,
                          regexp=True, starttime=self.server.ctime,
                          max_attempts=10)

    def eoe_check(self, jid, eoe, secs):
        # check that job is running and that the vnode has current_eoe set
        # check for the appropriate log messages for cray
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        qstat = self.server.status(JOB, id=jid)
        nodes = self.job.get_vnodes(self.job.exec_vnode)
        for vname in nodes:
            self.server.expect(VNODE, {'current_eoe': eoe}, id=vname)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=secs)
        self.host = qstat[0]['exec_host'].partition('/')[0]
        self.mom_logcheck(";Job;%s;Cray: get_usage", jid)
        self.mom_logcheck("capmc get_node_energy_counter --nids")
        self.mom_logcheck(";Job;%s;energy usage", jid)
        self.mom_logcheck(";Job;%s;Cray: pcap node", jid)
        self.mom_logcheck("capmc set_power_cap --nids")
        self.mom_logcheck(";Job;%s;PMI: reset current_eoe", jid)
        self.mom_logcheck(";Job;%s;Cray: remove pcap node", jid)
        for vname in nodes:
            self.server.expect(VNODE, {'current_eoe': eoe}, id=vname, op=UNSET)

    def eoe_job(self, num, eoe):
        """
        Helper function to submit a job with an eoe value.
        Parameters:
        num: number of chunks
        eoe: profile name
        """
        secs = 10
        jid = self.submit_job(secs,
                              {'Resource_List.place': 'scatter',
                               'Resource_List.select': '%d:eoe=%s' % (num,
                                                                      eoe)})
        self.eoe_check(jid, eoe, secs)
        return jid

    @timeout(700)
    def test_cray_eoe_job(self):
        """
        Submit jobs with an eoe value and check that messages are logged
        indicating PMI activity, and current_eoe and resources_used.energy
        get set.
        """

        eoes = ['low', 'med', 'high']
        for profile in eoes:
            jid = self.eoe_job(self.npp, profile)
            self.energy_check(jid)

    @timeout(700)
    def test_cray_request_more_eoe(self):
        """
        Submit jobs with available+1 eoe chunks and verify job comment.
        """

        x = self.npp + 1
        jid = self.submit_job(10,
                              {'Resource_List.place': 'scatter',
                               'Resource_List.select': '%d:eoe=%s' % (x,
                                                                      'high')})
        self.server.expect(JOB, {
            'job_state': 'Q',
            'comment': 'Not Running: No available resources on nodes'},
            id=jid)

    @timeout(700)
    def test_cray_eoe_job_multiple_eoe(self):
        """
        Submit jobs requesting multiple eoe and job should rejected by qsub.
        """

        a = {'Resource_List.place': 'scatter',
             'Resource_List.select': '10:eoe=low+10:eoe=high'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        jid = None
        try:
            jid = self.server.submit(j)
        except PbsSubmitError as e:
            self.assertTrue(
                'Invalid provisioning request in chunk' in e.msg[0])
        self.assertFalse(jid)

    @timeout(700)
    def test_cray_server_prov_off(self):
        """
        Submit jobs requesting eoe when power provisioning unset on server
        and verify that jobs wont run.
        """

        eoes = ['low', 'med', 'high']
        a = {'power_provisioning': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        for profile in eoes:
            jid = self.submit_job(10,
                                  {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (self.npp, profile)})
            self.server.expect(JOB, {
                'job_state': 'Q',
                'comment': 'Not Running: No available resources on nodes'},
                id=jid)

    @timeout(700)
    def test_cray_node_prov_off(self):
        """
        Submit jobs requesting eoe and verify that jobs wont run on
        nodes where power provisioning is set to false.
        """

        eoes = ['med', 'high']
        # set power_provisioning to off where eoe is set to false
        for i in range(0, self.npp):
            a = {'power_provisioning': 'False'}
            self.server.manager(MGR_CMD_SET, NODE, a, id=self.names[i])

        for profile in eoes:
            jid = self.submit_job(10,
                                  {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (self.npp, profile)})
            self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        jid_low = self.submit_job(10,
                                  {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (self.npp, 'low')})
        exp_comm = 'Not Running: Insufficient amount of resource: '
        exp_comm += 'vntype (cray_compute != cray_login)'
        self.server.expect(JOB, {
                           'job_state': 'Q',
                           'comment': exp_comm}, attrop=PTL_AND, id=jid_low)

    @timeout(700)
    def test_cray_job_preemption(self):
        """
        Submit job to a high priority queue and verify
        that job is preempted by requeueing.
        """

        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'execution', 'started': 'True',
                             'enabled': 'True', 'priority': 150}, id='workq2')
        jid = self.submit_job(10,
                              {'Resource_List.place': 'scatter',
                               'Resource_List.select': '%d:eoe=%s'
                               % (self.npp, 'low')})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        t = int(time.time())
        jid_hp = self.submit_job(10, {ATTR_queue: 'workq2',
                                      'Resource_List.place': 'scatter',
                                      'Resource_List.select': '%d:eoe=%s' %
                                      (self.npp, 'low')})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_hp)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.scheduler.log_match("Job preempted by requeuing", starttime=t)

    def test_power_provisioning_attribute(self):
        """
        Test that when hook is disabled power_provisioning on
        server is set to false and when enabled true.
        """
        self.enable_power()
        a = {'power_provisioning': 'True'}
        self.server.expect(SERVER, a)

        self.disable_power()
        a = {'power_provisioning': 'False'}
        self.server.expect(SERVER, a)

    def test_poweroff_eligible_atrribute(self):
        """
        Test that we can set poweroff_eligible for nodes to true/false.
        """
        nodes = self.server.status(NODE)
        host = nodes[0]['id']
        self.server.manager(MGR_CMD_SET, NODE, {'poweroff_eligible': 'True'},
                            expect=True, id=host)
        self.server.manager(MGR_CMD_SET, NODE, {'poweroff_eligible': 'False'},
                            expect=True, id=host)

    def test_last_state_change_time(self):
        """
        Test last_state_change_time is set when a job is run and is exited.
        """
        pattern = '%a %b %d %H:%M:%S %Y'
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_history_enable': 'True'})
        nodes = self.server.status(NODE)
        host = nodes[0]['resources_available.host']
        ncpus = nodes[0]['resources_available.ncpus']
        jid = self.submit_job(
            5, {'Resource_List.host': host, 'Resource_List.ncpus': ncpus})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=host)
        fmttime = status[0][ATTR_NODE_last_state_change_time]
        sts_time1 = int(time.mktime(time.strptime(fmttime, pattern)))
        jid = self.submit_job(
            5, {'Resource_List.host': host, 'Resource_List.ncpus': ncpus})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=host)
        fmttime = status[0][ATTR_NODE_last_state_change_time]
        sts_time2 = int(time.mktime(time.strptime(fmttime, pattern)))
        rv = sts_time2 > sts_time1
        self.assertTrue(rv)

    def test_last_used_time(self):
        """
        Test last_used_time is set when a job is run and is exited.
        """
        pattern = '%a %b %d %H:%M:%S %Y'
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_history_enable': 'True'})
        nodes = self.server.status(NODE)
        host = nodes[0]['resources_available.host']
        jid = self.submit_job(5, {'Resource_List.host': host})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=host)
        fmttime = status[0][ATTR_NODE_last_used_time]
        sts_time1 = int(time.mktime(time.strptime(fmttime, pattern)))
        jid = self.submit_job(5, {'Resource_List.host': host})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=host)
        fmttime = status[0][ATTR_NODE_last_used_time]
        sts_time2 = int(time.mktime(time.strptime(fmttime, pattern)))
        rv = sts_time2 > sts_time1
        self.assertTrue(rv)
