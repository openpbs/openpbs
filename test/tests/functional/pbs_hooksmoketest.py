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


@tags('hooks')
class TestHookSmokeTest(TestFunctional):

    """
    Hooks Smoke Test
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.server.manager(MGR_CMD_SET, SERVER, {'log_events': 2047})
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'False'})
        self.clean_hooks()

    def get_file_path(self, hook_name):
        """
        This function returns the path of server's hook
        directory, name of the py file, and path of the PY file
        and HK file
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
        return server_hooks_dir, hk_file, hk_file_location

    def check_hk_file(self, existence):
        if existence:
            msg = "As expected file '%s' is present" % self.hk_file
            msg += " in '%s' directory" % self.server_hooks_dir
            _msg = "File '%s' is not present" % self.hk_file
            _msg += " in '%s' directory" % self.server_hooks_dir
        else:
            msg = "As expected file '%s' is not present" % self.hk_file
            msg += " in '%s' directory" % self.server_hooks_dir
            _msg = "File '%s' is present" % self.hk_file
            _msg += " in '%s' directory" % self.server_hooks_dir

        # sleeping for some time as generation of *.HK file takes time
        count = 5
        while True:
            rc = self.du.isfile(hostname=self.server.hostname,
                                path=self.hk_file_location,
                                sudo=True)
            count = count - 1
            if rc or count == 0:
                break
            time.sleep(1)
        self.assertEqual(rc, existence, _msg)
        self.logger.info(msg)

    def clean_hooks(self):
        """
        Function to delete the hooks which got created during test run
        """
        try:
            self.server.manager(MGR_CMD_LIST, HOOK)
        except:
            pass
        if 'my_hook_queuejob' in self.server.hooks:
            self.server.manager(MGR_CMD_DELETE, HOOK, id="my_hook_queuejob")
        if 'my_hook_queuejob2' in self.server.hooks:
            self.server.manager(MGR_CMD_DELETE, HOOK, id="my_hook_queuejob2")
        if 'my_hook' in self.server.hooks:
            self.server.manager(MGR_CMD_DELETE, HOOK, id="my_hook")

    def test_create_and_print_hook(self):
        """
        Test create and print a hook
        """
        hook_name = "my_hook_queuejob"
        attrs = {'event': 'queuejob'}
        self.logger.info('Create hook my_hook_queuejob')
        self.server.create_hook(hook_name, attrs)
        self.logger.info(
            'Verify .HK file hook exists in PBS_HOME/server_priv/hooks')
        (self.server_hooks_dir, self.hk_file,
         self.hk_file_location) = self.get_file_path(hook_name)
        self.check_hk_file(existence=True)

        attrs = {'type': 'site', 'enabled': 'true', 'event': 'queuejob',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        self.logger.info('Verify hook values for my_hook_queuejob')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)

    def test_import_and_export_hook(self):
        """
        Test import and export hook
        """
        hook_name = "my_hook_queuejob2"
        hook_body = """
import pbs

e = pbs.event()
j = e.job

if j.Resource_List["walltime"] is None:
  e.reject("no walltime specified")

j.Resource_List["mem"] = pbs.size("7mb")
e.accept()
"""
        imp_hook_body = hook_body.split('\n')
        exp_hook_body = imp_hook_body[0:len(imp_hook_body) - 1]
        attrs = {'event': 'queuejob'}
        self.server.create_import_hook(hook_name, attrs, hook_body)
        fn = self.du.create_temp_file()
        hook_attrs = 'application/x-config default %s' % fn
        rc = self.server.manager(MGR_CMD_EXPORT, HOOK, hook_attrs, hook_name)
        self.assertEqual(rc, 0)
        cmd = "export h my_hook_queuejob2 application/x-python default"
        export_cmd = [os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                   'qmgr'), '-c', cmd]
        ret = self.du.run_cmd(self.server.hostname, export_cmd, sudo=True)
        self.assertEqual(ret['out'], exp_hook_body,
                         msg="Failed to get expected usage message")

    def test_enable_and_disable_hook(self):
        """
        Test enable and disable a hook
        """
        hook_name = "my_hook"
        rc = self.server.manager(MGR_CMD_CREATE, HOOK, None, hook_name)
        self.assertEqual(rc, 0)
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 0}, id=hook_name)
        attrs = {'type': 'site', 'enabled': 'false', 'event': '""',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        self.logger.info('Verify hook values for my_hook')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)
        self.server.manager(MGR_CMD_SET, HOOK, {'enabled': 1}, id=hook_name)
        self.logger.info('Verify hook values for my_hook')
        attrs = {'type': 'site', 'enabled': 'true', 'event': '""',
                 'alarm': 30, 'order': 1, 'debug': 'false',
                 'user': 'pbsadmin', 'fail_action': 'none'}
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)

    def test_modify_hook(self):
        """
        Test to modify a hook"
        """
        hook_name = "my_hook2"
        attrs = {'event': 'queuejob', 'alarm': 60,
                 'enabled': 'false', 'order': 7}
        self.logger.info('Create hook my_hook2')
        rv = self.server.create_hook(hook_name, attrs)
        self.assertTrue(rv)
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)
        self.logger.info("Modify hook my_hook2 event")
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event+': 'resvsub'}, id=hook_name)
        self.logger.info('Verify hook values for my_hook2')
        attrs2 = {'event': 'queuejob,resvsub',
                  'alarm': 60, 'enabled': 'false', 'order': 7}
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs2, id=hook_name)
        self.assertTrue(rv)
        self.server.manager(MGR_CMD_SET, HOOK, {
                            'event-': 'resvsub'}, id=hook_name)
        self.logger.info('Verify hook values for my_hook2')
        rc = self.server.manager(MGR_CMD_LIST, HOOK,
                                 id=hook_name)
        self.assertEqual(rc, 0)
        rv = self.server.expect(HOOK, attrs, id=hook_name)
        self.assertTrue(rv)

    def test_delete_hook(self):
        """
        Test delete a hook
        """
        hook_name = "my_hook"
        rc = self.server.manager(MGR_CMD_CREATE, HOOK, None, hook_name)
        self.assertEqual(rc, 0)
        self.server.manager(MGR_CMD_DELETE, HOOK, id=hook_name)
        cmd = "l h my_hook"
        export_cmd = [os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin',
                                   'qmgr'), '-c', cmd]
        ret = self.du.run_cmd(self.server.hostname, export_cmd, sudo=True)
        err_msg = []
        err_msg.append("qmgr obj=my_hook svr=default: hook not found")
        err_msg.append("qmgr: hook error returned from server")
        for i in err_msg:
            self.assertIn(i, ret['err'],
                          msg="Failed to get expected error message")
        self.logger.info(
            'Verify .HK file doesnot exists in PBS_HOME/server_priv/hooks')
        (self.server_hooks_dir, self.hk_file,
         self.hk_file_location) = self.get_file_path(hook_name)
        self.check_hk_file(existence=False)

    def tearDown(self):
        self.clean_hooks()
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'scheduling': 'True'})
        PBSTestSuite.tearDown(self)
