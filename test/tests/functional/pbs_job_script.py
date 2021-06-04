# coding: utf-8

# Copyright (C) 1994-2021 Altair Engineering, Inc.
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


class TestPbsJobScript(TestFunctional):
    """
    Test suite for testing PBS's job script functionality
    """

    def submit_job(self, addnewline=False):
        a = {'resources_available.ncpus': 2}
        self.mom.create_vnodes(a, 500, vname='Verylongvnodename')

        selstr = "#PBS -l select=1"
        for node in range(500):
            selstr += ":ncpus=1:vnode=Verylongvnodename[" + str(node) + "]+1"
            if addnewline and node == 250:
                selstr += "\\\n"
        selstr = selstr[0:-2]

        scr = []
        scr += [selstr + '\n']
        scr += ['%s 100\n' % (self.mom.sleep_cmd)]

        j = Job()
        j.create_script(scr)
        jid = self.server.submit(j)
        return jid

    def test_long_select_spec(self):
        """
        Test that PBS is able to accept jobs scripts with very long select
        specification with no newline in it.
        """
        jid = self.submit_job()
        execvnode = ""
        for node in range(500):
            execvnode += "(Verylongvnodename[" + str(node) + "]:ncpus=1)+"
        execvnode = execvnode[0:-1]
        self.server.expect(JOB, {'job_state': 'R', 'exec_vnode': execvnode},
                           id=jid)

    def test_long_select_spec_extend(self):
        """
        Test that PBS is able to accept jobs scripts with very long select
        specification with newline in it.
        """
        jid = self.submit_job(addnewline=True)
        execvnode = ""
        for node in range(500):
            execvnode += "(Verylongvnodename[" + str(node) + "]:ncpus=1)+"
        execvnode = execvnode[0:-1]
        self.server.expect(JOB, {'job_state': 'R', 'exec_vnode': execvnode},
                           id=jid)
