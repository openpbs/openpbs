# coding: utf-8

# Copyright (C) 2021 Altair Engineering, Inc.
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


class TestGrunt(TestFunctional):

    """
    This test suite is for testing the grunt routines
    """
    our_queue = 'workq2'
    kvp_size = 50
    # Define a lot of resource names
    resources = ["resource%d" % i for i in range(2*kvp_size)]

    def setUp(self):
        TestFunctional.setUp(self)

        rlist = ','.join(self.resources)
        a = {ATTR_RESC_TYPE: 'long', ATTR_RESC_FLAG: 'hn'}
        self.server.manager(MGR_CMD_CREATE, RSC, a, id=rlist)

        # Create a queue to test against
        a = {'queue_type': 'execution', 'enabled': 'True', 'started': 'False'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id=self.our_queue)

    def try_a_job(self, base, job_res, que_res, svr_res):
        """ Submit a job and check its schedselect result

        :param base: the prefix of the job select statement before the
            resources under test
        :type base: list of str
        :param job_res: resources requested by job
        :type job_res: dict with keys of resource names, values of values
        :param que_res: resource defaults for queue
        :type que_res: same as job_res
        :param svr_res: resource defaults for server
        :type svr_res: same as job_res
        :returns: job id
        """
        attrs = {ATTR_queue: self.our_queue}

        job_part = ['%s=%s' % r for r in job_res.items()]
        sel_arg = ':'.join(base + job_part)
        attrs[ATTR_l] = 'select=' + sel_arg
        j = Job(TEST_USER, attrs)
        jid = self.server.submit(j)

        # Merge server, queue, and job requested resources into
        # expected resource list.  Last one wins.
        expected = svr_res.copy()
        expected.update(que_res)
        expected.update(job_res)
        e_set = set(["%s=%s" % r for r in expected.items()])

        # See which resources ended up in job's schedselect
        a = [ATTR_SchedSelect]
        job_stat = self.server.status(JOB, a, id=jid)
        ssel = job_stat[0][ATTR_SchedSelect]
        # Generate actual resource list
        a_set = set(ssel.split(':'))
        # Ignore any pieces from base
        a_set -= set((':'.join(base)).split(':'))
        # Determine where expected and actual differ
        missing = e_set.difference(a_set)
        extra = a_set.difference(e_set)
        if missing:
            msg = "Actual schedselect missing %s for select=%s" % \
                   (', '.join(sorted(missing)), sel_arg)
            self.fail(msg)
        if extra:
            msg = "Actual schedselect includes extra %s for select=%s" % \
                   (', '.join(sorted(extra)), sel_arg)
            self.fail(msg)
        return jid

    @tags('server')
    def test_nkve_overflow(self):
        """
        Test whether do_schedselect() in vnparse.c can overflow the
        grunt nkve array if a queue has a large number of default resources
        (> KVP_SIZE (50)).
        Note: This test can corrupt memory in an unpatched server.
        """

        # Remove any current server defaults
        rlist = ['default_chunk.%s' % r for r in self.resources]
        a = ','.join(rlist)
        self.server.manager(MGR_CMD_UNSET, SERVER, a)

        # Set our queue to have default values for all the resources.
        a = {'default_chunk.%s' % r: 1 for r in self.resources}
        self.server.manager(MGR_CMD_SET, QUEUE, a, id=self.our_queue)

        base_sel = ['1:ncpus=1']
        job_res = {}
        que_res = {r: 1 for r in self.resources}
        svr_res = {}
        # Submit job to that queue and check schedselect value
        self.try_a_job(base_sel, job_res, que_res, svr_res)

    @tags('server')
    def test_general_dflt_chunks(self):
        """
        Test that chunk specifications are handled correctly. That is,
        job specs should override queue defaults which override server
        defaults.
        """
        # Remove any current defaults
        rlist = ['default_chunk.%s' % r for r in self.resources]
        a = ','.join(rlist)
        self.server.manager(MGR_CMD_UNSET, QUEUE, a, id=self.our_queue)
        self.server.manager(MGR_CMD_UNSET, SERVER, a)

        # Job with no resources

        base_sel = ['1:ncpus=1']
        job_res = {}
        que_res = {}
        svr_res = {}
        self.try_a_job(base_sel, job_res, que_res, svr_res)

        # Job specifying resources

        job_res = {'resource10': 1, 'resource11': 2}
        self.try_a_job(base_sel, job_res, que_res, svr_res)

        # Add a server chunk default

        self.server.manager(MGR_CMD_SET, SERVER,
                            {'default_chunk.resource12': 3})
        svr_res = {'resource12': 3}
        self.try_a_job(base_sel, job_res, que_res, svr_res)

        # Add a queue chunk default

        self.server.manager(MGR_CMD_SET, QUEUE,
                            {'default_chunk.resource13': 4},
                            id=self.our_queue)
        que_res = {'resource13': 4}

        self.try_a_job(base_sel, job_res, que_res, svr_res)

        # Check that job can override a default

        job_res = {'resource12': 10}
        self.try_a_job(base_sel, job_res, que_res, svr_res)
