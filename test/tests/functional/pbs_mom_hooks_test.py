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
class TestMoMHooks(TestFunctional):
    """
    This test covers basic functionality of MoM Hooks
    """

    def setUp(self):
        TestFunctional.setUp(self)
        if len(self.moms) != 2:
            self.skipTest('test requires two MoMs as input, ' +
                          'use -p moms=<mom1>:<mom2>')
        self.momA = self.moms.values()[0]
        self.momB = self.moms.values()[1]
        self.hostA = self.momA.shortname
        self.hostB = self.momB.shortname
        a = {'resources_available.ncpus': 8, 'resources_available.mem': '8gb'}
        for mom in self.moms.values():
            self.server.manager(MGR_CMD_SET, NODE, a, mom.shortname)
        pbsdsh_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                  'bin', 'pbsdsh')
        self.job1 = Job()
        self.job1.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            "sleep 20\n")
        self.job2 = Job()
        self.job2.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            pbsdsh_cmd + " -n 1 /bin/echo hi\n" +
            pbsdsh_cmd + " -n 1 /bin/ls\n" +
            "sleep 20")
        self.job3 = Job()
        self.job3.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            "sleep 600\n")
        self.job4 = Job()
        self.job4.create_script(
            "#PBS -l select=vnode=" + self.hostA + "+vnode=" + self.hostB +
            ":mem=4mb\n" +
            pbsdsh_cmd + " -n 1 /bin/date\n" +
            "sleep 20\n" +
            "exit 7")

    def hook_init(self, hook_name, hook_event, hook_body=None,
                  freq=None):
        """
        Dynamically create and import a MoM hook into the server.
        hook_name: the name of the hook to create. No default
        hook_event: the event type of the hook. No default
        hook_body: the body of the hook. If None, it is created "on-the-fly"
        based on vnode_comment, resc_avail_file, resc_avail_ncpus by calling
        customize_hook.
        resc_avail_file: the file size to set in the hook. Defaults to 1gb
        resc_avail_ncpus: the ncpus to set in the hook. Defaults to 2
        freq: The frequency of the periodic hook.
        ignoreerror: if True, ignore an error in importing the hook. This is
        needed for tests that test a hook error. Defaults to False.

        Return True on success and False otherwise.
        """
        a = {}
        if hook_event:
            a['event'] = hook_event
        if freq:
            a['freq'] = freq
        a['enabled'] = 'true'
        a['alarm'] = 5

        self.server.create_import_hook(hook_name, a, hook_body,
                                       overwrite=True)

    def basic_hook_accept_periodic(self, hook_name, freq, hook_body):

        hook_event = "exechost_periodic"
        self.hook_init(hook_name, hook_event, hook_body, freq=freq)
        exp_msg = ["Hook;pbs_python;event is %s" % hook_event.upper(),
                   "Hook;pbs_python;hook_name is %s" % hook_name,
                   "Hook;pbs_python;hook_type is site",
                   "Hook;pbs_python;requestor_host is %s" % self.hostA,
                   ]
        for msg in exp_msg:
            self.momA.log_match(msg)
        exp_msg[3] = "Hook;pbs_python;requestor_host is %s" % self.hostB
        for msg in exp_msg:
            self.momB.log_match(msg)
        msg = "Not allowed to update vnode 'aspasia'"
        msg += ", as it is owned by a different mom"
        self.server.log_match(msg)

        a = {'state': 'offline',
             'resources_available.file': '17tb',
             'resources_available.ncpus': 17,
             'resources_available.mem': '700gb',
             'comment': "Comment update done  by %s hook @ %s" %
             (hook_name, self.hostA)}
        self.server.expect(NODE, a, id=self.hostA)
        a['comment'] = "Comment update done  by %s hook @ %s" % (
            hook_name, self.hostB)
        self.server.expect(NODE, a, id=self.hostB)
        a = {'resources_available.file': '500tb',
             'resources_available.mem': '300gb'}
        self.server.expect(NODE, a, id="aspasia")

    def test_exechost_periodic_with_accept(self):
        """
        Test exechost_periodic which accepts the event
        """
        self.basic_hook_accept_periodic("period", 5, period_py)

    def tearDown(self):
        TestFunctional.tearDown(self)
        hooks = self.server.status(HOOK)
        for h in hooks:
            if h['id'] in ("period",):
                self.server.manager(MGR_CMD_DELETE, HOOK, id=h['id'])

