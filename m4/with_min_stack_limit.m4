
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

AC_DEFUN([PBS_AC_WITH_MIN_STACK_LIMIT],
[
  AC_MSG_CHECKING([for min stack limit])
  AC_ARG_WITH([stack-limit],
    AS_HELP_STRING([--with_min_stack_limit=LIMIT],
      [Specify the minimum stack limit.]
    )
  )
  AS_IF([test "x$with_min_stack_limit" != "x"],
    limit_value=[$with_min_stack_limit],
    limit_value=[0x1000000]
  )
  AC_MSG_RESULT([$limit_value])
  AC_SUBST([limit_value])
  AC_DEFINE_UNQUOTED([MIN_STACK_LIMIT], [$limit_value], [Mininum stack limit])
])

