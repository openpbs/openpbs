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


import copy
import datetime
import logging
import os
import random
import re
import sys
import time

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
 LE, LT, MATCH, MATCH_RE, NOT, DFLT) = list(range(14))

(PTL_OR, PTL_AND) = [0, 1]

(IFL_SUBMIT, IFL_SELECT, IFL_TERMINATE, IFL_ALTER,
 IFL_MSG, IFL_DELETE, IFL_RALTER) = [0, 1, 2, 3, 4, 5, 6]

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
    'terminate': 'PbsQtermError',
    'alterresv': 'PbsResvAlterError'
}