period_py = """import pbs
import os
import sys
import time

local_node = pbs.get_local_nodename()
other_node = local_node
other_node2 = "aspasia"

def print_attribs(pbs_obj):
   for a in pbs_obj.attributes:
      v = getattr(pbs_obj, a)
      if (v != None) and str(v) != "":
         pbs.logmsg(pbs.LOG_DEBUG, "%s = %s" % (a,v))

s = pbs.server()

jobs = pbs.server().jobs()
for j in jobs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found job %s" % (j.id))
   print_attribs(j)

queues = s.queues()
for q in queues:
   pbs.logmsg(pbs.LOG_DEBUG, "Found queue %s" % (q.name))
   for k in q.jobs():
     pbs.logmsg(pbs.LOG_DEBUG, "Found job %s in queue %s" % (k.id, q.name))

resvs = s.resvs()
for r in resvs:
   pbs.logmsg(pbs.LOG_DEBUG, "Found resv %s" % (r.id))

vnodes = s.vnodes()
for v in vnodes:
   pbs.logmsg(pbs.LOG_DEBUG, "Found vnode %s" % (v.name))

e = pbs.event()

pbs.logmsg(pbs.LOG_DEBUG,
           "printing pbs.event() values ---------------------->")
pbs.logmsg(pbs.LOG_DEBUG, "event is %s" % ("EXECHOST_PERIODIC"))

pbs.logmsg(pbs.LOG_DEBUG, "hook_name is %s" % (e.hook_name))
pbs.logmsg(pbs.LOG_DEBUG, "hook_type is %s" % (e.hook_type))
pbs.logmsg(pbs.LOG_DEBUG, "requestor is %s" % (e.requestor))
pbs.logmsg(pbs.LOG_DEBUG, "requestor_host is %s" % (e.requestor_host))

vn = pbs.event().vnode_list

pbs.logmsg(pbs.LOG_DEBUG, "vn is %s type is %s" % (str(vn), type(vn)))
for k in pbs.event().vnode_list.keys():

   if k == local_node:
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pcpus=%d" % (k, vn[k].pcpus));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: pbs_version=%s" % (k, vn[k].pbs_version));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%d" % (k,
                "ncpus", vn[k].resources_available["ncpus"]));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s type=%s" % (k,
                "mem", vn[k].resources_available["mem"],
                type(vn[k].resources_available["mem"])));
      pbs.logmsg(pbs.LOG_DEBUG, "%s: resources_available[%s]=%s" % (k, "arch",
                    vn[k].resources_available["arch"]));

if other_node not in vn:
   vn[other_node] = pbs.vnode(other_node)

vn[other_node].pcpus = 7
vn[other_node].ntype = pbs.ND_PBS
vn[other_node].state = pbs.ND_OFFLINE
vn[other_node].sharing = pbs.ND_FORCE_EXCL
vn[other_node].resources_available["ncpus"] = 17
vn[other_node].resources_available["file"] = pbs.size("17tb")
vn[other_node].resources_available["mem"] = pbs.size("700gb")
vn[other_node].comment = "Comment update done  by period hook "
vn[other_node].comment += "@ %s" % (local_node)

if other_node2 not in vn:
   vn[other_node2] = pbs.vnode(other_node2)

vn[other_node2].resources_available["file"] = pbs.size("500tb")
vn[other_node2].resources_available["mem"] = pbs.size("300gb")
"""
