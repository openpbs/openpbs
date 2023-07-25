
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

AC_DEFUN([PBS_AC_WITH_CJSON],
[
  AC_ARG_WITH([cjson],
    AS_HELP_STRING([--with-cjson=DIR],
      [Specify the directory where cJSON is installed.]
    )
  )
  [cjson_dir="$with_cjson"]
  AC_MSG_CHECKING([for cJSON])
  AS_IF(
    [test "$cjson_dir" = ""],
    AC_CHECK_HEADER([cjson/cJSON.h], [], AC_MSG_ERROR([cJSON headers not found.])),
    [test -r "$cjson_dir/include/cjson/cJSON.h"],
    [cjson_inc="-I$cjson_dir/include"],
    AC_MSG_ERROR([cJSON headers not found.])
  )
  AS_IF(
    [test "$cjson_dir" = ""],
    # Using system installed cjson
    AC_CHECK_LIB([cjson], [cJSON_Parse],
      [cjson_lib="-lcjson"],
      AC_MSG_ERROR([cJSON shared object library not found.])),
    # Using developer installed cJSON
    [test -r "${cjson_dir}/lib64/libcjson.so"],
    [cjson_lib="-L${cjson_dir}/lib64 -lcjson"],
    [test -r "${cjson_dir}/lib/libcjson.so"],
    [cjson_lib="-L${cjson_dir}/lib -lcjson"],
    AC_MSG_ERROR([cJSON library not found.])
  )
  AC_MSG_RESULT([$cjson_dir])
  AC_SUBST(cjson_inc)
  AC_SUBST(cjson_lib)
  AC_DEFINE([CJSON], [], [Defined when cjson is available])
])
