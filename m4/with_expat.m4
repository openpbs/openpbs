
#
# Copyright (C) 1994-2018 Altair Engineering, Inc.
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

AC_DEFUN([PBS_AC_WITH_EXPAT],
[
  AC_ARG_WITH([expat],
    AS_HELP_STRING([--with-expat=DIR],
      [Specify the directory where expat is installed.]
    )
  )
  AS_IF([test "x$with_expat" != "x"],
    expat_dir=["$with_expat"],
    expat_dir=["/usr"]
  )
  AC_MSG_CHECKING([for expat])
  AS_IF([test -r "$expat_dir/include/expat.h"],
    AS_IF([test "$expat_dir" != "/usr"],
      [expat_inc="-I$expat_dir/include"]),
    AC_MSG_ERROR([expat headers not found.]))
  AS_IF([test "$expat_dir" = "/usr"],
    # Using system installed expat
    AS_IF([test -r "/usr/lib64/libexpat.so" -o -r "/usr/lib/libexpat.so" -o -r "/usr/lib/x86_64-linux-gnu/libexpat.so"],
      [expat_lib="-lexpat"],
      AC_MSG_ERROR([expat shared object library not found.])),
    # Using developer installed expat
    AS_IF([test -r "${expat_dir}/lib64/libexpat.a"],
      [expat_lib="${expat_dir}/lib64/libexpat.a"],
      AS_IF([test -r "${expat_dir}/lib/libexpat.a"],
        [expat_lib="${expat_dir}/lib/libexpat.a"],
        AC_MSG_ERROR([expat library not found.])
      )
    )
  )
  AC_MSG_RESULT([$expat_dir])
  AC_SUBST(expat_inc)
  AC_SUBST(expat_lib)
  AC_DEFINE([EXPAT], [], [Defined when expat is available])
])

