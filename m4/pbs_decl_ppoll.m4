
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


#
# Prefix the macro names with PBS_ so they don't conflict with Python definitions
#
AC_DEFUN([PBS_AC_DECL_PPOLL],
[
  AS_CASE([x$target_os],
    [xlinux*],
      AC_MSG_CHECKING(whether ppoll API is supported)
      AC_TRY_RUN([
#include <unistd.h>
#include <poll.h>
#include <signal.h>
int main()
{
  sigset_t allsigs;
  int n;
  int fd[2];
  struct timespec timeoutspec;
  struct   pollfd  pollfds[1];
  timeoutspec.tv_nsec = 1000;
  timeoutspec.tv_sec = 0;
  pipe(fd);
  pollfds[0].fd = fd[0];
  sigemptyset(&allsigs);
  n = ppoll(pollfds, 1, &timeoutspec, &allsigs);
  return (n);
}],
        AC_DEFINE([PBS_HAVE_PPOLL], [], [Defined when ppoll is available])
        AC_MSG_RESULT([yes]),
        AC_MSG_RESULT([no])
      )
  )
])

