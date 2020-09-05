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



import datetime
import os
import re
import sys
import time

from ptl.lib.ptl_batchutils import get_batchutils_obj 


class PbsTypeSize(str):

    """
    Descriptor class for memory as a numeric entity.
    Units can be one of ``b``, ``kb``, ``mb``, ``gb``, ``tb``, ``pt``

    :param unit: The unit type associated to the memory value
    :type unit: str
    :param value: The numeric value of the memory
    :type value: int or None
    :raises: ValueError and TypeError
    """

    def __init__(self, value=None):
        if value is None:
            return

        if len(value) < 2:
            raise ValueError

        if value[-1:] in ('b', 'B') and value[:-1].isdigit():
            self.unit = 'b'
            self.value = int(int(value[:-1]) / 1024)
            return

        # lower() applied to ignore case
        unit = value[-2:].lower()
        self.value = value[:-2]
        if not self.value.isdigit():
            raise ValueError
        if unit == 'kb':
            self.value = int(self.value)
        elif unit == 'mb':
            self.value = int(self.value) * 1024
        elif unit == 'gb':
            self.value = int(self.value) * 1024 * 1024
        elif unit == 'tb':
            self.value = int(self.value) * 1024 * 1024 * 1024
        elif unit == 'pb':
            self.value = int(self.value) * 1024 * 1024 * 1024 * 1024
        else:
            raise TypeError
        self.unit = 'kb'

    def encode(self, value=None, valtype='kb', precision=1):
        """
        Encode numeric memory input in kilobytes to a string, including
        unit

        :param value: The numeric value of memory to encode
        :type value: int or None.
        :param valtype: The unit of the input value, defaults to kb
        :type valtype: str
        :param precision: Precision of the encoded value, defaults to 1
        :type precision: int
        :returns: Encoded memory in kb to string
        """
        if value is None:
            value = self.value

        if valtype == 'b':
            val = value
        elif valtype == 'kb':
            val = value * 1024
        elif valtype == 'mb':
            val = value * 1024 * 1024
        elif valtype == 'gb':
            val = value * 1024 * 1024 * 1024 * 1024
        elif valtype == 'tb':
            val = value * 1024 * 1024 * 1024 * 1024 * 1024
        elif valtype == 'pt':
            val = value * 1024 * 1024 * 1024 * 1024 * 1024 * 1024

        m = (
            (1 << 50, 'pb'),
            (1 << 40, 'tb'),
            (1 << 30, 'gb'),
            (1 << 20, 'mb'),
            (1 << 10, 'kb'),
            (1, 'b')
        )

        for factor, suffix in m:
            if val >= factor:
                break

        return '%.*f%s' % (precision, float(val) / factor, suffix)

    def __cmp__(self, other):
        if self.value < other.value:
            return -1
        if self.value == other.value:
            return 0
        return 1

    def __lt__(self, other):
        if self.value < other.value:
            return True
        return False

    def __le__(self, other):
        if self.value <= other.value:
            return True
        return False

    def __gt__(self, other):
        if self.value > other.value:
            return True
        return False

    def __ge__(self, other):
        if self.value < other.value:
            return True
        return False

    def __eq__(self, other):
        if self.value == other.value:
            return True
        return False

    def __get__(self):
        return self.value

    def __add__(self, other):
        if isinstance(other, int):
            self.value += other
        else:
            self.value += other.value
        return self

    def __mul__(self, other):
        if isinstance(other, int):
            self.value *= other
        else:
            self.value *= other.value
        return self

    def __floordiv__(self, other):
        self.value /= other.value
        return self

    def __sub__(self, other):
        self.value -= other.value
        return self

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return self.encode(valtype=self.unit)


