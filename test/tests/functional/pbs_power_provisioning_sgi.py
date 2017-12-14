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

    def setUp(self):
        """
        Don't set any special flags.
        Use the MOM's that are already setup or define the ones passed in.
        """
        TestFunctional.setUp(self)

        # Delete all the nodes then recreate them.
        done = set()
        nodes = self.server.status(NODE)
        for n in nodes:
            host = n['Mom']
            if host is None:
                continue
            if host == self.server.hostname:
                self.server.manager(MGR_CMD_DELETE, NODE, None, host)

    def setup_sgi_api(self, script, perm=0755):
        """
        Setup a fake sgi_api script on all the nodes.
        Return the number of nodes.
        """
        (fd, fn) = self.du.mkstemp()
        os.write(fd, script)
        os.close(fd)
        os.chmod(fn, perm)

        done = set()
        nodes = self.server.status(NODE)
        for n in nodes:
            host = n['Mom']
            if host is None:
                continue
            if host in done:
                continue
            done.add(host)
            dir = "/opt/sgi/ta"
            dest = os.path.join(dir, "sgi_power_api.py")
            self.server.du.run_cmd(host, "mkdir -p " + dir, sudo=True)
            self.server.du.run_copy(host, fn, dest, True)
            # Set PBS_PMINAME=sgi in pbs_environment so the power hook
            # will use the SGI functionality.
            mom = self.moms[host]
            self.server.du.set_pbs_environment(host,
                                               vars={"PBS_PMINAME": "sgi"})
            self.server.du.run_cmd(host, "chown root %s" %
                                   os.path.join(
                                       mom.pbs_conf[
                                           'PBS_HOME'], "pbs_environment"),
                                   sudo=True)

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
            dir = "/opt/sgi/ta"
            dest = os.path.join(dir, "sgi_power_api.py")
            self.server.du.run_cmd(host, "rm " + dest, sudo=True)

        return len(nodes)

    def enable_power(self):
        """
        Enable power_provisioning on the server.
        """
        a = {'power_provisioning': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

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
                              {'Resource_List.select': '%d:eoe=%s' % (num,
                                                                      eoe)})
        self.eoe_check(jid, eoe, secs)
        return jid

    def test_sgi_eoe_job(self):
        """
        Submit jobs with an eoe value and check that messages are logged
        indicating PMI activity, and current_eoe and resources_used.energy
        get set.
        """

        # There needs to be at least one Mom that is not running on the
        # server host.
        multimom = False
        for filt in self.server.filter(NODE, 'Mom'):
            mom = filt.partition('=')[2]
            if mom != self.server.shortname:
                self.logger.info("found different mom %s from local %s" %
                                 (mom, self.server.shortname))
                multimom = True
                break
        if not multimom:
            self.skip_test("No mom defined on non-server host")
            return

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

        num = self.setup_sgi_api(script)
        self.enable_power()		# enable hooks

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

    def tearDown(self):
        self.revert_sgi_api()  # remove file
        TestFunctional.tearDown(self)
