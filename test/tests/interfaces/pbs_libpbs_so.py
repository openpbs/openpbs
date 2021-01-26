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


from tests.interfaces import *

test_code = '''
#include <stdio.h>
#include <string.h>
#include <pbs_ifl.h>

int main(int argc, char **argv)
{
    struct batch_status *status = NULL;
    struct attrl *a;
    int c = pbs_connect(NULL);

    if (c <= 0)
        return 1;
    status = pbs_statserver(c, NULL, NULL);
    if (status == NULL)
        return 1;
    a = status->attribs;
    while (a != NULL) {
        if (a->name != NULL &&
            (!strcmp(a->name, ATTR_SvrHost) ||
                !strcmp(a->name, ATTR_total))) {
            printf("%s = %s\\n", a->name, a->value);
        }
        a = a->next;
    }
    pbs_statfree(status);
    pbs_disconnect(c);
    return 0;
}
'''


class TestLibpbsLinking(TestInterfaces):
    """
    Test suite to shared libpbs library linking
    """

    def test_libpbs(self):
        """
        Test shared libpbs library linking with test code
        """
        if self.du.get_platform().lower() != 'linux':
            self.skipTest("This test is only supported on Linux!")
        _gcc = self.du.which(exe='gcc')
        if _gcc == 'gcc':
            self.skipTest("Couldn't find gcc!")
        _exec = self.server.pbs_conf['PBS_EXEC']
        _id = os.path.join(_exec, 'include')
        _ld = os.path.join(_exec, 'lib')
        if not self.du.isfile(path=os.path.join(_id, 'pbs_ifl.h')):
            _m = "Couldn't find pbs_ifl.h in %s" % _id
            _m += ", Please install PBS devel package"
            self.skipTest(_m)
        self.assertTrue(self.du.isfile(path=os.path.join(_ld, 'libpbs.so')))
        _fn = self.du.create_temp_file(body=test_code, suffix='.c')
        _en = self.du.create_temp_file()
        self.du.rm(path=_en)
        cmd = ['gcc', '-g', '-O2', '-Wall', '-Werror']
        cmd += ['-o', _en]
        cmd += ['-I%s' % _id, _fn, '-L%s' % _ld, '-lpbs', '-lz']
        _res = self.du.run_cmd(cmd=cmd)
        self.assertEqual(_res['rc'], 0, "\n".join(_res['err']))
        self.assertTrue(self.du.isfile(path=_en))
        cmd = ['LD_LIBRARY_PATH=%s %s' % (_ld, _en)]
        _res = self.du.run_cmd(cmd=cmd, as_script=True)
        self.assertEqual(_res['rc'], 0)
        self.assertEqual(len(_res['out']), 2)
        _s = self.server.status(SERVER)[0]
        _exp = ["%s = %s" % (ATTR_SvrHost, _s[ATTR_SvrHost])]
        _exp += ["%s = %s" % (ATTR_total, _s[ATTR_total])]
        _exp = "\n".join(_exp)
        _out = "\n".join(_res['out'])
        self.assertEqual(_out, _exp)
