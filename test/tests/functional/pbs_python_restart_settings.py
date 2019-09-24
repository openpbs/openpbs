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
from ptl.utils.pbs_logutils import PBSLogUtils


class TestPythonRestartSettings(TestFunctional):

    """
    For addressing memory leak in server due to python objects python
    interpreter needs to be restarted. Previously there were macros in
    code to do that. The new design has added attributes in server to
    configure how frequently python interpreter should be restarted
    This test suite is to validate the server attributes. Actual memory
    leak test is still manual
    """
    logutils = PBSLogUtils()

    def test_non_integer(self):
        """
        This is to test that qmgr will throw error when non-integer
        values are provided
        """

        exp_err = "Illegal attribute or resource value"
        # -1 will throw error
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_hooks': '-1'},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_objects': '-1'},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': '-1'},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        # 0 will also give error
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_hooks': 0},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_objects': 0},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': 0},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': "00:00:00"},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': "HH:MM:SS"},
                                runas=ROOT_USER, logerr=True)
        except PbsManagerError as e:
            self.assertTrue(exp_err in e.msg[0],
                            "Error message is not expected")

    def test_non_manager(self):
        """
        Test that hook values can not be set as operator or users.
        """
        exp_err = "Cannot set attribute, read only or insufficient permission"
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_hooks': 30},
                                runas=OPER_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_objects': 2000},
                                runas=OPER_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': 10},
                                runas=OPER_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")
        exp_err = "Unauthorized Request"
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_hooks': 30},
                                runas=TEST_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_max_objects': 2000},
                                runas=TEST_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")
        try:
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'python_restart_min_interval': 10},
                                runas=TEST_USER, logerr=True)
        except PbsManagerError as e:
            self.assertIn(exp_err, e.msg[0],
                          "Error message is not expected")

    def test_log_message(self):
        """
        Test that message logged in server_logs when values get set
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 200},
                            runas=ROOT_USER, logerr=True)
        self.server.log_match("python_restart_max_hooks = 200",
                              max_attempts=5)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 2000},
                            runas=ROOT_USER, logerr=True)
        self.server.log_match("python_restart_max_objects = 2000",
                              max_attempts=5)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': "00:01:00"},
                            runas=ROOT_USER, logerr=True)
        self.server.log_match("python_restart_min_interval = 00:01:00",
                              max_attempts=5)

    def test_long_values(self):
        """
        Test that very long values are accepted
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 2147483647},
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 2147483647},
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': 2147483647},
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': "596523:00:00"},
                            runas=ROOT_USER, logerr=True)

    def test_set_unset(self):
        """
        Test that when unset attribte is not visible in qmgr.
        Also values will not change after server restart.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 20},
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 20},
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': "00:00:20"},
                            runas=ROOT_USER, logerr=True)
        # Restart server
        self.server.restart()
        self.server.expect(SERVER, {'python_restart_max_hooks': 20},
                           op=SET, runas=ROOT_USER)
        self.server.expect(SERVER, {'python_restart_max_objects': 20},
                           op=SET, runas=ROOT_USER)
        self.server.expect(SERVER, {'python_restart_min_interval': 20},
                           op=SET, runas=ROOT_USER)
        self.server.manager(MGR_CMD_UNSET, SERVER,
                            'python_restart_max_hooks',
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_UNSET, SERVER,
                            'python_restart_max_objects',
                            runas=ROOT_USER, logerr=True)
        self.server.manager(MGR_CMD_UNSET, SERVER,
                            'python_restart_min_interval',
                            runas=ROOT_USER, logerr=True)
        # Restart server again
        self.server.restart()
        self.server.expect(SERVER, "python_restart_max_hooks",
                           op=UNSET, runas=ROOT_USER)
        self.server.expect(SERVER, "python_restart_max_objects",
                           op=UNSET, runas=ROOT_USER)
        self.server.expect(SERVER, "python_restart_min_interval",
                           op=UNSET, runas=ROOT_USER)

    def test_max_hooks(self):
        """
        Test that python restarts at set interval
        """
        # create a hook
        hook_body = """
import pbs

e = pbs.event()

s = pbs.server()

