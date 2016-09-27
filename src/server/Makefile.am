
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

sbin_PROGRAMS = pbs_server.bin pbs_comm

pbs_server_bin_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@database_inc@ \
	@expat_inc@ \
	@libical_inc@ \
	@PYTHON_INCLUDES@ \
	@KRB5_CFLAGS@

pbs_server_bin_LDADD = \
	$(top_builddir)/src/lib/Libattr/libattr.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	$(top_builddir)/src/lib/Libsite/libsite.a \
	$(top_builddir)/src/lib/Libpython/libpbspython.a \
	$(top_builddir)/src/lib/Libpython/libpbspython_svr.a \
	$(top_builddir)/src/lib/Libdb/libdb.a \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	@database_ldflags@ \
	@database_lib@ \
	@expat_lib@ \
	@libical_lib@ \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@ \
	-lssl \
	-lcrypto \
	@KRB5_LIBS@

pbs_server_bin_SOURCES = \
	accounting.c \
	array_func.c \
	attr_recov.c \
	attr_recov_db.c \
	checkkey.c \
	dis_read.c \
	failover.c \
	geteusernam.c \
	hook_func.c \
	issue_request.c \
	job_attr_def.c \
	job_func.c \
	job_recov.c \
	job_recov_db.c \
	job_route.c \
	license_client.c \
	mom_info.c \
	node_attr_def.c \
	node_func.c \
	node_manager.c \
	node_recov_db.c \
	pbsd_init.c \
	pbsd_main.c \
	process_request.c \
	queue_attr_def.c \
	queue_func.c \
	queue_recov.c \
	queue_recov_db.c \
	reply_send.c \
	req_delete.c \
	req_getcred.c \
	req_gssauthenuser.c \
	req_holdjob.c \
	req_jobobit.c \
	req_locate.c \
	req_manager.c \
	req_message.c \
	req_modify.c \
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
	resc_attr.c \
	resc_def_all.c \
	resv_attr.c \
	resv_attr_def.c \
	run_sched.c \
	sched_attr_def.c \
	setup_resc.c \
	stat_job.c \
	svr_attr.c \
	svr_attr_def.c \
	svr_chk_owner.c \
	svr_connect.c \
	svr_func.c \
	svr_jobfunc.c \
	svr_mail.c \
	svr_migrate_data.c \
	svr_movejob.c \
	svr_recov.c \
	svr_recov_db.c \
	svr_resccost.c \
	user_func.c \
	vnparse.c

pbs_comm_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	-I$(top_srcdir)/src/lib/Libtpp \
	@KRB5_CFLAGS@

pbs_comm_LDADD = \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	-lpthread \
	@socket_lib@ \
	@KRB5_LIBS@

pbs_comm_SOURCES = pbs_comm.c

EXTRA_DIST = \
	master_job_attr_def.xml \
	master_node_attr_def.xml \
	master_queue_attr_def.xml \
	master_resc_def_all.xml \
	master_resv_attr_def.xml \
	master_sched_attr_def.xml \
	master_svr_attr_def.xml

CLEANFILES = \
	job_attr_def.c \
	node_attr_def.c \
	queue_attr_def.c \
	resc_def_all.c \
	resv_attr_def.c \
	sched_attr_def.c \
	svr_attr_def.c

job_attr_def.c: $(top_srcdir)/src/server/master_job_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_job_attr_def.xml \
		-e /dev/null -s $@ -a job

svr_attr_def.c: $(top_srcdir)/src/server/master_svr_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_svr_attr_def.xml \
		-e /dev/null -s $@ -a server

queue_attr_def.c: $(top_srcdir)/src/server/master_queue_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_queue_attr_def.xml \
		-e /dev/null -s $@ -a queue

node_attr_def.c: $(top_srcdir)/src/server/master_node_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_node_attr_def.xml \
		-e /dev/null -s $@ -a node

sched_attr_def.c: $(top_srcdir)/src/server/master_sched_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_sched_attr_def.xml \
		-e /dev/null -s $@ -a sched

resv_attr_def.c: $(top_srcdir)/src/server/master_resv_attr_def.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_resv_attr_def.xml \
		-e /dev/null -s $@ -a resv

resc_def_all.c: $(top_srcdir)/src/server/master_resc_def_all.xml
	@echo Generating $@ from $< ; \
	python $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/server/master_resc_def_all.xml \
		-e /dev/null -s $@ -a resc

