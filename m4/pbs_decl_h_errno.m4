
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

# Test to see whether h_errno is visible when netdb.h is included.
# At least under HP-UX 10.x this is not the case unless
# XOPEN_SOURCE_EXTENDED is declared but then other nasty stuff happens.
# The appropriate thing to do is to call this macro and then
# if it is not available do a "extern int h_errno;" in the code.

AC_DEFUN([PBS_AC_DECL_H_ERRNO],
  [AC_CACHE_CHECK([for h_errno declaration in netdb.h],
    ac_cv_decl_h_errno,
    [AC_TRY_COMPILE([#include <sys/types.h>
#ifdef HAVE_UNISTD_H
#include <unistd.h>
#endif
#include <netdb.h>
],
      [int _ZzQ = (int)(h_errno + 1);],
      [ac_cv_decl_h_errno=yes],
      [ac_cv_decl_h_errno=no])
    ])
  AS_IF([test x$ac_cv_decl_h_errno = xyes],
    AC_DEFINE(H_ERRNO_DECLARED, [], [Defined when h_errno is declared in netdb.h]))
])

