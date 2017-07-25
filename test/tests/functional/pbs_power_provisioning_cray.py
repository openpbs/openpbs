# coding: utf-8

# Copyright (C) 1994-2017 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

from tests.functional import *
import json
from subprocess import Popen, PIPE


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

    def setup_cray_eoe(self):
        """
        Setup a eoe list for all the nodes.
        Get possible values for pcaps using capmc command.
        """
        eoe_vals = "low, med, high"
        min_nid = 0
        max_nid = 0
        for n in self.server.status(NODE):
            name = n['id']
            if 'resources_available.PBScraynid' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"resources_available.eoe": eoe_vals},
                                    name)
                craynid = n['resources_available.PBScraynid']
                if min_nid == 0 or craynid < min_nid:
                    min_nid = craynid
                if craynid > max_nid:
                    max_nid = craynid

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
        a = {'power_provisioning': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        done = set()		# check that hook becomes active
        nodes = self.server.status(NODE)
        n = nodes[0]
        host = n['Mom']
        self.assertTrue(host is not None)
        mom = self.moms[host]
        s = mom.log_match(
            "Hook;PBS_power.HK;copy hook-related file request received",
            starttime=self.server.ctime, max_attempts=60)
        self.assertTrue(s)

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
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
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

    def eoe_check(self, jid, eoe, secs):
        # check that job is running and that the vnode has current_eoe set
        qstat = self.server.status(JOB, id=jid)
        vname = qstat[0]['exec_vnode'].partition(':')[0].strip('(')
        self.server.expect(VNODE, {'current_eoe': eoe}, id=vname)

        self.server.expect(JOB, 'job_state', op=UNSET, id=jid, offset=secs)
        host = qstat[0]['exec_host'].partition('/')[0]
        mom = self.moms[host]		# top mom
        s = mom.log_match(".*;Job;%s;PMI: reset current_eoe.*" % jid,
                          regexp=True, starttime=self.server.ctime,
                          max_attempts=10)
        self.assertTrue(s)
        # check that vnode has current_eoe unset
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

        self.setup_cray_eoe()   # setup hook and eoe
        self.enable_power()		# enable hooks

        # Make sure eoe is set correctly on the vnodes
        eoes = set()		# use sets to be order independent
        for n in self.server.status(NODE):
            name = n['id']
            if 'resources_available.eoe' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"power_provisioning": True}, name)
                curr = n['resources_available.eoe'].split(',')
                self.logger.info("%s has eoe values %s" % (name, str(curr)))
                if len(eoes) == 0:  # empty set
                    eoes.update(curr)
                else:  # all vnodes must have same eoes
                    self.assertTrue(eoes == set(curr))
        self.assertTrue(len(eoes) > 0)

        # submit jobs for each eoe value
        x = 5
        while len(eoes) > 0:
            eoe = eoes.pop()
            jid = self.eoe_job(x, eoe)
            self.energy_check(jid)

    def tearDown(self):
        TestFunctional.tearDown(self)
