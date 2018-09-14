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


class TestQrun(TestFunctional):

    def setUp(self):
        TestFunctional.setUp(self)
        # set ncpus to a known value, 2 here
        a = {'resources_available.ncpus': 2}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            self.mom.shortname, expect=True)
        self.pbs_exec = self.server.pbs_conf['PBS_EXEC']
        self.qrun = os.path.join(self.pbs_exec, 'bin', 'qrun')

    def test_misuse_of_qrun(self):
        j1 = Job(TEST_USER)
        # submit a multi-chunk job
        j1 = Job(attrs={'Resource_List.select':
                        'ncpus=2:host=%s+ncpus=2:host=%s' %
                 (self.mom.shortname, self.mom.shortname)})
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid1)
        cmd = [self.qrun, '-H', '"\'(%s)+(%s)\'"' %
               (self.mom.shortname, self.mom.shortname), jid1]
        ret = self.du.run_cmd(self.server.hostname, cmd,
                              sudo=True, as_script=True)
        msg = "qrun: Unknown node  \'(%s)+(%s)\'" % \
            (self.mom.shortname, self.mom.shortname)
        self.assertIn(msg, ret['err'][-1])
        j2 = Job(TEST_USER)
        # submit a sleep job
        j2 = Job(attrs={'Resource_List.select': 'ncpus=3'})
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {ATTR_state: 'Q'}, jid2)
        cmd = [self.qrun, '-H', '"\'(%s)+(%s)\'"' %
               (self.mom.shortname, self.mom.shortname), jid2]
        ret = self.du.run_cmd(self.server.hostname, cmd,
                              sudo=True, as_script=True)
        self.assertIn(msg, ret['err'][-1])
