
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

lib_LIBRARIES = libattr.a

libattr_a_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@KRB5_CFLAGS@

libattr_a_SOURCES = \
	attr_atomic.c \
	attr_fn_acl.c \
	attr_fn_arst.c \
	attr_fn_b.c \
	attr_fn_c.c \
	attr_fn_entlim.c \
	attr_fn_f.c \
	attr_fn_hold.c \
	attr_fn_intr.c \
	attr_fn_l.c \
	attr_fn_ll.c \
	attr_fn_resc.c \
	attr_fn_size.c \
	attr_fn_str.c \
	attr_fn_time.c \
	attr_fn_unkn.c \
	attr_func.c \
	attr_node_func.c \
	attr_resc_func.c \
	job_attr_def.c \
	Long_.c \
	LTostr.c \
	node_attr_def.c \
	queue_attr_def.c \
	resc_def_all.c \
	resc_map.c \
	resv_attr_def.c \
	sched_attr_def.c \
	strToL.c \
	strTouL.c \
	svr_attr_def.c \
	uLTostr.c

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

job_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_job_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_job_attr_def.xml \
		-e /dev/null -s $@ -a job

svr_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_svr_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_svr_attr_def.xml \
		-e /dev/null -s $@ -a server

queue_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_queue_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_queue_attr_def.xml \
		-e /dev/null -s $@ -a queue

node_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_node_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_node_attr_def.xml \
		-e /dev/null -s $@ -a node

sched_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_sched_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_sched_attr_def.xml \
		-e /dev/null -s $@ -a sched

resv_attr_def.c: $(top_srcdir)/src/lib/Libattr/master_resv_attr_def.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_resv_attr_def.xml \
		-e /dev/null -s $@ -a resv

resc_def_all.c: $(top_srcdir)/src/lib/Libattr/master_resc_def_all.xml
	@echo Generating $@ from $< ; \
	@PYTHON@ $(top_srcdir)/buildutils/attr_parser.py \
		-m $(top_srcdir)/src/lib/Libattr/master_resc_def_all.xml \
		-e /dev/null -s $@ -a resc
