# coding: utf-8
#!/usr/bin/python3
# -*- python -*-
#
#
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
#
# NOTE:
# Keep this script in sync with python-config.sh.in

import getopt
import os
import sys
import sysconfig

valid_opts = ['prefix', 'exec-prefix', 'includes', 'libs', 'cflags',
              'ldflags', 'extension-suffix', 'help', 'abiflags', 'configdir']

def exit_with_usage(code=1):
    print("Usage: {0} [{1}]".format(
        sys.argv[0], '|'.join('--'+opt for opt in valid_opts)), file=sys.stderr)
    sys.exit(code)

try:
    opts, args = getopt.getopt(sys.argv[1:], '', valid_opts)
except getopt.error:
    exit_with_usage()

if not opts:
    exit_with_usage()

pyver = sysconfig.get_config_var('VERSION')
getvar = sysconfig.get_config_var

opt_flags = [flag for (flag, val) in opts]

if '--help' in opt_flags:
    exit_with_usage(code=0)

for opt in opt_flags:
    if opt == '--prefix':
        print(sysconfig.get_config_var('prefix'))

    elif opt == '--exec-prefix':
        print(sysconfig.get_config_var('exec_prefix'))

    elif opt in ('--includes', '--cflags'):
        flags = ['-I' + sysconfig.get_path('include'),
                 '-I' + sysconfig.get_path('platinclude')]
        if opt == '--cflags':
            flags.extend(getvar('CFLAGS').split())
        print(' '.join(flags))

    elif opt in ('--libs', '--ldflags'):
        libs = ['-lpython' + pyver + sys.abiflags]
        libs += getvar('LIBS').split()
        libs += getvar('SYSLIBS').split()
        # add the prefix/lib/pythonX.Y/config dir, but only if there is no
        # shared library in prefix/lib/.
        if opt == '--ldflags':
            if not getvar('Py_ENABLE_SHARED'):
                libs.insert(0, '-L' + getvar('LIBPL'))
            if not getvar('PYTHONFRAMEWORK'):
                libs.extend(getvar('LINKFORSHARED').split())
        print(' '.join(libs))

    elif opt == '--extension-suffix':
        print(sysconfig.get_config_var('EXT_SUFFIX'))

    elif opt == '--abiflags':
        print(sys.abiflags)

    elif opt == '--configdir':
        print(sysconfig.get_config_var('LIBPL'))
