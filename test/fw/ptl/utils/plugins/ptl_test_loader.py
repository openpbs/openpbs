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
import logging
import copy
from nose.plugins.base import Plugin
from ptl.utils.pbs_testsuite import PBSTestSuite
from ptl.utils.pbs_dshutils import DshUtils

log = logging.getLogger('nose.plugins.PTLTestLoader')


class PTLTestLoader(Plugin):

    """
    Load test cases from given parameter
    """
    name = 'PTLTestLoader'
    score = sys.maxsize - 1
    logger = logging.getLogger(__name__)

    def __init__(self):
        Plugin.__init__(self)
        self.suites_list = []
        self.excludes = []
        self.follow = False
        self._only_ts = '__only__ts__'
        self._only_tc = '__only__tc__'
        self._test_marker = 'test_'
        self._tests_list = {self._only_ts: [], self._only_tc: []}
        self._excludes_list = {self._only_ts: [], self._only_tc: []}
        self.__tests_list_copy = {self._only_ts: [], self._only_tc: []}
        self.__allowed_cls = []
        self.__allowed_method = []
        self.testfiles = None

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, testgroup, suites, excludes, follow, testfiles=None):
        """
        Set the data required for loading test data

        :param testgroup: Test group
        :param suites: Test suites to load
        :param excludes: Tests to exclude while running
        :param testfiles: Flag to check if test is run by filename
        """
        if os.access(str(testgroup), os.R_OK):
            f = open(testgroup, 'r')
            self.suites_list.extend(f.readline().strip().split(','))
            f.close()
        elif suites is not None:
            self.suites_list.extend(suites.split(','))
        if excludes is not None:
            self.excludes.extend(excludes.split(','))
        self.follow = follow
        self.testfiles = testfiles

    def configure(self, options, config):
        """
        Configure the ``plugin`` and ``system``, based on selected options
        """
        tl = self._tests_list
        tlc = self.__tests_list_copy
        for _is in self.suites_list:
            if '.' in _is:
                suite, case = _is.split('.')
                if case in tl[self._only_tc]:
                    tl[self._only_tc].remove(case)
                    tlc[self._only_tc].remove(case)
                if suite in tl.keys():
                    if case not in tl[suite]:
                        tl[suite].append(case)
                        tlc[suite].append(case)
                else:
                    tl.setdefault(suite, [case])
                    tlc.setdefault(suite, [case])
            elif _is.startswith(self._test_marker):
                if _is not in tl[self._only_tc]:
                    tl[self._only_tc].append(_is)
                    tlc[self._only_tc].append(_is)
            else:
                if _is not in tl[self._only_ts]:
                    tl[self._only_ts].append(_is)
                    tlc[self._only_ts].append(_is)
        for k, v in tl.items():
            if k in (self._only_ts, self._only_tc):
                continue
            if len(v) == 0:
                tl[self._only_ts].append(k)
                tlc[self._only_ts].append(k)
        for name in tl[self._only_ts]:
            if name in tl.keys():
                del tl[name]
                del tlc[name]
        extl = self._excludes_list
        for _is in self.excludes:
            if '.' in _is:
                suite, case = _is.split('.')
                if case in extl[self._only_tc]:
                    extl[self._only_tc].remove(case)
                if suite in extl.keys():
                    if case not in extl[suite]:
                        extl[suite].append(case)
                else:
                    extl.setdefault(suite, [case])
            elif _is.startswith(self._test_marker):
                if _is not in extl[self._only_tc]:
                    extl[self._only_tc].append(_is)
            else:
                if _is not in extl[self._only_ts]:
                    extl[self._only_ts].append(_is)
        for k, v in extl.items():
            if k in (self._only_ts, self._only_tc):
                continue
            if len(v) == 0:
                extl[self._only_ts].append(k)
        for name in extl[self._only_ts]:
            if name in extl.keys():
                del extl[name]
        log.debug('included_tests:%s' % (str(self._tests_list)))
        log.debug('included_tests(copy):%s' % (str(self.__tests_list_copy)))
        log.debug('excluded_tests:%s' % (str(self._excludes_list)))
        self.enabled = len(self.suites_list) > 0
        del self.suites_list
        del self.excludes

    def check_unknown(self):
        """
        Check for unknown test suite and test case
        """
        log.debug('check_unknown called')
        tests_list_copy = copy.deepcopy(self.__tests_list_copy)
        only_ts = tests_list_copy.pop(self._only_ts)
        only_tc = tests_list_copy.pop(self._only_tc)
        msg = []
        if len(tests_list_copy) > 0:
            for k, v in tests_list_copy.items():
                msg.extend(map(lambda x: k + '.' + x, v))
        if len(only_tc) > 0:
            msg.extend(only_tc)
        if len(msg) > 0:
            _msg = ['unknown testcase(s): %s' % (','.join(msg))]
            msg = _msg
        if len(only_ts) > 0:
            msg += ['unknown testsuite(s): %s' % (','.join(only_ts))]
        if len(msg) > 0:
            for l in msg:
                logging.error(l)
            sys.exit(1)

    def prepareTestLoader(self, loader):
        """
        Prepare test loader
        """
        old_loadTestsFromNames = loader.loadTestsFromNames

        def check_loadTestsFromNames(names, module=None):
            tests_dir = names
            if not self.testfiles:
                ptl_test_dir = __file__
                ptl_test_dir = os.path.join(ptl_test_dir.split('ptl')[0],
                                            "ptl", "tests")
                user_test_dir = os.environ.get("PTL_TESTS_DIR", None)
                if user_test_dir and os.path.isdir(user_test_dir):
                    tests_dir += [user_test_dir]
                if os.path.isdir(ptl_test_dir):
                    tests_dir += [ptl_test_dir]
            rv = old_loadTestsFromNames(tests_dir, module)
            self.check_unknown()
            return rv
        loader.loadTestsFromNames = check_loadTestsFromNames
        return loader

    def check_follow(self, cls, method=None):
        cname = cls.__name__
        if not issubclass(cls, PBSTestSuite):
            return False
        if cname == 'PBSTestSuite':
            if 'PBSTestSuite' not in self._tests_list[self._only_ts]:
                return False
        if cname in self._excludes_list[self._only_ts]:
            return False
        if cname in self._tests_list[self._only_ts]:
            if cname in self.__tests_list_copy[self._only_ts]:
                self.__tests_list_copy[self._only_ts].remove(cname)
            return True
        if ((cname in self._tests_list.keys()) and (method is None)):
            return True
        if method is not None:
            mname = method.__name__
            if not mname.startswith(self._test_marker):
                return False
            if mname in self._excludes_list[self._only_tc]:
                return False
            if ((cname in self._excludes_list.keys()) and
                    (mname in self._excludes_list[cname])):
                return False
            if ((cname in self._tests_list.keys()) and
                    (mname in self._tests_list[cname])):
                if cname in self.__tests_list_copy.keys():
                    if mname in self.__tests_list_copy[cname]:
                        self.__tests_list_copy[cname].remove(mname)
                    if len(self.__tests_list_copy[cname]) == 0:
                        del self.__tests_list_copy[cname]
                return True
            if mname in self._tests_list[self._only_tc]:
                if mname in self.__tests_list_copy[self._only_tc]:
                    self.__tests_list_copy[self._only_tc].remove(mname)
                return True
        if self.follow:
            return self.check_follow(cls.__bases__[0], method)
        else:
            return False

    def is_already_allowed(self, cls, method=None):
        """
        :param method: Method to check
        :returns: True if method is already allowed else False
        """
        name = cls.__name__
        if method is not None:
            name += '.' + method.__name__
            if name in self.__allowed_method:
                return True
            else:
                self.__allowed_method.append(name)
                return False
        else:
            if name in self.__allowed_cls:
                return True
            else:
                self.__allowed_cls.append(name)
                return False

    def wantClass(self, cls):
        """
        Is the class wanted?
        """
        has_test = False
        for t in dir(cls):
            if t.startswith(self._test_marker):
                has_test = True
                break
        if not has_test:
            return False
        rv = self.check_follow(cls)
        if rv and not self.is_already_allowed(cls):
            log.debug('wantClass:%s' % (str(cls)))
        else:
            return False

    def wantFunction(self, function):
        """
        Is the function wanted?
        """
        return self.wantMethod(function)

    def wantMethod(self, method):
        """
        Is the method wanted?
        """
        try:
            cls = method.__self__.__class__
        except AttributeError:
            return False
        if not method.__name__.startswith(self._test_marker):
            return False
        rv = self.check_follow(cls, method)
        if rv and not self.is_already_allowed(cls, method):
            log.debug('wantMethod:%s' % (str(method)))
        else:
            return False
