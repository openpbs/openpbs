
#
# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

AC_DEFUN([PBS_AC_WITH_PMIX],
[
  AC_ARG_WITH([pmix],
    AS_HELP_STRING([--with-pmix=DIR],
      [Specify the directory where the pmix library is installed.]
    )
  )
  AC_MSG_CHECKING([for PMIx])
  AS_IF([test "x$with_pmix" = "xno" -o "x$with_pmix" = "x"],
    AC_MSG_RESULT([no]),
    AS_IF([test "x$with_pmix" = "xyes"],
      pmix_dir=["/usr"],
      pmix_dir=["$with_pmix"]
    )
    AS_IF([test -r "$pmix_dir/include/pmix_version.h"],
      [pmix_version_h="$pmix_dir/include/pmix_version.h"],
      AC_MSG_ERROR([PMIx headers not found.])
    )
    AC_MSG_RESULT([$pmix_dir])
    AC_MSG_CHECKING([PMIx version])
    pmix_version_major=`${SED} -n 's/^#define PMIX_VERSION_MAJOR \([[0-9]]*\)L/\1/p' "$pmix_version_h"`
    AS_IF([test "x$pmix_version_major" = "x"],
      AC_MSG_ERROR([Could not determine PMIx major version.])
    )
    pmix_version_minor=`${SED} -n 's/^#define PMIX_VERSION_MINOR \([[0-9]]*\)L/\1/p' "$pmix_version_h"`
    AS_IF([test "x$pmix_version_minor" = "x"],
      AC_MSG_ERROR([Could not determine PMIx minor version.])
    )
    pmix_version_release=`${SED} -n 's/^#define PMIX_VERSION_RELEASE \([[0-9]]*\)L/\1/p' "$pmix_version_h"`
    AS_IF([test "x$pmix_version_release" = "x"],
      AC_MSG_ERROR([Could not determine PMIx release version.])
    )
    pmix_version="$pmix_version_major.$pmix_version_minor.$pmix_version_release"
    AC_MSG_RESULT([$pmix_version])
    AS_IF([test "$pmix_dir" = "/usr"],
      [pmix_lib="-lpmix"; pmix_inc=""],
      AS_IF([test -r "$pmix_dir/lib/libpmix.so"],
        [pmix_lib="-L$pmix_dir/lib -lpmix"],
        AS_IF([test -r "$pmix_dir/lib64/libpmix.so"],
          [pmix_lib="-L$pmix_dir/lib64 -lpmix"],
          AC_MSG_ERROR([PMIx library not found.])
        )
      )
      pmix_inc="-I$pmix_dir/include"
    )
    AC_SUBST(pmix_inc)
    AC_SUBST(pmix_lib)
    AC_DEFINE([PMIX], [], [Defined when PMIx is available])
  )
])
