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


import collections
import copy
import datetime
import json
import logging
import os
import random
import re
import string
import sys
import time
from collections import OrderedDict
from distutils.version import LooseVersion

from ptl.lib.pbs_api_to_cli import api_to_cli
from ptl.utils.pbs_dshutils import DshUtils
from ptl.lib.ptl_constants import *

from ptl.lib.ptl_types import (PbsTypeSize, PbsTypeChunk,
                               PbsTypeDuration, PbsAttribute)


class BatchUtils(object):

    """
    Utility class to create/convert/display various PBS
    data structures
    """

    legal = r"\d\w:\+=\[\]~"
    chunks_tag = re.compile(r"(?P<chunk>\([\d\w:\+=\[\]~]\)[\+]?)")
    chunk_tag = re.compile(r"(?P<vnode>[\w\d\[\]]+):" +
                           r"(?P<resources>[\d\w:\+=\[\]~])+\)")

    array_tag = re.compile(r"(?P<jobid>[\d]+)\[(?P<subjobid>[0-9]*)\]*" +
                           r"[.]*[(?P<server>.*)]*")
    subjob_tag = re.compile(r"(?P<jobid>[\d]+)\[(?P<subjobid>[0-9]+)\]*" +
                            r"[.]*[(?P<server>.*)]*")

    pbsobjname_re = re.compile(r"^(?P<tag>[\w\d][\d\w\s]*:?[\s]+)" +
                               r"*(?P<name>[\^\\\w@\.\d\[\]-]+)$")
    pbsobjattrval_re = re.compile(r"""
                            [\s]*(?P<attribute>[\w\d\.-]+)
                            [\s]*=[\s]*
                            (?P<value>.*)
                            [\s]*""",
                                  re.VERBOSE)
    dt_re = r'(?P<dt_from>\d\d/\d\d/\d\d\d\d \d\d:\d\d)' + \
            r'[\s]+' + \
            r'(?P<dt_to>\d\d/\d\d/\d\d\d\d \d\d:\d\d)'
    dt_tag = re.compile(dt_re)
    hms_tag = re.compile(r'(?P<hr>\d\d):(?P<mn>\d\d):(?P<sc>\d\d)')
    lim_tag = re.compile(r"(?P<limtype>[a-z_]+)[\.]*(?P<resource>[\w\d-]*)"
                         r"=[\s]*\[(?P<entity_type>[ugpo]):"
                         r"(?P<entity_name>[\w\d-]+)"
                         r"=(?P<entity_value>[\d\w]+)\][\s]*")

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.du = DshUtils()
        self.platform = self.du.get_platform()

    def list_to_attrl(self, l):
        """
        Convert a list to a PBS attribute list

        :param l: List to be converted
        :type l: List
        :returns: PBS attribute list
        """
        return self.list_to_attropl(l, None)

    def list_to_attropl(self, l, op=SET):
        """
        Convert a list to a PBS attribute operation list

        :param l: List to be converted
        :type l: List
        :returns: PBS attribute operation list
        """
        head = None
        prev = None

        for i in l:
            a = self.str_to_attropl(i, op)
            if prev is None:
                head = a
            else:
                prev.next = a
            prev = a
            if op is not None:
                a.op = op
        return head

    def str_to_attrl(self, s):
        """
        Convert a string to a PBS attribute list

        :param s: String to be converted
        :type s: str
        :returns: PBS attribute list
        """
        return self.str_to_attropl(s, None)

    def str_to_attropl(self, s, op=SET):
        """
        Convert a string to a PBS attribute operation list

        :param s: String to be converted
        :type s: str
        :returns: PBS attribute operation list
        """
        if op is not None:
            a = attropl()
        else:
            a = attrl()
        if '.' in s:
            (attribute, resource) = s.split('.')
            a.name = attribute
            a.resource = resource.strip()
        else:
            a.name = s
        a.value = ''
        a.next = None
        if op:
            a.op = op
        return a

    def dict_to_attrl(self, d={}):
        """
        Convert a dictionary to a PBS attribute list

        :param d: Dictionary to be converted
        :type d: Dictionary
        :returns: PBS attribute list
        """
        return self.dict_to_attropl(d, None)

    def dict_to_attropl(self, d={}, op=SET):
        """
        Convert a dictionary to a PBS attribute operation list

        :param d: Dictionary to be converted
        :type d: Dictionary
        :returns: PBS attribute operation list
        """
        if len(d.keys()) == 0:
            return None

        prev = None
        head = None

        for k, v in d.items():
            if isinstance(v, tuple):
                op = v[0]
                v = v[1]
            if op is not None:
                a = attropl()
            else:
                a = attrl()
            if '.' in k:
                (attribute, resource) = k.split('.')
                a.name = attribute
                a.resource = resource
            else:
                a.name = k
            a.value = str(v)
            if op is not None:
                a.op = op
            a.next = None

            if prev is None:
                head = a
            else:
                prev.next = a
            prev = a
        return head

    def convert_to_attrl(self, attrib):
        """
        Generic call to convert Python type to PBS attribute list

        :param attrib: Attributes to be converted
        :type attrib: List or tuple or dictionary or str
        :returns: PBS attribute list
        """
        return self.convert_to_attropl(attrib, None)

    def convert_to_attropl(self, attrib, cmd=MGR_CMD_SET, op=None):
        """
        Generic call to convert Python type to PBS attribute
        operation list

        :param attrib: Attributes to be converted
        :type attrib: List or tuple or dictionary or str
        :returns: PBS attribute operation list
        """
        if op is None:
            op = self.command_to_op(cmd)

        if isinstance(attrib, (list, tuple)):
            a = self.list_to_attropl(attrib, op)
        elif isinstance(attrib, (dict, OrderedDict)):
            a = self.dict_to_attropl(attrib, op)
        elif isinstance(attrib, str):
            a = self.str_to_attropl(attrib, op)
        else:
            a = None
        return a

    def command_to_op(self, cmd=None):
        """
        Map command to a ``SET`` or ``UNSET`` Operation. An unrecognized
        command will return SET. No command will return None.

        :param cmd: Command to be mapped
        :type cmd: str
        :returns: ``SET`` or ``UNSET`` operation for the command
        """

        if cmd is None:
            return None
        if cmd in (MGR_CMD_SET, MGR_CMD_EXPORT, MGR_CMD_IMPORT):
            return SET
        if cmd == MGR_CMD_UNSET:
            return UNSET
        return SET

    def display_attrl(self, a=None, writer=sys.stdout):
        """
        Display an attribute list using writer, defaults to sys.stdout

        :param a: Attributes
        :type a: List
        :returns: Displays attribute list
        """
        return self.display_attropl(a)

    def display_attropl(self, attropl=None, writer=sys.stdout):
        """
        Display an attribute operation list with writer, defaults to
        sys.stdout

        :param attropl: Attribute operation list
        :type attropl: List
        :returns: Displays an attribute operation list
        """
        attrs = attropl
        while attrs is not None:
            if attrs.resource:
                writer.write('\t' + attrs.name + '.' + attrs.resource + '= ' +
                             attrs.value + '\n')
            else:
                writer.write('\t' + attrs.name + '= ' + attrs.value + '\n')
            attrs = attrs.__next__

    def display_dict(self, d, writer=sys.stdout):
        """
        Display a dictionary using writer, defaults to sys.stdout

        :param d: Dictionary
        :type d: Dictionary
        :returns: Displays a dictionary
        """
        if not d:
            return
        for k, v in d.items():
            writer.write(k + ': ' + v + '\n')

    def batch_status_to_dictlist(self, bs=None, attr_names=None, id=None):
        """
        Convert a batch status to a list of dictionaries.
        version 0.1a6 added this conversion as a typemap(out) as
        part of the swig wrapping itself so there are fewer uses
        for this function.Returns a list of dictionary
        representation of batch status

        :param bs: Batch status
        :param attr_names: Attribute names
        :returns: List of dictionaries
        """
        attr_time = (
            'ctime', 'mtime', 'qtime', 'start', 'end', 'reserve_start',
            'reserve_end', 'estimated.start_time')
        ret = []
        while bs:
            if id is not None and bs.name != id:
                bs = bs.__next__
                continue
            d = {}
            attrs = bs.attribs
            while attrs is not None:
                if attrs.resource:
                    key = attrs.name + '.' + attrs.resource
                else:
                    key = attrs.name
                if attr_names is not None:
                    if key not in attr_names:
                        attrs = attrs.__next__
                        continue
                val = attrs.value
                if attrs.name in attr_time:
                    val = self.convert_time(val)
                # for attributes that may occur multiple times (e.g., max_run)
                # append the value in a comma-separated representation
                if key in d:
                    d[key] = d[key] + ',' + str(val)
                else:
                    d[key] = str(val)
                attrs = attrs.__next__
            if len(d.keys()) > 0:
                ret.append(d)
                d['id'] = bs.name
            bs = bs.__next__
        return ret

    def display_batch_status(self, bs=None, attr_names=None,
                             writer=sys.stdout):
        """
        Display a batch status using writer, defaults to sys.stdout
        :param bs: Batch status
        :param attr_name: Attribute name
        :type attr_name: str
        :returns: Displays batch status
        """
        if bs is None:
            return

        attr_list = self.batch_status_to_dictlist(bs, attr_names)
        self.display_batch_status_as_dictlist(attr_list, writer)

    def display_dictlist(self, dict_list=[], writer=sys.stdout, fmt=None):
        """
        Display a list of dictionaries using writer, defaults to
        sys.stdout

        :param l: The list to display
        :type l: List
        :param writer: The stream on which to write
        :param fmt: An optional formatting string
        :type fmt: str or None
        :returns: Displays list of dictionaries
        """
        self.display_batch_status_as_dictlist(dict_list, writer, fmt)

    def dictlist_to_file(self, dict_list=[], filename=None, mode='w'):
        """
        write a dictlist to file

        :param l: Dictlist
        :type l: List
        :param filename: File to which dictlist need to be written
        :type filename: str
        :param mode: Mode of file
        :type mode: str
        :raises: Exception writing to file
        """
        if filename is None:
            self.logger.error('a filename is required')
            return

        d = os.path.dirname(filename)
        if d != '' and not os.path.isdir(d):
            os.makedirs(d)
        try:
            with open(filename, mode) as f:
                self.display_dictlist(dict_list, f)
        except Exception:
            self.logger.error('error writing to file ' + filename)
            raise

    def batch_status_as_dictlist_to_file(self, dictlist=[], writer=sys.stdout):
        """
        Write a dictlist to file

        :param dictlist: Dictlist
        :type dictlist: List
        :raises: Exception writing to file
        """
        return self.dictlist_to_file(dictlist, writer)

    def file_to_dictlist(self, fpath=None, attribs=None, id=None):
        """
        Convert a file to a batch dictlist format

        :param fpath: File to be converted
        :type fpath: str
        :param attribs: Attributes
        :returns: File converted to a batch dictlist format
        """
        if fpath is None:
            return []

        try:
            with open(fpath, 'r') as f:
                lines = f.readlines()
        except Exception as e:
            self.logger.error('error converting list of dictionaries to ' +
                              'file ' + str(e))
            return []

        return self.convert_to_dictlist(lines, attribs, id=id)

    def file_to_vnodedef(self, fpath=None):
        """
        Convert a file output of pbsnodes -av to a vnode
        definition format

        :param fpath: File to be converted
        :type fpath: str
        :returns: Vnode definition format
        """
        if fpath is None:
            return None
        try:
            with open(fpath, 'r') as f:
                lines = f.readlines()
        except Exception:
            self.logger.error('error converting nodes to vnode def')
            return None

        dl = self.convert_to_dictlist(lines)

        return self.dictlist_to_vnodedef(dl)

    def show(self, obj_list=[], name=None, fmt=None):
        """
        Alias to display_dictlist with sys.stdout as writer

        :param name: if specified only show the object of
                     that name
        :type name: str
        :param fmt: Optional formatting string, uses %n for
                    object name, %a for attributes, for example
                    a format of r'%nE{}nE{}t%aE{}n' will display
                    objects with their name starting on the first
                    column, a new line, and attributes indented by
                    a tab followed by a new line at the end.
        :type fmt: str
        """
        if name:
            i = 0
            for obj in obj_list:
                if obj['id'] == name:
                    obj_list = [obj_list[i]]
                    break
                i += 1
        self.display_dictlist(obj_list, fmt=fmt)

    def get_objtype(self, d={}):
        """
        Get the type of a given object

        :param d: Dictionary
        :type d: Dictionary
        :Returns: Type of the object
        """
        if 'Job_Name' in d:
            return JOB
        elif 'queue_type' in d:
            return QUEUE
        elif 'Reserve_Name' in d:
            return RESV
        elif 'server_state' in d:
            return SERVER
        elif 'Mom' in d:
            return NODE
        elif 'event' in d:
            return HOOK
        elif 'type' in d:
            return RSC
        return None

    def display_batch_status_as_dictlist(self, dict_list=[], writer=sys.stdout,
                                         fmt=None):
        """
        Display a batch status as a list of dictionaries
        using writer, defaults to sys.stdout

        :param dict_list: List
        :type dict_list: List
        :param fmt: - Optional format string
        :type fmt: str or None
        :returns: Displays batch status as a list of dictionaries
        """
        if dict_list is None:
            return

        for d in dict_list:
            self.display_batch_status_as_dict(d, writer, fmt)

    def batch_status_as_dict_to_str(self, d={}, fmt=None):
        """
        Return a string representation of a batch status dictionary

        :param d: Dictionary
        :type d: Dictionary
        :param fmt: Optional format string
        :type fmt: str or None
        :returns: String representation of a batch status dictionary
        """
        objtype = self.get_objtype(d)

        if fmt is not None:
            if '%1' in fmt:
                _d1 = fmt['%1']
            else:
                _d1 = '\n'
            if '%2' in fmt:
                _d2 = fmt['%2']
            else:
                _d2 = '    '
            if '%3' in fmt:
                _d3 = fmt['%3']
            else:
                _d3 = ' = '
            if '%4' in fmt:
                _d4 = fmt['%4']
            else:
                _d4 = '\n'
            if '%5' in fmt:
                _d5 = fmt['%5']
            else:
                _d5 = '\n'
            if '%6' in fmt:
                _d6 = fmt['%6']
            else:
                _d6 = ''
        else:
            _d1 = '\n'
            _d2 = '    '
            _d3 = ' = '
            _d4 = '\n'
            _d5 = '\n'
            _d6 = ''

        if objtype == JOB:
            _n = 'Job Id: ' + d['id'] + _d1
        elif objtype == QUEUE:
            _n = 'Queue: ' + d['id'] + _d1
        elif objtype == RESV:
            _n = 'Name: ' + d['id'] + _d1
        elif objtype == SERVER:
            _n = 'Server: ' + d['id'] + _d1
        elif objtype == RSC:
            _n = 'Resource: ' + d['id'] + _d1
        elif 'id' in d:
            _n = d['id'] + _d1
            del d['id']
        else:
            _n = ''

        _a = []
        for k, v in sorted(d.items()):
            if k == 'id':
                continue
            _a += [_d2 + k + _d3 + str(v)]

        return _n + _d4.join(_a) + _d5 + _d6

    def display_batch_status_as_dict(self, d={}, writer=sys.stdout, fmt=None):
        """
        Display a dictionary representation of a batch status
        using writer, defaults to sys.stdout

        :param d: Dictionary
        :type d: Dictionary
        :param fmt: Optional format string
        :param fmt: str
        :returns: Displays dictionary representation of a batch
                  status
        """
        writer.write(self.batch_status_as_dict_to_str(d, fmt))

    def decode_dictlist(self, dict_list=None, json=True):
        """
        decode a list of dictionaries

        :param dict_list: List of dictionaries
        :type dict_list: List
        :param json: The target of the decode is meant for ``JSON``
                     formatting
        :returns: Decoded list of dictionaries
        """
        if dict_list is None:
            return ''

        _js = []
        for d in dict_list:
            _jdict = {}
            for k, v in d.items():
                if ',' in v:
                    _jdict[k] = v.split(',')
                else:
                    _jdict[k] = PbsAttribute.decode_value(v)
            _js.append(_jdict)
        return _js

    def convert_to_ascii(self, s):
        """
        Convert char sequences within string like ^A, ^B, ... to
        ASCII 0x01, ...

        :param s: string to convert
        :type s: string
        :returns: converted string
        """
        def repl(m):
            c = m.group(1)
            return chr(ord(c) - 64) if "@" < c <= "_" else m.group(0)
        return re.sub(r"\^(.)", repl, s)

    def convert_to_dictlist(self, l, attribs=None, mergelines=True, id=None,
                            obj_type=None):
        """
        Convert a list of records into a dictlist format.

        :param l: array of records to convert
        :type l: List
        :param mergelines: merge qstat broken lines into one
        :param obj_type: The type of object to query, one of the *
                         objects.
        :returns: Record list converted into dictlist format
        """

        if mergelines:
            lines = []
            count = 1
            for i in range(len(l)):
                if l[i].startswith('\t'):
                    _e = len(lines) - 1
                    lines[_e] = lines[_e].strip('\r\n\t') + \
                        l[i].strip('\r\n\t')
                elif (not l[i].startswith(' ') and i > count and
                      l[i - count].startswith('\t')):
                    _e = len(lines) - count
                    lines[_e] = lines[_e] + l[i]
                    if ((i + 1) < len(l) and not
                            l[i + 1].startswith(('\t', ' '))):
                        count += 1
                    else:
                        count = 1
                else:
                    lines.append(l[i])
        else:
            lines = l

        objlist = []
        d = {}

        for l in lines:
            strip_line = l.strip()
            m = self.pbsobjname_re.match(strip_line)
            if m:
                if len(d.keys()) > 1:
                    if id is None or (id is not None and d['id'] == id):
                        objlist.append(d.copy())
                d = {}
                d['id'] = self.convert_to_ascii(m.group('name'))
                _t = m.group('tag')
                if _t == 'Resv ID: ':
                    d[_t.replace(': ', '')] = d['id']
            else:
                m = self.pbsobjattrval_re.match(strip_line)
                if m:
                    attr = m.group('attribute')
                    # Revisit this after having separate VNODE class
                    if (attribs is None or attr.lower() in attribs or
                            attr in attribs or (obj_type == MGR_OBJ_NODE and
                                                attr == 'Mom')):
                        if attr in d:
                            d[attr] = d[attr] + "," + m.group('value')
                        else:
                            d[attr] = m.group('value')
        # add the last element
        if len(d.keys()) > 1:
            if id is None or (id is not None and d['id'] == id):
                objlist.append(d.copy())

        return objlist

    def convert_to_batch(self, l, mergelines=True):
        """
        Convert a list of records into a batch format.

        :param l: array of records to convert
        :type l: List
        :param mergelines: qstat breaks long lines over
                           multiple lines, merge them\
                           to one by default.
        :type mergelines: bool
        :returns: A linked list of batch status
        """

        if mergelines:
            lines = []
            for i in range(len(l)):
                if l[i].startswith('\t'):
                    _e = len(lines) - 1
                    lines[_e] = lines[_e].strip('\r\t') + \
                        l[i].strip('\r\n')
                else:
                    lines.append(l[i])
        else:
            lines = l

        head_bs = None
        prev_bs = None
        prev_attr = None

        for l in lines:
            strip_line = l.strip()
            m = self.pbsobjname_re.match(strip_line)
            if m:
                bs = batch_status()
                bs.name = m.group('name')
                bs.attribs = None
                bs.next = None
                if prev_bs:
                    prev_bs.next = bs
                if head_bs is None:
                    head_bs = bs
                prev_bs = bs
                prev_attr = None
            else:
                m = self.pbsobjattrval_re.match(strip_line)
                if m:
                    attr = attrl()
                    attr.name = m.group('attribute')
                    attr.value = m.group('value')
                    attr.next = None
                    if bs.attribs is None:
                        bs.attribs = attr
                    if prev_attr:
                        prev_attr.next = attr
                    prev_attr = attr

        return head_bs

    def file_to_batch(self, fpath=None):
        """
        Convert a file to batch format

        :param fpath: File to be converted
        :type fpath: str or None
        :returns: File converted into batch format
        """
        if fpath is None:
            return None

        try:
            with open(fpath, 'r') as f:
                lines = f.readlines()
        except Exception:
            self.logger.error('error converting file ' + fpath + ' to batch')
            return None

        return self.convert_to_batch(lines)

    def batch_to_file(self, bs=None, fpath=None):
        """
        Write a batch object to file

        :param bs: Batch status
        :param fpath: File to which batch object is to be written
        :type fpath: str
        """
        if bs is None or fpath is None:
            return

        try:
            with open(fpath, 'w') as f:
                self.display_batch_status(bs, writer=f)
        except Exception:
            self.logger.error('error converting batch status to file')

    def batch_to_vnodedef(self, bs):
        """
        :param bs: Batch status
        :returns: The vnode definition string representation
                  of nodes batch_status
        """
        out = ["$configversion 2\n"]

        while bs is not None:
            attr = bs.attribs
            while attr is not None:
                if attr.name.startswith("resources_available") or \
                        attr.name.startswith("sharing"):
                    out += [bs.name + ": "]
                    out += [attr.name + "=" + attr.value + "\n"]
                attr = attr.__next__
            bs = bs.__next__
        return "".join(out)

    def dictlist_to_vnodedef(self, dl=None):
        """
        :param dl: Dictionary list
        :type dl: List
        :returns: The vnode definition string representation
                  of a dictlist
        """
        if dl is None:
            return ''

        out = ["$configversion 2\n"]

        for node in dl:
            for k, v in node.items():
                if (k.startswith("resources_available") or
                        k.startswith("sharing") or
                        k.startswith("provision_enable") or
                        k.startswith("queue")):
                    out += [node['id'] + ": "]
                    # MoM dislikes empty values reported in vnode defs so
                    # we substitute no value for an actual empty string
                    if not v:
                        v = '""'
                    out += [k + "=" + str(v) + "\n"]

        return "".join(out)

    def objlist_to_dictlist(self, objlist=None):
        """
        Convert a list of PBS/PTL objects ``(e.g. Server/Job...)``
        into a dictionary list representation of the batch status

        :param objlist: List of ``PBS/PTL`` objects
        :type objlist: List
        :returns: Dictionary list representation of the batch status
        """
        if objlist is None:
            return None

        bsdlist = []
        for obj in objlist:
            newobj = self.obj_to_dict(obj)
            bsdlist.append(newobj)
        return bsdlist

    def obj_to_dict(self, obj):
        """
        Convert a PBS/PTL object (e.g. Server/Job...) into a
        dictionary format

        :param obj: ``PBS/PTL`` object
        :returns: Dictionary of ``PBS/PTL`` objects
        """
        newobj = dict(obj.attributes.items())
        newobj[id] = obj.name
        return newobj

    def parse_execvnode(self, s=None):
        """
        Parse an execvnode string into chunk objects

        :param s: Execvnode string
        :type s: str or None
        :returns: Chunk objects for parsed execvnode string
        """
        if s is None:
            return None

        chunks = []
        start = 0
        for c in range(len(s)):
            if s[c] == '(':
                start = c + 1
            if s[c] == ')':
                chunks.append(PbsTypeChunk(chunkstr=s[start:c]).info)
        return chunks

    def anupbs_exechost_numhosts(self, s=None):
        """
        :param s: Exechost string
        :type s: str or None
        """
        n = 0
        if '[' in s:
            eh = re.sub(r'.*\[(.*)\].*', r'\1', s)
            hosts = eh.split(',')
            for hid in hosts:
                elm = hid.split('-')
                if len(elm) == 2:
                    n += int(elm[1]) - int(elm[0]) + 1
                else:
                    n += 1
        else:
            n += 1
        return n

    def parse_exechost(self, s=None):
        """
        Parse an exechost string into a dictionary representation

        :param s: String to be parsed
        :type s: str or None
        :returns: Dictionary format of the exechost string
        """
        if s is None:
            return None

        hosts = []
        hsts = s.split('+')
        for h in hsts:
            hi = {}
            ti = {}
            (host, task) = h.split('/',)
            d = task.split('*')
            if len(d) == 1:
                taskslot = d[0]
                ncpus = 1
            elif len(d) == 2:
                (taskslot, ncpus) = d
            else:
                (taskslot, ncpus) = (0, 1)
            ti['task'] = taskslot
            ti['ncpus'] = ncpus
            hi[host] = ti
            hosts.append(hi)
        return hosts

    def parse_select(self, s=None):
        """
        Parse a ``select/schedselect`` string into a list
        of dictionaries.

        :param s: select/schedselect string
        :type s: str or None
        :returns: List of dictonaries
        """
        if s is None:
            return
        info = []
        chunks = s.split('+')
        for chunk in chunks:
            d = chunk.split(':')
            numchunks = int(d[0])
            resources = {}
            for e in d[1:]:
                k, v = e.split('=')
                resources[k] = v
            for _ in range(numchunks):
                info.append(resources)

        return info

    def convert_time(self, val, fmt='%a %b %d %H:%M:%S %Y'):
        """
        Convert a date time format into number of seconds
        since epoch

        :param val: date time value
        :param fmt: date time format
        :type fmt: str
        :returns: seconds
        """
        # Tweak for NAS format that puts the number of seconds since epoch
        # in between
        if val.split()[0].isdigit():
            val = int(val.split()[0])
        elif not val.isdigit():
            val = time.strptime(val, fmt)
            val = int(time.mktime(val))
        return val

    def convert_duration(self, val):
        """
        Convert HH:MM:SS into number of seconds
        If a number is fed in, that number is returned
        If neither formatted data is fed in, returns 0

        :param val: duration value
        :type val: str
        :raises: Incorrect format error
        :returns: seconds
        """
        if val.isdigit():
            return int(val)

        hhmmss = val.split(':')
        if len(hhmmss) != 3:
            self.logger.error('Incorrect format, expected HH:MM:SS')
            return 0
        return int(hhmmss[0]) * 3600 + int(hhmmss[1]) * 60 + int(hhmmss[2])

    def convert_seconds_to_datetime(self, tm, fmt=None, seconds=True):
        """
        Convert time format to number of seconds since epoch

        :param tm: the time to convert
        :type tm: str
        :param fmt: optional format string. If used, the seconds
                    parameter is ignored.Defaults to ``%Y%m%d%H%M``
        :type fmt: str or None
        :param seconds: if True, convert time with seconds
                        granularity. Defaults to True.
        :type seconds: bool
        :returns: Number of seconds
        """
        if fmt is None:
            fmt = "%Y%m%d%H%M"
            if seconds:
                fmt += ".%S"

        return time.strftime(fmt, time.localtime(int(tm)))

    def convert_stime_to_seconds(self, st):
        """
        Convert a time to seconds, if we fail we return the
        original time

        :param st: Time to be converted
        :type st: str
        :returns: Number of seconds
        """
        try:
            ret = time.mktime(time.strptime(st, '%a %b %d %H:%M:%S %Y'))
        except Exception:
            ret = st
        return ret

    def convert_dedtime(self, dtime):
        """
        Convert dedicated time string of form %m/%d/%Y %H:%M.

        :param dtime: A datetime string, as an entry in the
                      dedicated_time file
        :type dtime: str
        :returns: A tuple of (from,to) of time since epoch
        """
        dtime_from = None
        dtime_to = None

        m = self.dt_tag.match(dtime.strip())
        if m:
            try:
                _f = "%m/%d/%Y %H:%M"
                dtime_from = self.convert_datetime_to_epoch(m.group('dt_from'),
                                                            fmt=_f)
                dtime_to = self.convert_datetime_to_epoch(m.group('dt_to'),
                                                          fmt=_f)
            except Exception:
                self.logger.error('error converting dedicated time')
        return (dtime_from, dtime_to)

    def convert_datetime_to_epoch(self, mdyhms, fmt="%m/%d/%Y %H:%M:%S"):
        """
        Convert the date time to epoch

        :param mdyhms: date time
        :type mdyhms: str
        :param fmt: Format for date time
        :type fmt: str
        :returns: Epoch time
        """
        return int(time.mktime(time.strptime(mdyhms, fmt)))

    def compare_versions(self, v1, v2, op=None):
        """
        Compare v1 to v2 with respect to operation op

        :param v1: If not a looseversion, it gets converted
                   to it
        :param v2: If not a looseversion, it gets converted
                   to it
        :param op: An operation, one of ``LT``, ``LE``, ``EQ``,
                   ``GE``, ``GT``
        :type op: str
        :returns: True or False
        """
        if op is None:
            self.logger.error('missing operator, one of LT,LE,EQ,GE,GT')
            return None

        if v1 is None or v2 is None:
            return False

        if isinstance(v1, str):
            v1 = LooseVersion(v1)
        if isinstance(v2, str):
            v2 = LooseVersion(v2)

        if op == GT:
            if v1 > v2:
                return True
        elif op == GE:
            if v1 >= v2:
                return True
        elif op == EQ:
            if v1 == v2:
                return True
        elif op == LT:
            if v1 < v2:
                return True
        elif op == LE:
            if v1 <= v2:
                return True

        return False

    def convert_arglist(self, attr):
        """
        strip the XML attributes from the argument list attribute

        :param attr: Argument list attributes
        :type attr: List
        :returns: Stripped XML attributes
        """

        xmls = "<jsdl-hpcpa:Argument>"
        xmle = "</jsdl-hpcpa:Argument>"
        nattr = attr.replace(xmls, " ")
        nattr = nattr.replace(xmle, " ")

        return nattr.strip()

    def convert_to_cli(self, attrs, op=None, hostname=None, dflt_conf=True,
                       exclude_attrs=None):
        """
        Convert attributes into their CLI format counterpart. This
        method is far from complete, it grows as needs come by and
        could use a rewrite, especially going along with a rewrite
        of pbs_api_to_cli

        :param attrs: Attributes to convert
        :type attrs: List or str or dictionary
        :param op: The qualifier of the operation being performed,
                   such as ``IFL_SUBMIT``, ``IFL_DELETE``,
                   ``IFL_TERMINUTE``...
        :type op: str or None
        :param hostname: The name of the host on which to operate
        :type hostname: str or None
        :param dflt_conf: Whether we are using the default PBS
                          configuration
        :type dflt_conf: bool
        :param exclude_attrs: Optional list of attributes to not
                              convert
        :type exclude_attrs: List
        :returns: CLI format of attributes
        """
        ret = []

        if op == IFL_SUBMIT:
            executable = arglist = None

        elif op == IFL_DELETE:
            _c = []
            if isinstance(attrs, str):
                attrs = [attrs]

            if isinstance(attrs, list):
                for a in attrs:
                    if 'force' in a:
                        _c.append('-Wforce')
                    if 'deletehist' in a:
                        _c.append('-x')
                    if 'nomail' in a:
                        _c.append('-Wsuppress_email=-1')
            return _c

        elif op == IFL_TERMINATE:
            _c = []
            if attrs is None:
                _c = []
            elif isinstance(attrs, str):
                _c = ['-t', attrs]
            else:
                if ((attrs & SHUT_QUICK) == SHUT_QUICK):
                    _c = ['-t', 'quick']
                if ((attrs & SHUT_IMMEDIATE) == SHUT_IMMEDIATE):
                    _c = ['-t', 'immediate']
                if ((attrs & SHUT_DELAY) == SHUT_DELAY):
                    _c = ['-t', 'delay']
                if ((attrs & SHUT_WHO_SCHED) == SHUT_WHO_SCHED):
                    _c.append('-s')
                if ((attrs & SHUT_WHO_MOM) == SHUT_WHO_MOM):
                    _c.append('-m')
                if ((attrs & SHUT_WHO_SECDRY) == SHUT_WHO_SECDRY):
                    _c.append('-f')
                if ((attrs & SHUT_WHO_IDLESECDRY) == SHUT_WHO_IDLESECDRY):
                    _c.append('-F')
                if ((attrs & SHUT_WHO_SECDONLY) == SHUT_WHO_SECDONLY):
                    _c.append('-i')
            return _c

        elif op == IFL_RALTER:
            if isinstance(attrs, dict):
                if 'extend' in attrs and attrs['extend'] == 'force':
                    ret.append('-Wforce')
                    del attrs['extend']

        if attrs is None or len(attrs) == 0:
            return ret

        # if a list, convert to a dictionary to fall into a single processing
        # of the attributes
        if (isinstance(attrs, list) and len(attrs) > 0 and
                not isinstance(attrs[0], tuple)):
            tmp_attrs = {}
            for each_attr in attrs:
                tmp_attrs[each_attr] = ''
            del attrs
            attrs = tmp_attrs
            del tmp_attrs

        if isinstance(attrs, (dict, OrderedDict)):
            attrs = attrs.items()

        for a, v in attrs:
            # In job name string, use prefix "\" with special charater
            # to read as an ordinary character on
            # cray, craysim, and shasta platform
            if (a == "Job_Name") and (self.platform == 'cray' or
                                      self.platform == 'craysim' or
                                      self.platform == 'shasta'):
                v = v.translate({ord(c): "\\" +
                                 c for c in r"~`!@#$%^&*()[]{};:,/<>?\|="})
            if exclude_attrs is not None and a in exclude_attrs:
                continue

            if op == IFL_SUBMIT:
                if a == ATTR_executable:
                    executable = v
                    continue
                if a == ATTR_Arglist:
                    if v is not None:
                        arglist = self.convert_arglist(v)
                        if len(arglist) == 0:
                            return []
                    continue
            if isinstance(v, list):
                v = ','.join(v)

            # when issuing remote commands, escape spaces in attribute values
            if (((hostname is not None) and
                 (not self.du.is_localhost(hostname))) or
                    (not dflt_conf)):
                if ' ' in str(v):
                    v = '"' + v + '"'

            if '.' in a:
                (attribute, resource) = a.split('.')
                ret.append('-' + api_to_cli[attribute])
                rv = resource
                if v is not None:
                    rv += '=' + str(v)
                ret.append(rv)
            else:
                try:
                    val = api_to_cli[a]
                except KeyError:
                    self.logger.error('error  retrieving key ' + str(a))
                    # for unknown or junk options
                    ret.append(a)
                    if v is not None:
                        ret.append(str(v))
                    continue
                # on a remote job submit append the remote server name
                # to the queue name
                if ((op == IFL_SUBMIT) and (hostname is not None)):
                    if ((not self.du.is_localhost(hostname)) and
                            (val == 'q') and (v is not None) and
                            ('@' not in v) and (v != '')):
                        v += '@' + hostname
                val = '-' + val
                if '=' in val:
                    if v is not None:
                        ret.append(val + str(v))
                    else:
                        ret.append(val)
                else:
                    ret.append(val)
                    if v is not None:
                        ret.append(str(v))

        # Executable and argument list must come last in a job submission
        if ((op == IFL_SUBMIT) and (executable is not None)):
            ret.append('--')
            ret.append(executable)
            if arglist is not None:
                ret.append(arglist)
        return ret

    def filter_batch_status(self, bs, attrib):
        """
        Filter out elements that don't have the attributes requested
        This is needed to adapt to the fact that requesting a
        resource attribute returns all ``'<resource-name>.*'``
        attributes so we need to ensure that the specific resource
        requested is present in the stat'ed object.

        This is needed especially when calling expect with an op=NE
        because we need to filter on objects that have exactly
        the attributes requested

        :param bs: Batch status
        :param attrib: Requested attributes
        :type attrib: str or dictionary
        :returns: Filtered batch status
        """

        if isinstance(attrib, dict):
            keys = attrib.keys()
        elif isinstance(attrib, str):
            keys = attrib.split(',')
        else:
            keys = attrib

        if keys:
            del_indices = []
            for idx in range(len(bs)):
                for k in bs[idx].keys():
                    if '.' not in k:
                        continue
                    if k != 'id' and k not in keys:
                        del bs[idx][k]
                # if no matching resources, remove the object
                if len(bs[idx]) == 1:
                    del_indices.append(idx)

            for i in sorted(del_indices, reverse=True):
                del bs[i]

        return bs

    def convert_attributes_by_op(self, attributes, setattrs=False):
        """
        Convert attributes by operator, i.e. convert an attribute
        of the form

        ``<attr_name><op><value>`` (e.g. resources_available.ncpus>4)

        to

        ``<attr_name>: (<op>, <value>)``
        (e.g. resources_available.ncpus: (GT, 4))

        :param attributes: the attributes to convert
        :type attributes: List
        :param setattrs: if True, set the attributes with no operator
                         as (SET, '')
        :type setattrs: bool
        :returns: Converted attributes by operator
        """
        # the order of operator matters because they are used to search by
        # regex so the longer strings to search must come first
        operators = ('<=', '>=', '!=', '=', '>', '<', '~')
        d = {}
        for attr in attributes:
            found = False
            for op in operators:
                if op in attr:
                    a = attr.split(op)
                    d[a[0]] = (PTL_STR_TO_OP[op], a[1])
                    found = True
                    break
            if not found and setattrs:
                d[attr] = (SET, '')
        return d

    def operator_in_attribute(self, attrib):
        """
        Returns True if an operator string is present in an
        attribute name

        :param attrib: Attribute name
        :type attrib: str
        :returns: True or False
        """
        operators = PTL_STR_TO_OP.keys()
        for a in attrib:
            for op in operators:
                if op in a:
                    return True
        return False

    def list_resources(self, objtype=None, objs=[]):
        """
        Lists the resources

        :param objtype: Type of the object
        :type objtype: str
        :param objs: Object list
        :type objs: List
        :returns: List of resources
        """
        if objtype in (VNODE, NODE, SERVER, QUEUE, SCHED):
            prefix = 'resources_available.'
        elif objtype in (JOB, RESV):
            prefix = 'Resource_List.'
        else:
            return

        resources = []
        for o in objs:
            for a in o.keys():
                if a.startswith(prefix):
                    res = a.replace(prefix, '')
                    if res not in resources:
                        resources.append(res)
        return resources

    def compare(self, obj1, obj2, showdiff=False):
        """
        Compare two objects.

        :param showdiff: whether to print the specific differences,
                         defaults to False
        :type showdiff: bool
        :returns: 0 if objects are identical and non zero otherwise
        """
        if not showdiff:
            ret = cmp(obj1, obj2)
            if ret != 0:
                self.logger.info('objects differ')
            return ret

        if not isinstance(obj1, type(obj2)):
            self.logger.error('objects are of different type')
            return 1

        if isinstance(obj1, list):
            if len(obj1) != len(obj2):
                self.logger.info(
                    'comparing ' + str(
                        obj1) + ' and ' + str(
                        obj2))
                self.logger.info('objects are of different lengths')
                return
            for i in range(len(obj1)):
                self.compare(obj1[i], obj2[i], showdiff=showdiff)
            return

        if isinstance(obj1, dict):
            self.logger.info('comparing ' + str(obj1) + ' and ' + str(obj2))
            onlyobj1 = []
            diffobjs = []
            onlyobj2 = []
            for k1, v1 in obj1.items():
                if k1 not in obj2:
                    onlyobj1.append(k1 + '=' + str(v1))

                if k1 in obj2 and obj2[k1] != v1:
                    diffobjs.append(
                        k1 + '=' + str(v1) + ' vs ' + k1 + '=' + str(obj2[k1]))

            for k2, v2 in obj2.items():
                if k2 not in obj1:
                    onlyobj2.append(k2 + '=' + str(v2))

            if len(onlyobj1) > 0:
                self.logger.info("only in first object: " + " ".join(onlyobj1))
            if len(onlyobj2) > 0:
                self.logger.info(
                    "only in second object: " + " ".join(onlyobj2))
            if len(diffobjs) > 0:
                self.logger.info("diff between objects: " + " ".join(diffobjs))
            if len(onlyobj1) == len(onlyobj2) == len(diffobjs) == 0:
                self.logger.info("objects are identical")
                return 0

            return 1

    def _make_template_formula(self, formula):
        """
        Create a template of the formula

        :param formula: Formula for which template is to be created
        :type formula: str
        :returns: Template
        """
        tformula = []
        skip = False
        for c in formula:
            if not skip and c.isalpha():
                tformula.append('$')
                skip = True
            if c in ('+', '-', '/', ' ', '*', '%'):
                skip = False
            tformula.append(c)
        return "".join(tformula)

    def update_attributes_list(self, obj):
        """
        Updates the attribute list

        :param obj: Objects
        :returns: Updated attribute list
        """
        if not hasattr(obj, 'attributes'):
            return
        if not hasattr(obj, 'Resource_List'):
            setattr(obj, 'Resource_List', {})

        for attr, val in obj.attributes.items():
            if attr.startswith('Resource_List.'):
                (_, resource) = attr.split('.')
                obj.Resource_List[resource] = val

    def parse_fgc_limit(self, limstr=None):
        """
        Parse an ``FGC`` limit entry, of the form:

        ``<limtype>[.<resource>]=[<entity_type>:<entity_name>
        =<entity_value>]``

        :param limstr: FGC limit string
        :type limstr: str or None
        :returns: Parsed FGC string in given format
        """
        m = self.lim_tag.match(limstr)
        if m:
            _v = str(PbsAttribute.decode_value(m.group('entity_value')))
            return (m.group('limtype'), m.group('resource'),
                    m.group('entity_type'), m.group('entity_name'), _v)
        return None

    def is_job_array(self, jobid):
        """
        If a job array return True, otherwise return False

        :param jobid: PBS jobid
        :returns: True or False
        """
        if self.array_tag.match(jobid):
            return True
        return False

    def is_subjob(self, jobid):
        """
        If a subjob of a job array, return the subjob id
        otherwise return False

        :param jobid: PBS job id
        :type jobid: str
        :returns: True or False
        """
        m = self.subjob_tag.match(jobid)
        if m:
            return m.group('subjobid')
        return False


class PbsBatchObject(list):

    def __init__(self, bs):
        self.set_batch_status(bs)

    def set_batch_status(self, bs):
        """
        Sets the batch status

        :param bs: Batch status
        """
        if 'id' in bs:
            self.name = bs['id']
        for k, v in bs.items():
            self.append(PbsAttribute(k, v))


class PbsBatchStatus(list):

    """
    Wrapper class for Batch Status object
    Converts a batch status (as dictlist) into a list of
    PbsBatchObjects

    :param bs: Batch status
    :type bs: List or dictionary
    :returns: List of PBS batch objects
    """

    def __init__(self, bs):
        if not isinstance(bs, (list, dict)):
            raise TypeError("Expected a list or dictionary")

        if isinstance(bs, dict):
            self.append(PbsBatchObject(bs))
        else:
            for b in bs:
                self.append(PbsBatchObject(b))

    def __str__(self):
        rv = []
        for l in self.__bs:
            rv += [self.__bu.batch_status_as_dict_to_str(l)]
        return "\n".join(rv)
