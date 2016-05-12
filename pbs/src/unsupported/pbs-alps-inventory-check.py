# coding: utf-8
#!/usr/bin/python


'''
#  Copyright (C) 1994-2016 Altair Engineering, Inc.
#  For more information, contact Altair at www.altair.com.
#   
#  This file is part of the PBS Professional ("PBS Pro") software.
#  
#  Open Source License Information:
#   
#  PBS Pro is free software. You can redistribute it and/or modify it under the
#  terms of the GNU Affero General Public License as published by the Free 
#  Software Foundation, either version 3 of the License, or (at your option) any 
#  later version.
#   
#  PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#   
#  You should have received a copy of the GNU Affero General Public License along 
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
#   
#  Commercial License Information: 
#  
#  The PBS Pro software is licensed under the terms of the GNU Affero General 
#  Public License agreement ("AGPL"), except where a separate commercial license 
#  agreement for PBS Pro version 14 or later has been executed in writing with Altair.
#   
#  Altair’s dual-license business model allows companies, individuals, and 
#  organizations to create proprietary derivative works of PBS Pro and distribute 
#  them - whether embedded or bundled with other software - under a commercial 
#  license agreement.
#  
#  Use of Altair’s trademarks, including but not limited to "PBS™", 
#  "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
#  trademark licensing policies.

v2.0  20130711  author: Scott Suchyta

Define pbs-alps-inventory-check hook within PBS Professional
qmgr -c "create hook pbs-alps-inventory-check"
qmgr -c "set hook pbs-alps-inventory-check event = exechost_periodic"
qmgr -c "set hook pbs-alps-inventory-check freq = 300
qmgr -c "import hook pbs-alps-inventory-check application/x-python default pbs-alps-inventory-check.py"

Requirements:
- Cray Login nodes must be time sync (NTP)
- hostname of the machine must be the same as what was defined in qmgr
- PBS-ALPS Inventory Check runs every 5mins (300s)
- If multipe cray_login nodes are available (free or running jobs), then a different
cray_login node will execute the script. This avoids single point of failure.
- Force PBS to re-read ALPS inventory if the number of free compute nodes in PBS is
different than the number of free compute nodes in ALPS

Assumptions:
- apstat and xtprocadmin are in the PATH
- If PBS and ALPS values are NOT EQUAL, then PBS MOM is HUP'd.
- PBS-ALPS Inventory Check runs every 5 mins, therefore if the site has >12 Cray Login nodes
that are available, then only the first 12 available Cray Login nodes will ever execute this
script.

Caveats:
- If PBS sees 1024 free and ALPS see 1024 free BUT they are different set of 1024, PBS MOM
will NOT be HUP'd
- Not all PEP8 rules may be followed.
'''

import pbs
import time
import sys
import os


# Set the following if you would like mail sent when a mismatch occurs.
# The mail command must be properly configured.
EMAIL = None                      # can set to say EMAIL="john_doe@foo.com"
SUBJECT = "PBS/ALPS out of sync"  # can set to say SUBJECT="PBS/ALPS out of sync on $time"
EMAILMSG = "/tmp/emailmsg.txt"
ADDITIONAL_DEBUG = 0           # 0 disbales addition debug, 1 enables additional_debug


# round_down: Small function to round down the current minute to the nearest 5
def round_down(num, divisor):
    return num - (num % divisor)

# check_pbs: returns the number of usable, cray vnodes that are not of
# cray login type.
def check_pbs():
    vnodes = pbs.server().vnodes()
    free = 0
    for v in vnodes:
        if v.resources_available["vntype"] and \
           v.resources_available["vntype"] != "cray_login" and \
           ((v.state == pbs.ND_FREE) or (v.state == pbs.ND_JOB_EXCLUSIVE) or (v.state == pbs.ND_RESV_EXCLUSIVE)):
            free += 1
    return free

# check_alps: returns the # of nodes marked "up" and of "batch" type.
#
# NOTE: This is doing the equivalent of:
#        echo $(apstat -nv | grep ' B ' | grep ' UP ' | wc -l)
#
def check_alps():
    pfd = os.popen("apstat -nv")
    alps_ct = 0
    while True:
        line = pfd.readline()
        if not line:
            break
        l = line.split()
        if len(l) < 4:
            break
        state = l[2]
        hw = l[3]
        if (state == "UP") and (hw == "B"):
            alps_ct += 1
        pfd.close()
        return alps_ct

# check_sdb: returns the # of nodes marked "compute", of status "up", and mode
# "batch"
#
# NOTE: This is doing the equivalent of:
#  echo $(xtprocadmin | grep ' compute ' | grep ' up ' | grep ' batch' | wc -l)
#
def check_sdb():
    pfd = os.popen("xtprocadmin")
    sdb_ct = 0
    while True:
        line = pfd.readline()
        if not line:
            break
        l = line.split()
        if len(l) < 6:
            break
        node_type = l[3]
        status = l[4]
        mode = l[5]
        if (node_type == "compute") and (status == "up") and (mode == "batch"):
            sdb_ct += 1
    pfd.close()
    return sdb_ct

