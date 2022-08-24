
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

bin_PROGRAMS = \
	pbs_hostn \
	pbs_python \
	pbs_tclsh \
	pbs_wish \
	printjob.bin \
	printjob_svr.bin \
	tracejob \
	pbs_sleep

sbin_PROGRAMS = \
	pbs_ds_monitor \
	pbs_idled \
	pbs_probe \
	pbs_upgrade_job

EXTRA_PROGRAMS = \
	chk_tree \
	rstester

common_cflags = \
	-I$(top_srcdir)/src/include \
	@KRB5_CFLAGS@

common_libs = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@

pbs_sleep_LDFLAGS = -all-static
pbs_sleep_SOURCES = pbs_sleep.c

chk_tree_CPPFLAGS = ${common_cflags}
chk_tree_LDADD = ${common_libs}
chk_tree_SOURCES = chk_tree.c

pbs_ds_monitor_CPPFLAGS = ${common_cflags}
pbs_ds_monitor_LDADD = \
	$(top_builddir)/src/lib/Libdb/libpbsdb.la \
	${common_libs} \
	-lssl \
	-lcrypto

pbs_ds_monitor_SOURCES = pbs_ds_monitor.c $(top_srcdir)/src/lib/Libcmds/cmds_common.c

pbs_idled_CPPFLAGS = ${X_CFLAGS} ${common_cflags}
pbs_idled_LDADD = \
	${common_libs} \
	${X_PRE_LIBS} \
	${X_LIBS} \
	-lX11
pbs_idled_SOURCES = pbs_idled.c $(top_srcdir)/src/lib/Libcmds/cmds_common.c

pbs_hostn_CPPFLAGS = ${common_cflags}
pbs_hostn_LDADD = ${common_libs}
pbs_hostn_SOURCES = hostn.c

pbs_probe_CPPFLAGS = \
	${common_cflags} \
	@PYTHON_INCLUDES@
pbs_probe_LDADD = \
	${common_libs} \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@
pbs_probe_SOURCES = pbs_probe.c $(top_srcdir)/src/lib/Libcmds/cmds_common.c

pbs_python_CPPFLAGS =  \
	-DPBS_PYTHON=1.1 \
	${common_cflags} \
	@PYTHON_INCLUDES@

pbs_python_LDADD = \
	$(top_builddir)/src/lib/Libpython/libpbspython.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libattr/libattr.a \
	${common_libs} \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@

pbs_python_SOURCES = \
	$(top_srcdir)/src/server/resc_attr.c \
	$(top_srcdir)/src/server/jattr_get_set.c \
	$(top_srcdir)/src/server/sattr_get_set.c \
	$(top_srcdir)/src/server/qattr_get_set.c \
	$(top_srcdir)/src/server/nattr_get_set.c \
	$(top_srcdir)/src/server/setup_resc.c \
	$(top_srcdir)/src/server/vnparse.c \
	$(top_srcdir)/src/lib/Libcmds/cmds_common.c \
	pbs_python.c

pbs_tclsh_CPPFLAGS = \
	${common_cflags} \
	@libz_inc@ \
	@tcl_inc@

pbs_tclsh_LDADD = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@ \
	@libz_lib@ \
	@tcl_lib@

pbs_tclsh_SOURCES = \
	pbs_tclWrap.c \
	site_tclWrap.c \
	pbsTclInit.c

pbs_upgrade_job_CPPFLAGS = ${common_cflags}
pbs_upgrade_job_LDADD = ${common_libs}
pbs_upgrade_job_SOURCES = pbs_upgrade_job.c

pbs_wish_CPPFLAGS = \
	${common_cflags} \
	@libz_inc@ \
	@tk_inc@

pbs_wish_LDADD = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@ \
	@libz_lib@ \
	@tk_lib@

pbs_wish_SOURCES = \
	pbs_tclWrap.c \
	site_tclWrap.c \
	pbsTkInit.c

printjob_bin_CPPFLAGS = ${common_cflags}
printjob_bin_LDADD = ${common_libs}
printjob_bin_SOURCES = printjob.c $(top_srcdir)/src/lib/Libcmds/cmds_common.c

printjob_svr_bin_CPPFLAGS = \
	${common_cflags} \
	-I$(top_srcdir)/src/lib/Libdb \
	-DPRINTJOBSVR

printjob_svr_bin_LDADD = \
	$(top_builddir)/src/lib/Libdb/libpbsdb.la \
	${common_libs} \
	-lssl \
	-lcrypto

printjob_svr_bin_SOURCES = \
	$(top_srcdir)/src/server/jattr_get_set.c \
	$(top_srcdir)/src/lib/Libcmds/cmds_common.c \
	printjob.c

rstester_CPPFLAGS = ${common_cflags}
rstester_LDADD = ${common_libs}
rstester_SOURCES = rstester.c

tracejob_CPPFLAGS = ${common_cflags}
tracejob_LDADD = ${common_libs}
tracejob_SOURCES = \
	$(top_srcdir)/src/lib/Libcmds/cmds_common.c \
	tracejob.c \
	tracejob.h
