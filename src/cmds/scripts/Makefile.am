
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

libinitdir = $(libdir)/init.d

dist_libinit_DATA = \
	limits.pbs_mom \
	limits.pbs_mom.compat \
	limits.post_services \
	limits.post_services.compat 

libmpidir = $(libdir)/MPI

dist_libmpi_DATA = \
	pbsrun.ch_gm.init.in \
	pbsrun.ch_mx.init.in \
	pbsrun.gm_mpd.init.in \
	pbsrun.intelmpi.init.in \
	pbsrun.mpich2.init.in \
	pbsrun.mvapich1.init.in \
	pbsrun.mvapich2.init.in \
	pbsrun.mx_mpd.init.in \
	sgiMPI.awk

pythonlibdir = $(libdir)/python

dist_pythonlib_PYTHON = \
	pbs_bootcheck.py \
	pbs_topologyinfo.py

sysprofiledir = /etc/profile.d

dist_sysprofile_DATA = \
	pbs.csh \
	pbs.sh

unitfiledir = @_unitdir@

dist_unitfile_DATA = \
	pbs.service

dist_libexec_SCRIPTS = \
	pbs_habitat \
	pbs_init.d \
	pbs_postinstall \
	pbs_preuninstall \
	pbs_posttrans \
	pbs_reload

dist_bin_SCRIPTS = \
	pbs_topologyinfo \
	printjob

dist_sbin_SCRIPTS = \
	pbs_dataservice \
	pbs_ds_password \
	pbs_server \
	pbs_snapshot

dist_sysconf_DATA = \
	modulefile \
	pbs.csh \
	pbs.sh

CLEANFILES = \
	pbs_init.d \
	limits.pbs_mom \
	limits.post_services

limits.pbs_mom: $(srcdir)/limits.pbs_mom.compat
	cp $? $@

limits.post_services: $(srcdir)/limits.post_services.compat
	cp $? $@
