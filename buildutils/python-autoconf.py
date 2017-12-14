# coding: utf-8
#

#
# Python module to detect python settings to build and install python
#  embedded interpreter and any external modules
# 
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
# NOTE:
#   - requires the distutils, os and sys packages to be installed.

_REQUIRED_VERSION_MIN = '2.6.0'
_REQUIRED_VERSION_MAX = '2.7.99'

import sys
import os

if sys.version < _REQUIRED_VERSION_MIN or sys.version > _REQUIRED_VERSION_MAX:
    print "requires python version >= %s" % (_REQUIRED_VERSION,)
    raise SystemExit,2

from optparse import OptionParser
from distutils import sysconfig

get_py_config_var = sysconfig.get_config_var
py_version = get_py_config_var('VERSION')

if py_version is None:
    py_version = sys.version[:3]
    
py_stdlibdir = get_py_config_var('LIBDIR')
# the actual LIBDIR in case install path got moved
if py_stdlibdir:
    py_stdlibdir_real  = "%s/%s" % (sysconfig.PREFIX, py_stdlibdir.split(os.sep)[-1])
else:
    py_stdlibdir_real  = "%s/lib" % (sysconfig.PREFIX,) 

py_lib_configdir = get_py_config_var('LIBPL')
if py_lib_configdir:
    py_lib_configdir=py_lib_configdir.replace(py_stdlibdir,py_stdlibdir_real)

def get_includes():
    """get compiled pythons include directories"""

    rv = ["-I%s" % (sysconfig.get_python_inc(plat_specific=1),), "-I%s" % (sysconfig.get_python_inc(),)]
    return " ".join(rv)
#:: get_includes()

def get_cflags():
    """get compiler flags"""
    rv = ""
    cflags = get_py_config_var('CFLAGS')
    if cflags:
        rv = " ".join(cflags.split())
        #: TODO you could remove some options?
    return rv   
#:: get_cflags()

def get_libs():
    """get libraries to link with"""
    rv = ""
    tmp_list = []
    if py_lib_configdir:
        tmp_list.append('-L%s' % (py_lib_configdir,))
    tmp_list.append("-lpython%s" % (py_version,))
    libs = get_py_config_var('LIBS')
    if libs:
        tmp_list.extend(libs.split())
    syslibs = get_py_config_var('SYSLIBS')
    if syslibs:
        tmp_list.extend(syslibs.split())
    if tmp_list:
        rv = " ".join(tmp_list)
    return rv   
#:: get_libs()

def get_ldflags():
    """get linker flags for the compiled python"""

    rv = ""
    tmp_list = []
    
    #: this is needed so that symbols are not removed from the static library
    #: when shared modules need to be loaded
    
    py_link_for_shared = get_py_config_var('LINKFORSHARED')
    if py_lib_configdir:
        py_link_for_shared = py_link_for_shared.replace("Modules",
							py_lib_configdir);
    if py_link_for_shared:
        tmp_list.append(py_link_for_shared)
        
    if tmp_list:
        rv = " ".join(tmp_list)
        
    return rv   
#:: get_ldflagss()

def get_stdlibdir():
    """The installed pythons library directory"""

    rv = ""
    tmp_list = []
    
    
    if py_stdlibdir_real:
        tmp_list.append(py_stdlibdir_real)
        
    if tmp_list:
        rv = " ".join(tmp_list)
        
    return rv   
#:: get_stdlibdir()


def setupOptions():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("--includes", action="store_true", dest="includes", 
                      help="get header file includes for python installation")
    parser.add_option("--cflags", action="store_true", dest="cflags", 
                      help="get Compiler flags")
    parser.add_option("--libs", action="store_true", dest="libs", 
                      help="get additional libraries to be linked with")
    parser.add_option("--ldflags",action="store_true", dest="ldflags",
                      help="get library flags")
    parser.add_option("--stdlibdir",action="store_true", dest="stdlibdir",
                      help="get installed python's libdir")
    parser.add_option("--py-version",action="store_true", dest="py_version",
                      help="get version string to determine the installed python standard modules dir")
    parser.add_option("--stdlibmoddir",action="store_true", dest="stdlibmoddir",
                      help="get installed python's standard modules libdir")
    parser.add_option("--stdlibmodshareddir",action="store_true", dest="stdlibmodshareddir",
                      help="get installed python's standard modules *shared* libdir")
    return parser.parse_args()
#:: seetupOptions()


def Main():
    (options, args) = setupOptions()
    if options.ldflags:
        print get_ldflags()
    elif options.libs:
        print get_libs()
    elif options.cflags:
        print get_cflags()
    elif options.includes:
        print get_includes() 
    elif options.stdlibdir:
        print get_stdlibdir() 
    elif options.py_version:
        print py_version 
    elif options.stdlibmoddir:
        print \
	 get_py_config_var('DESTLIB').replace(py_stdlibdir,py_stdlibdir_real)
    elif options.stdlibmodshareddir:
        print \
	 get_py_config_var('DESTSHARED').replace(py_stdlibdir,py_stdlibdir_real)
#:: Main()

if __name__ == '__main__':
    Main()

