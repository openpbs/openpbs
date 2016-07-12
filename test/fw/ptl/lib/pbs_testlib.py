# coding: utf-8

# Copyright (C) 1994-2016 Altair Engineering, Inc.
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
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License along 
# with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# Commercial License Information: 
#
# The PBS Pro software is licensed under the terms of the GNU Affero General 
# Public License agreement ("AGPL"), except where a separate commercial license 
# agreement for PBS Pro version 14 or later has been executed in writing with Altair.
# 
# Altair’s dual-license business model allows companies, individuals, and 
# organizations to create proprietary derivative works of PBS Pro and distribute 
# them - whether embedded or bundled with other software - under a commercial 
# license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™", 
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
# trademark licensing policies.

"""
    PTL: PbsTestLab, PBS Pro unit testing and benchmarking framework

    Author: Vincent Matossian

    Core features include capabilities to programmatically:

    Interface to the PBS Server through IFL API or CLI

    Define a Cluster Configuration (policies and resources)

    Generate a workload

    Verify that environment and configuration are as expected

    Query objects and expect specific values to be set
"""

import sys
import os
import socket
import pwd
import grp
import logging
import time
import re
import random
import string
import tempfile
import cPickle
import copy
import datetime
import traceback
import threading
from operator import itemgetter
from collections import OrderedDict
from distutils.version import LooseVersion

try:
    import psycopg2
    PSYCOPG = True
except:
    PSYCOPG = False

try:
    from ptl.lib.pbs_ifl import *
    API_OK = True
except:
    try:
        from ptl.lib.pbs_ifl_mock import *
    except:
        sys.stderr.write("failed to import pbs_ifl, run pbs_swigify " +
                         "to make it\n")
        raise ImportError
    API_OK = False

from ptl.lib.pbs_api_to_cli import api_to_cli
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_procutils import ProcUtils
from ptl.utils.pbs_cliutils import CliUtils
from ptl.utils.pbs_fileutils import FileUtils, FILE_TAIL

# suppress logging exceptions
logging.raiseExceptions = False

# Various mappings and aliases

MGR_OBJ_VNODE = MGR_OBJ_NODE

VNODE = MGR_OBJ_VNODE
NODE = MGR_OBJ_NODE
HOST = MGR_OBJ_HOST
JOB = MGR_OBJ_JOB
RESV = MGR_OBJ_RESV
SERVER = MGR_OBJ_SERVER
QUEUE = MGR_OBJ_QUEUE
SCHED = MGR_OBJ_SCHED
HOOK = MGR_OBJ_HOOK
RSC = MGR_OBJ_RSC
PBS_HOOK = MGR_OBJ_PBS_HOOK

# the order of these symbols matters, see pbs_ifl.h
(SET, UNSET, INCR, DECR, EQ, NE, GE, GT,
 LE, LT, MATCH, MATCH_RE, NOT, DFLT) = range(14)

(PTL_OR, PTL_AND) = [0, 1]

(IFL_SUBMIT, IFL_SELECT, IFL_TERMINATE, IFL_ALTER,
 IFL_MSG, IFL_DELETE) = [0, 1, 2, 3, 4, 5]

(PTL_API, PTL_CLI) = ['api', 'cli']

(PTL_COUNTER, PTL_FILTER) = [0, 1]

PTL_STR_TO_OP = {
    '<': LT,
    '<=': LE,
    '=': EQ,
    '>=': GE,
    '>': GT,
    '!=': NE,
    ' set ': SET,
    ' unset ': UNSET,
    ' match ': MATCH,
    '~': MATCH_RE,
    '!': NOT
}

PTL_OP_TO_STR = {
    LT: '<',
    LE: '<=',
    EQ: '=',
    GE: '>=',
    GT: '>',
    SET: ' set ',
    NE: '!=',
    UNSET: ' unset ',
    MATCH: ' match ',
    MATCH_RE: '~',
    NOT: 'is not'
}

PTL_ATTROP_TO_STR = {PTL_AND: '&&', PTL_OR: '||'}

(RESOURCES_AVAILABLE, RESOURCES_TOTAL) = [0, 1]

EXPECT_MAP = {
    UNSET: 'Unset',
    SET: 'Set',
    EQ: 'Equal',
    NE: 'Not Equal',
    LT: 'Less Than',
    GT: 'Greater Than',
    LE: 'Less Equal Than',
    GE: 'Greater Equal Than',
    MATCH_RE: 'Matches regexp',
    MATCH: 'Matches',
    NOT: 'Not'
}

PBS_CMD_MAP = {
    MGR_CMD_CREATE: 'create',
    MGR_CMD_SET: 'set',
    MGR_CMD_DELETE: 'delete',
    MGR_CMD_UNSET: 'unset',
    MGR_CMD_IMPORT: 'import',
    MGR_CMD_EXPORT: 'export',
    MGR_CMD_LIST: 'list',
}

PBS_CMD_TO_OP = {
    MGR_CMD_SET: SET,
    MGR_CMD_UNSET: UNSET,
    MGR_CMD_DELETE: UNSET,
    MGR_CMD_CREATE: SET,
}

PBS_OBJ_MAP = {
    MGR_OBJ_NONE: 'none',
    SERVER: 'server',
    QUEUE: 'queue',
    JOB: 'job',
    NODE: 'node',
    RESV: 'reservation',
    RSC: 'resource',
    SCHED: 'sched',
    HOST: 'host',
    HOOK: 'hook',
    VNODE: 'node',
    PBS_HOOK: 'pbshook'
}

PTL_TRUE = ('1', 'true', 't', 'yes', 'y', 'enable', 'enabled', 'True', True)
PTL_FALSE = ('0', 'false', 'f', 'no', 'n', 'disable', 'disabled', 'False',
             False)
PTL_NONE = ('None', None)
PTL_FORMULA = '__formula__'
PTL_NOARG = '__noarg__'
PTL_ALL = '__ALL__'

CMD_ERROR_MAP = {
    'alterjob': 'PbsAlterError',
    'holdjob': 'PbsHoldError',
    'sigjob': 'PbsSignalError',
    'msgjob': 'PbsMessageError',
    'rlsjob': 'PbsReleaseError',
    'rerunjob': 'PbsRerunError',
    'orderjob': 'PbsOrderError',
    'runjob': 'PbsRunError',
    'movejob': 'PbsMoveError',
    'delete': 'PbsDeleteError',
    'deljob': 'PbsDeljobError',
    'delresv': 'PbsDelresvError',
    'status': 'PbsStatusError',
    'manager': 'PbsManagerError',
    'submit': 'PbsSubmitError',
    'terminate': 'PbsQtermError'
}


class PtlConfig(object):

    """
    Holds configuration options
    The options can be stored in a file as well as in the OS environment
    variables.
    When set, the environment variables will override definitions in the file.
    By default, on Unix like systems, the file read is /etc/ptl.conf, the
    environment variable PTL_CONF_FILE can be used to set the path to the
    file to read.

    The format of the file is a series of <key> = <value> properties.
    A line that starts with a '#' is ignored and can be used for comments
    """
    logger = logging.getLogger(__name__)

    def __init__(self, conf=None):
        self.options = {
            'PTL_SUDO_CMD': 'sudo -H',
            'PTL_RSH_CMD': 'ssh',
            'PTL_CP_CMD': 'scp -p',
            'PTL_EXPECT_MAX_ATTEMPTS': 60,
            'PTL_EXPECT_INTERVAL': 0.5,
            'PTL_UPDATE_ATTRIBUTES': True,
        }
        self.handlers = {
            'PTL_SUDO_CMD': DshUtils.set_sudo_cmd,
            'PTL_RSH_CMD': DshUtils.set_rsh_cmd,
            'PTL_CP_CMD': DshUtils.set_copy_cmd,
            'PTL_EXPECT_MAX_ATTEMPTS': Server.set_expect_max_attempts,
            'PTL_EXPECT_INTERVAL': Server.set_expect_interval,
            'PTL_UPDATE_ATTRIBUTES': Server.set_update_attributes
        }
        if conf is None:
            conf = os.environ.get('PTL_CONF_FILE', '/etc/ptl.conf')
        try:
            lines = open(conf).readlines()
        except IOError:
            lines = []
        for line in lines:
            line = line.strip()
            if (line.startswith('#') or (line == '')):
                continue
            try:
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip()
                self.options[k] = v
            except:
                self.logger.error('Error parsing line ' + line)
        for k, v in self.options.items():
            if k in os.environ:
                v = os.environ[k]
            else:
                os.environ[k] = str(v)
            if k in self.handlers:
                self.handlers[k](v)


class PtlException(Exception):

    """
    Generic errors raised by PTL operations.
    Sets a return value, a return code, and a message
    A post function and associated positional and named arguments are available
    to perform any necessary cleanup.
    """

    def __init__(self, rv=None, rc=None, msg=None, post=None, *args, **kwargs):
        self.rv = rv
        self.rc = rc
        self.msg = msg
        if post is not None:
            post(*args, **kwargs)

    def __str__(self):
        return ('rc=' + str(self.rc) + ', rv=' + str(self.rv) +
                ', msg=' + str(self.msg))

    def __repr__(self):
        return (self.__class__.__name__ + '(rc=' + str(self.rc) + ', rv=' +
                str(self.rv) + ', msg=' + str(self.msg) + ')')


class PbsServiceError(PtlException):
    pass


class PbsConnectError(PtlException):
    pass


class PbsStatusError(PtlException):
    pass


class PbsSubmitError(PtlException):
    pass


class PbsManagerError(PtlException):
    pass


class PbsDeljobError(PtlException):
    pass


class PbsDelresvError(PtlException):
    pass


class PbsDeleteError(PtlException):
    pass


class PbsRunError(PtlException):
    pass


class PbsSignalError(PtlException):
    pass


class PbsMessageError(PtlException):
    pass


class PbsHoldError(PtlException):
    pass


class PbsReleaseError(PtlException):
    pass


class PbsOrderError(PtlException):
    pass


class PbsRerunError(PtlException):
    pass


class PbsMoveError(PtlException):
    pass


class PbsAlterError(PtlException):
    pass


class PbsResourceError(PtlException):
    pass


class PbsSelectError(PtlException):
    pass


class PbsSchedConfigError(PtlException):
    pass


class PbsMomConfigError(PtlException):
    pass


class PbsFairshareError(PtlException):
    pass


class PbsQdisableError(PtlException):
    pass


class PbsQenableError(PtlException):
    pass


class PbsQstartError(PtlException):
    pass


class PbsQstopError(PtlException):
    pass


class PtlExpectError(PtlException):
    pass

class PbsInitServicesError(PtlException):
    pass

class PbsQtermError(PtlException):
    pass

class PbsTypeSize(str):

    """
    Descriptor class for memory as a numeric entity.
    Units can be one of b, kb, mb, gb, tb, pt

    Attributes:

    unit - The unit type associated to the memory value

    value - The numeric value of the memory
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
        Encode numeric memory input in kilobytes to a string, including unit

        value - the numeric value of memory to encode

        valtype - the unit of the input value, defaults to kb

        precision - precision of the encoded value, defaults to 1
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
    Descriptor class for a duration represented as hours, minutes, and seconds,
    in the form of [HH:][MM:]SS

    Attributes:

    as_seconds - HH:MM:SS represented in seconds

    as_str - duration represented in HH:MM:SS
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
    """

    def __init__(self, value=None, sep=','):
        self.separator = sep
        self = list.__init__(self, value.split(sep))

    def __str__(self):
        return self.separator.join(self)


class PbsTypeList(dict):

    """
    Descriptor class for a generic PBS list that are key/value pairs delimited
    """

    def __init__(self, value=None, sep=',', kvsep='='):
        self.kvsep = kvsep
        self.separator = sep
        d = {}
        as_list = map(lambda v: v.split(kvsep), value.split(sep))
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
    """

    def __init__(self, value=None):
        super(PbsTypeLicenseCount, self).__init__(value, sep=' ', kvsep=':')


class PbsTypeVariableList(PbsTypeList):

    """
    Descriptor class for a PBS Variable_List attribute

    It is a specialized list where key/values are '=' delimited, separated
    by a ',' (space)
    """

    def __init__(self, value=None):
        super(PbsTypeVariableList, self).__init__(value, sep=',', kvsep='=')


class PbsTypeSelect(list):

    """
    Descriptor class for PBS select/schedselect specification.
    Select is of the form:

    <select> ::= <m>":"<chunk> | <select>"+"<select>

    <m> ::= <digit> | <digit><m>

    <chunk> ::= <resc_name>":"<resc_value> | <chunk>":"<chunk>

    <m> is a multiplying factor for each chunk requested

    <chunk> are resource key/value pairs

    The type populates a list of single chunk of resource key/value pairs,
    the list can be walked by iterating over the type itself.

    Attributes:

    num_chunks - The total number of chunks in the select

    resources - A dictionary of all resource counts in the select
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
    Descriptor class for a PBS chunk associated to a PbsTypeExecVnode.
    This type of chunk corresponds to a node solution to a resource request,
    not to the select specification.

    chunk ::= <subchk> | <chunk>"+"<chunk>

    subchk ::= <node>":"<resource>

    resource ::= <key>":"<val> | <resource>":"<resource>

    A chunk expresses a solution to a specific select-chunk request. If
    multiple chunks are needed to solve a single select-chunk, e.g., on a
    shared memory system, the chunk will be extended into virtual chunk,
    vchunk.

    Attributes:

    vnode - the vnode name corresponding to the chunk

    resources - the key:value pair of resources in dictionary form

    vchunk - a list of virtual chunks needed to solve the select-chunk, vchunk
    is only set if more than one vchunk are required to solve the select-chunk
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
        Add a chunk specificiation. If a chunk is already defined, add the
        chunk as a vchunk.

        vnode - The vnode to add

        resources - The resources associated to the vnode
        """
        if self.vnode == vnode:
            self.resources = dict(self.resources.items() + resources.items())
            return self
        elif len(self.vchunk) != 0:
            for chk in self.vchunk:
                if chk.vnode == vnode:
                    chk.resources = dict(self.resources.items() +
                                         resources.items())
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
    Execvnode representation, expressed as a list of PbsTypeChunk

    Attributes:

    vchunk - List of virtual chunks, only set when more than one vnode
    is allocated to a host satisfy a chunk requested

    num_chunks - The number of chunks satisfied by this execvnode

    vnodes - List of vnode names allocated to the execvnode

    resource - method to return the amount of a named resource satisfied by
    this execvnode
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
                vnodes += map(lambda n: n.vnode, e.vchunk)

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

    Attributes:

    hosts - List of hosts in the exec_host. Each entry is a host info
    dictionary that maps the number of cpus and its task number
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

    Attributes:

    id - The numeric portion of a job identifier

    server_name - The pbs server name

    server_shortname - The first portion of a FQDN server name
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


class PbsUser(object):

    """
    The PbsUser type augments a PBS username to associate it to groups to
    which the user belongs

    name - The user name referenced

    uid - uid of user

    groups - The list of PbsGroup objects the user belongs to
    """

    def __init__(self, name, uid=None, groups=None):
        self.name = name
        if uid is not None:
            self.uid = int(uid)
        else:
            self.uid = None
        self.home = None
        self.gid = None
        self.shell = None
        self.gecos = None

        try:
            _user = pwd.getpwnam(self.name)
            self.uid = _user.pw_uid
            self.home = _user.pw_dir
            self.gid = _user.pw_gid
            self.shell = _user.pw_shell
            self.gecos = _user.pw_gecos
        except:
            pass

        if groups is None:
            self.groups = []
        elif isinstance(groups, list):
            self.groups = groups
        else:
            self.groups = groups.split(",")

        for g in self.groups:
            if isinstance(g, str):
                self.groups.append(PbsGroup(g, users=[self]))
            elif self not in g.users:
                g.users.append(self)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return self.__repr__()

    def __int__(self):
        return int(self.uid)


class PbsGroup(object):

    """
    The PbsGroup type augments a PBS groupname to associate it to users to
    which the group belongs

    name - The group name referenced

    gid - gid of group

    users - The list of PbsUser objects the group belongs to
    """

    def __init__(self, name, gid=None, users=None):
        self.name = name
        if gid is not None:
            self.gid = int(gid)
        else:
            self.gid = None

        try:
            _group = grp.getgrnam(self.name)
            self.gid = _group.gr_gid
        except:
            pass

        if users is None:
            self.users = []
        elif isinstance(users, list):
            self.users = users
        else:
            self.users = users.split(",")

        for u in self.users:
            if isinstance(u, str):
                self.users.append(PbsUser(u, groups=[self]))
            elif self not in u.groups:
                u.groups.append(self)

    def __repr__(self):
        return str(self.name)

    def __str__(self):
        return self.__repr__()

    def __int__(self):
        return int(self.gid)


class BatchUtils(object):

    """
    Utility class to create/convert/display various PBS data structures
    """

    legal = "\d\w:\+=\[\]~"
    chunks_tag = re.compile("(?P<chunk>\([\d\w:\+=\[\]~]\)[\+]?)")
    chunk_tag = re.compile("(?P<vnode>[\w\d\[\]]+):" +
                           "(?P<resources>[\d\w:\+=\[\]~])+\)")

    array_tag = re.compile("(?P<jobid>[\d]+)\[(?P<subjobid>[0-9]*)\]*" +
                           "[.]*[(?P<server>.*)]*")
    subjob_tag = re.compile("(?P<jobid>[\d]+)\[(?P<subjobid>[0-9]+)\]*" +
                            "[.]*[(?P<server>.*)]*")

    pbsobjname_re = re.compile("^([\w\d][\d\w\s]*:?[\s]+)" +
                               "*(?P<name>[\w@\.\d\[\]-]+)$")
    pbsobjattrval_re = re.compile(r"""
                            [\s]*(?P<attribute>[\w\d\.-]+)
                            [\s]*=[\s]*
                            (?P<value>.*)
                            [\s]*""",
                                  re.VERBOSE)
    dt_re = '(?P<dt_from>\d\d/\d\d/\d\d\d\d \d\d:\d\d)' + \
            '[\s]+' + \
            '(?P<dt_to>\d\d/\d\d/\d\d\d\d \d\d:\d\d)'
    dt_tag = re.compile(dt_re)
    hms_tag = re.compile('(?P<hr>\d\d):(?P<mn>\d\d):(?P<sc>\d\d)')
    lim_tag = re.compile("(?P<limtype>[a-z_]+)[\.]*(?P<resource>[\w\d-]*)"
                         "=[\s]*\[(?P<entity_type>[ugpo]):"
                         "(?P<entity_name>[\w\d-]+)"
                         "=(?P<entity_value>[\d\w]+)\][\s]*")

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.du = DshUtils()

    def list_to_attrl(self, l):
        """
        Convert a list to a PBS attribute list
        """
        return self.list_to_attropl(l, None)

    def list_to_attropl(self, l, op=SET):
        """
        Convert a list to a PBS attribute operation list
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
        """
        return self.str_to_attropl(s, None)

    def str_to_attropl(self, s, op=SET):
        """
        Convert a string to a PBS attribute operation list
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
        """
        return self.dict_to_attropl(d, None)

    def dict_to_attropl(self, d={}, op=SET):
        """
        Convert a dictionary to a PBS attribute operation list
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
        """
        return self.convert_to_attropl(attrib, None)

    def convert_to_attropl(self, attrib, cmd=MGR_CMD_SET, op=None):
        """
        Generic call to convert Python type to PBS attribute operation list
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
        Map command to a SET or UNSET Operation. An unrecognized command will
        return SET. No command will return None.
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
        """
        return self.display_attropl(a)

    def display_attropl(self, attropl=None, writer=sys.stdout):
        """
        Display an attribute operation list with writer, defaults to sys.stdout
        """
        attrs = attropl
        while attrs is not None:
            if attrs.resource:
                writer.write('\t' + attrs.name + '.' + attrs.resource + '= ' +
                             attrs.value + '\n')
            else:
                writer.write('\t' + attrs.name + '= ' + attrs.value + '\n')
            attrs = attrs.next

    def display_dict(self, d, writer=sys.stdout):
        """
        Display a dictionary using writer, defaults to sys.stdout
        """
        if not d:
            return
        for k, v in d.items():
            writer.write(k + ': ' + v + '\n')

    def batch_status_to_dictlist(self, bs=None, attr_names=None, id=None):
        """
        Convert a batch status to a list of dictionaries.
        version 0.1a6 added this conversion as a typemap(out) as part of the
        swig wrapping itself so there are fewer uses for this function.
        Returns a list of dictionary representation of batch status
        """
        attr_time = (
            'ctime', 'mtime', 'qtime', 'start', 'end', 'reserve_start',
            'reserve_end', 'estimated.start_time')
        ret = []
        while bs:
            if id is not None and bs.name != id:
                bs = bs.next
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
                        attrs = attrs.next
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
                attrs = attrs.next
            if len(d.keys()) > 0:
                ret.append(d)
                d['id'] = bs.name
            bs = bs.next
        return ret

    def display_batch_status(self, bs=None, attr_names=None,
                             writer=sys.stdout):
        """
        Display a batch status using writer, defaults to sys.stdout
        """
        if bs is None:
            return

        l = self.batch_status_to_dictlist(bs, attr_names)
        self.display_batch_status_as_dictlist(l, writer)

    def display_dictlist(self, l=[], writer=sys.stdout, fmt=None):
        """
        Display a list of dictionaries using writer, defaults to sys.stdout

        l - The list to display

        writer - The stream on which to write

        fmt - An optional formatting string
        """
        self.display_batch_status_as_dictlist(l, writer, fmt)

    def dictlist_to_file(self, l=[], filename=None, mode='w'):
        """
        write a dictlist to file
        """
        if filename is None:
            self.logger.error('a filename is required')
            return

        d = os.path.dirname(filename)
        if d != '' and not os.path.isdir(d):
            os.makedirs(d)
        try:
            f = open(filename, mode)
            self.display_dictlist(l, f)
            f.close()
        except:
            self.logger.error('error writing to file ' + filename)
            raise

    def batch_status_as_dictlist_to_file(self, l=[], writer=sys.stdout):
        """
        Write a dictlist to file
        """
        return self.dictlist_to_file(l, writer)

    def file_to_dictlist(self, file=None, attribs=None, id=None):
        """
        Convert a file to a batch dictlist format
        """
        if file is None:
            return []

        try:
            f = open(file, 'r')
            lines = f.readlines()
            f.close()
        except Exception, e:
            self.logger.error('error converting list of dictionaries to ' +
                              'file ' + str(e))
            return []

        return self.convert_to_dictlist(lines, attribs, id=id)

    def file_to_vnodedef(self, file=None):
        """
        Convert a file output of pbsnodes -av to a vnode definition format
        """
        if file is None:
            return None
        try:
            f = open(file, 'r')
            lines = f.readlines()
            f.close()
        except:
            self.logger.error('error converting nodes to vnode def')
            return None

        dl = self.convert_to_dictlist(lines)

        return self.dictlist_to_vnodedef(dl)

    def show(self, l=[], name=None, fmt=None):
        """
        Alias to display_dictlist with sys.stdout as writer
        name - if specified only show the object of that name

        fmt - Optional formatting string, uses %n for object name, %a for
        attributes, for example a format of '%nE{\}nE{\}t%aE{\}n' will display
        objects with their name starting on the first column, a new line, and
        attributes indented by a tab followed by a new line at the end.
        """
        if name:
            i = 0
            for obj in l:
                if obj['id'] == name:
                    l = [l[i]]
                    break
                i += 1
        self.display_dictlist(l, fmt=fmt)

    def get_objtype(self, d={}):
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

    def display_batch_status_as_dictlist(self, l=[], writer=sys.stdout,
                                         fmt=None):
        """
        Display a batch status as a list of dictionaries using writer, defaults
        to sys.stdout

        fmt - Optional format string
        """
        if l is None:
            return

        for d in l:
            self.display_batch_status_as_dict(d, writer, fmt)

    def batch_status_as_dict_to_str(self, d={}, fmt=None):
        """
        Return a string representation of a batch status dictionary

        fmt - Optional format string
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
        Display a dictionary representation of a batch status using writer,
        defaults to sys.stdout

        fmt - Optional format string
        """
        writer.write(self.batch_status_as_dict_to_str(d, fmt))

    def decode_dictlist(self, l=None, json=True):
        """
        decode a list of dictionaries

        json - The target of the decode is meant for JSON formatting
        """
        if l is None:
            return ''

        _js = []
        for d in l:
            _jdict = {}
            for k, v in d.items():
                if ',' in v:
                    _jdict[k] = v.split(',')
                else:
                    _jdict[k] = self.decode_value(v)
            _js.append(_jdict)
        return _js

    def convert_to_dictlist(self, l, attribs=None, mergelines=True, id=None):
        """
        Convert a list of records into a dictlist format.

        l - array of records to convert

        mergelines - merge qstat broken lines into one
        """

        if mergelines:
            lines = []
            for i in range(len(l)):
                if l[i].startswith('\t'):
                    _e = len(lines) - 1
                    lines[_e] = lines[_e].strip('\r\n\t') + \
                        l[i].strip('\r\n\t')
                else:
                    lines.append(l[i])
        else:
            lines = l

        objlist = []
        d = {}

        for l in lines:
            l = l.strip()
            m = self.pbsobjname_re.match(l)
            if m:
                if len(d.keys()) > 1:
                    if id is None or (id is not None and d['id'] == id):
                        objlist.append(d.copy())
                d = {}
                d['id'] = m.group('name')
            else:
                m = self.pbsobjattrval_re.match(l)
                if m:
                    attr = m.group('attribute')
                    if attribs is None or attr in attribs:
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

        l - array of records to convert

        mergelines - qstat breaks long lines over multiple lines, merge them\
        to one by default.

        Return a linked list of batch status
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
            l = l.strip()
            m = self.pbsobjname_re.match(l)
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
                m = self.pbsobjattrval_re.match(l)
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

    def file_to_batch(self, file=None):
        """
        Convert a file to batch format
        """
        if file is None:
            return None

        try:
            f = open(file, 'r')
            l = f.readlines()
            f.close()
        except:
            self.logger.error('error converting file ' + file + ' to batch')
            return None

        return self.convert_to_batch(l)

    def batch_to_file(self, bs=None, file=None):
        """
        Write a batch object to file
        """
        if bs is None or file is None:
            return

        try:
            f = open(file, 'w')
            self.display_batch_status(bs, writer=f)
            f.close()
        except:
            self.logger.error('error converting batch status to file')

    def batch_to_vnodedef(self, bs):
        """
        Return a vnode definition string representation of nodes batch_status
        """
        out = ["$configversion 2\n"]

        while bs is not None:
            attr = bs.attribs
            while attr is not None:
                if attr.name.startswith("resources_available") or \
                        attr.name.startswith("sharing"):
                    out += [bs.name + ": "]
                    out += [attr.name + "=" + attr.value + "\n"]
                attr = attr.next
            bs = bs.next
        return "".join(out)

    def dictlist_to_vnodedef(self, dl=None):
        """
        Return a vnode definition string representation of a dictlist
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
        Convert a list of PBS/PTL objects (e.g. Server/Job...) into a
        dictionary list representation of the batch status
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
        Convert a PBS/PTL object (e.g. Server/Job...) into a dictionary format
        """
        newobj = dict(obj.attributes.items())
        newobj[id] = obj.name
        return newobj

    def parse_execvnode(self, s=None):
        """
        Parse an execvnode string into chunk objects
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
        Parse a select/schedselect string into a list of dictionaries.
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

    @classmethod
    def isfloat(cls, value):
        """
        returns true if value is a float or a string representation of a float
        returns false otherwise
        """
        if isinstance(value, float):
            return True
        if isinstance(value, str):
            try:
                float(value)
                return True
            except ValueError:
                return False

    @classmethod
    def decode_value(cls, value):
        """
        Decode an attribute/resource value, if a value is made up of digits
        only then return the numeric value of it, if it is made of alphanumeric
        values only, return it as a string, if it is of type size, i.e., with
        a memory unit such as b,kb,mb,gb then return the converted size to
        kb without the unit
        """
        if value is None or callable(value):
            return value

        if isinstance(value, (int, float)):
            return value

        if value.isdigit():
            return int(value)

        if value.isalpha() or value == '':
            return value

        if cls.isfloat(value):
            return float(value)

        if ':' in value:
            try:
                value = int(PbsTypeDuration(value))
            except ValueError:
                pass
            return value

        # TODO revisit:  assume (this could be the wrong type, need a real
        # data model anyway) that the remaining is a memory expression
        try:
            value = PbsTypeSize(value)
            return value.value
        except ValueError:
            pass
        except TypeError:
            # if not then we pass to return the value as is
            pass

        return value

    def convert_time(self, val, fmt='%a %b %d %H:%M:%S %Y'):
        """
        Convert a date time format into number of seconds since epoch
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
        """
        if val.isdigit():
            return int(val)

        hhmmss = val.split(':')
        if len(hhmmss) != 3:
            self.logger.error('Incorrect format, expected HH:MM:SS')
            return 0
        return int(hhmmss[0]) * 3600 + int(hhmmss[1]) * 60 + int(hhmmss[2])

    def convert_seconds_to_resvtime(self, tm, fmt=None, seconds=True):
        """
        Convert time format to number of seconds since epoch

        tm - the time to convert

        fmt - optional format string. If used, the seconds parameter is ignored
        Defaults to %Y%m%d%H%M

        seconds - if True, convert time with seconds granularity. Defaults
        to True.
        """
        if fmt is None:
            fmt = "%Y%m%d%H%M"
            if seconds:
                fmt += ".%S"

        return time.strftime(fmt, time.localtime(int(tm)))

    def convert_stime_to_seconds(self, st):
        " Convert a time to seconds, if we fail we return the original time "
        try:
            ret = time.mktime(time.strptime(st, '%a %b %d %H:%M:%S %Y'))
        except:
            ret = st
        return ret

    def convert_dedtime(self, dtime):
        """
        Convert dedicated time string of form %m/%d/%Y %H:%M.

        dtime - a datetime string, as an entry in the dedicated_time file

        Returns a tuple of (from,to) of time since epoch
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
            except:
                self.logger.error('error converting dedicated time')
        return (dtime_from, dtime_to)

    def convert_datetime_to_epoch(self, mdyhms, fmt="%m/%d/%Y %H:%M:%S"):
        return int(time.mktime(time.strptime(mdyhms, fmt)))

    def compare_versions(self, v1, v2, op=None):
        """
        Compare v1 to v2 with respect to operation op

        v1 - If not a looseversion, it gets converted to it

        v2 - If not a looseversion, it gets converted to it

        op - an operation, one of LT, LE, EQ, GE, GT
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
        """

        xmls = "<jsdl-hpcpa:Argument>"
        xmle = "</jsdl-hpcpa:Argument>"
        nattr = attr.replace(xmls, " ")
        nattr = nattr.replace(xmle, " ")

        return nattr.strip()

    def convert_to_cli(self, attrs, op=None, hostname=None, dflt_conf=True,
                       exclude_attrs=None):
        """
        Convert attributes into their CLI format counterpart. This method
        is far from complete, it grows as needs come by and could use a
        rewrite, especially going along with a rewrite of pbs_api_to_cli

        attrs - Attributes to convert

        op - The qualifier of the operation being performed, such as IFL_SUBMIT
        IFL_DELETE, IFL_TERMINUTE...

        hostname - The name of the host on which to operate

        dflt_conf - Whether we are using the default PBS configuration

        exclude_attrs - Optional list of attributes to not convert
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
                        _c.append('-W')
                        _c.append('force')
                    if 'deletehist' in a:
                        _c.append('-x')
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
        resource attribute returns all '<resource-name>.*' attributes
        so we need to ensure that the specific resource requested is
        present in the stat'ed object.

        This is needed especially when calling expect with an op=NE
        because we need to filter on objects that have exactly
        the attributes requested
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
        Convert attributes by operator, i.e. convert an attribute of the form

        <attr_name><op><value> (e.g. resources_available.ncpus>4)

        to

        <attr_name>: (<op>, <value>) (e.g. resources_available.ncpus: (GT, 4))

        attributes - the attributes to convert

        setattrs - if True, set the attributes with no operator as (SET, '')
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
        " Returns True if an operator string is present in an attribute name "
        operators = PTL_STR_TO_OP.keys()
        for a in attrib:
            for op in operators:
                if op in a:
                    return True
        return False

    def list_resources(self, objtype=None, objs=[]):
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

        Returns 0 if objects are identical and non zero otherwise

        showdiff - whether to print the specific differences, defaults to False
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

    @classmethod
    def random_str(cls, length=1, prefix=''):
        r = [random.choice(string.letters) for _ in range(length)]
        r = ''.join([prefix] + r)
        if hasattr(cls, '__uniq_rstr'):
            while r in cls.__uniq_rstr:
                r = [random.choice(string.letters) for _ in range(length)]
                r = ''.join([prefix] + r)
            cls.__uniq_rstr.append(r)
        else:
            cls.__uniq_rstr = [r]

        return r

    def _make_template_formula(self, formula):
        """
        Create a template of the formula
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
        Parse an FGC limit entry, of the form:

        <limtype>[.<resource>]=\[<entity_type>:<entity_name>=<entity_value>\]
        """
        m = self.lim_tag.match(limstr)
        if m:
            _v = str(self.decode_value(m.group('entity_value')))
            return (m.group('limtype'), m.group('resource'),
                    m.group('entity_type'), m.group('entity_name'), _v)
        return None

    def is_job_array(self, jobid):
        """
        If a job array return True, otherwise return False
        """
        if self.array_tag.match(jobid):
            return True
        return False

    def is_subjob(self, jobid):
        """
        If a subjob of a job array, return the subjob id
        otherwise return False
        """
        m = self.subjob_tag.match(jobid)
        if m:
            return m.group('subjobid')
        return False


class PbsTypeFGCLimit(object):

    """
    FGC limit entry, of the form:

    <limtype>[.<resource>]=\[<entity_type>:<entity_name>=<entity_value>\]

    """

    fgc_attr_pat = re.compile("(?P<ltype>[a-z_]+)[\.]*(?P<resource>[\w\d-]*)")
    fgc_val_pat = re.compile("[\s]*\[(?P<etype>[ugpo]):(?P<ename>[\w\d-]+)"
                             "=(?P<eval>[\d]+)\][\s]*")
    utils = BatchUtils()

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


