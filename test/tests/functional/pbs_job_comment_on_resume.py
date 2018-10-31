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


class TestJobComment(TestFunctional):

    """
    Testing job comment is accurate
    """

    def test_job_comment_on_resume(self):
        """
        Testing whether job comment is accurate
        after resuming from suspended state.
        """
        attr = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, attr, self.mom.shortname)
        attr = {'queue_type': 'execution', 'started': 't', 'enabled': 't',
                'priority': 200}
        self.server.manager(MGR_CMD_CREATE, QUEUE, attr, id='expressq')
        J = Job(TEST_USER)
        jid1 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        J = Job(TEST_USER, {'queue': 'expressq'})
        jid2 = self.server.submit(J)
        self.server.expect(JOB, {'job_state': 'S'}, id=jid1)
        self.server.delete(jid2, wait=True)
        self.server.log_match(
            jid2 + ";dequeuing from expressq")
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, {'comment': (MATCH_RE, '.*Job run at.*')})
