
#
# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# The PBS Pro software is licensed under the terms of the GNU Affero General
# Public License agreement ("AGPL"), except where a separate commercial license
# agreement for PBS Pro version 14 or later has been executed in writing with
# Altair.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software - under
# a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.
#

ptlmoduledir = $(exec_prefix)/unsupported/fw/ptl
ptlbindir = $(exec_prefix)/unsupported/fw/bin

dist_ptlbin_SCRIPTS = \
	bin/pbs_stat \
	bin/pbs_loganalyzer

dist_ptlmodule_PYTHON = ptl/__init__.py

ptlmodulelibdir = $(ptlmoduledir)/lib

dist_ptlmodulelib_PYTHON = \
	ptl/lib/pbs_api_to_cli.py \
	ptl/lib/pbs_ifl_mock.py \
	ptl/lib/pbs_testlib.py \
	ptl/lib/__init__.py

ptlmoduleutilsdir = $(ptlmoduledir)/utils

dist_ptlmoduleutils_PYTHON = \
	ptl/utils/pbs_procutils.py \
	ptl/utils/pbs_dshutils.py \
	ptl/utils/pbs_covutils.py \
	ptl/utils/pbs_cliutils.py \
	ptl/utils/pbs_logutils.py \
	ptl/utils/pbs_testsuite.py \
	ptl/utils/pbs_fileutils.py \
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
	mv pbs_loganalyzer pbs_loganalyzer.py

uninstall-hook:
	cd $(DESTDIR)$(ptlbindir) && \
	rm -f pbs_stat.py pbs_loganalyzer.py

