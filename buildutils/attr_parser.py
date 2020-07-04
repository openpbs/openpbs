# coding: utf-8
# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


"""
    attr_parser.py will parse xml files also called master attribute files
containing all the members of both server and ecl files,and will generate
two corresponding files one for server and one for ecl
"""
import getopt
import os
import pdb
import re
import string
import sys
import enum
import xml.dom.minidom
import xml.parsers.expat

list_ecl = []
list_svr = []
list_defs = []

global attr_type
global newattr

global ms
global me

class PropType(enum.Enum):
    BOTH = 0
    SERVER = 1
    ECL = 2

class switch(object):

    """
    This class provides the functionality which is equivalent
    to switch/case statements in C. It only needs to be defined
    once.
    """

    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:  # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


def fileappend(prop_type, line):
    """
    fileappend function - (wrapper on top of append for being able to
    select the file where to write
    """
    global attr_type

    if prop_type == PropType.SERVER:
        if attr_type == PropType.SERVER or attr_type == PropType.BOTH:
            list_svr.append(line)
    elif prop_type == PropType.ECL:
        if attr_type == PropType.ECL or attr_type == PropType.BOTH:
            list_ecl.append(line)
    elif prop_type == PropType.BOTH:
        if attr_type == PropType.SERVER or attr_type == PropType.BOTH:
            list_svr.append(line)
        if attr_type == PropType.ECL or attr_type == PropType.BOTH:
            list_ecl.append(line)
    return None


def getText(s_file, e_file, d_file):
    """
    getText function - (writes the data stored in lists to file)
    """
    buff = "".join(list_svr)
    for line in buff:
        s_file.write(line)

    buff = "".join(list_ecl)
    for line in buff:
        e_file.write(line)

    buff = "".join(list_defs)
    for line in buff:
        d_file.write(line)

def do_head(node):
    alist = node.getElementsByTagName('head')
    for a in alist:
        list_svr.append ("/*Disclaimer: This is a machine generated file.*/" + '\n')
        list_svr.append("/*For modifying any attribute change corresponding XML file */" + '\n')
        list_ecl.append("/*Disclaimer: This is a machine generated file.*/" + '\n')
        list_ecl.append("/*For modifying any attribute change corresponding XML file */" + '\n')
        blist = a.getElementsByTagName('SVR')
        blist_ecl = a.getElementsByTagName('ECL')
        for s in blist:
            text1 = s.childNodes[0].nodeValue
            text1 = text1.strip(' \t')
            list_svr.append(text1)
        for e in blist_ecl:
            text2 = e.childNodes[0].nodeValue
            text2 = text2.strip(' \t')
            list_ecl.append(text2)

def do_index(attr):
    li = None
    li = attr.getElementsByTagName('member_index')
    if li:
        for v in li:
            buf = v.childNodes[0].nodeValue
            list_defs.append("\n\t" + buf + ",")

def do_member(attr, p_flag, tag_name):
    global newattr
    buf = None
    comma = ','
    if newattr:
        comma = ''

    newattr = False
    li = attr.getElementsByTagName(tag_name)
    if li:
        svr = li[0].getElementsByTagName('SVR')
        if svr:
            value = svr
            for v in value:
                buf = v.childNodes[0].nodeValue
                fileappend(PropType.SERVER, comma + '\n' + '\t' + '\t' + buf)

        ecl = li[0].getElementsByTagName('ECL')
        if ecl:
            value = ecl
            for v in value:
                buf = v.childNodes[0].nodeValue
                fileappend(PropType.ECL, comma + '\n' + '\t' + '\t' + buf)

        value = li
        for v in value:
            buf = v.childNodes[0].nodeValue
            if buf:
                s = buf.strip('\n \t')
                if s:
                    fileappend(p_flag, comma + '\n' + '\t' + '\t' + buf)


