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


def reportsockets_win(f):
    temp = f.read().split(',')
    for item in temp:
        if item.find('sockets:') != -1:
            sockets = int(item[8:])  # len('sockets:') = 8
        if item.find('gpus:') != -1:
            gpus = int(item[5:])  # len('gpus:') = 5
        if item.find('mics:') != -1:
            coproc = int(item[5:])  # len('mics:') = 5
    return (sockets, gpus, coproc)


def latest_hwloc(hwlocVersion):
    hwlocVersion = hwlocVersion.split('.')
    major = int(hwlocVersion[0])
    minor = int(hwlocVersion[1]) if len(hwlocVersion) > 1 else 0
    if ((major == 1) and (minor >= 11)) or (major > 1):
        return 1
    return 0


try:
    import xml.parsers.expat
    from xml.parsers.expat import ExpatError

    def reportsockets(dirs, files, options):
        """
        Look for and report the number of "Package" elements which stands
        for Sockets in a string produced by hwloc_topology_export_xmlbuffer().

        This version of reportsockets uses expat to parse the XML.
        If the PBS version of Python does not allow import of expat,
        we go on to try a simpler approach (below).
        """

        def socketXMLstart(name, attrs):
            if name == "BasilResponse":
                socketXMLstart.CrayVersion = attrs.get("protocol")
                return
            if (name == "info" and attrs.get("name") == "hwlocVersion"):
                socketXMLstart.hwloclatest = latest_hwloc(attrs.get("value"))
                return
            if socketXMLstart.CrayVersion != "0.0":
                if float(socketXMLstart.CrayVersion) <= 1.2 and name == "Node":
                    socketXMLstart.nsockets += 2
                elif name == "Socket":
                    socketXMLstart.nsockets += 1
                if name == "Accelerator" and attrs.get("type") == "GPU":
                    socketXMLstart.ngpus += 1
            else:
                if (name == "object" and ((socketXMLstart.hwloclatest == 1 and
                    attrs.get("type") == "Package") or
                    (socketXMLstart.hwloclatest == 0 and attrs.get("type") ==
                        "Socket"))):
                    socketXMLstart.nsockets += 1
                if (name == "object" and attrs.get("type") == "OSDev" and
                    attrs.get("osdev_type") == "1" and
                        attrs.get("name").startswith("card")):
                    socketXMLstart.ngpus += 1
                if (name == "object" and attrs.get("type") == "OSDev" and
                    attrs.get("osdev_type") == "5" and
                        attrs.get("name").startswith("mic")):
                    socketXMLstart.ncoproc += 1

        if files is None:
            compute_socket_nodelist = True
            try:
                files = os.listdir(dirs)
            except (IOError, OSError) as err:
                (e, strerror) = err.args
                print "%s:  %s (%s)" % (dirs, strerror, e)
                return
        else:
            compute_socket_nodelist = False
        try:
            maxwidth = max(map(len, files))
        except StandardError, e:
            print 'max/map failed: %s' % e
            return
        for name in files:
            pathname = os.sep.join((dirs, name))
            socketXMLstart.nsockets = 0
            socketXMLstart.ngpus = 0
            socketXMLstart.ncoproc = 0
            socketXMLstart.hwloclatest = 0
            socketXMLstart.CrayVersion = "0.0"
            try:
                with open(pathname, "r") as f:
                    if platform.system() == "Windows":
                        (socketXMLstart.nsockets, socketXMLstart.ngpus,
                            socketXMLstart.ncoproc) = reportsockets_win(f)
                    else:
                        try:
                            socketXMLstart.isCray = False
                            p = xml.parsers.expat.ParserCreate()
                            p.StartElementHandler = socketXMLstart
                            p.ParseFile(f)
                        except ExpatError as e:
                            print "%s:  parsing error at line %d, column %d" \
                                % (name, e.lineno, e.offset)

                    if options.sockets:
                        print "%-*s%d" % (maxwidth + 1, name,
                                          socketXMLstart.nsockets)
                    else:
                        total = socketXMLstart.nsockets + \
                            socketXMLstart.ngpus + socketXMLstart.ncoproc
                        print "%-*s%d" % (maxwidth + 1, name,
                                          int(math.ceil(total / 4.0)))
            except IOError as err:
                (e, strerror) = err.args
                if e == errno.ENOENT:
                    if not compute_socket_nodelist:
                        print "no socket information available for node %s" \
                            % name
                    continue
                else:
                    print "%s:  %s (%s)" % (pathname, strerror, e)
                    raise

