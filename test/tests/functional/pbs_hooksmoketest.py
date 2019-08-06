# coding: utf-8

# Copyright (C) 2003-2019 Altair Engineering, Inc. All rights reserved.
# Copyright notice does not imply publication.
#
# ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
# Information. Not for use or disclosure outside of Licensee's organization.
# The software and information contained herein may only be used internally and
# is provided on a non-exclusive, non-transferable basis. License may not
# sublicense, sell, lend, assign, rent, distribute, publicly display or
# publicly perform the software or other information provided herein,
# nor is Licensee permitted to decompile, reverse engineer, or
# disassemble the software. Usage of the software and other information
# provided by Altair(or its resellers) is only as explicitly stated in the
# applicable end user license agreement between Altair and Licensee.
# In the absence of such agreement, the Altair standard end user
# license agreement terms shall govern.

from tests.functional import *


@tags('hooks', 'smoke')
class TestHookSmokeTest(TestFunctional):
    """
    Hooks Smoke Test
    """
    def setUp(self):
        TestFunctional.setUp(self)
        a = {'log_events': 2047, 'scheduling': 'False'}
        self.server.manager(MGR_CMD_SET, SERVER, a)

    hook_name = "test_hook"

    def check_hk_file(self, hook_name, existence=False):
        """
        This function to find the path of server's hook
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
        return server_hooks_dir, hk_file

    def test_create_and_print_hook(self):
        """
        Test create and print a hook
        """
        attrs = {'event': 'queuejob'}
        self.logger.info('Create hook test_hook_queuejob')
        self.server.create_hook(self.hook_name, attrs)
        (self.server_hooks_dir,
         self.hk_file) = self.check_hk_file(self.hook_name, existence=True)
        self.logger.info('Verified ' + self.hk_file + ' file hook exists in' +
                         self.server_hooks_dir + ' as expected')

        attrs = {'type': 'site', 'enabled': 'true', 'event': 'queuejob',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        self.logger.info('Verify hook values for test_hook_queuejob')
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
        fn = self.du.create_temp_file()
        hook_attrs = 'application/x-config default %s' % fn
        rc = self.server.manager(MGR_CMD_EXPORT, HOOK, hook_attrs,
                                 self.hook_name)
        self.assertEqual(rc, 0)
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
        attrs = {'type': 'site', 'enabled': 'true', 'event': '""',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
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
        self.logger.info('Create hook test_hook2')
        rv = self.server.create_hook(self.hook_name, attrs)
        self.assertTrue(rv)
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=self.hook_name)
        self.assertTrue(rv)
        self.logger.info("Modify hook test_hook2 event")
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event+': 'resvsub'}, id=self.hook_name)
        self.logger.info('Verify hook values for test_hook2')
        attrs2 = {'event': 'queuejob,resvsub',
                  'alarm': 60, 'enabled': 'false', 'order': 7}
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=self.hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs2, id=self.hook_name)
        self.assertTrue(rv)
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event-': 'resvsub'}, id=self.hook_name)
        self.logger.info('Verify hook values for test_hook2')
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
        (self.server_hooks_dir,
         self.hk_file) = self.check_hk_file(self.hook_name)
        self.logger.info('Verified ' + self.hk_file + ' file not exists in' +
                         self.server_hooks_dir + ' as expected')

    def tearDown(self):
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})
        PBSTestSuite.tearDown(self)
