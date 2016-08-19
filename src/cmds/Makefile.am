
#
#  Copyright (C) 1994-2016 Altair Engineering, Inc.
#  For more information, contact Altair at www.altair.com.
#   
#  This file is part of the PBS Professional ("PBS Pro") software.
#  
#  Open Source License Information:
#   
#  PBS Pro is free software. You can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License as published by the Free 
#  Software Foundation, either version 3 of the License, or (at your option) any 
#  later version.
#   
#  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#   
#  You should have received a copy of the GNU Affero General Public License along 
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
#   
#  Commercial License Information: 
#  
#  The PBS Pro software is licensed under the terms of the GNU Affero General 
#  Public License agreement ("AGPL"), except where a separate commercial license 
#  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#   
#  Altair’s dual-license business model allows companies, individuals, and 
#  organizations to create proprietary derivative works of PBS Pro and distribute 
#  them - whether embedded or bundled with other software - under a commercial 
#  license agreement.
#  
#  Use of Altair’s trademarks, including but not limited to "PBS™", 
#  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
#  trademark licensing policies.
#

SUBDIRS = scripts

bin_PROGRAMS = \
	pbsdsh \
	pbsnodes \
	pbs_attach \
	pbs_password \
	pbs_tmrsh \
	pbs_rdel \
	pbs_rstat \
	pbs_rsub \
	pbs_migrate_users \
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

common_libs = \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@

pbsdsh_CPPFLAGS = -I$(top_srcdir)/src/include
pbsdsh_LDADD = ${common_libs}
pbsdsh_SOURCES = pbsdsh.c

pbsnodes_CPPFLAGS = -I$(top_srcdir)/src/include
pbsnodes_LDADD = ${common_libs}
pbsnodes_SOURCES = pbsnodes.c

pbs_attach_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_attach_LDADD = ${common_libs}
pbs_attach_SOURCES = pbs_attach.c

pbs_demux_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_demux_LDADD = ${common_libs}
pbs_demux_SOURCES = pbs_demux.c

pbs_ds_password_bin_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@database_inc@
pbs_ds_password_bin_LDADD = \
	$(top_builddir)/src/lib/Libdb/libdb.a \
	${common_libs} \
	@database_lib@ \
	-lssl \
	-lcrypto

pbs_ds_password_bin_SOURCES = pbs_ds_password.c

pbs_password_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_password_LDADD = ${common_libs}
pbs_password_SOURCES = pbs_password.c

pbs_tmrsh_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_tmrsh_LDADD = ${common_libs}
pbs_tmrsh_SOURCES = pbs_tmrsh.c

pbs_rdel_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_rdel_LDADD = ${common_libs}
pbs_rdel_SOURCES = pbs_rdel.c

pbs_rstat_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_rstat_LDADD = ${common_libs}
pbs_rstat_SOURCES = pbs_rstat.c

pbs_rsub_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_rsub_LDADD = ${common_libs}
pbs_rsub_SOURCES = pbs_rsub.c

pbs_migrate_users_CPPFLAGS = -I$(top_srcdir)/src/include
pbs_migrate_users_LDADD = ${common_libs}
pbs_migrate_users_SOURCES = pbs_migrate_users.c

qalter_CPPFLAGS = -I$(top_srcdir)/src/include
qalter_LDADD = ${common_libs}
qalter_SOURCES = qalter.c

qdel_CPPFLAGS = -I$(top_srcdir)/src/include
qdel_LDADD = ${common_libs}
qdel_SOURCES = qdel.c

qdisable_CPPFLAGS = -I$(top_srcdir)/src/include
qdisable_LDADD = ${common_libs}
qdisable_SOURCES = qdisable.c

qenable_CPPFLAGS = -I$(top_srcdir)/src/include
qenable_LDADD = ${common_libs}
qenable_SOURCES = qenable.c

qhold_CPPFLAGS = -I$(top_srcdir)/src/include
qhold_LDADD = ${common_libs}
qhold_SOURCES = qhold.c

qmgr_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@editline_inc@
qmgr_LDADD = \
	${common_libs} \
	@editline_lib@
qmgr_SOURCES = qmgr.c

qmove_CPPFLAGS = -I$(top_srcdir)/src/include
qmove_LDADD = ${common_libs}
qmove_SOURCES = qmove.c

qorder_CPPFLAGS = -I$(top_srcdir)/src/include
qorder_LDADD = ${common_libs}
qorder_SOURCES = qorder.c

qmsg_CPPFLAGS = -I$(top_srcdir)/src/include
qmsg_LDADD = ${common_libs}
qmsg_SOURCES = qmsg.c

qrerun_CPPFLAGS = -I$(top_srcdir)/src/include
qrerun_LDADD = ${common_libs}
qrerun_SOURCES = qrerun.c

qrls_CPPFLAGS = -I$(top_srcdir)/src/include
qrls_LDADD = ${common_libs}
qrls_SOURCES = qrls.c

qrun_CPPFLAGS = -I$(top_srcdir)/src/include
qrun_LDADD = ${common_libs}
qrun_SOURCES = qrun.c

qselect_CPPFLAGS = -I$(top_srcdir)/src/include
qselect_LDADD = ${common_libs}
qselect_SOURCES = qselect.c

qsig_CPPFLAGS = -I$(top_srcdir)/src/include
qsig_LDADD = ${common_libs}
qsig_SOURCES = qsig.c

qstat_CPPFLAGS = -I$(top_srcdir)/src/include
qstat_LDADD = ${common_libs}
qstat_SOURCES = qstat.c

qstart_CPPFLAGS = -I$(top_srcdir)/src/include
qstart_LDADD = ${common_libs}
qstart_SOURCES = qstart.c

qstop_CPPFLAGS = -I$(top_srcdir)/src/include
qstop_LDADD = ${common_libs}
qstop_SOURCES = qstop.c

qsub_CPPFLAGS = -I$(top_srcdir)/src/include
qsub_LDADD = ${common_libs}
qsub_SOURCES = qsub.c

qterm_CPPFLAGS = -I$(top_srcdir)/src/include
qterm_LDADD = ${common_libs}
qterm_SOURCES = qterm.c

