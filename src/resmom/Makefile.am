
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

sbin_PROGRAMS = pbs_mom

pbs_mom_CPPFLAGS = \
	-DPBS_MOM \
	-I$(top_srcdir)/src/include \
	-I$(top_srcdir)/src/resmom/linux \
	@hwloc_flags@ \
	@hwloc_inc@ \
	@pmix_inc@ \
	@libz_inc@ \
	@PYTHON_INCLUDES@ \
	@KRB5_CFLAGS@

pbs_mom_LDADD = \
	$(top_builddir)/src/lib/Libattr/libattr.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	$(top_builddir)/src/lib/Libsite/libsite.a \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	@hwloc_lib@ \
	@pmix_lib@ \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@ \
	@libz_lib@ \
	-lssl \
	-lcrypto \
	@KRB5_LIBS@

pbs_mom_SOURCES = \
	$(top_builddir)/src/lib/Libattr/job_attr_def.c \
	$(top_builddir)/src/lib/Libattr/node_attr_def.c \
	$(top_builddir)/src/lib/Libattr/resc_def_all.c \
	$(top_builddir)/src/lib/Libpython/shared_python_utils.c \
	$(top_srcdir)/src/server/mom_info.c \
	$(top_srcdir)/src/server/attr_recov.c \
	$(top_srcdir)/src/server/dis_read.c \
	$(top_srcdir)/src/server/jattr_get_set.c \
	$(top_srcdir)/src/server/nattr_get_set.c \
	$(top_srcdir)/src/server/job_func.c \
	$(top_srcdir)/src/server/process_request.c \
	$(top_srcdir)/src/server/reply_send.c \
	$(top_srcdir)/src/server/req_quejob.c \
	$(top_srcdir)/src/server/resc_attr.c \
	$(top_srcdir)/src/server/vnparse.c \
	$(top_srcdir)/src/server/setup_resc.c \
	linux/mom_mach.c \
	linux/mom_mach.h \
	linux/mom_start.c \
	linux/pe_input.c \
	catch_child.c \
	job_recov_fs.c \
	mock_run.c \
	mock_run.h \
	mom_comm.c \
	mom_hook_func.c \
	mom_inter.c \
	linux/mom_func.c \
	mom_main.c \
	mom_updates_bundle.c \
	mom_pmix.c \
	mom_pmix.h \
	mom_server.c \
	mom_vnode.c \
	mom_walltime.c \
	popen.c \
	prolog.c \
	requests.c \
	rm_dep.h \
	stage_func.c \
	start_exec.c \
	vnode_storage.c \
	renew_creds.c \
	renew_creds.h

if ALPS_ENABLED
pbs_mom_CPPFLAGS += -DMOM_ALPS=1 @expat_inc@
pbs_mom_LDADD += @expat_lib@
pbs_mom_SOURCES += linux/alps.c
endif
