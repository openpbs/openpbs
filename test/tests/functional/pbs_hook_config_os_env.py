# coding: utf-8

# Copyright (C) 2003-2020 Altair Engineering, Inc. All rights reserved.
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
class TestHookConfigOSEnv(TestFunctional):
    """
    Test suite to check if hook can access
    os.environ when a config file is configured
    for a hook
    """

    def test_hook_config_os_env(self):
        """
        Create a hook, import a config file for the hook
        and test the os.environ call in the hook
        """
        hook_name = "test_hook"
        hook_body = """
import pbs
import os
pbs.logmsg(pbs.LOG_DEBUG, "Printing os.environ %s" % os.environ)
"""
        cfg = """
{'hook_config':'testhook'}
"""
        a = {'event': 'queuejob', 'enabled': 'True'}
        self.server.create_import_hook(hook_name, a, hook_body)
        fn = self.du.create_temp_file(body=cfg)
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': fn}
        self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)
        a = {'Resource_List.select': '1:ncpus=1'}
        j = Job(TEST_USER, a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.log_match("Printing os.environ", self.server.shortname)
