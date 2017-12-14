
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

AC_DEFUN([PBS_AC_WITH_EDITLINE],
[
  AC_ARG_WITH([editline],
    AS_HELP_STRING([--with-editline=DIR],
      [Specify the directory where editline is installed.]
    )
  )
  AS_IF([test "x$with_editline" != "x"],
    editline_dir=["$with_editline"],
    editline_dir=["/usr"]
  )
  AC_MSG_CHECKING([for editline])
  AS_IF([test -r "$editline_dir/include/histedit.h"],
    AS_IF([test "$editline_dir" != "/usr"],
      [editline_inc="-I$editline_dir/include"]),
    AC_MSG_ERROR([editline headers not found.]))
  AS_IF([test "$editline_dir" = "/usr"],
    # Using system installed editline
    AS_IF([test -r /usr/lib64/libedit.so],
      [editline_lib="-ledit"],
      AS_IF([test -r /usr/lib/libedit.so],
        [editline_lib="-ledit"],
        AS_IF([test -r /usr/lib/x86_64-linux-gnu/libedit.so],
          [editline_lib="-ledit"],
          AC_MSG_ERROR([editline shared object library not found.])))),
    # Using developer installed editline
    AS_IF([test -r "${editline_dir}/lib64/libedit.a"],
      [editline_lib="${editline_dir}/lib64/libedit.a"],
      AS_IF([test -r "${editline_dir}/lib/libedit.a"],
        [editline_lib="${editline_dir}/lib/libedit.a"],
        AC_MSG_ERROR([editline library not found.])
      )
    )
  )
  AC_MSG_RESULT([$editline_dir])
  AC_CHECK_LIB([ncurses], [tgetent],
    [curses_lib="-lncurses"],
    AC_CHECK_LIB([curses], [tgetent],
      [curses_lib="-lcurses"],
      AC_MSG_ERROR([curses library not found.])))
  [editline_lib="$editline_lib $curses_lib"]
  AC_SUBST(editline_inc)
  AC_SUBST(editline_lib)
  AC_DEFINE([QMGR_HAVE_HIST], [], [Defined when editline is available])
])