localnode = pbs.get_local_nodename()
vn = pbs.server().vnode(localnode)
pbs.event().accept()
"""
        a = {'event': ["queuejob", "movejob", "modifyjob", "runjob"],
             'enabled': "True"}
        self.server.create_import_hook("test", a, hook_body, overwrite=True)
        # Create workq2
        a = {'queue_type': 'e', 'started': 't', 'enabled': 't'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, "workq2")
        # Set max_hooks and min_interval so that further changes
        # will generate a log message.
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 100},
                            runas=ROOT_USER)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': 30},
                            runas=ROOT_USER)
        # Need to run a job so these new settings are remembered
        j = Job()
        jid = self.server.submit(j)
        # Set server log_events
        self.server.manager(MGR_CMD_SET, SERVER, {"log_events": 2047})
        # Set time to start scanning logs
        time.sleep(1)
        stime = int(time.time())
        # Set max_hooks to low to hit max_hooks only
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 1},
                            runas=ROOT_USER)
        # Set min_interval to 3
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': 3},
                            runas=ROOT_USER)
        # Submit multiple jobs
        for x in range(6):
            j = Job()
            j.set_attributes({ATTR_h: None})
            j.set_sleep_time(1)
            jid = self.server.submit(j)
            self.server.expect(JOB, {'job_state': "H"}, id=jid)
            self.server.alterjob(jid, {ATTR_N: "yaya"})
            self.server.movejob(jid, "workq2")
            self.server.rlsjob(jid, None)
            time.sleep(1)
        # Verify the logs and make sure that python interpreter is restarted
        # every 3s
        logs = self.server.log_match(
            "Restarting Python interpreter to reduce mem usage",
            allmatch=True, starttime=stime, max_attempts=8)
        self.assertTrue(len(logs) > 1)
        log1 = logs[0][1]
        log2 = logs[1][1]
        tmp = log1.split(';')
        # Convert the time into epoch time
        time1 = int(self.logutils.convert_date_time(tmp[0]))
        tmp = log2.split(';')
        time2 = int(self.logutils.convert_date_time(tmp[0]))
        # Difference between log message should not be less than 3
        diff = time2 - time1
        self.logger.info("Time difference between log message is " +
                         str(diff) + " seconds")
        # Leave a little wiggle room for slow systems
        self.assertTrue(diff >= 3 and diff <= 5)
        # This message only gets printed if /proc/self/statm is present
        if os.path.isfile("/proc/self/statm"):
            self.server.log_match("Current memory usage:",
                                  starttime=self.server.ctime,
                                  max_attempts=5)
        else:
            self.server.log_match("unknown", max_attempts=5)
        # Verify other log messages
        self.server.log_match("python_restart_max_hooks is now 1",
                              starttime=stime, max_attempts=5)
        self.server.log_match("python_restart_min_interval is now 3",
                              starttime=stime, max_attempts=5)

    def test_max_objects(self):
        """
        Test that python restarts if max objects limit have met
        """
        hook_body = """
import pbs
pbs.event().accept()
"""
        a = {'event': ["queuejob", "modifyjob"], 'enabled': 'True'}
        self.server.create_import_hook("test", a, hook_body, overwrite=True)
        # Set max_objects and min_interval so that further changes
        # will generate a log message.
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 1000},
                            runas=ROOT_USER)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': 30},
                            runas=ROOT_USER)
        # Need to run a job so these new settings are remembered
        j = Job()
        jid = self.server.submit(j)
        # Set server log_events
        self.server.manager(MGR_CMD_SET, SERVER, {"log_events": 2047})
        # Set time to start scanning logs
        time.sleep(1)
        stime = int(time.time())
        # Set max_objects only
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 1},
                            runas=ROOT_USER)
        # Set min_interval to 1
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': '00:00:01'},
                            runas=ROOT_USER)
        # Submit held jobs
        for x in range(3):
            j = Job()
            j.set_attributes({ATTR_h: None})
            j.set_sleep_time(1)
            jid = self.server.submit(j)
            self.server.expect(JOB, {'job_state': "H"}, id=jid)
            self.server.alterjob(jid, {ATTR_N: "yaya"})
        # Verify that python is restarted
        self.server.log_match(
            "Restarting Python interpreter to reduce mem usage",
            starttime=self.server.ctime, max_attempts=5)
        # This message only gets printed if
        # /proc/self/statm presents
        if os.path.isfile("/proc/self/statm"):
            self.server.log_match(
                "Current memory usage:",
                starttime=self.server.ctime, max_attempts=5)
        else:
            self.server.log_match("unknown", max_attempts=5)
        # Verify other log messages
        self.server.log_match(
            "python_restart_max_objects is now 1",
            starttime=stime, max_attempts=5)
        self.server.log_match(
            "python_restart_min_interval is now 1",
            starttime=stime, max_attempts=5)

    def test_no_restart(self):
        """
        Test that if limit not reached then python interpreter
        will not be started
        """
        hook_body = """
import pbs
pbs.event().accept()
"""
        a = {'event': "queuejob", 'enabled': "True"}
        self.server.create_import_hook("test", a, hook_body, overwrite=True)
        # Set max_hooks, max_objects, and min_interval to large values
        # to avoid restarting the Python interpreter.
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_hooks': 10000},
                            runas=ROOT_USER)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_max_objects': 10000},
                            runas=ROOT_USER)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'python_restart_min_interval': 10000},
                            runas=ROOT_USER)
        stime = time.time()
        # Submit a job
        for x in range(10):
            j = Job()
            j.set_sleep_time(1)
            jid = self.server.submit(j)
        # Verify no restart message
        msg = "Restarting Python interpreter to reduce mem usage"
        self.server.log_match(msg, starttime=stime, max_attempts=8,
                              existence=False)
