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


from tests.selftest import *
from ptl.utils.pbs_dshutils import PbsConfigError
import pwd
import getpass
import grp
import os


class TestDshUtils(TestSelf):
    """
    Test pbs distributed utilities util pbs_dshutils.py
    """

    def test_pbs_conf(self):
        """
        Test setting a pbs.conf variable and then unsetting it
        """
        var = 'PBS_COMM_THREADS'
        val = '16'
        self.du.set_pbs_config(confs={var: val})
        conf = self.du.parse_pbs_config()
        msg = 'pbs.conf variable not set'
        self.assertIn(var, conf, msg)
        self.assertEqual(conf[var], val, msg)

        msg = 'pbs.conf variable not unset'
        self.du.unset_pbs_config(confs=[var])
        conf = self.du.parse_pbs_config()
        self.assertNotIn(var, conf, msg)

        exception_found = False
        try:
            self.du.set_pbs_config(confs={'f': 'b'}, fout='/does/not/exist')
        except PbsConfigError:
            exception_found = True

        self.assertTrue(exception_found, 'PbsConfigError not thrown')

    def test_pbs_env(self):
        """
        Test setting a pbs_environment variable and then unsetting it
        """
        self.du.set_pbs_environment(environ={'pbs_foo': 'True'})
        environ = self.du.parse_pbs_environment()
        msg = 'pbs environment variable not set'
        self.assertIn('pbs_foo', environ, msg)
        self.assertEqual(environ['pbs_foo'], 'True', msg)

        msg = 'pbs environment variable not unset'
        self.du.unset_pbs_environment(environ=['pbs_foo'])
        environ = self.du.parse_pbs_environment()
        self.assertNotIn('pbs_foo', environ, msg)

    def check_access(self, path, mode=0o755, user=None, group=None, host=None):
        """
        Helper function to check user, group and mode of given path
        """
        if host is None:
            result = os.stat(path)
            m = result.st_mode
            u = result.st_uid
            g = result.st_gid

        else:
            py = self.du.which(host, 'python3')
            c = '"import os;s = os.stat(\'' + path + '\');'
            c += 'print(s.st_uid,s.st_gid,s.st_mode)"'
            cmd = [py, '-c', c]
            runas = self.du.get_current_user()
            ret = self.du.run_cmd(host, cmd, sudo=True, runas=runas)
            self.assertEqual(ret['rc'], 0)
            res = ret['out'][0]
            u, g, m = [int(v) for v in
                       res.split(' ')]

        self.assertEqual(oct(m & 0o777), oct(mode))
        if user is not None:
            uid = pwd.getpwnam(str(user)).pw_uid
            self.assertEqual(u, uid)
        if group is not None:
            gid = grp.getgrnam(str(group))[2]
            self.assertEqual(g, gid)

    def test_create_dir_as_user(self):
        """
        Test creating a directory as user
        """

        # create a directory with permissions
        tmpdir = self.du.create_temp_dir(mode=0o750)
        self.check_access(tmpdir, mode=0o750)

        # check default configurations
        tmpdir = self.du.create_temp_dir()
        self.check_access(tmpdir, user=getpass.getuser())

        # create a directory as a specific user
        tmpdir = self.du.create_temp_dir(asuser=TEST_USER2)
        self.check_access(tmpdir, user=TEST_USER2, mode=0o755)

        # create a directory as a specific user and permissions
        tmpdir = self.du.create_temp_dir(asuser=TEST_USER2, mode=0o750)
        self.check_access(tmpdir, mode=0o750, user=TEST_USER2)

        # create a directory as a specific user, group and permissions
        tmpdir = self.du.create_temp_dir(asuser=TEST_USER2, mode=0o770,
                                         asgroup=TSTGRP3)
        self.check_access(tmpdir, mode=0o770, user=TEST_USER2, group=TSTGRP3)

    @requirements(num_moms=2)
    def test_create_remote_dir_as_user(self):
        """
        Test creating a directory on a remote host as a user
        """

        if len(self.moms) < 2:
            self.skip_test("Test requires 2 moms: use -p moms=mom1:mom2")
        remote = None
        for each in self.moms:
            if not self.du.is_localhost(each):
                remote = each
                break

        if remote is None:
            self.skip_test("Provide a remote hostname")

        # check default configurations
        tmpdir = self.du.create_temp_dir(remote)
        self.check_access(tmpdir, user=getpass.getuser(), host=remote)

        # create a directory with permissions
        tmpdir = self.du.create_temp_dir(remote, mode=0o750)
        self.check_access(tmpdir, mode=0o750, host=remote)

        # create a directory as a specific user
        tmpdir = self.du.create_temp_dir(remote, asuser=TEST_USER2)
        self.check_access(tmpdir, user=TEST_USER2, mode=0o755, host=remote)

        # create a directory as a specific user and permissions
        tmpdir = self.du.create_temp_dir(remote, asuser=TEST_USER2,
                                         mode=0o750)
        self.check_access(tmpdir, mode=0o750, user=TEST_USER2, host=remote)

        # create a directory as a specific user, group and permissions
        tmpdir = self.du.create_temp_dir(remote, asuser=TEST_USER2, mode=0o770,
                                         asgroup=TSTGRP3)
        self.check_access(tmpdir, mode=0o770, user=TEST_USER2, group=TSTGRP3,
                          host=remote)

    @requirements(num_moms=1)
    def test_script_cleanup(self):
        """
        Make sure run_cmd with the as_script option cleans up the
        temporary file it creates.
        """

        if len(self.moms) < 1:
            self.skip_test("Test requires a mom: use -p mom=mom_host")
        remote = None
        for each in self.moms:
            if not self.du.is_localhost(each):
                remote = each
                break

        if remote is None:
            self.skip_test("Provide a remote mom")

        # First, figure out where temp files are created
        pfx = 'PtlPbs'      # This should be a constant someplace
        tmpname = self.du.create_temp_file(prefix=pfx)
        tmp_dir_path = os.path.dirname(tmpname)
        long_pfx = os.path.join(tmp_dir_path, pfx)
        self.du.rm(path=tmpname)

        # Get current contents of temp file dir
        before = self.du.listdir(path=tmp_dir_path, level=logging.DEBUG)

        # Run an as_script command
        example_cmd = "printenv HOME"
        result = self.du.run_cmd(cmd=example_cmd, as_script=True,
                                 level=logging.DEBUG)
        self.assertEqual(result['rc'], 0)

        # Get contents of temp file dir post script
        after = self.du.listdir(path=tmp_dir_path, level=logging.DEBUG)

        # Compare contents, looking for new PTL files
        new_files = set(after) - set(before)
        our_new_files = [x for x in new_files if x.startswith(long_pfx)]
        self.assertEqual([], our_new_files, "script file not cleaned up")

        # Repeat, running on remote host
        before = self.du.listdir(hostname=remote, path=tmp_dir_path,
                                 level=logging.DEBUG)
        result = self.du.run_cmd(hosts=remote, cmd=example_cmd,
                                 as_script=True, level=logging.DEBUG)
        self.assertEqual(result['rc'], 0)
        after = self.du.listdir(hostname=remote, path=tmp_dir_path,
                                level=logging.DEBUG)
        new_files = set(after) - set(before)
        our_new_files = [x for x in new_files if x.startswith(long_pfx)]
        self.assertEqual([], our_new_files,
                         "remote script file not cleaned up")

        # Repeat, running locally as a different user
        before = self.du.listdir(path=tmp_dir_path, runas=TEST_USER,
                                 level=logging.DEBUG)
        result = self.du.run_cmd(cmd=example_cmd, as_script=True,
                                 runas=TEST_USER, level=logging.DEBUG)
        self.assertEqual(result['rc'], 0)
        after = self.du.listdir(path=tmp_dir_path, runas=TEST_USER,
                                level=logging.DEBUG)
        new_files = set(after) - set(before)
        our_new_files = [x for x in new_files if x.startswith(long_pfx)]
        self.assertEqual([], our_new_files,
                         "alternate user script file not cleaned up")

        # Once more, with both remote host and different user
        before = self.du.listdir(hostname=remote, path=tmp_dir_path,
                                 runas=TEST_USER, level=logging.INFOCLI)
        result = self.du.run_cmd(hosts=remote, cmd=example_cmd,
                                 as_script=True, runas=TEST_USER,
                                 level=logging.DEBUG)
        self.assertEqual(result['rc'], 0)
        after = self.du.listdir(hostname=remote, path=tmp_dir_path,
                                runas=TEST_USER, level=logging.INFOCLI)
        new_files = set(after) - set(before)
        our_new_files = [x for x in new_files if x.startswith(long_pfx)]
        self.assertEqual([], our_new_files,
                         "alt user script file on remote not cleaned up")
