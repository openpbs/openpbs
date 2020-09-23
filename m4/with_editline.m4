
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

AC_DEFUN([PBS_AC_WITH_EDITLINE],
[
  AC_ARG_WITH([editline],
    AS_HELP_STRING([--with-editline=DIR],
      [Specify the directory where editline is installed.]
    )
  )
  [editline_dir="$with_editline"]
  AC_MSG_CHECKING([for editline])
  AS_IF(
    [test "$editline_dir" = ""],
    AC_CHECK_HEADER([histedit.h], [], AC_MSG_ERROR([editline headers not found.])),
    [test -r "$editline_dir/include/histedit.h"],
    [editline_inc="-I$editline_dir/include"],
    AC_MSG_ERROR([editline headers not found.])
  )
  AS_IF(
    # Using system installed editline
    [test "$editline_dir" = ""],
    AC_CHECK_LIB([edit], [el_init],
      [editline_lib="-ledit"],
      AC_MSG_ERROR([editline shared object library not found.])),
    # Using developer installed editline
    [test -r "${editline_dir}/lib64/libedit.a"],
    [editline_lib="${editline_dir}/lib64/libedit.a"],
    [test -r "${editline_dir}/lib/libedit.a"],
    [editline_lib="${editline_dir}/lib/libedit.a"],
    AC_MSG_ERROR([editline library not found.])
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
