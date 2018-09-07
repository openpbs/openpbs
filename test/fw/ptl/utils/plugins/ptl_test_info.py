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

import sys
import logging
from nose.plugins.base import Plugin
from ptl.utils.pbs_testsuite import PBSTestSuite
from ptl.utils.plugins.ptl_test_tags import TAGKEY
from ptl.utils.pbs_testsuite import REQUIREMENTS_KEY
from ptl.utils.pbs_testsuite import default_requirements
from copy import deepcopy

log = logging.getLogger('nose.plugins.PTLTestInfo')


def get_effective_reqs(ts_reqs=None, tc_reqs=None):
    """
    get effective requirements at test case
    """
    tc_effective_reqs = {}
    if (tc_reqs is None and ts_reqs is None):
        tc_effective_reqs = deepcopy(default_requirements)
    else:
        tc_effective_reqs = deepcopy(default_requirements)
        tc_effective_reqs.update(ts_reqs)
        tc_effective_reqs.update(tc_reqs)
    return tc_effective_reqs


class FakeRunner(object):

    def __init__(self, config):
        self.config = config

    def run(self, test):
        self.config.plugins.finalize(None)
        sys.exit(0)


class PTLTestInfo(Plugin):

    """
    Load test cases from given parameter
    """
    name = 'PTLTestInfo'
    score = sys.maxsize - 2
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.list_test = None
        self.showinfo = None
        self.verbose = None
        self.gen_ts_tree = None
        self.suites = []
        self._tree = {}
        self.total_suite = 0
        self.total_case = 0
        self.__ts_tree = {}
        self.__tags_tree = {'NoTags': {}}

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, suites, list_test, showinfo, verbose, gen_ts_tree):
        """
        Set the data required for running the tests

        :param suites: Test suites to run
        :param list_test: List of test to run
        :param gen_ts_tree: Generate test suite tree
        """
        self.suites = suites.split(',')
        self.list_test = list_test
        self.showinfo = showinfo
        self.verbose = verbose
        self.gen_ts_tree = gen_ts_tree

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options

        :param options: Options to configure plugin and system
        """
        self.config = config
        self.enabled = True

    def prepareTestRunner(self, runner):
        return FakeRunner(config=self.config)

    def wantClass(self, cls):
        """
        Is the class wanted?
        """
        self._tree.setdefault(cls.__name__, cls)
        if len(cls.__bases__) > 0:
            self.wantClass(cls.__bases__[0])

    def _get_hierarchy(self, cls, level=0):
        delim = '    ' * level
        msg = [delim + cls.__name__]
        self.logger.info(dir(cls))
        subclses = cls.__subclasses__()
        for subcls in subclses:
            msg.extend(self._get_hierarchy(subcls, level + 1))
        return msg

    def _print_suite_info(self, suite):
        w = sys.stdout
        self.total_suite += 1
        if self.list_test:
            w.write('\n\n')
        w.write('Test Suite: %s\n\n' % suite.__name__)
        w.write('    file: %s.py\n\n' % suite.__module__.replace('.', '/'))
        w.write('    module: %s\n\n' % suite.__module__)
        tags = getattr(suite, TAGKEY, None)
        if tags is not None:
            w.write('    Tags: %s\n\n' % (', '.join(tags)))
        w.write('    Suite Doc: \n')
        for l in str(suite.__doc__).split('\n'):
            w.write('    %s\n' % l)
        dcl = suite.__dict__
        cases = []
        for k in dcl.keys():
            if k.startswith('test_'):
                k = getattr(suite, k)
                try:
                    k.__name__
                except BaseException:
                    # not a test case, ignore
                    continue
                self.total_case += 1
                cases.append('\t%s\n' % (k.__name__))
                if self.verbose:
                    tags = getattr(k, TAGKEY, None)
                    if tags is not None:
                        cases.append('\n\t    Tags: %s\n\n' %
                                     (', '.join(tags)))
                    doc = k.__doc__
                    if doc is not None:
                        cases.append('\t    Test Case Doc: \n')
                        for l in str(doc).split('\n'):
                            cases.append('\t%s\n' % (l))
        if len(cases) > 0:
            w.write('    Test Cases: \n')
            w.writelines(cases)
        if self.list_test or self.showinfo:
            lines = self._get_hierarchy(suite, 1)[1:]
            if len(lines) > 0:
                w.write('\n    Test suite hierarchy:\n')
                for l in lines:
                    w.write(l + '\n')

    def _gen_ts_tree(self, suite):
        n = suite.__name__
        tsd = {}
        tsd['doc'] = str(suite.__doc__)
        tstags = getattr(suite, TAGKEY, [])
        numnodes = 1
        for tag in tstags:
            if 'numnodes' in tag:
                numnodes = tag.split('=')[1].strip()
                break
        tsd['tags'] = tstags if len(tstags) > 0 else "None"
        tsd['numnodes'] = str(numnodes)
        tsd['file'] = suite.__module__.replace('.', '/') + '.py'
        tsd['module'] = suite.__module__
        dcl = suite.__dict__
        tcs = {}
        ts_req = getattr(suite, REQUIREMENTS_KEY, {})
        for k in dcl.keys():
            if k.startswith('test_'):
                tcd = {}
                tc = getattr(suite, k)
                try:
                    tc.__name__
                except BaseException:
                    # not a test case, ignore
                    continue
                tcd['doc'] = str(tc.__doc__)
                tc_req = getattr(tc, REQUIREMENTS_KEY, {})
                tcd['requirements'] = get_effective_reqs(ts_req, tc_req)
                numnodes = 1
                tctags = sorted(set(tstags + getattr(tc, TAGKEY, [])))
                for tag in tctags:
                    if 'numnodes' in tag:
                        numnodes = tag.split('=')[1].strip()
                        break
                tcd['tags'] = tctags if len(tctags) > 0 else "None"
                tcd['numnodes'] = str(numnodes)
                tcs[k] = deepcopy(tcd)
                if len(tctags) > 0:
                    for tag in tctags:
                        if tag not in self.__tags_tree.keys():
                            self.__tags_tree[tag] = {}
                        if n not in self.__tags_tree[tag].keys():
                            self.__tags_tree[tag][n] = deepcopy(tsd)
                        if 'tclist' not in self.__tags_tree[tag][n].keys():
                            self.__tags_tree[tag][n]['tclist'] = {}
                        self.__tags_tree[tag][n]['tclist'][k] = deepcopy(tcd)
                else:
                    if n not in self.__tags_tree['NoTags'].keys():
                        self.__tags_tree['NoTags'][n] = deepcopy(tsd)
                    if 'tclist' not in self.__tags_tree['NoTags'][n].keys():
                        self.__tags_tree['NoTags'][n]['tclist'] = {}
                    self.__tags_tree['NoTags'][n]['tclist'][k] = deepcopy(tcd)
        if len(tcs.keys()) > 0:
            self.__ts_tree[n] = deepcopy(tsd)
            self.__ts_tree[n]['tclist'] = tcs

    def finalize(self, result):
        if self.list_test or self.gen_ts_tree:
            suites = list(self._tree.keys())
        else:
            suites = self.suites
        suites.sort()
        unknown = []
        if self.gen_ts_tree:
            func = self._gen_ts_tree
        else:
            func = self._print_suite_info
        for k in suites:
            try:
                suite = eval(k, globals(), self._tree)
            except BaseException:
                unknown.append(k)
                continue
            func(suite)
        if self.list_test:
            w = sys.stdout
            w.write('\n\n')
            w.write('Total number of Test Suites: %d\n' % (self.total_suite))
            w.write('Total number of Test Cases: %d\n' % (self.total_case))
        elif self.gen_ts_tree:
            tsdata = ''
            tagsdata = ''
            try:
                import json
                tsdata = json.dumps(self.__ts_tree, indent=4)
                tagsdata = json.dumps(self.__tags_tree, indent=4)
            except ImportError:
                try:
                    import simplejson
                    tsdata = simplejson.dumps(self.__ts_tree, indent=4)
                    tagsdata = simplejson.dumps(self.__tags_tree, indent=4)
                except ImportError:
                    _pre = str(self.__ts_tree).replace('"', '\\"')
                    tsdata = _pre.replace('\'', '"')
                    _pre = str(self.__tags_tree).replace('"', '\\"')
                    tagsdata = _pre.replace('\'', '"')
            f = open('ptl_ts_tree.json', 'w+')
            f.write(tsdata)
            f.close()
            f = open('ptl_tags_tree.json', 'w+')
            f.write(tagsdata)
            f.close()
        if len(unknown) > 0:
            self.logger.error('Unknown testsuite(s): %s' % (','.join(unknown)))
