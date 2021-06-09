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


@tags('hooks', 'smoke')
class TestHookSmokeTest(TestFunctional):
    """
    Hooks Smoke Test
    """
    hook_name = "test_hook"

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'log_events': 2047, 'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

        self.script = []
        self.script += ['echo Hello World\n']
        self.script += ['%s 30\n' % (self.mom.sleep_cmd)]
        if self.du.get_platform() == "cray" or \
           self.du.get_platform() == "craysim":
            self.script += ['aprun -b -B /bin/sleep 10']

    def check_hk_file(self, hook_name, existence=False):
        """
        Function to check existence of server's hook
        directory, name of the .HK file and path of HK file
        """
        conf = self.du.parse_pbs_config()
        pbs_home = conf['PBS_HOME']
        server_hooks_dir = os.path.join(pbs_home, "server_priv", "hooks")
        rc = self.du.isdir(hostname=self.server.hostname,
                           path=server_hooks_dir, sudo=True)
        msg = "Dir '%s' not present" % server_hooks_dir
        self.assertEqual(rc, True, msg)
        self.logger.info("As expected dir '%s' present" % server_hooks_dir)
        hk_file = hook_name + ".HK"
        hk_file_location = os.path.join(server_hooks_dir, hk_file)
        self.logger.info("Check existence of .HK file")
        count = 2
        if existence:
            count = 10
            msg = "As expected file '%s' is present" % hk_file
            msg += " in '%s' directory" % server_hooks_dir
            _msg = "File '%s' is not present" % hk_file
            _msg += " in '%s' directory" % server_hooks_dir
        else:
            msg = "As expected file '%s' is not present" % hk_file
            msg += " in '%s' directory" % server_hooks_dir
            _msg = "File '%s' is present" % hk_file
            _msg += " in '%s' directory" % server_hooks_dir

        # sleeping for some time as generation of *.HK file takes time
        while True:
            rc = self.du.isfile(hostname=self.server.hostname,
                                path=hk_file_location,
                                sudo=True)
            count = count - 1
            if rc or count == 0:
                break
            time.sleep(1)
        self.assertEqual(rc, existence, _msg)
        self.logger.info(msg)

    def test_create_and_print_hook(self):
        """
        Test create and print a hook
        """
        attrs = {'event': 'queuejob'}
        self.logger.info('Create a queuejob hook')
        self.server.create_hook(self.hook_name, attrs)
        self.check_hk_file(self.hook_name, existence=True)

        attrs = {'type': 'site', 'enabled': 'true', 'event': 'queuejob',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        self.logger.info('Verify hook values for test_hook')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)

    def test_import_and_export_hook(self):
        """
        Test import and export hook
        """
        hook_body = """import pbs
e = pbs.event()
j = e.job
if j.Resource_List["walltime"] is None:
  e.reject("no walltime specified")
j.Resource_List["mem"] = pbs.size("7mb")
e.accept()"""
        imp_hook_body = hook_body.split('\n')
        exp_hook_body = imp_hook_body
        attrs = {'event': 'queuejob'}
        self.server.create_import_hook(self.hook_name, attrs, hook_body)
        fn = self.du.create_temp_file(asuser=ROOT_USER)
        hook_attrs = 'application/x-config default %s' % fn
        rc = self.server.manager(MGR_CMD_EXPORT, HOOK, hook_attrs,
                                 self.hook_name)
        self.assertEqual(rc, 0)
        # For Cray PTL does not run on the server host
        if self.du.is_localhost(self.server.hostname):
            cmd = "export h test_hook application/x-python default"
        else:
            cmd = "'export h test_hook application/x-python default'"
        export_cmd = [os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                   'qmgr'), '-c', cmd]
        ret = self.du.run_cmd(self.server.hostname, export_cmd, sudo=True)
        self.assertEqual(ret['out'], exp_hook_body,
                         msg="Failed to get expected usage message")

    def test_enable_and_disable_hook(self):
        """
        Test enable and disable a hook
        """
        rc = self.server.manager(MGR_CMD_CREATE, HOOK, None, self.hook_name)
        self.assertEqual(rc, 0)
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'enabled': 0}, id=self.hook_name)
        attrs = {'type': 'site', 'enabled': 'false', 'event': '""',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        self.logger.info('Verify hook values for test_hook')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'enabled': 1}, id=self.hook_name)
        self.logger.info('Verify hook values for test_hook')
        attrs['enabled'] = 'true'
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)

    def test_modify_hook(self):
        """
        Test to modify a hook"
        """
        attrs = {'event': 'queuejob', 'alarm': 60,
                 'enabled': 'false', 'order': 7}
        self.logger.info('Create hook test_hook')
        rv = self.server.create_hook(self.hook_name, attrs)
        self.assertTrue(rv)
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)
        self.logger.info("Modify hook test_hook event")
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event+': 'resvsub'}, id=self.hook_name)
        self.logger.info('Verify hook values for test_hook')
        attrs2 = {'event': 'queuejob,resvsub',
                  'alarm': 60, 'enabled': 'false', 'order': 7}
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs2, id=self.hook_name)
        self.assertTrue(rv)
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event-': 'resvsub'}, id=self.hook_name)
        self.logger.info('Verify hook values for test_hook')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)

    def test_delete_hook(self):
        """
        Test delete a hook
        """
        rc = self.server.manager(MGR_CMD_CREATE, HOOK, None, self.hook_name)
        self.assertEqual(rc, 0)
        self.server.manager(MGR_CMD_DELETE, HOOK, id=self.hook_name)
        # For Cray PTL does not run on the server host
        if self.du.is_localhost(self.server.hostname):
            cmd = "l h test_hook"
        else:
            cmd = "'l h test_hook'"
        export_cmd = [os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                   'qmgr'), '-c', cmd]
        ret = self.du.run_cmd(self.server.hostname, export_cmd, sudo=True)
        err_msg = []
        err_msg.append("qmgr obj=test_hook svr=default: hook not found")
        err_msg.append("qmgr: hook error returned from server")
        for i in err_msg:
            self.assertIn(i, ret['err'],
                          msg="Failed to get expected error message")
        self.check_hk_file(self.hook_name)

    def test_queuejob_hook(self):
        """
        Test queuejob hook
        """
        # Create a hook with event queuejob
        hook_body = """import pbs
import time

e = pbs.event()
j = e.job
if not j.Resource_List["walltime"]:

        e.reject("No walltime specified. Master does not approve! ;o)")
        # select resource
        sel = pbs.select("1:ncpus=2")
        s = repr(sel)
else:
        e.accept()"""

        attrs = {'event': 'queuejob', 'enabled': 'True'}
        rv = self.server.create_import_hook(self.hook_name, attrs, hook_body)
        self.assertTrue(rv)
        # As a user submit a job requesting walltime
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {'Resource_List.walltime': 30}
        j1 = Job(TEST_USER, a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        # As a user submit a job without requesting walltime
        # Job is denied with the message
        _msg = "qsub: No walltime specified. Master does not approve! ;o)"
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER1)
        j2 = Job(TEST_USER1)
        j2.create_script(self.script)
        try:
            jid2 = self.server.submit(j2, submit_dir=submit_dir)
        except PbsSubmitError as e:
            self.assertEqual(
                e.msg[0], _msg, msg="Did not get expected qsub err message")
            self.logger.info("Got expected qsub err message as %s", e.msg[0])
        # To handle delay in  ALPS reservation cancelation on cray simulator
        # Deleting job explicitly
        self.server.delete([jid1])

    def test_modifyjob_hook(self):
        """
        Test modifyjob hook
        """
        # Create a hook with event modifyjob
        hook_body = """import pbs

try:
 e = pbs.event()
 r = e.resv

except pbs.EventIncompatibleError:
 e.reject( "Event is incompatible")"""

        a = {'eligible_time_enable': 'True', 'scheduling': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        attrs = {'event': 'modifyjob', 'enabled': 'True'}
        rv = self.server.create_import_hook(self.hook_name, attrs, hook_body)
        self.assertTrue(rv)
        # As user submit a job j1
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER2)
        j1 = Job(TEST_USER2)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        # qalter the job, qalter will fail with error
        _msg = "qalter: Event is incompatible " + jid1
        try:
            self.server.alterjob(jid1, {ATTR_p: '5'})
        except PbsAlterError as e:
            self.assertEqual(
                e.msg[0], _msg, msg="Did not get expected qalter err message")
            self.logger.info("Got expected qalter err message as %s", e.msg[0])
        # To handle delay in  ALPS reservation cancelation on cray simulator
        # Deleting job explicitly
        self.server.delete([jid1])

    def test_resvsub_hook(self):
        """
        Test resvsub hook
        """
        # Create a hook with event resvsub
        hook_body = """import pbs
e = pbs.event()
r = e.resv

r.Resource_List["place"] = pbs.place("pack:freed")"""

        attrs = {'event': 'resvsub', 'enabled': 'True'}
        rv = self.server.create_import_hook(self.hook_name, attrs, hook_body)
        self.assertTrue(rv)
        # Submit a reservation
        now = int(time.time())
        a = {'reserve_start': now + 10,
             'reserve_end': now + 120}
        r = Reservation(TEST_USER3, attrs=a)
        # The reservation gets an error as
        _msg = "pbs_rsub: request rejected as filter hook " + "'" + \
            self.hook_name + "'" + \
            " encountered an exception. Please inform Admin"
        try:
            rid = self.server.submit(r)
        except PbsSubmitError as e:
            self.assertEqual(
                e.msg[0], _msg,
                msg="Did not get expected pbs_rsub err message")
            self.logger.info(
                "Got expected pbs_rsub err message as %s", e.msg[0])

    def test_movejob_hook(self):
        """
        Test movejob hook
        """
        # Create testq
        qname = 'testq'
        err_msg = []
        err_msg.append("qmgr obj=testq svr=default: Unknown queue")
        err_msg.append("qmgr: Error (15018) returned from server")
        try:
            self.server.manager(MGR_CMD_DELETE, QUEUE, None, qname)
        except PbsManagerError as e:
            for i in err_msg:
                self.assertIn(i, e.msg,
                              msg="Failed to get expected error message")
            self.logger.info("Got expected qmgr err message as %s", e.msg)

        a = {'queue_type': 'Execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, qname)
        # Create a hook with event movejob
        hook_body = """import pbs
e = pbs.event()
j = e.job

if j.queue.name == "testq" and not j.Resource_List["mem"]:
 e.reject("testq requires job to have mem")"""
        attrs = {'event': 'movejob', 'enabled': 'True'}
        rv = self.server.create_import_hook(self.hook_name, attrs, hook_body)
        self.assertTrue(rv)
        # submit a job j1 to default queue
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER4)
        a = {ATTR_h: None, 'Resource_List.mem': '30mb'}
        j1 = Job(TEST_USER4, a)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid1)
        # qmove the job to queue testq
        self.server.movejob(jid1, "testq")
        self.server.expect(
            JOB, {'job_state': 'H', ATTR_queue: 'testq'},
            attrop=PTL_AND, id=jid1)
        # Submit a job j2
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER5)
        a = {ATTR_h: None}
        j2 = Job(TEST_USER5, a)
        j2.create_script(self.script)
        jid2 = self.server.submit(j2, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'H'}, id=jid2)
        # qmove the job j2 to queue testq
        # Qmove will fail with an error
        _msg = "qmove: testq requires job to have mem " + jid2
        try:
            self.server.movejob(jid2, "testq")
        except PbsMoveError as e:
            self.assertEqual(
                e.msg[0], _msg, msg="Did not get expected qmove err message")
            self.logger.info("Got expected qmove err message as %s", e.msg[0])
        # Delete the jobs and delete queue testq
        self.server.delete([jid1, jid2])
        self.server.manager(MGR_CMD_DELETE, QUEUE, None, qname)

    def test_runjob_hook(self):
        """
        Test runjob hook using qrun
        """
        # Create a hook with event runjob
        hook_body = """import pbs

def print_attribs(pbs_obj):

 pbs.logmsg(pbs.LOG_DEBUG, "Printing a PBS object of type %s" % (type(pbs_obj)
))
 for a in pbs_obj.attributes:
  v = getattr(pbs_obj, a)
  if v and str(v) != "":
   pbs.logmsg(pbs.LOG_DEBUG, "%s = %s" % (a,v))

e = pbs.event()

print_attribs(e)

j = e.job
print_attribs(j)"""
        now = time.time()
        attrs = {'event': 'runjob', 'enabled': 'True'}
        rv = self.server.create_import_hook(self.hook_name, attrs, hook_body)
        self.assertTrue(rv)
        # Set scheduling false
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})
        # submit job j1
        submit_dir = self.du.create_temp_dir(asuser=TEST_USER7)
        # submit job j1
        j1 = Job(TEST_USER7)
        j1.create_script(self.script)
        jid1 = self.server.submit(j1, submit_dir=submit_dir)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid1)
        # qrun job j1
        self.server.runjob(jid1)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid1)
        # Get exec_vnode for job j1
        ret = self.server.status(JOB, {'exec_vnode'}, id=jid1)
        ev = ret[0]['exec_vnode']
        # Verify server logs
        self.logger.info("Verifying logs in server")
        msg_1 = "Server@.*;Hook;%s;started" % \
                (re.escape(self.hook_name))
        msg_2 = "Hook;Server@.*;requestor = Scheduler"
        msg_3 = "Hook;Server@.*;hook_name = %s" % \
                (re.escape(self.hook_name))
        msg_4 = "Hook;Server@.*;exec_vnode = %s" % \
                (re.escape(ev))
        # Character escaping '()' as the log_match is regexp
        msg_5 = "Server@.*;Hook;%s;finished" % \
                (re.escape(self.hook_name))
        msg = [msg_1, msg_2, msg_3, msg_4, msg_5]
        for i in msg:
            self.server.log_match(i, starttime=now, regexp=True)
            self.logger.info("Got expected logs in server as %s", i)

    def tearDown(self):
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})
        PBSTestSuite.tearDown(self)
