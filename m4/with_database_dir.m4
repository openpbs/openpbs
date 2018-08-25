
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

AC_DEFUN([PBS_AC_WITH_DATABASE_DIR],
[
  AC_MSG_CHECKING([for PBS database directory])
  AC_ARG_WITH([database-dir],
    AS_HELP_STRING([--with-database-dir=DIR],
      [Specify the directory where the PBS database is installed.]
    )
  )
  AS_IF([test "x$with_database_dir" != "x"],
    [database_dir="$with_database_dir"],
    [database_dir="/usr"]
  )
  AS_IF([test -r "$database_dir/include/libpq-fe.h"],
    AS_IF([test "$database_dir" != "/usr"],
      [database_inc="-I$database_dir/include"]),
    AS_IF([test -r "$database_dir/include/pgsql/libpq-fe.h"],
      [database_inc="-I$database_dir/include/pgsql"],
      AS_IF([test -r "$database_dir/include/postgresql/libpq-fe.h"],
        [database_inc="-I$database_dir/include/postgresql"],
        AC_MSG_ERROR([Database headers not found.]))))
  AS_IF([test "$database_dir" = "/usr"],
    # Using system installed PostgreSQL
    AS_IF([test -r "/usr/lib64/libpq.so" -o -r "/usr/lib/libpq.so" -o -r "/usr/lib/x86_64-linux-gnu/libpq.so"],
      [database_lib="-lpq"],
      AC_MSG_ERROR([PBS database shared object library not found.])),
    # Using developer installed PostgreSQL
      AS_IF([test -r "$database_dir/lib64/libpq.a"],
        [database_lib="$database_dir/lib64/libpq.a"],
        AS_IF([test -r "$database_dir/lib/libpq.a"],
          [database_lib="$database_dir/lib/libpq.a"],
          AC_MSG_ERROR([PBS database library not found.])
        )
      )
  )
  AC_MSG_RESULT([$database_dir])
  AC_SUBST([database_dir])
  AC_SUBST([database_inc])
  AC_SUBST([database_lib])
  AC_SUBST([database_ldflags])
  AC_DEFINE([DATABASE], [], [Defined when PBS database is available])
])

