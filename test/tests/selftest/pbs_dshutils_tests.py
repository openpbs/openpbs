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


from tests.selftest import *
from ptl.utils.pbs_dshutils import PbsConfigError
import pwd
import getpass
import grp


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

    def check_access(self, path, mode=0o700, user=None, group=None):
        """
        Helper function to check user, group and mode of given path
        """
        result = os.stat(path)
        self.assertEqual(oct(result.st_mode & 0o777), oct(mode))
        if user is not None:
            uid = pwd.getpwnam(str(user)).pw_uid
            self.assertEqual(result.st_uid, uid)
        if group is not None:
            gid = grp.getgrnam(str(group))[2]
            self.assertEqual(result.st_gid, gid)

    def test_create_dir_as_user(self):
        """
        Test creating a directory as user
        """

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
                                         asgroup=TSTGRP2)
        self.check_access(tmpdir, mode=0o770, user=TEST_USER2, group=TSTGRP2)
