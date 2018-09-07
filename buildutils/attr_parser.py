# coding: utf-8
# Copyright (C) 1994-2019 Altair Engineering, Inc.
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

"""
    attr_parser.py will parse xml files also called master attribute files 
containing all the members of both server and ecl files,and will generate 
two corresponding files one for server and one for ecl 
"""
import sys
import os
import re
import getopt
import string
import xml.parsers.expat
import xml.dom.minidom
import pdb

list_ecl = []
list_svr = []
global e_flag
global s_flag

global ms
global me

e_flag = 0
s_flag = 0


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
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:  # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


def fileappend(line):
    """
    fileappend function - (wrapper on top of append for being able to
    select the file where to write
    """
    global s_flag
    global e_flag

    if s_flag == 1 and e_flag == 0:
        list_svr.append(line)
    if e_flag == 1 and s_flag == 0:
        list_ecl.append(line)
    if e_flag == 0 and s_flag == 0:
        list_svr.append(line)
        list_ecl.append(line)
    return None


def getText(efl, sfl):
    """ 
    getText function - (writes the data stored in lists to file)
    """
    buff1 = "".join(list_svr)
    buff2 = "".join(list_ecl)
    for line in buff1:
        sfl.write(line)
    for line in buff2:
        efl.write(line)


def add_comma(string):
    """
    add_comma function - (will take Tag values and will put if there is any comma in it)
    """
    buff2 = string.split('\n')
    for line in buff2:
        if re.search(r'#', line):
            line = line.strip(' \t')
            list_svr.append('\t' + '\t' + line + '\n')
        elif re.search(r'\n', line):
            pass
        else:
            line = line.strip(' \t')
            list_svr.append('\t' + '\t' + '\t' + line + ',' + '\n')


