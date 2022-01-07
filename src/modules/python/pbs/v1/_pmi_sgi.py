
"""

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

__doc__ = """
This module is used for SGI systems.
"""

import pbs
import os
import sys
from pbs.v1._pmi_types import BackendError
from pbs.v1._pmi_utils import _pbs_conf, _get_hosts

pbsexec = _pbs_conf("PBS_EXEC")
if pbsexec is None:
    raise BackendError("PBS_EXEC not found")

py_version = str(sys.version_info.major) + "." + str(sys.version_info.minor)
_path = os.path.join(pbsexec, "python", "lib", py_version)
if _path not in sys.path:
    sys.path.append(_path)
_path = os.path.join(pbsexec, "python", "lib", py_version, "lib-dynload")
if _path not in sys.path:
    sys.path.append(_path)
import encodings


# Plug in the path for the HPE/SGI power API.
_path = "/opt/clmgr/power-service"
if os.path.exists(_path):
    # Look for HPCM support.
    if _path not in sys.path:
        sys.path.append(_path)
    import hpe_clmgr_power_api as api
else:
    # Look for SGIMC support.
    _path = "/opt/sgi/ta"
    if _path not in sys.path:
        sys.path.append(_path)
    import sgi_power_api as api


class Pmi:
    def __init__(self, pyhome=None):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: init")
        api.SERVER = """lead-eth:8888"""

    def _connect(self, endpoint, port, job):
        if job is None:
            pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: connect")
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: %s connect" % (job.id))
        api.VerifyConnection()
        return

    def _disconnect(self, job):
        if job is None:
            pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: disconnect")
        else:
            pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: %s disconnect" % (job.id))
        return

    def _get_usage(self, job):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: %s get_usage" % (job.id))
        report = api.MonitorReport(job.id)
        if report is not None and report[0] == 'total_energy':
            pbs.logjobmsg(job.id, "SGI: energy %fkWh" % report[1])
            return report[1]
        return None

    def _query(self, query_type):
        pbs.logmsg(pbs.LOG_DEBUG, "SGI: query")
        if query_type == pbs.Power.QUERY_PROFILE:
            return api.ListAvailableProfiles()
        return None

    def _activate_profile(self, profile_name, job):
        pbs.logmsg(pbs.LOG_DEBUG, "SGI: %s activate '%s'" %
                   (job.id, str(profile_name)))
        api.NodesetCreate(job.id, _get_hosts(job))
        api.MonitorStart(job.id, profile_name)
        return False

    def _deactivate_profile(self, job):
        pbs.logmsg(pbs.LOG_DEBUG, "SGI: %s deactivate" % (job.id))
        try:
            api.MonitorStop(job.id)
        # be sure to remove the nodeset
        finally:
            api.NodesetDelete(job.id)
        return False

    def _pmi_power_off(self, hosts):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: powering-off the node")
        return False

    def _pmi_power_on(self, hosts):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: powering-on the node")
        return False

    def _pmi_ramp_down(self, hosts):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: ramp-down the node")
        return False

    def _pmi_ramp_up(self, hosts):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: ramp up the node")
        return False

    def _pmi_power_status(self, hosts):
        pbs.logmsg(pbs.EVENT_DEBUG3, "SGI: status of the nodes")
        return False