class PbsBatchStatus(list):

    """
    Wrapper class for Batch Status object
    Converts a batch status (as dictlist) into a list of PbsBatchObjects
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


class PbsBatchObject(list):

    def __init__(self, bs):
        self.set_batch_status(bs)

    def set_batch_status(self, bs):
        if 'id' in bs:
            self.name = bs['id']
        for k, v in bs.items():
            self.append(PbsAttribute(k, v))


class PbsAttribute(object):

    utils = BatchUtils()

    def __init__(self, name=None, value=None):
        self.set_name(name)
        self.set_value(value)

    def set_name(self, name):
        self.name = name
        if name is not None and '.' in name:
            self.is_resource = True
            self.resource_type, self.resource_name = self.name.split('.')
        else:
            self.is_resource = False
            self.resource_type = self.resource_name = None

    def set_value(self, value):
        self.value = value
        if isinstance(value, (int, float)) or str(value).isdigit():
            self.is_consumable = True
        else:
            self.is_consumable = False

    def obfuscate_name(self, a=None):
        if a is not None:
            on = a
        else:
            on = self.utils.random_str(len(self.name))

        self.decoded_name = self.name
        if self.is_resource:
            self.set_name(self.resource_name + '.' + on)

    def obfuscate_value(self, v=None):
        if not self.is_consuable:
            self.decoded_value = self.value
            return

        if v is not None:
            ov = v
        else:
            ov = self.utils.random_str(len(self.value))

        self.decoded_value = self.value
        self.set_value(ov)


class PbsAnonymizer(object):

    """
    Holds and controls anonymizing operations of PBS data
    When a dictionary, the values associated to each key is substituted
    during obfuscation.

    The anonymizer operates on attributes or resources. Resources operate on
    the resource name itself rather than the entire name, for example,
    to obfuscate the values associated to a custom resource "foo" that
    could be set as resources_available.foo resources_default.foo or
    Resource_List.foo, all that needs to be passed in to the function is
    "foo" in the resc_vals list.
    """

    logger = logging.getLogger(__name__)
    utils = BatchUtils()
    du = DshUtils()

    def __init__(self, attr_delete=None, resc_delete=None,
                 attr_key=None, attr_val=None,
                 resc_key=None, resc_val=None):

        # special cases
        self._entity = False
        self.job_sort_formula = None
        self.schedselect = None
        self.select = None

        self.set_attr_delete(attr_delete)
        self.set_resc_delete(resc_delete)
        self.set_attr_key(attr_key)
        self.set_attr_val(attr_val)
        self.set_resc_key(resc_key)
        self.set_resc_val(resc_val)
        self.anonymize = self.anonymize_batch_status

        # global anonymized mapping data
        self.gmap_attr_val = {}
        self.gmap_resc_val = {}
        self.gmap_attr_key = {}
        self.gmap_resc_key = {}

    def _initialize_key_map(self, keys):
        k = {}
        if keys is not None:
            if isinstance(keys, dict):
                return keys
            elif isinstance(keys, list):
                for i in keys:
                    k[i] = None
            elif isinstance(keys, str):
                for i in keys.split(','):
                    k[i] = None
            else:
                self.logger.error('unhandled map type')
                k = {None: None}
        return k

    def _initialize_value_map(self, keys):
        k = {}
        if keys is not None:
            if isinstance(keys, dict):
                return keys
            elif isinstance(keys, list):
                for i in keys:
                    k[i] = {}
            elif isinstance(keys, str):
                for i in keys.split(','):
                    k[i] = {}
            else:
                self.logger.error('unhandled map type')
                k = {None: None}
        return k

    def set_attr_delete(self, ad):
        """
        Name of attributes to delete
        """
        self.attr_delete = self._initialize_value_map(ad)

    def set_resc_delete(self, rd):
        """
        Name of resources to delete
        """
        self.resc_delete = self._initialize_value_map(rd)

    def set_attr_key(self, ak):
        """
        Name of attributes to obfuscate.
        """
        self.attr_key = self._initialize_key_map(ak)

    def set_attr_val(self, av):
        """
        Name of attributes for which to obfuscate the value
        """
        self.attr_val = self._initialize_value_map(av)
        if 'euser' in self.attr_val:
            self._entity = True
        elif 'egroup' in self.attr_val:
            self._entity = True
        elif 'project' in self.attr_val:
            self._entity = True

    def set_resc_key(self, rk):
        """
        Name of resources to obfuscate
        """
        self.resc_key = self._initialize_key_map(rk)

    def set_resc_val(self, rv):
        """
        Name of resources for which to obfuscate the value
        """
        self.resc_val = self._initialize_value_map(rv)

    def set_anon_map_file(self, name):
        """
        Name of file in which to store anonymized map data.
        This file is meant to remain private to a site as it contains the
        sensitive anonymized data.
        """
        self.anon_map_file = name

    def anonymize_resource_group(self, file):
        """
        Anonymize the user and group fields of a resource group file
        """
        anon_rg = []

        try:
            f = open(file)
            lines = f.readlines()
            f.close()
        except:
            self.logger.error("Error processing " + file)
            return None

        for data in lines:
            data = data.strip()
            if data:
                if data[0] == '#':
                    continue

                _d = data.split()
                ug = _d[0]
                if ':' in ug:
                    (euser, egroup) = ug.split(':')
                else:
                    euser = ug
                    egroup = None

                if 'euser' not in self.attr_val:
                    anon_euser = euser
                else:
                    anon_euser = None
                    if 'euser' in self.gmap_attr_val:
                        if euser in self.gmap_attr_val['euser']:
                            anon_euser = self.gmap_attr_val['euser'][euser]
                    else:
                        self.gmap_attr_val['euser'] = {}

                if euser is not None and anon_euser is None:
                    anon_euser = self.utils.random_str(len(euser))
                    self.gmap_attr_val['euser'][euser] = anon_euser

                if 'egroup' not in self.attr_val:
                    anon_egroup = egroup
                else:
                    anon_egroup = None

                    if egroup is not None:
                        if 'egroup' in self.gmap_attr_val:
                            if egroup in self.gmap_attr_val['egroup']:
                                anon_egroup = (self.gmap_attr_val['egroup']
                                               [egroup])
                        else:
                            self.gmap_attr_val['egroup'] = {}

                if egroup is not None and anon_egroup is None:
                    anon_egroup = self.utils.random_str(len(egroup))
                    self.gmap_attr_val['egroup'][egroup] = anon_egroup

                # reconstruct the fairshare info by combining euser and egroup
                out = [anon_euser]
                if anon_egroup is not None:
                    out[0] += ':' + anon_egroup
                # and appending the rest of the original line
                out.append(_d[1])
                if len(_d) > 1:
                    p = _d[2].strip()
                    if ('euser' in self.gmap_attr_val and
                            p in self.gmap_attr_val['euser']):
                        out.append(self.gmap_attr_val['euser'][p])
                    else:
                        out.append(_d[2])
                if len(_d) > 2:
                    out += _d[3:]
                anon_rg.append(" ".join(out))

        return anon_rg

    def anonymize_resource_def(self, resources):
        if not self.resc_key:
            return resources

        for curr_anon_resc, val in self.resc_key.items():
            if curr_anon_resc in resources:
                tmp_resc = copy.copy(resources[curr_anon_resc])
                del resources[curr_anon_resc]
                if val is None:
                    if curr_anon_resc in self.gmap_resc_key:
                        val = self.gmap_resc_key[curr_anon_resc]
                    else:
                        val = self.utils.random_str(len(curr_anon_resc))
                elif curr_anon_resc not in self.gmap_resc_key:
                    self.gmap_resc_key[curr_anon_resc] = val
                tmp_resc.set_name(val)
                resources[val] = tmp_resc
        return resources

    def __anonymize_fgc(self, d, attr, ar, name, val):
        """
        Anonymize an FGC limit value
        """

        m = {'u': 'euser', 'g': 'egroup', 'p': 'project'}

        if ',' in val:
            fgc_lim = val.split(',')
        else:
            fgc_lim = [val]

        nfgc = []
        for lim in fgc_lim:
            _fgc = PbsTypeFGCLimit(attr, lim)
            ename = _fgc.entity_name
            if ename in ('PBS_GENERIC', 'PBS_ALL'):
                nfgc.append(lim)
                continue

            obf_ename = ename
            for etype, nm in m.items():
                if _fgc.entity_type == etype:
                    if nm not in self.gmap_attr_val:
                        if nm in ar and ename in ar[nm]:
                            obf_ename = ar[nm][ename]
                        else:
                            obf_ename = self.utils.random_str(len(ename))
                        self.gmap_attr_val[nm] = {ename: obf_ename}
                    elif ename in self.gmap_attr_val[nm]:
                        if ename in self.gmap_attr_val[nm]:
                            obf_ename = self.gmap_attr_val[nm][ename]
                    break
            _fgc.entity_name = obf_ename
            nfgc.append(_fgc.__val__())

        d[attr] = ",".join(nfgc)

    def __anonymize_attr_val(self, d, attr, ar, name, val):
        """
        Obfuscate an attribute/resource values
        """

        # don't obfuscate default project
        if attr == 'project' and val == '_pbs_project_default':
            return

        nstr = []
        if '.' in attr:
            m = self.gmap_resc_val
        else:
            m = self.gmap_attr_val

        if val in ar[name]:
            nstr.append(ar[name][val])
            if name in self.lmap:
                self.lmap[name][val] = ar[name][val]
            else:
                self.lmap[name] = {val: ar[name][val]}
            if name not in m:
                m[name] = {val: ar[name][val]}
            elif val not in m[name]:
                m[name][val] = ar[name][val]
        else:
            # Obfuscate by randomizing with a value of the same length
            tmp_v = val.split(',')
            for v in tmp_v:
                if v in ar[name]:
                    r = ar[name][v]
                elif name in m and v in m[name]:
                    r = m[name][v]
                else:
                    r = self.utils.random_str(len(v))
                    if not isinstance(ar[name], dict):
                        ar[name] = {}
                    ar[name][v] = r
                self.lmap[name] = {v: r}
                if name not in m:
                    m[name] = {v: r}
                elif v not in m[name]:
                    m[name][v] = r

                nstr.append(r)

        if d is not None:
            d[attr] = ",".join(nstr)

    def __anonymize_attr_key(self, d, attr, ar, name, res):
        """
        Obfuscate an attribute/resource key
        """

        if res is not None:
            m = self.gmap_resc_key
        else:
            m = self.gmap_attr_key

        if not ar[name]:
            if name in m:
                ar[name] = m[name]
            else:
                randstr = self.utils.random_str(len(name))
                ar[name] = randstr
                m[name] = randstr

        if d is not None:
            tmp_val = d[attr]
            del d[attr]

            if res is not None:
                d[res + '.' + ar[name]] = tmp_val
            else:
                d[ar[name]] = tmp_val

        if name not in self.lmap:
            self.lmap[name] = ar[name]

        if name not in m:
            m[name] = ar[name]

    def anonymize_batch_status(self, data=None):
        """
        Anonymize arbitrary batch_status data
        """
        if not isinstance(data, (list, dict)):
            self.logger.error('data expected to be dict or list')
            return None

        if isinstance(data, dict):
            dat = [data]
        else:
            dat = data

        # Local mapping data used to store obfuscation mapping data for this
        # specific item, d
        self.lmap = {}

        # loop over each "batch_status" entry to obfuscate
        for d in dat:

            if self.attr_delete is not None:
                for todel in self.attr_delete:
                    if todel in d:
                        del d[todel]

            if self.resc_delete is not None:
                for todel in self.resc_delete:
                    for tmpk, _ in d.items():
                        if '.' in tmpk and todel == tmpk.split('.')[1]:
                            del d[tmpk]

            # Loop over each object's attributes, this is where the special
            # cases are handled (e.g., FGC limits, formula, select spec...)
            for attr in d:
                val = d[attr]

                if '.' in attr:
                    (res_type, res_name) = attr.split('.')
                else:
                    res_type = None
                    res_name = attr

                if res_type is not None:
                    if self._entity and attr.startswith('max_run'):
                        self.__anonymize_fgc(d, attr, self.attr_val,
                                             attr, val)

                    if res_name in self.resc_val:
                        if attr.startswith('max_run'):
                            self.__anonymize_fgc(d, attr, self.attr_val,
                                                 attr, val)
                        self.__anonymize_attr_val(d, attr, self.resc_val,
                                                  res_name, val)

                    if res_name in self.resc_key:
                        self.__anonymize_attr_key(d, attr, self.resc_key,
                                                  res_name, res_type)
                else:
                    if attr in self.attr_val:
                        self.__anonymize_attr_val(d, attr, self.attr_val,
                                                  attr, val)

                    if attr in self.attr_key:
                        self.__anonymize_attr_key(d, attr, self.attr_key,
                                                  attr, None)

                    if ((attr in ('job_sort_formula', 'schedselect',
                       'select')) and self.resc_key):
                        for r in self.resc_key:
                            if r in val:
                                if r not in self.gmap_resc_key:
                                    self.gmap_resc_key[
                                        r] = self.utils.random_str(len(r))
                                val = val.replace(r, self.gmap_resc_key[r])
                                setattr(self, attr, val)

                        d[attr] = val

    def anonymize_file(self, filename, extension='.anon', inplace=False):
        """
        Replace every occurrence of any entry in the global map for the given
        file by its anonymized values.
        Returns a file named after the original file with the extension suffix,
        if inplace is True returns the original file name for which contents
        have been replaced
        """
        if not inplace:
            fn = (filename + extension)
            nf = open(fn, 'w')
        else:
            (_, fn) = self.du.mkstemp()
            nf = open(fn, "w")

        f = open(filename)
        for data in f:
            for k in self.attr_key:
                if k in data:
                    if k not in self.gmap_attr_key:
                        ak = self.utils.random_str(len(k))
                        self.gmap_attr_key[k] = ak
                    else:
                        k = self.gmap_attr_key[k]
                    data = data.replace(k, self.gmap_attr_key[k])

            for k in self.resc_key:
                if k not in self.gmap_resc_key:
                    rk = self.utils.random_str(len(k))
                    self.gmap_resc_key[k] = rk
                else:
                    rk = self.gmap_resc_key[k]
                data = data.replace(k, self.gmap_resc_key[k])

            for ak, av in self.gmap_attr_val.items():
                for k, v in av.items():
                    data = data.replace(k, v)

            for ak, av in self.gmap_resc_val.items():
                for k, v in av.items():
                    data = data.replace(k, v)
            nf.write(data)
        nf.close()
        f.close()

        if inplace:
            self.du.run_cmd(cmd=['mv', fn, filename])
            return filename

        return fn

    def anonymize_accounting_log(self, logfile):
        try:
            f = open(logfile)
        except:
            self.logger.error("Error processing " + logfile)
            return None

        if 'euser' in self.attr_val:
            self.attr_val['user'] = self.attr_val['euser']
            self.attr_val['requestor'] = self.attr_val['euser']

        if 'egroup' in self.attr_val:
            self.attr_val['group'] = self.attr_val['egroup']

        if 'euser' in self.gmap_attr_val:
            self.gmap_attr_val['user'] = self.gmap_attr_val['euser']

        if 'egroup' in self.gmap_attr_val:
            self.gmap_attr_val['group'] = self.gmap_attr_val['egroup']

        anon_data = []
        for data in f:
            # accounting log format is
            # %Y/%m/%d %H:%M:%S;<Key>;<Id>;<key1=val1> <key2=val2> ...
            curr = data.split(';', 3)
            if curr[1] in ('A', 'L'):
                anon_data.append(data.strip())
                continue
            buf = curr[3].strip().split(' ')

            # Split the attribute list into key value pairs
            kvl = map(lambda n: n.split('=', 1), buf)
            for i in range(len(kvl)):
                k, v = kvl[i]
                if k == 'requestor':
                    if '@' in v:
                        (v, host) = v.split('@', 1)

                if k in self.attr_val:
                    if k == 'project' and v == '_pbs_project_default':
                        continue
                    anon_kv = None
                    if k in self.gmap_attr_val:
                        if v in self.gmap_attr_val[k]:
                            anon_kv = self.gmap_attr_val[k][v]
                    else:
                        self.gmap_attr_val[k] = {}

                    if anon_kv is None:
                        anon_kv = self.utils.random_str(len(v))
                        self.gmap_attr_val[k][v] = anon_kv

                    kvl[i][1] = anon_kv

                    # append server from where request was made
                    if k == 'requestor':
                        kvl[i][1] += '@' + host

                if k in self.attr_key:
                    if k in self.gmap_attr_key:
                        anon_ak = self.gmap_resc_key[k]
                    else:
                        anon_ak = self.utils.random_str(len(k))
                        self.gmap_attr_key[k] = anon_ak
                    kvl[i][0] = anon_ak

                if '.' in k:
                    restype, resname = k.split('.')
                    for rv in self.resc_val:
                        if resname == rv:
                            anon_rv = None
                            if resname in self.gmap_resc_val:
                                if v in self.gmap_resc_val[resname]:
                                    anon_rv = self.gmap_resc_val[resname][v]
                            else:
                                self.gmap_resc_val[resname] = {}

                            if anon_rv is None:
                                anon_rv = self.utils.random_str(len(v))
                                self.gmap_resc_val[resname][v] = anon_rv

                            kvl[i][1] = anon_rv

                    if resname in self.resc_key:
                        if resname in self.gmap_resc_key:
                            anon_rk = self.gmap_resc_key[resname]
                        else:
                            anon_rk = self.utils.random_str(len(resname))
                            self.gmap_resc_key[resname] = anon_rk

                        kvl[i][0] = restype + '.' + anon_rk

            anon_data.append(";".join(curr[:3]) + ";" +
                             " ".join(map(lambda n: "=".join(n), kvl)))
        f.close()

        return anon_data

    def anonymize_sched_config(self, scheduler):
        if len(self.resc_key) == 0:
            return

        # when anonymizing we get rid of the comments as they may contain
        # sensitive information
        scheduler._sched_config_comments = {}

        # If resources need to be anonymized then update the resources line
        # job_sort_key and node_sort_key
        sr = scheduler.get_resources()
        if sr:
            for i in range(0, len(sr)):
                if sr[i] in self.resc_key:
                    if sr[i] in self.gmap_resc_key:
                        sr[i] = self.gmap_resc_key[sr[i]]
                    else:
                        anon_res = self.utils.random_str(len(sr[i]))
                        self.gmap_resc_key[sr[i]] = anon_res
                        sr[i] = anon_res

            scheduler.sched_config['resources'] = ",".join(sr)

        for k in ['job_sort_key', 'node_sort_key']:
            if k in scheduler.sched_config:
                sc_jsk = scheduler.sched_config[k]
                if not isinstance(sc_jsk, list):
                    sc_jsk = list(sc_jsk)

                for r in self.resc_key:
                    for i in range(len(sc_jsk)):
                        if r in sc_jsk[i]:
                            sc_jsk[i] = sc_jsk[i].replace(r, self.resc_key[r])

    def __str__(self):
        return ("Attributes Values: " + str(self.gmap_attr_val) + "\n" +
                "Resources Values: " + str(self.gmap_resc_val) + "\n" +
                "Attributes Keys: " + str(self.gmap_attr_key) + "\n" +
                "Resources Keys: " + str(self.gmap_resc_key))


class Entity(object):

    """
    Abstract representation of a PBS consumer that has an external relationship
    to the PBS system. For example, a user associated to an OS identifier (uid)
    maps to a PBS user entity.

    Entities may be subject to policies, such as limits, consume a certain
    amount of resource and/or fairshare usage.
    """

    def __init__(self, etype=None, name=None):
        self.type = etype
        self.name = name
        self.limits = []
        self.resource_usage = {}
        self.fairshare_usage = 0

    def set_limit(self, limit=None):
        for l in self.limits:
            if str(limit) == str(l):
                return
        self.limits.append(limit)

    def set_resource_usage(self, container=None, resource=None, usage=None):
        if self.type:
            if container in self.resource_usage:
                if self.resource_usage[self.type]:
                    if resource in self.resource_usage[container]:
                        self.resource_usage[container][resource] += usage
                    else:
                        self.resource_usage[container][resource] = usage
                else:
                    self.resource_usage[container] = {resource: usage}

    def set_fairshare_usage(self, usage=0):
        self.fairshare_usage += usage

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return str(self.limits) + ' ' + str(self.resource_usage) + ' ' + \
            str(self.fairshare_usage)


class Policy(object):

    """
    Abstract PBS policy. Can be one of limits, access control, scheduling
    policy, etc...this class does not currently support any operations
    """

    def __init__(self):
        pass


class Limit(Policy):

    """
    Representation of a PBS limit
    Limits apply to containers, are of a certain type (e.g., max_run_res.ncpus)
    associated to a given resource (e.g., resource), on a given entity (e.g.,
    user Bob) and have a certain value.
    """

    def __init__(self, limit_type=None, resource=None,
                 entity_obj=None, value=None, container=None,
                 container_id=None):
        self.set_container(container, container_id)
        self.soft_limit = False
        self.hard_limit = False
        self.set_limit_type(limit_type)
        self.set_resource(resource)
        self.set_value(value)
        self.entity = entity_obj

    def set_container(self, container, container_id):
        self.container = container
        self.container_id = container_id

    def set_limit_type(self, t):
        self.limit_type = t
        if '_soft' in t:
            self.soft_limit = True
        else:
            self.hard_limit = True

    def set_resource(self, resource):
        self.resource = resource

    def set_value(self, value):
        self.value = value

    def __eq__(self, value):
        if str(self) == str(value):
            return True
        return False

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        l = [self.container_id, self.limit_type, self.resource, '[',
             self.entity.type, ':', self.entity.name, '=', self.value, ']']
        return " ".join(l)


class ExpectActions(object):

    """
    List of action handlers to run when Server's expect function does not get
    the expected result
    """

    actions = {}

    def __init__(self, action=None, level=logging.INFO):
        self.logger = logging.getLogger(__name__)
        self.add_action(action, level=level)

    def add_action(self, action=None, hostname=None, level=logging.INFO):
        if action is not None and action.name is not None and\
           action.name not in self.actions:
            self.actions[action.name] = action
            msg = ['expect action: added action ' + action.name]
            if hostname:
                msg += [' to server ' + hostname]
            if level >= logging.INFO:
                self.logger.info("".join(msg))
            else:
                self.logger.debug("".join(msg))

    def has_action(self, name):
        if name in self.actions:
            return True
        return False

    def get_action(self, name):
        if name in self.actions:
            return self.actions[name]
        return None

    def list_actions(self, level=logging.INFO):
        if level >= logging.INFO:
            self.logger.info(self.get_all_cations)
        else:
            self.logger.debug(self.get_all_cations)

    def get_all_actions(self):
        return self.actions.values()

    def get_actions_by_type(self, atype=None):
        if atype is None:
            return None

        ret_actions = []
        for action in self.actions.values():
            if action.type is not None and action.type == atype:
                ret_actions.append(action)
        return ret_actions

    def _control_action(self, action=None, name=None, enable=None):
        if action:
            action.enabled = False
            name = action.name
        elif name is not None:
            if name == 'ALL':
                for a in self.actions:
                    a.enabled = enable
            else:
                a = self.get_action(name)
                a.enabled = False
        else:
            return

        if enable:
            msg = 'enabled'
        else:
            msg = 'disabled'

        self.logger.info('expect action: ' + name + ' ' + msg)

    def disable_action(self, action=None, name=None):
        self._control_action(action, name, enable=False)

    def enable_action(self, action=None, name=None):
        self._control_action(action, name, enable=True)

    def disable_all_actions(self):
        for a in self.actions.values():
            a.enabled = False

    def enable_all_actions(self):
        for a in self.actions.values():
            a.enabled = True


class ExpectAction(object):

    """
    Action function to run when Server's expect function does not get the
    expected result
    """

    def __init__(self, name=None, enabled=True, atype=None, action=None,
                 level=logging.INFO):
        self.logger = logging.getLogger(__name__)
        self.set_name(name, level=level)
        self.set_enabled(enabled)
        self.set_type(atype)
        self.set_action(action)

    def set_name(self, name, level=logging.INFO):
        if level >= logging.INFO:
            self.logger.info('expect action: created new action ' + name)
        else:
            self.logger.debug('expect action: created new action ' + name)
        self.name = name

    def set_enabled(self, enabled):
        self.enabled = enabled

    def set_type(self, atype):
        self.type = atype

    def set_action(self, action):
        self.action = action


class PbsTypeAttribute(dict):

    """
    Experimental. This is a placeholder object that will be used in the future
    to map attribute information and circumvent the error-pron dynamic type
    detection that is currently done using decode_value()
    """

    def __getitem__(self, name):
        return BatchUtils.decode_value(super(PbsTypeAttribute,
                                             self).__getitem__(name))


class PBSObject(object):

    """
    Generic PBS Object encapsulating attributes and defaults
    """

    utils = BatchUtils()
    platform = sys.platform

    def __init__(self, name, attrs={}, defaults={}):
        """
        Initialize a PBS Object

        name - The name associated to the object

        attrs - Dictionary of attributes to set on object

        defaults - Dictionary of default attributes. Setting this will override
        any other object's default
        """
        self.attributes = OrderedDict()
        self.name = name
        self.dflt_attributes = defaults
        self.attropl = None
        self.custom_attrs = OrderedDict()
        self.ctime = int(time.time())

        self.set_attributes(attrs)

    def set_attributes(self, a={}):
        """
        set attributes and custom attributes on this object.
        custom attributes are used when converting attributes to CLI
        """
        if isinstance(a, list):
            a = OrderedDict(a)

        self.attributes = OrderedDict(self.dflt_attributes.items() +
                                      self.attributes.items() + a.items())

        self.custom_attrs = OrderedDict(self.custom_attrs.items() +
                                        a.items())

    def unset_attributes(self, attrl=[]):
        """
        Unset attributes from object's attributes and custom attributes
        """
        for attr in attrl:
            if attr in self.attributes:
                del self.attributes[attr]
            if attr in self.custom_attrs:
                del self.custom_attrs[attr]

    def __str__(self):
        """
        Return a string representation of this PBSObject
        """
        if self.name is None:
            return ""

        s = []
        if isinstance(self, Job):
            s += ["Job Id: " + self.name + "\n"]
        elif isinstance(self, Queue):
            s += ["Queue: " + self.name + "\n"]
        elif isinstance(self, Server):
            s += ["Server: " + self.hostname + "\n"]
        elif isinstance(self, Reservation):
            s += ["Name: " + "\n"]
        else:
            s += [self.name + "\n"]
        for k, v in self.attributes.items():
            s += ["    " + k + " = " + str(v) + "\n"]
        return "".join(s)

    def __repr__(self):
        return str(self.attributes)


class PBSService(PBSObject):

    """
    Generic PBS service object to hold properties of PBS daemons
    """
    du = DshUtils()
    pu = ProcUtils()

    def __init__(self, name=None, attrs={}, defaults={}, pbsconf_file=None,
                 diagmap={}, diag=None):
        """
        Initialize a PBS Controller Object (typically a daemon)

        name - The name associated to the object

        attrs - Dictionary of attributes to set on object

        defaults - Dictionary of default attributes. Setting this will override
        any other object's default

        pbsconf_file - Optional path to the pbs configuration file

        diagmap - A dictionary of PBS objects (node,server,etc) to mapped files
        from PBS diag directory

        diag - path to PBS diag directory (This will overrides diagmap)
        """
        if name is None:
            self.hostname = socket.gethostname()
        else:
            self.hostname = name
        if diag:
            self.diagmap = self._load_from_diag(diag)
            self.has_diag = True
            self.diag = diag
        elif len(diagmap) > 0:
            self.diagmap = diagmap
            self.diag = None
            self.has_diag = True
        else:
            self.diagmap = {}
            self.diag = None
            self.has_diag = False
        if not self.has_diag:
            try:
                self.fqdn = socket.gethostbyaddr(self.hostname)[0]
                if self.hostname != self.fqdn:
                    self.logger.debug('FQDN name ' + self.fqdn + ' differs '
                                      'from name provided ' + self.hostname)
            except:
                pass
        else:
            self.fqdn = self.hostname

        self.shortname = self.hostname.split('.')[0]

        self.logutils = None
        self.logfile = None
        self.acctlogfile = None
        self.pid = None
        self.pbs_conf = {}
        self.pbs_env = {}
        self._is_local = True
        self.launcher = None

        PBSObject.__init__(self, name, attrs, defaults)

        if not self.has_diag:
            if not self.du.is_localhost(self.hostname):
                self._is_local = False

        if pbsconf_file is None and not self.has_diag:
            self.pbs_conf_file = self.du.get_pbs_conf_file(name)
        else:
            self.pbs_conf_file = pbsconf_file

        if self.pbs_conf_file == '/etc/pbs.conf':
            self.default_pbs_conf = True
        elif (('PBS_CONF_FILE' not in os.environ) or
              (os.environ['PBS_CONF_FILE'] != self.pbs_conf_file)):
            self.default_pbs_conf = False
        else:
            self.default_pbs_conf = True

        # default pbs_server_name to hostname, it will get set again once the
        # config file is processed
        self.pbs_server_name = self.hostname

        # If diag is given then bypass parsing pbs.conf
        if self.has_diag:
            if diag is None:
                t = 'pbs_diag_%s' % (time.strftime("%y%m%d_%H%M%S"))
                self.diag = os.path.join(self.du.get_tempdir(), t)
            self.pbs_conf['PBS_HOME'] = self.diag
            self.pbs_conf['PBS_EXEC'] = self.diag
            self.pbs_conf['PBS_SERVER'] = self.hostname
            m = re.match('.*pbs_diag_(?P<datetime>\d{6,6}_\d{6,6}).*',
                         self.diag)
            if m:
                tm = time.strptime(m.group('datetime'), "%y%m%d_%H%M%S")
                self.ctime = int(time.mktime(tm))
        else:
            self.pbs_conf = self.du.parse_pbs_config(self.hostname,
                                                     self.pbs_conf_file)
            if self.pbs_conf is None or len(self.pbs_conf) == 0:
                self.pbs_conf = {'PBS_HOME': "", 'PBS_EXEC': ""}
            else:
                ef = os.path.join(self.pbs_conf['PBS_HOME'], 'pbs_environment')
                self.pbs_env = self.du.parse_pbs_environment(self.hostname, ef)
                self.pbs_server_name = self.du.get_pbs_server_name(
                    self.pbs_conf)

        self.init_logfile_path(self.pbs_conf)

    def _load_from_diag(self, diag):
        diagmap = {}
        diagmap[SERVER] = os.path.join(diag, 'qstat_Bf.out')
        diagmap[VNODE] = os.path.join(diag, 'pbsnodes_va.out')
        diagmap[QUEUE] = os.path.join(diag, 'qstat_Qf.out')
        diagmap[JOB] = os.path.join(diag, 'qstat_tf.out')
        if not os.path.isfile(diagmap[JOB]):
            diagmap[JOB] = os.path.join(diag, 'qstat_f.out')
        diagmap[RESV] = os.path.join(diag, 'pbs_rstat_f.out')
        diagmap[SCHED] = os.path.join(diag, 'qmgr_psched.out')
        diagmap[HOOK] = []
        if (os.path.isdir(os.path.join(diag, 'server_priv')) and
                os.path.isdir(os.path.join(diag, 'server_priv', 'hooks'))):
            _ld = os.listdir(os.path.join(diag, 'server_priv', 'hooks'))
            for f in _ld:
                if f.endswith('.HK'):
                    diagmap[HOOK].append(
                        os.path.join(diag, 'server_priv', 'hooks', f))

        # Format of qmgr_psched.out differs from Batch Status, we transform
        # it to go through the common batch status parsing routines
        if os.path.isfile(diagmap[SCHED]):
            f = open(os.path.join(diag, 'ptl_qstat_Sched.out'), 'w')
            lines = open(diagmap[SCHED])
            f.write("Sched \n")
            for l in lines:
                recs = l.split()
                f.write("".join(recs[2:5]) + "\n")
            f.close()
            diagmap[SCHED] = os.path.join(diag, 'ptl_qstat_Sched.out')
        else:
            diagmap[SCHED] = None
        return diagmap

    def init_logfile_path(self, conf=None):
        " Initialize path to log files for this service "
        elmt = self._instance_to_logpath(self)
        if elmt is None:
            return

        if conf is not None and 'PBS_HOME' in conf:
            tm = time.strftime("%Y%m%d", time.localtime())
            self.logfile = os.path.join(conf['PBS_HOME'], elmt, tm)
            self.acctlogfile = os.path.join(conf['PBS_HOME'], 'server_priv',
                                            'accounting', tm)

    def _instance_to_logpath(self, inst):
        " returns the log path associated to this service "
        if isinstance(inst, Scheduler):
            logval = 'sched_logs'
        elif isinstance(inst, Server):
            logval = 'server_logs'
        elif isinstance(inst, MoM):
            logval = 'mom_logs'
        elif isinstance(inst, Comm):
            logval = 'comm_logs'
        else:
            logval = None
        return logval

    def _instance_to_cmd(self, inst):
        " returns the command associated to this service "
        if isinstance(inst, Scheduler):
            cmd = 'pbs_sched'
        elif isinstance(inst, Server):
            cmd = 'pbs_server'
        elif isinstance(inst, MoM):
            cmd = 'pbs_mom'
        elif isinstance(inst, Comm):
            cmd = 'pbs_comm'
        else:
            cmd = None
        return cmd

    def _instance_to_servicename(self, inst):
        """
        return the service name associated to the instance. One of
        server, scheduler, or mom.
        """
        if isinstance(inst, Scheduler):
            nm = 'scheduler'
        elif isinstance(inst, Server):
            nm = 'server'
        elif isinstance(inst, MoM):
            nm = 'mom'
        elif isinstance(inst, Comm):
            nm = 'comm'
        else:
            nm = ''
        return nm

    def _instance_to_privpath(self, inst):
        " returns the path to priv associated to this service "
        if isinstance(inst, Scheduler):
            priv = 'sched_priv'
        elif isinstance(inst, Server):
            priv = 'server_priv'
        elif isinstance(inst, MoM):
            priv = 'mom_priv'
        elif isinstance(inst, Comm):
            priv = 'server_priv'
        else:
            priv = None
        return priv

    def _instance_to_lock(self, inst):
        " returns the path to lock file associated to this service "
        if isinstance(inst, Scheduler):
            lock = 'sched.lock'
        elif isinstance(inst, Server):
            lock = 'server.lock'
        elif isinstance(inst, MoM):
            lock = 'mom.lock'
        elif isinstance(inst, Comm):
            lock = 'comm.lock'
        else:
            lock = None
        return lock

    def set_launcher(self, execargs=None):
        self.launcher = execargs

    def _isUp(self, inst):
        " returns True if service is up and False otherwise "
        live_pids = self._all_instance_pids(inst)
        pid = self._get_pid(inst)
        if live_pids is not None and pid in live_pids:
            return True
        return False

    def _signal(self, sig, inst=None, procname=None):
        """
        Send signal sig to service. sig is the signal name as it would be
        sent to the program kill, e.g. -HUP.

        Return the out/err/rc from the command run to send the signal. See
        DshUtils.run_cmd
        """
        pid = None

        if inst is not None:
            if inst.pid is not None:
                pid = inst.pid
            else:
                pid = self._get_pid(inst)

        if procname is not None:
            pi = self.pu.get_proc_info(self.hostname, procname)
            if pi is not None and pi.values() and pi.values()[0]:
                for _p in pi.values()[0]:
                    ret = self.du.run_cmd(self.hostname, ['kill', sig, _p.pid],
                                          sudo=True)
                return ret

        if pid is None:
            return {'rc': 0, 'err': '', 'out': 'no pid to signal'}

        return self.du.run_cmd(self.hostname, ['kill', sig, pid], sudo=True)

    def _all_instance_pids(self, inst):
        """
        Return a list of all PIDS that match the instance name or None.
        """
        cmd = self._instance_to_cmd(inst)
        self.pu.get_proc_info(self.hostname, ".*" + cmd + ".*",
                              regexp=True)
        _procs = self.pu.processes.values()
        if _procs:
            _pids = []
            for _p in _procs:
                _pids.extend(map(lambda x: x.pid, _p))
            return _pids
        return None

    def _get_pid(self, inst):
        """
        Get the PID associated to this instance. Implementation note, the pid
        is read from the daemon's lock file.

        This is different than _all_instance_pids in that the PID of the last
        running instance can be retrieved with _get_pid but not with
        _all_instance_pids
        """
        priv = self._instance_to_privpath(inst)
        lock = self._instance_to_lock(inst)
        path = os.path.join(self.pbs_conf['PBS_HOME'], priv, lock)
        rv = self.du.cat(self.hostname, path, sudo=True, logerr=False)
        if ((rv['rc'] == 0) and (len(rv['out']) > 0)):
            self.pid = rv['out'][0].strip()
        else:
            self.pid = None
        return self.pid

    def _start(self, inst=None, args=None, cmd_map=None, launcher=None):
        """
        Generic service startup

        inst - The instance to act upon

        args - Optional command-line arguments

        cmd_map - Optional dictionary of command line options to configuration
        variables

        launcher - Optional utility to invoke the launch of the service. This
        option only takes effect on Unix/Linux. The option can be a string
        or a list.Options may be passed to the launcher, for example to start
        a service through the valgrind utility redirecting to a log file,
        launcher could be set to e.g. ['valgrind', '--log-file=/tmp/vlgrd.out']
        or 'valgrind --log-file=/tmp/vlgrd.out'
        """
        if launcher is None and self.launcher is not None:
            launcher = self.launcher

        app = self._instance_to_cmd(inst)
        if app is None:
            return
        _m = ['service: starting', app]
        if args is not None:
            _m += ['with args: ']
            _m += args

        as_script = False
        wait_on = True
        if launcher is not None:
            if isinstance(launcher, str):
                launcher = launcher.split()
            if app == 'pbs_server':
                # running the pbs server through valgrind requires a bit of
                # a dance because the pbs_server binary is pbs_server.bin
                # and to run it requires being able to find libraries, so
                # LD_LIBRARY_PATH is set and pbs_server.bin is run as a
                # script
                pexec = inst.pbs_conf['PBS_EXEC']
                ldlib = ['LD_LIBRARY_PATH=' +
                         os.path.join(pexec, 'lib') + ':' +
                         os.path.join(pexec, 'pgsql', 'lib')]
                app = 'pbs_server.bin'
            else:
                ldlib = []
            cmd = ldlib + launcher
            as_script = True
            wait_on = False
        else:
            cmd = []

        cmd += [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', app)]
        if args is not None:
            cmd += args
        if not self.default_pbs_conf:
            cmd = ['PBS_CONF_FILE=' + inst.pbs_conf_file] + cmd
            as_script = True
        if cmd_map is not None:
            conf_cmd = self.du.map_pbs_conf_to_cmd(cmd_map,
                                                   pconf=self.pbs_conf)
            cmd.extend(conf_cmd)
            _m += conf_cmd

        self.logger.info(" ".join(_m))

        ret = self.du.run_cmd(self.hostname, cmd, sudo=True,
                              as_script=as_script, wait_on_script=wait_on,
                              level=logging.INFOCLI, logerr=False)
        if ret['rc'] != 0:
            raise PbsServiceError(rv=False, rc=ret['rc'], msg=ret['err'])

        ret_msg = True
        if ret['err']:
            ret_msg = ret['err']

        self.pid = self._get_pid(inst)
        # get_pid gets information from a lock file that may not have been
        # removed when the daemon stopped so we verify that the PID is
        # actually alive in the list of pids returned by ps
        live_pids = self._all_instance_pids(inst)
        i = 0
        while ((self.pid is None) or
               (live_pids is None or self.pid not in live_pids)) and (i < 30):
            time.sleep(1)
            i += 1
            live_pids = self._all_instance_pids(inst)
            self.pid = self._get_pid(inst)
            if live_pids is not None and self.pid in live_pids:
                return ret_msg
        if i == 30:
            raise PbsServiceError(rv=False, rc=-1, msg="Could not find PID")
        return ret_msg

    def _stop(self, sig='-TERM', inst=None):
        if inst is None:
            return True
        self._signal(sig, inst)
        pid = self._get_pid(inst)
        chk_pid = self._all_instance_pids(inst)
        if pid is None or chk_pid is None:
            return True
        num_seconds = 0
        while (chk_pid is not None) and (str(pid) in chk_pid):
            if num_seconds > 60:
                m = (self.logprefix + 'could not stop service ' +
                     self._instance_to_servicename(inst))
                raise PbsServiceError(rv=False, rc=-1, msg=m)
            time.sleep(1)
            num_seconds += 1
            chk_pid = self._all_instance_pids(inst)
        inst.pid = None
        return True

    def log_lines(self, logtype, id=None, n=50, tail=True, day=None,
                  starttime=None, endtime=None):
        """
        Return the last <n> lines of a PBS log file, which can be one of
        server, scheduler, MoM, or tracejob

        logtype - The entity requested, an instance of a Scheduler, Server,
        or MoM object, or the string 'tracejob' for tracejob

        id -  The id of the object to trace. Only used for tracejob

        n - One of 'ALL' of the number of lines to process/display,
        defaults to 50.

        tail - if True, parse log from the end to the start, otherwise parse
        from the start to the end. Defaults to True.

        day - Optional day in YYYMMDD format. Defaults to current day

        starttime - date timestamp to start matching

        endtime - date timestamp to end matching
        """
        logval = None
        lines = None
        sudo = False

        try:
            if logtype == 'tracejob':
                if id is None:
                    return None
                cmd = [os.path.join(
                       self.pbs_conf['PBS_EXEC'],
                       'bin',
                       'tracejob')]
                cmd += [str(id)]
                lines = self.du.run_cmd(self.hostname, cmd)['out']
                if n != 'ALL':
                    lines = lines[-n:]
            else:
                if day is None:
                    day = time.strftime("%Y%m%d", time.localtime(time.time()))
                if logtype == 'accounting':
                    filename = os.path.join(self.pbs_conf['PBS_HOME'],
                                            'server_priv', 'accounting', day)
                    sudo = True
                else:
                    logval = self._instance_to_logpath(logtype)
                    if logval:
                        filename = os.path.join(self.pbs_conf['PBS_HOME'],
                                                logval, day)
                if n == 'ALL':
                    if self._is_local and not sudo:
                        lines = open(filename)
                    else:
                        lines = self.du.cat(self.hostname, filename, sudo=sudo,
                                            level=logging.DEBUG2)['out']
                # tail is not a standard, e.g. on Solaris it does not recognize
                # -n. We circumvent this problem by using PTL's version of tail
                # but it currently only works on a local host, for remote hosts
                # we fall back to using tail/head -n
                elif self._is_local and not sudo:
                    if tail:
                        futils = FileUtils(filename, FILE_TAIL)
                    else:
                        futils = FileUtils(filename)
                    lines = futils.next(n)
                else:
                    if tail:
                        cmd = ['/usr/bin/tail']
                    else:
                        cmd = ['/usr/bin/head']

                    pyexec = os.path.join(self.pbs_conf['PBS_EXEC'], 'python',
                                          'bin', 'python')
                    osflav = self.du.get_platform(self.hostname, pyexec)
                    if osflav.startswith('sunos'):
                        cmd += ['-']
                    else:
                        cmd += ['-n']
                    cmd += [str(n), filename]
                    lines = self.du.run_cmd(self.hostname, cmd, sudo=sudo,
                                            level=logging.DEBUG2)['out']
        except:
            self.logger.error('error in log_lines ')
            traceback.print_exc()
            return None

        return lines

    def _log_match(self, logtype, msg, id=None, n=50, tail=True,
                   allmatch=False, regexp=False, day=None, max_attempts=1,
                   interval=1, starttime=None, endtime=None,
                   level=logging.INFO):
        """
        If 'msg' found in the 'n' lines of the log file, returns a tupe (x,y)
        where x is the matching line number and y the line itself. If no match,
        return None. If allmatch is True, a list of tuples is returned.

        logtype - The entity requested, an instance of a Scheduler, Server,
        or MoM object, or the strings 'tracejob' for tracejob or 'accounting'
        for accounting logs.

        id - The id of the object to trace. Only used for tracejob

        n - 'ALL' or the number of lines to search through, defaults to 50

        tail - If true (default), starts from the end of the file

        allmatch - If True all matching lines out of the n parsed are returned
        as a list. Defaults to False

        regexp - If true msg is a Python regular expression. Defaults to False

        day - Optional day in YYYMMDD format.

        max_attempts - the number of attempts to make to find a matching entry

        interval - the interval between attempts

        starttime - If set ignore matches that occur before specified time

        endtime - If set ignore matches that occur after specified time

        Note that the matching line number is relative to the record number,
        not the absolute line number in the file.
        """
        try:
            from ptl.utils.pbs_logutils import PBSLogUtils
        except:
            self.logger.error('error loading ptl.utils.pbs_logutils')
            return None

        if self.logutils is None:
            self.logutils = PBSLogUtils()

        rv = (None, None)
        attempt = 1
        name = self._instance_to_servicename(logtype)
        infomsg = (name + ' ' + self.shortname +
                   ' log match: searching for "' + msg + '"')
        if regexp:
            infomsg += ' - using regular expression '
        if allmatch:
            infomsg += ' - on all matches '
        attemptmsg = ' - No match'
        while attempt <= max_attempts:
            if attempt > 1:
                attemptmsg = ' - attempt ' + str(attempt)
            lines = self.log_lines(logtype, id, n=n, tail=tail, day=day,
                                   starttime=starttime, endtime=endtime)
            rv = self.logutils.match_msg(lines, msg, allmatch=allmatch,
                                         regexp=regexp, starttime=starttime,
                                         endtime=endtime)
            if rv:
                self.logger.log(level, infomsg + '... OK')
                break
            else:
                if ((starttime is not None or endtime is not None) and
                        n != 'ALL'):
                    if attempt > max_attempts:
                        # We will do one last attempt to match in case the
                        # number of lines that were provided did not capture
                        # the start or end time of interest
                        max_attempts += 1
                    n = 'ALL'
                self.logger.log(level, infomsg + attemptmsg)
            attempt += 1
            time.sleep(interval)
        try:
            # Depending on whether the hostname is local or remote and whether
            # sudo privileges were required, lines returned by log_lines can be
            # an open file descriptor, we close here but ignore errors in case
            # any were raised for all irrelevant cases
            lines.close()
        except:
            pass
        return rv

    def accounting_match(self, msg, id=None, n=50, tail=True,
                         allmatch=False, regexp=False, day=None,
                         max_attempts=1, interval=1, starttime=None,
                         endtime=None):
        " Find msg in accounting log. See _log_match for details "
        return self._log_match('accounting', msg, id, n, tail, allmatch,
                               regexp, day, max_attempts, interval, starttime,
                               endtime)

    def tracejob_match(self, msg, id=None, n=50, tail=True, allmatch=False,
                       regexp=False, **kwargs):
        " Find msg in tracejob log. See _log_match for details "
        return self._log_match('tracejob', msg, id, n, tail, allmatch,
                               regexp, kwargs)

    def _save_config_file(self, dict_conf, fname):
        ret = self.du.cat(self.hostname, fname, sudo=True)
        if ret['rc'] == 0:
            dict_conf[fname] = ret['out']
        else:
            self.logger.error('error saving configuration ' + fname)

    def _load_configuration(self, infile, objtype=None):
        """
        Load configuration as was saved in infile

        infile - the file in which configuration was saved

        objtype - the object type to load configuration for, one of server,

        scheduler, mom, or, if None, load all objects in infile
        """
        if os.path.isfile(infile):
            conf = {}
            f = open(infile, 'r')
            # load all objects from the Pickled file
            while True:
                try:
                    conf = cPickle.load(f)
                except:
                    break
            f.close()

            if objtype and objtype in conf:
                conf = conf[objtype]
            else:
                # load all object types that could be in infile
                newconf = {}
                for ky in [MGR_OBJ_SERVER, MGR_OBJ_SCHED, MGR_OBJ_NODE]:
                    if ky not in conf:
                        conf[ky] = {}
                    newconf = dict(newconf.items() + conf[ky].items())
                conf = newconf

            for k, v in conf.items():
                (fd, fn) = self.du.mkstemp()
                # handle server data saved as output of qmgr commands by piping
                # data back into qmgr
                if k.startswith('qmgr_'):
                    qmgr = os.path.join(self.client_conf['PBS_EXEC'],
                                        'bin', 'qmgr')
                    os.write(fd, "\n".join(v))
                    self.du.run_cmd(
                        self.hostname,
                        [qmgr],
                        cstdin=fd,
                        sudo=True)
                else:
                    os.write(fd, "\n".join(v))
                    # append the last line
                    os.write(fd, "\n")
                    self.du.run_cmd(self.hostname, ['cp', fn, k], sudo=True)
                os.close(fd)
                os.remove(fn)

            return True
        return False

    def is_cray(self):
        """
        Returns True if the version of PBS used was built for Cray platforms
        """
        rv = self.log_match("--enable-alps", tail=False, n=10, max_attempts=1,
                            level=logging.DEBUG)
        if rv:
            return True
        return False

    def get_tempdir(self):
        " platform independent call to get a temporary directory "
        return self.du.get_tempdir(self.hostname)

    def __str__(self):
        return (self.__class__.__name__ + ' ' + self.hostname + ' config ' +
                self.pbs_conf_file)

    def __repr__(self):
        return (self.__class__.__name__ + '/' + self.pbs_conf_file + '@' +
                self.hostname)


class Comm(PBSService):

    """
    PBS Comm configuration and control
    """

    logger = logging.getLogger(__name__)
    logprefix = 'pbs_comm: '

    conf_to_cmd_map = {'PBS_COMM_NAME': '-n', 'PBS_COMM_ROUTERS': '-r',
                       'PBS_COMM_THREADS': '-t'}

    def isUp(self):
        return super(Comm, self)._isUp(self)

    def signal(self, sig):
        self.logger.info(self.logprefix + 'sent signal ' + sig)
        return super(Comm, self)._signal(sig, inst=self)

    def get_pid(self):
        return super(Comm, self)._get_pid(inst=self)

    def all_instance_pids(self):
        return super(Comm, self)._all_instance_pids(inst=self)

    def start(self, args=None, launcher=None):
        return super(Comm, self)._start(inst=self, args=args,
                                        cmd_map=self.conf_to_cmd_map,
                                        launcher=launcher)

    def stop(self, sig='-TERM'):
        self.logger.info(self.logprefix + 'stopping Comm on host ' +
                         self.hostname)
        rv = super(Comm, self)._stop(sig, inst=self)
        return rv

    def restart(self):
        if self.stop():
            return self.start()
        return False

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, day=None, max_attempts=1, interval=1,
                  starttime=None, endtime=None, level=logging.INFO):
        return self._log_match(self, msg, id, n, tail, allmatch, regexp,
                               day, max_attempts, interval, starttime, endtime,
                               level=level)


class Server(PBSService):

    """
    PBS server configuration and control

    The Server class is a container to PBS server attributes and implements
    wrappers to the IFL API to perform operations on the server. For example
    to submit, status, delete, manage, etc... jobs, reservations and
    configurations.

    This class also offers higher-level routines to ease testing, see
    functions, for example: revert_to_defaults, init_logging, expect, counter.

    The ptl_conf dictionary holds general configuration for the framework's
    operations, specifically, one can control:

    mode: set to PTL_CLI to operate in CLI mode or PTL_API to operate in API
    mode

    expect_max_attempts: the default maximum number of attempts to be used\
    by expect. Defaults to 60

    expect_interval: the default time interval (in seconds) between expect\
    requests. Defaults to 0.5

    update_attributes: the default on whether Object attributes should be\
    updated using a list of dictionaries. Defaults to True
    """

    logger = logging.getLogger(__name__)

    dflt_attributes = {
        ATTR_scheduling: "True",
        ATTR_dfltque: "workq",
        ATTR_logevents: "511",
        ATTR_mailfrom: "adm",
        ATTR_queryother: "True",
        ATTR_rescdflt + ".ncpus": "1",
        ATTR_DefaultChunk + ".ncpus": "1",
        ATTR_schedit: "600",
        ATTR_ResvEnable: "True",
        ATTR_nodefailrq: "310",
        ATTR_maxarraysize: "10000",
        ATTR_license_linger: "3600",
        ATTR_EligibleTimeEnable: "False",
        ATTR_max_concurrent_prov: "5",
        ATTR_FlatUID: 'True',
    }

    ptl_conf = {
        'mode': PTL_API,
        'expect_max_attempts': 60,
        'expect_interval': 0.5,
        'update_attributes': True,
    }
    # this pattern is a bit relaxed to match common developer build numbers
    version_tag = re.compile("[a-zA-Z_]*(?P<version>[\d\.]+.[\w\d\.]*)[\s]*")

    actions = ExpectActions()

    def __init__(self, name=None, attrs={}, defaults={}, pbsconf_file=None,
                 diagmap={}, diag=None, client=None, client_pbsconf_file=None,
                 db_access=None, stat=True):
        """
        Initialize a Server instance.

        name - The hostname of the server. Defaults to current hostname.

        attrs - Dictionary of attributes to set, these will override defaults.

        defaults - Dictionary of default attributes. Default: dflt_attributes

        pbsconf_file - path to config file to parse for PBS_HOME, PBS_EXEC, etc

        diagmap - A dictionary of PBS objects (node,server,etc) to mapped files
        from PBS diag directory

        diag - path to PBS diag directory (This will overrides diagmap)

        client - The host to use as client for CLI queries. Defaults to the
        local hostname.

        client_pbsconf_file - The path to a custom PBS_CONF_FILE on the client
        host. Defaults to the same path as pbsconf_file.

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}

        stat- if True, stat the server attributes
        """
        self.jobs = {}
        self.nodes = {}
        self.reservations = {}
        self.queues = {}
        self.resources = {}
        self.hooks = {}
        self.pbshooks = {}
        self.entities = {}
        self.scheduler = None
        self.version = None
        self.default_queue = None
        self.last_error = []  # type: array. Set for CLI IFL errors. Not reset
        self.last_rc = None  # Set for CLI IFL return code. Not thread-safe

        # default timeout on connect/disconnect set to 60s to mimick the qsub
        # buffer introduced in PBS 11
        self._conn_timeout = 60
        self._conn_timer = None
        self._conn = None
        self._db_conn = None
        self.current_user = pwd.getpwuid(os.getuid())[0]

        if len(defaults.keys()) == 0:
            defaults = self.dflt_attributes

        self.pexpect_timeout = 15
        self.pexpect_sleep_time = .1

        PBSService.__init__(self, name, attrs, defaults, pbsconf_file, diagmap,
                            diag)
        _m = ['server ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)

        self.set_client(client)

        if client_pbsconf_file is None:
            self.client_pbs_conf_file = self.du.get_pbs_conf_file(self.client)
        else:
            self.client_pbs_conf_file = client_pbsconf_file

        self.client_conf = self.du.parse_pbs_config(
            self.client, file=self.client_pbs_conf_file)

        if self.client_pbs_conf_file == '/etc/pbs.conf':
            self.default_client_pbs_conf = True
        elif (('PBS_CONF_FILE' not in os.environ) or
              (os.environ['PBS_CONF_FILE'] != self.client_pbs_conf_file)):
            self.default_client_pbs_conf = False
        else:
            self.default_client_pbs_conf = True

        a = {}
        if os.getuid() == 0:
            a = {ATTR_aclroot: 'root'}
        self.dflt_attributes.update(a)

        if not API_OK:
            # mode must be set before the first stat call
            self.set_op_mode(PTL_CLI)

        if stat:
            try:
                tmp_attrs = self.status(SERVER, level=logging.DEBUG,
                                        db_access=db_access)
            except (PbsConnectError, PbsStatusError):
                tmp_attrs = None

            if tmp_attrs is not None and len(tmp_attrs) > 0:
                self.attributes = tmp_attrs[0]

            if ATTR_dfltque in self.attributes:
                self.default_queue = self.attributes[ATTR_dfltque]

            self.update_version_info()

    def update_version_info(self):
        if ATTR_version not in self.attributes:
            self.attributes[ATTR_version] = 'unknown'
        else:
            m = self.version_tag.match(self.attributes[ATTR_version])
            if m:
                v = m.group('version')
                self.version = LooseVersion(v)
        self.logger.info(self.logprefix + 'version ' +
                         self.attributes[ATTR_version])

    @classmethod
    def set_update_attributes(cls, val):
        cls.logger.info('setting update attributes ' + str(val))
        if val == 1 or val[0] in ('t', 'T'):
            val = True
        else:
            val = False
        cls.ptl_conf['update_attributes'] = val

    @classmethod
    def set_expect_max_attempts(cls, val):
        cls.logger.info('setting expect max attempts ' + str(val))
        cls.ptl_conf['expect_max_attempts'] = int(val)

    @classmethod
    def set_expect_interval(cls, val):
        cls.logger.info('setting expect interval ' + str(val))
        cls.ptl_conf['expect_interval'] = float(val)

    def set_client(self, name=None):
        if name is None:
            self.client = socket.gethostname()
        else:
            self.client = name

    def _connect(self, hostname, attempt=1):
        if ((self._conn is None or self._conn < 0) or
                (self._conn_timeout == 0 or self._conn_timer is None)):
            self._conn = pbs_connect(hostname)
            self._conn_timer = time.time()

        if self._conn is None or self._conn < 0:
            if attempt > 5:
                m = self.logprefix + 'unable to connect'
                raise PbsConnectError(rv=None, rc=-1, msg=m)
            else:
                self._disconnect(self._conn, force=True)
                time.sleep(1)
                return self._connect(hostname, attempt + 1)

        return self._conn

    def _disconnect(self, conn, force=False):
        """
        disconnect a connection to a Server.
        For performance of the API calls, a connection is maintained up
        to _conn_timer, unless the force parameter is set to True
        """
        if ((conn is not None and conn >= 0) and
            (force or
             (self._conn_timeout == 0 or
              (self._conn_timer is not None and
               (time.time() - self._conn_timer > self._conn_timeout))))):
            pbs_disconnect(conn)
            self._conn_timer = None
            self._conn = None

    def set_connect_timeout(self, timeout=0):
        self._conn_timeout = timeout

    def get_op_mode(self):
        """
        Returns operating mode for calls to the PBS server. Currently, two
        modes are supported, either the API or the CLI. Default is API
        """
        if (not API_OK or (self.ptl_conf['mode'] == PTL_CLI)):
            return PTL_CLI
        return PTL_API

    def set_op_mode(self, mode):
        """
        set operating mode to one of either PTL_CLI or PTL_API.
        Returns the mode that was set which can be different from the value
        requested, for example, if requesting to set PTL_API, in the absence
        of the appropriate SWIG wrappers, the library will fall back to CLI, or
        if requesting PTL_CLI and there is no PBS_EXEC on the system, None is
        returned.
        """
        if mode == PTL_API:
            if self._conn is not None or self._conn < 0:
                self._conn = None
            if not API_OK:
                self.logger.error(self.logprefix +
                                  'API submission is not available')
                return PTL_CLI
        elif mode == PTL_CLI:
            if ((not self.has_diag) and
                not os.path.isdir(os.path.join(self.client_conf['PBS_EXEC'],
                                               'bin'))):
                self.logger.error(self.logprefix +
                                  'PBS commands are not available')
                return None
        else:
            self.logger.error(self.logprefix + "Unrecognized operating mode")
            return None

        self.ptl_conf['mode'] = mode
        self.logger.info(self.logprefix + 'server operating mode set to ' +
                         mode)
        return mode

    def add_expect_action(self, name=None, action=None):
        """
        Add an action handler to expect. Expect Actions are custom handlers
        that are triggered when an unexpected value is encountered
        """
        if name is None and action.name is None:
            return
        if name is None and action.name is not None:
            name = action.name

        if not self.actions.has_action(name):
            self.actions.add_action(action, self.shortname)

    def set_attributes(self, a={}):
        """
        set server attributes
        """
        super(Server, self).set_attributes(a)
        self.__dict__.update(a)

    def isUp(self):
        """
        returns True if server is up and False otherwise
        """
        if self.has_diag:
            return True
        i = 0
        op_mode = self.get_op_mode()
        if ((op_mode == PTL_API) and (self._conn is not None)):
            self._disconnect(self._conn, force=True)
        while i < 20:
            rv = False
            try:
                if op_mode == PTL_CLI:
                    self.status(SERVER, level=logging.DEBUG, logerr=False)
                else:
                    c = self._connect(self.hostname)
                    self._disconnect(c, force=True)
                return True
            except (PbsConnectError, PbsStatusError):
                # if the status/connect operation fails then there might be
                # chances that server process is running but not responsive
                # so we wait until the server is reported operational.
                rv = self._isUp(self)
                # We really mean to check != False rather than just "rv"
                if str(rv) != 'False':
                    self.logger.warning('Server process started' +
                                        'but not up yet')
                    time.sleep(1)
                    i += 1
                else:
                    # status/connect failed + no server process means
                    # server is actually down
                    return False
        return False

    def signal(self, sig):
        self.logger.info('server ' + self.shortname + ': sent signal ' + sig)
        return super(Server, self)._signal(sig, inst=self)

    def get_pid(self):
        return super(Server, self)._get_pid(inst=self)

    def all_instance_pids(self):
        return super(Server, self)._all_instance_pids(inst=self)

    def start(self, args=None, launcher=None):
        rv = super(Server, self)._start(inst=self, args=args,
                                        launcher=launcher)
        if self.isUp():
            return rv
        else:
            raise PbsServiceError(rv=False, rc=1, msg=rv)

    def stop(self, sig='-TERM'):
        self.logger.info(self.logprefix + 'stopping Server on host ' +
                         self.hostname)
        rc = super(Server, self)._stop(sig, inst=self)
        self._disconnect(self._conn, force=True)
        return rc

    def restart(self):
        """
        Terminate and start a PBS server.
        """
        if self.isUp():
            self.stop()
        return self.start()

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, day=None, max_attempts=1, interval=1,
                  starttime=None, endtime=None, level=logging.INFO):
        return self._log_match(self, msg, id, n, tail, allmatch, regexp,
                               day, max_attempts, interval, starttime, endtime,
                               level=level)

    def revert_to_defaults(self, reverthooks=True, revertqueues=True,
                           revertresources=True, delhooks=True,
                           delqueues=True, server_stat=None):
        """
        reset server attributes back to out of box defaults.

        reverthooks - If True disable all hooks. Defaults to True

        revertqueues - If True disable all non-default queues. Defaults to True

        revertresources - If True, resourcedef file is removed. Defaults to
        True. Reverting resources causes a server restart to occur.

        delhooks - If True, hooks are deleted, if deletion fails, fall back
        to reverting hooks. Defaults to True.

        delqueues - If True, all non-default queues are deleted, will attempt
        to delete all jobs first, if it fails, revertqueues will be honored,
        otherwise, revertqueues is ignored. Defaults to True

        Returns True upon success and False if an error is encountered.
        May raise PbsStatusError or PbsManagerError
        """
        ignore_attrs = ['id', 'pbs_license', ATTR_NODE_ProvisionEnable]
        ignore_attrs += [ATTR_status, ATTR_total, ATTR_count]
        ignore_attrs += [ATTR_rescassn, ATTR_FLicenses, ATTR_SvrHost]
        ignore_attrs += [ATTR_license_count, ATTR_version, ATTR_managers]
        ignore_attrs += [ATTR_pbs_license_info]
        unsetlist = []
        setdict = {}
        self.logger.info(self.logprefix + 'reverting configuration to defaults')
        self.cleanup_jobs_and_reservations()
        if server_stat is None:
            server_stat = self.status(SERVER, level=logging.DEBUG)[0]
        for k in server_stat.keys():
            if (k in ignore_attrs) or (k in self.dflt_attributes.keys()):
                continue
            elif (('.' in k) and (k.split('.')[0] in ignore_attrs)):
                continue
            else:
                unsetlist.append(k)
        if len(unsetlist) != 0:
            self.manager(MGR_CMD_UNSET, MGR_OBJ_SERVER, unsetlist)
        for k in self.dflt_attributes.keys():
            if(k not in self.attributes or
               self.attributes[k] != self.dflt_attributes[k]):
                setdict[k] = self.dflt_attributes[k]
        if delhooks:
            reverthooks = False
            hooks = self.status(HOOK, level=logging.DEBUG)
            hooks = [h['id'] for h in hooks]
            if len(hooks) > 0:
                self.manager(MGR_CMD_DELETE, HOOK, id=hooks, expect=True)
        if delqueues:
            revertqueues = False
            queues = self.status(QUEUE, level=logging.DEBUG)
            queues = [q['id'] for q in queues]
            if len(queues) > 0:
                self.manager(MGR_CMD_DELETE, QUEUE, id=queues, expect=True)
            a = {ATTR_qtype: 'Execution',
                 ATTR_enable: 'True',
                 ATTR_start: 'True'}
            self.manager(MGR_CMD_CREATE, QUEUE, a, id='workq', expect=True)
            setdict.update({ATTR_dfltque: 'workq'})
        if reverthooks:
            hooks = self.status(HOOK, level=logging.DEBUG)
            hooks = [h['id'] for h in hooks]
            a = {ATTR_enable: 'false'}
            if len(hooks) > 0:
                self.manager(MGR_CMD_SET, MGR_OBJ_HOOK, a, hooks, expect=True)
        if revertqueues:
            self.status(QUEUE, level=logging.DEBUG)
            queues = []
            for (qname, qobj) in self.queues.items():
                # skip reservation queues. This syntax for Python 2.4
                # compatibility
                if (qname.startswith('R') or qname.startswith('S') or
                        qname == server_stat[ATTR_dfltque]):
                    continue
                qobj.revert_to_defaults()
                queues.append(qname)
                a = {ATTR_enable: 'false'}
                self.manager(MGR_CMD_SET, QUEUE, a, id=queues, expect=True)
            a = {ATTR_enable: 'True', ATTR_start: 'True'}
            self.manager(MGR_CMD_SET, MGR_OBJ_QUEUE, a,
                         id=server_stat[ATTR_dfltque], expect=True)
        if len(setdict) > 0:
            self.manager(MGR_CMD_SET, MGR_OBJ_SERVER, setdict)
        if revertresources:
            try:
                rescs = self.status(RSC)
                rescs = [r['id'] for r in rescs]
            except:
                rescs = []
            if len(rescs) > 0:
                self.manager(MGR_CMD_DELETE, RSC, id=rescs, expect=True)
        return True

    def save_configuration(self, outfile, mode='a'):
        """
        Save a server configuration, this includes:

          - server_priv/resourcedef

          - qmgr -c "print server"

          - qmgr -c "print sched"

          - qmgr -c "print hook"

        outfile - the output file to which onfiguration is saved

        mode - the mode in which to open outfile to save configuration. The
        first object being saved should open this file with 'w' and subsequent
        calls from other objects should save with mode 'a' or 'a+'. Defaults
        to a+

        Returns True on success, False on error
        """
        conf = {}
        sconf = {MGR_OBJ_SERVER: conf}

        rd = os.path.join(self.pbs_conf['PBS_HOME'], 'server_priv',
                          'resourcedef')
        self._save_config_file(conf, rd)

        qmgr = os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmgr')

        ret = self.du.run_cmd(self.client, [qmgr, '-c', 'p s'], sudo=True)
        if ret['rc'] != 0:
            return False
        else:
            conf['qmgr_print_server'] = ret['out']

        ret = self.du.run_cmd(self.hostname, [qmgr, '-c', 'p sched'],
                              sudo=True)
        if ret['rc'] != 0:
            return False
        else:
            conf['qmgr_print_sched'] = ret['out']

        ret = self.du.run_cmd(self.hostname, [qmgr, '-c', 'p h'], sudo=True)
        if ret['rc'] != 0:
            return False
        else:
            conf['qmgr_print_hook'] = ret['out']

        try:
            f = open(outfile, mode)
            cPickle.dump(sconf, f)
            f.close()
        except:
            self.logger.error('Error processing file ' + outfile)
            return False

        return True

    def load_configuration(self, infile):
        " load configuration from saved file infile "
        self.revert_to_defaults()
        self._load_configuration(infile, MGR_OBJ_SERVER)

    def get_hostname(self):
        " return the default server hostname "

        if self.get_op_mode() == PTL_CLI:
            return self.hostname
        return pbs_default()

    def _db_connect(self, db_access=None):
        if self._db_conn is None:
            if 'user' not in db_access or\
               'password' not in db_access:
                self.logger.error('missing credentials to access DB')
                return None

            if 'dbname' not in db_access:
                db_access['dbname'] = 'pbs_datastore'
            if 'port' not in db_access:
                db_access['port'] = '15007'

            if 'host' not in db_access:
                db_access['host'] = self.hostname

            user = db_access['user']
            dbname = db_access['dbname']
            port = db_access['port']
            password = db_access['password']
            host = db_access['host']

            cred = "host=%s dbname=%s user=%s password=%s port=%s" % \
                (host, dbname, user, password, port)
            self._db_conn = psycopg2.connect(cred)

        return self._db_conn

    def _db_server_host(self, cur=None, db_access=None):
        """
        Get the server host name from the database. The server host name is
        stored in the pbs.server table and not in pbs.server_attr.

        cur - Optional, a predefined cursor to use to operate on the DB

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        local_init = False

        if cur is None:
            conn = self._db_connect(db_access)
            local_init = True
            if conn is None:
                return None
            cur = conn.cursor()

        # obtain server name. The server hostname is stored in table
        # pbs.server
        cur.execute('SELECT sv_hostname from pbs.server')
        if local_init:
            conn.commit()

        tmp_query = cur.fetchone()
        if len(tmp_query) > 0:
            svr_host = tmp_query[0]
        else:
            svr_host = "unknown"
        return svr_host

    def status_db(self, obj_type=None, attrib=None, id=None, db_access=None,
                  logerr=True):
        """
        Status PBS objects from the SQL database

        obj_type - The type of object to query, one of the * objects,\
        Default: SERVER

        attrib - Attributes to query, can a string, a list, a dictionary\
        Default: None. All attributes will be queried

        id - An optional identifier, the name of the object to status

        db_access - information needed to access the database, can be either
        a file containing user, port, dbname, password info or a dictionary
        of key/value entries
        """
        if not PSYCOPG:
            self.logger.error('psycopg module unavailable, install from ' +
                              'http://initd.org/psycopg/ and retry')
            return None

        if not isinstance(db_access, dict):
            try:
                f = open(db_access, 'r')
            except IOError:
                self.logger.error('Unable to access ' + db_access)
                return None
            lines = f.readlines()
            db_access = {}
            for line in lines:
                (k, v) = line.split('=')
                db_access[k] = v

        conn = self._db_connect(db_access)
        if conn is None:
            return None

        cur = conn.cursor()

        stmt = []
        if obj_type == SERVER:
            stmt = ["SELECT sv_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.server_attr"]
            svr_host = self.hostname  # self._db_server_host(cur)
        elif obj_type == SCHED:
            stmt = ["SELECT sched_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.scheduler_attr"]
            # reuse server host name for sched host
            svr_host = self.hostname
        elif obj_type == JOB:
            stmt = ["SELECT ji_jobid,attr_name,attr_resource,attr_value " +
                    "FROM pbs.job_attr"]
            if id:
                id_stmt = ["ji_jobid='" + id + "'"]
        elif obj_type == QUEUE:
            stmt = ["SELECT qu_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.queue_attr"]
            if id:
                id_stmt = ["qu_name='" + id + "'"]
        elif obj_type == RESV:
            stmt = ["SELECT ri_resvid,attr_name,attr_resource,attr_value " +
                    "FROM pbs.resv_attr"]
            if id:
                id_stmt = ["ri_resvid='" + id + "'"]
        elif obj_type in (NODE, VNODE):
            stmt = ["SELECT nd_name,attr_name,attr_resource,attr_value " +
                    "FROM pbs.node_attr"]
            if id:
                id_stmt = ["nd_name='" + id + "'"]
        else:
            self.logger.error('status: object type not handled')
            return None

        if attrib or id:
            stmt += ["WHERE"]
            extra_stmt = []
            if attrib:
                if isinstance(attrib, dict):
                    attrs = attrib.keys()
                elif isinstance(attrib, list):
                    attrs = attrib
                elif isinstance(attrib, str):
                    attrs = attrib.split(',')
                for a in attrs:
                    extra_stmt += ["attr_name='" + a + "'"]
                stmt += [" OR ".join(extra_stmt)]
            if id:
                stmt += [" AND ", " AND ".join(id_stmt)]

        exec_stmt = " ".join(stmt)
        self.logger.debug('server: executing db statement: ' + exec_stmt)
        cur.execute(exec_stmt)
        conn.commit()
        _results = cur.fetchall()
        obj_dict = {}
        for _res in _results:
            if obj_type in (SERVER, SCHED):
                obj_name = svr_host
            else:
                obj_name = _res[0]
            if obj_name not in obj_dict:
                obj_dict[obj_name] = {'id': obj_name}
            attr = _res[1]
            if _res[2]:
                attr += '.' + _res[2]

            obj_dict[obj_name][attr] = _res[3]

        return obj_dict.values()