def attr(masterf, svrf, eclf):
    """
    attr function - (opens the files reads them and using minidom filters relevant 
    data to individual lists) 
    """
    from xml.dom import minidom

    global e_flag
    global s_flag
    doc = minidom.parse(masterf)
    nodes = doc.getElementsByTagName('data')

    for node in nodes:
        alist = node.getElementsByTagName('head')
        for a in alist:
            list_svr.append (
                "/*Disclaimer: This is a machine generated file.*/" + '\n')
            list_svr.append(
                "/*For modifying any attribute change corresponding XML file */" + '\n')
            list_ecl.append(
                "/*Disclaimer: This is a machine generated file.*/" + '\n')
            list_ecl.append(
                "/*For modifying any attribute change corresponding XML file */" + '\n') 
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
        at_list = node.getElementsByTagName('attributes')
        for i in at_list:
            e_flag = 0
            s_flag = 0
            attr_list = i.childNodes[0].nodeValue
            inc_name =  i.getAttribute('include')
            list_svr.append( '\n' + inc_name)
            flag_name = i.getAttribute('flag')
            if flag_name == 'SVR':
                s_flag = 1
            if flag_name == 'ECL':
                e_flag = 1
            if flag_name == None:
                e_flag = 0
                s_flag = 0
            attr_list = attr_list.strip(' \t')
            fileappend(attr_list)
            h = None 
            s_mem = None 
            e_mem = None 
            mem_list1 = i.getElementsByTagName('member_name')
            if mem_list1:
                bot = mem_list1[0].getElementsByTagName('both')
                svr = mem_list1[0].getElementsByTagName('SVR')
                ecl = mem_list1[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    h = h.strip(' \t')
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + h + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_mem = s_mem.strip(' \t')
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + s_mem + ',' + '\n')
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_mem = e_mem.strip(' \t')
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + e_mem + ',' + '\n')
            else:
                sys.exit(
                    "member_name does not exist!" + i.childNodes[0].nodeValue)

            mem_list2 = i.getElementsByTagName('member_at_decode')
            if mem_list2:
                mem = mem_list2[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue  
                sys.exit(
                    "member_at_decode <Tag> does not exist! for Attribute -> " + tmp)
                 

            mem_list3 = i.getElementsByTagName('member_at_encode')
            if mem_list3:
                mem = mem_list3[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                s_flag = 1
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue 
                sys.exit(
                    "member_at_encode <Tag> does not exist! for Attribute -> " + tmp)

            mem_list4 = i.getElementsByTagName('member_at_set')
            s_flag = 1
            if mem_list4:
                mem = mem_list4[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_set <Tag> does not exist! for Attribute -> " + tmp)
            
            mem_list5 = i.getElementsByTagName('member_at_comp')
            s_flag = 1
            if mem_list5:
                mem = mem_list5[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_comp <Tag> does not exist! for Attribute -> " + tmp)
           
            mem_list6 = i.getElementsByTagName('member_at_free')
            s_flag = 1
            if mem_list6:
                mem = mem_list6[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_free <Tag> does not exist! for Attribute -> " + tmp)

            mem_list7 = i.getElementsByTagName('member_at_action')
            s_flag = 1
            if mem_list7:
                mem = mem_list7[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_action <Tag> does not exist! for Attribute -> " + tmp)
            e_flag = 0
            s_flag = 0

            mem_list8 = i.getElementsByTagName('member_at_flags')
            if mem_list8:
                mem = mem_list8[0].childNodes[0].nodeValue
                bot = mem_list8[0].getElementsByTagName('both')
                svr = mem_list8[0].getElementsByTagName('SVR')
                ecl = mem_list8[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    h = h.strip(' \t')
                    fileappend('\t' + '\t' + h + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_mem = s_mem.strip(' \t')
                    s_flag = 1
                    if re.search(r'^#', s_mem):
                        add_comma(s_mem)
                    else:
                        fileappend('\t' + '\t' + s_mem + ',' + '\n')
                s_flag = 0
                e_flag = 0
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_mem = e_mem.strip(' \t')
                    e_flag = 1
                    fileappend('\t' + '\t' + e_mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_flags <Tag> does not exist! for Attribute -> " + tmp)
            e_flag = 0
            s_flag = 0

            mem_list9 = i.getElementsByTagName('member_at_type')
            if mem_list9:
                mem = mem_list9[0].childNodes[0].nodeValue
                bot = mem_list9[0].getElementsByTagName('both')
                svr = mem_list9[0].getElementsByTagName('SVR')
                ecl = mem_list9[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    h = h.strip(' \t')
                    fileappend('\t' + '\t' + h + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_mem = s_mem.strip(' \t')
                    s_flag = 1
                    if re.search(r'^#', s_mem):
                        add_comma(s_mem)
                    else:
                        fileappend('\t' + '\t' + s_mem + ',' + '\n')
                s_flag = 0
                e_flag = 0
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_mem = e_mem.strip(' \t')
                    e_flag = 1
                    fileappend('\t' + '\t' + e_mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_type <Tag> does not exist! for Attribute -> " + tmp)
            e_flag = 0
            s_flag = 0

            mem_list10 = i.getElementsByTagName('member_at_parent')
            if mem_list10:
                mem = mem_list10[0].childNodes[0].nodeValue
                mem = mem.strip(' \t')
                s_flag = 1
                fileappend('\t' + '\t' + mem + '\n' + '\t' + '},')
                s_flag = 0
            else:
                pass
            e_flag = 0
            s_flag = 0
            mem_list11 = i.getElementsByTagName('member_verify_function')
            if mem_list11:
                mem = mem_list11[0].childNodes[0].nodeValue
                ecl = mem_list11[0].getElementsByTagName('ECL')
                e_mem1 = []
                # <Tag> member_verify_function, will always have only 2 ECL subtags.
                e_flag = 1
                for e in ecl:
                    e_mem1.append(e.childNodes[0].nodeValue.strip(' \t'))
                fileappend('\t' + '\t' + e_mem1[0] + ',' + '\n')
                fileappend('\t' + '\t' + e_mem1[1] + '\t' + '\n' + '\t' + '},')
                e_flag = 0
                s_flag = 0
            else:
                pass

        tail_list = node.getElementsByTagName('tail')
        for t in tail_list:
            tail_value = t.childNodes[0].nodeValue
            if tail_value == None:
                pass
            fileappend('\n') 
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

        getText(eclf, svrf)


def resc_attr(masterf, svrf, eclf):
    """
    resc_attr function - (opens the resc_def file reads them and using minidom 
    filters relevant data to individual lists) 
    """
    from xml.dom import minidom

    global e_flag
    global s_flag

    global ms
    global me

    doc = minidom.parse(masterf)
    nodes = doc.getElementsByTagName('data')

    for node in nodes:
        alist = node.getElementsByTagName('head')
        for a in alist:
            list_svr.append (
                "/*Disclaimer: This is a machine generated file.*/" + '\n')
            list_svr.append(                                                                 
                  "/*For modifying any attribute change corresponding XML file */" + '\n')            
            list_ecl.append(                                                                 
                  "/*Disclaimer: This is a machine generated file.*/" + '\n')                         
            list_ecl.append(                                                                 
                  "/*For modifying any attribute change corresponding XML file */" + '\n')
            blist = a.getElementsByTagName('SVR')
            blist_ecl = a.getElementsByTagName('ECL')
            for s in blist:
                text1 = s.childNodes[0].nodeValue
                list_svr.append(text1)
            for e in blist_ecl:
                text2 = e.childNodes[0].nodeValue
                list_ecl.append(text2)
        at_list = node.getElementsByTagName('attributes')
        for i in at_list:
            attr_list = i.childNodes[0].nodeValue
            flag_name = i.getAttribute('flag')
            macro_name = i.getAttribute('macro')
            s_flag = 0
            e_flag = 0
            ms = 0
            me = 0
            mflg = i.getAttribute('mflag')
            if flag_name == 'SVR':
                s_flag = 1
            if flag_name == 'ECL':
                e_flag = 1
            if flag_name == None:
                e_flag = 0
                s_flag = 0
            if macro_name:
                ms = 1
                me = 1
                for case in switch(mflg):
                    if case('SVR'):
                        ms = 1
                        me = 0
                        break
                    if case('ECL'):
                        me = 1
                        ms = 0
                        break
            if me == 1 and macro_name != None:
                list_ecl.append('\n' + macro_name)
            if ms == 1 and macro_name != None:
                list_svr.append('\n' + macro_name)
            fileappend(attr_list)
            h = None
            s_mem = None
            e_mem = None
            mem_list1 = i.getElementsByTagName('member_name')
            if mem_list1:
                mem = mem_list1[0].childNodes[0].nodeValue
                bot = mem_list1[0].getElementsByTagName('both')
                svr = mem_list1[0].getElementsByTagName('SVR')
                ecl = mem_list1[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + h.strip(' \t') + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_mem = s_mem.strip(' \t')
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + s_mem + ',' + '\n')
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_mem = e_mem.strip(' \t')
                    fileappend(
                        '\n' + '\t' + '{' + '\n' + '\t' + '\t' + e_mem + ',' + '\n')
            else:
                sys.exit(
                    "member_name does not exist!" + i.childNodes[0].nodeValue)
            mem_list2 = i.getElementsByTagName('member_at_decode')
            if mem_list2:
                mem = mem_list2[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_decode <Tag> does not exist! for Attribute -> " + tmp)

            mem_list3 = i.getElementsByTagName('member_at_encode')
            if mem_list3:
                mem = mem_list3[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_encode <Tag> does not exist! for Attribute -> " + tmp)  

            mem_list4 = i.getElementsByTagName('member_at_set')
            if mem_list4:
                mem = mem_list4[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_set <Tag> does not exist! for Attribute -> " + tmp) 

            mem_list5 = i.getElementsByTagName('member_at_comp')
            if mem_list5:
                mem = mem_list5[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_comp <Tag> does not exist! for Attribute -> " + tmp)

            mem_list6 = i.getElementsByTagName('member_at_free')
            if mem_list6:
                mem = mem_list6[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_free <Tag> does not exist! for Attribute -> " + tmp)

            mem_list7 = i.getElementsByTagName('member_at_action')
            if mem_list7:
                mem = mem_list7[0].childNodes[0].nodeValue
                s_flag = 1  # This is not required in ECL files
                if re.search(r'^#', mem):
                    add_comma(mem)
                else:
                    fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_action <Tag> does not exist! for Attribute -> " + tmp) 
            e_flag = 0
            s_flag = 0

            mem_list8 = i.getElementsByTagName('member_at_flags')
            if mem_list8:
                mem = mem_list8[0].childNodes[0].nodeValue
                bot = mem_list8[0].getElementsByTagName('both')
                svr = mem_list8[0].getElementsByTagName('SVR')
                ecl = mem_list8[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    fileappend('\t' + '\t' + h + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_flag = 1
                    if re.search(r'^#', s_mem):
                        add_comma(s_mem)
                    else:
                        fileappend('\t' + '\t' + s_mem + ',' + '\n')
                s_flag = 0
                e_flag = 0
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_flag = 1
                    fileappend('\t' + '\t' + e_mem + ',' + '\n')

            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_flags <Tag> does not exist! for Attribute -> " + tmp)
            e_flag = 0
            s_flag = 0

            mem_list9 = i.getElementsByTagName('member_at_type')
            if mem_list9:
                mem = mem_list9[0].childNodes[0].nodeValue
                bot = mem_list9[0].getElementsByTagName('both')
                svr = mem_list9[0].getElementsByTagName('SVR')
                ecl = mem_list9[0].getElementsByTagName('ECL')
                for b in bot:
                    h = b.childNodes[0].nodeValue
                    fileappend('\t' + '\t' + h + ',' + '\n')
                for s in svr:
                    s_mem = s.childNodes[0].nodeValue
                    s_flag = 1
                    if re.search(r'^#', s_mem):
                        add_comma(s_mem)
                    else:
                        fileappend('\t' + '\t' + s_mem + ',' + '\n')
                e_flag = 0
                s_flag = 0

                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    e_flag = 1
                    fileappend('\t' + '\t' + e_mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_type <Tag> does not exist! for Attribute -> " + tmp) 
            e_flag = 0
            s_flag = 0

            mem_list10 = i.getElementsByTagName('member_at_entlim')
            if mem_list10:
                mem = mem_list10[0].childNodes[0].nodeValue
                s_flag = 1
                fileappend('\t' + '\t' + mem + ',' + '\n')
            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_entlim <Tag> does not exist! for Attribute -> " + tmp)  

            mem_list11 = i.getElementsByTagName('member_at_struct')
            if mem_list11:
                mem = mem_list11[0].childNodes[0].nodeValue
                s_flag = 1
                fileappend('\t' + '\t' + mem + '\n' + '\t' + '},')
                if ms == 1:
                    fileappend('\n' + '#endif' + '\n')

            else:
                if h:
                    tmp = h
                elif s_mem:
                    tmp = s_mem
                elif e_mem:
                    tmp = e_mem
                else:
                    tmp = i.childNodes[0].nodeValue
                sys.exit(
                    "member_at_struct <Tag> does not exist! for Attribute -> " + tmp)
            e_flag = 0
            s_flag = 0

            mem_list12 = i.getElementsByTagName('member_verify_function')
            if mem_list12:
                mem = mem_list12[0].childNodes[0].nodeValue
                ecl = mem_list12[0].getElementsByTagName('ECL')
                for e in ecl:
                    e_mem = e.childNodes[0].nodeValue
                    ecl = mem_list12[0].getElementsByTagName('ECL')
                e_mem1 = []
                # <Tag> member_verify_function, will always have only 2 ECL subtags.
                e_flag = 1
                for e in ecl:
                    e_mem1.append(e.childNodes[0].nodeValue.strip(' \t'))
                fileappend('\t' + '\t' + e_mem1[0] + ',' + '\n')
                fileappend('\t' + '\t' + e_mem1[1] + '\t' + '\n' + '\t' + '},')

                if me == 1:
                    fileappend('\n' + '#endif' + '\n')
                e_flag = 0
                s_flag = 0
            else:
                pass

        tail_list = node.getElementsByTagName('tail')
        for t in tail_list:
            tail_value = t.childNodes[0].nodeValue
            if tail_value == None:
                pass
            fileappend('\n') 
            tail_both = t.getElementsByTagName('both')
            tail_svr = t.getElementsByTagName('SVR')
            tail_ecl = t.getElementsByTagName('ECL')
            for tb in tail_both:
                b = tb.childNodes[0].nodeValue
                list_ecl.append(b)
                list_svr.append(b)
            for ts in tail_svr:
                s = ts.childNodes[0].nodeValue
                list_svr.append(s)
            for te in tail_ecl:
                e = te.childNodes[0].nodeValue
                list_ecl.append(e)

    getText(eclf, svrf)


def main(argv):
    """
    The Main Module starts here-
    Opens files,and calls appropriate functions based on Object values.
    """
    global SVR_FILE
    global ECL_FILE
    global MASTER_FILE
    global ATTRIBUTE_SCRIPT_ARG

    if len(sys.argv) == 2:
        usage()
        sys.exit(1)
    try:
        opts, args = getopt.getopt(
            argv, "m:s:e:a:h", ["master=", "svr=", "ecl=", "attr=", "help"])
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
        elif opt in ("-e", "--ecl"):
            ECL_FILE = arg
        elif opt in ("-a", "--attr"):
            ATTRIBUTE_SCRIPT_ARG = arg
        else:
            print("Invalid Option!")
            sys.exit(1)
#    Error conditions are checked here.

    if MASTER_FILE is None or not os.path.isfile(MASTER_FILE) or not os.path.getsize(MASTER_FILE) > 0:
        print("Master file not found or data is not present in File")
        sys.exit(1)

    if SVR_FILE is None:
        SVR_FILE = "attr_def.c"

    if ECL_FILE is None:
        ECL_FILE = "ecl_attr_def.c"

    if ATTRIBUTE_SCRIPT_ARG is None or not str:
        print("Attribute type is required")
        sys.exit(1)

    try:
        m_file = open(MASTER_FILE)
    except IOError as err:
        print(str(err))
        print('Cannot Open Master File!')
        sys.exit(1)

    try:
        s_file = open(SVR_FILE, 'w')
    except IOError as err:
        print(str(err))
        print('Cannot Open Server File!')
        sys.exit(1)

    try:
        e_file = open(ECL_FILE, 'w')
    except IOError as err:
        print(str(err))
        print('Cannot Open Ecl File!')
        sys.exit(1)

    n = str(ATTRIBUTE_SCRIPT_ARG)

    for case in switch(n):
        if case('job', 'server', 'node', 'queue', 'sched', 'resv'):
            attr(m_file, s_file, e_file)
            break
        if case('resc'):
            resc_attr(m_file, s_file, e_file)
            break
        if case():  # default, could also just omit condition or 'if True'
            print("Invalid Object!")
        # No need to break here, it'll stop anyway

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

