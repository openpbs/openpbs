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


##############################################################################
# Purpose: To create a class for preforming node disk checks
# Date: 20141114
##############################################################################

'''
create hook NHC
set hook NHC event = 'execjob_begin,execjob_prologue'
set hook NHC fail_action = offline_vnodes
import hook NHC application/x-python default NodeHealthCheck.py
import hook NHC application/x-config default NodeHealthCheck.json

One can also optionally add exechost_periodic to NHC event
'''

import json
import os
# Import the needed modules for the program
import platform
import signal
import subprocess
import sys
import time
from pwd import getpwnam

try:
    import pbs

    # Remember, periodic events do not have a job associated to them.
    if pbs.event().type != pbs.EXECHOST_PERIODIC:
        who = pbs.event().job.euser

# For limiting testing to 1 user's jobs, uncomment this and change username
#        pbs.logmsg(pbs.EVENT_DEBUG3,'User: %s'%who)
#        if who != 'jshelley':
#            pbs.logmsg(pbs.EVENT_DEBUG,'jshelley != %s'%who)
#            pbs.event().accept()

    pbs.logmsg(pbs.EVENT_DEBUG3, 'Event: %s' % pbs.event().type)

    # Add the site-packages paths to the sys path
    pbs_conf = pbs.pbs_conf
#    py_path = '/opt/pbs/default/python/lib'
    py_path = pbs_conf['PBS_EXEC'] + os.sep + 'python/lib'
    py_version = str(sys.version_info.major) + "." + \
        str(sys.version_info.minor)
    my_paths = [py_path + '/python' + py_version + '.zip',
                py_path + '/python' + py_version,
                py_path + '/python' + py_version + '/plat-linux2',
                py_path + '/python' + py_version + '/lib-tk',
                py_path + '/python' + py_version + '/lib-dynload',
                py_path + '/python' + py_version + '/site-packages']

    if sys.path.__contains__(py_path + '/python' + py_version) == False:
        for my_path in my_paths:
            if my_path not in sys.path:
                sys.path.append(my_path)

except ImportError:
    pass




