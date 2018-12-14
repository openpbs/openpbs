
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

AC_DEFUN([PBS_AC_WITH_LIBZ],
[
  AC_ARG_WITH([libz],
    AS_HELP_STRING([--with-libz=DIR],
      [Specify the directory where libz is installed.]
    )
  )
  AS_IF([test "x$with_libz" != "x"],
    libz_dir=["$with_libz"],
    libz_dir=["/lib64"]
  )
  AC_MSG_CHECKING([for libz])
  AS_IF([test "$libz_dir" = "/lib64"],
    # Using system installed libz
	libz_inc=""
	AS_IF([test -r "/lib64/libz.so" -o -r "/usr/lib64/libz.so" -o -r "/usr/lib/x86_64-linux-gnu/libz.so"],
    	[libz_lib="-lz"],
      AC_MSG_ERROR([libz shared object library not found.])
	),

	# Using developer installed libz
    AS_IF([test -r "$libz_dir/include/zlib.h"],
      [libz_include="$libz_dir/include"],
      AC_MSG_ERROR([libz headers not found.])
    )
	libz_inc="-I$libz_include"
    AS_IF([test -r "${libz_dir}/lib64/libz.a"],
      [libz_lib="${libz_dir}/lib64/libz.a"],
      AS_IF([test -r "${libz_dir}/lib/libz.a"],
        [libz_lib="${libz_dir}/lib/libz.a"],
        AC_MSG_ERROR([libz not found.])
      )
    )
  )
  AC_MSG_RESULT([$libz_dir])
  AC_SUBST(libz_inc)
  AC_SUBST(libz_lib)
  AC_DEFINE([PBS_COMPRESSION_ENABLED], [], [Defined when libz is available])
])
