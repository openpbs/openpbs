
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

AC_DEFUN([PBS_AC_ENABLE_CPUSET],
[
  AC_MSG_CHECKING([whether native cpuset support was requested])
  AC_ARG_ENABLE([cpuset],
    AS_HELP_STRING([--enable-cpuset],
      [Enable native cpuset support.]
    )
  )
  [cpuset_flags=""]
  AS_IF([test x$enable_cpuset = xyes],
    AC_MSG_RESULT([yes])
    AS_IF([test ! -r /usr/include/cpuset.h],
      AC_MSG_ERROR([Missing cpuset header file]))
    AS_IF([test -r /usr/include/cpumemset.h],
      [cpuset_flags="-DCPUSET_VERSION=2"; cpuset_v4=no],
      [cpuset_flags="-DCPUSET_VERSION=4"; cpuset_v4=yes])
      AS_IF([test x$cpuset_v4 = xyes],
        AS_IF([test ! -r /usr/include/bitmask.h],
          AC_MSG_ERROR([Missing libbitmask or bitmask.h header file])))
    AS_CASE([$PBS_MACH],
      [irix6*],
        [cpuset_flags="$cpuset_flags -DIRIX6_CPUSET=1"]
        [cpuset_for_irix6=yes],
      [cpuset_for_irix6=no]
    ),
    AC_MSG_RESULT([no])
  )
  AC_SUBST([cpuset_flags])
  AM_CONDITIONAL([CPUSET_ENABLED], [test x$enable_cpuset = xyes])
  AM_CONDITIONAL([CPUSET_FOR_IRIX6], [test x$cpuset_for_irix6 = xyes])
  AM_CONDITIONAL([CPUSET_V4], [test x$cpuset_v4 = xyes])
])

