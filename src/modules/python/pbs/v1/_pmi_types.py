
"""

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

__doc__ = """
This file contains the Power Management Infrastructure (PMI) base types.
It contains mostly vendor agnostic code with the exception of the
initialization method that determines which vendor specific PMI calls
to import.
"""

import sys
import os
import pbs
from pbs.v1._pmi_utils import _get_hosts, _get_vnode_names, _running_excl
from pbs.v1._exc_types import *


class InternalError(Exception):
    def __init__(self, msg="Internal error encountered."):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class BackendError(Exception):
    def __init__(self, msg="Backend error encountered."):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class Power:

    QUERY_PROFILE = 0

    def __init__(self, requested_pmi=None):
        self.__pmi = None
        self.__sitepk = None

        if requested_pmi is None:
            self.pmi_type = self.__get_pmi_type()
        else:
            self.pmi_type = requested_pmi

        try:
            _temp = __import__("pbs.v1._pmi_" + self.pmi_type,
                               globals(), locals(), ['Pmi'], 0)
        except Exception as e:
            raise InternalError(
                "could not import: " + self.pmi_type + ": " + str(e))

        try:
            self.__pmi = _temp.Pmi(self.__sitepk)
        except Exception as e:
            raise InternalError(
                "No such PMI: " + self.pmi_type + ": " + str(e))

    def __get_pmi_type(self):
        """
        Determine what system is being used.
        """
        if os.path.exists('/proc/cray_xt/cname'):
            return "cray"
        if os.path.exists('/opt/clmgr/power-service') or os.path.exists('/opt/sgi'):
            return "sgi"
        return "none"

    def _map_profile_names(self, pnames):
        """
        Take a python list of profile names and create a string suitable for
        setting the eoe value for a node.
        """
        if pnames is None:
            return ""
        return ",".join(pnames)

    def _check_pmi(self):
        if self.__pmi is None:
            raise InternalError("No Power Management Interface instance.")

    def connect(self, endpoint=None, port=None, job=None):
        self._check_pmi()
        if job is None:
            try:
                job = pbs.event().job
            except EventIncompatibleError:
                pass
        return self.__pmi._connect(endpoint, port, job)

    def disconnect(self, job=None):
        self._check_pmi()
        if job is None:
            try:
                job = pbs.event().job
            except EventIncompatibleError:
                pass
        return self.__pmi._disconnect(job)

    def get_usage(self, job=None):
        self._check_pmi()
        if job is None:
            job = pbs.event().job
        return self.__pmi._get_usage(job)

    def query(self, query_type=None):
        self._check_pmi()
        return self.__pmi._query(query_type)

    def activate_profile(self, profile_name=None, job=None):
        self._check_pmi()
        if job is None:
            job = pbs.event().job

        try:
            ret = self.__pmi._activate_profile(profile_name, job)
            if profile_name is not None:
                hosts = _get_vnode_names(job)
                for h in hosts:
                    try:
                        pbs.event().vnode_list[h].current_eoe = profile_name
                    except:
                        pass
            return ret
        except BackendError as e:
            # get fresh set of profile names, ignore errors
            mynode = pbs.event().vnode_list[pbs.get_local_nodename()]
            if mynode.power_provisioning:
                try:
                    profiles = self.__pmi._query(
                        pbs.Power.QUERY_PROFILE)
                    names = self._map_profile_names(profiles)
                    mynode.resources_available["eoe"] = names
                    pbs.logmsg(pbs.LOG_WARNING,
                               "PMI:activate: set eoe: %s" % names)
                except:
                    pass
            raise BackendError(e)
        except InternalError as e:
            # couldn't do activation so set vnode offline
            me = pbs.get_local_nodename()
            pbs.event().vnode_list[me].state += pbs.ND_OFFLINE
            pbs.logmsg(pbs.LOG_WARNING, "PMI:activate: set vnode offline")
            raise InternalError(e)

    def deactivate_profile(self, job=None):
        self._check_pmi()

        if job is None:
            job = pbs.event().job
        if _running_excl(job):
            pbs.logjobmsg(job.id, "PMI: reset current_eoe")
            for h in _get_vnode_names(job):
                try:
                    pbs.event().vnode_list[h].current_eoe = None
                except:
                    pass
        return self.__pmi._deactivate_profile(job)

    def power_off(self, hosts=None):
        self._check_pmi()
        pbs.logmsg(pbs.EVENT_DEBUG3, "PMI:poweroff: powering off nodes")
        return self.__pmi._pmi_power_off(hosts)

    def power_on(self, hosts=None):
        self._check_pmi()
        pbs.logmsg(pbs.EVENT_DEBUG3, "PMI:poweron: powering on nodes")
        return self.__pmi._pmi_power_on(hosts)

    def ramp_down(self, hosts=None):
        self._check_pmi()
        pbs.logmsg(pbs.EVENT_DEBUG3, "PMI:rampdown: ramping down nodes")
        return self.__pmi._pmi_ramp_down(hosts)

    def ramp_up(self, hosts=None):
        self._check_pmi()
        pbs.logmsg(pbs.EVENT_DEBUG3, "PMI:rampup: ramping up nodes")
        return self.__pmi._pmi_ramp_up(hosts)

    def power_status(self, hosts=None):
        self._check_pmi()
        pbs.logmsg(pbs.EVENT_DEBUG3, "PMI:powerstatus: status of nodes")
        return self.__pmi._pmi_power_status(hosts)
