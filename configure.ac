
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

AC_PREREQ([2.63])
# Use PBS_VERSION to override the version statically defined here. For example:
# ./configure PBS_VERSION=20.0.0 --prefix=/opt/pbs
AC_INIT([OpenPBS],
  [20.0.0],
  [pbssupport@altair.com],
  [openpbs],
  [http://www.openpbs.org/])
AC_CONFIG_HEADERS([src/include/pbs_config.h])
AC_CONFIG_SRCDIR([src/cmds/qmgr.c])
AC_CONFIG_AUX_DIR([buildutils])
AC_CONFIG_MACRO_DIR([m4])
AC_CANONICAL_TARGET([])
os_id=`grep ^ID= /etc/os-release | sed -n 's/.*"\(.*\)"/\1/p'`
AS_CASE([$os_id],
  [opensuse-tumbleweed], m4_define([am_init_string], [-Wall foreign subdir-objects]),
  [*], m4_define([am_init_string], [-Wall foreign]))
AM_INIT_AUTOMAKE(am_init_string)
AC_USE_SYSTEM_EXTENSIONS


# Checks for programs.
AC_PROG_AWK
AC_PROG_YACC
AC_PROG_SED
AC_PROG_CC
AC_PROG_LEX
AC_PROG_INSTALL
AC_PROG_LN_S
AC_PROG_CXX

AC_SUBST([AM_CXXFLAGS], [--std=c++11])

# Automake macros
#AM_PROG_AR macro is defined with automake version >= 1.12
m4_ifdef([AM_PROG_AR], [AM_PROG_AR])
AM_PROG_CC_C_O

# Initialize libtool
AM_PROG_LIBTOOL
LT_INIT([shared static])

# Checks for libraries.
AC_CHECK_LIB([c], [xdr_int],
  [],
  AC_CHECK_LIB(nsl, xdr_int)
)
AC_CHECK_LIB([c], [ruserok],
  [],
  AC_CHECK_LIB(socket, ruserok)
)
AC_CHECK_LIB([c], [crypt],
  [],
  AC_CHECK_LIB(crypt, crypt)
)
AC_CHECK_LIB([c], [posix_openpt],
  AC_DEFINE([HAVE_POSIX_OPENPT], [], [Defined whe posix_openpt is available])
)
AC_CHECK_LIB(dl, dlopen)
AC_CHECK_LIB([kvm], [kvm_open])
AC_CHECK_LIB([socket], [socket],
  [socket_lib="-lsocket -lnsl"]
  AC_SUBST(socket_lib),
  [socket_lib=""]
  AC_SUBST(socket_lib),
  [-lnsl]
)
AC_CHECK_LIB([c], [malloc_info],
  AC_DEFINE([HAVE_MALLOC_INFO], [], [Defined when malloc_info is available])
)

# Check for X Window System
AC_PATH_XTRA

# Checks for optional header files.
AC_CHECK_HEADERS([ \
	com_err.h \
	gssapi.h \
	krb5.h \
	libpq-fe.h \
	mach/mach.h \
	nlist.h \
	sys/eventfd.h \
	sys/systeminfo.h \
])

# Checks for required header files.
AC_CHECK_HEADERS([ \
	stdio.h \
	alloca.h \
	arpa/inet.h \
	assert.h \
	ctype.h \
	dirent.h \
	dlfcn.h \
	execinfo.h \
	fcntl.h \
	float.h \
	fstab.h \
	ftw.h \
	grp.h \
	libgen.h \
	limits.h \
	math.h \
	memory.h \
	netdb.h \
	netinet/in.h \
	netinet/in_systm.h \
	netinet/ip.h \
	netinet/tcp.h \
	openssl/aes.h \
	openssl/bio.h \
	openssl/err.h \
	openssl/evp.h \
	openssl/ssl.h \
	paths.h \
	poll.h \
	pthread.h \
	pwd.h \
	regex.h \
	signal.h \
	stdbool.h \
	stddef.h \
	stdint.h \
	stdio.h \
	stdlib.h \
	string.h \
	strings.h \
	syslog.h \
	sys/fcntl.h \
	sys/file.h \
	sys/ioctl.h \
	sys/mman.h \
	sys/mount.h \
	sys/param.h \
	sys/poll.h \
	sys/quota.h \
	sys/resource.h \
	sys/select.h \
	sys/signal.h \
	sys/socket.h \
	sys/stat.h \
	sys/statvfs.h \
	sys/time.h \
	sys/timeb.h \
	sys/times.h \
	sys/types.h \
	sys/uio.h \
	sys/un.h \
	sys/unistd.h \
	sys/user.h \
	sys/utsname.h \
	sys/wait.h \
	termios.h \
	time.h \
	unistd.h \
	utime.h \
	X11/Intrinsic.h \
	X11/X.h \
	X11/Xlib.h \
	zlib.h \
	],, AC_MSG_ERROR([Required header file is missing.]) \
)

# Checks for typedefs, structures, and compiler characteristics.
#AC_CHECK_HEADER_STDBOOL macro is defined with autoconf version >= 2.67
m4_ifdef([AC_CHECK_HEADER_STDBOOL], [AC_CHECK_HEADER_STDBOOL])
AC_TYPE_UID_T
AC_TYPE_MODE_T
AC_TYPE_OFF_T
AC_TYPE_PID_T
AC_C_RESTRICT
AC_TYPE_SIZE_T
AC_TYPE_SSIZE_T
AC_CHECK_MEMBERS([struct stat.st_blksize])
AC_TYPE_UINT16_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_UINT8_T
AC_CHECK_TYPES([ptrdiff_t])

# Checks for library functions.
AC_FUNC_ALLOCA
AC_FUNC_CHOWN
AC_FUNC_ERROR_AT_LINE
AC_FUNC_FORK
AC_FUNC_GETGROUPS
AC_FUNC_GETMNTENT
AC_FUNC_LSTAT_FOLLOWS_SLASHED_SYMLINK
AC_FUNC_MKTIME
AC_FUNC_MMAP
AC_FUNC_STRERROR_R
AC_FUNC_STRTOD
AC_CHECK_FUNCS([ \
	alarm \
	atexit \
	bzero \
	dup2 \
	endpwent \
	floor \
	ftruncate \
	getcwd \
	gethostbyaddr \
	gethostbyname \
	gethostname \
	getmntent \
	getpagesize \
	gettimeofday \
	hasmntopt \
	inet_ntoa \
	localtime_r \
	memchr \
	memmove \
	memset \
	mkdir \
	munmap \
	pathconf \
	poll \
	pstat_getdynamic \
	putenv \
	realpath \
	regcomp \
	rmdir \
	select \
	setresuid \
	setresgid \
	getpwuid \
	initgroups \
	seteuid \
	setegid \
	strerror_r \
	socket \
	strcasecmp \
	strchr \
	strcspn \
	strdup \
	strerror \
	strncasecmp \
	strpbrk \
	strrchr \
	strspn \
	strstr \
	strtol \
	strtoul \
	strtoull \
	sysinfo \
	uname \
	utime \
])

PKG_PROG_PKG_CONFIG
m4_ifdef([PKG_INSTALLDIR],
  [PKG_INSTALLDIR],
  [
    pkgconfigdir=/usr/lib64/pkgconfig
    AC_SUBST([pkgconfigdir])
  ])


# PBS macros (order matters for some of these)
PBS_AC_PBS_VERSION
PBS_AC_DECL_H_ERRNO
PBS_AC_DECL_SOCKLEN_T
PBS_AC_DECL_EPOLL
PBS_AC_DECL_EPOLL_PWAIT
PBS_AC_DECL_PPOLL
PBS_AC_WITH_SERVER_HOME
PBS_AC_WITH_SERVER_NAME_FILE
PBS_AC_WITH_DATABASE_DIR
PBS_AC_WITH_DATABASE_USER
PBS_AC_WITH_DATABASE_PORT
PBS_AC_WITH_PBS_CONF_FILE
PBS_AC_WITH_TMP_DIR
PBS_AC_WITH_UNSUPPORTED_DIR
PBS_AC_WITH_CORE_LIMIT
PBS_AC_WITH_PYTHON
PBS_AC_WITH_EXPAT
PBS_AC_WITH_EDITLINE
PBS_AC_WITH_HWLOC
PBS_AC_WITH_LIBICAL
PBS_AC_WITH_PMIX
PBS_AC_WITH_SENDMAIL
PBS_AC_WITH_SWIG
PBS_AC_WITH_TCL
PBS_AC_WITH_TCLATRSEP
PBS_AC_WITH_XAUTH
PBS_AC_WITH_KRBAUTH
PBS_AC_WITH_MIN_STACK_LIMIT
PBS_AC_DISABLE_SHELL_PIPE
PBS_AC_DISABLE_SYSLOG
PBS_AC_SECURITY
PBS_AC_ENABLE_ALPS
PBS_AC_WITH_LIBZ
PBS_AC_ENABLE_PTL
PBS_AC_SYSTEMD_UNITDIR
PBS_AC_PATCH_LIBTOOL

AC_CONFIG_FILES([
	openpbs.spec
	Makefile
	buildutils/Makefile
	doc/Makefile
	test/Makefile
	test/fw/Makefile
	test/tests/Makefile
	test/fw/setup.py
	test/fw/ptl/__init__.py
	src/Makefile
	src/cmds/Makefile
	src/cmds/mpiexec
	src/cmds/pbs_lamboot
	src/cmds/pbs_mpihp
	src/cmds/pbs_mpilam
	src/cmds/pbs_mpirun
	src/cmds/pbs_remsh
	src/cmds/pbsrun_unwrap
	src/cmds/pbsrun_wrap
	src/cmds/pbsrun
	src/cmds/scripts/Makefile
	src/cmds/scripts/modulefile
	src/cmds/scripts/pbs_habitat
	src/cmds/scripts/pbs_init.d
	src/cmds/scripts/pbs_reload
	src/cmds/scripts/pbs_poerun
	src/cmds/scripts/pbs_postinstall
	src/cmds/scripts/pbs.service
	src/cmds/scripts/pbsrun.poe
	src/hooks/Makefile
	src/iff/Makefile
	src/include/Makefile
	src/include/pbs_version.h
	src/lib/Libattr/Makefile
	src/lib/Libdb/Makefile
	src/lib/Libdb/pgsql/Makefile
	src/lib/Libifl/Makefile
	src/lib/Liblog/Makefile
	src/lib/Libnet/Makefile
	src/lib/Libpbs/Makefile
	src/lib/Libpbs/pbs.pc
	src/lib/Libpython/Makefile
	src/lib/Libsec/Makefile
	src/lib/Libsite/Makefile
	src/lib/Libtpp/Makefile
	src/lib/Libutil/Makefile
	src/lib/Libauth/Makefile
	src/lib/Libauth/gss/Makefile
	src/lib/Libauth/munge/Makefile
	src/lib/Liblicensing/Makefile
	src/lib/Makefile
	src/modules/Makefile
	src/modules/python/Makefile
	src/mom_rcp/Makefile
	src/resmom/Makefile
	src/scheduler/Makefile
	src/server/Makefile
	src/tools/Makefile
	src/tools/wrap_tcl.sh
	src/unsupported/Makefile
])
AC_OUTPUT
