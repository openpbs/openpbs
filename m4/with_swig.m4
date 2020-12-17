
#
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

#

AC_DEFUN([PBS_AC_WITH_SWIG],
[
  AC_ARG_WITH([swig],
    AS_HELP_STRING([--with-swig=EXECUTABLE],
      [Specify the full path where the swig executable is installed.]
    )
  )
  AS_IF([test "x$with_swig" != "x"],
    swig_dir=["$with_swig"],
    swig_dir=["/usr"]
  )
  AC_MSG_CHECKING([for swig])
  AS_IF([test -x "$swig_dir/bin/swig"],
    AC_MSG_RESULT([$swig_dir/bin/swig])
    AC_DEFINE([SWIG], [], [Defined when swig is available]),
    AC_MSG_RESULT([not found])
    AC_MSG_WARN([swig command not found.]))
  AS_IF([test "x`ls -d ${swig_dir}/share/swig/* 2>/dev/null`" = "x" ],
          [swig_py_inc="-I`ls -d ${swig_dir}/share/swig* | tail -n 1` -I`ls -d ${swig_dir}/share/swig*/python | tail -n 1`"],
          [swig_py_inc="-I`ls -d ${swig_dir}/share/swig/* | tail -n 1` -I`ls -d ${swig_dir}/share/swig/*/python | tail -n 1`"])
  AC_SUBST([swig_dir])
  AC_SUBST([swig_py_inc])
])
