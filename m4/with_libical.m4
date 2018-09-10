
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

AC_DEFUN([PBS_AC_WITH_LIBICAL],
[
  AC_ARG_WITH([libical],
    AS_HELP_STRING([--with-libical=DIR],
      [Specify the directory where the ical library is installed.]
    )
  )
  AS_IF([test "x$with_libical" != "x"],
    libical_dir=["$with_libical"],
    libical_dir=["/usr"]
  )
  AC_MSG_CHECKING([for libical])
  AS_IF([test -r "$libical_dir/include/libical/ical.h"],
    [libical_include="$libical_dir/include"],
    AC_MSG_ERROR([libical headers not found.])
  )
  libical_version=`$SED -n 's/^#define ICAL_VERSION "\([[0-9]]*\)..*/\1/p' "$libical_include/libical/ical.h"`
  AS_IF([test "x$libical_version" = "x"],
    AC_MSG_ERROR([Could not determine libical version.])
  )
  AS_IF([test $libical_version -gt 1],
    AC_DEFINE([LIBICAL_API2], [], [Defined when libical version >= 2])
  )
  AS_IF([test "$libical_dir" = "/usr"],
    dnl Using system installed libical
    libical_inc=""
    AS_IF([test -r "/usr/lib64/libical.so" -o -r "/usr/lib/libical.so" -o -r "/usr/lib/x86_64-linux-gnu/libical.so"],
      [libical_lib="-lical"],
      AC_MSG_ERROR([libical shared object library not found.])
    ),
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
