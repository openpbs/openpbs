
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

AC_DEFUN([PBS_AC_WITH_HWLOC],
[
  AC_ARG_WITH([hwloc],
    AS_HELP_STRING([--with-hwloc=DIR],
      [Specify the directory where hwloc is installed.]
    )
  )
  hwloc_dir=["$with_hwloc"]
  AC_MSG_CHECKING([for hwloc])
  [hwloc_flags=""]
  [hwloc_inc=""]
  [hwloc_lib=""]
  AS_IF(
    [test "$hwloc_dir" = ""],
    AC_CHECK_HEADER([hwloc.h], [], AC_MSG_ERROR([hwloc headers not found.])),
    [test -r "$hwloc_dir/include/hwloc.h"],
    [hwloc_inc="-I$hwloc_dir/include"],
    AC_MSG_ERROR([hwloc headers not found.])
  )
  AS_IF(
    # Using system installed hwloc
    [test "$hwloc_dir" = ""],
    AC_CHECK_LIB([hwloc], [hwloc_topology_init],
      [hwloc_lib="-lhwloc"],
      AC_MSG_ERROR([hwloc shared object library not found.])
    ),
    # Using developer installed hwloc
    [test -r "${hwloc_dir}/lib64/libhwloc_embedded.a"],
    [hwloc_lib="${hwloc_dir}/lib64/libhwloc_embedded.a"],
    [test -r "${hwloc_dir}/lib/libhwloc_embedded.a"],
    [hwloc_lib="${hwloc_dir}/lib/libhwloc_embedded.a"],
    AC_MSG_ERROR([hwloc library not found.])
  )
  AC_MSG_RESULT([$hwloc_dir])
  AS_CASE([x$target_os],
    [xlinux*],
      AC_CHECK_LIB([numa], [mbind], [hwloc_lib="$hwloc_lib -lnuma"])
      AC_CHECK_LIB([udev], [udev_new], [hwloc_lib="$hwloc_lib -ludev"])
      AC_CHECK_LIB([pciaccess], [pci_system_init], [hwloc_lib="$hwloc_lib -lpciaccess"])
  )
  AC_SUBST(hwloc_flags)
  AC_SUBST(hwloc_inc)
  AC_SUBST(hwloc_lib)
  AC_DEFINE([HWLOC], [], [Defined when hwloc is available])
])
