
#
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

#

AC_DEFUN([PBS_AC_WITH_PYTHON],
[
  AC_ARG_WITH([python],
    AS_HELP_STRING([--with-python=DIR],
      [Specify the directory where Python is installed.]
    )
  )
  AS_IF([test "x$with_python" != "x"],
    [PYTHON="$with_python/bin/python3"] [PYTHON_CONFIG="$with_python/bin/python3-config"],
    [PYTHON_CONFIG="python3-config"]
  )
  AM_PATH_PYTHON([3.6])
  [python_major_version=`echo $PYTHON_VERSION | sed -e 's/\..*$//'`]
  [python_minor_version=`echo $PYTHON_VERSION | sed -e 's/^[^.]*\.//'`]
  AS_IF([test $python_major_version -eq 3],
  [
    python_config_embed=""
    AS_IF([test $python_minor_version -ge 8], [python_config_embed="--embed"])
    [PYTHON_INCLUDES=`$PYTHON_CONFIG --includes ${python_config_embed}`]
    AC_SUBST(PYTHON_INCLUDES)
    [PYTHON_CFLAGS=`$PYTHON_CONFIG --cflags ${python_config_embed}`]
    AC_SUBST(PYTHON_CFLAGS)
    [PYTHON_LDFLAGS=`$PYTHON_CONFIG --ldflags ${python_config_embed}`]
    AC_SUBST(PYTHON_LDFLAGS)
    [PYTHON_LIBS=`$PYTHON_CONFIG --libs ${python_config_embed}`]
    AC_SUBST(PYTHON_LIBS)
    AC_DEFINE([PYTHON], [], [Defined when Python is available])
    AC_DEFINE_UNQUOTED([PYTHON_BIN_PATH], ["$PYTHON"], [Python executable path])
  ],
  [AC_MSG_ERROR([Python version 3 is required.])])
])
