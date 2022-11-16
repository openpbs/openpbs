# coding: utf-8
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

class PropType(enum.Enum):
    '''
    BOTH - Write information for this tag to all the output files
    SERVER - Write information for this tag to the SERVER file only
    ECL - Write information for this tag to the ECL file only
    '''
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
    '''
    Selects files to append line to dependig on prop_type
    prop_type - BOTH, SERVER, ECL
    line - The string line to append to the file(s)
    '''
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


def getText(svr_file, ecl_file, defines_file):
    '''
    getText function - (writes the data stored in lists to file)
    svr_file - the server side output file
    ecl_file - the output file to be used by the ECL layer
    defines_file - the output file containing the macro definitions for the index positions
    '''
    buff = "".join(list_svr)
    for line in buff:
        svr_file.write(line)

    buff = "".join(list_ecl)
    for line in buff:
        ecl_file.write(line)

    buff = "".join(list_defs)
    for line in buff:
        defines_file.write(line)


def do_head(node):
    '''
    Processes the head element of the node passed
    '''
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
    '''
    Processes the member_index attribute attr
    '''
    li = None
    li = attr.getElementsByTagName('member_index')
    if li:
        for v in li:
            buf = v.childNodes[0].nodeValue
            list_defs.append("\n\t" + buf + ",")


def do_member(attr, p_flag, tag_name):
    '''
    Processes the member identified by tage_name
    attr - the attribute definition node
    p_flag - property flag - SVR, ECL, BOTH
    tag_name - the tag_name string to process
    '''
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


def process(master_file, svr_file, ecl_file, defines_file):
    '''
    process the master xml file and produce the outputs files as requested
    master_file - the Master XML files to process
    svr_file - the server side output file
    ecl_file - the output file to be used by the ECL layer
    defines_file - the output file containing the macro definitions for the index positions
    '''
    from xml.dom import minidom

    global attr_type
    global newattr
    newattr = False

    doc = minidom.parse(master_file)
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
            do_member(attr, PropType.SERVER, 'member_at_entlim')
            do_member(attr, PropType.SERVER, 'member_at_struct')

            fileappend(PropType.BOTH, '\n\t}')
            fileappend(PropType.BOTH, ",")

            if macro_name:
                fileappend(PropType.BOTH, '\n#else')
                fileappend(PropType.BOTH, '\n\t{\n\t\t"noop"\n\t},')
                fileappend(PropType.BOTH, '\n#endif')

        tail_list = node.getElementsByTagName('tail')
        for t in tail_list:
            tail_value = t.childNodes[0].nodeValue
            if tail_value is None:
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

        getText(svr_file, ecl_file, defines_file)


def main(argv):
    '''
    Opens files,and calls appropriate functions based on Object values.
    '''
    global SVR_FILENAME
    global ECL_FILENAME
    global DEFINES_FILENAME
    global MASTER_FILENAME

    SVR_FILENAME = "/dev/null"
    ECL_FILENAME = "/dev/null"
    DEFINES_FILENAME = "/dev/null"
    MASTER_FILENAME = "/dev/null"

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
            MASTER_FILENAME = arg
        elif opt in ("-s", "--svr"):
            SVR_FILENAME = arg
        elif opt in ("-d", "--defines"):
            DEFINES_FILENAME = arg
        elif opt in ("-e", "--ecl"):
            ECL_FILENAME = arg
        else:
            print("Invalid Option!")
            sys.exit(1)
#    Error conditions are checked here.

    if MASTER_FILENAME is None or not os.path.isfile(MASTER_FILENAME) or not os.path.getsize(MASTER_FILENAME) > 0:
        print("Master file not found or data is not present in File")
        sys.exit(1)

    try:
        master_file = open(MASTER_FILENAME, encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot open master file ' + MASTER_FILENAME)
        sys.exit(1)

    try:
        svr_file = open(SVR_FILENAME, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot open ferver file ' + SVR_FILENAME)
        sys.exit(1)

    try:
        defines_file = open(DEFINES_FILENAME, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot open defines file ' + DEFINES_FILENAME)
        sys.exit(1)

    try:
        ecl_file = open(ECL_FILENAME, 'w', encoding='utf-8')
    except IOError as err:
        print(str(err))
        print('Cannot open ecl file ' + ECL_FILENAME)
        sys.exit(1)

    process(master_file, svr_file, ecl_file, defines_file)

    master_file.close()
    svr_file.close()
    ecl_file.close()


def usage():
    """
    Usage (depicts the usage of the script)
    """
    print("usage: prog -m <MASTER_FILENAME> -s <svr_attr_file> -e <ecl_attr_file> -d <defines_file>")


if __name__ == "__main__":
    main(sys.argv[1:])
