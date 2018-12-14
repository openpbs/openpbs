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
if ENABLEPTL
ptl_testsdir = ${ptl_prefix}/tests
dist_ptl_tests_PYTHON = $(wildcard $(srcdir)/*.py)

ptl_testfunctionaldir = $(ptl_testsdir)/functional
dist_ptl_testfunctional_DATA = $(wildcard $(srcdir)/functional/*.py)

ptl_testinterfacesdir = $(ptl_testsdir)/interfaces
dist_ptl_testinterfaces_DATA = $(wildcard $(srcdir)/interfaces/*.py)

ptl_testperformancedir = $(ptl_testsdir)/performance
dist_ptl_testperformance_DATA = $(wildcard $(srcdir)/performance/*.py)

ptl_testresiliencedir = $(ptl_testsdir)/resilience
dist_ptl_testresilience_DATA = $(wildcard $(srcdir)/resilience/*.py)

ptl_testsecuritydir = $(ptl_testsdir)/security
dist_ptl_testsecurity_DATA = $(wildcard $(srcdir)/security/*.py)

ptl_testselftestdir = $(ptl_testsdir)/selftest
dist_ptl_testselftest_DATA = $(wildcard $(srcdir)/selftest/*.py)

ptl_testupgradesdir = $(ptl_testsdir)/upgrades
dist_ptl_testupgrades_DATA = $(wildcard $(srcdir)/upgrades/*.py)
endif
