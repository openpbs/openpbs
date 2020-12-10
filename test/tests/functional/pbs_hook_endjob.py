# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

import datetime
import os
import socket
import textwrap
import time

from tests.functional import *
from tests.functional import JOB, MGR_CMD_SET, SERVER, TEST_USER, ATTR_h, Job


def get_hook_body(hook_msg):
    hook_body = """
    import pbs
    import sys, os
    import time

    pbs.logmsg(pbs.LOG_DEBUG, "pbs.__file__:" + pbs.__file__)
    
    try:
        e = pbs.event()

        # print additional info
        pbs.logmsg(pbs.LOG_DEBUG, '%s')
        pbs.logjobmsg(e.job.id, 'executed endjob hook')
        time.sleep(10)
        pbs.logjobmsg(e.job.id, 'endjob hook ended')
    except Exception as err:
        ty, _, tb = sys.exc_info()
        pbs.logmsg(pbs.LOG_DEBUG, str(ty) + str(tb.tb_frame.f_code.co_filename)
                   + str(tb.tb_lineno))
        e.reject()
    else:
        e.accept()
    """ % hook_msg
    hook_body = textwrap.dedent(hook_body)
    return hook_body

@tags('hooks', 'smoke')
class TestHookJob(TestFunctional):

    def test_hook_endjob_00(self):
        """
        By creating an import hook, it executes a job hook.
        """
        self.logger.info("**************** HOOK START ****************")
        hook_name = "hook_endjob_00"
        hook_msg = 'running %s' % hook_name
        hook_body = get_hook_body(hook_msg)
        attrs = {'event': 'endjob', 'enabled': 'True'}
        start_time = time.time()

        ret = self.server.create_hook(hook_name, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name)
        ret = self.server.import_hook(hook_name, hook_body)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name)

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        j = Job(TEST_USER)
        j.set_sleep_time(4)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.expect(JOB, {'job_state': 'F'}, extend='x',
                                offset=4, id=jid)
        #self.server.delete(id=jid, extend='force', wait=True)
        #self.server.log_match("dequeuing from workq, state E",
        #                      starttime=start_time)
        ret = self.server.delete_hook(hook_name)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name)
        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")

    # TODO: add test for job array 
    def test_hook_endjob_01(self):
        """
        By creating an import hook, it executes a job hook.
        """
        self.logger.info("**************** HOOK START ****************")
        hook_name = "hook_endjob_01"
        hook_msg = 'running %s' % hook_name
        hook_body = get_hook_body(hook_msg)
        attrs = {'event': 'endjob', 'enabled': 'True'}
        start_time = time.time()

        ret = self.server.create_hook(hook_name, attrs)
        self.assertEqual(ret, True, "Could not create hook %s" % hook_name)
        ret = self.server.import_hook(hook_name, hook_body)
        self.assertEqual(ret, True, "Could not import hook %s" % hook_name)

        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        a = {'resources_available.ncpus': 1}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        num_array_jobs = 10
        attr_j_str = '1-' + str(num_array_jobs)
        j = Job(TEST_USER, attrs={
            ATTR_J: attr_j_str, 'Resource_List.select': 'ncpus=1'})

        j.set_sleep_time(20)

        jid = self.server.submit(j)

        subjid = []
        subjid.append(jid)
        #subjid.append(jid)
        for i in range (1,(num_array_jobs+1)):
            subjid.append( j.create_subjob_id(jid, i) )

        # 1. check job array has begun            
        self.server.expect(JOB, {'job_state': 'B'}, jid)

        for i in range (1,(num_array_jobs+1)):
            self.server.expect(JOB, {'job_state': 'R'}, 
                               id=subjid[i], offset=20)            
            
        self.server.expect(JOB, {'job_state': 'F'}, extend='x',
                                offset=4, id=jid, interval=5)

        #self.server.delete(id=jid, extend='force', wait=True)
        self.server.log_match(
            "chk_array_doneness, rq_endjob process_hooks call succeeded",
            starttime=start_time)
        ret = self.server.delete_hook(hook_name)
        self.assertEqual(ret, True, "Could not delete hook %s" % hook_name)
        self.server.log_match(hook_msg, starttime=start_time)
        self.logger.info("**************** HOOK END ****************")
    # TODO: add test for a job run under a reservation
    