class PbsTypeDuration(str):

    """
    Descriptor class for a duration represented as ``hours``,
    ``minutes``, and ``seconds``,in the form of ``[HH:][MM:]SS``

    :param as_seconds: HH:MM:SS represented in seconds
    :type as_seconds: int
    :param as_str: duration represented in HH:MM:SS
    :type as_str: str
    """

    def __init__(self, val):
        if isinstance(val, str):
            if ':' in val:
                s = val.split(':')
                l = len(s)
                if l > 3:
                    raise ValueError
                hr = mn = sc = 0
                if l >= 2:
                    sc = s[l - 1]
                    mn = s[l - 2]
                    if l == 3:
                        hr = s[0]
                self.duration = int(hr) * 3600 + int(mn) * 60 + int(sc)
            elif val.isdigit():
                self.duration = int(val)
        elif isinstance(val, int) or isinstance(val, float):
            self.duration = val

    def __add__(self, other):
        self.duration += other.duration
        return self

    def __sub__(self, other):
        self.duration -= other.duration
        return self

    def __cmp__(self, other):
        if self.duration < other.duration:
            return -1
        if self.duration == other.duration:
            return 0
        return 1

    def __lt__(self, other):
        if self.duration < other.duration:
            return True
        return False

    def __le__(self, other):
        if self.duration <= other.duration:
            return True
        return False

    def __gt__(self, other):
        if self.duration > other.duration:
            return True
        return False

    def __ge__(self, other):
        if self.duration < other.duration:
            return True
        return False

    def __eq__(self, other):
        if self.duration == other.duration:
            return True
        return False

    def __get__(self):
        return self.as_str

    def __repr__(self):
        return self.__str__()

    def __int__(self):
        return int(self.duration)

    def __str__(self):
        return str(datetime.timedelta(seconds=self.duration))


class PbsTypeArray(list):

    """
    Descriptor class for a PBS array list type, e.g. String array

    :param value: Array value to be passed
    :param sep: Separator for two array elements
    :type sep: str
    :returns: List
    """

    def __init__(self, value=None, sep=','):
        self.separator = sep
        self = list.__init__(self, value.split(sep))

    def __str__(self):
        return self.separator.join(self)


class PbsTypeList(dict):

    """
    Descriptor class for a generic PBS list that are key/value pairs
    delimited

    :param value: List value to be passed
    :param sep: Separator for two key/value pair
    :type sep: str
    :param kvsep: Separator for key and value
    :type kvsep: str
    :returns: Dictionary
    """

    def __init__(self, value=None, sep=',', kvsep='='):
        self.kvsep = kvsep
        self.separator = sep
        d = {}
        as_list = [v.split(kvsep) for v in value.split(sep)]
        if as_list:
            for k, v in as_list:
                d[k] = v
            del as_list
        dict.__init__(self, d)

    def __str__(self):
        s = []
        for k, v in self.items():
            s += [str(k) + self.kvsep + str(v)]
        return self.separator.join(s)


class PbsTypeLicenseCount(PbsTypeList):

    """
    Descriptor class for a PBS license_count attribute.

    It is a specialized list where key/values are ':' delimited, separated
    by a ' ' (space)

    :param value: PBS license_count attribute value
    :returns: Specialized list
    """

    def __init__(self, value=None):
        super(PbsTypeLicenseCount, self).__init__(value, sep=' ', kvsep=':')


class PbsTypeVariableList(PbsTypeList):

    """
    Descriptor class for a PBS Variable_List attribute

    It is a specialized list where key/values are '=' delimited, separated
    by a ',' (space)

    :param value: PBS Variable_List attribute value
    :returns: Specialized list
    """

    def __init__(self, value=None):
        super(PbsTypeVariableList, self).__init__(value, sep=',', kvsep='=')


class PbsTypeSelect(list):

    """
    Descriptor class for PBS select/schedselect specification.
    Select is of the form:

    ``<select> ::= <m>":"<chunk> | <select>"+"<select>``

    ``<m> ::= <digit> | <digit><m>``

    ``<chunk> ::= <resc_name>":"<resc_value> | <chunk>":"<chunk>``

    ``<m>`` is a multiplying factor for each chunk requested

    ``<chunk>`` are resource key/value pairs

    The type populates a list of single chunk of resource
    ``key/value`` pairs, the list can be walked by iterating over
    the type itself.

    :param num_chunks: The total number of chunks in the select
    :type num_chunk: int
    :param resources: A dictionary of all resource counts in the select
    :type resources: Dictionary
    """

    def __init__(self, s=None):
        if s is not None:
            self._as_str = s
            self.resources = {}
            self.num_chunks = 0
            nc = s.split('+')
            for chunk in nc:
                self._parse_chunk(chunk)

    def _parse_chunk(self, chunk):
        d = chunk.split(':')
        # number of chunks
        _num_chunks = int(d[0])
        self.num_chunks += _num_chunks
        r = {}
        for e in d[1:]:
            k, v = e.split('=')
            r[k] = v
            if 'mem' in k:
                try:
                    v = PbsTypeSize(v).value
                except:
                    # failed so we guessed wrong on the type
                    pass
            if isinstance(v, int) or v.isdigit():
                if k not in self.resources:
                    self.resources[k] = _num_chunks * int(v)
                else:
                    self.resources[k] += _num_chunks * int(v)
            else:
                if k not in self.resources:
                    self.resources[k] = v
                else:
                    self.resources[k] = [self.resources[k], v]

        # explicitly expose the multiplying factor
        for _ in range(_num_chunks):
            self.append(r)

    def __add__(self, chunk=None):
        if chunk is None:
            return self
        self._parse_chunk(chunk)
        self._as_str = self._as_str + "+" + chunk
        return self

    def __repr__(self):
        return str(self)

    def __str__(self):
        return self._as_str


