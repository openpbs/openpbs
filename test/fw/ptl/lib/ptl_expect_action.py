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

import logging


class ExpectActions(object):

    """
    List of action handlers to run when Server's expect
    function does not get the expected result

    :param action: Action to run
    :type action: str
    :param level: Logging level
    """

    actions = {}

    def __init__(self, action=None, level=logging.INFO):
        self.logger = logging.getLogger(__name__)
        self.add_action(action, level=level)

    def add_action(self, action=None, hostname=None, level=logging.INFO):
        """
        Add an action

        :param action: Action to add
        :param hostname: Machine hostname
        :type hostname: str
        :param level: Logging level
        """
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
        """
        check whether action exists or not

        :param name: Name of action
        :type name: str
        """
        if name in self.actions:
            return True
        return False

    def get_action(self, name):
        """
        Get an action if exists

        :param name: Name of action
        :type name: str
        """
        if name in self.actions:
            return self.actions[name]
        return None

    def list_actions(self, level=logging.INFO):
        """
        List an actions

        :param level: Logging level
        """
        if level >= logging.INFO:
            self.logger.info(self.get_all_cations)
        else:
            self.logger.debug(self.get_all_cations)

    def get_all_actions(self):
        """
        Get all the action
        """
        return list(self.actions.values())

    def get_actions_by_type(self, atype=None):
        """
        Get an action by type

        :param atype: Action type
        :type atype: str
        """
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
        """
        Disable an action
        """
        self._control_action(action, name, enable=False)

    def enable_action(self, action=None, name=None):
        """
        Enable an action
        """
        self._control_action(action, name, enable=True)

    def disable_all_actions(self):
        """
        Disable all actions
        """
        for a in self.actions.values():
            a.enabled = False

    def enable_all_actions(self):
        """
        Enable all actions
        """
        for a in self.actions.values():
            a.enabled = True


class ExpectAction(object):

    """
    Action function to run when Server's expect function does
    not get the expected result

    :param atype: Action type
    :type atype: str
    """

    def __init__(self, name=None, enabled=True, atype=None, action=None,
                 level=logging.INFO):
        self.logger = logging.getLogger(__name__)
        self.set_name(name, level=level)
        self.set_enabled(enabled)
        self.set_type(atype)
        self.set_action(action)

    def set_name(self, name, level=logging.INFO):
        """
        Set the actione name

        :param name: Action name
        :type name: str
        """
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
