#
# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

lib_LTLIBRARIES = libdb.la

libdb_la_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@database_inc@

libdb_la_LDFLAGS = -version-info 0:0:0

libdb_la_LIBADD = \
	@database_lib@

libdb_la_SOURCES = \
	db_postgres.h \
	db_common.c \
	db_attr.c \
	db_job.c \
	db_resv.c \
	db_svr.c \
	db_que.c \
	db_node.c \
	db_sched.c

dist_libexec_SCRIPTS = \
	pbs_db_utility \
	pbs_db_env \
	pbs_db_schema.sql \
	pbs_schema_upgrade

dist_sbin_SCRIPTS = \
	pbs_ds_systemd

install-exec-hook:
	install -D $(DESTDIR)$(libdir)/libdb.so.0.0.0 $(DESTDIR)$(libdir)/libdb_pg.so
uninstall:
	rm -f $(DESTDIR)$(libdir)/libdb_pg.so