class PbsTypeChunk(dict):

    """
    Descriptor class for a PBS chunk associated to a
    ``PbsTypeExecVnode``.This type of chunk corresponds to
    a node solution to a resource request,not to the select
    specification.

    ``chunk ::= <subchk> | <chunk>"+"<chunk>``

    ``subchk ::= <node>":"<resource>``

    ``resource ::= <key>":"<val> | <resource>":"<resource>``

    A chunk expresses a solution to a specific select-chunk
    request. If multiple chunks are needed to solve a single
    select-chunk, e.g., on a shared memory system, the chunk
    will be extended into virtual chunk,vchunk.

    :param vnode: the vnode name corresponding to the chunk
    :type vnode: str or None
    :param resources: the key value pair of resources in
                      dictionary form
    :type resources: Dictionary or None
    :param vchunk: a list of virtual chunks needed to solve
                   the select-chunk, vchunk is only set if more
                   than one vchunk are required to solve the
                   select-chunk
    :type vchunk: list
    """

    def __init__(self, vnode=None, resources=None, chunkstr=None):
        self.vnode = vnode
        if resources is not None:
            self.resources = resources
        else:
            self.resources = {}
        self.vchunk = []
        self.as_str = chunkstr
        self.__parse_chunk(chunkstr)

    def __parse_chunk(self, chunkstr=None):
        if chunkstr is None:
            return

        vchunks = chunkstr.split('+')
        if len(vchunks) == 1:
            entities = chunkstr.split(':')
            self.vnode = entities[0]
            if len(entities) > 1:
                for e in entities[1:]:
                    (r, v) = e.split('=')
                    self.resources[r] = v
            self[self.vnode] = self.resources
        else:
            for sc in vchunks:
                chk = PbsTypeChunk(chunkstr=sc)
                self.vchunk.append(chk)
                self[chk.vnode] = chk.resources

    def add(self, vnode, resources):
        """
        Add a chunk specificiation. If a chunk is already
        defined, add the chunk as a vchunk.

        :param vnode: The vnode to add
        :type vnode: str
        :param resources: The resources associated to the
                          vnode
        :type resources: str
        :returns: Added chunk specification
        """
        if self.vnode == vnode:
            self.resources = {**self.resources, **resources}
            return self
        elif len(self.vchunk) != 0:
            for chk in self.vchunk:
                if chk.vnode == vnode:
                    chk.resources = {**self.resources, **resources}
                    return self
        chk = PbsTypeChunk(vnode, resources)
        self.vchunk.append(chk)
        return self

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        _s = ["("]
        _s += [self.vnode, ":"]
        for resc_k, resc_v in self.resources.items():
            _s += [resc_k, "=", str(resc_v)]
        if self.vchunk:
            for _v in self.vchunk:
                _s += ["+", _v.vnode, ":"]
                for resc_k, resc_v in _v.resources.items():
                    _s += [resc_k, "=", str(resc_v)]
        _s += [")"]
        return "".join(_s)


