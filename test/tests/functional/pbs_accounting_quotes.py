# coding: utf-8

# Copyright (C) 1994-2019 Altair Engineering, Inc.
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


class TestQuotesInAccountingLogs(TestFunctional):

    """
    This test suite tests whether the quotes that are introduced in the
    accounting logs for non alphanumeric values are working as expected or not.
    This test suite must be run as root because tracejob_match does not accept
    runas as yet and the output is different for a root user.
    """

    def setUp(self):
        TestFunctional.setUp(self)

    def test_project(self):
        """
        In this test case we assign a non alphanumeric value to the project
        attribute and check if the accounting logs have surrounding quotes
        for the value or not.
        We also check for tracejob output to not have surrounding quotes
        for the value.
        """

        test = []
        test += ['#PBS -N AccountingQuotesTest\n']
        test += ['sleep 1\n']

        # Submit a job with a non alpha-numeric string as value for the
        # "project" attribute
        j = Job(TEST_USER, attrs={ATTR_project: 'a\\&%bcd\\'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the S record has project value with quotes.
        msg = '.*S;' + str(jid) + '.*project="a\\\\\\\\&%bcd\\\\\\\\".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # Check if the E record has project value with quotes.
        msg = '.*E;' + str(jid) + '.*project="a\\\\\\\\&%bcd\\\\\\\\".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # check that there is tracejob output without the quotes.
        msg = 'project=a\\\\&%bcd\\\\'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)

    def test_account(self):
        """
        In this test case we assign a non alphanumeric value to the account
        attribute and check if the accounting logs have surrounding quotes
        for the value or not.
        We also check for tracejob output to not have surrounding quotes
        for the value.
        """

        test = []
        test += ['#PBS -N AccountingQuotesTest\n']
        test += ['sleep 1\n']

        # Submit a job with a non alpha-numeric string as value for the
        # "account" attribute
        j = Job(TEST_USER, attrs={ATTR_account: 'a\\&%b"cd\\'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the S record has account value with quotes.
        msg = '.*S;' + str(jid) + '.*account="a\\\\\\\\&%b\\\\"cd\\\\\\\\".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # Check if the E record has account value with quotes.
        msg = '.*E;' + str(jid) + '.*account="a\\\\\\\\&%b\\\\"cd\\\\\\\\".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # check that there is tracejob output without the quotes.
        msg = 'account=a\\\\&%b"cd\\\\'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)

    def test_array_indices(self):
        """
        In this test case we submit an array job and ensure that the array
        indices do not have the surrounding quotes.
        """

        test = []
        test += ['#PBS -N AccountingQuotesTest\n']
        test += ['sleep 1\n']

        # Submit array job.
        j = Job(TEST_USER, attrs={ATTR_J: '1-2'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        subjobs = self.server.status(JOB, id=jid, extend='t')
        jids1 = subjobs[1]['id']
        jids2 = subjobs[2]['id']
        self.server.expect(JOB, {ATTR_substate: '42'}, jids1)
        self.server.expect(JOB, {ATTR_substate: '42'}, jids2)

        # Check if the S record has array_indices value without quotes.
        jid1 = jid
        jid = jid.replace("[", "\\[")
        jid = jid.replace("]", "\\]")
        self.logger.info(jid)
        msg = '.*S;' + str(jid) + '.*array_indices=1-2.*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True)

        # Check if the E record has array_indices value without quotes.
        msg = '.*E;' + str(jid) + '.*array_indices=1-2.*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True)

        # check that there is tracejob output without the quotes.
        msg = 'array_indices=1-2'
        self.server.tracejob_match(
            msg, id=jid1, n=10, tail=True, regexp=True)

    def test_jobname(self):
        """
        In this test case we assign a non alphanumeric value to the jobname
        attribute and check if the accounting logs have surrounding quotes
        for the value or not.
        We also check for tracejob output to not have surrounding quotes
        for the value.
        """

        test = []
        test += ['sleep 1\n']

        # Submit a job with a non alpha-numeric string as value for the
        # "account" attribute
        j = Job(TEST_USER, attrs={ATTR_N: 'ab-+cd'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the S record has jobname value with quotes.
        msg = '.*S;' + str(jid) + '.*jobname="ab-\+cd".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # Check if the E record has jobname value with quotes.
        msg = '.*E;' + str(jid) + '.*jobname="ab-\+cd".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # check that there is tracejob output without the quotes.
        msg = 'jobname=ab-\+cd'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)

    def test_queuename(self):
        """
        In this test case we create a queue with a non alphanumeric name
        and submit a job to that queue and check if the accounting logs
        have surrounding quotes for the value or not.
        We also check for tracejob output to not have surrounding quotes
        for the value.
        """

        # Create the queue.
        a = {'queue_type': 'execution', 'started': 't', 'enabled': 't'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='w-q')

        test = []
        test += ['sleep 1\n']

        # Submit a job to this queue.
        j = Job(TEST_USER, attrs={'queue': 'w-q'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the Q record has queue name without quotes.
        msg = '.*Q;' + str(jid) + '.*queue=w-q.*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True)

        # check that there is tracejob output without the quotes.
        msg = 'queue=w-q'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)

    def test_resources(self):
        """
        In this test case we create a resource with a non alphanumeric value
        and submit a job asking for the resource and check if the accounting
        logs have surrounding quotes for the value or not.
        We also check for tracejob output to not have surrounding quotes
        for the value.
        """

        # create resource as root.
        attr = {'type': 'string', 'flag': 'h'}
        self.server.manager(
            MGR_CMD_CREATE, RSC, attr, id='dummy',
            runas=ROOT_USER, logerr=False)
        self.server.manager(
            MGR_CMD_SET, NODE,
            {'resources_available.dummy': 'abc@#$%*()_-={}:'},
            id=self.mom.shortname,
            runas=ROOT_USER)

        # Submit a job that uses this resource.
        test = []
        test += ['sleep 1\n']

        j = Job(TEST_USER, attrs={ATTR_l: 'dummy=abc@#$%*()_-={}:'})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the S record has resource value with quotes.
        msg = '.*S;' + str(jid) + '.*dummy="abc@#\$%\*\(\)_-={}:".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # Check if the E record has resource value with quotes.
        msg = '.*E;' + str(jid) + '.*dummy="abc@#\$%\*\(\)_-={}:".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # check that tracejob output does have the value without quotes.
        msg = 'dummy=abc@#\$%\*\(\)_-={}:'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)

    def test_resv(self):
        """
        In this test case we create a reservation with a non alphanumeric
        value for its name and submit a job to that reservation.
        We check for the reservation name in the B record.
        We also check for tracejob output to not have surrounding quotes
        for the reservation name.
        """

        # Create a reservation with a non alphanumeric name.
        r = Reservation(TEST_USER)
        a = {'reserve_start': int(time.time() + 5),
             'reserve_end': int(time.time() + 15),
             ATTR_name: 'ab-'}
        r.set_attributes(a)
        rid = self.server.submit(r)
        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, rid)

        r_que = rid.split('.')[0]

        test = []
        test += ['sleep 1\n']

        # Submit a job to the reservation queue
        j = Job(TEST_USER, attrs={'queue': r_que})
        j.create_script(body=test)
        jid = self.server.submit(j)
        self.server.expect(JOB, {ATTR_substate: '42'}, jid)

        # Check if the B record has name value with quotes.
        msg = '.*B;' + str(rid) + '.*name="ab-".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True)

        # In the S record of the reservation job, check if the attribute
        # resvname has the value with quotes.
        msg = '.*S;' + str(jid) + '.*resvname="ab-".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # In the E record of the reservation job, check if the attribute
        # resvname has the value with quotes.
        msg = '.*E;' + str(jid) + '.*resvname="ab-".*'
        self.server.accounting_match(
            msg, n=10, tail=True, regexp=True, max_attempts=10)

        # check if tracejob output does have the value without quotes.
        msg = 'resvname=ab-'
        self.server.tracejob_match(
            msg, id=jid, n=10, tail=True, regexp=True)
