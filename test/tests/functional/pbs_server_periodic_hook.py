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


class Test_server_periodic_hook(TestFunctional):
    hook_string = """
import pbs
import time
e = pbs.event()
pbs.logmsg(pbs.LOG_DEBUG, "periodic hook started at %%d" %% time.time())
time.sleep(%d)
pbs.logmsg(pbs.LOG_DEBUG, "periodic hook ended at %%d" %% time.time())
%s
"""

    def create_hook(self, accept, sleep_time):
        """
        function to create a hook script.
        It accepts 2 arguments
        - accept	If set to true, then hook will accept else reject
        - sleep_time	Number of seconds we want the hook to sleep
        """
        hook_action = "e.accept()"
        if accept is False:
            hook_action = "e.reject()"
        final_hook = self.hook_string % (int(sleep_time), hook_action)
        return final_hook

    start_msg = "periodic hook started at "
    end_msg = "periodic hook ended at "

    def get_timestamp(self, msg):
        a = msg.rsplit(' ', 1)
        return int(a[1])

    def check_next_occurances(self, count, freq,
                              hook_run_time, check_for_hook_end):
        """
        Helper function to check the occurances of hook by matching their
        logs in server logs.
        It needs 4 arguments:
        - count			to know how many times to repeat
                                checking these logs
        - freq			is the frequency set in pbs server to run this hook
        - hook_run_time		is the amount of time hook takes to run.
        - check_for_hook_end	If it is true then the functions checks for
                                hook end messages.
        """
        occurance = 0
        time_expected = int(time.time()) + freq
        # time after which we want to start matching log
        search_after = int(time.time())
        intr = freq
        while (occurance < count):
            msg_expected = self.start_msg
            msg = self.server.log_match(msg_expected,
                                        interval=(intr + 1),
                                        starttime=search_after)
            time_logged = self.get_timestamp(msg[1])
            self.assertFalse((time_logged - time_expected) > 1)

            if check_for_hook_end is True:
                time_expected += hook_run_time
                # set it to a second before we expect the hook to end
                search_after = time_expected - 1
                msg_expected = self.end_msg
                msg = self.server.log_match(msg_expected, max_attempts=2,
                                            interval=(hook_run_time + 1),
                                            starttime=search_after)
                time_logged = self.get_timestamp(msg[1])
                self.assertFalse((time_logged - time_expected) > 1)

                if hook_run_time <= freq:
                    intr = freq - hook_run_time
                else:
                    intr = freq - (hook_run_time % freq)
            else:
                if hook_run_time <= freq:
                    intr = freq
                else:
                    intr = hook_run_time + (freq - (hook_run_time % freq))

            # we just matched hook start/end message, next start message is
            # surely after time_expected.
            search_after = time_expected
            time_expected = time_expected + intr
            occurance += 1

    def test_sp_hook_run(self):
        """
        Submit a server periodic hook that rejects
        """
        hook_name = "medium_hook"
        freq = 20
        hook_run_time = 10
        scr = self.create_hook(True, hook_run_time)
        attrs = {'event': "periodic"}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        attrs = {'freq': freq}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        attrs = {'enabled': 'True'}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        self.check_next_occurances(2, freq, hook_run_time, True)

    def test_sp_hook_reject(self):
        """
        Submit a server periodic hook that rejects
        """
        hook_name = "reject_hook"
        freq = 20
        hook_run_time = 10
        scr = self.create_hook(False, hook_run_time)
        attrs = {'event': "periodic"}
        msg_expected = ";periodic request rejected by " + "'" + hook_name + "'"
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        attrs = {'freq': freq}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        attrs = {'enabled': 'True'}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        self.check_next_occurances(2, freq, hook_run_time, True)
        self.server.log_match(msg_expected, interval=1)

    def test_sp_hook_long_run(self):
        """
        Submit a hook that runs longer than the frequency set by the hook and
        see if the hook starts at the next subsequent freq interval.
        in this case hook runs for 20 seconds and freq is 6. So if a hook
        starts at time 'x' then it's next occurance should be at 'x +24'.
        """
        hook_name = "long_hook"
        freq = 6
        hook_run_time = 20
        scr = self.create_hook(True, hook_run_time)
        attrs = {'event': "periodic"}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        attrs = {'freq': freq}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        attrs = {'enabled': 'True'}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        self.check_next_occurances(2, freq, hook_run_time, True)

    def test_sp_hook_aborts_after_short_alarm(self):
        """
        Submit a hook that runs longer than the frequency set by the hook and
        see if the hook starts at the next subsequent freq interval.
        in this case hook runs for 20 seconds and freq is 15 and alarm is 12.
        So if a hook starts at time 'x' then it's next occurance should be
        at 'x +15' because alarm is going to kill it at 12th second of it's
        run.
        """
        hook_name = "long_hook"
        freq = 15
        alarm = 12
        hook_run_time = alarm
        scr = self.create_hook(True, 20)
        attrs = {'event': "periodic"}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        attrs = {'freq': freq, 'alarm': alarm}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        attrs = {'enabled': 'True'}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        self.check_next_occurances(2, freq, hook_run_time, False)

    def test_sp_hook_aborts_after_long_alarm(self):
        """
        Submit a hook that runs longer than the frequency set by the hook and
        see if the hook starts at the next subsequent freq interval.
        in this case hook runs for 20 seconds and freq is 12 and alarm is 15.
        So if a hook starts at time 'x' then it's next occurance should be
        at 'x +12' but it is going to run and get killed due to an alarm at
        x +15 and then again start execution at x+24.
        """
        hook_name = "long_hook"
        freq = 12
        alarm = 15
        hook_run_time = alarm
        scr = self.create_hook(True, 20)
        attrs = {'event': "periodic"}
        rv = self.server.create_import_hook(
            hook_name,
            attrs,
            scr,
            overwrite=True)
        self.assertTrue(rv)
        attrs = {'freq': freq, 'alarm': alarm}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        attrs = {'enabled': 'True'}
        rv = self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.assertEqual(rv, 0)
        self.check_next_occurances(2, freq, hook_run_time, False)

    def test_sp_with_queuejob(self):
        """
        This test case checks that periodic and queuejob
        event can be set for the same hook
        """
        events = ["periodic", "queuejob"]
        hook_name = "TestHook"
        hook_attrib = {'event': events, 'freq': 100}
        scr = self.create_hook(True, 10)
        retval = self.server.create_import_hook(hook_name,
                                                hook_attrib,
                                                scr,
                                                overwrite=True)
        self.assertTrue(retval)
        attrs = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)

        job = Job(TEST_USER1, attrs={ATTR_l: 'select=1:ncpus=1',
                                     ATTR_l: 'walltime=1:00:00'})
        jid = self.server.submit(job)
        self.server.log_match(self.start_msg, interval=3)
        self.server.log_match(self.end_msg, interval=3)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)

    def test_alarm_more_than_freq(self):
        """
        Test when alarm is more than freq. Ensure multiple
        instances do not get launched
        """
        hook_name = "medium_hook"
        scr = self.create_hook(accept=True, sleep_time=10)
        attrs = {'event': 'periodic', 'alarm': 15, 'freq': 5}
        self.server.create_import_hook(hook_name, attrs, scr, overwrite=True)
        self.check_next_occurances(2, freq=5, hook_run_time=10,
                                   check_for_hook_end=True)

    def test_check_for_negative_freq(self):
        """
        Check for the correct messages thrown if negative values of freq is set
        """
        hook_name = "med_hook"
        attrs = {'event': "periodic", 'freq': "0"}
        match_str1 = "set_hook_freq: freq value '0'"
        match_str1 += " of a hook must be > 0"
        try:
            self.server.create_hook(hook_name, attrs)
        except PbsManagerError as e:
            self.assertIn(match_str1, e.msg[0])
            self.logger.info('Expected error: ' + match_str1)
        else:
            msg = "Able to set freq to zero"
            self.assertTrue(False, msg)
        attrs = {'enabled': "False", 'event': "periodic", 'freq': '120'}
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        attrs = {'freq': "-1"}
        match_str1 = "set_hook_freq: freq value '-1'"
        match_str1 += " of a hook must be > 0"
        try:
            self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        except PbsManagerError as e:
            self.assertIn(match_str1, e.msg[0])
            self.logger.info('Expected error: ' + match_str1)
        else:
            msg = "Able to set freq to negative value"
            self.assertTrue(False, msg)

    @timeout(600)
    def test_with_other_hooks(self):
        """
        Test periodic hook works fine with other hooks
        """
        hook_name = "periodic_hook"
        freq = 30
        scr = self.create_hook(accept=True, sleep_time=25)
        attrs = {'event': "periodic", 'alarm': "28"}
        self.server.create_import_hook(hook_name, attrs, scr, overwrite=True)
        start_time = int(time.time())
        attrs = {'freq': 30, 'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        expected_msg = "periodic hook started at "
        self.server.log_match(expected_msg, starttime=start_time,
                              interval=(freq + 1))
        self.check_next_occurances(count=1, freq=freq, hook_run_time=25,
                                   check_for_hook_end=False)
        hook_name = "exechost_periodic_hook3"
        freq = 8
        hook_run_time = 5
        scr = self.create_hook(True, sleep_time=5)
        attrs = {'event': "exechost_periodic", 'alarm': "7", 'freq': "8",
                 'enabled': 'True'}
        self.server.create_import_hook(hook_name, attrs, scr)
        start_time = int(time.time())
        expected_msg = "periodic hook started at "
        self.mom.log_match(expected_msg, interval=(freq + 1),
                           starttime=start_time)
        expected_msg = "periodic hook ended at "
        self.mom.log_match(expected_msg, interval=(hook_run_time + 1),
                           starttime=start_time)

    def test_other_pbs_operations_work(self):
        """
        Test that when periodic hook is launched PBS operations do not get
        hampered
        """
        hook_name = "medium_hook"
        freq = 20
        scr = self.create_hook(accept=True, sleep_time=15)
        attrs = {'event': "periodic"}
        self.server.create_import_hook(hook_name, attrs, scr)
        attrs = {'alarm': "18", 'freq': freq}
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        attrs = {'enabled': 'True'}
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.start_msg = ";periodic hook started at "
        self.check_next_occurances(count=1, freq=freq, hook_run_time=25,
                                   check_for_hook_end=False)
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 3}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(3)
        jid1 = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        self.server.expect(JOB, 'queue', id=jid1, op=UNSET, offset=3)
        self.server.log_match(jid1 + ";Exit_status=0")
        j1 = Job(TEST_USER)
        jid2 = self.server.submit(j1)
        self.server.delete(jid2)

    def test_set_as_non_admin(self):
        """
        Check for the correct messages thrown if user other
        than pbsadmin tries to set
        """
        hook_name = "medium_hook"
        host_name = str(self.server.hostname)
        self.server.create_hook(hook_name, attrs={'enabled': "False"})
        attrs = {'event': "periodic", 'freq': '120'}
        match_str1 = str(TEST_USER1) + "@" + host_name + \
            " is unauthorized to access hooks data from server " + host_name
        try:
            self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name,
                                runas=TEST_USER1)
        except PbsManagerError as e:
            self.assertIn(match_str1, e.msg[0])
            self.logger.info('Expected error: ' + match_str1)
        else:
            msg = "Able to create hook as other user"
            self.assertTrue(False, msg)
        self.server.manager(MGR_CMD_SET, HOOK, attrs, hook_name)
        self.server.manager(MGR_CMD_LIST, HOOK, {'freq': '120'}, hook_name)
