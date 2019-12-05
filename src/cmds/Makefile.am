
#
# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

SUBDIRS = scripts

bin_PROGRAMS = \
	pbsdsh \
	pbsnodes \
	pbs_attach \
	pbs_password \
	pbs_tmrsh \
	pbs_ralter \
	pbs_rdel \
	pbs_rstat \
	pbs_rsub \
	pbs_migrate_users \
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
	pbs_ds_password.bin \
	pbs_demux

dist_bin_SCRIPTS = \
	mpiexec \
	nqs2pbs \
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
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@

pbsdsh_CPPFLAGS = ${common_cflags}
pbsdsh_LDADD = ${common_libs}
pbsdsh_SOURCES = pbsdsh.c

pbsnodes_CPPFLAGS = ${common_cflags}
pbsnodes_LDADD = ${common_libs}
pbsnodes_SOURCES = pbsnodes.c

pbs_attach_CPPFLAGS = ${common_cflags}
pbs_attach_LDADD = ${common_libs}
pbs_attach_SOURCES = pbs_attach.c

pbs_demux_CPPFLAGS = ${common_cflags}
pbs_demux_LDADD = ${common_libs}
pbs_demux_SOURCES = pbs_demux.c

pbs_ds_password_bin_CPPFLAGS = \
	${common_cflags} \
	@database_inc@
pbs_ds_password_bin_LDADD = \
	$(top_builddir)/src/lib/Libdb/libdb.a \
	${common_libs} \
	@database_lib@ \
	-lssl \
	-lcrypto

pbs_ds_password_bin_SOURCES = pbs_ds_password.c

pbs_password_CPPFLAGS = ${common_cflags}
pbs_password_LDADD = ${common_libs}
pbs_password_SOURCES = pbs_password.c

pbs_tmrsh_CPPFLAGS = ${common_cflags}
pbs_tmrsh_LDADD = ${common_libs}
pbs_tmrsh_SOURCES = pbs_tmrsh.c

pbs_ralter_CPPFLAGS = ${common_cflags}
pbs_ralter_LDADD = ${common_libs}
pbs_ralter_SOURCES = pbs_ralter.c cmds_common.c

pbs_rdel_CPPFLAGS = ${common_cflags}
pbs_rdel_LDADD = ${common_libs}
pbs_rdel_SOURCES = pbs_rdel.c

pbs_rstat_CPPFLAGS = ${common_cflags}
pbs_rstat_LDADD = ${common_libs}
pbs_rstat_SOURCES = pbs_rstat.c

pbs_rsub_CPPFLAGS = ${common_cflags}
pbs_rsub_LDADD = ${common_libs}
pbs_rsub_SOURCES = pbs_rsub.c cmds_common.c

pbs_migrate_users_CPPFLAGS = ${common_cflags}
pbs_migrate_users_LDADD = ${common_libs}
pbs_migrate_users_SOURCES = pbs_migrate_users.c

pbs_release_nodes_CPPFLAGS = ${common_cflags}
pbs_release_nodes_LDADD = ${common_libs}
pbs_release_nodes_SOURCES = pbs_release_nodes.c

qalter_CPPFLAGS = ${common_cflags}
qalter_LDADD = ${common_libs}
qalter_SOURCES = qalter.c cmds_common.c

qdel_CPPFLAGS = ${common_cflags}
qdel_LDADD = ${common_libs}
qdel_SOURCES = qdel.c

qdisable_CPPFLAGS = ${common_cflags}
qdisable_LDADD = ${common_libs}
qdisable_SOURCES = qdisable.c

qenable_CPPFLAGS = ${common_cflags}
qenable_LDADD = ${common_libs}
qenable_SOURCES = qenable.c

qhold_CPPFLAGS = ${common_cflags}
qhold_LDADD = ${common_libs}
qhold_SOURCES = qhold.c

qmgr_CPPFLAGS = \
	${common_cflags} \
	@editline_inc@
qmgr_LDADD = \
	${common_libs} \
	@editline_lib@
qmgr_SOURCES = qmgr.c cmds_common.c

qmove_CPPFLAGS = ${common_cflags}
qmove_LDADD = ${common_libs}
qmove_SOURCES = qmove.c

qorder_CPPFLAGS = ${common_cflags}
qorder_LDADD = ${common_libs}
qorder_SOURCES = qorder.c

qmsg_CPPFLAGS = ${common_cflags}
qmsg_LDADD = ${common_libs}
qmsg_SOURCES = qmsg.c

qrerun_CPPFLAGS = ${common_cflags}
qrerun_LDADD = ${common_libs}
qrerun_SOURCES = qrerun.c

qrls_CPPFLAGS = ${common_cflags}
qrls_LDADD = ${common_libs}
qrls_SOURCES = qrls.c

qrun_CPPFLAGS = ${common_cflags}
qrun_LDADD = ${common_libs}
qrun_SOURCES = qrun.c

qselect_CPPFLAGS = ${common_cflags}
qselect_LDADD = ${common_libs}
qselect_SOURCES = qselect.c

qsig_CPPFLAGS = ${common_cflags}
qsig_LDADD = ${common_libs}
qsig_SOURCES = qsig.c

qstat_CPPFLAGS = ${common_cflags}
qstat_LDADD = ${common_libs}
qstat_SOURCES = qstat.c

qstart_CPPFLAGS = ${common_cflags}
qstart_LDADD = ${common_libs}
qstart_SOURCES = qstart.c

qstop_CPPFLAGS = ${common_cflags}
qstop_LDADD = ${common_libs}
qstop_SOURCES = qstop.c

qsub_CPPFLAGS = ${common_cflags}
qsub_LDADD = ${common_libs}
qsub_SOURCES = qsub.c cmds_common.c

qterm_CPPFLAGS = ${common_cflags}
qterm_LDADD = ${common_libs}
qterm_SOURCES = qterm.c
