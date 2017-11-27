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


class Test_enforce_on_exclhost(TestFunctional):
    """
    Check whether or not jobs with exceeded limits (burst, sum, mem)
    will survive the limit enforcement if the enforce_on_exclhost
    is false
    """

    def setUp(self):
        """
        Set enforce_on_exclhost to false
        """

        TestFunctional.setUp(self)

        self.mom.add_config({'$enforce_on_exclhost': 'false'})
        self.mom.restart()

    def test_job_not_killed_cpuaverage(self):
        """
        Set cpuaverage enforcement and run a job with exclhost
        Check whether or not the job will survive
        """

        mom_conf_attr = {'$enforce': 'cpuaverage',
                         '$enforce average_trialperiod': "1",
                         '$enforce average_percent_over': "1",
                         '$enforce average_cpufactor': "0.1"}
        self.mom.add_config(mom_conf_attr)
        self.mom.restart()

        script = []
        script += ['#!/bin/bash']
        script += ['yes > /dev/null']

        j = Job(TEST_USER, attrs={
            'Resource_List.select': '1:ncpus=1',
            'Resource_List.place': 'exclhost'})

        j.create_script(body=script)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Giving a chance to pbs to kill the job...")
        time.sleep(15)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_job_not_killed_cpuburst(self):
        """
        Set cpuburst enforcement and run a job with exclhost
        Check whether or not the job will survive
        """

        mom_conf_attr = {'$enforce': 'cpuburst',
                         '$enforce delta_percent_over': "1",
                         '$enforce delta_cpufactor': "0.1"}
        self.mom.add_config(mom_conf_attr)
        self.mom.restart()

        script = []
        script += ['#!/bin/bash']
        script += ['yes > /dev/null']

        j = Job(TEST_USER, attrs={
            'Resource_List.select': '1:ncpus=1',
            'Resource_List.place': 'exclhost'})

        j.create_script(body=script)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Giving a chance to pbs to kill the job...")
        time.sleep(15)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_job_not_killed_mem(self):
        """
        Set mem enforcement and run a job with exclhost
        Check whether or not the job will survive
        """

        self.mom.add_config({'$enforce': 'mem'})
        self.mom.restart()

        script = []
        script += ['#!/bin/bash']
        script += ['sleep 1000']

        j = Job(TEST_USER, attrs={
            'Resource_List.select': '1:ncpus=1:mem=1kb',
            'Resource_List.place': 'exclhost'})

        j.create_script(body=script)
        jid = self.server.submit(j)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

        self.logger.info("Giving a chance to pbs to kill the job...")
        time.sleep(15)

        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
