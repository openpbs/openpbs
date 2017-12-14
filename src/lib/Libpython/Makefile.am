
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

noinst_LIBRARIES = libpbspython.a libpbspython_svr.a

libpbspython_a_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@

libpbspython_a_SOURCES = \
	common_python_utils.c \
	pbs_ifl_wrap.c \
	pbs_python_external.c

libpbspython_svr_a_CPPFLAGS = \
	-I$(top_srcdir)/src/include \
	@PYTHON_INCLUDES@

libpbspython_svr_a_SOURCES = \
	pbs_python_svr_external.c \
	module_pbs_v1.c \
	pbs_python_svr_internal.c \
	pbs_python_svr_size_type.c \
	pbs_python_import_types.c

EXTRA_DIST = \
	$(top_srcdir)/src/lib/Libifl/pbs_ifl_wrap.c

CLEANFILES = \
	pbs_ifl.py \
	pbs_ifl_wrap.c \
	pbs_ifl.i

pbs_ifl_wrap.c: $(top_srcdir)/src/lib/Libifl/pbs_ifl_wrap.c
	echo '%module pbs_ifl' > pbs_ifl.i ; \
	echo '%{' >> pbs_ifl.i ; \
	echo '#include "pbs_ifl.h"' >> pbs_ifl.i ; \
	echo '%}' >> pbs_ifl.i ; \
	echo '%include "pbs_ifl.h"' >> pbs_ifl.i ; \
	@swig_dir@/bin/swig -I`ls -d @swig_dir@/share/swig/*` \
		-I`ls -d @swig_dir@/share/swig/*/python` \
		-I$(top_srcdir)/src/include \
		-python pbs_ifl.i
