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

# making aptl installation in case it is enabled with configure
# all directories for ptl install start with 'ptl_'

if ENABLEPTL
ptlpkg_bindir = ${ptl_prefix}/bin

dist_ptlpkg_bin_SCRIPTS = $(wildcard $(srcdir)/bin/*)

ptlpkg_fwdir = ${ptl_prefix}/fw

dist_ptlpkg_fw_DATA =  $(srcdir)/requirements.txt

ptlpkg_pylib_topdir = ${ptl_prefix}/lib/python$(PYTHON_VERSION)/site-packages/ptl

dist_ptlpkg_pylib_top_PYTHON = $(wildcard $(builddir)/ptl/*.py)

ptlpkg_pylib_libdir = $(ptlpkg_pylib_topdir)/lib

dist_ptlpkg_pylib_lib_PYTHON = $(wildcard $(srcdir)/ptl/lib/*.py)

ptlpkg_pylib_utilsdir = $(ptlpkg_pylib_topdir)/utils

dist_ptlpkg_pylib_utils_PYTHON = $(wildcard $(srcdir)/ptl/utils/*.py)

ptlpkg_pylib_pluginsdir = $(ptlpkg_pylib_utilsdir)/plugins

dist_ptlpkg_pylib_plugins_PYTHON = $(wildcard $(srcdir)/ptl/utils/plugins/*.py)

sysprofiledir = /etc/profile.d

dist_sysprofile_DATA = \
	ptl.csh \
	ptl.sh
endif

ptlmoduledir = $(exec_prefix)/unsupported/fw/ptl
ptlbindir = $(exec_prefix)/unsupported/fw/bin

dist_ptlbin_SCRIPTS = \
	bin/pbs_stat \
	bin/pbs_loganalyzer \
	bin/pbs_snapshot \
	bin/pbs_config \
	bin/pbs_compare_results

dist_ptlmodule_PYTHON = ptl/__init__.py

ptlmodulelibdir = $(ptlmoduledir)/lib

dist_ptlmodulelib_PYTHON = \
	ptl/lib/pbs_api_to_cli.py \
	ptl/lib/pbs_ifl_mock.py \
	ptl/lib/pbs_testlib.py \
	ptl/lib/__init__.py \
	ptl/lib/ptl_config.py \
	ptl/lib/ptl_error.py \
	ptl/lib/ptl_types.py \
	ptl/lib/ptl_batchutils.py \
	ptl/lib/ptl_constants.py \
	ptl/lib/ptl_expect_action.py \
	ptl/lib/ptl_object.py \
	ptl/lib/ptl_mom.py \          
	ptl/lib/ptl_sched.py \
	ptl/lib/ptl_server.py \
	ptl/lib/ptl_comm.py \
	ptl/lib/ptl_entities.py \
	ptl/lib/ptl_fairshare.py \
	ptl/lib/ptl_resourceresv.py \
	ptl/lib/ptl_service.py \
	ptl/lib/ptl_wrappers.py

ptlmoduleutilsdir = $(ptlmoduledir)/utils

dist_ptlmoduleutils_PYTHON = \
	ptl/utils/pbs_procutils.py \
	ptl/utils/pbs_dshutils.py \
	ptl/utils/pbs_covutils.py \
	ptl/utils/pbs_cliutils.py \
	ptl/utils/pbs_logutils.py \
	ptl/utils/pbs_testsuite.py \
	ptl/utils/pbs_anonutils.py \
	ptl/utils/pbs_snaputils.py \
	ptl/utils/pbs_testusers.py \
	ptl/utils/__init__.py

ptlmoduleutilspluginsdir = $(ptlmoduleutilsdir)/plugins

dist_ptlmoduleutilsplugins_PYTHON = \
	ptl/utils/plugins/ptl_test_tags.py \
	ptl/utils/plugins/ptl_test_loader.py \
	ptl/utils/plugins/ptl_test_db.py \
	ptl/utils/plugins/ptl_test_info.py \
	ptl/utils/plugins/ptl_test_runner.py \
	ptl/utils/plugins/ptl_test_data.py \
	ptl/utils/plugins/__init__.py

install-data-hook:
	cd $(DESTDIR)$(ptlbindir) && \
	mv pbs_stat pbs_stat.py && \
	mv pbs_loganalyzer pbs_loganalyzer.py && \
	mv pbs_snapshot pbs_snapshot.py && \
	mv pbs_config pbs_config.py

uninstall-hook:
	cd $(DESTDIR)$(ptlbindir) && \
	rm -f pbs_stat.py pbs_loganalyzer.py pbs_snapshot.py pbs_config.py