# Given pbs.conf variable name (ex. PBS_HOME), return
# the value as obtained from PBS' pbs.conf file.
def get_conf_val(var):
    conf_file = os.environ.get("PBS_CONF_FILE", "/etc/pbs.conf")
    fd = open(conf_file, "r")
    for line in fd:
        l = line.strip().split("=")
        if l[0] == var:
            fd.close()
            return l[1]
    fd.close()
    return None


# Main
pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: START")

# Determine the minute of the time.
now = time.strftime("%M", time.gmtime())

if ADDITIONAL_DEBUG:
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: ADDITIONAL DEBUG, the minute right now = %s" % (now))

# Identify the cray_login nodes, which are running the pbs_mom and put them
# into a list.
cray_login = []
vnodes = pbs.server().vnodes()
for v in vnodes:
    if v.resources_available["vntype"] and \
       v.resources_available["vntype"] == "cray_login" and \
       ((v.state == pbs.ND_FREE) or (v.state == pbs.ND_JOB_EXCLUSIVE) or (v.state == pbs.ND_RESV_EXCLUSIVE)):
        cray_login.append(str(v))

if ADDITIONAL_DEBUG:
    for cl in cray_login:
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: ADDITIONAL DEBUG, Eligible Cray Login Nodes = %s" % (cl))

# Determine the total number of cray_login nodes
cray_login_total = len(cray_login)
if cray_login_total > 0:
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: Total Eligible Cray Login Nodes = %s" % (cray_login_total))
else:
    pbs.logmsg(pbs.LOG_ERROR, "PBS/ALP Inventory Check: NO ELIGIBLE Cray Login Nodes to perform inventory check!!")
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: FINISH")
    sys.exit(0)

# Determine the local cray_login index number
cray_login_local_name = pbs.get_local_nodename()

if ADDITIONAL_DEBUG:
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: ADDITIONAL DEBUG, Cray Login Local Name = %s" %
               (cray_login_local_name))

# Evaluate whether cray_login_local_name is in the cray_login list
try:
    cray_login_index = cray_login.index(str(cray_login_local_name))
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: Evaluating Cray Login node (%s, %s) for executing hook" %
               (cray_login_local_name, cray_login_index))

    # Start the clock at the beginning of the hour: 0mins
    time = 0
    time = (cray_login_index - 1) * 5

    while (time < 60):
        if (int(time) == round_down(int(now), 5)):
            if ADDITIONAL_DEBUG:
                pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: ADDITIONAL DEBUG, Round down minute = %s" % (time))
            pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: Cray Login node (%s) will continue executing the hook" %
                       (cray_login_local_name))
            break
        time = time + (cray_login_total * 5)
    else:
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: Cray Login node (%s) will STOP executing the hook - it's NOT my turn" % (cray_login_local_name))
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: FINISH")
        sys.exit(0)

    PBSFREE = check_pbs()
    ALPSFREE = check_alps()
    SDBFREE = check_sdb()
    if PBSFREE != ALPSFREE:
        pbs.logmsg(pbs.LOG_WARNING, "PBS/ALP Inventory Check: PBS and ALPS are out of sync!")
        pbs.logmsg(pbs.LOG_WARNING, "PBS/ALP Inventory Check: PBS see free = %d" % (PBSFREE))
        pbs.logmsg(pbs.LOG_WARNING, "PBS/ALP Inventory Check: ALPS see free = %d" % (ALPSFREE))
        pbs.logmsg(pbs.LOG_WARNING, "PBS/ALP Inventory Check: HUP'ing MOM")
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: FINISH")

        if EMAIL:
            fd = open(EMAILMSG, "w")
            msg = "Hello,\n\n" + \
                "PBS and ALPS are out of sync at this time: " + time.asctime() + \
                "\n\n PBS reports: %d nodes marked free.\n" % (PBSFREE) + \
                " ALPS reports: %d nodes marked up and batch.\n" % (ALPSFREE) + \
                " SDB reports: %d nodes marked compute, up, and batch." % \
                (SDBFREE) + \
                "\n\nSending SIGHUP to MOM on " + pbs.get_local_nodename() + \
                "...\n\n"
            fd.write(msg)
            fd.close()
            os.system("mail -s '" + SUBJECT + "' " + EMAIL + " < " + EMAILMSG)

        PBS_MOM_HOME = get_conf_val("PBS_MOM_HOME")
        if not PBS_MOM_HOME:
            PBS_MOM_HOME = get_conf_val("PBS_HOME")

        if PBS_MOM_HOME:
            pidfile = PBS_MOM_HOME + "/mom_priv/mom.lock"
            os.system("kill -HUP `cat " + pidfile + "`")
    else:
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: PBS and ALPS are in sync")
        pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: FINISH")

except SystemExit:
    pass

except:
    pbs.logmsg(pbs.LOG_ERROR, "PBS/ALP Inventory Check: Cray Login Local Name (%s) is not found in PBS inventory" %
               (cray_login_local_name))
    pbs.logmsg(pbs.LOG_DEBUG, "PBS/ALP Inventory Check: FINISH")

