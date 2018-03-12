
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

pbsmoduledir = $(libdir)/@PBS_PYTHON_DESTLIB@/pbs

pbsmodule_PYTHON = pbs/__init__.py

pbsv1moduledir = $(libdir)/@PBS_PYTHON_DESTLIB@/pbs/v1

pbsv1module_PYTHON = \
	$(top_builddir)/src/lib/Libpython/pbs_ifl.py \
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



pbshooksdir = $(libdir)/@PBS_PYTHON_DESTLIB@/pbs_hooks

dist_pbshooks_DATA = \
	pbs_hooks/PBS_translate_mpp.HK \
	pbs_hooks/PBS_translate_mpp.PY \
	pbs_hooks/PBS_power.HK \
	pbs_hooks/PBS_power.PY \
	pbs_hooks/PBS_power.CF \
	pbs_hooks/PBS_alps_inventory_check.HK \
	pbs_hooks/PBS_alps_inventory_check.PY \
	pbs_hooks/PBS_xeon_phi_provision.HK \
	pbs_hooks/PBS_xeon_phi_provision.PY 