#
# Begin IFL Wrappers
#
    def status(self, obj_type=SERVER, attrib=None, id=None,
               extend=None, level=logging.INFO, db_access=None, runas=None,
               resolve_indirectness=False, logerr=True):
        """
        Stat any PBS object [queue, server, node, hook, job, resv, sched].
        If the Server is setup from diag input, see diag or diagmap member, the
        status calls are routed directly to the data on files from diag.

        The server can be queried either through the 'qstat' command line tool
        or through the wrapped PBS IFL api, see set_op_mode.

        Return a dictionary representation of a batch status object
        raises PbsStatsuError on error.

        obj_type - The type of object to query, one of the * objects.
        Default: SERVER

        attrib - Attributes to query, can be a string, a list, a dictionary.
        Default is to query all attributes.

        id - An optional id, the name of the object to status

        extend - Optional extension to the IFL call

        level - The logging level, defaults to INFO

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}

        runas - run stat as user

        resolve_indirectness - If True resolves indirect node resources values

        logerr - If True (default) logs run_cmd errors

        In addition to standard IFL stat call, this wrapper handles a few cases
        that aren't implicitly offered by pbs_stat*, those are for Hooks,
        Resources, and a formula evaluation.
        """

        prefix = 'status on ' + self.shortname
        if runas:
            prefix += ' as ' + str(runas)
        prefix += ': '
        self.logit(prefix, obj_type, attrib, id, level)

        bs = None
        bsl = []
        freebs = False
        # 2 - Special handling for gathering the job formula value.
        if attrib is not None and PTL_FORMULA in attrib:
            if (((isinstance(attrib, list) or isinstance(attrib, dict)) and
                 (len(attrib) == 1)) or
                    (isinstance(attrib, str) and len(attrib.split(',')) == 1)):
                bsl = self.status(
                    JOB, 'Resource_List.select', id=id, extend='t')
            if self.scheduler is None:
                self.scheduler = Scheduler(self.hostname)
            if 'log_filter' in self.scheduler.sched_config:
                _prev_filter = self.scheduler.sched_config['log_filter']
                if int(_prev_filter) & 2048:
                    self.scheduler.set_sched_config(
                        {'log_filter': 2048})
            self.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
            if id is None:
                _formulas = self.scheduler.job_formula()
            else:
                _formulas = {id: self.scheduler.job_formula(jobid=id)}
            if not int(_prev_filter) & 2048:
                self.scheduler.set_sched_config(
                    {'log_filter': int(_prev_filter)})

            if len(bsl) == 0:
                bsl = [{'id': id}]
            for _b in bsl:
                if _b['id'] in _formulas:
                    _b[PTL_FORMULA] = _formulas[_b['id']]
            return bsl

        # 3- Serve data from database if requested... and available for the
        # given object type
        if db_access and obj_type in (SERVER, SCHED, NODE, QUEUE, RESV, JOB):
            bsl = self.status_db(obj_type, attrib, id, db_access=db_access,
                                 logerr=logerr)

        # 4- Serve data from diag files
        elif obj_type in self.diagmap:
            if obj_type in (HOOK, PBS_HOOK):
                for f in self.diagmap[obj_type]:
                    _b = self.utils.file_to_dictlist(f, attrib)
                    if _b and 'hook_name' in _b[0]:
                        _b[0]['id'] = _b[0]['hook_name']
                    else:
                        _b[0]['id'] = os.path.basename(f)
                    if id is None or id == _b[0]['id']:
                        bsl.extend(_b)
            else:
                bsl = self.utils.file_to_dictlist(self.diagmap[obj_type],
                                                  attrib, id=id)
        # 6- Stat using PBS CLI commands
        elif self.get_op_mode() == PTL_CLI:
            tgt = self.client
            if obj_type in (JOB, QUEUE, SERVER):
                pcmd = [os.path.join(
                        self.client_conf['PBS_EXEC'],
                        'bin',
                        'qstat')]

                if extend:
                    pcmd += ['-' + extend]

                if obj_type == JOB:
                    pcmd += ['-f']
                    if id:
                        pcmd += [id]
                    else:
                        pcmd += ['@' + self.hostname]
                elif obj_type == QUEUE:
                    pcmd += ['-Qf']
                    if id:
                        if '@' not in id:
                            pcmd += [id + '@' + self.hostname]
                        else:
                            pcmd += [id]
                    else:
                        pcmd += ['@' + self.hostname]
                elif obj_type == SERVER:
                    pcmd += ['-Bf', self.hostname]

            elif obj_type in (NODE, VNODE, HOST):
                pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                     'pbsnodes')]
                pcmd += ['-s', self.hostname]
                if obj_type in (NODE, VNODE):
                    pcmd += ['-v']
                if id:
                    pcmd += [id]
                else:
                    pcmd += ['-a']
            elif obj_type == RESV:
                pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                     'pbs_rstat')]
                pcmd += ['-f']
                if id:
                    pcmd += [id]
            elif obj_type in (SCHED, PBS_HOOK, HOOK, RSC):
                try:
                    rc = self.manager(MGR_CMD_LIST, obj_type, attrib, id,
                                      runas=runas, level=level, logerr=logerr)
                except PbsManagerError, e:
                    rc = e.rc
                    # PBS bug, no hooks yields a return code of 1, we ignore
                    if obj_type != HOOK:
                        raise PbsStatusError(
                            rc=rc, rv=[], msg=self.geterrmsg())
                if rc == 0:
                    if obj_type == HOOK:
                        o = self.hooks
                    elif obj_type == PBS_HOOK:
                        o = self.pbshooks
                    elif obj_type == SCHED:
                        if self.scheduler is None:
                            return []
                        o = {'sched': self.scheduler}
                    elif obj_type == RSC:
                        o = self.resources
                    if id:
                        if id in o:
                            return [o[id].attributes]
                        else:
                            return None
                    return [h.attributes for h in o.values()]
                return []

            else:
                self.logger.error(self.logprefix + "unrecognized object type")
                raise PbsStatusError(rc=-1, rv=[],
                                     msg="unrecognized object type")
                return None

            # as_script is used to circumvent some shells that will not pass
            # along environment variables when invoking a command through sudo
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif obj_type == RESV and not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(tgt, pcmd, runas=runas, as_script=as_script,
                                  level=logging.INFOCLI, logerr=logerr)
            o = ret['out']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if ret['rc'] != 0:
                raise PbsStatusError(rc=ret['rc'], rv=[], msg=self.geterrmsg())

            bsl = self.utils.convert_to_dictlist(o, attrib, mergelines=True)

        # 7- Stat with impersonation over PBS IFL swig-wrapped API
        elif runas is not None:
            _data = {'obj_type': obj_type, 'attrib': attrib, 'id': id}
            bsl = self.pbs_api_as('status', user=runas, data=_data,
                                  extend=extend)
        else:
            # 8- Stat over PBS IFL API
            #
            # resources are special attributes, all resources are queried as
            # a single attribute.
            # e.g. querying the resources_available attribute returns all
            # resources such as ncpus, mem etc. when querying for
            # resources_available.ncpus and resources_available.mem only query
            # resources_available once and retrieve the resources desired from
            # there
            if isinstance(attrib, dict):
                attribcopy = {}
                restype = []
                for k, v in attrib.items():
                    if isinstance(v, tuple):
                        # SET requires a special handling because status may
                        # have been called through counter to count the number
                        # of objects have a given attribute set, in this case
                        # we set the attribute to an empty string rather than
                        # the number of elements requested. This is a
                        # side-effect of the way pbs_statjob works
                        if v[0] in (SET, MATCH_RE):
                            v = ''
                        else:
                            v = v[1]
                    if callable(v):
                        v = ''
                    if '.' in k:
                        _r = k.split('.')[0]
                        if _r not in restype:
                            attribcopy[k] = v
                            restype.append(_r)
                    else:
                        attribcopy[k] = v
            elif isinstance(attrib, list):
                attribcopy = []
                for k in attrib:
                    if '.' in k:
                        _found = False
                        for _e in attribcopy:
                            _r = k.split('.')[0]
                            if _r == _e.split('.')[0]:
                                _found = True
                                break
                        if not _found:
                            attribcopy.append(k)
                    else:
                        attribcopy.append(k)
            else:
                attribcopy = attrib

            a = self.utils.convert_to_attrl(attribcopy)
            c = self._connect(self.hostname)

            if obj_type == JOB:
                bs = pbs_statjob(c, id, a, extend)
            elif obj_type == QUEUE:
                bs = pbs_statque(c, id, a, extend)
            elif obj_type == SERVER:
                bs = pbs_statserver(c, a, extend)
            elif obj_type == HOST:
                bs = pbs_statnode(c, id, a, extend)
            elif obj_type == VNODE:
                bs = pbs_statvnode(c, id, a, extend)
            elif obj_type == RESV:
                bs = pbs_statresv(c, id, a, extend)
            elif obj_type == SCHED:
                bs = pbs_statsched(c, a, extend)
            elif obj_type == RSC:
                # up to PBSPro 12.3 pbs_statrsc was not in pbs_ifl.h
                bs = pbs_statrsc(c, id, a, extend)
            elif obj_type in (HOOK, PBS_HOOK):
                if os.getuid() != 0:
                    try:
                        rc = self.manager(MGR_CMD_LIST, obj_type, attrib,
                                          id, level=level)
                        if rc == 0:
                            if id:
                                if (obj_type == HOOK and
                                        id in self.hooks):
                                    return [self.hooks[id].attributes]
                                elif (obj_type == PBS_HOOK and
                                      id in self.pbshooks):
                                    return [self.pbshooks[id].attributes]
                                else:
                                    return None
                            if obj_type == HOOK:
                                return [h.attributes for h in
                                        self.hooks.values()]
                            elif obj_type == PBS_HOOK:
                                return [h.attributes for h in
                                        self.pbshooks.values()]
                    except:
                        pass
                else:
                    bs = pbs_stathook(c, id, a, extend)
            else:
                self.logger.error(self.logprefix +
                                  "unrecognized object type " + str(obj_type))

            freebs = True
            err = self.geterrmsg()
            self._disconnect(c)

            if err:
                raise PbsStatusError(rc=-1, rv=[], msg=err)

            if not isinstance(bs, list):
                bsl = self.utils.batch_status_to_dictlist(bs, attrib)
            else:
                bsl = self.utils.filter_batch_status(bs, attrib)

        # Update each object's dictionary with corresponding attributes and
        # values
        self.update_attributes(obj_type, bsl)

        # Hook stat is done through CLI, no need to free the batch_status
        if (not isinstance(bs, list) and freebs and
                obj_type not in (HOOK, PBS_HOOK) and os.getuid() != 0):
            pbs_statfree(bs)

        # 9- Resolve indirect resources
        if obj_type in (NODE, VNODE) and resolve_indirectness:
            nodes = {}
            for _b in bsl:
                for k, v in _b.items():
                    if v.startswith('@'):
                        if v[1:] in nodes:
                            _b[k] = nodes[v[1:]][k]
                        else:
                            for l in bsl:
                                if l['id'] == v[1:]:
                                    nodes[k] = l[k]
                                    _b[k] = l[k]
                                    break
            del nodes
        return bsl

    def submit_interactive_job(self, job, cmd):
        """
        submit an interactive job. Returns a job identifier or raises
        PbsSubmitError on error

        job - the job object. The job must have the attribute 'interactive_job'
        populated. That attribute is a list of tuples of the form:

        (<command>, <expected output>, <...>)

        for example to send the command
        hostname and expect 'myhost.mydomain' one would set:

        job.interactive_job = [('hostname', 'myhost.mydomain')]

        If more than one lines are expected they are appended to the tuple.

        cmd - The command to run to submit the interactive job
        """
        ij = InteractiveJob(job, cmd, self.hostname)
        # start the interactive job submission thread and wait to pickup the
        # actual job identifier
        ij.start()
        while ij.jobid is None:
            continue
        return ij.jobid

    def submit(self, obj, script=None, extend=None, submit_dir=None):
        """
        Submit a job or reservation. Returns a job identifier or raises
        PbsSubmitError on error

        obj - The Job or Reservation instance to submit

        script - Path to a script to submit. Default: None as an executable\
        /bin/sleep 100 is submitted

        extend - Optional extension to the IFL call. see pbs_ifl.h

        submit_dir - directory from which job is submitted. Defaults to
        temporary directory
        """

        _interactive_job = False
        as_script = False
        rc = None

        if isinstance(obj, Job):
            if script is None and obj.script is not None:
                script = obj.script
            if ATTR_inter in obj.attributes:
                _interactive_job = True
                if ATTR_executable in obj.attributes:
                    del obj.attributes[ATTR_executable]
                if ATTR_Arglist in obj.attributes:
                    del obj.attributes[ATTR_Arglist]
        elif not isinstance(obj, Reservation):
            m = self.logprefix + "unrecognized object type"
            self.logger.error(m)
            return None

        if submit_dir is None:
            submit_dir = tempfile.gettempdir()

        cwd = os.getcwd()
        os.chdir(submit_dir)
        c = None
        # 1- Submission using the command line tools
        if self.get_op_mode() == PTL_CLI:
            exclude_attrs = []  # list of attributes to not convert to CLI
            if isinstance(obj, Job):
                runcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                       'qsub')]
            elif isinstance(obj, Reservation):
                runcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                       'pbs_rsub')]
                if ATTR_resv_start in obj.custom_attrs:
                    start = obj.custom_attrs[ATTR_resv_start]
                    obj.custom_attrs[ATTR_resv_start] = \
                        self.utils.convert_seconds_to_resvtime(start)
                if ATTR_resv_end in obj.custom_attrs:
                    end = obj.custom_attrs[ATTR_resv_end]
                    obj.custom_attrs[ATTR_resv_end] = \
                        self.utils.convert_seconds_to_resvtime(end)
                if ATTR_resv_timezone in obj.custom_attrs:
                    exclude_attrs += [ATTR_resv_timezone, ATTR_resv_standing]
                    # handling of impersonation differs widely across OS's,
                    # when setting PBS_TZID we standardize on running the cmd
                    # as a script instead of customizing for each OS flavor
                    _tz = obj.custom_attrs[ATTR_resv_timezone]
                    runcmd = ['PBS_TZID=' + _tz] + runcmd
                    as_script = True
                    if ATTR_resv_rrule in obj.custom_attrs:
                        _rrule = obj.custom_attrs[ATTR_resv_rrule]
                        if _rrule[0] not in ("'", '"'):
                            _rrule = "'" + _rrule + "'"
                        obj.custom_attrs[ATTR_resv_rrule] = _rrule

            if not self._is_local:
                if ATTR_queue not in obj.attributes:
                    runcmd += ['-q@' + self.hostname]
                elif '@' not in obj.attributes[ATTR_queue]:
                    curq = obj.attributes[ATTR_queue]
                    runcmd += ['-q' + curq + '@' + self.hostname]
                if obj.custom_attrs and (ATTR_queue in obj.custom_attrs):
                    del obj.custom_attrs[ATTR_queue]

            _conf = self.default_client_pbs_conf
            cmd = self.utils.convert_to_cli(obj.custom_attrs, IFL_SUBMIT,
                                            self.hostname, dflt_conf=_conf,
                                            exclude_attrs=exclude_attrs)

            if cmd is None:
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
                return None

            runcmd += cmd

            if script:
                runcmd += [script]
            else:
                if ATTR_executable in obj.attributes:
                    runcmd += ['--', obj.attributes[ATTR_executable]]
                    if ((ATTR_Arglist in obj.attributes) and
                            (obj.attributes[ATTR_Arglist] is not None)):
                        args = obj.attributes[ATTR_Arglist]
                        arglist = self.utils.convert_arglist(args)
                        if arglist is None:
                            try:
                                os.chdir(cwd)
                            except OSError:
                                pass
                            return None
                        runcmd += [arglist]
            if obj.username != self.current_user:
                runas = obj.username
            else:
                runas = None

            if _interactive_job:
                ijid = self.submit_interactive_job(obj, runcmd)
                try:
                    os.chdir(cwd)
                except OSError:
                    pass
                return ijid

            if not self.default_client_pbs_conf:
                runcmd = [
                    'PBS_CONF_FILE=' + self.client_pbs_conf_file] + runcmd
                as_script = True

            ret = self.du.run_cmd(self.client, runcmd, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script,
                                  logerr=False)
            if ret['rc'] != 0:
                objid = None
            else:
                objid = ret['out'][0]
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc = ret['rc']

        # 2- Submission with impersonation over API
        elif obj.username != self.current_user:
            # submit job as a user requires setting uid to that user. It's
            # done in a separate process
            obj.set_variable_list(obj.username, submit_dir)
            obj.set_attributes()
            if (obj.script is not None and not self._is_local):
                # This copy assumes that the file system layout on the
                # remote host is identical to the local host. When not
                # the case, this code will need to be updated to copy
                # to a known remote location and update the obj.script
                self.du.run_copy(self.hostname, obj.script, obj.script)
                os.remove(obj.script)
            objid = self.pbs_api_as('submit', obj, user=obj.username,
                                    extend=extend)
        # 3- Submission as current user over API
        else:
            c = self._connect(self.hostname)

            if isinstance(obj, Job):
                if script:
                    if ATTR_o not in obj.attributes:
                        obj.attributes[ATTR_o] = (self.hostname + ':' +
                                                  obj.script + '.o')
                    if ATTR_e not in obj.attributes:
                        obj.attributes[ATTR_e] = (self.hostname + ':' +
                                                  obj.script + '.e')
                    sc = os.path.basename(script)
                    obj.unset_attributes([ATTR_executable, ATTR_Arglist])
                    if ATTR_N not in obj.custom_attrs:
                        obj.attributes[ATTR_N] = sc
                if ATTR_queue in obj.attributes:
                    destination = obj.attributes[ATTR_queue]
                    # queue must be removed otherwise will cause the submit
                    # to fail silently
                    del obj.attributes[ATTR_queue]
                else:
                    destination = None

                    if (ATTR_o not in obj.attributes or
                            ATTR_e not in obj.attributes):
                        fn = self.utils.random_str(
                            length=4, prefix='PtlPbsJob')
                        tmp = self.du.get_tempdir(self.hostname)
                        fn = os.path.join(tmp, fn)
                    if ATTR_o not in obj.attributes:
                        obj.attributes[ATTR_o] = (self.hostname + ':' +
                                                  fn + '.o')
                    if ATTR_e not in obj.attributes:
                        obj.attributes[ATTR_e] = (self.hostname + ':' +
                                                  fn + '.e')

                obj.attropl = self.utils.dict_to_attropl(obj.attributes)
                objid = pbs_submit(c, obj.attropl, script, destination,
                                   extend)
            elif isinstance(obj, Reservation):
                if ATTR_resv_duration in obj.attributes:
                    # reserve_duration is not a valid attribute, the API call
                    # will get rejected if it is used
                    wlt = ATTR_l + '.walltime'
                    obj.attributes[wlt] = obj.attributes[ATTR_resv_duration]
                    del obj.attributes[ATTR_resv_duration]

                obj.attropl = self.utils.dict_to_attropl(obj.attributes)
                objid = pbs_submit_resv(c, obj.attropl, extend)

        prefix = 'submit to ' + self.shortname + ' as '
        if isinstance(obj, Job):
            self.logit(prefix + '%s: ' % obj.username, JOB, obj.custom_attrs,
                       objid)
            if obj.script_body:
                self.logger.log(logging.INFOCLI, 'job script ' + script +
                                '\n---\n' + obj.script_body + '\n---')
            if objid is not None:
                self.jobs[objid] = obj
        elif isinstance(obj, Reservation):
            # Reservations without -I option return as 'R123 UNCONFIRMED'
            # so split to get the R123 only

            self.logit(prefix + '%s: ' % obj.username, RESV, obj.attributes,
                       objid)
            if objid is not None:
                objid = objid.split()[0]
                self.reservations[objid] = obj

        if objid is not None:
            obj.server[self.hostname] = objid
        else:
            try:
                os.chdir(cwd)
            except OSError:
                pass
            raise PbsSubmitError(rc=rc, rv=None, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        try:
            os.chdir(cwd)
        except OSError:
            pass

        return objid

    def deljob(self, id=None, extend=None, runas=None, wait=False,
               logerr=True, attr_W=None):
        """
        delete a single job or list of jobs specified by id
        raises PbsDeljobError on error

        id - The identifier(s) of the jobs to delete

        extend - Optional parameters to pass along to PBS

        runas - run as user

        wait - Set to True to wait for job(s) to no longer be reported
        by PBS. False by default

        logerr - Whether to log errors. Defaults to True.

        attr_w - -W args to qdel (Only for cli mode)
        """
        prefix = 'delete job on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ', '.join(id)
        self.logger.info(prefix)
        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qdel')]
            if extend is not None:
                pcmd += self.utils.convert_to_cli(extend, op=IFL_DELETE,
                                                  hostname=self.hostname)
            if attr_W is not None:
                pcmd += ['-W']
                if attr_W != PTL_NOARG:
                    pcmd += [attr_W]
            if id is not None:
                pcmd += id
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, logerr=logerr,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('deljob', id, user=runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in id:
                tmp_rc = pbs_deljob(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsDeljobError(rc=rc, rv=False, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)
        if self.jobs is not None:
            for j in id:
                if j in self.jobs:
                    if self.jobs[j].interactive_handle is not None:
                        self.jobs[j].interactive_handle.close()
                    del self.jobs[j]
        if c:
            self._disconnect(c)
        if wait:
            for oid in id:
                self.expect(JOB, 'queue', id=oid, op=UNSET, runas=runas,
                            level=logging.DEBUG)
        return rc

    def delresv(self, id=None, extend=None, runas=None, wait=False,
                logerr=True):
        """
        delete a single job or list of jobs specified by id
        raises PbsDeljobError on error

        id - The identifier(s) of the jobs to delete

        extend - Optional parameters to pass along to PBS

        runas - run as user

        wait - Set to True to wait for job(s) to no longer be reported
        by PBS. False by default

        logerr - Whether to log errors. Defaults to True.
        """
        prefix = 'delete resv on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ', '.join(id)
        self.logger.info(prefix)
        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'pbs_rdel')]
            if id is not None:
                pcmd += id
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            elif not self._is_local:
                pcmd = ['PBS_SERVER=' + self.hostname] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, logerr=logerr,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('delresv', id, user=runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in id:
                tmp_rc = pbs_delresv(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsDelresvError(rc=rc, rv=False, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)
        if self.reservations is not None:
            for j in id:
                if j in self.reservations:
                    del self.reservations[j]
        if c:
            self._disconnect(c)
        if wait:
            for oid in id:
                self.expect(RESV, 'queue', id=oid, op=UNSET, runas=runas,
                            level=logging.DEBUG)
        return rc

    def delete(self, id=None, extend=None, runas=None, wait=False,
               logerr=True):
        """
        delete a single job or list of jobs specified by id
        raises PbsDeleteError on error

        id - The identifier(s) of the jobs/resvs to delete

        extend - Optional parameters to pass along to PBS

        runas - run as user

        wait - Set to True to wait for job(s)/resv(s) to no longer be reported
        by PBS. False by default

        logerr - Whether to log errors. Defaults to True.
        """
        prefix = 'delete on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if id is not None:
            if not isinstance(id, list):
                id = id.split(',')
            prefix += ','.join(id)
        if extend is not None:
            prefix += ' with ' + str(extend)
        self.logger.info(prefix)

        if not len(id) > 0:
            return 0

        obj_type = {}
        for j in id:
            if j[0] in ('R', 'S'):
                obj_type[j] = RESV
                try:
                    rc = self.delresv(j, extend, runas, logerr=logerr)
                except PbsDelresvError, e:
                    rc = e.rc
                    msg = e.msg
                    rv = e.rv
            else:
                obj_type[j] = JOB
                try:
                    rc = self.deljob(j, extend, runas, logerr=logerr)
                except PbsDeljobError, e:
                    rc = e.rc
                    msg = e.msg
                    rv = e.rv

        if rc != 0:
            raise PbsDeleteError(rc=rc, rv=rv, msg=msg)

        if wait:
            for oid in id:
                self.expect(obj_type[oid], 'queue', id=oid, op=UNSET,
                            runas=runas, level=logging.DEBUG)

        return rc

    def select(self, attrib=None, extend=None, runas=None, logerr=True):
        """
        Select jobs that match attributes list or all jobs if no attributes
        raises PbsSelectError on error

        attrib - A string, list, or dictionary of attributes

        extend - the extended attributes to pass to select

        runas - run as user

        logerr - If True (default) logs run_cmd errors

        Return a list of job identifiers that match the attributes specified
        """
        prefix = "select on " + self.shortname
        if runas is not None:
            prefix += " as " + str(runas)
        prefix += ": "
        if attrib is None:
            s = PTL_ALL
        elif not isinstance(attrib, dict):
            self.logger.error(prefix + "attributes must be a dictionary")
            return
        else:
            s = str(attrib)
        self.logger.info(prefix + s)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'],
                                 'bin', 'qselect')]

            cmd = self.utils.convert_to_cli(attrib, op=IFL_SELECT,
                                            hostname=self.hostname)
            if extend is not None:
                pcmd += ['-' + extend]

            if not self._is_local and ((attrib is None) or
                                       (ATTR_queue not in attrib)):
                pcmd += ['-q', '@' + self.hostname]

            pcmd += cmd
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsSelectError(rc=self.last_rc, rv=False,
                                     msg=self.geterrmsg())
            jobs = ret['out']
            # command returns no jobs as empty, since we expect a valid id,
            # we reset the jobs to an empty array
            if len(jobs) == 1 and jobs[0] == '':
                jobs = []
        elif runas is not None:
            jobs = self.pbs_api_as('select', user=runas, data=attrib,
                                   extend=extend)
        else:
            attropl = self.utils.convert_to_attropl(attrib, op=EQ)
            c = self._connect(self.hostname)
            jobs = pbs_selectjob(c, attropl, extend)
            err = self.geterrmsg()
            if err:
                raise PbsSelectError(rc=-1, rv=False, msg=err,
                                     post=self._disconnect, conn=c)
            self._disconnect(c)

        return jobs

    def selstat(self, select_list, rattrib, runas=None, extend=None):
        """
        stat and filter jobs attributes.

        select_list - The filter criteria

        rattrib - The attributes to query

        runas - run as user

        No CLI counterpart for this call
        """

        attrl = self.utils.convert_to_attrl(rattrib)
        attropl = self.utils.convert_to_attropl(select_list)

        c = self._connect(self.hostname)
        bs = pbs_selstat(c, attropl, attrl, extend)
        self._disconnect(c)
        return bs

    def manager(self, cmd, obj_type, attrib=None, id=None, extend=None,
                expect=False, max_attempts=None, level=logging.INFO,
                sudo=None, runas=None, logerr=True):
        """
        issue a management command to the server, e.g to set an attribute

        Returns the return code of qmgr/pbs_manager() on success, if expect
        is set to True, the return value is that of the call to expect.
        Raises PbsManagerError on error

        cmd - The command to issue, MGR_CMD_[SET,UNSET, LIST,...] see pbs_ifl.h

        obj_type - The type of object to query, one of the * objects

        attrib - Attributes to operate on, can be a string, a list,
        a dictionary

        id - The name or list of names of the object(s) to act upon.

        extend - Optional extension to the IFL call. see pbs_ifl.h

        expect - If set to True, query the server expecting the value to be\
        accurately reflected. Defaults to False

        max_attempts - Sets a maximum number of attempts to call expect with.
        level - logging level

        sudo - If True, run the manager command as super user. Defaults to
        None. Some attribute settings should be run with sudo set to
        True, those are acl_roots, job_sort_formula, hook operations,
        no_sched_hook_event, in those cases, setting sudo to False is
        only needed for testing purposes

        runas - run as user

        logerr - If False, CLI commands do not log error, i.e. silent mode

        When expect is False, return the value, 0/!0 returned by pbs_manager

        When expect is True, return the value, True/False, returned by expect
        """

        if isinstance(id, str):
            oid = id.split(',')
        else:
            oid = id

        self.logit('manager on ' + self.shortname +
                   [' as ' + str(runas), ''][runas is None] + ': ' +
                   PBS_CMD_MAP[cmd] + ' ', obj_type, attrib, oid, level=level)

        c = None  # connection handle

        if (self.get_op_mode() == PTL_CLI or
            sudo is not None or
            obj_type in (HOOK, PBS_HOOK) or
            (attrib is not None and ('job_sort_formula' in attrib or
                                     'acl_roots' in attrib or
                                     'no_sched_hook_event' in attrib))):

            execcmd = [PBS_CMD_MAP[cmd], PBS_OBJ_MAP[obj_type]]

            if oid is not None:
                if cmd == MGR_CMD_DELETE and obj_type == NODE and oid[0] == "":
                    oid[0] = "@default"
                execcmd += [",".join(oid)]

            if attrib is not None and cmd != MGR_CMD_LIST:
                if cmd == MGR_CMD_IMPORT:
                    execcmd += [attrib['content-type'],
                                attrib['content-encoding'],
                                attrib['input-file']]
                else:
                    if isinstance(attrib, (dict, OrderedDict)):
                        kvpairs = []
                        for k, v in attrib.items():
                            if isinstance(v, tuple):
                                if v[0] == INCR:
                                    op = '+='
                                elif v[0] == DECR:
                                    op = '-='
                                else:
                                    msg = 'Invalid operation: %s' % (v[0])
                                    raise PbsManagerError(rc=1, rv=False,
                                                          msg=msg)
                                v = v[1]
                            else:
                                op = '='
                            # handle string arrays as double quotes if
                            # not already set:
                            if isinstance(v, str) and ',' in v and v[0] != '"':
                                v = '"' + v + '"'
                            kvpairs += [str(k) + op + str(v)]
                        if kvpairs:
                            execcmd += [",".join(kvpairs)]
                            del kvpairs
                    elif isinstance(attrib, list):
                        execcmd += [",".join(attrib)]
                    elif isinstance(attrib, str):
                        execcmd += [attrib]

            if not self.default_pbs_conf or not self.default_client_pbs_conf:
                as_script = True
            else:
                as_script = False

            if not self._is_local or as_script:
                execcmd = '\'' + " ".join(execcmd) + '\''
            else:
                execcmd = " ".join(execcmd)

            # Hooks can only be queried as a privileged user on the host where
            # the server is running, care must be taken to use the appropriate
            # path to qmgr and appropriate escaping sequences
            # VERSION INFO: no_sched_hook_event introduced in 11.3.120 only
            if sudo is None:
                if (obj_type in (HOOK, PBS_HOOK) or
                    (attrib is not None and
                     ('job_sort_formula' in attrib or
                      'acl_roots' in attrib or
                      'no_sched_hook_event' in attrib))):
                    sudo = True
                else:
                    sudo = False

            pcmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'bin', 'qmgr'),
                    '-c', execcmd]

            if as_script:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd

            ret = self.du.run_cmd(self.hostname, pcmd, sudo=sudo, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script,
                                  logerr=logerr)
            rc = ret['rc']
            # NOTE: workaround the fact that qmgr overloads the return code in
            # cases where the list returned is empty an error flag is set even
            # through there is no error. Handled here by checking if there is
            # no err and out message, in which case return code is set to 0
            if rc != 0 and (ret['out'] == [''] and ret['err'] == ['']):
                rc = 0
            if rc == 0:
                if cmd == MGR_CMD_LIST:
                    bsl = self.utils.convert_to_dictlist(ret['out'], attrib,
                                                         mergelines=False)
                    self.update_attributes(obj_type, bsl)
            else:
                # Need to rework setting error, this is not thread safe
                self.last_error = ret['err']
            self.last_rc = ret['rc']
        elif runas is not None:
            _data = {'cmd': cmd, 'obj_type': obj_type, 'attrib': attrib,
                     'id': oid}
            rc = self.pbs_api_as('manager', user=runas, data=_data,
                                 extend=extend)
        else:
            a = self.utils.convert_to_attropl(attrib, cmd)
            c = self._connect(self.hostname)
            rc = 0
            if obj_type == SERVER and oid is None:
                oid = [self.hostname]
            if oid is None:
                # server will run strlen on id, it can not be NULL
                oid = ['']
            if cmd == MGR_CMD_LIST:
                if oid is None:
                    bsl = self.status(obj_type, attrib, oid, extend)
                else:
                    bsl = None
                    for i in oid:
                        tmpbsl = self.status(obj_type, attrib, i, extend)
                        if tmpbsl is None:
                            rc = 1
                        else:
                            if bsl is None:
                                bsl = tmpbsl
                            else:
                                bsl += tmpbsl
            else:
                rc = 0
                if oid is None:
                    rc = pbs_manager(c, cmd, obj_type, i, a, extend)
                else:
                    for i in oid:
                        tmprc = pbs_manager(c, cmd, obj_type, i, a, extend)
                        if tmprc != 0:
                            rc = tmprc
                            break
                    if rc == 0:
                        rc = tmprc

        if cmd == MGR_CMD_DELETE and oid is not None:
            for i in oid:
                if obj_type == MGR_OBJ_HOOK and i in self.hooks:
                    del self.hooks[i]
                if obj_type in (NODE, VNODE) and i in self.nodes:
                    del self.nodes[i]
                if obj_type == MGR_OBJ_QUEUE and i in self.queues:
                    del self.queues[i]
                if obj_type == MGR_OBJ_RSC and i in self.resources:
                    del self.resources[i]

        if rc != 0:
            raise PbsManagerError(rv=False, rc=rc, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)

        if c is not None:
            self._disconnect(c)

        if expect:
            if obj_type in (NODE, HOST):
                obj_type = VNODE
            if cmd in PBS_CMD_TO_OP:
                op = PBS_CMD_TO_OP[cmd]
            else:
                op = EQ

            if oid is None:
                return self.expect(obj_type, attrib, oid, op=op,
                                   max_attempts=max_attempts)
            for i in oid:
                rc = self.expect(obj_type, attrib, i, op=op,
                                 max_attempts=max_attempts)
                if not rc:
                    break
        return rc

    def sigjob(self, jobid=None, signal=None, extend=None, runas=None,
               logerr=True):
        """
        Send a signal to a job. Raises PbsSignalError on error.

        jobid - identifier of the job or list of jobs to send the signal to

        signal - The signal to send to the job, see pbs_ifl.h

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """

        prefix = 'signal on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if signal is not None:
            prefix += ' with signal = ' + str(signal)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qsig')]
            if signal is not None:
                pcmd += ['-s']
                if signal != PTL_NOARG:
                    pcmd += [str(signal)]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('sigjob', jobid, runas, data=signal)
        else:
            c = self._connect(self.hostname)
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_sigjob(c, ajob, signal, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsSignalError(rc=rc, rv=False, msg=self.geterrmsg(),
                                 post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def msgjob(self, jobid=None, to_file=None, msg=None, extend=None,
               runas=None, logerr=True):
        """
        Send a message to a job. Raises PbsMessageError on error.

        jobid - identifier of the job or list of jobs to send the message to

        msg - The message to send to the job

        to_file - one of MSG_ERR or MSG_OUT or MSG_ERR|MSG_OUT

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'msgjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if to_file is not None:
            prefix += ' with to_file = '
            if MSG_ERR == to_file:
                prefix += 'MSG_ERR'
            elif MSG_OUT == to_file:
                prefix += 'MSG_OUT'
            elif MSG_OUT | MSG_ERR == to_file:
                prefix += 'MSG_ERR|MSG_OUT'
            else:
                prefix += str(to_file)
        if msg is not None:
            prefix += ' msg = %s' % (str(msg))
        if extend is not None:
            prefix += ' extend = %s' % (str(extend))
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmsg')]
            if to_file is not None:
                if MSG_ERR == to_file:
                    pcmd += ['-E']
                elif MSG_OUT == to_file:
                    pcmd += ['-O']
                elif MSG_OUT | MSG_ERR == to_file:
                    pcmd += ['-E', '-O']
                else:
                    pcmd += ['-' + str(to_file)]
            if msg is not None:
                pcmd += [msg]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            data = {'msg': msg, 'to_file': to_file}
            rc = self.pbs_api_as('msgjob', jobid, runas, data=data,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            for ajob in jobid:
                tmp_rc = pbs_msgjob(c, ajob, to_file, msg, extend)
                if tmp_rc != 0:
                    rc = tmp_rc

        if rc != 0:
            raise PbsMessageError(rc=rc, rv=False, msg=self.geterrmsg(),
                                  post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def alterjob(self, jobid=None, attrib=None, extend=None, runas=None,
                 logerr=True):
        """
        Alter attributes associated to a job. Raises PbsAlterError on error.

        jobid - identifier of the job or list of jobs to operate on

        attrib - A dictionary of attributes to set

        extend - extend options

        runas - run as user

        logerr - If False, CLI commands do not log error, i.e. silent mode
        """
        prefix = 'alter on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if attrib is not None:
            prefix += ' %s' % (str(attrib))
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qalter')]
            if attrib is not None:
                _conf = self.default_client_pbs_conf
                pcmd += self.utils.convert_to_cli(attrib, op=IFL_ALTER,
                                                  hostname=self.client,
                                                  dflt_conf=_conf)
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('alterjob', jobid, runas, data=attrib)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            a = self.utils.convert_to_attrl(attrib)
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_alterjob(c, ajob, a, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsAlterError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def holdjob(self, jobid=None, holdtype=None, extend=None, runas=None,
                logerr=True):
        """
        Hold a job. Raises PbsHoldError on error.

        jobid - identifier of the job or list of jobs to hold

        holdtype - The type of hold to put on the job

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'holdjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if holdtype is not None:
            prefix += ' with hold_list = %s' % (holdtype)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qhold')]
            if holdtype is not None:
                pcmd += ['-h']
                if holdtype != PTL_NOARG:
                    pcmd += [holdtype]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  logerr=logerr, as_script=as_script,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('holdjob', jobid, runas, data=holdtype,
                                 logerr=logerr)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_holdjob(c, ajob, holdtype, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsHoldError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def rlsjob(self, jobid, holdtype, extend=None, runas=None, logerr=True):
        """
        Release a job. Raises PbsReleaseError on error.

        jobid - job or list of jobs to release

        holdtype - The type of hold to release on the job

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'release on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if holdtype is not None:
            prefix += ' with hold_list = %s' % (holdtype)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qrls')]
            if holdtype is not None:
                pcmd += ['-h']
                if holdtype != PTL_NOARG:
                    pcmd += [holdtype]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('rlsjob', jobid, runas, data=holdtype)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_rlsjob(c, ajob, holdtype, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsHoldError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def rerunjob(self, jobid=None, extend=None, runas=None, logerr=True):
        """
        Rerun a job. Raises PbsRerunError on error.

        jobid - job or list of jobs to release

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'rerun on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if extend is not None:
            prefix += extend
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qrerun')]
            if extend:
                pcmd += ['-W', extend]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('rerunjob', jobid, runas, extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                tmp_rc = pbs_rerunjob(c, ajob, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsRerunError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def orderjob(self, jobid1=None, jobid2=None, extend=None, runas=None,
                 logerr=True):
        """
        reorder position of jobid1 and jobid2. Raises PbsOrderJob on error.

        jobid1 - first jobid

        jobid2 - second jobid

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'orderjob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        prefix += str(jobid1) + ', ' + str(jobid2)
        if extend is not None:
            prefix += ' ' + str(extend)
        self.logger.info(prefix)

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qorder')]
            if jobid1 is not None:
                pcmd += [jobid1]
            if jobid2 is not None:
                pcmd += [jobid2]
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('orderjob', jobid1, runas, data=jobid2,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = pbs_orderjob(c, jobid1, jobid2, extend)
        if rc != 0:
            raise PbsOrderError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def runjob(self, jobid=None, location=None, async=False, extend=None,
               runas=None, logerr=False):
        """
        Run a job on given nodes. Raises PbsRunError on error.

        jobid - job or list of jobs to run

        location - An execvnode on which to run the job

        async - If true the call will return immediately assuming success.

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        if async:
            prefix = 'Async run on ' + self.shortname
        else:
            prefix = 'run on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if location is not None:
            prefix += ' with location = %s' % (location)
        self.logger.info(prefix)

        if self.has_diag:
            return 0

        c = None
        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qrun')]
            if async:
                pcmd += ['-a']
            if location is not None:
                pcmd += ['-H']
                if location != PTL_NOARG:
                    pcmd += [location]
            if jobid:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as(
                'runjob', jobid, runas, data=location, extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            rc = 0
            for ajob in jobid:
                if async:
                    tmp_rc = pbs_asyrunjob(c, ajob, location, extend)
                else:
                    tmp_rc = pbs_runjob(c, ajob, location, extend)
                if tmp_rc != 0:
                    rc = tmp_rc
        if rc != 0:
            raise PbsRunError(rc=rc, rv=False, msg=self.geterrmsg(),
                              post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def movejob(self, jobid=None, destination=None, extend=None, runas=None,
                logerr=True):
        """
        Move a job or list of job ids to a given destination queue.
        Raises PbsMoveError on error.

        jobid - A job or list of job ids to move

        destination - The destination queue@server

        extend - extend options

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'movejob on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if jobid is not None:
            if not isinstance(jobid, list):
                jobid = jobid.split(',')
            prefix += ', '.join(jobid)
        if destination is not None:
            prefix += ' destination = %s' % (destination)
        self.logger.info(prefix)

        c = None
        rc = 0

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qmove')]
            if destination is not None:
                pcmd += [destination]
            if jobid is not None:
                pcmd += jobid
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  logerr=logerr, as_script=as_script,
                                  level=logging.INFOCLI)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            rc = self.pbs_api_as('movejob', jobid, runas, data=destination,
                                 extend=extend)
        else:
            c = self._connect(self.hostname)
            if c < 0:
                return c
            for ajob in jobid:
                tmp_rc = pbs_movejob(c, ajob, destination, extend)
                if tmp_rc != 0:
                    rc = tmp_rc

        if rc != 0:
            raise PbsMoveError(rc=rc, rv=False, msg=self.geterrmsg(),
                               post=self._disconnect, conn=c)

        if c:
            self._disconnect(c)

        return rc

    def qterm(self, manner=None, extend=None, server_name=None, runas=None,
              logerr=True):
        """
        Terminate the pbs_server daemon

        manner - one of (SHUT_IMMEDIATE | SHUT_DELAY | SHUT_QUICK) and can be\
                 combined with SHUT_WHO_SCHED, SHUT_WHO_MOM, SHUT_WHO_SECDRY, \
                 SHUT_WHO_IDLESECDRY, SHUT_WHO_SECDONLY. \

        Default:None

        extend - extend options

        server_name - name of the pbs server

        runas - run as user

        logerr - If True (default) logs run_cmd errors
        """
        prefix = 'terminate ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': with manner '
        attrs = manner
        if attrs is None:
            prefix += "None "
        elif isinstance(attrs, str):
            prefix += attrs
        else:
            if ((attrs & SHUT_QUICK) == SHUT_QUICK):
                prefix += "quick "
            if ((attrs & SHUT_IMMEDIATE) == SHUT_IMMEDIATE):
                prefix += "immediate "
            if ((attrs & SHUT_DELAY) == SHUT_DELAY):
                prefix += "delay "
            if ((attrs & SHUT_WHO_SCHED) == SHUT_WHO_SCHED):
                prefix += "schedular "
            if ((attrs & SHUT_WHO_MOM) == SHUT_WHO_MOM):
                prefix += "mom "
            if ((attrs & SHUT_WHO_SECDRY) == SHUT_WHO_SECDRY):
                prefix += "secondary server "
            if ((attrs & SHUT_WHO_IDLESECDRY) == SHUT_WHO_IDLESECDRY):
                prefix += "idle secondary "
            if ((attrs & SHUT_WHO_SECDONLY) == SHUT_WHO_SECDONLY):
                prefix += "shoutdown secondary only "

        self.logger.info(prefix)

        if self.has_diag:
            return 0

        c = None
        rc = 0

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin', 'qterm')]
            _conf = self.default_client_pbs_conf
            pcmd += self.utils.convert_to_cli(manner, op=IFL_TERMINATE,
                                              hostname=self.hostname,
                                              dflt_conf=_conf)
            if server_name is not None:
                pcmd += [server_name]

            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False

            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  level=logging.INFOCLI, as_script=as_script)
            rc = ret['rc']
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = rc
        elif runas is not None:
            attrs = {'manner': manner, 'server_name': server_name}
            rc = self.pbs_api_as('terminate', None, runas, data=attrs,
                                 extend=extend)
        else:
            if server_name is None:
                server_name = self.hostname
            c = self._connect(self.hostname)
            rc = pbs_terminate(c, manner, extend)
        if rc != 0:
            raise PbsQtermError(rc=rc, rv=False, msg=self.geterrmsg(),
                                post=self._disconnect, conn=c, force=True)

        if c:
            self._disconnect(c, force=True)

        return rc
    teminate = qterm

    def geterrmsg(self):
        mode = self.get_op_mode()
        if mode == PTL_CLI:
            return self.last_error
        elif self._conn is not None and self._conn >= 0:
            m = pbs_geterrmsg(self._conn)
            if m is not None:
                m = m.split('\n')
            return m
#
# End IFL Wrappers
#

    def qdisable(self, queue=None, runas=None, logerr=True):
        """
        Disable queue. CLI mode only

        queue - The name of the queue or list of queue to disable

        runas - Optional name of user to run command as

        logerr - Set to False ot disable logging command errors.
        Defaults to True.
        """
        prefix = 'qdisable on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qdisable')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQdisableError(rc=self.last_rc, rv=False,
                                       msg=self.last_error)
        else:
            _msg = 'qdisable: currently not supported in API mode'
            raise PbsQdisableError(rv=False, rc=1, msg=_msg)

    def qenable(self, queue=None, runas=None, logerr=True):
        """
        Enable queue. CLI mode only

        queue - The name of the queue or list of queue to enable

        runas - Optional name of user to run command as

        logerr - Set to False ot disable logging command errors.
        Defaults to True.
        """
        prefix = 'qenable on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qenable')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQenableError(rc=self.last_rc, rv=False,
                                      msg=self.last_error)
        else:
            _msg = 'qenable: currently not supported in API mode'
            raise PbsQenableError(rv=False, rc=1, msg=_msg)

    def qstart(self, queue=None, runas=None, logerr=True):
        """
        Start queue. CLI mode only

        queue - The name of the queue or list of queue to start

        runas - Optional name of user to run command as

        logerr - Set to False ot disable logging command errors.
        Defaults to True.
        """
        prefix = 'qstart on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qstart')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQstartError(rc=self.last_rc, rv=False,
                                     msg=self.last_error)
        else:
            _msg = 'qstart: currently not supported in API mode'
            raise PbsQstartError(rv=False, rc=1, msg=_msg)

    def qstop(self, queue=None, runas=None, logerr=True):
        """
        Stop queue. CLI mode only

        queue - The name of the queue or list of queue to stop

        runas - Optional name of user to run command as

        logerr - Set to False ot disable logging command errors.
        Defaults to True.
        """
        prefix = 'qstop on ' + self.shortname
        if runas is not None:
            prefix += ' as ' + str(runas)
        prefix += ': '
        if queue is not None:
            if not isinstance(queue, list):
                queue = queue.split(',')
            prefix += ', '.join(queue)
        self.logger.info(prefix)

        if self.get_op_mode() == PTL_CLI:
            pcmd = [os.path.join(self.client_conf['PBS_EXEC'], 'bin',
                                 'qstop')]
            if queue is not None:
                pcmd += queue
            if not self.default_client_pbs_conf:
                pcmd = ['PBS_CONF_FILE=' + self.client_pbs_conf_file] + pcmd
                as_script = True
            else:
                as_script = False
            ret = self.du.run_cmd(self.client, pcmd, runas=runas,
                                  as_script=as_script, level=logging.INFOCLI,
                                  logerr=logerr)
            if ret['err'] != ['']:
                self.last_error = ret['err']
            self.last_rc = ret['rc']
            if self.last_rc != 0:
                raise PbsQstopError(rc=self.last_rc, rv=False,
                                    msg=self.last_error)
        else:
            _msg = 'qstop: currently not supported in API mode'
            raise PbsQstopError(rv=False, rc=1, msg=_msg)

    def parse_resources(self):
        """
        Parse server resources as defined in the resourcedef file
        Populates instance variable self.resources

        Returns the resources as a dictionary
        """
        if not self.has_diag:
            self.manager(MGR_CMD_LIST, RSC)
        return self.resources

    def remove_resource(self, name):
        """
        Remove an entry from resourcedef

        name - The name of the resource to remove
        """
        self.parse_resources()
        if not self.has_diag:
            if name in self.resources:
                self.manager(MGR_CMD_DELETE, RSC, id=name)

    def add_resource(self, name, type=None, flag=None):
        """
        Define a server resource

        name - The name of the resource to add to the resourcedef file

        type - The type of the resource, one of string, long, boolean, float

        flag - The target of the resource, one of n, h, q, or none

        return True on success False on error
        """
        rv = self.parse_resources()
        if rv is None:
            return False

        resource_exists = False
        if name in self.resources:
            msg = [self.logprefix + "resource " + name]
            if type:
                msg += ["type: " + type]
            if flag:
                msg += ["flag: " + flag]
            msg += [" already defined"]
            self.logger.info(" ".join(msg))

            (t, f) = (self.resources[name].type, self.resources[name].flag)
            if type == t and flag == f:
                return True

            self.logger.info("resource: redefining resource " + name +
                             " type: " + str(type) + " and flag: " + str(flag))
            del self.resources[name]
            resource_exists = True

        r = Resource(name, type, flag)
        self.resources[name] = r
        a = {}
        if type:
            a['type'] = type
        if flag:
            a['flag'] = flag
        if resource_exists:
            self.manager(MGR_CMD_SET, RSC, a, id=name)
        else:
            self.manager(MGR_CMD_CREATE, RSC, a, id=name)
        return True

    def write_resourcedef(self, resources=None, filename=None, restart=True):
        if resources is None:
            resources = self.resources
        if isinstance(resources, Resource):
            resources = {resources.name:resources}
        fn = self.du.mkstemp()[1]
        f = open(fn, 'w+')
        for r in resources.values():
            f.write(r.attributes['id'])
            if r.attributes['type'] is not None:
                f.write(' type=' + r.attributes['type'])
            if r.attributes['flag'] is not None:
                f.write(' flag=' + r.attributes['flag'])
            f.write('\n')
        f.close()
        if filename is None:
            dest = os.path.join(self.pbs_conf['PBS_HOME'], 'server_priv',
                                'resourcedef')
        else:
            dest = filename
        self.du.run_copy(self.hostname, fn, dest, mode=0644, sudo=True)
        if filename is None:
            self.du.chown(self.hostname, path=dest, uid=0, gid=0,
                          sudo=True)
        os.remove(fn)
        if restart:
            return self.restart()
        return True

    def parse_resourcedef(self, file=None):
        """
        Parse an arbitrary resource definition file passed as input and return
        a dictionary of resources
        """
        if file is None:
            file = os.path.join(self.pbs_conf['PBS_HOME'], 'server_priv',
                                    'resourcedef')
        ret = self.du.cat(self.hostname, file, logerr=False, sudo=True)
        if ret['rc'] != 0 or len(ret['out']) == 0:
            # Most probable error is that file does not exist, we'll let it
            # be created
            return {}

        resources = {}
        lines = ret['out']
        try:
            for l in lines:
                l = l.strip()
                if l == '' or l.startswith('#'):
                    continue
                name = None
                rtype = None
                flag = None
                res = l.split()
                e0 = res[0]
                if len(res) > 1:
                    e1 = res[1].split('=')
                else:
                    e1 = None
                if len(res) > 2:
                    e2 = res[2].split('=')
                else:
                    e2 = None
                if e1 is not None and e1[0] == 'type':
                    rtype = e1[1]
                elif e2 is not None and e2[0] == 'type':
                    rtype = e2[1]
                if e1 is not None and e1[0] == 'flag':
                    flag = e1[0]
                elif e2 is not None and e2[0] == 'flag':
                    flag = e2[1]
                name = e0
                r = Resource(name, rtype, flag)
                resources[name] = r
        except:
            raise PbsResourceError(rc=1, rv=False,
                                   msg="error in parse_resources")
        return resources

    def pbs_api_as(self, cmd=None, obj=None, user=None, **kwargs):
        """
        Generic handler to run an API call impersonating a given user.
        This method is only used for impersonation over the API because CLI
        impersonation takes place through the generic DshUtils run_cmd
        mechanism.
        """
        fn = None
        objid = None
        _data = None

        if user is None:
            user = self.du.get_current_user()
        else:
            # user may be a PbsUser object, cast it to string for the remainder
            # of the function
            user = str(user)

        if cmd == 'submit':
            if obj is None:
                return None

            _data = copy.copy(obj)
            # the following attributes cause problems 'pickling',
            # since they are not needed we unset them
            _data.attrl = None
            _data.attropl = None
            _data.logger = None
            _data.utils = None

        elif cmd in ('alterjob', 'holdjob', 'sigjob', 'msgjob', 'rlsjob',
                     'rerunjob', 'orderjob', 'runjob', 'movejob',
                     'select', 'delete', 'status', 'manager', 'terminate',
                     'deljob', 'delresv'):
            objid = obj
            if 'data' in kwargs:
                _data = kwargs['data']

        if _data is not None:
            (fd, fn) = self.du.mkstemp()
            tmpfile = open(fn, 'w+b')
            cPickle.dump(_data, tmpfile)
            tmpfile.close()
            os.close(fd)

            os.chmod(fn, 0755)

            if self._is_local:
                os.chdir(tempfile.gettempdir())
            else:
                self.du.run_copy(self.hostname, fn, fn, sudo=True)

        if not self._is_local:
            p_env = '"import os; print os.environ[\'PTL_EXEC\']"'
            ret = self.du.run_cmd(self.hostname, ['python', '-c', p_env],
                                  logerr=False)
            if ret['out']:
                runcmd = [os.path.join(ret['out'][0], 'pbs_as')]
            else:
                runcmd = ['pbs_as']
        elif 'PTL_EXEC' in os.environ:
            runcmd = [os.path.join(os.environ['PTL_EXEC'], 'pbs_as')]
        else:
            runcmd = ['pbs_as']

        runcmd += ['-c', cmd, '-u', user]

        if objid is not None:
            runcmd += ['-o']
            if isinstance(objid, list):
                runcmd += [','.join(objid)]
            else:
                runcmd += [objid]

        if fn is not None:
            runcmd += ['-f', fn]

        if 'hostname' in kwargs:
            hostname = kwargs['hostname']
        else:
            hostname = self.hostname
        runcmd += ['-s', hostname]

        if 'extend' in kwargs and kwargs['extend'] is not None:
            runcmd += ['-e', kwargs['extend']]

        ret = self.du.run_cmd(self.hostname, runcmd, logerr=False, runas=user)
        out = ret['out']
        if ret['err']:
            if cmd in CMD_ERROR_MAP:
                m = CMD_ERROR_MAP[cmd]
                if m in ret['err'][0]:
                    if fn is not None:
                        os.remove(fn)
                        if not self._is_local:
                            self.du.rm(self.hostname, fn)
                    raise eval(str(ret['err'][0]))
            self.logger.debug('err: ' + str(ret['err']))

        if fn is not None:
            os.remove(fn)
            if not self._is_local:
                self.du.rm(self.hostname, fn)

        if cmd == 'submit':
            if out:
                return out[0].strip()
            else:
                return None
        elif cmd in ('alterjob', 'holdjob', 'sigjob', 'msgjob', 'rlsjob',
                     'rerunjob', 'orderjob', 'runjob', 'movejob', 'delete',
                     'terminate'):
            if ret['out']:
                return int(ret['out'][0])
            else:
                return 1

        elif cmd in ('manager', 'select', 'status'):
            return eval(out[0])

    def expect(self, obj_type, attrib=None, id=None, op=EQ, attrop=PTL_OR,
               attempt=0, max_attempts=None, interval=None, count=None,
               extend=None, offset=0, runas=None, level=logging.INFO,
               msg=None):
        """
        expect an attribute to match a given value as per an operation.

        obj_type - The type of object to query, JOB, SERVER, SCHEDULER, QUEUE
        NODE

        attrib - Attributes to query, can be a string, a list, or a dict

        id - The id of the object to act upon

        op - An operation to perform on the queried data, e.g., EQ, SET, LT,..

        attrop - Operation on multiple attributes, either PTL_AND, PTL_OR
        when an PTL_AND is used, only batch objects having all matches
        are returned, otherwise an OR is applied

        attempt - The number of times this function has been called
        max_attempts - The maximum number of attempts to perform.
        C{param_max_attempts}: 5

        interval - The interval time btween attempts.
        C{param_interval}: 1s

        count - If True, attrib will be accumulated using function counter

        extend - passed to the stat call

        offset - the time to wait before the initial check. Defaults to 0.

        runas - query as a given user. Defaults to current user

        msg - Message from last call of this function, this message will be
        used while raising PtlExpectError.

        Return True if attributes are as expected and False otherwise
        """

        if attempt == 0 and offset > 0:
            self.logger.log(level, self.logprefix + 'expect offset set to ' +
                            str(offset))
            time.sleep(offset)

        if attrib is None:
            attrib = {}

        if ATTR_version in attrib and max_attempts is None:
            max_attempts = 3

        if max_attempts is None:
            max_attempts = int(self.ptl_conf['expect_max_attempts'])

        if interval is None:
            interval = self.ptl_conf['expect_interval']

        if attempt >= max_attempts:
            _msg = "expected on " + self.logprefix + msg
            raise PtlExpectError(rc=1, rv=False, msg=_msg)

        if obj_type == SERVER and id is None:
            id = self.hostname

        if isinstance(attrib, str):
            attrib = {attrib: ''}
        elif isinstance(attrib, list):
            d = {}
            for l in attrib:
                d[l] = ''
            attrib = d

        prefix = 'expect on ' + self.logprefix
        msg = []
        for k, v in attrib.items():
            args = None
            if isinstance(v, tuple):
                operator = v[0]
                if len(v) > 2:
                    args = v[2:]
                val = v[1]
            else:
                operator = op
                val = v
            msg += [k, PTL_OP_TO_STR[operator].strip()]
            if callable(val):
                msg += ['callable(' + val.__name__ + ')']
                if args is not None:
                    msg.extend(map(lambda x: str(x), args))
            else:
                msg += [str(val)]
            msg += [PTL_ATTROP_TO_STR[attrop]]

        # remove the last converted PTL_ATTROP_TO_STR
        if len(msg) > 1:
            msg = msg[:-1]

        if len(attrib) == 0:
            msg += [PTL_OP_TO_STR[op]]

        msg += [PBS_OBJ_MAP[obj_type]]
        if id is not None:
            msg += [str(id)]
        if attempt > 0:
            msg += ['attempt:', str(attempt + 1)]

        # Default count to True if the attribute contains an '=' in its name
        # for example 'job_state=R' implies that a count of job_state is needed
        if count is None and self.utils.operator_in_attribute(attrib):
            count = True

        if count:
            newattr = self.utils.convert_attributes_by_op(attrib)
            if len(newattr) == 0:
                newattr = attrib

            statlist = [self.counter(obj_type, newattr, id, extend, op=op,
                                     attrop=attrop, level=logging.DEBUG,
                                     runas=runas)]
        else:
            try:
                statlist = self.status(obj_type, attrib, id=id,
                                       level=logging.DEBUG, extend=extend,
                                       runas=runas, logerr=False)
            except PbsStatusError:
                statlist = []

        if (len(statlist) == 0 or statlist[0] is None or
                len(statlist[0]) == 0):
            if op == UNSET or list(set(attrib.values())) == [0]:
                self.logger.log(level, prefix + " ".join(msg) + ' ...  OK')
                return True
            else:
                time.sleep(interval)
                msg = " no data for " + " ".join(msg)
                self.logger.log(level, prefix + msg)
                return self.expect(obj_type, attrib, id, op, attrop,
                                   attempt + 1, max_attempts, interval, count,
                                   extend, level=level, msg=msg)

        if attrib is None:
            time.sleep(interval)
            return self.expect(obj_type, attrib, id, op, attrop, attempt + 1,
                               max_attempts, interval, count, extend,
                               runas=runas, level=level, msg=" ".join(msg))

        for k, v in attrib.items():
            varargs = None
            if isinstance(v, tuple):
                op = v[0]
                if len(v) > 2:
                    varargs = v[2:]
                v = v[1]

            for stat in statlist:
                if k == ATTR_version and k in stat:
                    m = self.version_tag.match(stat[k])
                    if m:
                        stat[k] = m.group('version')
                    else:
                        time.sleep(interval)
                        return self.expect(obj_type, attrib, id, op, attrop,
                                           attempt + 1, max_attempts, interval,
                                           count, extend, runas=runas,
                                           level=level, msg=" ".join(msg))
                if k not in stat:
                    if op == UNSET:
                        continue
                else:
                    # functions/methods are invoked and their return value
                    # used on expect
                    if callable(v):
                        if varargs is not None:
                            rv = v(stat[k], *varargs)
                        else:
                            rv = v(stat[k])
                        if isinstance(rv, bool):
                            if op == NOT:
                                if not rv:
                                    continue
                            if rv:
                                continue
                        else:
                            v = rv

                    stat[k] = self.utils.decode_value(stat[k])
                    v = self.utils.decode_value(v)

                    if k == ATTR_version:
                        stat[k] = LooseVersion(str(stat[k]))
                        v = LooseVersion(str(v))

                    if op == EQ and stat[k] == v:
                        continue
                    elif op == SET and count and stat[k] == v:
                        continue
                    elif op == SET and count in (False, None):
                        continue
                    elif op == NE and stat[k] != v:
                        continue
                    elif op == LT:
                        if stat[k] < v:
                            continue
                    elif op == GT:
                        if stat[k] > v:
                            continue
                    elif op == LE:
                        if stat[k] <= v:
                            continue
                    elif op == GE:
                        if stat[k] >= v:
                            continue
                    elif op == MATCH_RE:
                        if re.search(str(v), str(stat[k])):
                            continue
                    elif op == MATCH:
                        if str(stat[k]).find(str(v)) != -1:
                            continue

                if k in stat:
                    msg += [' got: ' + str(k) + ' = ' + str(stat[k])]
                self.logger.info(prefix + " ".join(msg))
                time.sleep(interval)

                # run custom actions defined for this object type
                if self.actions:
                    for act_obj in self.actions.get_actions_by_type(obj_type):
                        if act_obj.enabled:
                            act_obj.action(self, obj_type, attrib, id, op,
                                           attrop)

                return self.expect(obj_type, attrib, id, op, attrop,
                                   attempt + 1, max_attempts, interval, count,
                                   extend, level=level, msg=" ".join(msg))

        self.logger.log(level, prefix + " ".join(msg) + ' ...  OK')
        return True

    def is_history_enabled(self):
        """
        Short-hand method to return the value of job_history_enable
        """
        a = ATTR_JobHistoryEnable
        attrs = self.status(SERVER, level=logging.DEBUG)[0]
        if ((a in attrs.keys()) and attrs[a] == 'True'):
            return True
        return False

    def cleanup_jobs(self, extend=None, runas=None):
        """
        Helper function to delete all jobs.
        By default this method will determine whether job_history_enable is on
        and will cleanup all history jobs. Specifying an extend parameter could
        override this behavior.
        """
        delete_xt = 'force'
        select_xt = None
        if self.is_history_enabled():
            delete_xt += 'deletehist'
            select_xt = 'x'
        job_ids = self.select(extend=select_xt)
        if len(job_ids) > 0:
            try:
                self.deljob(id=job_ids, extend=delete_xt, runas=runas,
                            wait=True)
            except:
                pass
        rv = self.expect(JOB, {'job_state': 0}, count=True, op=SET)
        if not rv:
            return self.cleanup_jobs(extend=extend, runas=runas)
        return rv

    def cleanup_reservations(self, extend=None, runas=None):
        """ Helper function to delete all reservations """
        reservations = self.status(RESV, level=logging.DEBUG)
        while reservations is not None and len(reservations) != 0:
            resvs = [r['id'] for r in reservations]
            if len(resvs) > 0:
                try:
                    self.delresv(resvs, logerr=False, runas=runas)
                except:
                    pass
                reservations = self.status(RESV, level=logging.DEBUG)

    def cleanup_jobs_and_reservations(self, extend='forcedeletehist'):
        """
        Helper function to delete all jobs and reservations

        extend - Optional extend parameter that is passed to delete. It
        defaults to 'deletehist' which is used in qdel and pbs_deljob() to
        force delete all jobs, including history jobs
        """
        rv = self.cleanup_jobs(extend)
        self.cleanup_reservations()
        return rv

    def update_attributes(self, obj_type, bs):
        """
        Populate objects from batch status data
        """

        if bs is None:
            return

        for binfo in bs:
            if 'id' not in binfo:
                continue
            id = binfo['id']
            obj = None
            if obj_type == JOB:
                if ATTR_owner in binfo:
                    user = binfo[ATTR_owner].split('@')[0]
                else:
                    user = None
                if id in self.jobs:
                    self.jobs[id].attributes.update(binfo)
                    if self.jobs[id].username != user:
                        self.jobs[id].username = user
                else:
                    self.jobs[id] = Job(user, binfo)
                obj = self.jobs[id]
            elif obj_type in (VNODE, NODE):
                if id in self.nodes:
                    self.nodes[id].attributes.update(binfo)
                else:
                    self.nodes[id] = MoM(id, binfo, diagmap={NODE: None})
                obj = self.nodes[id]
            elif obj_type == SERVER:
                self.attributes.update(binfo)
                obj = self
            elif obj_type == QUEUE:
                if id in self.queues:
                    self.queues[id].attributes.update(binfo)
                else:
                    self.queues[id] = Queue(id, binfo, server=self)
                obj = self.queues[id]
            elif obj_type == RESV:
                if id in self.reservations:
                    self.reservations[id].attributes.update(binfo)
                else:
                    self.reservations[id] = Reservation(id, binfo)
                obj = self.reservations[id]
            elif obj_type == HOOK:
                if id in self.hooks:
                    self.hooks[id].attributes.update(binfo)
                else:
                    self.hooks[id] = Hook(id, binfo, server=self)
                obj = self.hooks[id]
            elif obj_type == SCHED:
                if self.scheduler:
                    self.scheduler.attributes.update(binfo)
                else:
                    if SCHED in self.diagmap:
                        diag = self.diag
                        diagmap = self.diagmap
                    else:
                        diag = None
                        diagmap = None
                    self.scheduler = Scheduler(server=self, diag=diag,
                                               diagmap=diagmap)
                    self.scheduler.attributes.update(binfo)
                obj = self.scheduler
            elif obj_type == RSC:
                if id in self.resources:
                    self.resources[id].attributes.update(binfo)
                else:
                    rtype = None
                    rflag = None
                    if 'type' in binfo:
                        rtype = binfo['type']
                    if 'flag' in binfo:
                        rflag = binfo['flag']
                    self.resources[id] = Resource(id, rtype, rflag)

            if obj is not None:
                self.utils.update_attributes_list(obj)
                obj.__dict__.update(binfo)

    def counter(self, obj_type=None, attrib=None, id=None, extend=None,
                op=None, attrop=None, bslist=None, level=logging.INFO,
                idonly=True, grandtotal=False, db_access=None, runas=None,
                resolve_indirectness=False):
        """
        Accumulate properties set on an object. For example, to count number
        of free nodes: server.counter(VNODE,{'state':'free'})

        obj_type - The type of object to query, one of the * objects

        attrib - Attributes to query, can be a string, a list, a dictionary

        id - The id of the object to act upon

        extend - The extended parameter to pass to the stat call

        op - The operation used to match attrib to what is queried. SET or None

        attrop - Operation on multiple attributes, either PTL_AND, PTL_OR

        bslist - Optional, use a batch status dict list instead of an obj_type

        idonly - if true, return the name/id of the matching objects

        db_access - credentials to access db, either a path to file or
        dictionary

        runas - run as user
        """
        self.logit('counter: ', obj_type, attrib, id, level=level)
        return self._filter(obj_type, attrib, id, extend, op, attrop, bslist,
                            PTL_COUNTER, idonly, grandtotal, db_access,
                            runas=runas,
                            resolve_indirectness=resolve_indirectness)

    def filter(self, obj_type=None, attrib=None, id=None, extend=None, op=None,
               attrop=None, bslist=None, idonly=True, grandtotal=False,
               db_access=None, runas=None, resolve_indirectness=False):
        """
        Filter objects by properties. For example, to filter all free nodes:
        server.filter(VNODE,{'state':'free'})

        For each attribute queried, if idonly is True, a list of matching
        object names is returned; if idonly is False, then the value of each
        attribute queried is returned.

        This is unlike Python's built-in 'filter' that returns a subset of
        objects matching from a pool of objects. The Python filtering mechanism
        remains very useful in some situations and should be
        used programmatically to achieve desired filtering goals that can not
        be met easily with PTL's filter method.

        obj_type - The type of object to query, one of the * objects

        attrib - Attributes to query, can be a string, a list, a dictionary

        id - The id of the object to act upon

        extend - The extended parameter to pass to the stat call

        op - The operation used to match attrib to what is queried. SET or
        None

        bslist - Optional, use a batch status dict list instead of an obj_type

        idonly - if true, return the name/id of the matching objects

        db_access - credentials to access db, either path to file or dictionary

        runas - run as user
        """
        self.logit('filter: ', obj_type, attrib, id)
        return self._filter(obj_type, attrib, id, extend, op, attrop, bslist,
                            PTL_FILTER, idonly, db_access, runas=runas,
                            resolve_indirectness=resolve_indirectness)

    def _filter(self, obj_type=None, attrib=None, id=None, extend=None,
                op=None, attrop=None, bslist=None, mode=PTL_COUNTER,
                idonly=True, grandtotal=False, db_access=None, runas=None,
                resolve_indirectness=False):

        if bslist is None:
            try:
                tmp_bsl = self.status(obj_type, attrib, id,
                                      level=logging.DEBUG, extend=extend,
                                      db_access=db_access, runas=runas,
                                      resolve_indirectness=resolve_indirectness)
            except PbsStatusError:
                return None

            bslist = self.utils.filter_batch_status(tmp_bsl, attrib)
            del tmp_bsl

        if bslist is None:
            return None

        if isinstance(attrib, str):
            attrib = attrib.split(',')

        total = {}
        for bs in bslist:
            if isinstance(attrib, list):
                # when filtering on multiple values, ensure that they are
                # all present on the object, otherwise skip
                if attrop == PTL_AND:
                    match = True
                    for k in attrib:
                        if k not in bs:
                            match = False
                    if not match:
                        continue

                for a in attrib:
                    if a in bs:
                        if op == SET:
                            k = a
                        else:
                            # Since this is a list of attributes, no operator
                            # was provided so we settle on "equal"
                            k = a + '=' + str(bs[a])
                        if mode == PTL_COUNTER:
                            amt = 1
                            if grandtotal:
                                amt = self.utils.decode_value(bs[a])
                                if not isinstance(amt, (int, float)):
                                    amt = 1
                                if a in total:
                                    total[a] += amt
                                else:
                                    total[a] = amt
                            else:
                                if k in total:
                                    total[k] += amt
                                else:
                                    total[k] = amt
                        elif mode == PTL_FILTER:
                            if k in total:
                                if idonly:
                                    total[k].append(bs['id'])
                                else:
                                    total[k].append(bs)
                            else:
                                if idonly:
                                    total[k] = [bs['id']]
                                else:
                                    total[k] = [bs]
                        else:
                            self.logger.error("Unhandled mode " + str(mode))
                            return None

            elif isinstance(attrib, dict):
                tmptotal = {}  # The running count that will be used for total

                # when filtering on multiple values, ensure that they are
                # all present on the object, otherwise skip
                match = True
                for k, v in attrib.items():
                    if k not in bs:
                        match = False
                        if attrop == PTL_AND:
                            break
                        else:
                            continue
                    amt = self.utils.decode_value(bs[k])
                    if isinstance(v, tuple):
                        op = v[0]
                        val = self.utils.decode_value(v[1])
                    elif op == SET:
                        val = None
                        pass
                    else:
                        op = EQ
                        val = self.utils.decode_value(v)

                    if ((op == LT and amt < val) or
                            (op == LE and amt <= val) or
                            (op == EQ and amt == val) or
                            (op == GE and amt >= val) or
                            (op == GT and amt > val) or
                            (op == NE and amt != val) or
                            (op == MATCH and str(amt).find(str(val)) != -1) or
                            (op == MATCH_RE and
                             re.search(str(val), str(amt))) or
                            (op == SET)):
                        # There is a match, proceed to track the attribute
                        self._filter_helper(bs, k, val, amt, op, mode,
                                            tmptotal, idonly, grandtotal)
                    elif attrop == PTL_AND:
                        match = False
                        if mode == PTL_COUNTER:
                            # requesting specific key/value pairs should result
                            # in 0 available elements
                            tmptotal[str(k) + PTL_OP_TO_STR[op] + str(val)] = 0
                        break
                    elif mode == PTL_COUNTER:
                        tmptotal[str(k) + PTL_OP_TO_STR[op] + str(val)] = 0

                if attrop != PTL_AND or (attrop == PTL_AND and match):
                    for k, v in tmptotal.items():
                        if k not in total:
                            total[k] = v
                        else:
                            total[k] += v
        return total

    def _filter_helper(self, bs, k, v, amt, op, mode, total, idonly,
                       grandtotal):
        # default operation to '='
        if op is None or op not in PTL_OP_TO_STR:
            op = '='
        op_str = PTL_OP_TO_STR[op]

        if op == SET:
            # override PTL_OP_TO_STR fro SET operations
            op_str = ''
            v = ''

        ky = k + op_str + str(v)
        if mode == PTL_COUNTER:
            incr = 1
            if grandtotal:
                if not isinstance(amt, (int, float)):
                    incr = 1
                else:
                    incr = amt
            if ky in total:
                total[ky] += incr
            else:
                total[ky] = incr
        elif mode == PTL_FILTER:
            if ky in total:
                if idonly:
                    total[ky].append(bs['id'])
                else:
                    total[ky].append(bs)
            else:
                if idonly:
                    total[ky] = [bs['id']]
                else:
                    total[ky] = [bs]

    def logit(self, msg, obj_type, attrib, id, level=logging.INFO):
        """
        Generic logging routine for IFL commands

        msg - The message to log

        obj_type - object type, i.e *

        attrib - attributes to log

        id - name of object to log

        level - log level, defaults to INFO
        """
        s = []
        if self.logger is not None:
            if obj_type is None:
                obj_type = MGR_OBJ_NONE
            s = [msg + PBS_OBJ_MAP[obj_type]]
            if id:
                if isinstance(id, list):
                    s += [' ' + ",".join(id)]
                else:
                    s += [' ' + str(id)]
            if attrib:
                s += [' ' + str(attrib)]
            self.logger.log(level, "".join(s))

    def equivalence_classes(self, obj_type=None, attrib={}, bslist=None,
                            op=RESOURCES_AVAILABLE, show_zero_resources=True,
                            db_access=None, resolve_indirectness=False):
        """
        obj_type - PBS Object to query, one of *

        attrib - attributes to build equivalence classes out of.

        bslist - Optional, list of dictionary representation of a batch status

        op - set to RESOURCES_AVAILABLE uses the dynamic amount of resources
        available, i.e., available - assigned, otherwise uses static amount of
        resources available

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """

        if attrib is None:
            attrib = {}

        if len(attrib) == 0 and obj_type is not None:
            if obj_type in (VNODE, NODE):
                attrib = ['resources_available.ncpus',
                          'resources_available.mem', 'state']
            elif obj_type == JOB:
                attrib = ['Resource_List.select',
                          'queue', 'array_indices_submitted']
            elif obj_type == RESV:
                attrib = ['Resource_List.select']
            else:
                return {}

        if bslist is None and obj_type is not None:
            # To get the resources_assigned we must stat the entire object so
            # bypass the specific attributes that would filter out assigned
            if op == RESOURCES_AVAILABLE:
                bslist = self.status(obj_type, None, level=logging.DEBUG,
                                     db_access=db_access,
                                     resolve_indirectness=resolve_indirectness)
            else:
                bslist = self.status(obj_type, attrib, level=logging.DEBUG,
                                     db_access=db_access,
                                     resolve_indirectness=resolve_indirectness)

        if bslist is None or len(bslist) == 0:
            return {}

        # automatically convert an objectlist into a batch status dict list
        # for ease of use.
        if not isinstance(bslist[0], dict):
            bslist = self.utils.objlist_to_dictlist(bslist)

        if isinstance(attrib, str):
            attrib = attrib.split(',')

        self.logger.debug("building equivalence class")
        equiv = {}
        for bs in bslist:
            cls = ()
            skip_cls = False
            # attrs will be part of the EquivClass object
            attrs = {}
            # Filter the batch attributes by the attribs requested
            for a in attrib:
                if a in bs:
                    amt = self.utils.decode_value(bs[a])
                    if a.startswith('resources_available.'):
                        val = a.replace('resources_available.', '')
                        if (op == RESOURCES_AVAILABLE and
                                'resources_assigned.' + val in bs):
                            amt = (int(amt) - int(self.utils.decode_value(
                                   bs['resources_assigned.' + val])))
                        # this case where amt goes negative is not a bug, it
                        # may happen when computing whats_available due to the
                        # fact that the computation is subtractive, it does
                        # add back resources when jobs/reservations end but
                        # is only concerned with what is available now for
                        # a given duration, that is why in the case where
                        # amount goes negative we set it to 0
                        if amt < 0:
                            amt = 0

                        # TODO: not a failproof way to catch a memory type
                        # but PbsTypeSize should return the right value if
                        # it fails to parse it as a valid memory value
                        if a.endswith('mem'):
                            try:
                                amt = PbsTypeSize().encode(amt)
                            except:
                                # we guessed the type incorrectly
                                pass
                    else:
                        val = a
                    if amt == 0 and not show_zero_resources:
                        skip_cls = True
                        break
                    # Build the key of the equivalence class
                    cls += (val + '=' + str(amt),)
                    attrs[val] = amt
            # Now that we are done with this object, add it to an equiv class
            if len(cls) > 0 and not skip_cls:
                if cls in equiv:
                    equiv[cls].add_entity(bs['id'])
                else:
                    equiv[cls] = EquivClass(cls, attrs, [bs['id']])

        return equiv.values()

    def show_equivalence_classes(self, eq=None, obj_type=None, attrib={},
                                 bslist=None, op=RESOURCES_AVAILABLE,
                                 show_zero_resources=True, db_access=None,
                                 resolve_indirectness=False):
        """
        helper function to show the equivalence classes

        eq - equivalence classes as compute by equivalence_classes
        see equivalence_classes for remaining parameters description

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        if eq is None:
            equiv = self.equivalence_classes(obj_type, attrib, bslist, op,
                                             show_zero_resources, db_access,
                                             resolve_indirectness)
        else:
            equiv = eq
        equiv = sorted(equiv, key=lambda e: len(e.entities))
        for e in equiv:
            # e.show()
            print str(e)

    def whats_available(self, attrib=None, jobs=None, resvs=None, nodes=None):
        """
        Returns what's available as a list of node equivalence classes
        listed by availability over time.

        attrib - attributes to consider

        jobs - jobs to consider, if None, jobs are queried locally

        resvs - reservations to consider, if None, they are queried locally

        nodes - nodes to consider, if None, they are queried locally
        """

        if attrib is None:
            attrib = ['resources_available.ncpus',
                      'resources_available.mem', 'state']

        if resvs is None:
            self.status(RESV)
            resvs = self.reservations

        if jobs is None:
            self.status(JOB)
            jobs = self.jobs

        if nodes is None:
            self.status(NODE)
            nodes = self.nodes

        nodes_id = nodes.keys()
        avail_nodes_by_time = {}

        def alloc_resource(self, node, resources):
            # helper function. Must work on a scratch copy of nodes otherwise
            # resources_available will get corrupted
            for rsc, value in resources.items():
                if isinstance(value, int) or value.isdigit():
                    avail = node.attributes['resources_available.' + rsc]
                    nvalue = int(avail) - int(value)
                    node.attributes['resources_available.' + rsc] = nvalue

        # Account for reservations
        for resv in resvs.values():
            resvnodes = resv.execvnode('resv_nodes')
            if resvnodes:
                starttime = self.utils.convert_stime_to_seconds(
                    resv.attributes['reserve_start'])
                for node in resvnodes:
                    for n, resc in node.items():
                        tm = int(starttime) - int(self.ctime)
                        if tm < 0 or n not in nodes_id:
                            continue
                        if tm not in avail_nodes_by_time:
                            avail_nodes_by_time[tm] = []
                        if nodes[n].attributes['sharing'] in ('default_excl',
                                                              'force_excl'):
                            avail_nodes_by_time[tm].append(nodes[n])
                            try:
                                nodes_id.remove(n)
                            except:
                                pass
                        else:
                            ncopy = copy.copy(nodes[n])
                            ncopy.attributes = copy.deepcopy(
                                nodes[n].attributes)
                            avail_nodes_by_time[tm].append(ncopy)
                            self.alloc_resource(nodes[n], resc)

        # go on to look at the calendar of scheduled jobs to run and set
        # the node availability according to when the job is estimated to
        # start on the node
        for job in self.jobs.values():
            if (job.attributes['job_state'] != 'R' and
                    'estimated.exec_vnode' in job.attributes):
                estimatednodes = job.execvnode('estimated.exec_vnode')
                if estimatednodes:
                    st = job.attributes['estimated.start_time']
                    # Tweak for nas format of estimated time that has
                    # num seconds from epoch followed by datetime
                    if st.split()[0].isdigit():
                        starttime = st.split()[0]
                    else:
                        starttime = self.utils.convert_stime_to_seconds(st)
                    for node in estimatednodes:
                        for n, resc in node.items():
                            tm = int(starttime) - int(self.ctime)
                            if (tm < 0 or n not in nodes_id or
                                    nodes[n].state != 'free'):
                                continue
                            if tm not in avail_nodes_by_time:
                                avail_nodes_by_time[tm] = []
                            if (nodes[n].attributes['sharing'] in
                                    ('default_excl', 'force_excl')):
                                avail_nodes_by_time[tm].append(nodes[n])
                                try:
                                    nodes_id.remove(n)
                                except:
                                    pass
                            else:
                                ncopy = copy.copy(nodes[n])
                                ncopy.attributes = copy.deepcopy(
                                    nodes[n].attributes)
                                avail_nodes_by_time[tm].append(ncopy)
                                self.alloc_resource(nodes[n], resc)

        # remaining nodes are free "forever"
        for node in nodes_id:
            if self.nodes[node].state == 'free':
                if 'infinity' not in avail_nodes_by_time:
                    avail_nodes_by_time['infinity'] = [nodes[node]]
                else:
                    avail_nodes_by_time['infinity'].append(nodes[node])

        # if there is a dedicated time, move the availaility time up to that
        # time as necessary
        if self.scheduler:
            scheduler = self.scheduler
        else:
            scheduler = Scheduler(server=self)
        scheduler.parse_dedicated_time()

        if scheduler.dedicated_time:
            dedtime = scheduler.dedicated_time[0]['from'] - int(self.ctime)
            if dedtime <= int(time.time()):
                dedtime = None
        else:
            dedtime = None

        # finally, build the equivalence classes off of the nodes availability
        # over time
        self.logger.debug("Building equivalence classes")
        whazzup = {}
        if 'state' in attrib:
            attrib.remove('state')
        for tm, nds in avail_nodes_by_time.items():
            equiv = self.equivalence_classes(VNODE, attrib, bslist=nds,
                                             show_zero_resources=False)
            if dedtime and (tm > dedtime or tm == 'infinity'):
                tm = dedtime
            if tm != 'infinity':
                tm = str(datetime.timedelta(seconds=int(tm)))
            whazzup[tm] = equiv

        return whazzup

    def show_whats_available(self, wa=None, attrib=None, jobs=None,
                             resvs=None, nodes=None):
        """
        helper function to show availability as computed by whats_available

        wa - a dictionary of available attributes. see whats_available for a\
             description of the remaining parameters
        """
        if wa is None:
            wa = self.whats_available(attrib, jobs, resvs, nodes)
        if len(wa) > 0:
            print "%24s\t%s" % ("Duration of availability", "Resources")
            print "-------------------------\t----------"
        swa = sorted(wa.items(), key=lambda x: x[0])
        for (k, eq_classes) in swa:
            for eq_cl in eq_classes:
                print "%24s\t%s" % (str(k), str(eq_cl))

    def utilization(self, resources=None, nodes=None, jobs=None, entity={}):
        """
        Return utilization of consumable resources on a set of nodes

        nodes - A list of dictionary of nodes on which to compute utilization.
        Defaults to nodes resulting from a stat call to the current server.

        resources - comma-separated list of resources to compute utilization
        on. The name of the resource is for example, ncpus or mem

        entity - An optional dictionary of entities to compute utilization of,
        e.g. {'user':u1, 'group':g1, 'project'=p1}

        The utilization is returned as a dictionary of percentage utilization
        for each resource.

        Non-consumable resources are silently ignored.
        """
        if nodes is None:
            nodes = self.status(NODE)

        if jobs is None:
            jobs = self.status(JOB)

        if resources is None:
            rescs = ['ncpus', 'mem']
        else:
            rescs = resources

        utilization = {}
        resavail = {}
        resassigned = {}
        usednodes = 0
        totnodes = 0
        nodes_set = set()

        for res in rescs:
            resavail[res] = 0
            resassigned[res] = 0

        # If an entity is specified utilization must be collected from the
        # Jobs usage, otherwise we can get the information directly from
        # the nodes.
        if len(entity) > 0 and jobs is not None:
            for job in jobs:
                if 'job_state' in job and job['job_state'] != 'R':
                    continue
                entity_match = True
                for k, v in entity.items():
                    if k not in job or job[k] != v:
                        entity_match = False
                        break
                if entity_match:
                    for res in rescs:
                        r = 'Resource_List.' + res
                        if r in job:
                            tmpr = int(self.utils.decode_value(job[r]))
                            resassigned[res] += tmpr
                    if 'exec_host' in job:
                        hosts = ResourceResv.get_hosts(job['exec_host'])
                        nodes_set |= set(hosts)

        for node in nodes:
            # skip nodes in non-schedulable state
            nstate = node['state']
            if ('down' in nstate or 'unavailable' in nstate or
                    'unknown' in nstate or 'Stale' in nstate):
                continue

            totnodes += 1

            # If an entity utilization was requested, all used nodes were
            # already filtered into the nodes_set specific to that entity, we
            # simply add them up. If no entity was requested, it suffices to
            # have the node have a jobs attribute to count it towards total
            # used nodes
            if len(entity) > 0:
                if node['id'] in nodes_set:
                    usednodes += 1
            elif 'jobs' in node:
                usednodes += 1

            for res in rescs:
                avail = 'resources_available.' + res
                if avail in node:
                    val = self.utils.decode_value(node[avail])
                    if isinstance(val, int):
                        resavail[res] += val

                        # When entity matching all resources assigned are
                        # accounted for by the job usage
                        if len(entity) == 0:
                            assigned = 'resources_assigned.' + res
                            if assigned in node:
                                val = self.utils.decode_value(node[assigned])
                                if isinstance(val, int):
                                    resassigned[res] += val

        for res in rescs:
            if res in resavail:
                if res in resassigned:
                    if resavail[res] > 0:
                        utilization[res] = [resassigned[res], resavail[res]]

        # Only report nodes utilization if no specific resources were requested
        if resources is None:
            utilization['nodes'] = [usednodes, totnodes]

        return utilization

    def create_vnodes(self, name=None, attrib=None, num=1, mom=None,
                      additive=False, sharednode=True, restart=True,
                      delall=True, natvnode=None, usenatvnode=False,
                      attrfunc=None, fname=None, vnodes_per_host=1,
                      createnode=True, expect=True):
        """
        helper function to create vnodes.

        name - prefix name of the vnode(s) to create

        attrib - attributes to assign to each node

        num - the number of vnodes to create. Defaults to 1

        mom - the MoM object on which the vnode definition is to be inserted

        additive - If True, vnodes are added to the existing vnode defs.
        Defaults to False.

        sharednode - If True, all vnodes will share the same host.
        Defaults to True.

        restart - If True the MoM will be restarted.

        delall - If True delete all server nodes prior to inserting vnodes

        natvnode - name of the natural vnode.
        i.e. The node name in qmgr -c "create node <name>"

        usenatvnode - count the natural vnode as an allocatable node.

        attrfunc - an attribute=value function generator, see create_vnode_def

        fname - optional name of the vnode def file

        vnodes_per_host - number of vnodes per host

        createnode - whether to create the node via manage or not. Defaults
        to True

        expect - whether to expect attributes to be set or not. Defaults to
        True

        return True on success and False otherwise
        """
        if mom is None or name is None or attrib is None:
            self.logger.error("name, attributes, and mom object are required")
            return False

        if delall:
            try:
                rv = self.manager(MGR_CMD_DELETE, NODE, None, "")
                if rv != 0:
                    return False
            except PbsManagerError:
                pass

        if natvnode is None:
            natvnode = mom.shortname

        vdef = mom.create_vnode_def(name, attrib, num, sharednode,
                                    usenatvnode=usenatvnode, attrfunc=attrfunc,
                                    vnodes_per_host=vnodes_per_host)
        mom.insert_vnode_def(vdef, fname=fname, additive=additive,
                             restart=restart)
        if createnode:
            try:
                statm = self.status(NODE, id=natvnode)
            except:
                statm = []
            if len(statm) >= 1:
                _m = 'Mom %s already exists, not creating' % (natvnode)
                self.logger.info(_m)
            else:
                if mom.pbs_conf and 'PBS_MOM_SERVICE_PORT' in mom.pbs_conf:
                    m_attr = {'port': mom.pbs_conf['PBS_MOM_SERVICE_PORT']}
                else:
                    m_attr = None
                self.manager(MGR_CMD_CREATE, NODE, m_attr, natvnode)
        attrs = {}
        # only expect if vnodes were added rather than the nat vnode modified
        if expect and num > 0:
            for k, v in attrib.items():
                attrs[str(k) + '=' + str(self.utils.decode_value(v))] = num
            attrs['state=free'] = num
            rv = self.expect(VNODE, attrs, attrop=PTL_AND)
        else:
            rv = True
        return rv

    def create_moms(self, name=None, attrib=None, num=1, delall=True,
                    createnode=True, conf_prefix='pbs.conf_m',
                    home_prefix='pbs_m', momhosts=None, init_port=15011,
                    step_port=2):
        """
        Create MoM configurations and optionall add them to the server. Unique
        pbs.conf files are defined and created on each hosts on which MoMs are
        to be created.

        name - Optional prefix name of the nodes to create. Defaults to the
        name of the MoM host.

        attrib - Optional node attributes to assign to the MoM.

        num - Number of MoMs to create

        delall - Whether to delete all nodes on the server. Defaults to True.

        createnode - Whether to create the nodes and add them to the server.
        Defaults to True.

        conf_prefix - The prefix of the PBS conf file. Defaults to pbs.conf_m

        home_prefix - The prefix of the PBS_HOME directory. Defaults to pbs_m

        momhosts - A list of hosts on which to deploy num MoMs.

        init_port - The initial port number to start assigning
        PBS_MOM_SERIVCE_PORT to. Default 15011.

        step_port - The increments at which ports are allocated. Defaults to 2.
        Note that since PBS requires that
        PBS_MANAGER_SERVICE_PORT = PBS_MOM_SERVICE_PORT+1
        The step number must be greater or equal to 2.
        """

        if not self.isUp():
            logging.error("An up and running PBS server on " + self.hostname +
                          " is required")
            return False

        if delall:
            try:
                rc = self.manager(MGR_CMD_DELETE, NODE, None, "")
            except PbsManagerError, e:
                rc = e.rc
            if rc:
                if len(self.status(NODE)) > 0:
                    self.logger.error("create_moms: Error deleting all nodes")
                    return False

        pi = PBSInitServices()
        if momhosts is None:
            momhosts = [self.hostname]

        if attrib is None:
            attrib = {}

        error = False
        for hostname in momhosts:
            _pconf = self.du.parse_pbs_config(hostname)
            if 'PBS_HOME' in _pconf:
                _hp = _pconf['PBS_HOME']
                if _hp.endswith('/'):
                    _hp = _hp[:-1]
                _hp = os.path.dirname(_hp)
            else:
                _hp = '/var/spool'
            _np_conf = _pconf
            _np_conf['PBS_START_SERVER'] = '0'
            _np_conf['PBS_START_SCHED'] = '0'
            _np_conf['PBS_START_MOM'] = '1'
            for i in xrange(0, num * step_port, step_port):
                _np = os.path.join(_hp, home_prefix + str(i))
                _n_pbsconf = os.path.join('/etc', conf_prefix + str(i))
                _np_conf['PBS_HOME'] = _np
                port = init_port + i
                _np_conf['PBS_MOM_SERVICE_PORT'] = str(port)
                _np_conf['PBS_MANAGER_SERVICE_PORT'] = str(port + 1)
                self.du.set_pbs_config(hostname, fout=_n_pbsconf,
                                       confs=_np_conf)
                pi.initd(hostname, conf_file=_n_pbsconf, op='start')
                m = MoM(hostname, pbsconf_file=_n_pbsconf)
                if m.isUp():
                    m.stop()
                if hostname != self.hostname:
                    m.add_config({'$clienthost': self.hostname})
                try:
                    m.start()
                except PbsServiceError:
                    # The service failed to start
                    self.logger.error("Service failed to start using port " +
                                      str(port) + "...skipping")
                    self.du.rm(hostname, _n_pbsconf)
                    continue
                if createnode:
                    attrib['Mom'] = hostname
                    attrib['port'] = port
                    if name is None:
                        name = hostname.split('.')[0]
                    _n = name + '-' + str(i)
                    rc = self.manager(MGR_CMD_CREATE, NODE, attrib, id=_n)
                    if rc != 0:
                        self.logger.error("error creating node " + _n)
                        error = True
        if error:
            return False

        return True

    def create_hook(self, name, attrs):
        """
        Helper function to create a hook by name.

        name - The name of the hook to create

        attrs - The attributes to create the hook with.

        If hook already exists, return False, on failure to create raises
        PbsManagerError, otherwise return True.
        """
        hooks = self.status(HOOK)
        if ((hooks is None or len(hooks) == 0) or
                (name not in map(lambda x: x['id'], hooks))):
            self.manager(MGR_CMD_CREATE, HOOK, None, name)
        else:
            self.logger.error('hook named ' + name + ' exists')
            return False

        self.manager(MGR_CMD_SET, HOOK, attrs, id=name, expect=True)
        return True

    def import_hook(self, name, body):
        """
        Helper function to import hook body into hook by name.
        The hook must have been created prior to calling this function.

        name - The name of the hook to import body to

        body - The body of the hook as a string.

        Return True on success, raises PbsManagerError on error
        """
        (fd, fn) = self.du.mkstemp()
        os.write(fd, body)
        os.close(fd)

        if not self._is_local:
            tmpdir = self.du.get_tempdir(self.hostname)
            rfile = os.path.join(tmpdir, os.path.basename(fn))
            self.du.run_copy(self.hostname, fn, rfile)
        else:
            rfile = fn

        a = {'content-type': 'application/x-python',
             'content-encoding': 'default',
             'input-file': rfile}
        self.manager(MGR_CMD_IMPORT, HOOK, a, name)

        os.remove(rfile)
        if not self._is_local:
            self.du.rm(self.hostname, rfile)

        self.logger.info('server ' + self.shortname +
                         ': imported hook body\n---\n' + body + '---')
        return True

    def create_import_hook(self, name, attrs=None, body=None, overwrite=True):
        """
        Helper function to create a hook, import content into it, set the event
        and enable it.

        name - The name of the hook to create

        attrs - The attributes to create the hook with. Event and Enabled are
        mandatory. No defaults.

        body - The hook body as a string

        overwrite - If True, if a hook of the same name already exists, bypass
        its creation. Defaults to True

        Return True on success and False otherwise
        """
        if 'event' not in attrs:
            self.logger.error('attrs must specify at least an event and key')
            return False

        hook_exists = False
        hooks = self.status(HOOK)
        for h in hooks:
            if h['id'] == name:
                hook_exists = True

        if not hook_exists or not overwrite:
            rv = self.create_hook(name, attrs)
            if not rv:
                return False
        else:
            if attrs is None:
                attrs = {'enabled': 'true'}
            rc = self.manager(MGR_CMD_SET, HOOK, attrs, id=name)
            if rc != 0:
                return False

        # In 12.0 A MoM hook must be enabled and the event set prior to
        # importing, otherwise the MoM does not get the hook content
        return self.import_hook(name, body)

    def evaluate_formula(self, jobid=None, formula=None, full=True,
                         include_running_jobs=False, exclude_subjobs=True):
        """
        Evaluate the job sort formula

        jobid - If set, evaluate the formula for the given jobid, if not set,
        formula is evaluated for all jobs in state Q

        formula - If set use the given formula. If not set, the server's
        formula, if any, is used

        full - If True, returns a dictionary of job identifiers as keys and
        the evaluated formula as values. Returns None if no formula is used.
        Each job id formula is returned as a tuple (s,e) where s is the formula
        expression associated to the job and e is the evaluated numeric value
        of that expression, for example, if job_sort_formula is ncpus + mem
        a job requesting 2 cpus and 100kb of memory would return
        ('2 + 100', 102). If False, if a jobid is specified, return the
        integer value of the evaluated formula.

        include_running_jobs - If True, reports formula value of running jobs.
        Defaults to False.

        exclude_subjobs - If True, only report formula of parent job array
        """
        _f_builtins = ['queue_priority', 'job_priority', 'eligible_time',
                       'fair_share_perc']
        if formula is None:
            d = self.status(SERVER, 'job_sort_formula')
            if len(d) > 0 and 'job_sort_formula' in d[0]:
                formula = d[0]['job_sort_formula']
            else:
                return None

        template_formula = self.utils._make_template_formula(formula)
        # to split up the formula into keywords, first convert all possible
        # operators into spaces and split the string.
        # TODO: The list of operators may need to be expanded
        T = string.maketrans('()%+*/-', ' ' * 7)
        fres = string.translate(formula, T).split()
        if jobid:
            d = self.status(JOB, id=jobid, extend='t')
        else:
            d = self.status(JOB, extend='t')
        ret = {}
        for job in d:
            if not include_running_jobs and job['job_state'] != 'Q':
                continue
            f_value = {}
            # initialize the formula values to 0
            for res in fres:
                f_value[res] = 0
            if 'queue_priority' in fres:
                queue = self.status(JOB, 'queue', id=job['id'])[0]['queue']
                d = self.status(QUEUE, 'Priority', id=queue)
                if d and 'Priority' in d[0]:
                    qprio = int(d[0]['Priority'])
                    f_value['queue_priority'] = qprio
                else:
                    continue
            if 'job_priority' in fres:
                if 'Priority' in job:
                    jprio = int(job['Priority'])
                    f_value['job_priority'] = jprio
                else:
                    continue
            if 'eligible_time' in fres:
                if 'eligible_time' in job:
                    f_value['eligible_time'] = self.utils.convert_duration(
                        job['eligible_time'])
            if 'fair_share_perc' in fres:
                if self.scheduler is None:
                    self.scheduler = Scheduler(server=self)

                if 'fairshare_entity' in self.scheduler.sched_config:
                    entity = self.scheduler.sched_config['fairshare_entity']
                else:
                    self.logger.error(self.logprefix +
                                      ' no fairshare entity in sched config')
                    continue
                if entity not in job:
                    self.logger.error(self.logprefix +
                                      ' job does not have property ' + entity)
                    continue
                try:
                    fs_info = self.scheduler.query_fairshare(name=job[entity])
                    if fs_info is not None and 'TREEROOT' in fs_info.perc:
                        f_value['fair_share_perc'] = \
                            (fs_info.perc['TREEROOT'] / 100)
                except PbsFairshareError:
                    f_value['fair_share_perc'] = 0

            for job_res, val in job.items():
                val = self.utils.decode_value(val)
                if job_res.startswith('Resource_List.'):
                    job_res = job_res.replace('Resource_List.', '')
                if job_res in fres and job_res not in _f_builtins:
                    f_value[job_res] = val
            tf = string.Template(template_formula)
            tfstr = tf.safe_substitute(f_value)
            if (jobid is not None or not exclude_subjobs or
                    (exclude_subjobs and not self.utils.is_subjob(job['id']))):
                ret[job['id']] = (tfstr, eval(tfstr))
        if not full and jobid is not None and jobid in ret:
            return ret[job['id']][1]
        return ret

    def _parse_limits(self, container=None, dictlist=None, id=None,
                      db_access=None):
        """
        Helper function to parse limits syntax on a given container.

        container - The PBS object to query, one of QUEUE or SERVER.
        Metascheduling node group limits are not yet queri-able

        dictlist - A list of dictionaries off of a batch status

        id - Optional id of the object to query

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        if container is None:
            self.logger.error('parse_limits expect container to be set')
            return {}

        if dictlist is None:
            d = self.status(container, db_access=db_access)
        else:
            d = dictlist

        if not d:
            return {}

        limits = {}
        for obj in d:
            # filter the id here instead of during the stat call so that
            # we can call a full stat once rather than one stat per object
            if id is not None and obj['id'] != id:
                continue
            for k, v in obj.items():
                if k.startswith('max_run'):
                    v = v.split(',')
                    for rval in v:
                        rval = rval.strip("'")
                        l = self.utils.parse_fgc_limit(k + '=' + rval)
                        if l is None:
                            self.logger.error("Couldn't parse limit: " +
                                              k + str(rval))
                            continue

                        (lim_type, resource, etype, ename, value) = l
                        if (etype, ename) not in self.entities:
                            entity = Entity(etype, ename)
                            self.entities[(etype, ename)] = entity
                        else:
                            entity = self.entities[(etype, ename)]

                        lim = Limit(lim_type, resource, entity, value,
                                    container, obj['id'])

                        if container in limits:
                            limits[container].append(lim)
                        else:
                            limits[container] = [lim]

                        entity.set_limit(lim)
        return limits

    def parse_server_limits(self, server=None, db_access=None):
        """
        Parse all server limits

        server - list of dictionary of server data

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        return self._parse_limits(SERVER, server, db_access=db_access)

    def parse_queue_limits(self, queues=None, id=None, db_access=None):
        """
        Parse queue limits

        queues - list of dictionary of queue data

        id - The id of the queue to parse limit for. If None, all queue limits
        are parsed

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        return self._parse_limits(QUEUE, queues, id=id, db_access=db_access)

    def parse_all_limits(self, server=None, queues=None, db_access=None):
        """
        Parse all server and queue limits

        server - list of dictionary of server data

        queues - list of dictionary of queue data

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        if hasattr(self, 'limits'):
            del self.limits

        slim = self.parse_server_limits(server, db_access=db_access)
        qlim = self.parse_queue_limits(queues, id=None, db_access=db_access)
        self.limits = dict(slim.items() + qlim.items())
        del slim
        del qlim
        return self.limits

    def limits_info(self, etype=None, ename=None, server=None, queues=None,
                    jobs=None, db_access=None, over=False):
        """
        Collect limit information for each entity on which a server/queue limit
        is applied.

        etype - entity type, one of u, g, p, o

        ename - entity name

        server - optional list of dictionary representation of server object

        queues - optional list of dictionary representation of queues object

        jobs - optional list of dictionary representation of jobs object

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}

        over - If True, show only entities that are over their limit.
        Default is False.

        Returns a list of dictionary similar to that returned by a converted
        batch_status object, i.e., can be displayed using the Utils.show
        method
        """
        def create_linfo(lim, entity_type, id, used):
            tmp = {}
            tmp['id'] = entity_type + ':' + id
            c = [PBS_OBJ_MAP[lim.container]]
            if lim.container_id:
                c += [':', lim.container_id]
            tmp['container'] = "".join(c)
            s = [str(lim.limit_type)]
            if lim.resource:
                s += ['.', lim.resource]
            tmp['limit_type'] = "".join(s)
            tmp['usage/limit'] = "".join([str(used), '/', str(lim.value)])
            tmp['remainder'] = int(lim.value) - int(used)

            return tmp

        def calc_usage(jobs, attr, name=None, resource=None):
            usage = {}
            # initialize usage of the named entity
            if name is not None and name not in ('PBS_GENERIC', 'PBS_ALL'):
                usage[name] = 0
            for j in jobs:
                entity = j[attr]
                if entity not in usage:
                    if resource:
                        usage[entity] = int(
                            self.utils.decode_value(
                                j['Resource_List.' + resource]))
                    else:
                        usage[entity] = 1
                else:
                    if resource:
                        usage[entity] += int(
                            self.utils.decode_value(
                                j['Resource_List.' + resource]))
                    else:
                        usage[entity] += 1
            return usage

        self.parse_all_limits(server, queues, db_access)
        entities_p = self.entities.values()

        linfo = []
        cache = {}

        if jobs is None:
            jobs = self.status(JOB)

        for entity in sorted(entities_p, key=lambda e: e.name):
            for lim in entity.limits:
                _t = entity.type
                # skip non-matching entity types. We can't skip the entity
                # name due to proper handling of the PBS_GENERIC limits
                # we also can't skip overall limits
                if (_t != 'o') and (etype is not None and etype != _t):
                    continue

                _n = entity.name

                a = {}
                if lim.container == QUEUE and lim.container_id is not None:
                    a['queue'] = (EQ, lim.container_id)
                if lim.resource:
                    resource = 'Resource_List.' + lim.resource
                    a[resource] = (GT, 0)
                a['job_state'] = (EQ, 'R')
                a['substate'] = (EQ, 42)
                if etype == 'u' and ename is not None:
                    a['euser'] = (EQ, ename)
                else:
                    a['euser'] = (SET, '')
                if etype == 'g' and ename is not None:
                    a['egroup'] = (EQ, ename)
                else:
                    a['egroup'] = (SET, '')
                if etype == 'p' and ename is not None:
                    a['project'] = (EQ, ename)
                else:
                    a['project'] = (SET, '')

                # optimization: cache filtered results
                d = None
                for v in cache.keys():
                    if cmp(a, eval(v)) == 0:
                        d = cache[v]
                        break
                if d is None:
                    d = self.filter(JOB, a, bslist=jobs, attrop=PTL_AND,
                                    idonly=False, db_access=db_access)
                    cache[str(a)] = d
                if not d or 'job_state=R' not in d:
                    # in the absence of jobs, display limits defined with usage
                    # of 0
                    if ename is not None:
                        _u = {ename: 0}
                    else:
                        _u = {_n: 0}
                else:
                    if _t in ('u', 'o'):
                        _u = calc_usage(
                            d['job_state=R'], 'euser', _n, lim.resource)
                        # an overall limit applies across all running jobs
                        if _t == 'o':
                            all_used = sum(_u.values())
                            for k in _u.keys():
                                _u[k] = all_used
                    elif _t == 'g':
                        _u = calc_usage(
                            d['job_state=R'], 'egroup', _n, lim.resource)
                    elif _t == 'p':
                        _u = calc_usage(
                            d['job_state=R'], 'project', _n, lim.resource)

                for k, used in _u.items():
                    if not over or (int(used) > int(lim.value)):
                        if ename is not None and k != ename:
                            continue
                        if _n in ('PBS_GENERIC', 'PBS_ALL'):
                            if k not in ('PBS_GENERIC', 'PBS_ALL'):
                                k += '/' + _n
                        elif _n != k:
                            continue
                        tmp_linfo = create_linfo(lim, _t, k, used)
                        linfo.append(tmp_linfo)
                del a
        del cache
        return linfo

    def __insert_jobs_in_db(self, jobs, hostname=None):
        """
        An experimental interface that converts jobs from file into entries
        in the PBS database that can be recovered upon server restart if all
        other objects, queues, resources, etc... are already defined.

        The interface to PBS used in this method is incomplete and will most
        likely cause serious issues. Use only for development purposes
        """

        if not jobs:
            return []

        if hostname is None:
            hostname = socket.gethostname()

        # a very crude, and not quite maintainale way to get the flag value
        # of an attribute. This is one of the reasons why this conversion
        # of jobs is highly experimental
        flag_map = {'ctime': 9, 'qtime': 9, 'hop_count': 9, 'queue_rank': 9,
                    'queue_type': 9, 'etime': 9, 'job_kill_delay': 9,
                    'run_version': 9, 'job_state': 9, 'exec_host': 9,
                    'exec_host2': 9, 'exec_vnode': 9, 'mtime': 9, 'stime': 9,
                    'substate': 9, 'hashname': 9, 'comment': 9, 'run_count': 9,
                    'schedselect': 13}

        state_map = {'Q': 1, 'H': 2, 'W': 3, 'R': 4, 'E': 5, 'X': 6, 'B': 7}

        job_attr_stmt = ("INSERT INTO pbs.job_attr (ji_jobid, attr_name, "
                         "attr_resource, attr_value, attr_flags)")

        job_stmt = ("INSERT INTO pbs.job (ji_jobid, ji_sv_name, ji_state, "
                    "ji_substate,ji_svrflags, ji_numattr,"
                    " ji_ordering, ji_priority, ji_stime, ji_endtbdry, "
                    "ji_queue, ji_destin, ji_un_type, ji_momaddr, "
                    "ji_momport, ji_exitstat, ji_quetime, ji_rteretry, "
                    "ji_fromsock, ji_fromaddr, ji_4jid, ji_4ash, "
                    "ji_credtype, ji_qrank, ji_savetm, ji_creattm)")

        all_stmts = []

        for job in jobs:

            keys = []
            values = []
            flags = []

            for k, v in job.items():
                if k in ('id', 'Mail_Points', 'Mail_Users'):
                    continue
                keys.append(k)
                if not v.isdigit():
                    values.append("'" + v + "'")
                else:
                    values.append(v)
                if k in flag_map:
                    flags.append(flag_map[k])
                elif k.startswith('Resource_List'):
                    flags.append(15)
                else:
                    flags.append(11)

            jobid = job['id'].split('.')[0] + '.' + hostname

            for i in range(len(keys)):
                stmt = job_attr_stmt
                stmt += " VALUES('" + jobid + "', "
                if '.' in keys[i]:
                    k, v = keys[i].split('.')
                    stmt += "'" + k + "', '" + v + "'" + ", "
                else:
                    stmt += "'" + keys[i] + "', ''" + ", "
                stmt += values[i] + "," + str(flags[i])
                stmt += ");"
                self.logger.debug(stmt)
                all_stmts.append(stmt)

            js = job['job_state']
            svrflags = 1
            state = 1
            if js in state_map:
                state = state_map[js]
                if state == 4:
                    # Other states svrflags aren't handled and will
                    # cause issues, another reason this is highly experimental
                    svrflags = 12289

            tm = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            stmt = job_stmt
            stmt += " VALUES('" + jobid + "', 1, "
            stmt += str(state) + ", " + job['substate']
            stmt += ", " + str(svrflags)
            stmt += ", 0, 0, 0"
            if 'stime' in job:
                print job['stime']
                st = time.strptime(job['stime'], "%a %b %d %H:%M:%S %Y")
                stmt += ", " + str(time.mktime(st))
            else:
                stmt += ", 0"
            stmt += ", 0"
            stmt += ", '" + job['queue'] + "'"
            if 'exec_host2' in job:
                stmt += ", " + job['exec_host2']
            else:
                stmt += ", ''"
            stmt += ", 0, 0, 0, 0, 0, 0, 0, 0, '', '', 0, 0"
            stmt += ", '" + tm + "', '" + tm + "');"
            self.logger.debug(stmt)

            all_stmts.append(stmt)

        return all_stmts

    def clusterize(self, conf_file=None, hosts=None, import_jobs=False,
                   db_creds_file=None):
        """
        Mimic a pbs_diag snapshot onto a set of hosts running a PBS server,
        scheduler, and MoM.

        This method clones the following information from the diag:

        Server attributes
        Server resourcedef
        Hooks
        Scheduler configuration
        Scheduler resource_group
        Scheduler holiday file
        Per Queue attributes

        Nodes are copied as a vnode definition file inserted into each host's
        MoM instance.

        Currently no support for cloning the server 'sched' object, nor to
        copy nodes to multi-mom instances.

        Jobs are copied over only if import_jobs is True, see below for details

        Paramters:

        asdiag - Path to the pbs_diag snapshot to use

        conf_file - Configuration file for the MoM instance

        hosts - List of hosts on which to clone the diag snapshot

        include_jobs - [Experimental] if True jobs from the pbs_diag are
        imported into the host's database. There are several caveats to this
        option:
        The scripts are not imported
        The users and groups are not created on the local system
        There are no actual processes created on the MoM for each job so
        operations on the job such as signals or delete will fail (delete -W
        force will still work)

        db_creds_file - Path to file containing credentials to access the DB
        """
        if not self.has_diag:
            return
        if hosts is None:
            return
        for h in hosts:
            svr = Server(h)
            sched = Scheduler(server=svr, diag=self.diag, diagmap=self.diagmap)
            try:
                svr.manager(MGR_CMD_DELETE, NODE, None, id="")
            except:
                pass
            svr.revert_to_defaults(delqueues=True, delhooks=True)
            local = svr.pbs_conf['PBS_HOME']

            diag_rdef = os.path.join(self.diag, 'server_priv', 'resourcedef')
            diag_sc = os.path.join(self.diag, 'sched_priv', 'sched_config')
            diag_rg = os.path.join(self.diag, 'sched_priv', 'resource_group')
            diag_hldy = os.path.join(self.diag, 'sched_priv', 'holidays')
            nodes = os.path.join(self.diag, 'pbsnodes_va.out')
            diag_hooks = os.path.join(self.diag, 'qmgr_ph.out')
            diag_ps = os.path.join(self.diag, 'qmgr_ps.out')

            local_rdef = os.path.join(local, 'server_priv', 'resourcedef')
            local_sc = os.path.join(local, 'sched_priv', 'sched_config')
            local_rg = os.path.join(local, 'sched_priv', 'resource_group')
            local_hldy = os.path.join(local, 'sched_priv', 'holidays')

            _fcopy = [(diag_rdef, local_rdef), (diag_sc, local_sc),
                      (diag_rg, local_rg), (diag_hldy, local_hldy)]

            # Restart since resourcedef may have changed
            svr.restart()

            if os.path.isfile(diag_ps):
                tmp_ps = open(diag_ps)
                cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin', 'qmgr')]
                self.du.run_cmd(h, cmd, stdin=tmp_ps, sudo=True, logerr=False)
                tmp_ps.close()

            # Unset any site-sensitive attributes
            for a in ['pbs_license_info', 'manager', 'operators',
                      'mail_from', 'acl_roots', 'acl_hosts']:
                try:
                    svr.manager(MGR_CMD_UNSET, SERVER, a, sudo=True)
                except:
                    pass

            for (d, l) in _fcopy:
                if os.path.isfile(d):
                    self.logger.info('copying ' + d + ' to ' + l)
                    self.du.run_copy(h, src=d, dest=l, sudo=True)

            diag_sched = self.status(SCHED)
            for ds in diag_sched:
                for k, v in ds.items():
                    if k != 'id':
                        try:
                            svr.manager(MGR_CMD_SET, SCHED, {k: v},
                                        logerr=False)
                        except PbsManagerError:
                            self.logger.warning('Skipping sched attribute ' + k)
            sched.signal('-HUP')

            if os.path.isfile(nodes):
                f = open(nodes)
                lines = f.readlines()
                f.close()
                dl = self.utils.convert_to_dictlist(lines)
                vdef = self.utils.dictlist_to_vnodedef(dl)
                if vdef:
                    try:
                        svr.manager(MGR_CMD_DELETE, NODE, None, "")
                    except:
                        pass
                    MoM(h, pbsconf_file=conf_file).insert_vnode_def(vdef)
                    svr.restart()
                    svr.manager(MGR_CMD_CREATE, NODE, id=svr.shortname)
                # check if any node is associated to a queue.
                # This is needed because the queues 'hasnodes' attribute
                # does not get set through vnode def update and must be set
                # via qmgr. It only needs to be set once, not for each node
                qtoset = {}
                for n in dl:
                    if 'queue' in n and n['queue'] not in qtoset:
                        qtoset[n['queue']] = n['id']

                # before setting queue on nodes make sure that the vnode
                # def is all set
                svr.expect(NODE, {'state=free': (GE, len(dl))}, interval=3)
                for k, v in qtoset.items():
                    svr.manager(MGR_CMD_SET, NODE, {'queue': k}, id=v)

            # populate hooks
            if os.path.isfile(diag_hooks):
                tmp_hook = open(diag_hooks)
                cmd = [os.path.join(svr.pbs_conf['PBS_EXEC'], 'bin', 'qmgr')]
                self.du.run_cmd(h, cmd, stdin=tmp_hook, sudo=True)
                tmp_hook.close()

            # import jobs
            if import_jobs is not None:
                jobs = self.status(JOB)
                sql_stmt = self.__insert_jobs_in_db(jobs, h)
                print "\n".join(sql_stmt)
                if db_creds_file is not None:
                    pass


class EquivClass(PBSObject):

    """
    Equivalence class holds information on a collection of entities grouped
    according to a set of attributes
    """

    def __init__(self, name, attributes={}, entities=[]):
        self.name = name
        self.attributes = attributes
        self.entities = entities
        self.logger = logging.getLogger(__name__)

    def add_entity(self, entity):
        if entity not in self.entities:
            self.entities.append(entity)

    def __str__(self):
        s = [str(len(self.entities)), ":", ":".join(self.name)]
        return "".join(s)

    def show(self, showobj=False):
        s = " && ".join(self.name) + ': '
        if showobj:
            s += str(self.entities)
        else:
            s += str(len(self.entities))
        print s
        return s


class Resource(PBSObject):

    """
    PBS resource referenced by name, type and flag
    """

    def __init__(self, name=None, type=None, flag=None):
        PBSObject.__init__(self, name)
        self.set_name(name)
        self.set_type(type)
        self.set_flag(flag)

    def set_name(self, name):
        self.name = name
        self.attributes['id'] = name

    def set_type(self, type):
        self.type = type
        self.attributes['type'] = type

    def set_flag(self, flag):
        self.flag = flag
        self.attributes['flag'] = flag

    def __str__(self):
        s = [self.attributes['id']]
        if 'type' in self.attributes:
            s.append('type=' + self.attributes['type'])
        if 'flag' in self.attributes:
            s.append('flag=' + self.attributes['flag'])
        return " ".join(s)


class Holidays():

    def __init__(self):
        self.year = {'id': "YEAR", 'value': None, 'valid': False}
        self.weekday = {'id': "weekday", 'p': None, 'np': None, 'valid': None,
                        'position': None}
        self.monday = {'id': "monday", 'p': None, 'np': None, 'valid': None,
                       'position': None}
        self.tuesday = {'id': "tuesday", 'p': None, 'np': None, 'valid': None,
                        'position': None}
        self.wednesday = {'id': "wednesday", 'p': None, 'np': None,
                          'valid': None, 'position': None}
        self.thursday = {'id': "thursday", 'p': None, 'np': None,
                         'valid': None, 'position': None}
        self.friday = {'id': "friday", 'p': None, 'np': None, 'valid': None,
                       'position': None}
        self.saturday = {'id': "saturday", 'p': None, 'np': None,
                         'valid': None, 'position': None}
        self.sunday = {'id': "sunday", 'p': None, 'np': None, 'valid': None,
                       'position': None}

        self.days_set = []  # list of set days
        self._days_map = {'weekday': self.weekday, 'monday': self.monday,
                          'tuesday': self.tuesday, 'wednesday': self.wednesday,
                          'thursday': self.thursday, 'friday': self.friday,
                          'saturday': self.saturday, 'sunday': self.sunday}
        self.holidays = []  # list of calendar holidays

    def __str__(self):
        """
        Return the content to write to holidays file as a string
        """
        content = []
        if self.year['valid']:
            content.append(self.year['id'] + "\t" +
                           self.year['value'])

        for i in range(0, len(self.days_set)):
            content.append(self.days_set[i]['id'] + "\t" +
                           self.days_set[i]['p'] + "\t" +
                           self.days_set[i]['np'])

        # Add calendar holidays
        for day in self.holidays:
            content.append(day)

        return "\n".join(content)


class Scheduler(PBSService):

    """
    Container of Scheduler related properties
    """

    # A vanilla scheduler configuration. This set may change based on
    # updates to PBS
    sched_dflt_config = {
        "backfill": "true        ALL",
        "backfill_prime": "false ALL",
        "help_starving_jobs": "true     ALL",
        "max_starve": "24:00:00",
        "strict_ordering": "false ALL",
        "provision_policy": "\"aggressive_provision\"",
        "preempt_order": "\"SCR\"",
        "fairshare_entity": "euser",
        "dedicated_prefix": "ded",
        "primetime_prefix": "p_",
        "nonprimetime_prefix": "np_",
        "preempt_queue_prio": "150",
        "preempt_prio": "\"express_queue, normal_jobs\"",
        "load_balancing": "false ALL",
        "prime_exempt_anytime_queues": "false",
        "round_robin": "False    all",
        "fairshare_usage_res": "cput",
        "smp_cluster_dist": "pack",
        "fair_share": "false     ALL",
        "preempt_sort": "min_time_since_start",
        "node_sort_key": "\"sort_priority HIGH\" ALL",
        "sort_queues": "true     ALL",
        "by_queue": "True                ALL",
        "preemptive_sched": "true        ALL",
        "resources": "\"ncpus, mem, arch, host, vnode, netwins, aoe\"",
        "log_filter": "3328 ",

    }

    sched_config_options = ["node_group_key",
                            "dont_preempt_starving",
                            "fairshare_enforce_no_shares",
                            "strict_ordering",
                            "resource_unset_infinite",
                            "sync_time",
                            "unknown_shares",
                            "log_filter",
                            "dedicated_prefix",
                            "load_balancing",
                            "help_starving_jobs",
                            "max_starve",
                            "sort_queues",
                            "backfill",
                            "primetime_prefix",
                            "nonprimetime_prefix",
                            "backfill_prime",
                            "prime_exempt_anytime_queues",
                            "prime_spill",
                            "prime_exempt_anytime_queues",
                            "prime_spill",
                            "resources",
                            "mom_resources",
                            "smp_cluster_dist",
                            "preempt_queue_prio",
                            "preempt_suspend",
                            "preempt_checkpoint",
                            "preempt_requeue",
                            "preemptive_sched",
                            "dont_preempt_starving",
                            "node_group_key",
                            "dont_preempt_starving",
                            "fairshare_enforce_no_shares",
                            "strict_ordering",
                            "resource_unset_infinite",
                            "provision_policy",
                            "resv_confirm_ignore",
                            "allow_aoe_calendar",
                            "max_job_check",
                            "preempt_attempts",
                            "update_comments",
                            "sort_by",
                            "key",
                            "preempt_starving",
                            "preempt_fairshare",
                            "load_balancing_rr",
                            "assign_ssinodes",
                            "cpus_per_ssinode",
                            "mem_per_ssinode",
                            "strict_fifo",
                            "mem_per_ssinode",
                            "strict_fifo"
                            ]

    fs_re = '(?P<name>[\S]+)[\s]*:[\s]*Grp:[\s]*(?P<Grp>[-]*[0-9]*)' + \
            '[\s]*cgrp:[\s]*(?P<cgrp>[-]*[0-9]*)[\s]*' + \
            'Shares:[\s]*(?P<Shares>[-]*[0-9]*)[\s]*Usage:[\s]*' + \
            '(?P<Usage>[0-9]+)[\s]*Perc:[\s]*(?P<Perc>.*)%'
    fs_tag = re.compile(fs_re)

    def __init__(self, hostname=None, server=None, pbsconf_file=None,
                 diagmap={}, diag=None, db_access=None):
        """
        Scheduler constructor.

        hostname - The hostname on which the scheduler instance is operating

        server - A PBS server instance to which this scheduler is associated

        pbsconf_file - path to a PBS configuration file

        diagmap - A dictionary of PBS objects (node,server,etc) to mapped files
        from PBS diag directory

        diag - path to PBS diag directory (This will overrides diagmap)

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """
        self.sched_config_file = None
        self.dflt_holidays_file = None
        self.holidays_file = None
        self.sched_config = {}
        self._sched_config_comments = {}
        self._config_order = []
        self.dedicated_time_file = None
        self.dedicated_time = None
        self.dedicated_time_as_str = None
        self.fairshare_tree = None
        self.resource_group = None
        self.server = None
        self.server_dyn_res = None
	self.deletable_files = ['usage']

        self.logger = logging.getLogger(__name__)

        if server is not None:
            self.server = server
            if diag is None and self.server.diag is not None:
                diag = self.server.diag
            if ((len(diagmap) == 0) and (len(self.server.diagmap) != 0)):
                diagmap = self.server.diagmap
        else:
            self.server = Server(hostname, pbsconf_file=pbsconf_file,
                                 db_access=db_access, diag=diag,
                                 diagmap=diagmap)

        if hostname is None:
            hostname = self.server.hostname

        self.server.scheduler = self

        PBSService.__init__(self, hostname, pbsconf_file=pbsconf_file,
                            diag=diag, diagmap=diagmap)
        _m = ['scheduler ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)

        self.pbs_conf = self.server.pbs_conf

        self.sched_config_file = os.path.join(self.pbs_conf['PBS_HOME'],
                                              'sched_priv', 'sched_config')
        self.dflt_sched_config_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                                   'etc', 'pbs_sched_config')
        self.parse_sched_config(self.sched_config_file)

        self.dflt_holidays_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                               'etc', 'pbs_holidays')

        self.holidays_file = os.path.join(self.pbs_conf['PBS_HOME'],
                                          'sched_priv', 'holidays')

        self.dflt_resource_group_file = os.path.join(self.pbs_conf['PBS_EXEC'],
                                                     'etc',
                                                     'pbs_resource_group')

        self.resource_group_file = os.path.join(self.pbs_conf['PBS_HOME'],
                                                'sched_priv', 'resource_group')
        self.fairshare_tree = self.query_fairshare()
        rg = self.parse_resource_group(self.hostname, self.resource_group_file)
        self.resource_group = rg

        try:
            attrs = self.server.status(SCHED, level=logging.DEBUG,
                                       db_access=db_access)
            if attrs is not None and len(attrs) > 0:
                self.attributes = attrs[0]
        except (PbsManagerError, PbsStatusError), e:
            self.logger.error('Error querying scheduler %s' % e.msg)

        self.version = None

        self.holidays_obj = Holidays()
        self.holidays_parse_file(level=logging.DEBUG)

    def isUp(self):
        return super(Scheduler, self)._isUp(self)

    def signal(self, sig):
        self.logger.info('scheduler ' + self.shortname + ': sent signal ' +
                         sig)
        return super(Scheduler, self)._signal(sig, inst=self)

    def get_pid(self):
        return super(Scheduler, self)._get_pid(inst=self)

    def all_instance_pids(self):
        return super(Scheduler, self)._all_instance_pids(inst=self)

    def start(self, args=None, launcher=None):
        return super(Scheduler, self)._start(inst=self, args=args,
                                             launcher=launcher)

    def stop(self, sig='-TERM'):
        self.logger.info(self.logprefix + 'stopping Scheduler on host ' +
                         self.hostname)
        rv = super(Scheduler, self)._stop(sig, inst=self)
        return rv

        self.signal(sig)

        pid = self.get_pid()
        chk_pid = self.all_instance_pids()
        if pid is None or chk_pid is None:
            return True

        num_seconds = 0
        while pid in chk_pid:
            if num_seconds > 10:
                self.logger.error(self.logprefix + 'could not stop Scheduler')
                return False
            time.sleep(1)
            num_seconds += 1
            chk_pid = self.all_instance_pids()
        return True

    def restart(self):
        if self.stop():
            return self.start()
        return False

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, day=None, max_attempts=1, interval=1,
                  starttime=None, endtime=None, level=logging.INFO):
        return self._log_match(self, msg, id, n, tail, allmatch, regexp, day,
                               max_attempts, interval, starttime, endtime,
                               level=level)

    def pbs_version(self):
        " Get the version of the scheduler instance "
        if self.version:
            return self.version

        version = self.log_match('pbs_version', tail=False)
        if version:
            version = version[1].strip().split('=')[1]
        else:
            version = "unknown"

        self.version = LooseVersion(version)

        return self.version

    def parse_sched_config(self, schd_cnfg=None):
        """
        Parse a sceduling configuration file into a dictionary.
        Special handling of identical keys (e.g., node_sort_key) is done
        by appending a delimiter, '%', between each value of the
        key. When printed back to file, each delimited entry gets written
        on a line of its own. For example, the python dictionary entry:

        {'node_sort_key':
        ["ncpus HIGH unusued" prime", "node_priority HIH" non-prime"]}

        will get written as:

        node_sort_key: "ncpus HIGH unusued" prime
        node_sort_key: "node_priority HIGH"  non-prime

        Returns sched_config dictionary that gets reinitialized every time
        this method is called.
        """
        # sched_config is initialized
        if self.sched_config:
            del(self.sched_config)
            self.sched_config = {}
            self._sched_config_comments = {}
            self._config_order = []

        if schd_cnfg is None:
            if self.sched_config_file is not None:
                schd_cnfg = self.sched_config_file
            else:
                self.logger.error('no scheduler configuration file to parse')
                return False
        try:
            conf_opts = self.du.cat(self.hostname, schd_cnfg,
                                    sudo=(not self.has_diag),
                                    level=logging.DEBUG2)['out']
        except:
            self.logger.error('error parsing scheduler configuration')
            return False

        _comment = []
        conf_re = re.compile(
            '[#]?[\s]*(?P<conf_id>[\w]+):[\s]*(?P<conf_val>.*)')
        for line in conf_opts:
            m = conf_re.match(line)
            if m:
                key = m.group('conf_id')
                val = m.group('conf_val')
                # line is a comment, it could be a commented out scheduling
                # option, or the description of an option. It could also be
                # that part of the description is an example setting of the
                # option.
                # We must keep track of commented out options in order to
                # rewrite the configuration in the same order as it was defined
                if line.startswith('#'):
                    if key in self.sched_config_options:
                        _comment += [line]
                        if key in self._sched_config_comments:
                            self._sched_config_comments[key] += _comment
                            _comment = []
                        else:
                            self._sched_config_comments[key] = _comment
                            _comment = []
                        if key not in self._config_order:
                            self._config_order.append(key)
                    else:
                        _comment += [line]
                    continue

                if key not in self._sched_config_comments:
                    self._sched_config_comments[key] = _comment
                else:
                    self._sched_config_comments[key] += _comment
                if key not in self._config_order:
                    self._config_order.append(key)

                _comment = []
                if key in self.sched_config:
                    if isinstance(self.sched_config[key], list):
                        if isinstance(val, list):
                            self.sched_config[key].extend(val)
                        else:
                            self.sched_config[key].append(val)
                    else:
                        if isinstance(val, list):
                            self.sched_config[key] = [self.sched_config[key]]
                            self.sched_config[key].extend(val)
                        else:
                            self.sched_config[key] = [self.sched_config[key],
                                                      val]
                else:
                    self.sched_config[key] = val
            else:
                _comment += [line]
        self._sched_config_comments['PTL_SCHED_CONFIG_TAIL'] = _comment
        return True

    def check_defaults(self, config):
        " Check the values in argument config against default values "

        if len(config.keys()) == 0:
            return
        for k, v in self.sched_dflt_config.items():
            if k in config:
                s1 = v
                s1 = s1.replace(" ", "")
                s1 = s1.replace("\t", "").strip()
                s2 = config[k]
                s2 = s2.replace(" ", "")
                s2 = s2.replace("\t", "").strip()

                if s1 != s2:
                    self.logger.debug(k + ' non-default: ' + v +
                                      ' != ' + config[k])

    def apply_config(self, config=None, validate=True, path=None):
        """
        Apply the configuration specified by config

        config - Configurations to set. Default: self.sched_config

        validate - If True (the default) validate that settings did not yield
        an error. Validation is done by parsing the scheduler log which, in
        some cases may be slow and therefore undesirable.

        path - Optional path to file to which configuration is written. If
        None, the configuration is written to PBS_HOME/sched_priv/sched_config

        Return True on success and False otherwise. Success means that upon
        applying the new configuration the scheduler did not emit an
        "Error reading line" in its log file.
        """

        if config is None:
            config = self.sched_config

        if len(config) == 0:
            return True

        reconfig_time = int(time.time())
        try:
            (fd, fn) = self.du.mkstemp()
            for k in self._config_order:
                if k in config:
                    if k in self._sched_config_comments:
                        os.write(fd, "\n".join(self._sched_config_comments[k]))
                        os.write(fd, "\n")
                    v = config[k]
                    if isinstance(v, list):
                        for val in v:
                            os.write(fd, k + ": " + str(val) + "\n")
                    else:
                        os.write(fd, k + ": " + str(v) + "\n")
                elif k in self._sched_config_comments:
                    os.write(fd, "\n".join(self._sched_config_comments[k]))
                    os.write(fd, "\n")
            for k, v in self.sched_config.items():
                if k not in self._config_order:
                    os.write(fd, k + ": " + str(v).strip() + "\n")

            if 'PTL_SCHED_CONFIG_TAIL' in self._sched_config_comments:
                os.write(fd, "\n".join(
                    self._sched_config_comments['PTL_SCHED_CONFIG_TAIL']))
                os.write(fd, "\n")
            os.close(fd)

            if path is None:
                sp = os.path.join(self.pbs_conf['PBS_HOME'], "sched_priv",
                                  "sched_config")
                if self.du.is_localhost(self.hostname):
                    self.du.run_copy(self.hostname, sp, sp + '.bak', sudo=True)
                else:
                    cmd = ['mv', sp, sp + '.bak']
                    self.du.run_cmd(self.hostname, cmd, sudo=True)
            else:
                sp = path
            self.du.run_copy(self.hostname, fn, sp, mode=0644, sudo=True)
            os.remove(fn)
            self.du.chown(self.hostname, path=sp, uid=0, gid=0, sudo=True)

            self.logger.debug(self.logprefix + "updated configuration")
        except:
            m = self.logprefix + 'error in apply_config '
            self.logger.error(m + str(traceback.print_exc()))
            raise PbsSchedConfigError(rc=1, rv=False, msg=m)

        if validate:
            self.signal('-HUP')

            m = self.log_match("Error reading line", n=10,
                               starttime=reconfig_time)
            if m is None:
                # no match, successful config
                return True
            raise PbsSchedConfigError(rc=1, rv=False, msg=str(m))

        return True

    def set_sched_config(self, confs={}, apply=True, validate=True):
        """
        set a sched_config property

        confs - dictionary of key value sched_config entries

        apply - if True (the default), apply configuration.

        validate - if True (the default), validate the configuration settings.
        """
        self.logger.info(self.logprefix + "config " + str(confs))
        self.sched_config = dict(self.sched_config.items() + confs.items())
        if apply:
            try:
                self.apply_config(validate=validate)
            except PbsSchedConfigError:
                for k in confs:
                    del self.sched_config[k]
                self.apply_config(validate=validate)
        return True

    def add_server_dyn_res(self, custom_resource, script_body=None, file=None,
                           apply=True, validate=True):
        """
        Add a server dynamic resource script or file to the scheduler
        configuration

        custom_resource - The name of the custom resource to define

        script_body - The body of the server dynamic resource

        file - Alternatively to passing the script body, use the file instead

        apply - if True (the default), apply configuration.

        validate - if True (the default), validate the configuration settings.
        """
        if file is not None:
            f = open(file)
            script_body = f.readlines()
            f.close()
        else:
            (fd, file) = self.du.mkstemp(prefix='PtlPbsSchedConfig')
            f = open(file, "w")
            f.write(script_body)
            f.close()
            os.close(fd)

        self.server_dyn_res = file
        self.logger.info(self.logprefix + "adding server dyn res " + file)
        self.logger.info("-" * 30)
        self.logger.info(script_body)
        self.logger.info("-" * 30)

        self.du.chmod(self.hostname, path=file, mode=0755)

        a = {'server_dyn_res': '"' + custom_resource + ' !' + file + '"'}
        self.set_sched_config(a, apply=apply, validate=validate)

    def unset_sched_config(self, name, apply=True):
        """
        Delete a sched_config entry

        name - the entry to delete from sched_config

        apply - if True, apply configuration. Defaults to True
        """
        self.parse_sched_config()
        if name not in self.sched_config:
            return True
        self.logger.info(self.logprefix + "unsetting config " + name)
        del self.sched_config[name]

        if apply:
            return self.apply_config()

    def set_dedicated_time_file(self, file):
        """
        Set the path to a dedicated time
        """
        self.logger.info(self.logprefix + " setting dedicated time file to " +
                         str(file))
        self.dedicated_time_file = file

    def revert_to_defaults(self):
        """
        Revert scheduler configuration to defaults.

        Return True on success, False otherwise
        """
        self.logger.info(self.logprefix + "reverting configuration to defaults")
        self.server.manager(MGR_CMD_LIST, SCHED)
        ignore_attrs = ['id', 'pbs_version', 'sched_host']
        unsetattrs = []
        for k in self.attributes.keys():
            if k not in ignore_attrs:
                unsetattrs.append(k)
        if len(unsetattrs) > 0:
            self.server.manager(MGR_CMD_UNSET, SCHED, unsetattrs)
        self.clear_dedicated_time(hup=False)
        if self.du.cmp(self.hostname, self.dflt_resource_group_file,
                       self.resource_group_file) != 0:
            self.du.run_copy(self.hostname, self.dflt_resource_group_file,
                             self.resource_group_file, mode=0644, sudo=True)
        if self.server_dyn_res is not None:
            self.du.rm(self.hostname, self.server_dyn_res, force=True,
                       sudo=True)
            self.server_dyn_res = None
        rc = self.holidays_revert_to_default()
        if self.du.cmp(self.hostname, self.dflt_sched_config_file,
                       self.sched_config_file) != 0:
            self.du.run_copy(self.hostname, self.dflt_sched_config_file,
                             self.sched_config_file, mode=0644, sudo=True)
        self.signal('-HUP')
        for f in self.deletable_files:
            fn = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv', f)
            if fn is not None:
                self.du.rm(self.hostname, fn, sudo=True)
        self.parse_sched_config()
        self.fairshare_tree = None
        self.resource_group = None
        return self.isUp()

    def save_configuration(self, outfile, mode='a'):
        """
        Save scheduler configuration

        outfile - Path to a file to which configuration is saved

        mode - mode to use to access outfile. Defaults to append, 'a'.

        Return True on success and False otherwise
        """
        conf = {}
        sconf = {MGR_OBJ_SCHED: conf}
        sched_priv = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv')
        sc = os.path.join(sched_priv, 'sched_config')
        self._save_config_file(conf, sc)
        rg = os.path.join(sched_priv, 'resource_group')
        self._save_config_file(conf, rg)
        dt = os.path.join(sched_priv, 'dedicated_time')
        self._save_config_file(conf, dt)
        hd = os.path.join(sched_priv, 'holidays')
        self._save_config_file(conf, hd)

        try:
            f = open(outfile, mode)
            cPickle.dump(sconf, f)
            f.close()
        except:
            self.logger.error('error saving configuration ' + outfile)
            return False

        return True

    def load_configuration(self, infile):
        " load configuration from saved file infile "
        self._load_configuration(infile, MGR_OBJ_SCHED)

    def get_resources(self, exclude=[]):
        """
        returns a list of allocatable resources.

        exclude - if set, excludes the named resources, if they exist, from
        the resulting list
        """
        if 'resources' not in self.sched_config:
            return None
        resources = self.sched_config['resources']
        resources = resources.replace('"', '')
        resources = resources.replace(' ', '')
        res = resources.split(',')
        if len(exclude) > 0:
            for e in exclude:
                if e in res:
                    res.remove(e)
        return res

    def add_resource(self, name, apply=True):
        """
        Add a resource to sched_config.

        name - the resource name to add

        apply - if True, apply configuration. Defaults to True

        Return True on success and False otherwise.

        Return True if the resource is already defined.
        """
        # if the sched_config has not been read in yet, parse it
        if not self.sched_config:
            self.parse_sched_config()

        if 'resources' in self.sched_config:
            resources = self.sched_config['resources']
            resources = resources.replace('"', '')
            splitres = [r.strip() for r in resources.split(",")]
            if name in splitres:
                return True
            resources = '"' + resources + ', ' + name + '"'
        else:
            resources = '"' + name + '"'

        return self.set_sched_config({'resources': resources}, apply=apply)

    def remove_resource(self, name, apply=True):
        """
        Remove a resource to sched_config.

        name - the resource name to add

        apply - if True, apply configuration. Defaults to True

        Return True on success and False otherwise
        """
        # if the sched_config has not been read in yet, parse it
        if not self.sched_config:
            self.parse_sched_config()

        if 'resources' in self.sched_config:
            resources = self.sched_config['resources']
            resources = resources.replace('"', '')
            splitres = [r.strip() for r in resources.split(",")]
            if name not in splitres:
                return True

            newres = []
            for r in splitres:
                if r != name:
                    newres.append(r)

            resources = '"' + ",".join(newres) + '"'
            return self.set_sched_config({'resources': resources}, apply=apply)

    def holidays_revert_to_default(self, level=logging.INFO):
        """
        Revert holidays file to default
        """
        self.logger.log(level, self.logprefix +
                        "reverting holidays file to default")

        rc = None

        # Copy over the holidays file from PBS_EXEC if it exists
        if self.du.cmp(self.hostname, self.dflt_holidays_file,
                       self.holidays_file) != 0:
            ret = self.du.run_copy(self.hostname, self.dflt_holidays_file,
                                   self.holidays_file, mode=0644, sudo=True,
                                   logerr=True)
            rc = ret['rc']
            # Update the internal data structures for the updated file
            self.holidays_parse_file(level=level)
        else:
            rc = 1
        return rc

    def holidays_parse_file(self, path=None, obj=None, level=logging.INFO):
        """
        Parse the existing holidays file
        path - optional path to the holidays file to parse
        obj - optional holidays object to be used instead of internal

        returns the content of holidays file as a list of lines
        """
        self.logger.log(level, self.logprefix + "Parsing holidays file")

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set

        if path is None:
            path = self.holidays_file
        lines = self.du.cat(self.hostname, path, sudo=True)['out']

        content = []    # valid content to return

        self.holidays_delete_entry(
            'a', apply=False, obj=obj, level=logging.DEBUG)

        for line in lines:
            entry = str(line).split()
            if len(entry) == 0:
                continue
            tag = entry[0].lower()
            if tag == "year":   # initialize year
                content.append("\t".join(entry))
                obj.year['valid'] = True
                if len(entry) > 1:
                    obj.year['value'] = entry[1]
            elif tag in days_map.keys():   # initialize a day
                content.append("\t".join(entry))
                day = days_map[tag]
                day['valid'] = True
                days_set.append(day)
                day['position'] = len(days_set) - 1
                if len(entry) > 1:
                    day['p'] = entry[1]
                if len(entry) > 2:
                    day['np'] = entry[2]
            elif tag.isdigit():   # initialize a holiday
                content.append("\t".join(entry))
                obj.holidays.append(tag)
            else:
                pass
        return content

    def holidays_set_day(self, day_id, prime="", nonprime="", apply=True,
                         obj=None, level=logging.INFO):
        """
        Set prime time values for a day

        day_id - the day to be set (string)
        prime - the prime time value
        nonprime - the non-prime time value
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal

        returns the position (0-7) of the set day
        """
        self.logger.log(level, self.logprefix +
                        "setting holidays file entry for %s",
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        day = obj._days_map[str(day_id).lower()]
        days_set = obj.days_set

        if day['valid'] is None:    # Fresh entry
            days_set.append(day)
            day['position'] = len(days_set) - 1
        elif day['valid'] is False:  # Previously invalidated entry
            days_set.insert(day['position'], day)
        else:
            pass

        day['valid'] = True
        day['p'] = str(prime)
        day['np'] = str(nonprime)

        self.logger.debug("holidays_set_day(): changed day struct: " +
                          str(day))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return day['position']

    def holidays_get_day(self, day_id, obj=None, level=logging.INFO):
        """
        Return a copy of info about a day/all set days
        obj - optional holidays object to be used instead of internal

        day_id - either a day's name or "all"
        """
        self.logger.log(level, self.logprefix +
                        "getting holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_set = obj.days_set
        days_map = obj._days_map

        if day_id == "all":
            return days_set[:]
        else:
            return days_map[day_id].copy()

    def holidays_reposition_day(self, day_id, new_pos, apply=True, obj=None,
                                level=logging.INFO):
        """
        Change position of a day (0-7) as it appears in the holidays file

        day_id - name of the day
        new_pos - new position
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal

        returns the new position of the day
        """
        self.logger.log(level, self.logprefix +
                        "repositioning holidays file entry for " +
                        day_id + " to position " + str(new_pos))

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set
        day = days_map[str(day_id).lower()]

        if new_pos == day['position']:
            return

        # We also want to update order of invalid days, so add them to
        # days_set temporarily
        invalid_days = []
        for name in days_map:
            if days_map[name]['valid'] is False:
                invalid_days.append(days_map[name])
        days_set += invalid_days

        # Sort the old list
        days_set.sort(key=itemgetter('position'))

        # Change position of 'day_id'
        day['position'] = new_pos
        days_set.remove(day)
        days_set.insert(new_pos, day)

        # Update the 'position' field
        for i in range(0, len(days_set)):
            days_set[i]['position'] = i

        # Remove invalid days from days_set
        len_days_set = len(days_set)
        days_set = [days_set[i] for i in range(0, len_days_set)
                    if days_set[i] not in invalid_days]

        self.logger.debug("holidays_reposition_day(): List of days after " +
                          " re-positioning " + str(day_id) + " is:\n" +
                          str(days_set))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return new_pos

    def holidays_unset_day(self, day_id, apply=True, obj=None,
                           level=logging.INFO):
        """
        Unset prime time values for a day
        Note: we do not unset the 'valid' field here so the entry
        will still be displayed but without any values

        day_id - day to unset (string)
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "unsetting holidays file entry for " + day_id)

        if obj is None:
            obj = self.holidays_obj

        day = obj._days_map[str(day_id).lower()]
        day['p'] = ""
        day['np'] = ""

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_invalidate_day(self, day_id, apply=True, obj=None,
                                level=logging.INFO):
        """
        Remove a day's entry from the holidays file

        day_id - the day to remove (string)
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "invalidating holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set

        day = days_map[str(day_id).lower()]
        day['valid'] = False
        days_set.remove(day)

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_validate_day(self, day_id, apply=True, obj=None,
                              level=logging.INFO):
        """
        Make valid a previously set day's entry
        Note: The day will retain its previous position in the file

        day_id - the day to validate (string)
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "validating holidays file entry for " +
                        day_id)

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set

        day = days_map[str(day_id).lower()]
        if day in days_set:  # do not insert a pre-existing day
            self.logger.debug("holidays_validate_day(): " +
                              day_id + " is already valid!")
            return

        day['valid'] = True
        days_set.insert(day['position'], day)

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_delete_entry(self, entry_type, idx=None, apply=True,
                              obj=None, level=logging.INFO):
        """
        Delete one/all entries from holidays file
        Note: The day cannot be validated and will lose it's position in the
        file

        entry_type - 'y':year, 'd':day, 'h':holiday or 'a': all
        idx - either a day of week (monday, tuesday etc.)
        or Julian date  of a holiday

        apply - to reflect the changes to file

        obj - optional holidays object to be used instead of internal

        returns False if entry_type is invalid, otherwise True
        """
        self.logger.log(level, self.logprefix +
                        "Deleting entries from holidays file")

        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        days_set = obj.days_set
        holiday_list = obj.holidays
        year = obj.year

        if entry_type not in ['a', 'y', 'd', 'h']:
            return False

        if entry_type == 'y' or entry_type == 'a':
            self.logger.debug(self.logprefix +
                              "deleting year entry from holidays file")
            # Delete year entry
            year['value'] = None
            year['valid'] = False

        if entry_type == 'd' or entry_type == 'a':
            # Delete one/all day entries
            num_days_to_delete = 1
            if entry_type == 'a':
                self.logger.debug(self.logprefix +
                                  "deleting all days from holidays file")
                num_days_to_delete = len(days_set)
            for i in range(0, num_days_to_delete):
                if (entry_type == 'd'):
                    self.logger.debug(self.logprefix +
                                      "deleting " + str(idx) +
                                      " entry from holidays file")
                    day = days_map[str(idx).lower()]
                else:
                    day = days_set[0]

                day['p'] = None
                day['np'] = None
                day['valid'] = None
                day['position'] = None
                days_set.remove(day)
                if entry_type == 'd':
                    # Correct 'position' field of every day
                    for i in range(0, len(days_set)):
                        days_set[i]['position'] = i

        if entry_type == 'h' or entry_type == 'a':
            # Delete one/all calendar holiday entries
            if entry_type == 'a':
                self.logger.debug(self.logprefix +
                                  "deleting all holidays from holidays file")
                del holiday_list[:]
            else:
                self.logger.debug(self.logprefix +
                                  "deleting holiday on " + str(idx) +
                                  " from holidays file")
                holiday_list.remove(str(idx))

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

        return True

    def holidays_set_year(self, new_year="", apply=True, obj=None,
                          level=logging.INFO):
        """
        Set the year value

        newyear -  year value to set
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "setting holidays file year entry to " +
                        str(new_year))
        if obj is None:
            obj = self.holidays_obj

        year = obj.year

        year['value'] = str(new_year)
        year['valid'] = True

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_unset_year(self, apply=True, obj=None, level=logging.INFO):
        """
        Unset the year value

        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "unsetting holidays file year entry")
        if obj is None:
            obj = self.holidays_obj

        obj.year['value'] = ""

        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_get_year(self, obj=None, level=logging.INFO):
        """
        Return the year entry of holidays file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "getting holidays file year entry")
        if obj is None:
            obj = self.holidays_obj

        year = obj.year
        return year.copy()

    def holidays_add_holiday(self, date=None, apply=True, obj=None,
                             level=logging.INFO):
        """
        Add a calendar holiday to the holidays file

        date - Date value for the holiday
        apply - to reflect the changes to file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "adding holiday " + str(date) +
                        " to holidays file")
        if obj is None:
            obj = self.holidays_obj

        holiday_list = obj.holidays

        if date is not None:
            holiday_list.append(str(date))
        else:
            pass
        self.logger.debug("holidays list after adding one: " +
                          str(holiday_list))
        if apply:
            self.holidays_write_file(obj=obj, level=logging.DEBUG)

    def holidays_get_holidays(self, obj=None, level=logging.INFO):
        """
        Return the list of holidays in holidays file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "retrieving list of holidays")

        if obj is None:
            obj = self.holidays_obj

        holiday_list = obj.holidays
        return holiday_list[:]

    def _holidays_process_content(self, content, obj=None):
        """
        Process a user provided list of holidays file content
        obj - optional holidays object to be used instead of internal
        """
        self.logger.debug("_holidays_process_content(): " +
                          "Processing user provided holidays content:\n" +
                          str(content))
        if obj is None:
            obj = self.holidays_obj

        days_map = obj._days_map
        year = obj.year
        holiday_list = obj.holidays
        days_set = obj.days_set

        self.holidays_delete_entry(
            'a', apply=False, obj=obj, level=logging.DEBUG)

        if content is None:
            self.logger.debug("Holidays file was wiped out")
            return

        for line in content:
            entry = line.split()
            if len(entry) == 0:
                continue
            tag = entry[0].lower()
            if tag == "year":   # initialize self.year
                year['valid'] = True
                if len(entry) > 1:
                    year['value'] = entry[1]
            elif tag in days_map.keys():   # initialize self.<day>
                day = days_map[tag]
                day['valid'] = True
                days_set.append(day)
                day['position'] = len(days_set) - 1
                if len(entry) > 1:
                    day['p'] = entry[1]
                if len(entry) > 2:
                    day['np'] = entry[2]
            elif tag.isdigit():   # initialize self.holiday
                holiday_list.append(tag)
            else:
                pass

    def holidays_write_file(self, content=None, out_path=None,
                            hup=True, obj=None, level=logging.INFO):
        """
        Write to the holidays file with content given/generated

        hup - SIGHUP the scheduler after writing the holidays file
        obj - optional holidays object to be used instead of internal
        """
        self.logger.log(level, self.logprefix +
                        "Writing to the holidays file")

        if obj is None:
            obj = self.holidays_obj

        if out_path is None:
            out_path = self.holidays_file

        if content is not None:
            self._holidays_process_content(content, obj)
        else:
            content = str(obj)

        self.logger.debug("content being written:\n" + str(content))

        (fd, fn) = self.du.mkstemp(self.hostname, body=content)
        ret = self.du.run_copy(self.hostname, fn, out_path, mode=0644,
                               sudo=True)
        self.du.rm(self.hostname, fn)
        self.du.chown(self.hostname, out_path, uid=0, gid=0,
                      sudo=True)

        if ret['rc'] != 0:
            raise PbsSchedConfigError(rc=ret['rc'], rv=ret['out'],
                                      msg=('error applying holidays file' +
                                           ret['err']))
        if hup:
            rv = self.signal('-HUP')
            if not rv:
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg='error applying holidays file')
        self.du.chown(self.hostname, path=out_path, uid=0,
                      gid=0, sudo=True)

        return True

    def parse_dedicated_time(self, file=None):
        """
        Parse the dedicated_time file and populate dedicated times as both
        a string dedicated_time array of dictionaries defined as
        [{'from': datetime, 'to': datetime}, ...] as well as a
        dedicated_time_as_str array with a string representation of each entry

        file - optional file to parse. Defaults to the one under
        PBS_HOME/sched_priv

        Returns the dedicated_time list of dictionaries or None on error.

        Return an empty array if dedicated time file is empty.
        """
        self.dedicated_time_as_str = []
        self.dedicated_time = []

        if file:
            dt_file = file
        elif self.dedicated_time_file:
            dt_file = self.dedicated_time_file
        else:
            dt_file = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv',
                                   'dedicated_time')
        try:
            lines = self.du.cat(self.hostname, dt_file, sudo=True)['out']
            if lines is None:
                return []

            for line in lines:
                if not line.startswith('#') and len(line) > 0:
                    self.dedicated_time_as_str.append(line)
                    (dtime_from, dtime_to) = self.utils.convert_dedtime(line)
                    self.dedicated_time.append({'from': dtime_from,
                                                'to': dtime_to})
        except:
            self.logger.error('error in parse_dedicated_time')
            return None

        return self.dedicated_time

    def clear_dedicated_time(self, hup=True):
        " Clear the dedicated time file "
        self.parse_dedicated_time()
        if ((len(self.dedicated_time) == 0) and
                (len(self.dedicated_time_as_str) == 0)):
            return True
        if self.dedicated_time:
            for d in self.dedicated_time:
                del d
        if self.dedicated_time_as_str:
            for d in self.dedicated_time_as_str:
                del d
        self.dedicated_time = []
        self.dedicated_time_as_str = []
        dt = "# FORMAT: MM/DD/YYYY HH:MM MM/DD/YYYY HH:MM"
        return self.add_dedicated_time(dt, hup=hup)

    def add_dedicated_time(self, as_str=None, start=None, end=None, hup=True):
        """
        Append a dedicated time entry. The function can be called in one of two
        ways, either by passing in start and end as time values, or by passing
        as_str, a string that gets appended to the dedicated time entries and
        formatted as follows, note that no check on validity of the format will
        be made the function uses strftime to parse the datetime and will fail
        if the strftime can not convert the string.
        MM/DD/YYYY HH:MM MM/DD/YYYY HH:MM

        Returns True on success and False otherwise
        """
        if self.dedicated_time is None:
            self.parse_dedicated_time()

        if start is not None and end is not None:
            dtime_from = time.strftime("%m/%d/%Y %H:%M", time.localtime(start))
            dtime_to = time.strftime("%m/%d/%Y %H:%M", time.localtime(end))
            dedtime = dtime_from + " " + dtime_to
        elif as_str is not None:
            (dtime_from, dtime_to) = self.utils.convert_dedtime(as_str)
            dedtime = as_str
        else:
            self.logger.warning("no dedicated from/to specified")
            return True

        for d in self.dedicated_time_as_str:
            if dedtime == d:
                if dtime_from is None or dtime_to is None:
                    self.logger.info(self.logprefix +
                                     "dedicated time already defined")
                else:
                    self.logger.info(self.logprefix +
                                     "dedicated time from " + dtime_from +
                                     " to " + dtime_to + " already defined")
                return True

        if dtime_from is not None and dtime_to is not None:
            self.logger.info(self.logprefix +
                             "adding dedicated time " + dedtime)

        self.dedicated_time_as_str.append(dedtime)
        if dtime_from is not None and dtime_to is not None:
            self.dedicated_time.append({'from': dtime_from, 'to': dtime_to})
        try:
            (fd, fn) = self.du.mkstemp()
            for l in self.dedicated_time_as_str:
                os.write(fd, l + '\n')
            os.close(fd)
            ddfile = os.path.join(self.pbs_conf['PBS_HOME'], 'sched_priv',
                                  'dedicated_time')
            self.du.run_copy(self.hostname, fn, ddfile, mode=0644, uid=0,
                             gid=0, sudo=True)
            os.remove(fn)
        except:
            raise PbsSchedConfigError(rc=1, rv=False,
                                      msg='error adding dedicated time')

        if hup:
            ret = self.signal('-HUP')
            if ret['rc'] != 0:
                raise PbsSchedConfigError(rc=1, rv=False,
                                          msg='error adding dedicated time')

        return True

    def terminate(self):
        self.signal('-KILL')

    def valgrind(self):
        " run scheduler instance through valgrind "
        if self.isUp():
            self.terminate()

        rv = CliUtils().check_bin('valgrind')
        if not rv:
            self.logger.error(self.logprefix + 'valgrind not available')
            return None

        cmd = ['valgrind']

        cmd += ["--log-file=" + os.path.join(tempfile.gettempdir(),
                                             'schd.vlgrd')]
        cmd += [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbs_sched')]

        return self.du.run_cmd(self.hostname, cmd, sudo=True)

    def alloc_to_execvnode(self, chunks):
        " convert a resource allocation to an execvnode string representation "
        execvnode = []
        for chunk in chunks:
            execvnode += ["(" + chunk.vnode]
            for res, val in chunk.resources.items():
                execvnode += [":" + str(res) + "=" + str(val)]
            for vchk in chunk.vchunk:
                execvnode += ["+" + vchk.vnode]
                for res, val in vchk.resources():
                    execvnode += [":" + str(res) + "=" + str(val)]
            execvnode += [")+"]

        if len(execvnode) != 0:
            ev = execvnode[len(execvnode) - 1]
            ev = ev[:-1]
            execvnode[len(execvnode) - 1] = ev

        return "".join(execvnode)

    def cycles(self, start=None, end=None, firstN=None, lastN=None):
        """
        Analyze scheduler log and return cycle information

        start - Optional setting of the start time to consider

        end - Optional setting of the end time to consider

        firstN - Optional setting to consider the given first N cycles

        lastN - Optional setting to consider only the given last N cycles
        """
        try:
            from ptl.utils.pbs_logutils import PBSSchedulerLog
        except:
            self.logger.error('error loading ptl.utils.pbs_logutils')
            return None

        sl = PBSSchedulerLog()
        sl.analyze(self.logfile, start, end, self.hostname)
        cycles = sl.cycles
        if not cycles or cycles is None:
            return []

        if lastN is not None:
            return cycles[-lastN:]
        elif firstN is not None:
            return cycles[:firstN]

        return cycles

    def query_fairshare(self, name=None, id=None):
        """
        Parse fairshare data using pbsfs and populates fairshare_tree.
        If name or id are specified, return the data associated to that id.
        Otherwise return the entire fairshare tree
        """
        if self.has_diag:
            return None

        tree = FairshareTree()
        cmd = [os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')]
        ret = self.du.run_cmd(self.hostname, cmd, sudo=True, logerr=False)
        if ret['rc'] != 0:
            raise PbsFairshareError(rc=ret['rc'], rv=None,
                                    msg=str(ret['err']))
        pbsfs = ret['out']
        for p in pbsfs:
            m = self.fs_tag.match(p)
            if m:
                usage = int(m.group('Usage'))
                perc = float(m.group('Perc'))
                nm = m.group('name')
                cgrp = int(m.group('cgrp'))
                pid = int(m.group('Grp'))
                nd = tree.get_node(id=pid)
                if nd:
                    pname = nd.parent_name
                else:
                    pname = None
                # if an entity has a negative cgroup it should belong
                # to the unknown resource, we work around the fact that
                # PBS Pro (up to 13.0) sets this cgroup id to -1 by
                # reassigning it to 0
                # TODO: cleanup once PBS code is updated
                if cgrp < 0:
                    cgrp = 0
                node = FairshareNode(name=nm,
                                     id=cgrp,
                                     parent_id=pid,
                                     parent_name=pname,
                                     nshares=int(m.group('Shares')),
                                     usage=usage,
                                     perc={'TREEROOT': perc})
                if perc:
                    node.prio['TREEROOT'] = float(usage) / perc
                if nm == name or id == cgrp:
                    return node

                tree.add_node(node, apply=False)
        # now that all nodes are known, update parent and child
        # relationship of the tree
        tree.update()

        for node in tree.nodes.values():
            pnode = node._parent
            while pnode is not None and pnode.id != 0:
                if pnode.perc['TREEROOT']:
                    node.perc[pnode.name] = \
                        (node.perc['TREEROOT'] * 100 / pnode.perc[
                         'TREEROOT'])
                if pnode.name in node.perc and node.perc[pnode.name]:
                    node.prio[pnode.name] = (
                        node.usage / node.perc[pnode.name])
                pnode = pnode._parent

        if name:
            n = tree.get_node(name)
            if n is None:
                raise PbsFairshareError(rc=1, rv=None,
                                        msg='Unknown entity ' + name)
            return n
        if id:
            n = tree.get_node(id=id)
            raise PbsFairshareError(rc=1, rv=None,
                                    msg='Unknown entity ' + str(id))
            return n
        return tree

    def set_fairshare_usage(self, name=None, usage=None):
        """
        Set the fairshare usage associated to a given entity.

        name - The entity to set the fairshare usage of

        usage - The usage value to set
        """
        if self.has_diag:
            return True

        if name is None:
            self.logger.error(self.logprefix + ' an entity name required')
            return False

        if usage is None:
            self.logger.error(self.logprefix + ' a usage is required')
            return False

        self.stop()
        pbsfs = os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')
        cmd = [pbsfs, '-s', name, str(usage)]
        ret = self.du.run_cmd(self.hostname, cmd, sudo=True)
        self.start()
        if ret['rc'] == 0:
            return True
        return False

    def decay_fairshare_tree(self):
        """
        Decay the fairshare tree through pbsfs
        """
        if self.has_diag:
            return True

        self.stop()
        pbsfs = os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')
        cmd = [pbsfs, '-d']
        ret = self.du.run_cmd(self.hostname, cmd, sudo=True)
        self.start()
        if ret['rc'] == 0:
            return True
        return False

    def cmp_fairshare_entities(self, name1=None, name2=None):
        """
        Compare two fairshare entities. Wrapper of pbsfs -c e1 e2

        name1 - name of first entity to compare

        name2 - name of second entity to compare

        Returns the name of the entity of higher priority or None on error
        """
        if self.has_diag:
            return None

        if name1 is None or name2 is None:
            self.logger.erro(self.logprefix + 'two fairshare entity names ' +
                             'required')
            return None

        pbsfs = os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbsfs')
        cmd = [pbsfs, '-c', name1, name2]
        ret = self.du.run_cmd(self.hostname, cmd, sudo=True)
        if ret['rc'] == 0:
            return ret['out'][0]
        return None

    def parse_resource_group(self, hostname=None, resource_group=None):
        """
        Parse the Scheduler's resource_group file

        hostname - The name of the host from which to parse resource_group

        resource_group - The path to a resource_group file

        Return a fairshare tree
        """

        if hostname is None:
            hostname = self.hostname
        if resource_group is None:
            resource_group = self.resource_group_file

        # if has_diag is True acces to sched_priv may not require su privilege
        ret = self.du.cat(hostname, resource_group, sudo=(not self.has_diag))
        if ret['rc'] != 0:
            self.logger.error(hostname + ' error reading ' + resource_group)
        tree = FairshareTree(hostname, resource_group)
        root = FairshareNode('root', -1, parent_id=0, nshares=100)
        tree.add_node(root, apply=False)
        lines = ret['out']
        for line in lines:
            line = line.strip()
            if not line.startswith("#") and len(line) > 0:
                # could have 5th column but we only need the first 4
                (name, id, parent, nshares) = line.split()[:4]
                node = FairshareNode(name, id, parent_name=parent,
                                     nshares=nshares)
                tree.add_node(node, apply=False)
        tree.update()
        return tree

    def add_to_resource_group(self, name, id, parent, nshares):
        """
        Add an entry to the resource group file

        name - The name of the entity to add

        id - The numeric identifier of the entity to add

        parent - The name of the parent group

        nshares - The number of shares associated to the entity
        """
        if self.resource_group is None:
            self.resource_group = self.parse_resource_group(
                self.hostname, self.resource_group_file)
        if not self.resource_group:
            self.resource_group = FairshareTree(
                self.hostname, self.resource_group_file)
        return self.resource_group.create_node(name, id, parent_name=parent,
                                               nshares=nshares)

    def job_formula(self, jobid=None, starttime=None, max_attempts=5):
        """
        Extract formula value out of scheduler log

        jobid - Optional, the job identifier for which to get the formula.

        starttime - The time at which to start parsing the scheduler log

        max_attempts - The number of attempts to search for formula in the logs

        If jobid is specified, return the formula value associated to that job
        if no jobid is specified, returns a dictionary mapping job ids to
        formula
        """
        if jobid is None:
            jobid = "(?P<jobid>.*)"
            _alljobs = True
        else:
            if isinstance(jobid, int):
                jobid = str(jobid)
            _alljobs = False

        formula_pat = (".*Job;" + jobid +
                       ".*;Formula Evaluation = (?P<fval>.*)")

        rv = self.log_match(formula_pat, regexp=True, starttime=starttime,
                            n='ALL', allmatch=True, max_attempts=5)
        ret = {}
        if rv:
            for _, l in rv:
                m = re.match(formula_pat, l)
                if m:
                    if _alljobs:
                        jobid = m.group('jobid')
                    ret[jobid] = float(m.group('fval').strip())

        if not _alljobs:
            if jobid in ret:
                return ret[jobid]
            else:
                return
        return ret


class FairshareTree(object):

    """
    Object representation of the Scheduler's resource_group file and pbsfs data
    """
    du = DshUtils()

    def __init__(self, hostname=None, resource_group=None):
        self.logger = logging.getLogger(__name__)
        self.hostname = hostname
        self.resource_group = resource_group
        self.nodes = {}
        self.root = None
        self._next_id = -1

    def update_resource_group(self):
        if self.resource_group:
            (fd, fn) = self.du.mkstemp()
            os.write(fd, self.__str__())
            os.close(fd)
            ret = self.du.run_copy(self.hostname, fn, self.resource_group,
                                   mode=0644, sudo=True)
            self.du.chown(self.hostname, self.resource_group, uid=0,
                          gid=0, sudo=True)

            os.remove(fn)

            if ret['rc'] != 0:
                raise PbsFairshareError(rc=1, rv=False,
                                        msg='error updating resource group')
        return True

    def update(self):
        for node in self.nodes.values():
            if node._parent is None:
                pnode = self.get_node(id=node.parent_id)
                if pnode:
                    node._parent = pnode
                    if node not in pnode._child:
                        pnode._child.append(node)

    def _add_node(self, node):
        if node.name == 'TREEROOT' or node.name == 'root':
            self.root = node
        self.nodes[node.name] = node
        if node.parent_name in self.nodes:
            self.nodes[node.parent_name]._child.append(node)
            node._parent = self.nodes[node.parent_name]

    def add_node(self, node, apply=True):
        " add node to the fairshare tree "
        self._add_node(node)
        if apply:
            return self.update_resource_group()
        return True

    def create_node(self, name, id, parent_name, nshares):
        """
        Add an entry to the resource_group file

        name - The name of the entity to add

        id - The uniqe numeric identifier of the entity

        parent - The name of the parent/group of the entity

        nshares - The number of shares assigned to this entity

        Return True on success, False otherwise
        """
        if name in self.nodes:
            self.logger.warning('fairshare: node ' + name + ' already defined')
            return True
        self.logger.info('creating tree node: ' + name)

        node = FairshareNode(name, id, parent_name=parent_name,
                             nshares=nshares)
        self._add_node(node)
        return self.update_resource_group()

    def get_node(self, name=None, id=None):
        """
        Return a node of the fairshare tree identified by either name or id.

        name - The name of the entity to query

        id - The id of the entity to query

        The name takes precedence over the id.

        Returns the fairshare information of the entity when found, if not,
        returns None
        """
        for node in self.nodes.values():
            if name is not None and node.name == name:
                return node
            if id is not None and node.id == id:
                return node
        return None

    def __batch_status__(self):
        """
        Convert fairshare tree object to a batch status format
        """
        dat = []
        for node in self.nodes.values():
            if node.name == 'root':
                continue
            einfo = {}
            einfo['cgroup'] = node.id
            einfo['id'] = node.name
            einfo['group'] = node.parent_id
            einfo['nshares'] = node.nshares
            if len(node.prio) > 0:
                p = []
                for k, v in node.prio.items():
                    p += ["%s:%d" % (k, int(v))]
                einfo['penalty'] = ", ".join(p)
            einfo['usage'] = node.usage
            if node.perc:
                p = []
                for k, v in node.perc.items():
                    p += ["%s:%.3f" % (k, float(v))]
                    einfo['shares_perc'] = ", ".join(p)
            ppnode = self.get_node(id=node.parent_id)
            if ppnode:
                ppname = ppnode.name
                ppid = ppnode.id
            else:
                ppnode = self.get_node(name=node.parent_name)
                if ppnode:
                    ppname = ppnode.name
                    ppid = ppnode.id
                else:
                    ppname = ''
                    ppid = None
            einfo['parent'] = "%s (%s) " % (str(ppid), ppname)
            dat.append(einfo)
        return dat

    def get_next_id(self):
        self._next_id -= 1
        return self._next_id

    def __repr__(self):
        return self.__str__()

    def _dfs(self, node, dat):
        if node.name != 'root':
            s = []
            if node.name is not None:
                s += [node.name]
            if node.id is not None:
                s += [str(node.id)]
            if node.parent_name is not None:
                s += [node.parent_name]
            if node.nshares is not None:
                s += [str(node.nshares)]
            if node.usage is not None:
                s += [str(node.usage)]
            dat.append("\t".join(s))
        for n in node._child:
            self._dfs(n, dat)

    def __str__(self):
        dat = []
        if self.root:
            self._dfs(self.root, dat)
        if len(dat) > 0:
            dat += ['\n']
        return "\n".join(dat)


class FairshareNode(object):

    """
    Object representation of the fairshare data as queryable through the
    command pbsfs.
    """

    def __init__(self, name=None, id=None, parent_name=None, parent_id=None,
                 nshares=None, usage='unknown', perc=None):
        self.name = name
        self.id = id
        self.parent_name = parent_name
        self.parent_id = parent_id
        self.nshares = nshares
        self.usage = usage
        self.perc = perc
        self.prio = {}
        self._parent = None
        self._child = []

    def __str__(self):
        ret = []
        if self.name is not None:
            ret.append(self.name)
        if self.id is not None:
            ret.append(str(self.id))
        if self.parent_name is not None:
            ret.append(str(self.parent_name))
        if self.nshares is not None:
            ret.append(str(self.nshares))
        if self.usage is not None:
            ret.append(str(self.usage))
        if self.perc is not None:
            ret.append(str(self.perc))
        return "\t".join(ret)


class MoM(PBSService):

    """
    Container for MoM properties.
    Provides various MoM operations, such as creation, insertion, deletion of
    vnodes.

    """
    dflt_attributes = {}
    conf_to_cmd_map = {'PBS_MOM_SERVICE_PORT': '-M',
                       'PBS_MANAGER_SERVICE_PORT': '-R',
                       'PBS_HOME': '-d'}

    def __init__(self, name=None, attrs={}, pbsconf_file=None, diagmap={},
                 diag=None, server=None, db_access=None):
        """
        name - The hostname of the mom. Defaults to current hostname.

        attrs - Dictionary of attributes to set, these will override defaults.

        pbsconf_file - path to config file to parse for PBS_HOME, PBS_EXEC, etc

        diagmap - A dictionary of PBS objects (node,server,etc) to mapped files
        from PBS diag directory

        diag - path to PBS diag directory (This will overrides diagmap)

        server - A PBS server instance to which this mom is associated

        db_acccess- set to either file containing credentials to DB access or
        dictionary containing {'dbname':...,'user':...,'port':...}
        """

        self.logger = logging.getLogger(__name__)

        if server is not None:
            self.server = server
            if diag is None and self.server.diag is not None:
                diag = self.server.diag
            if ((len(diagmap) == 0) and (len(self.server.diagmap) != 0)):
                diagmap = self.server.diagmap
        else:
            self.server = Server(name, pbsconf_file=pbsconf_file,
                                 db_access=db_access, diag=diag,
                                 diagmap=diagmap)

        PBSService.__init__(self, name, attrs, self.dflt_attributes,
                            pbsconf_file, diag=diag, diagmap=diagmap)
        _m = ['mom ', self.shortname]
        if pbsconf_file is not None:
            _m += ['@', pbsconf_file]
        _m += [': ']
        self.logprefix = "".join(_m)

        self.configd = os.path.join(self.pbs_conf['PBS_HOME'], 'mom_priv',
                                    'config.d')
        self.config = {}
        self.dflt_config = {'$clienthost': self.hostname}
        self.version = None

    def isUp(self):
        return super(MoM, self)._isUp(self)

    def signal(self, sig):
        self.logger.info(self.logprefix + 'sent signal ' + sig)
        return super(MoM, self)._signal(sig, inst=self)

    def get_pid(self):
        return super(MoM, self)._get_pid(inst=self)

    def all_instance_pids(self):
        return super(MoM, self)._all_instance_pids(inst=self)

    def start(self, args=None, launcher=None):
        return super(MoM, self)._start(inst=self, args=args,
                                       cmd_map=self.conf_to_cmd_map,
                                       launcher=launcher)

    def stop(self, sig='-TERM'):
        self.logger.info(self.logprefix + 'stopping MoM on host ' +
                         self.hostname)
        rv = super(MoM, self)._stop(sig, inst=self)
        return rv

    def restart(self):
        if self.stop():
            return self.start()
        return False

    def log_match(self, msg=None, id=None, n=50, tail=True, allmatch=False,
                  regexp=False, day=None, max_attempts=1, interval=1,
                  starttime=None, endtime=None):
        return self._log_match(self, msg, id, n, tail, allmatch, regexp, day,
                               max_attempts, interval, starttime, endtime)

    def pbs_version(self):
        if self.version:
            return self.version

        exe = os.path.join(self.pbs_conf['PBS_EXEC'], 'sbin', 'pbs_mom')
        version = self.du.run_cmd(self.hostname,
                                  [exe, '--version'], sudo=True)['out']
        if version:
            self.logger.debug(version)
            # in some cases pbs_mom --version may return multiple lines, we
            # only care about the one that carries pbs_version information
            for ver in version:
                if 'pbs_version' in ver:
                    version = ver.split('=')[1].strip()
                    break
        else:
            version = self.log_match('pbs_version', tail=False)
            if version:
                version = version[1].strip().split('=')[1].strip()
            else:
                version = "unknown"

        self.version = LooseVersion(version)

        return self.version

    def revert_to_defaults(self, delvnodedefs=True):
        """
        1. Revert MoM configuration to defaults.

        2. Remove epilogue and prologue

        3. Delete all vnode definitions
        HUP MoM

        delvnodedefs - if True (the default) delete all vnode definitions and
        restart the MoM

        Return True on success and False otherwise
        """
        self.logger.info(self.logprefix + 'reverting configuration to defaults')
        restart = False
        if not self.has_diag:
            self.delete_pelog()
            if delvnodedefs and self.has_vnode_defs():
                restart = True
                self.delete_vnode_defs()
                rah = ATTR_rescavail + '.host'
                rav = ATTR_rescavail + '.vnode'
                a = {rah: self.hostname, rav: None}
                try:
                    _vs = self.server.status(VNODE, a, id=self.hostname)
                except:
                    _vs = self.server.status(VNODE, a, id=self.shortname)
                vs = []
                for v in _vs:
                    if v[rav].split('.')[0] != v[rah].split('.')[0]:
                        vs.append(v['id'])
                if len(vs) > 0:
                    self.server.manager(MGR_CMD_DELETE, VNODE, id=vs,
                                        expect=True)
            if cmp(self.config, self.dflt_config) != 0:
                self.apply_config(self.dflt_config, hup=False, restart=False)
            if restart:
                self.restart()
            else:
                self.signal('-HUP')
            return self.isUp()
        return True

    def save_configuration(self, outfile, mode='a'):
        """
        Save a MoM mom_priv/config

        outfile - the output file to which onfiguration is saved

        mode - the mode in which to open outfile to save configuration. The

        first object being saved should open this file with 'w' and subsequent
        calls from other objects should save with mode 'a' or 'a+'. Defaults
        to a+

        Returns True on success, False on error
        """
        conf = {}
        mconf = {MGR_OBJ_NODE: conf}
        mpriv = os.path.join(self.pbs_conf['PBS_HOME'], 'mom_priv')
        cf = os.path.join(mpriv, 'config')
        self._save_config_file(conf, cf)

        if os.path.isdir(os.path.join(mpriv, 'config.d')):
            for f in os.listdir(os.path.join(mpriv, 'config.d')):
                self._save_config_file(conf,
                                       os.path.join(mpriv, 'config.d', f))
        try:
            f = open(outfile, mode)
            cPickle.dump(mconf, f)
            f.close()
        except:
            self.logger.error('error saving configuration to ' + outfile)
            return False

        return True

    def load_configuration(self, infile):
        " load configuration from saved file infile "
        self._load_configuration(infile, MGR_OBJ_NODE)

    def is_cpuset_mom(self):
        e = self.pbs_conf['PBS_EXEC']
        sbin = os.path.join(e, 'sbin')
        m1 = os.path.join(sbin, 'pbs_mom')
        m2 = os.path.join(sbin, 'pbs_mom.cpuset')
        ret = self.du.cmp(self.hostname, m1, m2, sudo=True, logerr=False)
        if ret == 0:
            return True
        return False

    def switch_to_standard_mom(self):
        if not self.is_cpuset_mom():
            return False

        rv = self.stop()
        if not rv:
            return False
        e = self.pbs_conf['PBS_EXEC']
        sbin = os.path.join(e, 'sbin')
        m1 = os.path.join(sbin, 'pbs_mom')
        m2 = os.path.join(sbin, 'pbs_mom.standard')
        ret = self.du.run_cmd(self.hostname, cmd=['cp', m2, m1], sudo=True)
        if ret['rc'] == 0:
            return True

    def create_vnode_def(self, name, attrs={}, numnodes=1, sharednode=True,
                         pre='[', post=']', usenatvnode=False, attrfunc=None,
                         vnodes_per_host=1):
        """
        Create a vnode definition string representation

        name - The prefix for name of vnode to create,
               name of vnode will be prefix + pre + <num> + post

        attrs - Dictionary of attributes to set on each vnode

        numnodes - The number of vnodes to create

        sharednode - If true vnodes are shared on a host

        pre - The symbol preceding the numeric value of that vnode.

        post - The symbol following the numeric value of that vnode.

        usenatvnode - use the natural vnode as the first vnode to allocate
        this only makes sense starting with PBS 11.3 when natural vnodes are
        reported as a allocatable

        attrfunc - function to customize the attributes, signature is
        (name, numnodes, curnodenum, attrs), must return a dict
        that contains new or modified attrs that will be added to
        the vnode def. The function is called once per vnode being
        created, it does not modify attrs itself across calls.

        vnodes_per_host - number of vnodes per host

        Returns a string representation of the vnode definition file
        """
        sethost = False

        attribs = attrs.copy()
        if not sharednode and 'resources_available.host' not in attrs:
            sethost = True

        if attrfunc is None:
            customattrs = attribs

        vdef = ["$configversion 2"]

        # altering the natural vnode information
        if numnodes == 0:
            for k, v in attribs.items():
                vdef += [name + ": " + str(k) + "=" + str(v)]
        else:
            if usenatvnode:
                if attrfunc:
                    customattrs = attrfunc(name, numnodes, "", attribs)
                for k, v in customattrs.items():
                    vdef += [self.shortname + ": " + str(k) + "=" + str(v)]
                # account for the use of the natural vnode
                numnodes -= 1
            else:
                # ensure that natural vnode is not allocatable by the scheduler
                vdef += [self.shortname + ": resources_available.ncpus=0"]
                vdef += [self.shortname + ": resources_available.mem=0"]

        for n in xrange(numnodes):
            vnid = name + pre + str(n) + post
            if sethost:
                if vnodes_per_host > 1:
                    if n % vnodes_per_host == 0:
                        _nid = vnid
                    else:
                        _nid = name + pre + str(n - n % vnodes_per_host) + post
                    attribs['resources_available.host'] = _nid
                else:
                    attribs['resources_available.host'] = vnid

            if attrfunc:
                customattrs = attrfunc(vnid, numnodes, n, attribs)
            for k, v in customattrs.items():
                vdef += [vnid + ": " + str(k) + "=" + str(v)]

        if numnodes == 0:
            nn = 1
        else:
            nn = numnodes
        if numnodes > 1:
            vnn_msg = ' vnodes '
        else:
            vnn_msg = ' vnode '

        self.logger.info(self.logprefix + 'created ' + str(nn) +
                         vnn_msg + name + ' with attr ' +
                         str(attribs) + ' on host ' + self.hostname)
        vdef += ["\n"]
        del attribs
        return "\n".join(vdef)

    def parse_config(self):
        """
        Parse mom config file into a dictionary of configuration options.

        Return a dictionary of configuration options on success, and None
        otherwise
        """
        try:
            mconf = os.path.join(self.pbs_conf['PBS_HOME'], 'mom_priv',
                                 'config')
            ret = self.du.cat(self.hostname, mconf, sudo=True)
            if ret['rc'] != 0:
                self.logger.error('error parsing configuration file')
                return None

            self.config = {}
            lines = ret['out']
            for line in lines:
                (k, v) = line.split()
                if k in self.config:
                    if isinstance(self.config[k], list):
                        self.config[k].append(v)
                    else:
                        self.config[k] = [self.config[k], v]
                else:
                    self.config[k] = v
        except:
            self.logger.error('error in parse_config')
            return None

        return self.config

    def add_config(self, conf={}, hup=True):
        """
        Add config options to mom_priv_config.

        conf - The configurations to add to mom_priv/config

        hup - If True (default) HUP the MoM

        Return True on success and False otherwise
        """

        doconfig = False

        if not self.config:
            self.parse_config()

        mc = self.config

        if mc is None:
            mc = {}

        for k, v in conf.items():
            if k in mc and (mc[k] == v or (isinstance(v, list) and
                                           mc[k] in v)):
                self.logger.debug(self.logprefix + 'config ' + k +
                                  ' already set to ' + str(v))
                continue
            else:
                doconfig = True
                break

        if not doconfig:
            return True

        self.logger.info(self.logprefix + "config " + str(conf))

        return self.apply_config(conf, hup)

    def apply_config(self, conf={}, hup=True, restart=False):
        """
        Apply configuration options to MoM.

        conf - A dictionary of configuration options to apply to MoM

        hup - If True (default) , HUP the MoM to apply the configuration

        Return True on success and False otherwise.
        """
        self.config = dict(self.config.items() + conf.items())
        try:
            (_, fn) = self.du.mkstemp()
            f = open(fn, 'w+')
            for k, v in self.config.items():
                if isinstance(v, list):
                    for eachprop in v:
                        f.write(str(k) + ' ' + str(eachprop) + '\n')
                else:
                    f.write(str(k) + ' ' + str(v) + '\n')
            f.close()

            dest = os.path.join(
                self.pbs_conf['PBS_HOME'],
                'mom_priv',
                'config')
            self.du.run_copy(self.hostname, fn, dest, mode=0644, sudo=True)
            self.du.chown(self.hostname, path=dest, uid=0, gid=0, sudo=True)
            os.remove(fn)
        except:
            raise PbsMomConfigError(rc=1, rv=False,
                                    msg='error processing add_config')

        if restart:
            return self.restart()
        elif hup:
            return self.signal('-HUP')

        return True

    def get_vnode_def(self, vnodefile=None):
        " return a vnode def file as a single string "
        if vnodefile is None:
            return None
        f = open(vnodefile)
        lines = f.readlines()
        f.close()
        return "".join(lines)

    def insert_vnode_def(self, vdef, fname=None, additive=False, restart=True):
        """
        Insert and enable a vnode definition. Root privilege is required

        vdef - The vnode definition string as created by create_vnode_def

        fname - The filename to write the vnode def string to

        additive - If True, keep all other vnode def files under config.d
        Default: False

        delete - If True, delete all nodes known to the server. Default: True

        restart - If True, restart the MoM. Default: True
        """
        try:
            (fd, fn) = self.du.mkstemp()
            os.write(fd, vdef)
            os.close(fd)
        except:
            logging.error("Failed to insert vnode definition")
            return
        if fname is None:
            fname = 'pbs_vnode.def'

        if not additive:
            self.delete_vnode_defs()

        self.du.mkdir(self.hostname, path=self.configd, logerr=False,
                      sudo=True)
        self.du.run_copy(self.hostname, fn, os.path.join(self.configd, fname),
                         sudo=True)

        msg = self.logprefix + 'inserted vnode definition file ' + fname + \
            ' on host: ' + self.hostname
        self.logger.info(msg)
        os.remove(fn)
        if restart:
            self.restart()

    def has_vnode_defs(self):
        cmd = ['ls', self.configd]
        ret = self.du.run_cmd(self.hostname, cmd, sudo=True, logerr=False)
        if ret['rc'] == 0 and len(ret['out']) > 0:
            return True
        else:
            return False

    def delete_vnode_defs(self, vdefname=None):
        """
        delete vnode definition(s) on this MoM

        vdefname - name of a vnode definition file to delete, if None all vnode
        definitions are deleted

        return True if delete succeed otherwise False
        """
        if vdefname is None:
            vdefname = self.configd
        else:
            vdefname = os.path.join(self.configd, vdefname)
        return self.du.rm(self.hostname, vdefname, recursive=True, force=True,
                          sudo=True)

    def has_pelog(self, filename=None):
        _has_pro = False
        _has_epi = False
        phome = self.pbs_conf['PBS_HOME']
        prolog = os.path.join(phome, 'mom_priv', 'prologue')
        epilog = os.path.join(phome, 'mom_priv', 'epilogue')
        if self.du.isfile(self.hostname, path=prolog, sudo=True):
            _has_pro = True
        if filename == 'prologue':
            return _has_pro
        if self.du.isfile(self.hostname, path=epilog, sudo=True):
            _has_epi = True
        if filename == 'epilogue':
            return _has_pro
        if _has_epi or _has_pro:
            return True
        return False

    def has_prologue(self):
        return self.has_pelog('prolouge')

    def has_epilogue(self):
        return self.has_pelog('epilogue')

    def delete_pelog(self):
        """
        Delete any prologue and epilogue files that may have been defined on
        this MoM
        """
        phome = self.pbs_conf['PBS_HOME']
        prolog = os.path.join(phome, 'mom_priv', 'prologue')
        epilog = os.path.join(phome, 'mom_priv', 'epilogue')
        ret = self.du.rm(self.hostname, epilog, force=True,
                         sudo=True, logerr=False)
        if ret:
            ret = self.du.rm(self.hostname, prolog, force=True,
                             sudo=True, logerr=False)
        if not ret:
            self.logger.error('problem deleting prologue/epilogue')
            # we don't bail because the problem may be that files did not
            # exist. Let tester fix the issue
        return ret

    def create_pelog(self, body=None, src=None, filename=None):
        """
        create prologue and epilogue files, functionality accepts
        either a body of the script or a source file.

        Return True on success and False on error
        """

        if self.has_diag:
            _msg = 'MoM is in loaded from diag so bypassing pelog creation'
            self.logger.info(_msg)
            return False

        if (src is None and body is None) or (filename is None):
            self.logger.error('file and body of script are required')
            return False

        pelog = os.path.join(self.pbs_conf['PBS_HOME'], 'mom_priv', filename)

        self.logger.info(self.logprefix +
                         ' creating ' + filename + ' with body\n' + '---')
        if body is not None:
            self.logger.info(body)
            (fd, src) = self.du.mkstemp(prefix='pbs-pelog')
            os.write(fd, body)
            os.close(fd)
        elif src is not None:
            _b = open(src)
            self.logger.info("\n".join(_b.readlines()))
            _b.close()
        self.logger.info('---')

        ret = self.du.run_copy(self.hostname, src, pelog, sudo=True)
        if body is not None:
            os.remove(src)
        if ret['rc'] != 0:
            self.logger.error('error creating pelog ')
            return False

        ret = self.du.chown(self.hostname, path=pelog, uid=0, gid=0, sudo=True,
                            logerr=False)
        if not ret:
            self.logger.error('error chowning pelog to root')
            return False

        ret = self.du.chmod(self.hostname, path=pelog, mode=0755, sudo=True)
        if not ret:
            self.logger.error('error changing mode of pelog')
            return False

        return True

    def prologue(self, body=None, src=None):
        return self.create_pelog(body, src, 'prologue')

    def epilogue(self, body=None, src=None):
        return self.create_pelog(body, src, 'epilogue')

    def action(self, act, script):
        " Define action script. Not currently implemented "
        pass


class Hook(PBSObject):

    """
    PBS hook objects. Holds attributes information and pointer to server
    """

    dflt_attributes = {}

    def __init__(self, name=None, attrs={}, server=None):
        self.logger = logging.getLogger(__name__)
        PBSObject.__init__(self, name, attrs, self.dflt_attributes)
        self.server = server


class ResourceResv(PBSObject):

    """
    Generic PBS resource reservation, i.e., job or advance/standing reservation
    """

    def execvnode(self, attr='exec_vnode'):
        if attr in self.attributes:
            return PbsTypeExecVnode(self.attributes[attr])
        else:
            return None

    def exechost(self):
        if 'exec_host' in self.attributes:
            return PbsTypeExecHost(self.attributes['exec_host'])
        else:
            return None

    def select(self):
        if hasattr(self, '_select') and self._select is not None:
            return self._select

        if 'schedselect' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['schedselect'])

        elif 'select' in self.attributes:
            self._select = PbsTypeSelect(self.attributes['select'])
        else:
            return None

        return self._select

    @classmethod
    def get_hosts(cls, exechost=None):
        " return the hosts portion of the exec_host "
        hosts = []
        exechosts = cls.utils.parse_exechost(exechost)
        if exechosts:
            for h in exechosts:
                eh = h.keys()[0]
                if eh not in hosts:
                    hosts.append(eh)
        return hosts

    def get_vnodes(self, execvnode=None):
        " return the unique vnode names of an execvnode as a list "
        if execvnode is None:
            if 'exec_vnode' in self.attributes:
                execvnode = self.attributes['exec_vnode']
            elif 'resv_nodes' in self.attributes:
                execvnode = self.attributes['resv_nodes']
            else:
                return []

        vnodes = []
        execvnodes = PbsTypeExecVnode(execvnode)
        if execvnodes:
            for n in execvnodes:
                ev = n.keys()[0]
                if ev not in vnodes:
                    vnodes.append(ev)
        return vnodes

    def walltime(self, attr='Resource_List.walltime'):
        if attr in self.attributes:
            return self.utils.convert_duration(self.attributes[attr])


class Job(ResourceResv):

    """
    PBS Job. Attributes and Resources
    """

    dflt_attributes = {
        ATTR_N: 'STDIN',
        ATTR_j: 'n',
        ATTR_m: 'a',
        ATTR_p: '0',
        ATTR_r: 'y',
        ATTR_k: 'oe',
    }
    runtime = 100
    logger = logging.getLogger(__name__)

    def __init__(self, username=None, attrs={}, jobname=None):
        self.server = {}
        self.script = None
        self.script_body = None
        if username is not None:
            self.username = str(username)
        else:
            self.username = None
        self.du = None
        self.interactive_handle = None

        PBSObject.__init__(self, None, attrs, self.dflt_attributes)

        if jobname is not None:
            self.custom_attrs[ATTR_N] = jobname
            self.attributes[ATTR_N] = jobname
        self.set_variable_list(self.username)
        self.set_sleep_time(100)

    def set_variable_list(self, user=None, workdir=None):
        " Customize the Variable_List job attribute to <user> "
        if user is None:
            userinfo = pwd.getpwuid(os.getuid())
            user = userinfo[0]
            homedir = userinfo[5]
        else:
            try:
                homedir = pwd.getpwnam(user)[5]
            except:
                homedir = ""

        self.username = user

        s = ['PBS_O_HOME=' + homedir]
        s += ['PBS_O_LANG=en_US.UTF-8']
        s += ['PBS_O_LOGNAME=' + user]
        s += ['PBS_O_PATH=/usr/bin:/bin:/usr/bin:/usr/local/bin']
        s += ['PBS_O_MAIL=/var/spool/mail/' + user]
        s += ['PBS_O_SHELL=/bin/bash']
        s += ['PBS_O_SYSTEM=Linux']
        if workdir is not None:
            wd = workdir
        else:
            wd = os.getcwd()
        s += ['PBS_O_WORKDIR=' + str(wd)]

        self.attributes[ATTR_v] = ",".join(s)
        self.set_attributes()

    def set_sleep_time(self, duration):
        """
        Set the sleep duration for this job.

        duration - The duration, in seconds, to sleep
        """
        self.set_execargs('/bin/sleep', duration)

    def set_execargs(self, executable, arguments=None):
        """
        Set the executable and arguments to use for this job

        executable - path to an executable. No checks are made.

        arguments - arguments to executable.
        """
        msg = ['job: executable set to ' + str(executable)]
        if arguments is not None:
            msg += [' with arguments: ' + str(arguments)]

        self.logger.info("".join(msg))
        self.attributes[ATTR_executable] = executable
        if arguments is not None:
            args = ''
            xml_beginargs = '<jsdl-hpcpa:Argument>'
            xml_endargs = '</jsdl-hpcpa:Argument>'
            if isinstance(arguments, list):
                for a in arguments:
                    args += xml_beginargs + str(a) + xml_endargs
            elif isinstance(arguments, str):
                args = xml_beginargs + arguments + xml_endargs
            elif isinstance(arguments, int):
                args = xml_beginargs + str(arguments) + xml_endargs
            self.attributes[ATTR_Arglist] = args
        else:
            self.unset_attributes([ATTR_Arglist])
        self.set_attributes()

    def create_script(self, body=None, uid=None, gid=None, hostname=None):
        """
        Create a job script from a given body of text into a temporary location

        body - the body of the script

        owner - Optionally the user to own this script, defaults ot current
        user

        hostname - The host on which the job script is to be created
        """
        if body is None:
            return None

        if isinstance(body, list):
            body = '\n'.join(body)

        self.script_body = body
        if self.du is None:
            self.du = DshUtils()
        # First create the temporary file as current user and only change
        # its mode once the current user has written to it
        (fd, fn) = self.du.mkstemp(hostname, prefix='PtlPbsJobScript', uid=uid,
                                   gid=gid, mode=0755, body=body)
        os.close(fd)

        if not self.du.is_localhost(hostname):
            self.du.run_copy(hostname, fn, fn)
        self.script = fn
        return fn


class Reservation(ResourceResv):

    " PBS Reservation. Attributes and Resources "

    dflt_attributes = {}

    def __init__(self, username=None, attrs={}):
        self.server = {}
        self.script = None
        self.attributes = attrs
        if username is None:
            userinfo = pwd.getpwuid(os.getuid())
            self.username = userinfo[0]
        else:
            self.username = str(username)

        # These are not in dflt_attributes because of the conversion to CLI
        # options is done strictly
        if ATTR_resv_start not in attrs:
            attrs[ATTR_resv_start] = str(int(time.time()) + 36 * 3600)

        if ATTR_resv_end not in attrs:
            if ATTR_resv_duration not in attrs:
                attrs[ATTR_resv_end] = str(int(time.time()) + 72 * 3600)

        PBSObject.__init__(self, None, attrs, self.dflt_attributes)
        self.set_attributes()

    def set_variable_list(self, user, workdir=None):
        pass


class InteractiveJob(threading.Thread):

    """
    An Interactive Job thread

    Interactive Jobs are submitted as a thread that sets the jobid as soon as
    it is returned by qsub -I, such that the caller can get back to monitoring
    the state of PBS while the interactive session goes on in the thread.

    The commands to be run within an interactive session are specified in the
    job's interactive_script attribute as a list of tuples, where the first
    item in each tuple is the command to run, and the subsequent items are
    the expected returned data.

    Implementation details:

    Support for interactive jobs is currently done through the pexpect
    module which must be installed separately from PTL. Interactive jobs are
    submitted through CLI only, there is no API support for this operation yet.

    The submission of an interactive job requires passing in job attributes,
    the command to execute (i.e. path to qsub -I) and the hostname

    when not impersonating:

    pexpect spawns the qsub -I command and expects a prompt back, for each
    tuple in the interactive_script, it sends the command and expects to
    match the return value.

    when impersonating:

    pexpect spawns sudo -u <user> qsub -I. The rest is as described in non-
    impersonating mode.
    """

    logger = logging.getLogger(__name__)

    pexpect_timeout = 15
    pexpect_sleep_time = .1
    du = DshUtils()

    def __init__(self, job, cmd, host):
        threading.Thread.__init__(self)
        self.job = job
        self.cmd = cmd
        self.jobid = None
        self.hostname = host

    def run(self):
        try:
            import pexpect
        except:
            self.logger.error('pexpect module is required for '
                              'interactive jobs')
            return None

        job = self.job
        cmd = self.cmd

        self.jobid = None
        self.logger.info("submit interactive job as " + job.username +
                         ": " + " ".join(cmd))
        if not hasattr(job, 'interactive_script'):
            self.logger.debug('no interactive_script attribute on job')
            return None

        try:
            # sleep to allow server to communicate with client
            # this value is set empirically so tweaking may be
            # needed
            _st = self.pexpect_sleep_time
            _to = self.pexpect_timeout
            _sc = job.interactive_script
            cmd = ['sudo', '-u', job.username] + cmd

            self.logger.debug(cmd)

            _p = pexpect.spawn(" ".join(cmd), timeout=_to)
            self.job.interactive_handle = _p
            time.sleep(_st)
            _p.expect('qsub: waiting for job (?P<jobid>[\d\w.]+) to start.*')
            if _p.match:
                self.jobid = _p.match.group('jobid')
            else:
                _p.close()
                self.job.interactive_handle = None
                return None
            self.logger.debug(_p.after.decode())
            for _l in _sc:
                self.logger.debug('sending: ' + _l[0])
                _p.sendline(_l[0])
                time.sleep(_st)
                # only way I could figure out to catch a sleep command
                # within a spawned pexpect child. Might need revisiting
                if 'sleep' in _l[0]:
                    _secs = _l[0].split()[1]
                    self.logger.debug('sleeping ' + str(_secs))
                    time.sleep(float(_secs))
                if len(_l) > 1:
                    for _r in range(1, len(_l)):
                        self.logger.debug('expecting: ' + _l[_r])
                        _p.expect(_l[_r])
                        time.sleep(_st)
                        self.logger.debug('received: ' + _p.after.decode())
                    time.sleep(_st)
                    self.logger.debug('received: ' + _p.after.decode())
            self.logger.debug('sending Ctrl-D')
            _p.sendcontrol('d')
            time.sleep(_st)
            _p.close()
            self.job.interactive_handle = None
            self.logger.debug(_p.exitstatus)
        except Exception:
            self.logger.error(traceback.print_exc())
            return None
        return self.jobid


class Queue(PBSObject):

    """
    PBS Queue container, holds attributes of the queue and pointer to server
    """

    dflt_attributes = {}

    def __init__(self, name=None, attrs={}, server=None):
        self.logger = logging.getLogger(__name__)
        PBSObject.__init__(self, name, attrs, self.dflt_attributes)

        self.server = server
        m = ['queue']
        if server is not None:
            m += ['@' + server.shortname]
        if self.name is not None:
            m += [' ', self.name]
        m += [': ']
        self.logprefix = "".join(m)

    def revert_to_defaults(self):
        " reset queue attributes to defaults "

        ignore_attrs = ['id', ATTR_count, ATTR_rescassn]
        ignore_attrs += [ATTR_qtype, ATTR_enable, ATTR_start, ATTR_total]
        ignore_attrs += ['THE_END']

        len_attrs = len(ignore_attrs)
        unsetlist = []
        setdict = {}

        self.logger.info(
            self.logprefix +
            "reverting configuration to defaults")
        if self.server is not None:
            self.server.status(QUEUE, id=self.name, level=logging.DEBUG)

        for k in self.attributes.keys():
            for i in range(len_attrs):
                if k.startswith(ignore_attrs[i]):
                    break
            if (i == (len_attrs - 1)) and k not in self.dflt_attributes:
                unsetlist.append(k)

        if len(unsetlist) != 0 and self.server is not None:
            try:
                self.server.manager(MGR_CMD_UNSET, MGR_OBJ_QUEUE, unsetlist,
                                    self.name)
            except PbsManagerError, e:
                self.logger.error(e.msg)

        for k in self.dflt_attributes.keys():
            if (k not in self.attributes or
                    self.attributes[k] != self.dflt_attributes[k]):
                setdict[k] = self.dflt_attributes[k]

        if len(setdict.keys()) != 0 and self.server is not None:
            self.server.manager(MGR_CMD_SET, MGR_OBJ_QUEUE, setdict)


class PBSInitServices(object):

    def __init__(self, hostname=None, conf=None):
        self.logger = logging.getLogger(__name__)
        self.hostname = hostname
        if self.hostname is None:
            self.hostname = socket.gethostname()
        self.dflt_conf_file = os.environ.get('PBS_CONF_FILE', '/etc/pbs.conf')
        self.conf_file = conf
        self.du = DshUtils()
        self.is_sunos = sys.platform.startswith('sunos')
        self.is_aix = sys.platform.startswith('aix')
        self.is_linux = sys.platform.startswith('linux')

    def initd(self, hostname=None, op='status', conf_file=None,
              init_script=None):
        """
        Run the init script for a given operation

        hostname - hostname on which to execute the init script

        op - one of status, start, stop, restart

        conf_file - optional path to a configuration file

        init_script - optional path to a PBS init script
        """
        if hostname is None:
            hostname = self.hostname
        if conf_file is None:
            conf_file = self.conf_file
        return self._unix_initd(hostname, op, conf_file, init_script)

    def restart(self, hostname=None, init_script=None):
        """
        Run the init script for a restart operation

        hostname - hostname on which to execute the init script

        init_script - optional path to a PBS init script
        """
        return self.initd(hostname, op='restart', init_script=init_script)

    def start(self, hostname=None, init_script=None):
        """
        Run the init script for a start operation

        hostname - hostname on which to execute the init script

        init_script - optional path to a PBS init script
        """
        return self.initd(hostname, op='start', init_script=init_script)

    def stop(self, hostname=None, init_script=None):
        """
        Run the init script for a stop operation

        hostname - hostname on which to execute the init script

        init_script - optional path to a PBS init script
        """
        return self.initd(hostname, op='stop', init_script=init_script)

    def status(self, hostname=None, init_script=None):
        """
        Run the init script for a status operation

        hostname - hostname on which to execute the init script

        init_script - optional path to a PBS init script
        """
        return self.initd(hostname, op='status', init_script=init_script)

    def _unix_initd(self, hostname, op, conf_file, init_script):
        """
        Helper function for initd (*nix version)
        """
        if ((conf_file is not None) and (conf_file != self.dflt_conf_file)):
            init_cmd = ['PBS_CONF_FILE=' + conf_file]
            _as = True
        else:
            init_cmd = []
            _as = False
        if ((init_script is None) or (not init_script.startswith('/'))):
            c = self.du.parse_pbs_config(hostname, conf_file)
            if 'PBS_EXEC' not in c:
                msg = 'Missing PBS_EXEC setting in pbs config'
                raise PbsInitServicesError(rc=1, rv=False, msg=msg)
            if init_script is None:
                init_script = os.path.join(c['PBS_EXEC'], 'libexec',
                                            'pbs_init.d')
            else:
                init_script = os.path.join(c['PBS_EXEC'], 'etc',
                                            init_script)
            if not self.du.isfile(hostname, path=init_script, sudo=True):
                # Could be Type 3 installation where we will not have
                # PBS_EXEC/libexec/pbs_init.d
                return []
        init_cmd += [init_script, op]
        msg = 'running init script to ' + op + ' pbs'
        msg += ' on ' + hostname
        if conf_file is not None:
            msg += ' using ' + conf_file
        msg += ' init_cmd=%s' % (str(init_cmd))
        self.logger.info(msg)
        ret = self.du.run_cmd(hostname, init_cmd, sudo=True, as_script=_as,
                              logerr=False)
        if ret['rc'] != 0:
            raise PbsInitServicesError(rc=ret['rc'], rv=False,
                                       msg='\n'.join(ret['err']))
        else:
            return ret['out']

    def switch_version(self, hostname=None, version=None):
        """
        Switch to another version of PBS installed on the system

        hostname - The hostname to operate on

        version - version to switch
        """
        pbs_conf = self.du.parse_pbs_config(hostname)
        if 'PBS_EXEC' in pbs_conf:
            dn = os.path.dirname(pbs_conf['PBS_EXEC'])
            newver = os.path.join(dn, version)
            ret = self.du.isdir(hostname, path=newver)
            if not ret:
                msg = 'no version ' + version + ' on host ' + hostname
                raise PbsInitServicesError(rc=0, rv=False, msg=msg)
            self.stop(hostname)
            dflt = os.path.join(dn, 'default')
            ret = self.du.isfile(hostname, path=dflt)
            if ret:
                self.logger.info('removing symbolic link ' + dflt)
                self.du.rm(hostname, dflt, sudo=True, logerr=False)
                self.du.set_pbs_config(hostname, confs={'PBS_EXEC': dflt})
            else:
                self.du.set_pbs_config(hostname, confs={'PBS_EXEC': newver})

            self.logger.info('linking ' + newver + ' to ' + dflt)
            self.du.run_cmd(hostname, ['ln', '-s', newver, dflt],
                            sudo=True, logerr=False)
            self.start(hostname)
