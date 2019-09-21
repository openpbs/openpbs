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
        a = {'log_events': '2047'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        self.nids = []
        self.names = []
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.names.append(n['id'])
                craynid = n['resources_available.PBScraynid']
                self.nids.append(craynid)
        self.enable_power()     # enable hooks

    def modify_hook_config(self, attrs, hook_id):
        """
        Modify the hook config file contents
        """
        conf_file = str(hook_id) + '.CF'
        conf_file_path = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                      'server_priv', 'hooks', conf_file)
        with open(conf_file_path) as data_file:
            data = json.load(data_file)
        for key, value in attrs.items():
            data[key] = value
        with open(conf_file_path, 'w') as fp:
            json.dump(data, fp)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_id, sudo=True)

    def setup_cray_eoe(self):
        """
        Setup a eoe list for all the nodes.
        Get possible values for pcaps using capmc command.
        """
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"power_provisioning": True}, n['id'])
        # Dividing total number of nodes by 3 and setting each part to a
        # different power profile , which will be used to submit jobs with
        # chunks matching to the number of nodes set to each profile
        self.npp = len(self.names) / 3
        for i in range(len(self.names)):
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
        cmd = "/opt/cray/capmc/default/bin/capmc "\
              "get_power_cap_capabilities --nids " + ','.join(self.nids)
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

    def cleanup_power_on(self):
        """
        cleanup by switching back all the nodes
        """
        capmc_cmd = os.path.join(
            os.sep, 'opt', 'cray', 'capmc', 'default', 'bin', 'capmc')
        self.du.run_cmd(self.server.hostname, [
                        capmc_cmd, 'node_on', '--nids',
                        ','.join(self.nids)], sudo=True)
        self.logger.info("Waiting for 15 mins to power on all the nodes")
        time.sleep(900)

    def cleanup_power_ramp_rate(self):
        """
        cleanup by ramping back all the nodes
        """
        for nid in self.nids:
            capmc_cmd = os.path.join(
                os.sep, 'opt', 'cray', 'capmc', 'default', 'bin', 'capmc')
            self.du.run_cmd(self.server.hostname, [
                capmc_cmd, 'set_sleep_state_limit', '--nids',
                str(nid), '--limit', '1'], sudo=True)
            self.logger.info("ramping up the node with nid" + str(nid))

    def setup_power_ramp_rate(self):
        """
        Offline the nodes which does not have sleep_state_capablities
        """
        self.offnodes = 0
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                nid = n['resources_available.PBScraynid']
                cmd = os.path.join(os.sep, 'opt', 'cray',
                                   'capmc', 'default', 'bin', 'capmc')
                ret = self.du.run_cmd(self.server.hostname,
                                      [cmd,
                                       'get_sleep_state_limit_capabilities',
                                       '--nids', str(nid)], sudo=True)
                try:
                    out = json.loads(ret['out'][0])
                except Exception:
                    out = None
                if out is not None:
                    errno = out["e"]
                    msg = out["err_msg"]
                    if errno == 52 and msg == "Invalid exchange":
                        self.offnodes = self.offnodes + 1
                        a = {'state': 'offline'}
                        self.server.manager(MGR_CMD_SET, NODE, a, id=n['id'])

    @timeout(700)
    def test_cray_eoe_job(self):
        """
        Submit jobs with an eoe value and check that messages are logged
        indicating PMI activity, and current_eoe and resources_used.energy
        get set.
        """
        self.setup_cray_eoe()
        eoes = ['low', 'med', 'high']
        for profile in eoes:
            jid = self.eoe_job(self.npp, profile)
            self.energy_check(jid)

    @timeout(700)
    def test_cray_request_more_eoe(self):
        """
        Submit jobs with available+1 eoe chunks and verify job comment.
        """
        self.setup_cray_eoe()
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
        self.setup_cray_eoe()
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
        self.setup_cray_eoe()
        eoes = ['low', 'med', 'high']
        a = {'enabled': 'False'}
        hook_name = "PBS_power"
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_name,
                            sudo=True)
        self.server.expect(SERVER, {'power_provisioning': 'False'})
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
        self.setup_cray_eoe()
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
        self.setup_cray_eoe()
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
                            id=host)
        self.server.manager(MGR_CMD_SET, NODE, {'poweroff_eligible': 'False'},
                            id=host)

    def test_last_state_change_time(self):
        """
        Test last_state_change_time is set when a job is run and is exited.
        """
        pattern = '%a %b %d %H:%M:%S %Y'
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_history_enable': 'True'})
        nodes = self.server.status(NODE)
        vnode = nodes[0]['resources_available.vnode']
        ncpus = nodes[0]['resources_available.ncpus']
        vntype = nodes[0]['resources_available.vntype']
        jid = self.submit_job(5, {'Resource_List.vnode': vnode,
                                  'Resource_List.ncpus': ncpus,
                                  'Resource_List.vntype': vntype})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=vnode)
        fmttime = status[0][ATTR_NODE_last_state_change_time]
        sts_time1 = int(time.mktime(time.strptime(fmttime, pattern)))
        jid = self.submit_job(5, {'Resource_List.vnode': vnode,
                                  'Resource_List.ncpus': ncpus,
                                  'Resource_List.vntype': vntype})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=vnode)
        fmttime = status[0][ATTR_NODE_last_state_change_time]
        sts_time2 = int(time.mktime(time.strptime(fmttime, pattern)))
        self.assertGreater(sts_time2, sts_time1)

    def test_last_used_time(self):
        """
        Test last_used_time is set when a job is run and is exited.
        """
        pattern = '%a %b %d %H:%M:%S %Y'
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_history_enable': 'True'})
        nodes = self.server.status(NODE)
        vnode = nodes[0]['resources_available.vnode']
        vntype = nodes[0]['resources_available.vntype']
        jid = self.submit_job(5, {'Resource_List.vnode': vnode,
                                  'Resource_List.vntype': vntype})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=vnode)
        fmttime = status[0][ATTR_NODE_last_used_time]
        sts_time1 = int(time.mktime(time.strptime(fmttime, pattern)))
        jid = self.submit_job(5, {'Resource_List.vnode': vnode,
                                  'Resource_List.vntype': vntype})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(NODE, id=vnode)
        fmttime = status[0][ATTR_NODE_last_used_time]
        sts_time2 = int(time.mktime(time.strptime(fmttime, pattern)))
        self.assertGreater(sts_time2, sts_time1)

    @timeout(1200)
    def test_power_off_nodes(self):
        """
        Test power hook will power off the nodes if power_on_off_enable when
        poweroff_eligible is set to true on nodes.
        """
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"poweroff_eligible": True}, n['id'])
        a = {"power_on_off_enable": True,
             "max_concurrent_nodes": "30", 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        t = int(time.time())
        self.logger.info("Waiting for 4 mins to power off all the nodes")
        time.sleep(240)
        self.server.log_match(
            "/opt/cray/capmc/default/bin/capmc node_off", starttime=t)
        # Expect sleep state on all nodes expect login node
        self.server.expect(
            NODE, {'state=sleep': len(self.server.status(NODE)) - 1})
        self.cleanup_power_on()

    @timeout(1200)
    def test_power_on_off_max_concurennt_nodes(self):
        """
        Test power hook will power off the only the number of
        max_concurrent nodes specified in conf file per hook run
        even when poweroff_eligible is set to true on all the nodes.
        """
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"poweroff_eligible": True}, n['id'])
        a = {"power_on_off_enable": True, 'node_idle_limit': '10',
             'max_concurrent_nodes': '2'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 40 secs to power off 2 nodes")
        time.sleep(40)
        a = {'enabled': 'False'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.server.expect(NODE, {'state=sleep': 2})
        self.cleanup_power_on()

    def test_poweroffelgible_false(self):
        """
        Test hook wont power off the nodes where
        poweroff_eligible is set to false
        """
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"poweroff_eligible": False}, n['id'])
        a = {"power_on_off_enable": True,
             "max_concurrent_nodes": "30", 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info(
            "Waiting for 100 secs to make sure no nodes are powered off")
        time.sleep(100)
        self.server.expect(NODE, {'state=free': len(self.server.status(NODE))})

    @timeout(900)
    def test_power_on_nodes(self):
        """
        Test when a job is calandered on a vnode which is in sleep state,
        the node will be powered on and job will run.
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, NODE, {
                            "poweroff_eligible": True}, self.names[0])
        a = {"power_on_off_enable": True, 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        t = int(time.time())
        self.logger.info("Waiting for 1 min to poweroff 1st node")
        time.sleep(60)
        self.server.log_match(
            "/opt/cray/capmc/default/bin/capmc node_off", starttime=t)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        t = int(time.time())
        jid = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        self.scheduler.log_match(
            jid + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        t = int(time.time())
        self.logger.info("Waiting for 10 min to poweron 1st node")
        time.sleep(600)
        self.server.log_match(
            "/opt/cray/capmc/default/bin/capmc node_on", starttime=t)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])

    @timeout(900)
    def test_power_on_ramp_rate_nodes(self):
        """
        Test when both ramp rate and power on off is enabled,
        power_on_off_enable will override and nodes will be powered off
        and powered on.
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, NODE, {
                            "poweroff_eligible": True}, self.names[0])
        a = {"power_on_off_enable": True,
             "power_ramp_rate_enable": True, 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        t = int(time.time())
        self.logger.info("Waiting for 1 min to poweroff 1st node")
        time.sleep(60)
        self.server.log_match(
            "power_on_off_enable is over-riding power_ramp_rate_enable",
            starttime=t)
        self.server.log_match(
            "/opt/cray/capmc/default/bin/capmc node_off", starttime=t)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        t = int(time.time())
        jid = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        self.scheduler.log_match(
            jid + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        t = int(time.time())
        self.logger.info("Waiting for 10 min to poweron 1st node")
        time.sleep(600)
        self.server.log_match(
            "/opt/cray/capmc/default/bin/capmc node_on", starttime=t)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])

    @timeout(1200)
    def test_power_on_min_node_down_delay(self):
        """
        Test when a job is calandered on a vnode which is in sleep state,
        the node will be not be powered on until min_node_down_delay time.
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, NODE, {
                            "poweroff_eligible": True}, self.names[0])
        a = {"power_on_off_enable": True, 'min_node_down_delay': '3000'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 1 min to poweroff 1st node")
        time.sleep(60)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        jid = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        t = int(time.time())
        self.scheduler.log_match(
            jid + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        self.logger.info("Waiting for 2 mins to make sure node is not powered")
        time.sleep(120)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        self.cleanup_power_on()

    @timeout(1800)
    def test_max_jobs_analyze_limit(self):
        """
        Test that even when 4 jobs are calandered only nodes assigned
        to max_jobs_analyze_limit number of jobs will be considered
        for powering on.
        """
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, SERVER, {'backfill_depth': '4'})
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE, {
                                    "poweroff_eligible": True}, n['id'])
        a = {"power_on_off_enable": True, 'max_jobs_analyze_limit': '2',
             'node_idle_limit': '30', 'max_concurrent_nodes': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 30}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 2 mins to poweroff all the nodes")
        time.sleep(120)
        # Expect sleep state on all nodes expect login node
        self.server.expect(
            NODE, {'state=sleep': len(self.server.status(NODE)) - 1})
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        j1id = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        j2id = self.submit_job(1000, {'Resource_List.vnode': self.names[1]})
        j3id = self.submit_job(1000, {'Resource_List.vnode': self.names[2]})
        j4id = self.submit_job(1000, {'Resource_List.vnode': self.names[3]})
        self.logger.info(
            "Waiting for 10 mins to poweron the nodes which are calandered")
        time.sleep(600)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, id=j1id)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[1])
        self.server.expect(JOB, {'job_state': 'Q'}, id=j3id)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[2])
        self.server.expect(JOB, {'job_state': 'Q'}, id=j4id)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[3])
        self.cleanup_power_on()

    def test_last_used_time_node_sort_key(self):
        """
        Test last_used_time as node sort key.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'job_history_enable': 'True'})
        i = 0
        for n in self.server.status(NODE):
            if 'resources_available.PBScraynid' in n:
                if i > 1:
                    self.server.manager(MGR_CMD_SET, NODE, {
                        'state': 'offline'}, id=n['id'])
                i += 1
        a = {'node_sort_key': '"last_used_time LOW" ALL'}
        self.scheduler.set_sched_config(a)
        jid = self.submit_job(
            1, {'Resource_List.select': '1:ncpus=1',
                'Resource_List.place': 'excl'})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(JOB, 'exec_vnode', id=jid, extend='x')
        exec_vnode = status[0]['exec_vnode']
        node1 = exec_vnode.split(':')[0][1:]
        jid = self.submit_job(
            1, {'Resource_List.select': '1:ncpus=1',
                'Resource_List.place': 'excl'})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        jid = self.submit_job(
            1, {'Resource_List.select': '1:ncpus=1',
                'Resource_List.place': 'excl'})
        self.server.expect(JOB, {'job_state': 'F'}, id=jid, extend='x')
        status = self.server.status(JOB, 'exec_vnode', id=jid, extend='x')
        exec_vnode = status[0]['exec_vnode']
        node2 = exec_vnode.split(':')[0][1:]
        # Check that 3rd job falls on the same node as 1st job as per
        # node_sort_key. Node on which 1st job ran has lower last_used_time
        # than the node on which 2nd job ran.
        self.assertEqual(node1, node2)

    @timeout(1200)
    def test_power_ramp_down_nodes(self):
        """
        Test power hook will ramp down the nodes if power_ramp_rate_enable
        is enabled and node_idle_limit is reached.
        """
        self.setup_power_ramp_rate()
        a = {"power_ramp_rate_enable": True, 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 60}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 15 mins to ramp down all the nodes")
        time.sleep(900)
        # Do not check for the offline nodes and 1 login node
        nn = self.offnodes + 1
        self.server.expect(
            NODE, {'state=sleep': len(self.server.status(NODE)) - nn})
        self.cleanup_power_ramp_rate()

    @timeout(1000)
    def test_power_ramp_down_max_concurennt_nodes(self):
        """
        Test power hook will ramp down only the number of
        max_concurrent nodes specified in conf file per hook run.
        """
        self.setup_power_ramp_rate()
        a = {"power_ramp_rate_enable": True, 'node_idle_limit': '10',
             'max_concurrent_nodes': '2'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 60}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 90 secs to ramp down 2 nodes")
        time.sleep(90)
        a = {'enabled': 'False'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.server.expect(NODE, {'state=sleep': 2})
        self.cleanup_power_ramp_rate()

    @timeout(1500)
    def test_power_ramp_up_nodes(self):
        """
        Test when a job is calandered on a vnode which is in sleep state,
        the node will be ramped up and job will run.
        """
        self.setup_power_ramp_rate()
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        a = {"power_ramp_rate_enable": True, 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 60}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 15 mins to ramp down all the nodes")
        time.sleep(900)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        t = int(time.time())
        jid = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        self.scheduler.log_match(
            jid + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        self.logger.info("Waiting for 90 secs to ramp up the calandered node")
        time.sleep(90)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])
        self.cleanup_power_ramp_rate()

    @timeout(1200)
    def test_max_jobs_analyze_limit_ramp_up(self):
        """
        Test that even when 4 jobs are calandered only nodes assigned
        to max_jobs_analyze_limit number of jobs will be considered
        for ramping up.
        """
        self.setup_power_ramp_rate()
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, SERVER, {'backfill_depth': '4'})
        a = {"power_ramp_rate_enable": True,
             'max_jobs_analyze_limit': '2', 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 60}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 15 mins to ramp down all the nodes")
        time.sleep(900)
        # Do not check for the offline nodes and 1 login node
        nn = self.offnodes + 1
        self.server.expect(
            NODE, {'state=sleep': len(self.server.status(NODE)) - nn})
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        j1id = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        j2id = self.submit_job(1000, {'Resource_List.vnode': self.names[1]})
        j3id = self.submit_job(1000, {'Resource_List.vnode': self.names[2]})
        j4id = self.submit_job(1000, {'Resource_List.vnode': self.names[3]})
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.logger.info("Waiting for 90 secs to ramp up the calandered nodes")
        time.sleep(90)
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        self.server.expect(JOB, {'job_state': 'R'}, id=j1id)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])
        self.server.expect(JOB, {'job_state': 'R'}, id=j2id)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[1])
        self.server.expect(JOB, {'job_state': 'Q'}, id=j3id)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[2])
        self.server.expect(JOB, {'job_state': 'Q'}, id=j4id)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[3])
        self.cleanup_power_ramp_rate()

    @timeout(1200)
    def test_power_ramp_up_poweroff_eligible(self):
        """
        Test that nodes are considered for ramp down and ramp up
        even when poweroff_elgible is set to false.
        """
        self.setup_power_ramp_rate()
        self.scheduler.set_sched_config({'strict_ordering': 'True ALL'})
        self.server.manager(MGR_CMD_SET, NODE, {'poweroff_eligible': 'False'},
                            id=self.names[0])
        a = {"power_ramp_rate_enable": True, 'node_idle_limit': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        a = {'freq': 60}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        a = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id='PBS_power',
                            sudo=True)
        self.logger.info("Waiting for 15 mins to ramp down all the nodes")
        time.sleep(900)
        self.server.expect(NODE, {'state': 'sleep'}, id=self.names[0])
        a = {"node_idle_limit": "1800", 'min_node_down_delay': '30'}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        t = int(time.time())
        jid = self.submit_job(1000, {'Resource_List.vnode': self.names[0]})
        self.scheduler.log_match(
            jid + ';Job is a top job and will run at',
            max_attempts=10, starttime=t)
        self.logger.info("Waiting for 90 secs to ramp up calandered node")
        time.sleep(90)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(NODE, {'state': 'job-exclusive'}, id=self.names[0])
        self.cleanup_power_ramp_rate()

    def tearDown(self):
        a = {"power_ramp_rate_enable": False,
             "power_on_off_enable": False,
             'node_idle_limit': '1800',
             'min_node_down_delay': '1800',
             "max_jobs_analyze_limit": "100",
             "max_concurrent_nodes": "5"}
        self.modify_hook_config(attrs=a, hook_id='PBS_power')
        self.disable_power()
        TestFunctional.tearDown(self)