class PbsTypeExecVnode(list):

    """
    Execvnode representation, expressed as a list of
    PbsTypeChunk

    :param vchunk: List of virtual chunks, only set when
                   more than one vnode is allocated to a
                   host satisfy a chunk requested
    :type vchunk: List
    :param num_chunks: The number of chunks satisfied by
                       this execvnode
    :type num_chunks: int
    :param vnodes: List of vnode names allocated to the execvnode
    :type vnodes: List
    :param resource: method to return the amount of a named
                     resource satisfied by this execvnode
    """

    def __init__(self, s=None):
        if s is None:
            return None

        self._as_str = s
        start = 0
        self.num_chunks = 0
        for c in range(len(s)):
            # must split on '+' between parens because '+' can occur within
            # paren for complex specs
            if s[c] == '(':
                start = c + 1
            if s[c] == ')':
                self.append(PbsTypeChunk(chunkstr=s[start:c]))
                self.num_chunks += 1

    def resource(self, name=None):
        """
        :param name: Name of the resource
        :type name: str or None
        """
        if name is None:
            return None
        _total = 0
        for _c in self:
            if _c.vchunk:
                for _v in _c.vchunk:
                    if name in _v.resources:
                        _total += int(_v.resources[name])
            if name in _c.resources:
                if name in _c.resources:
                    _total += int(_c.resources[name])
        return _total

    @property
    def vnodes(self):
        vnodes = []
        for e in self:
            vnodes += [e.vnode]
            if e.vchunk:
                vnodes += [n.vnode for n in e.vchunk]

        return list(set(vnodes))

    def _str__(self):
        return self._as_str
        # below would be to verify that the converted type maps back correctly
        _s = []
        for _c in self:
            _s += [str(_c)]
        return "+".join(_s)


class PbsTypeExecHost(str):

    """
    Descriptor class for exec_host attribute

    :param hosts: List of hosts in the exec_host. Each entry is
                  a host info dictionary that maps the number of
                  cpus and its task number
    :type hosts: List
    """

    def __init__(self, s=None):
        if s is None:
            return None

        self._as_str = s

        self.hosts = []
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
            self.hosts.append(hi)

    def __repr__(self):
        return str(self.hosts)

    def __str__(self):
        return self._as_str


class PbsTypeJobId(str):

    """
    Descriptor class for a Job identifier

    :param id: The numeric portion of a job identifier
    :type id: int
    :param server_name: The pbs server name
    :type server_name: str
    :param server_shortname: The first portion of a FQDN server
                             name
    :type server_shortname: str
    """

    def __init__(self, value=None):
        if value is None:
            return

        self.value = value

        r = value.split('.', 1)
        if len(r) != 2:
            return

        self.id = int(r[0])
        self.server_name = r[1]
        self.server_shortname = r[1].split('.', 1)[0]

    def __str__(self):
        return str(self.value)





class PbsTypeFGCLimit(object):

    """
    FGC limit entry, of the form:

    ``<limtype>[.<resource>]=\[<entity_type>:<entity_name>=
    <entity_value>\]``

    :param attr: FGC limit attribute
    :type attr: str
    :param value: Value of attribute
    :type value: int
    :returns: FGC limit entry of given format
    """

    fgc_attr_pat = re.compile(r"(?P<ltype>[a-z_]+)[\.]*(?P<resource>[\w\d-]*)")
    fgc_val_pat = re.compile(r"[\s]*\[(?P<etype>[ugpo]):(?P<ename>[\w\d-]+)"
                             r"=(?P<eval>[\d]+)\][\s]*")
    utils = get_batchutils_obj

    def __init__(self, attr, val):

        self.attr = attr
        self.val = val

        a = self.fgc_attr_pat.match(attr)
        if a:
            self.limit_type = a.group('ltype')
            self.resource_name = a.group('resource')
        else:
            self.limit_type = None
            self.resource_name = None

        v = self.fgc_val_pat.match(val)
        if v:
            self.lim_value = self.utils.decode_value(v.group('eval'))
            self.entity_type = v.group('etype')
            self.entity_name = v.group('ename')
        else:
            self.lim_value = None
            self.entity_type = None
            self.entity_name = None

    def __val__(self):
        return ('[' + str(self.entity_type) + ':' +
                str(self.entity_name) + '=' + str(self.lim_value) + ']')

    def __str__(self):
        return (self.attr + ' = ' + self.__val__())


class PbsTypeAttribute(dict):

    """
    Experimental. This is a placeholder object that will be used
    in the future to map attribute information and circumvent
    the error-pron dynamic type detection that is currently done
    using ``decode_value()``
    """

    def __getitem__(self, name):
        return get_batchutils_obj.decode_value(super(PbsTypeAttribute,
                                               self).__getitem__(name))
