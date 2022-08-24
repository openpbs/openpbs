
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

SUBDIRS = scripts

bin_PROGRAMS = \
	pbsdsh \
	pbsnodes \
	pbs_attach \
	pbs_tmrsh \
	pbs_ralter \
	pbs_rdel \
	pbs_rstat \
	pbs_rsub \
	pbs_release_nodes \
	qalter \
	qdel \
	qdisable \
	qenable \
	qhold \
	qmgr \
	qmove \
	qorder \
	qmsg \
	qrerun \
	qrls \
	qrun \
	qselect \
	qsig \
	qstat \
	qstart \
	qstop \
	qsub \
	qterm

sbin_PROGRAMS = \
	pbs_dataservice.bin \
	pbs_ds_password.bin \
	pbs_demux

dist_bin_SCRIPTS = \
	mpiexec \
	pbs_lamboot \
	pbs_mpihp \
	pbs_mpilam \
	pbs_mpirun \
	pbs_remsh \
	pbsrun \
	pbsrun_unwrap \
	pbsrun_wrap

common_cflags = \
	-I$(top_srcdir)/src/include \
	@KRB5_CFLAGS@

common_libs = \
	$(top_builddir)/src/lib/Libpbs/libpbs.la \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@

common_sources = \
	$(top_srcdir)/src/lib/Libcmds/cmds_common.c

pbsdsh_CPPFLAGS = ${common_cflags}
pbsdsh_LDADD = ${common_libs}
pbsdsh_SOURCES = pbsdsh.c ${common_sources}

pbsnodes_CPPFLAGS = ${common_cflags}
pbsnodes_LDADD = ${common_libs}
pbsnodes_SOURCES = pbsnodes.c ${common_sources}

pbs_attach_CPPFLAGS = ${common_cflags}
pbs_attach_LDADD = ${common_libs}
pbs_attach_SOURCES = pbs_attach.c pbs_attach_sup.c ${common_sources}

pbs_demux_CPPFLAGS = ${common_cflags}
pbs_demux_LDADD = ${common_libs}
pbs_demux_SOURCES = pbs_demux.c

pbs_dataservice_bin_CPPFLAGS = \
	${common_cflags}
pbs_dataservice_bin_LDADD = \
	$(top_builddir)/src/lib/Libdb/libpbsdb.la \
	${common_libs} \
	-lssl \
	-lcrypto
pbs_dataservice_bin_SOURCES = pbs_dataservice.c ${common_sources}

pbs_ds_password_bin_CPPFLAGS = \
	${common_cflags}
pbs_ds_password_bin_LDADD = \
	$(top_builddir)/src/lib/Libdb/libpbsdb.la \
	${common_libs} \
	-lssl \
	-lcrypto
pbs_ds_password_bin_SOURCES = pbs_ds_password.c ${common_sources}

pbs_tmrsh_CPPFLAGS = ${common_cflags}
pbs_tmrsh_LDADD = ${common_libs}
pbs_tmrsh_SOURCES = pbs_tmrsh.c ${common_sources}

pbs_ralter_CPPFLAGS = ${common_cflags}
pbs_ralter_LDADD = ${common_libs}
pbs_ralter_SOURCES = pbs_ralter.c ${common_sources}

pbs_rdel_CPPFLAGS = ${common_cflags}
pbs_rdel_LDADD = ${common_libs}
pbs_rdel_SOURCES = pbs_rdel.c ${common_sources}

pbs_rstat_CPPFLAGS = ${common_cflags}
pbs_rstat_LDADD = ${common_libs}
pbs_rstat_SOURCES = pbs_rstat.c ${common_sources}

pbs_rsub_CPPFLAGS = ${common_cflags}
pbs_rsub_LDADD = ${common_libs}
pbs_rsub_SOURCES = pbs_rsub.c ${common_sources}

pbs_release_nodes_CPPFLAGS = ${common_cflags}
pbs_release_nodes_LDADD = ${common_libs}
pbs_release_nodes_SOURCES = pbs_release_nodes.c ${common_sources}

qalter_CPPFLAGS = ${common_cflags}
qalter_LDADD = ${common_libs}
qalter_SOURCES = qalter.c ${common_sources}

qdel_CPPFLAGS = ${common_cflags}
qdel_LDADD = ${common_libs}
qdel_SOURCES = qdel.c ${common_sources}

qdisable_CPPFLAGS = ${common_cflags}
qdisable_LDADD = ${common_libs}
qdisable_SOURCES = qdisable.c ${common_sources}

qenable_CPPFLAGS = ${common_cflags}
qenable_LDADD = ${common_libs}
qenable_SOURCES = qenable.c ${common_sources}

qhold_CPPFLAGS = ${common_cflags}
qhold_LDADD = ${common_libs}
qhold_SOURCES = qhold.c ${common_sources}

qmgr_CPPFLAGS = \
	${common_cflags} \
	@editline_inc@
qmgr_LDADD = \
	${common_libs} \
	@editline_lib@
qmgr_SOURCES = qmgr.c qmgr_sup.c ${common_sources}

qmove_CPPFLAGS = ${common_cflags}
qmove_LDADD = ${common_libs}
qmove_SOURCES = qmove.c ${common_sources}

qorder_CPPFLAGS = ${common_cflags}
qorder_LDADD = ${common_libs}
qorder_SOURCES = qorder.c ${common_sources}

qmsg_CPPFLAGS = ${common_cflags}
qmsg_LDADD = ${common_libs}
qmsg_SOURCES = qmsg.c ${common_sources}

qrerun_CPPFLAGS = ${common_cflags}
qrerun_LDADD = ${common_libs}
qrerun_SOURCES = qrerun.c ${common_sources}

qrls_CPPFLAGS = ${common_cflags}
qrls_LDADD = ${common_libs}
qrls_SOURCES = qrls.c ${common_sources}

qrun_CPPFLAGS = ${common_cflags}
qrun_LDADD = ${common_libs}
qrun_SOURCES = qrun.c ${common_sources}

qselect_CPPFLAGS = ${common_cflags}
qselect_LDADD = ${common_libs}
qselect_SOURCES = qselect.c ${common_sources}

qsig_CPPFLAGS = ${common_cflags}
qsig_LDADD = ${common_libs}
qsig_SOURCES = qsig.c ${common_sources}

qstat_CPPFLAGS = ${common_cflags}
qstat_LDADD = ${common_libs}
qstat_SOURCES = qstat.c ${common_sources}

qstart_CPPFLAGS = ${common_cflags}
qstart_LDADD = ${common_libs}
qstart_SOURCES = qstart.c ${common_sources}

qstop_CPPFLAGS = ${common_cflags}
qstop_LDADD = ${common_libs}
qstop_SOURCES = qstop.c ${common_sources}

qsub_CPPFLAGS = ${common_cflags}
qsub_LDADD = ${common_libs} \
		-lssl \
		-lcrypto
qsub_SOURCES = qsub.c qsub_sup.c ${common_sources}

qterm_CPPFLAGS = ${common_cflags}
qterm_LDADD = ${common_libs}
qterm_SOURCES = qterm.c ${common_sources}
