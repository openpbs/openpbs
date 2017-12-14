
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

# Source in the /etc/pbs.conf file
conf="${PBS_CONF_FILE:-/etc/pbs.conf}"
if [ -r "${conf}" ]; then
   __PBS_EXEC=`grep '^[[:space:]]*PBS_EXEC=' "$conf" | tail -1 | sed 's/^[[:space:]]*PBS_EXEC=\([^[:space:]]*\)[[:space:]]*/\1/'`
   if [ "X${__PBS_EXEC}" != "X" ]; then
      # Define PATH and MANPATH for the users
      [ -d "${__PBS_EXEC}/bin" ] && export PATH="${PATH}:${__PBS_EXEC}/bin"
      [ -d "${__PBS_EXEC}/man" ] && export MANPATH="${MANPATH}:${__PBS_EXEC}/man"
      [ -d "${__PBS_EXEC}/share/man" ] && export MANPATH="${MANPATH}:${__PBS_EXEC}/share/man"
      if [ `whoami` = "root" ]; then
         [ -d "${__PBS_EXEC}/sbin" ] && export PATH="${PATH}:${__PBS_EXEC}/sbin"
      fi
   fi
   unset __PBS_EXEC
fi