except ImportError:
    def reportsockets(dirs, files, options):
        """
        Look for and report the number of "Package" elements in a string
        produced by hwloc_topology_export_xmlbuffer().

        This is a backup version of reportsockets which we use when an
        import of the xml.parsers.expat module fails.  In this version,
        we simply count occurrences of "Package" objects.
        """
        socketpattern = r'<\s*object\s+type="Socket"'
        packagepattern = r'<\s*object\s+type="Package"'
        gpupattern = r'<\s*object\s+type="OSDev"\s+name="card\d+"\s+' \
            'osdev_type="1"'
        micpattern = r'<\s*object\s+type="OSDev"\s+name="mic\d+"\s+' \
            'osdev_type="5"'
        craypattern = r'<\s*BasilResponse\s+'
        craynodepattern = r'<\s*Node\s+node_id='
        craysocketpattern = r'<\s*Socket\s+ordinal='
        craygpupattern = r'<\s*Accelerator\s+.*type="GPU"'
        hwloclatestpattern = r'<\s*info\s+name="hwlocVersion"\s+'
        if files is None:
            compute_socket_nodelist = True
            try:
                files = os.listdir(dirs)
            except (IOError, OSError) as err:
                (e, strerror) = err.args
                print "%s:  %s (%s)" % (dirs, strerror, e)
                return
        else:
            compute_socket_nodelist = False
        try:
            maxwidth = max(map(len, files))
        except StandardError, e:
            print 'max/map failed: %s' % e
            return
        for name in files:
            pathname = os.sep.join((dirs, name))
            try:
                with open(pathname, "r") as f:
                    (nsockets, ngpus, ncoproc, CrayVersion, hwloclatest) = \
                        (0, 0, 0, "0.0", 0)
                    if platform.system() == "Windows":
                        (nsockets, ngpus, ncoproc) = reportsockets_win(f)
                    else:
                        for line in f:
                            if hwloclatest == 1:
                                nsockets += 1 if re.search(packagepattern,
                                                           line) else 0
                            else:
                                nsockets += 1 if re.search(socketpattern,
                                                           line) else 0
                            ngpus += 1 if re.search(gpupattern, line) else 0
                            ncoproc += 1 if re.search(micpattern, line) else 0
                            if re.search(craypattern, line):
                                start_index = line.find('protocol="') + \
                                    len('protocol="')
                                CrayVersion = line[start_index:
                                                   line.find('"', start_index)]
                                continue
                            if re.search(hwloclatestpattern, line):
                                hwlocVer = line[line.find('value="') +
                                                len('value="'):
                                                line.rfind('"/>')]
                                hwloclatest = latest_hwloc(hwlocVer)
                            if CrayVersion != "0.0":
                                if float(CrayVersion) <= 1.2 and re.search(
                                        craynodepattern, line):
                                    nsockets += 2
                                elif re.search(craysocketpattern, line):
                                    nsockets += 1
                                if re.search(craygpupattern, line):
                                    ngpus += 1
                    if options.sockets:
                        print "%-*s%d" % (maxwidth + 1, name, nsockets)
                    else:
                        total = nsockets + ngpus + ncoproc
                        print "%-*s%d" % (maxwidth + 1, name,
                                          int(math.ceil(total / 4.0)))
            except IOError as err:
                (e, strerror) = err.args
                if e == errno.ENOENT:
                    if not compute_socket_nodelist:
                        print "no socket information available for node %s" \
                            % name
                    continue
                else:
                    print "%s:  %s (%s)" % (pathname, strerror, e)
                    raise

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
        print "PBS_HOME must be present in the caller's environment"
        sys.exit(1)
    if not (options.sockets or options.license):
        sys.exit(1)
    if options.allnodes:
        reportsockets(topology_dir, None, options)
    else:
        reportsockets(topology_dir, progargs, options)