class NodeHealthCheck:
    def __init__(self, **kwords):
        self.host = ''
        self.user = ''
        self.job_id = ''
        self.nhc_cfg = None

        # Set up the values for host and user
        pbs.logmsg(pbs.EVENT_DEBUG3, "get node name")
        self.host = pbs.get_local_nodename()

        # Read in the configurations file
        pbs_hook_cfg = pbs.hook_config_filename
        if pbs_hook_cfg is None:
            pbs.logmsg(pbs.EVENT_DEBUG3, "%s" % os.environ)
            pbs_hook_cfg = os.environ["PBS_HOOK_CONFIG_FILE"]
        pbs.logmsg(pbs.EVENT_DEBUG3, "read config file: %s" %
                   pbs.hook_config_filename)
        config_file = open(pbs.hook_config_filename).read()

        self.nhc_cfg = json.loads(config_file)
        pbs.logmsg(pbs.EVENT_DEBUG3, "config file: %s" % self.nhc_cfg)

        # Check to make sure the event has a user associated with it
        pbs.logmsg(pbs.EVENT_DEBUG3, 'Event: %s' % pbs.event().type)
        if pbs.event().type != pbs.EXECHOST_PERIODIC:
            self.user = repr(pbs.event().job.Job_Owner).split("@")[
                0].replace("'", "")
            self.job_id = pbs.event().job.id
        else:
            self.user = 'EXECHOST_PERIODIC'
            self.job_id = str(time.time())

        pbs.logmsg(pbs.EVENT_DEBUG3, 'Done initializing NodeHealthCheck')

    def ChkMountPoints(self):
        if not self.nhc_cfg['mounts']['check']:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Skipping mounts check")
            return True

        for mnt_pnt in self.nhc_cfg["mounts"]["mount_points"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "mount point: %s, %s" % (
                mnt_pnt, self.nhc_cfg["mounts"]["mount_points"][mnt_pnt]))
            try:
                # Added the line below to check to see if the real path is a
                # mount or not
                if not os.path.ismount(os.path.realpath(mnt_pnt)):
                    pbs.logmsg(
                        pbs.EVENT_DEBUG3, "Mount: %s\tAction: %s" %
                        (mnt_pnt, self.nhc_cfg["mounts"]["mount_points"][mnt_pnt]))
                    return [self.nhc_cfg["mounts"]["mount_points"][mnt_pnt],
                            '%s does not appear to be mounted' % mnt_pnt]
            except Exception as e:
                pbs.logmsg(pbs.EVENT_DEBUG, "Mount check error: %s" % e)
                return False
            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "mount point %s checked out" % (mnt_pnt))
        return True

    def ConvertToBytes(self, value):
        # Determine what units the user would like to use.
        if self.nhc_cfg["disk_space"]["units"].lower() == 'binary':
            units = {'kb': 1024, 'mb': 1048576,
                     'gb': 1073741824, 'tb': 1099511627776}
        elif self.nhc_cfg["disk_space"]["units"].lower() == 'decimal':
            units = {'kb': 1000, 'mb': 1000000,
                     'gb': 1000000000, 'tb': 1000000000000}
        else:
            pbs.logmsg(
                pbs.EVENT_DEBUG3,
                "I'm not sure how to handle units: %s\nSo I will default to binary" %
                (self.nhc_cfg["disk_space"]["units"]))
            units = {'kb': 1024, 'mb': 1048576,
                     'gb': 1073741824, 'tb': 1099511627776}

        value = value.lower()
        if value.find('%') != -1:
            pbs.logmsg(pbs.EVENT_DEBUG3, "found a % symbol")
            # Returned as a float so that I can distinguish between percentage
            # vs free space
            value = float(value.strip('%'))
            pbs.logmsg(pbs.EVENT_DEBUG3, "value: %s" % value)
        else:
            for key in list(units.keys()):
                if value.find(key) != -1:
                    try:
                        value = int(value[:-2].strip()) * units[key]
                    except Exception as e:
                        pbs.logmsg(
                            pbs.EVENT_DEBUG, "Error convertion value to int: %s\tkey: %s" %
                            (value, key))
                        return False
                    break
        return value

    def ChkDiskUsage(self):
        """
            Checks to see the disk usage. Returns True if the tests pass.
        """
        if not self.nhc_cfg["disk_space"]["check"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Skipping disk space check")
            return True

        for check_dir in self.nhc_cfg["disk_space"]["dirs"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Dir: %s\tSpace: %s" % (
                check_dir, self.nhc_cfg["disk_space"]["dirs"][check_dir]))
            # Get the requested space required for the check
            spaceVal = self.nhc_cfg["disk_space"]["dirs"][check_dir][0]
            if isinstance(spaceVal, int) or isinstance(spaceVal, (float)):
                spaceVal = int(spaceVal)
            else:
                spaceVal = self.ConvertToBytes(spaceVal)
                if not spaceVal:
                    return False

            try:
                st = os.statvfs(check_dir)
                free = (st.f_bavail * st.f_frsize)
                total = (st.f_blocks * st.f_frsize)
                used = (st.f_blocks - st.f_bfree) * st.f_frsize
            except OSError:
                line = "No file or directory: %s" % check_dir
                return [self.nhc_cfg["disk_space"]["dirs"][check_dir]
                        [1], "No file or directory: %s" % check_dir]
            except Exception as e:
                pbs.logmsg(pbs.EVENT_DEBUG, "Check Disk Usage Error: %s" % (e))
                return False

            gb_unit = 1073741824
            if self.nhc_cfg["disk_space"]['units'].lower() == 'decimal':
                gb_unit = 1000000000

            if isinstance(spaceVal, int):
                pbs.logmsg(
                    pbs.EVENT_DEBUG3, "Free: %0.2lfgb\tRequested: %0.2lfgb" %
                    (float(free) / float(gb_unit), float(spaceVal) / float(gb_unit)))
                if free < spaceVal:
                    return [
                        self.nhc_cfg["disk_space"]["dirs"][check_dir][1],
                        '%s failed disk space check. Free: %0.2lfgb\tRequested: %0.2lfgb' %
                        (check_dir,
                            float(free) /
                            float(gb_unit),
                            float(spaceVal) /
                            float(gb_unit))]

            elif isinstance(spaceVal, (float)):
                try:
                    pbs.logmsg(
                        pbs.EVENT_DEBUG3, "Free: %d\tTotal: %d\tUsed: %d\tUsed+Free: %d\tSpaceVal: %d" %
                        (free, total, used, used + free, int(spaceVal)))
                    percent = 100 - \
                        int((float(used) / float(used + free)) * 100)
                    pbs.logmsg(
                        pbs.EVENT_DEBUG3, "Free: %d%%\tRequested: %d%%" %
                        (percent, int(spaceVal)))

                    if percent < int(spaceVal):
                        return [
                            self.nhc_cfg["disk_space"]["dirs"][check_dir][1],
                            '%s failed disk space check. Free: %d%%\tRequested: %d%%' %
                            (check_dir,
                             percent,
                             int(spaceVal))]
                except Exception as e:
                    pbs.logmsg(pbs.EVENT_DEBUG, "Error: %s" % e)

        return True

    def ChkDirFilePermissions(self):
        """
            Returns True if the permissions match. The permissions from python are returned as string with the
            '0100600'. The last three digits are the file permissions for user,group, world
            Return action if the permissions don't match and NoFileOrDir if it can't find the file/dir
        """

        if not self.nhc_cfg["permissions"]["check"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Skipping permissions check")
            return True

        for file_dir in self.nhc_cfg["permissions"]["check_dirs_and_files"]:
            pbs.logmsg(
                pbs.EVENT_DEBUG3, "File/Dir: %s\t%s" %
                (file_dir, str(
                    self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0])))
            try:
                st = os.stat(file_dir)
                permissions = oct(st.st_mode)

                if permissions[-len(self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]):] != str(
                        self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]):
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "Required permissions: %s\tpermissions: %s" % (str(self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]),
                                                                              permissions[-len(self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]):]))
                    return [self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][1],
                            "File/Dir: %s\tRequired permissions: %s\tpermissions: %s" % (file_dir,
                                                                                         str(
                                                                                             self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]),
                                                                                         permissions[-len(self.nhc_cfg["permissions"]["check_dirs_and_files"][file_dir][0]):])]
            except OSError:
                return [self.nhc_cfg["permissions"]["check_dirs_and_files"]
                        [file_dir][1], "Can not find file/dir: %s" % file_dir]
            except BaseException:
                return False

        return True

    def ChkProcesses(self):
        if not self.nhc_cfg["processes"]["check"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Skipping processes check")
            return True

        # List all of the processes
        procs = {}
        if platform.uname()[0] == 'Linux':
            # out, err = subprocess.Popen(['ps', '-Af'], stdout=subprocess.PIPE).communicate()
            out, err = subprocess.Popen(
                ['top', '-bn1'], stdout=subprocess.PIPE).communicate()
            lines = out.split('\n')
            for line in lines[1:]:
                if line != "":
                    line = line.split()
                    # If ps -Af is used
                    # procs[os.path.split(line[-1].split()[0])[-1]] = line[0]

                    # If top -bn1 is used
                    procs[os.path.split(line[-1].split()[0])[-1]] = line[1]

        pbs.logmsg(pbs.EVENT_DEBUG3, "Processes: %s" % procs)

        # store procs that violate the checks
        chk_procs = {}
        chk_procs['running'] = []
        chk_procs['stopped'] = []
        chk_action = ""

        # Loop through processes
        for proc in self.nhc_cfg["processes"]["running"]:
            if proc not in list(procs.keys()):
                pbs.logmsg(
                    pbs.EVENT_DEBUG,
                    "Process: %s is not in the running process list but should be" %
                    proc)
                chk_procs['running'].append(proc)
                if chk_action == "":
                    chk_action = self.nhc_cfg['processes']['running'][proc][1]

        for proc in self.nhc_cfg['processes']['stopped']:
            if proc in list(procs.keys()):
                pbs.logmsg(
                    pbs.EVENT_DEBUG,
                    "Process: %s is in the stopped process list but was found to be running" %
                    proc)
                chk_procs['stopped'].append(proc)
                if chk_action == "":
                    chk_action = self.nhc_cfg['processes']['stopped'][proc][1]

        if len(chk_procs['running']) > 0 or len(chk_procs['stopped']) > 0:
            line = "running: %s\nstopped: %s" % (
                ",".join(chk_procs['running']), ",".join(chk_procs['stopped']))
            return [
                chk_action,
                "CheckProcesses: One or more processes were found which violates the check\n%s" %
                line]

        return True

    def ChkTouchFileAsUser(self):
        if not self.nhc_cfg["as_user_operations"]["check"]:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Skipping touch file as user check")
            return True

        for file_dir in self.nhc_cfg["as_user_operations"]["touch_files"]:
            file_dir_orig = file_dir
            # Check to see if this is a periodic hook. If so skip pbsuser file
            # touches
            if pbs.event(
            ).type == pbs.EXECHOST_PERIODIC and self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0] == 'pbsuser':
                pbs.logmsg(
                    pbs.EVENT_DEBUG3,
                    "Skipping this check dir: %s, since this is a periodic hook" %
                    file_dir)
                continue

