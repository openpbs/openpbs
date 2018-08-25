
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

AC_DEFUN([PBS_AC_WITH_TCL],
[
  AC_ARG_WITH([tcl],
    AS_HELP_STRING([--with-tcl=DIR],
      [Specify the directory where Tcl is installed.]
    )
  )
  AS_IF([test "x$with_tcl" != "x"],
    tcl_dir=["$with_tcl"],
    tcl_dir=["/usr"]
  )
  AC_MSG_CHECKING([for Tcl])
  AS_IF([test -r "$tcl_dir/lib64/tclConfig.sh"],
    [. "$tcl_dir/lib64/tclConfig.sh"],
    AS_IF([test -r "$tcl_dir/lib/tclConfig.sh"],
      [. "$tcl_dir/lib/tclConfig.sh"],
      AS_IF([test -r "$tcl_dir/lib/x86_64-linux-gnu/tclConfig.sh"],
        [. "$tcl_dir/lib/x86_64-linux-gnu/tclConfig.sh"],
        AC_MSG_ERROR([tclConfig.sh not found]))))
  AC_MSG_RESULT([$tcl_dir])
  AC_MSG_CHECKING([for Tcl version])
  AS_IF([test "x$TCL_VERSION" = "x"],
    AC_MSG_ERROR([Could not determine Tcl version]))
  AC_MSG_RESULT([$TCL_VERSION])
  [tcl_version="$TCL_VERSION"]
  AC_SUBST(tcl_version)
  AC_MSG_CHECKING([for Tk])
  AS_IF([test -r "$tcl_dir/lib64/tkConfig.sh"],
    [. "$tcl_dir/lib64/tkConfig.sh"],
    AS_IF([test -r "$tcl_dir/lib/tkConfig.sh"],
      [. "$tcl_dir/lib/tkConfig.sh"],
      AS_IF([test -r "$tcl_dir/lib/x86_64-linux-gnu/tkConfig.sh"],
        [. "$tcl_dir/lib/x86_64-linux-gnu/tkConfig.sh"],
        AC_MSG_ERROR([tkConfig.sh not found]))))
  AC_MSG_RESULT([$tcl_dir])
  AC_MSG_CHECKING([for Tk version])
  AS_IF([test "x$TK_VERSION" = "x"],
    AC_MSG_ERROR([Could not determine Tk version]))
  AC_MSG_RESULT([$TK_VERSION])
  [tk_version="$TK_VERSION"]
  AC_SUBST(tk_version)
  AS_IF([test x$TCL_INCLUDE_SPEC = x],
    # Using developer installed tcl
    [tcl_inc="-I$tcl_dir/include"]
    [tcl_lib="$tcl_dir/lib/libtcl$TCL_VERSION.a $TCL_LIBS"]
    [tk_inc="-I$tcl_dir/include"]
    [tk_lib="$tcl_dir/lib/libtcl$TCL_VERSION.a $tcl_dir/lib/libtk$TK_VERSION.a $TK_LIBS"],
    # Using system installed tcl
    [tcl_inc="$TCL_INCLUDE_SPEC"]
    [tcl_lib="$TCL_LIB_SPEC $TCL_LIBS"]
    [tk_inc="$TK_INCLUDE_SPEC"]
    [tk_lib=`echo "$TCL_LIB_SPEC $TK_LIB_SPEC $TK_LIBS" | ${SED} -e 's/-lXss //'`])
  AC_SUBST(tcl_inc)
  AC_SUBST(tcl_lib)
  AC_SUBST(tk_inc)
  AC_SUBST(tk_lib)
  [TCLSH_PATH=$tcl_dir/bin/tclsh$tcl_version]
  AC_SUBST(TCLSH_PATH)
  AC_DEFINE([TCL], [], [Defined when Tcl is available])
  AC_DEFINE([TK], [], [Defined when TK is available])
])

