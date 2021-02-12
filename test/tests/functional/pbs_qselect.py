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


class TestQselect(TestFunctional):
    """
    Test suite for qselect command
    """
    def test_qselect_buffer_overflow(self):
        """
        Check that various qselect option arguments does not buffer overflow
        """
        # test -q option
        qselect_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                   'bin', 'qselect')
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-q',
                                   ('a' * 30) + '@' + ('b' * 30)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegally formed destination: aaaaaaaaaaaaaaaa'
                      'aaaaaaaaaaaaaa@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                      ret['err'])
        # test -c
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-c.abcd.w'])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -c value', ret['err'])
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-c.eq.abcdefg'])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -c value', ret['err'])
        # test -a
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-a.ne.' + ('1' * 100)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -a value', ret['err'])
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-a.abcd.5001011212'])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -a value', ret['err'])
        # test accounting string buf and optarg buf using -A
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-A', ('a' * 300)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertEqual(ret['err'], [])
        # test -l
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-l',
                                   ('a' * 300) + '.abcd.' + ('b' * 300)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -l value', ret['err'])
        # test -N
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-N', ('a' * 300)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -N value', ret['err'])
        # test -u
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-u',
                                   ('a' * 300) + '@' + ('b' * 300)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -u value', ret['err'])
        # test -S
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-s', 'ABCD'])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -s value', ret['err'])
        # test -t
        ret = self.du.run_cmd(cmd=[qselect_cmd, '-t',
                                   ('a' * 90) + '.eq.' + ('1' * 90)])
        self.assertNotEqual(ret, None)
        self.assertIn('err', ret)
        self.assertIn('qselect: illegal -t value', ret['err'])