#            pbs.logmsg(pbs.EVENT_DEBUG3,"Dir: %s\tUser: %s"%(file_dir,str(self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0])))
#            pbs.logmsg(pbs.EVENT_DEBUG3,"Job User: %s"%(self.user))

            try:
                new_file_dir = ''
                if file_dir.startswith('$') != -1:
                    # I need to flesh out how to best handle this.
                    # It will require looking through the job environment
                    # varilables
                    V = pbs.event().job.Variable_List
                    pbs.logmsg(pbs.EVENT_DEBUG3, "Type(V): %s" % (type(V)))
                    pbs.logmsg(pbs.EVENT_DEBUG3, "Job variable list: %s" % (V))
                    for var in V:
                        pbs.logmsg(pbs.EVENT_DEBUG3,
                                   "var: %s, file_dir: %s" % (var, file_dir))
                        pbs.logmsg(pbs.EVENT_DEBUG3, "V[var]: %s" % (V[var]))
                        if var.startswith(file_dir[1:]):
                            new_file_dir = V[var]
                            pbs.logmsg(pbs.EVENT_DEBUG3,
                                       "New dir: %s" % (file_dir))
                            break

                    pass

                # Check to see what user this test should be run as.
                # Options: pbsuser or pbsadmin
                status = ''
                if self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0] == 'pbsadmin':
                    pbs.logmsg(pbs.EVENT_DEBUG3,
                               "TouchFileAsAdmin: %s" % (file_dir))
                    if new_file_dir != '':
                        status = self.TouchFileAsUser(
                            'root', new_file_dir, file_dir_orig)
                    else:
                        status = self.TouchFileAsUser(
                            'root', file_dir, file_dir_orig)

                elif self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0] == 'pbsuser':
                    # Check to see if check is to be written to a specific user
                    # dir
                    pbs.logmsg(
                        pbs.EVENT_DEBUG3, "TouchFileAsUser: User: %s, Dir: %s" %
                        (self.user, file_dir))
                    if file_dir.find('<userid>') != -1:
                        file_dir = file_dir.replace('<userid>', self.user)

                    # Try to touch the file
                    if new_file_dir != '':
                        status = self.TouchFileAsUser(
                            self.user, new_file_dir, file_dir_orig)
                    else:
                        status = self.TouchFileAsUser(
                            self.user, file_dir, file_dir_orig)
                else:
                    pbs.logmsg(
                        pbs.EVENT_DEBUG,
                        "Unknown User: %s. Please specify either pbsadmin or pbsuser" %
                        (str(
                            self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0])))
                    return [
                        self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][1],
                        "Unknown User: %s. Please specify either pbsadmin or pbsuser" %
                        (str(
                            self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][0]))]

                if not status:
                    return status

            except OSError:
                return [self.nhc_cfg["as_user_operations"]["touch_files"][
                    file_dir_orig][1], 'Can not find file/dir: %s' % file_dir]
            except Exception as e:
                return [self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig]
                        [1], 'Encountered an error %s for file/dir: %s' % (e, file_dir)]
                # return False

        return True

    def TouchFileAsUser(self, user, file_dir, file_dir_orig):
        # file_dir_orig is needed to access the "Warn" or "Offline" information for the file/directory in question from the config file when variable substitution has taken place
        # Define the child var
        child = 0
        user_data = None

        pbs.logmsg(pbs.EVENT_DEBUG3, "User name: %s\tFile dir: %s" %
                   (user, file_dir))
        try:
            # user_data = getpwnam(self.user)
            user_data = getpwnam(user)

            if file_dir.find('<user_home>') != -1:
                file_dir = file_dir.replace('<user_home>', user_data[5])

            pbs.logmsg(pbs.EVENT_DEBUG3, "User name: %s\tDir to write to: %s" %
                       (user_data[4], file_dir))

