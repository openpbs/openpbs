
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

AC_DEFUN([PBS_AC_WITH_PYTHON],
[
  AC_ARG_WITH([python],
    AS_HELP_STRING([--with-python=DIR],
      [Specify the directory where Python is installed.]
    )
  )
  AS_IF([test "x$with_python" != "x"],
    [PYTHON="$with_python/bin/python3"]
  )
  AM_PATH_PYTHON([3.5])
  AS_IF([test "$PYTHON_VERSION" != "3.5" -a "$PYTHON_VERSION" != "3.6" -a "$PYTHON_VERSION" != "3.7"],
    AC_MSG_ERROR([Python must be version 3.5, 3.6 or 3.7]))
  [PYTHON_INCLUDES=`$PYTHON ${srcdir}/buildutils/python-autoconf.py --includes`]
  AC_SUBST(PYTHON_INCLUDES)
  [PYTHON_CFLAGS=`$PYTHON ${srcdir}/buildutils/python-autoconf.py --cflags`]
  AC_SUBST(PYTHON_CFLAGS)
  [PYTHON_LDFLAGS=`$PYTHON ${srcdir}/buildutils/python-autoconf.py --ldflags`]
  AC_SUBST(PYTHON_LDFLAGS)
  [PYTHON_LIBS=`$PYTHON ${srcdir}/buildutils/python-autoconf.py --libs`]
  AC_SUBST(PYTHON_LIBS)
  [PBS_PYTHON_DESTLIB="python/altair"]
  AC_SUBST(PBS_PYTHON_DESTLIB)
  [PYTHON_STD_DESTLIB="python/python${PYTHON_VERSION}"]
  AC_SUBST(PYTHON_STD_DESTLIB)
  [PYTHON_STD_DESTSHAREDLIB="python/python${PYTHON_VERSION}/shared"]
  AC_SUBST(PYTHON_STD_DESTSHAREDLIB)
  [PYTHON_PBS_IFL_OBJ="pbs_ifl_wrap.o"]
  AC_SUBST(PYTHON_PBS_IFL_OBJ)
  AC_DEFINE([PYTHON], [], [Defined when Python is available])
  AS_IF([test "x$with_python" == "x"],
    [AC_DEFINE_UNQUOTED([SYSTEM_PYTHON_PATH], ["$PYTHON"], [Python executable path])]
  )
])

