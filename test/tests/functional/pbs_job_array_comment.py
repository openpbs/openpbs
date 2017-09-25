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


class TestJobArrayComment(TestFunctional):
    """
    Testing job array comment is accurate
    """

    def test_job_array_comment(self):
        """
        Testing job array comment is correct when one or more sub jobs
        are rejected by mom
        """
        attr = {'resources_available.ncpus': 10}
        self.server.manager(MGR_CMD_SET, NODE, attr)
        attr = {'job_history_enable': 'true'}
        self.server.manager(MGR_CMD_SET, SERVER, attr)
        # create a mom hook that rejects and deletes subjob 0, 5, and 7
        hook_name = "reject_subjob"
        hook_body = (
            "import pbs\n"
            "import re\n"
            "e = pbs.event()\n"
            "jid = str(e.job.id)\n"
            "if re.match(r'[0-9]*\[[057]\]', jid):\n"
            "    e.job.delete()\n"
            "    e.reject()\n"
            "else:\n"
            "    e.accept()\n"
        )
        attr = {'event': 'execjob_begin', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, attr, hook_body)

        test_job_array = Job(TEST_USER, attrs={
            ATTR_J: '0-9',
            'Resource_List.select': 'ncpus=1'
        })
        test_job_array.set_sleep_time(1)
        jid = self.server.submit(test_job_array)
        attr = {
            ATTR_state: 'B',
            ATTR_comment: (MATCH_RE, 'Job Array Began at .*')
        }
        self.server.expect(JOB, attr, id=jid, attrop=PTL_AND)
        self.server.expect(JOB, {ATTR_comment: 'Subjob failed'},
                           id=create_subjob_id(jid, 0), extend='x')
        self.server.expect(JOB, {ATTR_comment: 'Subjob failed'},
                           id=create_subjob_id(jid, 5), extend='x')
        self.server.expect(JOB, {ATTR_comment: 'Subjob failed'},
                           id=create_subjob_id(jid, 7), extend='x')


def create_subjob_id(job_array_id, subjob_index):
    """
    insert subjob index into the square brackets of job array id
    """
    idx = job_array_id.find('[]')
    return job_array_id[:idx+1] + str(subjob_index) + job_array_id[idx+1:]
