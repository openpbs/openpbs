
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

sbin_PROGRAMS = pbs_server.bin pbs_comm

pbs_server_bin_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	-I$(top_srcdir)/src/lib/Liblicensing \
	@expat_inc@ \
	@libical_inc@ \
	@libz_inc@ \
	@PYTHON_INCLUDES@ \
	@KRB5_CFLAGS@

pbs_server_bin_LDADD = \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Libattr/libattr.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	$(top_builddir)/src/lib/Libsite/libsite.a \
	$(top_builddir)/src/lib/Libpython/libpbspython_svr.a \
	$(top_builddir)/src/lib/Libdb/libpbsdb.la \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Liblicensing/liblicensing.la \
	@expat_lib@ \
	@libz_lib@ \
	@libical_lib@ \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@ \
	-lssl \
	-lcrypto \
	@KRB5_LIBS@ \
	@libundolr_lib@

pbs_server_bin_SOURCES = \
	accounting.c \
	array_func.c \
	attr_recov.c \
	attr_recov_db.c \
	dis_read.c \
	failover.c \
	geteusernam.c \
	hook_func.c \
	issue_request.c \
	jattr_get_set.c \
	job_func.c \
	job_recov_db.c \
	job_route.c \
	licensing_func.c \
	mom_info.c \
	daemon_info.c \
	multi_svr.c \
	nattr_get_set.c \
	svr_comm.c \
	node_func.c \
	node_manager.c \
	node_recov_db.c \
	pbs_db_func.c \
	pbsd_init.c \
	pbsd_main.c \
	process_request.c \
	qattr_get_set.c \
	queue_func.c \
	queue_recov_db.c \
	rattr_get_set.c \
	reply_send.c \
	req_delete.c \
	req_getcred.c \
	req_holdjob.c \
	req_jobobit.c \
	req_locate.c \
	req_manager.c \
	req_message.c \
	req_modify.c \
	req_preemptjob.c \
	req_movejob.c \
	req_quejob.c \
	req_register.c \
	req_rerun.c \
	req_rescq.c \
	req_runjob.c \
	req_select.c \
	req_shutdown.c \
	req_signal.c \
	req_stat.c \
	req_track.c \
	req_cred.c \
	resc_attr.c \
	run_sched.c \
	sattr_get_set.c \
	sched_attr_get_set.c \
	sched_func.c \
	setup_resc.c \
	stat_job.c \
	svr_chk_owner.c \
	svr_connect.c \
	svr_func.c \
	svr_jobfunc.c \
	svr_mail.c \
	svr_movejob.c \
	svr_recov_db.c \
	svr_resccost.c \
	svr_credfunc.c \
	user_func.c \
	vnparse.c

pbs_comm_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@libz_inc@ \
	@KRB5_CFLAGS@

pbs_comm_LDADD = \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	-lpthread \
	@libz_lib@ \
	@socket_lib@ \
	@KRB5_LIBS@ \
	@libundolr_lib@

pbs_comm_SOURCES = pbs_comm.c
