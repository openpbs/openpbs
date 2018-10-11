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


class Test_power_provisioning_sgi(TestFunctional):

    """
    Test power provisioning feature for the SGI platform.

    Create stub SGI API script at /opt/sgi/ta  and load eoe's from it.
    """
    script = \
        """
# Fake SGI API python
import time

def VerifyConnection():
    return "connected"

def ListAvailableProfiles():
    return ['100W', '150W', '200W', '250W', '300W', '350W', '400W', '450W',
            '500W', 'NONE']

def MonitorStart( nodeset_name, profile ):
    return None

def MonitorReport( nodeset_name ):
    # fake an energy value
    fmt = "%Y/%d/%m"
    now = time.time()
    st = time.strptime(time.strftime(fmt, time.localtime(now)), fmt)
    night = time.mktime(st)
    return ['total_energy', (now - night)/60000, 1415218704.5979109]

def MonitorStop( nodeset_name ):
    return None

def NodesetCreate( nodeset_name, node_hostname_list ):
    return None

def NodesetDelete( nodeset_name ):
    return None
"""
    power_nodes = None

    def setUp(self):
        """
        Don't set any special flags.
        Use the MOM's that are already setup or define the ones passed in.
        """
        TestFunctional.setUp(self)
        nodes = self.server.status(NODE)
        if(self.check_mom_configuration()):
            for n in nodes:
                host = n['Mom']
                if host is None:
                    continue
                # Delete the server side Mom
                if host == self.server.shortname:
                    self.server.manager(MGR_CMD_DELETE, NODE, None, host)
                    break
            # setup environment for power provisioning
            self.power_nodes = self.setup_sgi_api(self.script)
            if(self.power_nodes == 0):
                self.skip_test("No mom found with power profile setup")
            else:
                # enable power hook
                self.enable_power()
                for i in range(0, len(self.moms)):
                    a = {'power_provisioning': 'True'}
                    self.server.manager(
                        MGR_CMD_SET, NODE, a, id=self.moms.keys()[i])
        else:
            self.skip_test("No mom defined on non-server host")

    def check_mom_configuration(self):
        """
        There needs to be at least one Mom that is not running on the
        server host.
        """
        multimom = False
        moms = self.server.filter(NODE, 'Mom')
        if moms is not None:
            for filt in moms.values():
                if filt[0] != self.server.shortname:
                    self.logger.info("found different mom %s from local %s" %
                                     (filt, self.server.shortname))
                    multimom = True
                    return True
            if not multimom:
                return False
        else:
            self.skip_test(
                "No mom found at server/non-server host")

    def setup_sgi_api(self, script, perm=0o755):
        """
        Setup a fake sgi_api script on all the nodes.
        Return the number of nodes.
        """
        fn = self.du.create_temp_file(body=script)
        self.du.chmod(path=fn, mode=perm, sudo=True)

        done = set()
        nodes = self.server.status(NODE)
        for n in nodes:
            host = n['Mom']
            if host is None:
                continue
            if host in done:
                continue
            done.add(host)
            pwr_dir = os.path.join(os.sep, "opt", "clmgr", "power-service")
            dest = os.path.join(pwr_dir, "hpe_clmgr_power_api.py")
            self.server.du.run_cmd(host, "mkdir -p " + pwr_dir, sudo=True)
            self.server.du.run_copy(host, fn, dest, True)
            # Set PBS_PMINAME=sgi in pbs_environment so the power hook
            # will use the SGI functionality.
            mom = self.moms[host]
            if mom is not None:
                environ = {"PBS_PMINAME": "sgi"}
                self.server.du.set_pbs_environment(host,
                                                   environ=environ)
                self.server.du.run_cmd(host, "chown root %s" %
                                       os.path.join(mom.pbs_conf[
                                                    'PBS_HOME'],
                                                    "pbs_environment"),
                                       sudo=True)
            else:
                self.skip_test("Need to pass atleast one mom "
                               "use -p moms=<mom1:mom2>")

        os.remove(fn)
        return len(nodes)

    def revert_sgi_api(self):
        """
        Remove any fake sgi_api from the nodes.
        Return the number of nodes.
        """
        done = set()
        nodes = self.server.status(NODE)
        for n in nodes:
            host = n['Mom']
            if host is None:
                continue
            if host in done:
                continue
            done.add(host)
            pwr_dir = os.path.join(os.sep, "opt", "clmgr", "power-service")
            dest = os.path.join(pwr_dir, "hpe_clmgr_power_api.py")
            self.server.du.run_cmd(host, "rm " + dest, sudo=True)

    def enable_power(self):
        """
        Enable power_provisioning on the server.
        """
        a = {'enabled': 'True'}
        hook_name = "PBS_power"
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_name,
                            sudo=True)
        done = set()		# check that hook becomes active
        nodes = self.server.status(NODE)
        for n in nodes:
            host = n['Mom']
            if host is None:
                continue
            if host in done:
                continue
            mom = self.moms[host]
            s = mom.log_match(
                "Hook;PBS_power.HK;copy hook-related file request received",
                starttime=self.server.ctime, max_attempts=60)
            self.assertTrue(s)
            mom.signal("-HUP")

    def submit_job(self, secs=10, attr=None):
        """
        secs: sleep time for the job
        a: any job attributes
        """
        attr['Keep_Files'] = 'oe'
        j = Job(TEST_USER, attrs=attr)
        j.set_sleep_time(secs)
        self.logger.info(str(j))
        jid = self.server.submit(j)
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
                              {'Resource_List.select': '%d:eoe=%s' % (num,
                                                                      eoe)})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.eoe_check(jid, eoe, secs)
        return jid

    def test_sgi_job(self):
        """
        Submit jobs with an eoe value and check that messages are logged
        indicating PMI activity, and current_eoe and resources_used.energy
        get set.
        """
        # Make sure eoe is set correctly on the vnodes
        eoes = set()		# use sets to be order independent
        nodes = list()
        for n in self.server.status(NODE):
            name = n['id']
            if 'resources_available.eoe' in n:
                self.server.manager(MGR_CMD_SET, NODE,
                                    {"power_provisioning": True}, name)
                nodes.append(name)
                curr = n['resources_available.eoe'].split(',')
                self.logger.info("%s has eoe values %s" % (name, str(curr)))
                if len(eoes) == 0:  # empty set
                    eoes.update(curr)
                else:  # all vnodes must have same eoes
                    self.assertTrue(eoes == set(curr))
        self.assertTrue(len(eoes) > 0)

        # submit jobs for each eoe value
        while len(eoes) > 0:
            eoe = eoes.pop()
            for x in range(1, len(nodes) + 1):
                jid = self.eoe_job(x, eoe)
                self.energy_check(jid)

    def test_sgi_eoe_job(self):
        """
        Submit jobs with an eoe values and check that messages are logged
        indicating PMI activity, and current_eoe and resources_used.energy
        get set.
        """
        eoes = ['100W', '150W', '450W']
        for x in range(1, self.power_nodes + 1):
            while len(eoes) > 0:
                eoe_profile = eoes.pop()
                jid = self.eoe_job(x, eoe_profile)
                self.energy_check(jid)

    def test_sgi_request_more_power_nodes(self):
        """
        Submit job with available+1 power nodes and verify job comment.
        """
        total_nodes = self.power_nodes + 1
        jid = self.submit_job(10, {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (total_nodes, '150W')})
        msg = "Can Never Run: Not enough total nodes available"
        self.server.expect(JOB, {'job_state': 'Q', 'comment': msg},
                           id=jid)

    def test_sgi_job_multiple_eoe(self):
        """
        Submit jobs requesting multiple eoe and job should rejected by qsub.
        """
        try:
            a = {'Resource_List.place': 'scatter',
                 'Resource_List.select': '10:eoe=150W+10:eoe=300W'}
            self.submit_job(attr=a)
        except PbsSubmitError as e:
            self.assertTrue(
                'Invalid provisioning request in chunk' in e.msg[0])

    def test_sgi_server_prov_off(self):
        """
        Submit jobs requesting eoe when power provisioning unset on server
        and verify that jobs wont run.
        """
        a = {'enabled': 'False'}
        hook_name = "PBS_power"
        self.server.manager(MGR_CMD_SET, PBS_HOOK, a, id=hook_name,
                            sudo=True)
        self.server.expect(SERVER, {'power_provisioning': 'False'})
        eoes = ['150W', '300W', '450W']
        for profile in eoes:
            jid = self.submit_job(10,
                                  {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (self.power_nodes, profile)})
            self.server.expect(JOB, {
                'job_state': 'Q',
                'comment': 'Not Running: No available resources on nodes'},
                id=jid)

    def test_sgi_node_prov_off(self):
        """
        Submit jobs requesting eoe and verify that jobs won't run on
        nodes where power provisioning is set to false.
        """
        eoes = ['100W', '250W', '300W', '400W']
        # set power_provisioning to off where eoe is set to false
        for i in range(0, self.power_nodes):
            a = {'power_provisioning': 'False'}
            self.server.manager(MGR_CMD_SET, NODE, a, id=self.moms.keys()[i])
        for profile in eoes:
            jid = self.submit_job(10,
                                  {'Resource_List.place': 'scatter',
                                   'Resource_List.select': '%d:eoe=%s'
                                   % (self.power_nodes, profile)})
            msg = "Not Running: No available resources on nodes"
            self.server.expect(JOB, {'job_state': 'Q', 'comment': msg},
                               id=jid)

    def test_sgi_job_preemption(self):
        """
        Submit job to a high priority queue and verify
        that job is preempted by requeueing.
        """
        for i in range(0, self.power_nodes):
            a = {'resources_available.ncpus': 1}
            self.server.manager(MGR_CMD_SET, NODE, a, id=self.moms.keys()[i])
        self.server.manager(MGR_CMD_CREATE, QUEUE,
                            {'queue_type': 'execution', 'started': 'True',
                             'enabled': 'True', 'priority': 150}, id='workq2')
        jid = self.submit_job(30,
                              {'Resource_List.place': 'scatter',
                               'Resource_List.select': '%d:eoe=%s'
                               % (self.power_nodes, '150W')})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        t = int(time.time())
        jid_workq2 = self.submit_job(10, {ATTR_queue: 'workq2',
                                          'Resource_List.place': 'scatter',
                                          'Resource_List.select': '%d:eoe=%s' %
                                          (self.power_nodes, '150W')})
        self.server.expect(JOB, {'job_state': 'R'}, id=jid_workq2)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        self.scheduler.log_match("Job preempted by requeuing", starttime=t)

    def tearDown(self):
        # remove SGI fake script file
        self.revert_sgi_api()
        TestFunctional.tearDown(self)
