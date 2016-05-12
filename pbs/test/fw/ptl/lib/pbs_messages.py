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
A collection of PBS message interfaces

The purpose of this module is to provide an interface to PBS messages
to manage their state and provide change control across releases.
These messages may be emitted on stderr, stdout, or in logs and may be
associated to server, scheduler, mom, comm, or client.

Consumers of this class initialize an object by passing it a version of PBS
that is being worked on, and retrieve an instance variable of the message
of interest, for example, working with version 13.0 and looking for a
startup message on the db starting in the background one would:

messages = PbsMessages('13.0')
print messages.background_db_connect
"""

import logging
from distutils.version import LooseVersion


class PbsMessages(object):

    logger = logging.getLogger(__name__)

    # message's context
    stdout_msg = 'stdout'
    stderr_msg = 'stderr'
    log_msg = 'log'

    # message's associated component
    pbs = 'all'
    server = 'server'
    sched = 'scheduler'
    mom = 'mom'
    comm = 'comm'
    client = 'client'

    default_version = LooseVersion('0')

    # All interface messages must be added to this list.
    messages = {
        0:
        (
            default_version,
            'Connecting to PBS dataservice......continuing in background.',
            (stderr_msg,),
            (server,),
        ),
        1:
        (
            default_version,
            '"%s" does not start with alpha; ignoring resource',
            (stderr_msg,),
            (server,),
        ),
        2:
        (
            default_version,
            'invalid character in resource name "%s"',
            (stderr_msg,),
            (server,),
        ),
        3:
        (
            default_version,
            'invalid resource type %s',
            (stderr_msg,),
            (server,),
        ),
        4:
        (
            default_version,
            'Invalid resource flag %s',
            (stderr_msg,),
            (server,),
        ),
        5:
        (
            default_version,
            '%s: illegal -%s value',
            (stderr_msg,),
            (server,),
        ),
        6:
        (
            default_version,
            '(.*)%s: option requires an argument -- (\'?)%s(\'?)',
            (stderr_msg,),
            (server,),
        ),
        7:
        (
            default_version,
            '%s: Unauthorized Request  %s',
            (stderr_msg,),
            (server,),
        ),
        8:
        (
            default_version,
            '%s: illegally formed job identifier: %s',
            (stderr_msg,),
            (server,),
        ),
        9:
        (
            default_version,
            '%s: Unknown queue %s',
            (stderr_msg,),
            (server,),
        ),
        10:
        (
            default_version,
            'Unknown Host.',
            (stderr_msg,),
            (server,),
        ),
        11:
        (
            default_version,
            '%s: illegally formed destination: %s',
            (stderr_msg,),
            (server,),
        ),
        12:
        (
            default_version,
            '%s: Job rejected by all possible destinations %s',
            (stderr_msg,),
            (server,),
        ),
        13:
        (
            default_version,
            '%s: Request invalid for state of job %s',
            (stderr_msg,),
            (server,),
        ),
        14:
        (
            default_version,
            '%s: Queue is not enabled %s',
            (stderr_msg,),
            (server,),
        ),
        15:
        (
            default_version,
            '%s: invalid server name: %s',
            (stderr_msg,),
            (server,),
        ),
        16:
        (
            default_version,
            '%s: job is not rerunnable %s',
            (stderr_msg,),
            (server,),
        ),
        17:
        (
            default_version,
            '%s: Unknown node  %s',
            (stderr_msg,),
            (server,),
        ),
        18:
        (
            default_version,
            '%s: Unknown/illegal signal name %s',
            (stderr_msg,),
            (server,),
        ),
        19:
        (
            default_version,
            '%s: Illegal attribute or resource value',
            (stderr_msg,),
            (server,),
        ),
        20:
        (
            default_version,
            '%s: Unknown resource %s',
            (stderr_msg,),
            (server,),
        ),
        21:
        (
            default_version,
            '%s: Cannot modify attribute while job running  %s %s',
            (stderr_msg,),
            (server,),
        ),
        22:
        (
            default_version,
            '%s: Job name is too long ',
            (stderr_msg,),
            (server,),
        ),
        23:
        (
            default_version,
            '%s: Job violates queue and/or server resource limits',
            (stderr_msg,),
            (server,),
        ),
        24:
        (
            default_version,
            '.*;Job;%s;Dependency request for job rejected by %s.*',
            (log_msg,),
            (server,),
        ),
        25:
        (
            default_version,
            '.*;Job;%s;Job deleted as result of dependency on job %s.*',
            (log_msg,),
            (server,),
        ),
        26:
        (
            default_version,
            'qsub: script file:: No such file or directory',
            (stderr_msg,),
            (client,),
        ),
        27:
        (
            default_version,
            'qsub: script not a file',
            (stderr_msg,),
            (client,),
        ),
        28:
        (
            default_version,
            'qsub: directive error: %s ',
            (stderr_msg,),
            (client,),
        ),
        29:
        (
            default_version,
            'qsub: cannot send environment with the job',
            (stderr_msg,),
            (client,),
        ),
    }

    def __init__(self, version=None):
        if version is None:
            version = self.default_version
        elif not isinstance(version, LooseVersion):
            version = LooseVersion(version)
        self.version = version
        self.logger.info('messages middleware: initialized with version ' +
                         str(version))
        self._background_db_connect = (self.messages[0],)
        self._startup_resource_error = (self.messages[1],)
        self._startup_invalid_char_in_resource = (self.messages[2],)
        self._startup_invalid_resource_type = (self.messages[3],)
        self._startup_invalid_resource_flag = (self.messages[4],)
        self._illegal_option_value = (self.messages[5],)
        self._option_require_arg = (self.messages[6],)
        self._unauthorized_request = (self.messages[7],)
        self._illegally_formed_job_id = (self.messages[8],)
        self._unknown_queue = (self.messages[9],)
        self._unknown_host = (self.messages[10],)
        self._illegally_formed_destination = (self.messages[11],)
        self._bad_route = (self.messages[12],)
        self._invalid_state_of_job = (self.messages[13],)
        self._queue_is_not_enabled = (self.messages[14],)
        self._invalid_server_name = (self.messages[15],)
        self._job_is_not_rerunnable = (self.messages[16],)
        self._unknown_node = (self.messages[17],)
        self._unknown_illegal_signal = (self.messages[18],)
        self._illegal_attr_or_resc_value = (self.messages[19],)
        self._unknown_resource = (self.messages[20],)
        self._cannot_modify_attr_while_job_running = (self.messages[21],)
        self._job_name_too_long = (self.messages[22],)
        self._job_vialates_resc_limits = (self.messages[23],)
        self._dependency_req_rejected = (self.messages[24],)
        self._job_deleted_as_dependency_job = (self.messages[25],)
        self._qsub_scr_file_does_not_exist = (self.messages[26],)
        self._qsub_scr_not_a_file = (self.messages[27],)
        self._qsub_directive_err = (self.messages[28],)
        self._qsub_cannot_send_env_with_job = (self.messages[29],)

    def __getattr__(self, name):
        iname = '_' + name
        default_msg = ''
        messages = self.__dict__[iname]
        if len(messages) == 1 or self.version is None:
            default_msg = messages[0][1]
        else:
            for m in messages:
                ver, msg = m[0], m[1]
                if ver == self.default_version:
                    default_msg = msg
                    continue
                elif self.version >= ver:
                    return msg
        return default_msg
