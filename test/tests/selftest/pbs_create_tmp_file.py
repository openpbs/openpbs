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

from tests.selftest import *
from stat import *
from pwd import getpwuid


class TestPBStempfile(TestSelf):
    """
    Test suite to test create_temp_file functionality in PBS
    """
    def test_default_temp_file(self):
        """
        Test that by default the file created by create_temp_file
        interface is present in tmp directory with 0644 permissions
        """
        f = self.du.create_temp_file()
        name = f.split(os.sep)[-1]

        self.assertTrue(name.startswith('PtlPbs'))
        self.assertTrue(f.startswith('/tmp'))
        mode = str(oct(os.stat(f)[ST_MODE])[-3:])
        self.assertEqual(mode, '644')

    def test_tmp_file_owner(self):
        """
        Test that temp file is created as specified owner
        """
        file_user = getpwuid(os.getuid()).pw_name
        f = self.du.create_temp_file(asuser=file_user)

        user = getpwuid(os.stat(f).st_uid).pw_name
        self.assertEqual(file_user, user)

    def test_tmp_file_directory(self):
        """
        Test temp file is created in specified directory
        """
        home = os.path.expanduser('~')
        f = self.du.create_temp_file(dirname=home)
        dirname = os.sep.join(f.split(os.sep)[:-1])
        self.assertEqual(home, dirname)

    def test_tmp_file_perm(self):
        """
        Test temp file is created with certain permissions
        """
        mode = 0755
        f = self.du.create_temp_file(mode=mode)
        mode_out = oct(os.stat(f)[ST_MODE])[-4:]
        self.assertEqual(oct(mode), mode_out)

    def test_tmp_file_with_perm_in_directory(self):
        """
        Test temp file is created with certain permissions and inside
        a specified directory
        """
        mode = 0755
        home = os.path.expanduser('~')
        f = self.du.create_temp_file(mode=mode, dirname=home)
        mode_out = oct(os.stat(f)[ST_MODE])[-4:]
        dirname = os.sep.join(f.split(os.sep)[:-1])
        self.assertEqual(oct(mode), mode_out)
        self.assertEqual(home, dirname)

    def test_tmp_file_with_perm_in_directory_as_user(self):
        """
        Test temp file is created with certain permissions and inside
        a specified directory as a specific user
        """
        mode = 0755
        dirname = '/tmp'
        f = self.du.create_temp_file(mode=mode, dirname=dirname)
        mode_out = oct(os.stat(f)[ST_MODE])[-4:]
        dirname_out = os.sep.join(f.split(os.sep)[:-1])
        self.assertEqual(oct(mode), mode_out)
        self.assertEqual(dirname, dirname_out)