def attr(m_file, s_file, e_file, d_file):
    """
    attr function - (opens the files reads them and using minidom filters relevant
    data to individual lists)
    """
    from xml.dom import minidom

    global attr_type
    global newattr
    newattr = False

    doc = minidom.parse(m_file)
    nodes = doc.getElementsByTagName('data')

    for node in nodes:
        do_head(node)
    
        at_list = node.getElementsByTagName('attributes')
        for attr in at_list:
            attr_type = PropType.BOTH
            newattr  = True

            flag_name = attr.getAttribute('flag')
            if flag_name == 'SVR':
                attr_type = PropType.SERVER
            if flag_name == 'ECL':
                attr_type = PropType.ECL

            inc_name =  attr.getAttribute('include')
            if inc_name:
                fileappend(PropType.SERVER, '\n' + inc_name)

            mem_list = attr.childNodes[0].nodeValue
            mem_list = mem_list.strip(' \t')
            fileappend(PropType.BOTH, mem_list)

            macro_name = attr.getAttribute('macro')
            if macro_name:
                fileappend(PropType.BOTH, '\n' + macro_name + "\n")

            do_index(attr)
            fileappend(PropType.BOTH, '\t{')

            do_member(attr, PropType.BOTH, 'member_name')
            do_member(attr, PropType.SERVER, 'member_at_decode')
            do_member(attr, PropType.SERVER, 'member_at_encode')
            do_member(attr, PropType.SERVER, 'member_at_set')
            do_member(attr, PropType.SERVER, 'member_at_comp')
            do_member(attr, PropType.SERVER, 'member_at_free')
            do_member(attr, PropType.SERVER, 'member_at_action')
            do_member(attr, PropType.BOTH, 'member_at_flags')
            do_member(attr, PropType.BOTH, 'member_at_type')
            do_member(attr, PropType.SERVER, 'member_at_parent')
            do_member(attr, PropType.ECL, 'member_verify_function')

            fileappend(PropType.BOTH, '\n\t}')
            fileappend(PropType.BOTH, ",")

            if macro_name:
                fileappend(PropType.BOTH, '\n #endif')

        tail_list = node.getElementsByTagName('tail')
        for t in tail_list:
            tail_value = t.childNodes[0].nodeValue
            if tail_value == None:
                pass
            fileappend(PropType.BOTH, '\n')
            tail_both = t.getElementsByTagName('both')
            tail_svr = t.getElementsByTagName('SVR')
            tail_ecl = t.getElementsByTagName('ECL')
            for tb in tail_both:
                b = tb.childNodes[0].nodeValue
                b = b.strip(' \t')
                list_ecl.append(b)
                list_svr.append(b)
            for ts in tail_svr:
                s = ts.childNodes[0].nodeValue
                s = s.strip(' \t')
                list_svr.append(s)
            for te in tail_ecl:
                e = te.childNodes[0].nodeValue
                e = e.strip(' \t')
                list_ecl.append(e)

        getText(s_file, e_file, d_file)


def main(argv):
    """
    The Main Module starts here-
    Opens files,and calls appropriate functions based on Object values.
    """
    global SVR_FILE
    global ECL_FILE
    global DEF_FILE
    global MASTER_FILE

    SVR_FILE = "/dev/null"
    ECL_FILE = "/dev/null"
    DEF_FILE = "/dev/null"
    MASTER_FILE = "/dev/null"

    if len(sys.argv) == 2:
        usage()
        sys.exit(1)
    try:
        opts, args = getopt.getopt(argv, "m:s:e:d:h", ["master=", "svr=", "ecl=", "attr=", "help=", "defines="])
    except getopt.error as err:
        print(str(err))
        usage()
        sys.exit(1)
    for opt, arg in opts:
        if opt in ('-h', "--help"):
            usage()
            sys.exit(1)
        elif opt in ("-m", "--master"):
            MASTER_FILE = arg
        elif opt in ("-s", "--svr"):
            SVR_FILE = arg
        elif opt in ("-d", "--defines"):
            DEF_FILE = arg
        elif opt in ("-e", "--ecl"):
            ECL_FILE = arg
        else:
            print("Invalid Option!")
            sys.exit(1)
#    Error conditions are checked here.

    if MASTER_FILE is None or not os.path.isfile(MASTER_FILE) or not os.path.getsize(MASTER_FILE) > 0:
        print("Master file not found or data is not present in File")
        sys.exit(1)

    try:
        m_file = open(MASTER_FILE, encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot Open Master File!')
        sys.exit(1)

    try:
        s_file = open(SVR_FILE, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot Open Server File!')
        sys.exit(1)

    try:
        d_file = open(DEF_FILE, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot Open Defines File!')
        sys.exit(1)

    try:
        e_file = open(ECL_FILE, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot Open Ecl File!')
        sys.exit(1)

    attr(m_file, s_file, e_file, d_file)

    m_file.close()
    s_file.close()
    e_file.close()


def usage():
    """
    Usage (depicts the usage of the script)
    """
    print("usage: prog -m <MASTER_FILE> -s <svr_attr_file> -e <ecl_attr_file> -a <object>")


if __name__ == "__main__":
    main(sys.argv[1:])
