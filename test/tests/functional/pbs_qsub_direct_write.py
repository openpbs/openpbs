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


class TestQsub_direct_write(TestFunctional):
    """
    validate qsub direct write option.
    """

    def test_direct_write_when_job_succeeds(self):
        """
        submit a sleep job and make sure that the std_files
        are getting directly written directly to the mapped
        directory when direct_files option is used.
        """
        j = Job(TEST_USER)
        j.set_attributes({ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = DshUtils().mkdtemp(uid=TEST_USER.uid)
        mapping_dir = DshUtils().mkdtemp(uid=TEST_USER.uid)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir
             + ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.log_match(jid + ";Job Run at", max_attempts=10)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(2, file_count)

    def test_direct_write_without_config_entry(self):
        """
        submit a sleep job and make sure that the std_files
        is directly written to the submission directory when it is
        accessible from mom and direct_files option is used
        but submission directory is not mapped in mom config file.
        """
        j = Job(TEST_USER)
        j.set_attributes({ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = DshUtils().mkdtemp(uid=TEST_USER.uid)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.log_match(jid + ";Job Run at", max_attempts=10)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(2, file_count)

    def test_qalter_direct_write(self):
        """
        submit a job and make sure that it in queued state.
        alter the job with -koed and check whether it is
        reflecting in qstat -f output.
        """
        mydate = int(time.time()) + 60
        j = Job(TEST_USER)
        attribs = {
            ATTR_a: time.strftime(
                '%m%d%H%M',
                time.localtime(
                    float(mydate)))}
        j.set_attributes(attribs)
        jid = self.server.submit(j)
        attribs = {ATTR_k: 'oed'}
        try:
            self.server.alterjob(jid, attribs)
            if self.server.expect(JOB, {'job_state': 'W'},
                                  id=jid):
                self.server.expect(JOB, attribs,
                                   id=jid)
        except PbsAlterError as e:
            print str(e)
