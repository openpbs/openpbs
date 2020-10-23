
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

AC_DEFUN([PBS_AC_WITH_LIBICAL],
[
  AC_ARG_WITH([libical],
    AS_HELP_STRING([--with-libical=DIR],
      [Specify the directory where the ical library is installed.]
    )
  )
  [libical_dir="$with_libical"]
  AC_MSG_CHECKING([for libical])
  AS_IF(
    [test "$libical_dir" = ""],
    AC_CHECK_HEADER([libical/ical.h], [], AC_MSG_ERROR([libical headers not found.])),
    [test -r "$libical_dir/include/libical/ical.h"],
    [libical_include="$libical_dir/include"],
    AC_MSG_ERROR([libical headers not found.])
  )
  AS_IF(
    [test "$libical_include" = ""],
    [AC_PREPROC_IFELSE(
      [AC_LANG_SOURCE([[#include <libical/ical.h>
        ICAL_VERSION]])],
      [libical_version=`tail -n1 conftest.i | $SED -n 's/"\([[0-9]]*\)..*/\1/p'`]
    )],
    [libical_version=`$SED -n 's/^#define ICAL_VERSION "\([[0-9]]*\)..*/\1/p' "$libical_include/libical/ical.h"`]
  )
  AS_IF(
    [test "x$libical_version" = "x"],
    AC_MSG_ERROR([Could not determine libical version.]),
    [test "$libical_version" -gt 1],
    AC_DEFINE([LIBICAL_API2], [], [Defined when libical version >= 2])
  )
  AS_IF([test "$libical_dir" = ""],
    dnl Using system installed libical
    libical_inc=""
    AC_CHECK_LIB([ical], [icalrecurrencetype_from_string],
      [libical_lib="-lical"],
      AC_MSG_ERROR([libical shared object library not found.])),
    dnl Using developer installed libical
    libical_inc="-I$libical_include"
    AS_IF([test -r "${libical_dir}/lib64/libical.a"],
      [libical_lib="${libical_dir}/lib64/libical.a"],
      AS_IF([test -r "${libical_dir}/lib/libical.a"],
        [libical_lib="${libical_dir}/lib/libical.a"],
        AC_MSG_ERROR([ical library not found.])
      )
    )
  )
  AC_MSG_RESULT([$libical_dir])
  AC_SUBST(libical_inc)
  AC_SUBST(libical_lib)
  AC_DEFINE([LIBICAL], [], [Defined when libical is available])
])
