
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

lib_LIBRARIES = libpbs_sched.a

libpbs_sched_a_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@

libpbs_sched_a_SOURCES = \
	check.c \
	check.h \
	config.h \
	constant.h \
	data_types.h \
	dedtime.c \
	dedtime.h \
	fairshare.c \
	fairshare.h \
	fifo.c \
	fifo.h \
	get_4byte.c \
	globals.c \
	globals.h \
	job_info.c \
	job_info.h \
	limits.c \
	misc.c \
	misc.h \
	node_info.c \
	node_info.h \
	node_partition.c \
	node_partition.h \
	parse.c \
	parse.h \
	prev_job_info.c \
	prev_job_info.h \
	prime.c \
	prime.h \
	queue_info.c \
	queue_info.h \
	range.c \
	range.h \
	resource.h \
	resource_resv.c \
	resource_resv.h \
	resv_info.c \
	resv_info.h \
	resource.c \
	server_info.c \
	server_info.h \
	simulate.c \
	simulate.h \
	sort.c \
	sort.h \
	state_count.c \
	state_count.h \
	site_code.c \
	site_code.h \
	site_data.h

sbin_PROGRAMS = pbs_sched pbsfs

common_cppflags = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@ \
	@libical_inc@ \
	@KRB5_CFLAGS@

common_libs = \
	$(builddir)/libpbs_sched.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@ \
	@libical_lib@ \
	@KRB5_LIBS@

pbs_sched_CPPFLAGS = ${common_cppflags}
pbs_sched_LDADD = ${common_libs}
pbs_sched_SOURCES = pbs_sched.c

pbsfs_CPPFLAGS = ${common_cppflags}
pbsfs_LDADD = ${common_libs}
pbsfs_SOURCES = pbsfs.c

dist_sysconf_DATA = \
	pbs_dedicated \
	pbs_holidays \
	pbs_holidays.2017 \
	pbs_resource_group \
	pbs_sched_config