# This is a special case where the user account does not exist on the
# node.  Offlining here is a good alternative to the job failing to run 20
# times and being held, but it can be changed if desired
        except KeyError:
            pbs.logmsg(pbs.EVENT_DEBUG, "Unable to find user: %s" % user)
            #
            return ['Offline', 'unable to find user: %s' % user]

        # Fork the process for touching a file as the user
        r, w = os.pipe()

        pid = os.fork()
        pbs.logmsg(pbs.EVENT_DEBUG3, "pid: %d" % pid)

        if pid:
            # We are the parent
            os.close(w)

            r = os.fdopen(r)  # turn r into a file object

            child = pid

            pbs.logmsg(pbs.EVENT_DEBUG3,
                       "Ready to read from the child process: %d" % pid)
            lines = r.read()

            pbs.logmsg(pbs.EVENT_DEBUG3, lines)
            # Wait for the child process to complete
            os.waitpid(child, 0)

            # Close the pipes
            r.close()

            # Check to see if the file was successfully touched
            if lines.find('Successfully touched file') == - \
                    1 or lines.find('Failed to remove file') != -1:
                pbs.logmsg(
                    pbs.EVENT_DEBUG3, "Failed to touch/remove file in %s as %s" %
                    (file_dir, user))
                return [
                    self.nhc_cfg["as_user_operations"]["touch_files"][file_dir_orig][1],
                    'Failed to touch/remove file for %s in %s' %
                    (user,
                     file_dir)]
            else:
                pbs.logmsg(
                    pbs.EVENT_DEBUG3, "Successfully touched and removed file for %s in %s" %
                    (user, file_dir))

        else:
            try:
                # Close the reading pipe
                os.close(r)

                # Turn w into a file object
                w = os.fdopen(w, 'w')

                # Switch to the user
                w.write("Ready to switch to user: %s\tuid: %s\n" %
                        (user, user_data[2]))
                os.setuid(user_data[2])

                # Change to the user home dir
                w.write("Changing dir to: %s\n" % (file_dir))
                if os.path.isdir(file_dir):
                    os.chdir(file_dir)

                    # Touch a file in the user's home directory
                    touch_file_name = "__user_%s_jobid_%s_host_%s_pbs_test.txt" % (
                        user, self.job_id, self.host)
                    w.write("Ready to touch file: %s\n" % (touch_file_name))
                    touchFileSuccess = self.TouchFile(touch_file_name)

                    if touchFileSuccess:
                        w.write("Successfully touched file\n")

                    try:
                        os.remove(touch_file_name)
                    except OSError:
                        w.write("Failed to remove file: %s" % touch_file_name)
                    except Exception as e:
                        w.write("Remove file exception: %s\n" % (e))
                else:
                    w.write("%s does not appear to be a directory" % file_dir)

            except Exception as e:
                w.write("Exception: %s\n" % (e))
            finally:
                # Close the pipe
                w.close()
                # Exit the child thread
                os._exit(0)

        return True

    def TouchFile(self, fname, times=None):
        try:
            open(fname, 'a').close()
            os.utime(fname, times)
            return True
        except IOError:
            pbs.logmsg(pbs.EVENT_DEBUG3, "Failed to touch file: %s" % (fname))
            return False

    def CheckNode(self):
        # Setup the fail counter
        failCnt = 0

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the mounts")
        if not c.ContinueChk(c.ChkMountPoints()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the disk usage")
        if not c.ContinueChk(c.ChkDiskUsage()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the file permissions")
        if not c.ContinueChk(c.ChkDirFilePermissions()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the processes")
        if not c.ContinueChk(c.ChkProcesses()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to touch file as user")
        if not c.ContinueChk(c.ChkTouchFileAsUser()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Exiting CheckNode function")

        return failCnt

    def CheckNodePeriodic(self):
        # Setup the fail counter
        failCnt = 0

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready perform check node periodic")

        # Run block of code with timeouts
        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the mounts")
        if not c.ContinueChk(c.ChkMountPoints()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the disk usage")
        if not c.ContinueChk(c.ChkDiskUsage()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Ready to check the file permissions")
        if not c.ContinueChk(c.ChkDirFilePermissions()):
            failCnt += 1

        pbs.logmsg(pbs.EVENT_DEBUG3, "Exiting CheckNode function")

        return failCnt

    def CheckOfflineNode(self):

        failCnt = self.CheckNodePeriodic()

        if failCnt == 0:
            localtime = time.asctime(time.localtime(time.time()))
            self.ContinueChk(
                ['Online', 'Passed the periodic test at %s' % localtime])
        return True

    def ContinueChk(self, status, comment=''):
        if isinstance(status, list):
            comment = str(status[1])
            status = status[0].lower()
        elif isinstance(status, bool) != True:
            status = status.lower()

        # Check to see how to handle the status
        pbs.logmsg(pbs.EVENT_DEBUG3, 'Status: %s\tComment: %s' %
                   (status, comment))
        if not status:
            return False
        elif status == 'warn':
            pbs.logmsg(pbs.EVENT_DEBUG, 'WARNING: %s' % comment)
            return True
        elif status == 'offline' or status == 'reboot':
            pbs.logmsg(pbs.EVENT_DEBUG, "Status: %s\tComment: %s" %
                       (status, comment))
            # Get the node, offline it,
            pbs.logmsg(pbs.EVENT_DEBUG, "Offline node: %s" % (self.host))
            myvnode = pbs.event().vnode_list[self.host]
            myvnode.state = pbs.ND_OFFLINE
            pbs.logmsg(
                pbs.EVENT_DEBUG,
                "Offline node type: %s, comment: %s" %
                (type(
                    str(comment)),
                    comment))
            myvnode.comment = "-attn_nhc: " + comment
            # pbs.logmsg(pbs.EVENT_DEBUG,"restart scheduler: %s %s"%(self.host,repr(myvnode.state)))
            # pbs.server().scheduler_restart_cycle()

            # Check to see if the node should be rebooted
            if status == 'reboot':
                pbs.logmsg(
                    pbs.EVENT_DEBUG, "Comment: %s\nOfflined node: %s and rebooted" %
                    (comment, self.host))
                pbs.event().job.rerun()
                pbs.reboot('reboot')

                # Run this command if the node is rebooted
                # The event().reject function ends the script
                pbs.logmsg(
                    pbs.EVENT_DEBUG,
                    "Comment: %s\nOfflined node: %s and restarted scheduling cycle" %
                    (comment,
                     self.host))
                pbs.event().reject("Offlined node, sent the reboot signal, and restarted scheduling cycle")

            # Reject the job
            pbs.event().reject("Offlined node and restarted scheduling cycle")

        elif status == 'online':
            pbs.logmsg(pbs.EVENT_DEBUG, "Onlined node: %s" % (self.host))
            mynodename = pbs.get_local_nodename()
            myvnode = pbs.event().vnode_list[mynodename]
            mynodename = pbs.get_local_nodename()
            pbs.logmsg(pbs.EVENT_DEBUG3, "got node: %s" % (mynodename))
            myvnode.state = pbs.ND_FREE
            pbs.logmsg(pbs.EVENT_DEBUG,
                       "Changed node state to ND_FREE: %s" % (mynodename))
            myvnode.comment = None
            pbs.logmsg(pbs.EVENT_DEBUG, "Onlined node: %s" % (mynodename))

        else:
            return True


if __name__ == "__builtin__":
    start = time.time()
    pbs.logmsg(pbs.EVENT_DEBUG3, "Starting the node health check")
    c = NodeHealthCheck()

    if pbs.event().type == pbs.EXECHOST_PERIODIC:
        vnode = pbs.server().vnode(c.host)
        if vnode.state == pbs.ND_OFFLINE and vnode.comment.startswith(
                '-attn_nhc:'):
            # Still need to flesh out CheckOfflineNode function
            c.CheckOfflineNode()
        else:
            c.CheckNodePeriodic()
    else:
        c.CheckNode()

    pbs.logmsg(pbs.EVENT_DEBUG3, "Finished check disk hook: %0.5lf (s)" %
               (time.time() - start))
