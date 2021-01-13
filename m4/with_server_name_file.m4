
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

AC_DEFUN([PBS_AC_WITH_SERVER_NAME_FILE],
[
  AC_MSG_CHECKING([for PBS server name file])
  AC_ARG_WITH([pbs-server-name-file],
    AS_HELP_STRING([--with-pbs-server-name-file=FILE],
      [Location of the PBS server name file relative to PBS_HOME. Default is PBS_HOME/server_name]
    )
  )
  AS_IF([test "x$with_server_name_file" != "x"],
    [pbs_default_file=$with_server_name_file],
    [pbs_default_file=server_name]
  )
  AS_CASE([$pbs_default_file],
    [/*],
      [PBS_DEFAULT_FILE=$pbs_default_file],
    [PBS_DEFAULT_FILE=$PBS_SERVER_HOME/$pbs_default_file]
  )
  AC_MSG_RESULT([$PBS_DEFAULT_FILE])
  AC_SUBST(PBS_DEFAULT_FILE)
  AC_DEFINE_UNQUOTED([PBS_DEFAULT_FILE], ["$PBS_DEFAULT_FILE"], [Location of the PBS server name file])
])
