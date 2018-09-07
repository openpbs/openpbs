# coding: utf-8

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

import errno
from optparse import OptionParser
import os
import re
import sys
import math
import platform


class Inventory(object):
    """
    This class is used to parse the inventory details
    and hold the device information
    """

    def reset(self):
        self.nsockets = 0
        self.nnodes = 0
        self.hwloclatest = 0
        self.CrayVersion = "0.0"
        self.ndevices = 0
        self.gpudevices = 0

    def __init__(self):
        self.reset()

    def reportsockets_win(self, topo_file):
        """
        counting devices by parsing topo_file
        """
        temp = topo_file.read().split(',')
        for item in temp:
            if item.find('sockets:') != -1:
                self.nsockets = int(item[8:])  # len('sockets:') = 8
                self.ndevices += int(item[8:])
            if item.find('gpus:') != -1:
                self.ndevices += int(item[5:])  # len('gpus:') = 5
            if item.find('mics:') != -1:
                self.ndevices += int(item[5:])  # len('mics:') = 5

    def latest_hwloc(self, hwlocVersion):
        """
        socket tag is different on versions above 1.11
        turning hwloclatest flag on if the version is above 1.11
        """
        hwlocVersion = hwlocVersion.split('.')
        major = int(hwlocVersion[0])
        minor = int(hwlocVersion[1]) if len(hwlocVersion) > 1 else 0
        if ((major == 1) and (minor >= 11)) or (major > 1):
            self.hwloclatest = 1

    def calculate(self):
        """
        Returns the number of licenses required based on specific formula
        """
        self.ndevices += self.gpudevices
        return(int(math.ceil(self.ndevices / 4.0)))

    def reportsockets(self, dirs, files, options):
        """
        Look for and report the number of socket/node licenses
        required by the cluster. Uses expat to parse the XML.
        dirs - directory to look for topology files.
        files - files for which inventory needs to be parsed
        options - node / socket.
        """

        if files is None:
            compute_socket_nodelist = True
            try:
                files = os.listdir(dirs)
                if not files:
                    return
            except (IOError, OSError) as err:
                (e, strerror) = err.args
                print("%s:  %s (%s)" % (dirs, strerror, e))
                return
        else:
            compute_socket_nodelist = False
        try:
            maxwidth = max(list(map(len, files)))
        except Exception as e:
            print('max/map failed: %s' % e)
            return

        try:
            import xml.parsers.expat
            from xml.parsers.expat import ExpatError
            ExpatParser = True
        except ImportError:
            ExpatParser = False

        for name in files:
            pathname = os.sep.join((dirs, name))
            self.reset()
            try:
                with open(pathname, "rb") as topo_file:

                    if platform.system() == "Windows":
                        self.reportsockets_win(topo_file)
                    elif ExpatParser:
                        try:
                            p = xml.parsers.expat.ParserCreate()
                            p.StartElementHandler = socketXMLstart
                            p.ParseFile(topo_file)
                        except ExpatError as e:
                            print("%s:  parsing error at line %d, column %d"
                                  % (name, e.lineno, e.offset))
                    else:
                        self.countsockets(topo_file)

                    if options.sockets:
                        print("%-*s%d" % (maxwidth + 1, name, self.nsockets))
                    else:
                        self.nnodes += self.calculate()
                        print("%-*s%d" % (maxwidth + 1, name,
                              inventory.nnodes))

            except IOError as err:
                (e, strerror) = err.args
                if e == errno.ENOENT:
                    if not compute_socket_nodelist:
                        print("no socket information available for node %s"
                              % name)
                    continue
                else:
                    print("%s:  %s (%s)" % (pathname, strerror, e))
                    raise

    def countsockets(self, topo_file):
        """
        Used when an import of the xml.parsers.expat module fails.
        This version makes use of regex expressions.
        """
        socketpattern = r'<\s*object\s+type="Socket"'
        packagepattern = r'<\s*object\s+type="Package"'
        gpupattern = r'<\s*object\s+type="OSDev"\s+name="card\d+"\s+' \
            'osdev_type="1"'
        nongpupattern = r'<\s*object\s+type="OSDev"\s+name="controlD\d+"\s+' \
            'osdev_type="1"'
        micpattern = r'<\s*object\s+type="OSDev"\s+name="mic\d+"\s+' \
            'osdev_type="5"'
        craypattern = r'<\s*BasilResponse\s+'
        craynodepattern = r'<\s*Node\s+node_id='
        craysocketpattern = r'<\s*Socket\s+ordinal='
        craygpupattern = r'<\s*Accelerator\s+.*type="GPU"'
        hwloclatestpattern = r'<\s*info\s+name="hwlocVersion"\s+'

        for line in topo_file:
            if re.search(craypattern, line):
                start_index = line.find('protocol="') + len('protocol="')
                self.CrayVersion = line[start_index:
                                        line.find('"', start_index)]
                continue
            if re.search(hwloclatestpattern, line):
                hwlocVer = line[line.find('value="') + len('value="'):
                                line.rfind('"/>')]
                self.latest_hwloc(hwlocVer)
                continue

            if self.CrayVersion != "0.0":
                if re.search(craynodepattern, line):
                    self.nnodes += self.calculate()
                    self.ndevices = 0
                    if float(self.CrayVersion) <= 1.2:
                        self.nsockets += 2
                        self.ndevices += 2
                elif re.search(craysocketpattern, line):
                    self.nsockets += 1
                    self.ndevices += 1
                if re.search(craygpupattern, line):
                    self.ndevices += 1
            else:
                if ((self.hwloclatest and re.search(packagepattern, line)) or
                        (not self.hwloclatest and re.search(socketpattern,
                                                            line))):
                    self.nsockets += 1
                    self.ndevices += 1
                self.gpudevices += 1 if re.search(gpupattern, line) else 0
                if re.search(nongpupattern, line):
                    if (self.gpudevices > 0):
                        self.gpudevices -= 1
                self.ndevices += 1 if re.search(micpattern, line) else 0


