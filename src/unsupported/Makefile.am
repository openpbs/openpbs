
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

unsupporteddir = ${exec_prefix}/unsupported

unsupported_PROGRAMS = pbs_rmget

dist_unsupported_SCRIPTS = \
	pbs_loganalyzer \
	pbs_stat \
	pbs_config \
	sgiICEvnode.sh \
	sgiICEplacement.sh \
	sgigenvnodelist.awk

# Marking all *.py files as data as these files are meant to be used as hooks and
# need no compilation.
dist_unsupported_DATA = \
	NodeHealthCheck.py \
	load_balance.py \
	mom_dyn_res.py \
	rapid_inter.py \
	run_pelog_shell.py \
	NodeHealthCheck.json \
	README \
	pbs_jobs_at.8B \
	pbs_rescquery.3B \
	run_pelog_shell.ini \
	cray_readme \
	ReliableJobStartup.py \
	pbs_output.py

pbs_rmget_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@libz_inc@ \
	@KRB5_CFLAGS@

pbs_rmget_LDADD = \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	-lpthread \
	@libz_lib@ \
	@KRB5_LIBS@

pbs_rmget_SOURCES = pbs_rmget.c
