# coding: utf-8
#!/usr/bin/env python3
"""
/*
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

 *
 */
"""
__doc__ = """
This script is not intended to be run by users or Administrators.
It is run by the Cray RUR system as an "output plugin".
"""

import os
import sys
rur_path = os.path.join(os.path.sep, 'opt', 'cray', 'rur', 'default', 'bin')
if rur_path not in sys.path:
    sys.path.append(rur_path)
try:
    from rur_plugins import rur_output_args, get_plugin_name, rur_errorlog
except Exception:
    sys.stderr.write("Failed to import from rur_plugins\n")
    raise ImportError


def outname(jobid):
    # Create the pathname to write the RUR data for PBS.
    # By default it will be "/var/spool/pbs/spool/<jobid>.rur"
    home = "PBS_HOME"
    dirname = "/var/spool/pbs"
    if home in os.environ:
        dirname = os.environ[home]
    else:
        conf = 'PBS_CONF_FILE'
        if conf in os.environ:
            confile = os.environ[conf]
        else:
            confile = '/etc/pbs.conf'
        with open(confile, "r") as fp:
            for line in fp:
                line = line.strip()
                if line is "":
                    continue
                var, _, val = line.partition('=')
                if var == home:
                    dirname = val
                    break
    dirname = os.path.join(dirname, "spool")
    if os.path.isdir(dirname):
        return os.path.join(dirname, "%s.rur" % jobid)
    else:
        raise IOError("not a directory")


def main():
    # An RUR output plugin that will write data specific to a PBS job
    # to a well known path that PBS hooks can access.  The format of
    # the file will be:
    # pluginName : apid : pluginOutput
    #
    # See the Cray document: "Managing System Software for the Cray
    # Linux Environment" section 12.7 "RUR Plugins" for more
    # information on the RUR plugin interface.
    # http://docs.cray.com/books/S-2393-5101/S-2393-5101.pdf

    try:
        rur_output = list()
        rur_output = rur_output_args(sys.argv[1:], True)
        apid = rur_output[0]
        jobid = rur_output[1]
        inputfilelist = rur_output[4]
    except Exception as e:
        rur_errorlog("RUR PBS output plugin rur_output_args error '%s'" %
                     str(e))
        exit(1)

    # If an aprun runs within a PBS job, the jobid will have the PBS
    # jobid set.  It will have the short servername like "77.sdb".
    # If an aprun is run interactively, the jobid will be "0".
    if jobid == "0":		# not from a PBS job
        exit(0)

    try:
        output = outname(jobid)
        outfile = open(output, "a")
    except Exception:
        rur_errorlog("RUR PBS output plugin cannot access output file %s" %
                     output)
        exit(1)

    # copy input to job specific output file
    for inputfile in inputfilelist:
        try:
            plugin = get_plugin_name(inputfile)
            plugin = plugin.split()[1]		# keep just the plugin name
            with open(inputfile, "r") as infile:
                for line in infile:
                    outfile.write("%s : %s : %s" % (plugin, apid, line))
        except Exception:
            pass
    outfile.close()


if __name__ == "__main__":
    main()
