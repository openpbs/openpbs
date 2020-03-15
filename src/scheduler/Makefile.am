
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

lib_LIBRARIES = libpbs_sched.a

common_cflags = \
	-I$(top_srcdir)/src/include \
	@libz_inc@ \
	-pthread \
	@PYTHON_INCLUDES@ \
	@KRB5_CFLAGS@

common_libs = \
	$(builddir)/libpbs_sched.a \
	$(top_builddir)/src/lib/Libtpp/libtpp.a \
	$(top_builddir)/src/lib/Libutil/libutil.a \
	$(top_builddir)/src/lib/Liblog/liblog.a \
	$(top_builddir)/src/lib/Libpbs/.libs/libpbs.a \
	$(top_builddir)/src/lib/Libnet/libnet.a \
	$(top_builddir)/src/lib/Libsec/libsec.a \
	@PYTHON_LDFLAGS@ \
	@PYTHON_LIBS@ \
	@libz_lib@ \
	@libical_lib@ \
	@KRB5_LIBS@

libpbs_sched_a_CPPFLAGS = ${common_cflags}

libpbs_sched_a_SOURCES = \
	$(top_builddir)/src/lib/Libpython/shared_python_utils.c \
	buckets.c \
	buckets.h \
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
	multi_threading.c \
	multi_threading.h \
	node_info.c \
	node_info.h \
	node_partition.c \
	node_partition.h \
	parse.c \
	parse.h \
	pbs_bitmap.c \
	pbs_bitmap.h \
	prev_job_info.c \
	prev_job_info.h \
	prime.c \
	prime.h \
	queue.c \
	queue.h \
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

pbs_sched_CPPFLAGS = ${common_cflags}
pbs_sched_LDADD = ${common_libs} @libundolr_lib@
pbs_sched_SOURCES = pbs_sched.c

pbsfs_CPPFLAGS = ${common_cflags}
pbsfs_LDADD = ${common_libs}
pbsfs_SOURCES = pbsfs.c

dist_sysconf_DATA = \
	pbs_dedicated \
	pbs_holidays \
	pbs_holidays.2017 \
	pbs_resource_group \
	pbs_sched_config
