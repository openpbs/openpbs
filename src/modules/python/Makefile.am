
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

pbs_v1_sodir = $(libdir)/python/altair

pbs_v1_so_LTLIBRARIES = \
	_pbs_v1.la \
	_pbs_ifl.la

nodist_pbs_v1_so_PYTHON = $(top_builddir)/src/lib/Libifl/pbs_ifl.py

_pbs_v1_la_SOURCES = \
	$(top_builddir)/src/lib/Libattr/attr_fn_acl.c \
	$(top_builddir)/src/lib/Libattr/attr_fn_entlim.c \
	$(top_builddir)/src/lib/Libattr/attr_fn_resc.c \
	$(top_builddir)/src/lib/Libattr/attr_fn_time.c \
	$(top_builddir)/src/lib/Libattr/attr_node_func.c \
	$(top_builddir)/src/lib/Libattr/job_attr_def.c \
	$(top_builddir)/src/lib/Libattr/node_attr_def.c \
	$(top_builddir)/src/lib/Libattr/queue_attr_def.c \
	$(top_builddir)/src/lib/Libattr/resc_def_all.c \
	$(top_builddir)/src/lib/Libattr/resv_attr_def.c \
	$(top_builddir)/src/lib/Libattr/sched_attr_def.c \
	$(top_builddir)/src/lib/Libattr/svr_attr_def.c \
	$(top_srcdir)/src/lib/Libpython/shared_python_utils.c \
	$(top_srcdir)/src/lib/Libpython/common_python_utils.c \
	$(top_srcdir)/src/lib/Libpython/pbs_python_external.c \
	$(top_srcdir)/src/lib/Libpython/pbs_python_svr_external.c \
	$(top_srcdir)/src/lib/Libpython/module_pbs_v1.c \
	$(top_srcdir)/src/lib/Libpython/pbs_python_svr_internal.c \
	$(top_srcdir)/src/lib/Libpython/pbs_python_svr_size_type.c \
	$(top_srcdir)/src/lib/Libpython/pbs_python_import_types.c \
	$(top_srcdir)/src/lib/Libutil/entlim.c \
	$(top_srcdir)/src/lib/Libutil/hook.c \
	$(top_srcdir)/src/lib/Libutil/work_task.c \
	$(top_srcdir)/src/server/resc_attr.c \
	$(top_srcdir)/src/server/setup_resc.c \
	$(top_srcdir)/src/server/vnparse.c \
	$(top_srcdir)/src/server/jattr_get_set.c \
	$(top_srcdir)/src/server/sattr_get_set.c \
	$(top_srcdir)/src/server/qattr_get_set.c \
	$(top_srcdir)/src/server/nattr_get_set.c \
	$(top_srcdir)/src/server/rattr_get_set.c \
	pbs_v1_module_init.c
_pbs_v1_la_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@ \
	@KRB5_CFLAGS@
_pbs_v1_la_LDFLAGS = \
	-module \
	-shared \
	-export-dynamic \
	-avoid-version
_pbs_v1_la_LIBADD = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la

nodist__pbs_ifl_la_SOURCES = $(top_builddir)/src/lib/Libifl/pbs_ifl_wrap.c
_pbs_ifl_la_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@
_pbs_ifl_la_LDFLAGS = \
	-module \
	-shared \
	-export-dynamic \
	-avoid-version \
	-no-undefined \
	@PYTHON_LDFLAGS@
_pbs_ifl_la_LIBADD = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la

pbsmoduledir = $(libdir)/python/altair/pbs

pbsmodule_PYTHON = pbs/__init__.py

pbsv1moduledir = $(libdir)/python/altair/pbs/v1

pbsv1module_PYTHON = \
	pbs/v1/__init__.py \
	pbs/v1/_attr_types.py \
	pbs/v1/_base_types.py \
	pbs/v1/_exc_types.py \
	pbs/v1/_export_types.py \
	pbs/v1/_svr_types.py \
	pbs/v1/_pmi_types.py \
	pbs/v1/_pmi_sgi.py \
	pbs/v1/_pmi_cray.py \
	pbs/v1/_pmi_none.py \
	pbs/v1/_pmi_utils.py



pbshooksdir = $(libdir)/python/altair/pbs_hooks

dist_pbshooks_DATA = \
	pbs_hooks/PBS_power.HK \
	pbs_hooks/PBS_power.PY \
	pbs_hooks/PBS_power.CF \
	pbs_hooks/PBS_alps_inventory_check.HK \
	pbs_hooks/PBS_alps_inventory_check.PY \
	pbs_hooks/PBS_xeon_phi_provision.HK \
	pbs_hooks/PBS_xeon_phi_provision.PY \
	pbs_hooks/PBS_cray_atom.HK \
	pbs_hooks/PBS_cray_atom.PY \
	pbs_hooks/PBS_cray_atom.CF