def socketXMLstart(name, attrs):
    """
    StartElementHandler for expat parser
    """
    global inventory

    if name == "BasilResponse":
        inventory.CrayVersion = attrs.get("protocol")
        return
    if (name == "info" and attrs.get("name") == "hwlocVersion"):
        inventory.latest_hwloc(attrs.get("value"))
        return
    if inventory.CrayVersion != "0.0":
        if name == "Node":
            inventory.nnodes += inventory.calculate()
            inventory.ndevices = 0
            if float(inventory.CrayVersion) <= 1.2:
                inventory.nsockets += 2
                inventory.ndevices += 2
        elif name == "Socket":
            inventory.nsockets += 1
            inventory.ndevices += 1
        if name == "Accelerator" and attrs.get("type") == "GPU":
            inventory.ndevices += 1
    else:
        if (name == "object" and ((inventory.hwloclatest == 1 and
            attrs.get("type") == "Package") or
            (inventory.hwloclatest == 0 and attrs.get("type") ==
                "Socket"))):
            inventory.nsockets += 1
            inventory.ndevices += 1
        if (name == "object" and attrs.get("type") == "OSDev" and
            attrs.get("osdev_type") == "1" and
                attrs.get("name").startswith("card")):
            inventory.gpudevices += 1
        if (name == "object" and attrs.get("type") == "OSDev" and
            attrs.get("osdev_type") == "1" and
                attrs.get("name").startswith("controlD")):
            if (inventory.gpudevices > 0):
                inventory.gpudevices -= 1
        if (name == "object" and attrs.get("type") == "OSDev" and
            attrs.get("osdev_type") == "5" and
                attrs.get("name").startswith("mic")):
            inventory.ndevices += 1


if __name__ == "__main__":
    usagestr = "usage:  %prog [ -a -s ]\n\t%prog -s node1 [ node2 ... ]"
    parser = OptionParser(usage=usagestr)
    parser.add_option("-a", "--all", action="store_true", dest="allnodes",
                      help="report on all nodes")
    parser.add_option("-s", "--sockets", action="store_true", dest="sockets",
                      help="report node socket count")
    parser.add_option("-l", "--license", action="store_true", dest="license",
                      help="report license count")
    (options, progargs) = parser.parse_args()

    try:
        topology_dir = os.sep.join((os.environ["PBS_HOME"], "server_priv",
                                    "topology"))
    except KeyError:
        print("PBS_HOME must be present in the caller's environment")
        sys.exit(1)
    if not (options.sockets or options.license):
        sys.exit(1)
    inventory = Inventory()
    if options.allnodes:
        inventory.reportsockets(topology_dir, None, options)
    else:
        inventory.reportsockets(topology_dir, progargs, options)
