
#
# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

AC_DEFUN([_KRB5_CONFIG_PATH],
[
  AC_ARG_VAR([PATH_KRB5_CONFIG], [Path to krb5-config.])
  AC_PATH_PROG([PATH_KRB5_CONFIG], [krb5-config], [], [${PATH}:/usr/kerberos/bin])
  AS_IF([test -x "$PATH_KRB5_CONFIG"],
    [
    AC_MSG_NOTICE([krb5-config found])
    ],
    [
    AC_MSG_ERROR([krb5-config not found at provided/default path])
    ])
])

AC_DEFUN([_KRB5_CONFIG_LIBS],
  [AC_REQUIRE([_KRB5_CONFIG_PATH])
  $3[]_LIBS=`"$1" --libs $2 2>/dev/null | grep -vi unknown 2>/dev/null`
])

AC_DEFUN([_KRB5_CONFIG_CFLAGS],
  [AC_REQUIRE([_KRB5_CONFIG_PATH])
  $3[]_CFLAGS=`"$1" --cflags $2 2>/dev/null`
])

AC_DEFUN([_KRB5_CHECK_HEIMDAL],
  [AC_REQUIRE([_KRB5_CONFIG_PATH])
  _KRB5_HEIMDAL=`"$1" --vendor 2>/dev/null | grep Heimdal 2>/dev/null`
])

AC_DEFUN([KRB5_CONFIG],
[
  AC_REQUIRE([_KRB5_CONFIG_PATH])

  PKG_CHECK_MODULES(com_err, [com_err])

  _KRB5_CONFIG_CFLAGS([$PATH_KRB5_CONFIG],[],[_KRB5])
  _KRB5_CONFIG_LIBS([$PATH_KRB5_CONFIG],[krb5],[_KRB5_KRB5])
  _KRB5_CONFIG_LIBS([$PATH_KRB5_CONFIG],[gssapi],[_KRB5_GSSAPI])
  _KRB5_CONFIG_LIBS([$PATH_KRB5_CONFIG],[kafs],[_KRB5_KAFS])

  # we don't want to add -lkafs into the general LIBS
  ac_save_libs=${LIBS}

  AS_IF([test "x$_KRB5_KAFS_LIBS" != "x"],
  [ac_save_ldflags=${LDFLAGS}
  LDFLAGS="${_KRB5_KAFS_LIBS} ${LDFLAGS}"
  AC_CHECK_LIB([kafs],[k_hasafs],[],[_KRB5_KAFS_LIBS=""])
  LDFLAGS="$ac_save_ldflags"],
  [])

  AS_IF([test "x$_KRB5_KAFS_LIBS" == "x"],
    [
    AC_CHECK_LIB([kafs],[k_hasafs],
      [_KRB5_KAFS_LIBS="-lkafs"],
      AC_CHECK_LIB([kopenafs],[k_hasafs],[_KRB5_KAFS_LIBS="-lkopenafs"],
        AC_MSG_WARN([k(open)afs library not found - afs will be ignored])))
    ],[])

  LIBS="$ac_save_libs"

  _KRB5_CHECK_HEIMDAL([$PATH_KRB5_CONFIG])
  AS_IF([test "x$_KRB5_HEIMDAL" != "x"],
    [AC_MSG_NOTICE([Kerberos vendor is Heimdal])
    AC_DEFINE_UNQUOTED([KRB5_HEIMDAL],[],[Kerberos is Heimdal])
    ],[])

  AC_SUBST([KRB5_CFLAGS],["$_KRB5_CFLAGS $com_err_CFLAGS"])
  _KRB5_LIBS="$_KRB5_KRB5_LIBS $_KRB5_GSSAPI_LIBS $_KRB5_KAFS_LIBS $com_err_LIBS"
  AC_SUBST([KRB5_LIBS],[$_KRB5_LIBS])
])

AC_DEFUN([PBS_AC_WITH_KRBAUTH],
[
  AC_MSG_CHECKING([for kerberos support])
  AC_ARG_WITH([krbauth],
    [AS_HELP_STRING([--with-krbauth],
       [enable kerberos authentication, krb5-config required for setup])],
    [],[with_krbauth=no])
  AM_CONDITIONAL([KRB5_ENABLED], [test "x$with_krbauth" != xno])
  AS_IF([test "x$with_krbauth" != xno],
    [
    AC_MSG_RESULT([requested])
    _KRB5_CONFIG_PATH
    KRB5_CONFIG
    AC_DEFINE_UNQUOTED([PBS_SECURITY],[KRB5],[Enable krb5/gssapi security.])
    ],
    [
    AC_MSG_RESULT([disabled])
    ])
])
