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

import os
import sys
import time
import logging
import tempfile
from stat import S_IWOTH
from urllib.parse import urljoin
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_cliutils import CliUtils

try:
    from BeautifulSoup import BeautifulSoup
except:
    pass


class LcovUtils(object):
    """
    Coverage Utils

    :param cov_bin: Coverage binary
    :param html_bin: Coverage html binary
    :param cov_out: Coverage output directory
    :type cov_out: str or None
    :param data_dir: Coverage data directory
    :type data_dir: str or None
    :param html_nosrc: HTML reports without PBS source
    :type stml_nosrc: bool
    :param html_baseurl: HTML base url
    :type html_baseurl: str or None
    """
    du = DshUtils()
    logger = logging.getLogger(__name__)

    def __init__(self, cov_bin=None, html_bin=None, cov_out=None,
                 data_dir=None, html_nosrc=False, html_baseurl=None):
        self.set_coverage_data_dir(data_dir)
        self.set_coverage_bin(cov_bin)
        self.set_genhtml_bin(html_bin)
        self.set_coverage_out(cov_out)
        self.set_html_nosource(html_nosrc)
        self.set_html_baseurl(html_baseurl)
        self.coverage_traces = []

    def set_html_baseurl(self, baseurl):
        """
        Set ``HTML`` base url
        """
        self.logger.info('coverage baseurl set to ' + str(baseurl))
        self.html_baseurl = baseurl

    def set_html_nosource(self, nosource=False):
        """
        Set HTML nosource parameter to False.
        """
        self.logger.info('coverage no-source set to ' + str(nosource))
        self.html_nosrc = nosource

    def set_coverage_bin(self, cov_bin=None):
        """
        Set the coverage binary

        :param cov_binary: Coverage bin to set
        """
        if cov_bin is None:
            cov_bin = 'lcov'
        rv = CliUtils.check_bin(cov_bin)
        if not rv:
            self.logger.error('None lcov_bin defined!')
            sys.exit(1)
        else:
            self.logger.info('coverage utility set to ' + cov_bin)
            self.cov_bin = cov_bin
        return rv

    def set_genhtml_bin(self, html_bin=None):
        """
        Set HTML generation utility.

        :param html_bin: HTML bin to set
        """
        if html_bin is None:
            html_bin = 'genhtml'
        rv = CliUtils.check_bin(html_bin)
        if not rv:
            self.logger.error('%s tool not found' % (html_bin))
            self.html_bin = None
        else:
            self.logger.info('HTML generation utility set to ' + html_bin)
            self.html_bin = html_bin
        return rv

    def set_coverage_out(self, cov_out=None):
        """
        Set the coverage output directory

        :param cov_out: Coverage output directory path.
        """
        if cov_out is None:
            d = 'pbscov-' + time.strftime('%Y%m%d_%H%M%S', time.localtime())
            cov_out = os.path.join(tempfile.gettempdir(), d)
        if not os.path.isdir(cov_out):
            os.mkdir(cov_out)
        self.logger.info('coverage output directory set to ' + cov_out)
        self.cov_out = cov_out

    def set_coverage_data_dir(self, data=None):
        """
        Set the coverage data directory

        :param data: Data directory path
        :returns: True if file name ends with .gcno else return False
        """
        self.data_dir = data
        if self.data_dir is not None:
            walker = os.walk(self.data_dir)
            for _, _, files in walker:
                for f in files:
                    if f.endswith('.gcno'):
                        return True
        return False

    def add_trace(self, trace):
        """
        Add coverage trace

        :param trace: Coverage trace
        """
        if trace not in self.coverage_traces:
            self.logger.info('Adding coverage trace: %s' % (trace))
            self.coverage_traces.append(trace)

    def create_coverage_data_files(self, path):
        """
        Create .gcda counterpart files for every .gcno file and give it
        read/write permissions
        """
        walker = os.walk(path)
        for root, _, files in walker:
            for f in files:
                if f.endswith('.gcda'):
                    pf = os.path.join(root, f)
                    s = os.stat(pf)
                    if (s.st_mode & S_IWOTH) == 0:
                        self.du.run_cmd(cmd=['chmod', '666', pf],
                                        level=logging.DEBUG, sudo=True)
                elif f.endswith('.gcno'):
                    nf = f.replace('.gcno', '.gcda')
                    pf = os.path.join(root, nf)
                    if not os.path.isfile(pf):
                        self.du.run_cmd(cmd=['touch', pf],
                                        level=logging.DEBUG, sudo=True)
                        self.du.run_cmd(cmd=['chmod', '666', pf],
                                        level=logging.DEBUG, sudo=True)

    def initialize_coverage(self, out=None, name=None):
        """
        Initialize coverage

        :param out: Output path
        :type out: str or None
        :param name: name of the command
        :type name: str or None
        """
        if self.data_dir is not None:
            if out is None:
                out = os.path.join(self.cov_out, 'baseline.info')
            self.logger.info('Initializing coverage data to ' + out)
            self.create_coverage_data_files(self.data_dir)
            cmd = [self.cov_bin]
            if name is not None:
                cmd += ['-t', name]
            cmd += ['-i', '-d', self.data_dir, '-c', '-o', out]
            self.du.run_cmd(cmd=cmd, logerr=False)
            self.add_trace(out)

    def capture_coverage(self, out=None, name=None):
        """
        Capture the coverage parameters
        """
        if self.data_dir is not None:
            if out is None:
                out = os.path.join(self.cov_out, 'tests.info')
            self.logger.info('Capturing coverage data to ' + out)
            cmd = [self.cov_bin]
            if name is not None:
                cmd += ['-t', name]
            cmd += ['-c', '-d', self.data_dir, '-o', out]
            self.du.run_cmd(cmd=cmd, logerr=False)
            self.add_trace(out)

    def zero_coverage(self):
        """
        Zero the data counters. Note that a process would need to be restarted
        in order to collect data again, running ``--initialize`` will not get
        populate the data counters
        """
        if self.data_dir is not None:
            self.logger.info('Resetting coverage data')
            cmd = [self.cov_bin, '-z', '-d', self.data_dir]
            self.du.run_cmd(cmd=cmd, logerr=False)

    def merge_coverage_traces(self, out=None, name=None, exclude=None):
        """
        Merge the coverage traces
        """
        if not self.coverage_traces:
            return
        if out is None:
            out = os.path.join(self.cov_out, 'total.info')
        self.logger.info('Merging coverage traces to ' + out)
        if exclude is not None:
            tmpout = out + '.tmp'
        else:
            tmpout = out
        cmd = [self.cov_bin]
        if name is not None:
            cmd += ['-t', name]
        for t in self.coverage_traces:
            cmd += ['-a', t]
        cmd += ['-o', tmpout]
        self.du.run_cmd(cmd=cmd, logerr=False)
        if exclude is not None:
            cmd = [self.cov_bin]
            if name is not None:
                cmd += ['-t', name]
            cmd += ['-r', tmpout] + exclude + ['-o', out]
            self.du.run_cmd(cmd=cmd, logerr=False)
            self.du.rm(path=tmpout, logerr=False)

    def generate_html(self, out=None, html_out=None, html_nosrc=False):
        """
        Generate the ``HTML`` report
        """
        if self.html_bin is None:
            self.logger.warn('No genhtml bin is defined')
            return
        if out is None:
            out = os.path.join(self.cov_out, 'total.info')
        if not os.path.isfile(out):
            return
        if html_out is None:
            html_out = os.path.join(self.cov_out, 'html')
        if (self.html_nosrc or html_nosrc):
            self.logger.info('Generating HTML reports (without PBS source)'
                             ' from  coverage data')
            cmd = [self.html_bin, '--no-source', out]
            cmd += ['-o', html_out]
            self.du.run_cmd(cmd=cmd, logerr=False)
        else:
            self.logger.info('Generating HTML reports (with PBS Source) from'
                             ' coverage data')
            cmd = [self.html_bin, out, '-o', html_out]
            self.du.run_cmd(cmd=cmd, logerr=False)

    def change_baseurl(self, html_out=None, html_baseurl=None):
        """
        Change the ``HTML`` base url
        """
        if html_baseurl is None:
            html_baseurl = self.html_baseurl
        if html_baseurl is None:
            return
        if html_out is None:
            html_out = os.path.join(self.cov_out, 'html')
        if not os.path.isdir(html_out):
            return
        html_out_bu = os.path.join(os.path.dirname(html_out),
                                   os.path.basename(html_out) + '_baseurl')
        if html_baseurl[-1] != '/':
            html_baseurl += '/'
        self.logger.info('Changing baseurl to %s' % (html_baseurl))
        self.du.run_copy(src=html_out, dest=html_out_bu, recursive=True)
        for root, _, files in os.walk(html_out_bu):
            newroot = root.split(html_out_bu)[1]
            if ((len(newroot) > 0) and (newroot[0] == '/')):
                newroot = newroot[1:]
            newroot = urljoin(html_baseurl, newroot)
            if newroot[-1] != '/':
                newroot += '/'
            print(root, newroot)
            for f in files:
                if not f.endswith('.html'):
                    continue
                f = os.path.join(root, f)
                fd = open(f, 'r')
                line = ''.join(fd.readlines())
                fd.close()
                tree = BeautifulSoup(line)
                for a in tree.findAll('a'):
                    href = a['href']
                    if href.startswith('http://'):
                        continue
                    a['href'] = urljoin(newroot, href)
                for img in tree.findAll('img'):
                    img['src'] = urljoin(newroot, img['src'])
                for css in tree.findAll('link', rel='stylesheet'):
                    css['href'] = urljoin(newroot, css['href'])
                fd = open(f, 'w+')
                fd.write(str(tree))
                fd.close()

    def summarize_coverage(self, out=None):
        """
        Summarize the coverage output
        """
        if out is None:
            out = os.path.join(self.cov_out, 'total.info')
        if not os.path.isfile(out):
            return ''
        self.logger.info('Summarizing coverage data from ' + out)
        cmd = [self.cov_bin, '--summary', out]
        return self.du.run_cmd(cmd=cmd, logerr=False)['err']
