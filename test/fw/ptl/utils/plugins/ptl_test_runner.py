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


import datetime
import logging
import fnmatch
import os
import platform
import pwd
import re
import signal
import socket
import sys
import time
import tempfile
import unittest
from threading import Timer
from logging import StreamHandler
from traceback import format_exception
from types import ModuleType

from nose.core import TextTestRunner
from nose.plugins.base import Plugin
from nose.plugins.skip import SkipTest
from nose.suite import ContextSuite
from nose.util import isclass

import ptl
from ptl.lib.pbs_testlib import PBSInitServices
from ptl.utils.pbs_covutils import LcovUtils
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.pbs_dshutils import TimeOut
from ptl.utils.pbs_testsuite import (MINIMUM_TESTCASE_TIMEOUT,
                                     REQUIREMENTS_KEY, TIMEOUT_KEY)
from ptl.utils.plugins.ptl_test_info import get_effective_reqs
from ptl.utils.pbs_testusers import PBS_ALL_USERS, PBS_USERS, PbsUser
from ptl.lib.ptl_constants import (PTL_TRUE, PTL_FALSE)
from io import StringIO

log = logging.getLogger('nose.plugins.PTLTestRunner')


class TCThresholdReached(Exception):
    """
    Raise this exception to tell that tc-failure-threshold reached
    """


class TestLogCaptureHandler(StreamHandler):
    """
    Log handler for capturing logs which test case print
    using logging module
    """

    def __init__(self):
        self.buffer = StringIO()
        StreamHandler.__init__(self, self.buffer)
        self.setLevel(logging.DEBUG2)
        fmt = '%(asctime)-15s %(levelname)-8s %(message)s'
        self.setFormatter(logging.Formatter(fmt))

    def get_logs(self):
        return self.buffer.getvalue()


class _PtlTestResult(unittest.TestResult):

    """
    Ptl custom test result
    """
    separator1 = '=' * 70
    separator2 = '___m_oo_m___'
    logger = logging.getLogger(__name__)

    def __init__(self, stream, descriptions, verbosity, config=None):
        unittest.TestResult.__init__(self)
        self.stream = stream
        self.showAll = verbosity > 1
        self.dots = verbosity == 1
        self.descriptions = descriptions
        self.errorClasses = {}
        self.config = config
        self.success = []
        self.skipped = []
        self.timedout = []
        self.handler = TestLogCaptureHandler()
        self.start = datetime.datetime.now()
        self.stop = datetime.datetime.now()

    def getDescription(self, test):
        """
        Get the test result description
        """
        if hasattr(test, 'test'):
            return str(test.test)
        elif isinstance(test.context, ModuleType):
            tmn = getattr(test.context, '_testMethodName', 'unknown')
            return '%s (%s)' % (tmn, test.context.__name__)
        elif isinstance(test, ContextSuite):
            tmn = getattr(test.context, '_testMethodName', 'unknown')
            return '%s (%s.%s)' % (tmn,
                                   test.context.__module__,
                                   test.context.__name__)
        else:
            return str(test)

    def getTestDoc(self, test):
        """
        Get test document
        """
        if hasattr(test, 'test'):
            if hasattr(test.test, '_testMethodDoc'):
                return test.test._testMethodDoc
            else:
                return None
        else:
            if hasattr(test, '_testMethodDoc'):
                return test._testMethodDoc
            else:
                return None

    def clear_stop(self):
        self.shouldStop = False

    def startTest(self, test):
        """
        Start the test

        :param test: Test to start
        :type test: str
        """
        ptl_logger = logging.getLogger('ptl')
        if self.handler not in ptl_logger.handlers:
            ptl_logger.addHandler(self.handler)
        self.handler.buffer.truncate(0)
        self.handler.buffer.seek(0)
        unittest.TestResult.startTest(self, test)
        test.start_time = datetime.datetime.now()
        if self.showAll:
            self.logger.info('test name: ' + self.getDescription(test) + '...')
            self.logger.info('test start time: ' + test.start_time.ctime())
            tdoc = self.getTestDoc(test)
            if tdoc is not None:
                tdoc = '\n' + tdoc
            self.logger.info('test docstring: %s' % (tdoc))

    def addSuccess(self, test):
        """
        Add success to the test result
        """
        self.success.append(test)
        unittest.TestResult.addSuccess(self, test)
        if self.showAll:
            self.logger.info('ok\n')
        elif self.dots:
            self.logger.info('.')

    def _addError(self, test, err):
        unittest.TestResult.addError(self, test, err)
        if self.showAll:
            self.logger.info('ERROR\n')
        elif self.dots:
            self.logger.info('E')

    def addError(self, test, err):
        """
        Add error to the test result

        :param test: Test for which to add error
        :type test: str
        :param error: Error message to add
        :type error: str
        """
        if isclass(err[0]) and issubclass(err[0], TCThresholdReached):
            return
        if isclass(err[0]) and issubclass(err[0], SkipTest):
            self.addSkip(test, err[1])
            return
        if isclass(err[0]) and issubclass(err[0], TimeOut):
            self.addTimedOut(test, err)
            return
        for cls, (storage, label, isfail) in self.errorClasses.items():
            if isclass(err[0]) and issubclass(err[0], cls):
                if isfail:
                    test.passed = False
                storage.append((test, err))
                if self.showAll:
                    self.logger.info(label + '\n')
                elif self.dots:
                    self.logger.info(label[0])
                return
        test.passed = False
        self._addError(test, err)

    def addFailure(self, test, err):
        """
        Indicate failure
        """
        unittest.TestResult.addFailure(self, test, err)
        if self.showAll:
            self.logger.info('FAILED\n')
        elif self.dots:
            self.logger.info('F')

    def addSkip(self, test, reason):
        """
        Indicate skipping of test

        :param test: Test to skip
        :type test: str
        :param reason: Reason fot the skip
        :type reason: str
        """
        self.skipped.append((test, reason))
        if self.showAll:
            self.logger.info('SKIPPED')
        elif self.dots:
            self.logger.info('S')

    def addTimedOut(self, test, err):
        """
        Indicate timeout

        :param test: Test for which timeout happened
        :type test: str
        :param err: Error for timeout
        :type err: str
        """
        self.timedout.append((test, self._exc_info_to_string(err, test)))
        if self.showAll:
            self.logger.info('TIMEDOUT')
        elif self.dots:
            self.logger.info('T')

    def printErrors(self):
        """
        Print the errors
        """
        _blank_line = False
        if ((len(self.errors) > 0) or (len(self.failures) > 0) or
                (len(self.timedout) > 0)):
            if self.dots or self.showAll:
                self.logger.info('')
                _blank_line = True
            self.printErrorList('ERROR', self.errors)
            self.printErrorList('FAILED', self.failures)
            self.printErrorList('TIMEDOUT', self.timedout)
        for cls in self.errorClasses.keys():
            storage, label, isfail = self.errorClasses[cls]
            if isfail:
                if not _blank_line:
                    self.logger.info('')
                    _blank_line = True
                self.printErrorList(label, storage)
        self.config.plugins.report(self.stream)

    def printErrorList(self, flavour, errors):
        """
        Print the error list

        :param errors: Errors to print
        """
        for test, err in errors:
            self.logger.info(self.separator1)
            self.logger.info('%s: %s\n' % (flavour, self.getDescription(test)))
            self.logger.info(self.separator2)
            self.logger.info('%s\n' % err)

    def printLabel(self, label, err=None):
        """
        Print the label for the error

        :param label: Label to print
        :type label: str
        :param err: Error for which label to be printed
        :type err: str
        """
        if self.showAll:
            message = [label]
            if err:
                try:
                    detail = str(err[1])
                except BaseException:
                    detail = None
                if detail:
                    message.append(detail)
            self.logger.info(': '.join(message))
        elif self.dots:
            self.logger.info(label[:1])

    def wasSuccessful(self):
        """
        Check whether the test successful or not

        :returns: True if no ``errors`` or no ``failures`` or no ``timeout``
                  else return False
        """
        if self.errors or self.failures or self.timedout:
            return False
        for cls in self.errorClasses.keys():
            storage, _, isfail = self.errorClasses[cls]
            if not isfail:
                continue
            if storage:
                return False
        return True

    def printSummary(self):
        """
        Called by the test runner to print the final summary of test
        run results.

        :param start: Time at which test begins
        :param stop:  Time at which test ends
        """
        self.printErrors()
        msg = ['=' * 80]
        ef = []
        error = 0
        fail = 0
        skip = 0
        timedout = 0
        success = len(self.success)
        if len(self.failures) > 0:
            for failedtest in self.failures:
                fail += 1
                msg += ['failed: ' + self.getDescription(failedtest[0])]
                ef.append(failedtest)
        if len(self.errors) > 0:
            for errtest in self.errors:
                error += 1
                msg += ['error: ' + self.getDescription(errtest[0])]
                ef.append(errtest)
        if len(self.skipped) > 0:
            for skiptest, reason in self.skipped:
                skip += 1
                _msg = 'skipped: ' + str(skiptest).strip()
                _msg += ' reason: ' + str(reason).strip()
                msg += [_msg]
        if len(self.timedout) > 0:
            for tdtest in self.timedout:
                timedout += 1
                msg += ['timedout: ' + self.getDescription(tdtest[0])]
                ef.append(tdtest)
        cases = []
        suites = []
        for _ef in ef:
            if hasattr(_ef[0], 'test'):
                cname = _ef[0].test.__class__.__name__
                tname = getattr(_ef[0].test, '_testMethodName', 'unknown')
                cases.append(cname + '.' + tname)
                suites.append(cname)
        cases = sorted(list(set(cases)))
        suites = sorted(list(set(suites)))
        if len(cases) > 0:
            _msg = 'Test cases with failures: '
            _msg += ','.join(cases)
            msg += [_msg]
        if len(suites) > 0:
            _msg = 'Test suites with failures: '
            _msg += ','.join(suites)
            msg += [_msg]
        runned = success + fail + error + skip + timedout
        _msg = 'run: ' + str(runned)
        _msg += ', succeeded: ' + str(success)
        _msg += ', failed: ' + str(fail)
        _msg += ', errors: ' + str(error)
        _msg += ', skipped: ' + str(skip)
        _msg += ', timedout: ' + str(timedout)
        msg += [_msg]
        msg += ['Tests run in ' + str(self.stop - self.start)]
        self.logger.info('\n'.join(msg))


class SystemInfo:

    """
        used to get system's ram size and disk size information.

        :system_ram: Available ram(in GB) of the test running machine
        :system_disk: Available disk size(in GB) of the test running machine
    """
    logger = logging.getLogger(__name__)

    def get_system_info(self, hostname=None):
        du = DshUtils()
        # getting RAM size in gb
        mem_info = du.cat(hostname, "/proc/meminfo")
        if mem_info['rc'] != 0:
            _msg = 'failed to get content of /proc/meminfo of host: '
            self.logger.error(_msg + hostname)
        else:
            got_mem_available = False
            for i in mem_info['out']:
                if "MemTotal" in i:
                    self.system_total_ram = float(i.split()[1]) / (2**20)
                elif "MemAvailable" in i:
                    mem_available = float(i.split()[1]) / (2**20)
                    got_mem_available = True
                    break
                elif "MemFree" in i:
                    mem_free = float(i.split()[1]) / (2**20)
                elif "Buffers" in i:
                    buffers = float(i.split()[1]) / (2**20)
                elif i.startswith("Cached"):
                    cached = float(i.split()[1]) / (2**20)
            if got_mem_available:
                self.system_ram = mem_available
            else:
                self.system_ram = mem_free + buffers + cached
        # getting disk size in gb
        pbs_conf = du.parse_pbs_config(hostname)
        pbs_home_info = du.run_cmd(hostname, cmd=['df', '-k',
                                                  pbs_conf['PBS_HOME']])
        if pbs_home_info['rc'] != 0:
            _msg = 'failed to get output of df -k command of host: '
            self.logger.error(_msg + hostname)
        else:
            disk_info = pbs_home_info['out']
            disk_size = disk_info[1].split()
            self.system_disk = float(disk_size[3]) / (2**20)
            self.system_disk_used_percent = float(disk_size[4].rstrip('%'))


class PtlTextTestRunner(TextTestRunner):

    """
    Test runner that uses ``PtlTestResult`` to enable errorClasses,
    as well as providing hooks for plugins to override or replace the test
    output stream, results, and the test case itself.
    """

    cur_repeat_count = 1

    def __init__(self, stream=sys.stdout, descriptions=True, verbosity=3,
                 config=None, repeat_count=1, repeat_delay=0):
        self.logger = logging.getLogger(__name__)
        self.result = None
        self.repeat_count = repeat_count
        self.repeat_delay = repeat_delay
        TextTestRunner.__init__(self, stream, descriptions, verbosity, config)

    def _makeResult(self):
        return _PtlTestResult(self.stream, self.descriptions, self.verbosity,
                              self.config)

    def run(self, test):
        """
        Overrides to provide plugin hooks and defer all output to
        the test result class.
        """
        do_exit = False
        wrapper = self.config.plugins.prepareTest(test)
        if wrapper is not None:
            test = wrapper
        wrapped = self.config.plugins.setOutputStream(self.stream)
        if wrapped is not None:
            self.stream = wrapped
        self.result = result = self._makeResult()
        self.result.start = datetime.datetime.now()
        try:
            for i in range(self.repeat_count):
                PtlTextTestRunner.cur_repeat_count = i + 1
                if i != 0:
                    time.sleep(self.repeat_delay)
                test(result)
            if self.repeat_count > 1:
                self.logger.info("==========================================")
                self.logger.info("All Tests are repeated %d times"
                                 % self.repeat_count)
                self.logger.info("==========================================")
        except KeyboardInterrupt:
            do_exit = True
        self.result.stop = datetime.datetime.now()
        result.printSummary()
        self.config.plugins.finalize(result)
        if do_exit:
            sys.exit(1)
        return result


class PTLTestRunner(Plugin):

    """
    PTL Test Runner Plugin
    """
    name = 'PTLTestRunner'
    score = sys.maxsize - 4
    logger = logging.getLogger(__name__)
    timeout = None

    def __init__(self):
        Plugin.__init__(self)
        self.param = None
        self.repeat_count = 1
        self.repeat_delay = 0
        self.use_cur_setup = False
        self.lcov_bin = None
        self.lcov_data = None
        self.lcov_out = None
        self.lcov_utils = None
        self.lcov_nosrc = None
        self.lcov_baseurl = None
        self.genhtml_bin = None
        self.config = None
        self.result = None
        self.tc_failure_threshold = None
        self.cumulative_tc_failure_threshold = None
        self.__failed_tc_count = 0
        self.__tf_count = 0
        self.__failed_tc_count_msg = False
        self._test_marker = 'test_'
        self.hardware_report_timer = None

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, paramfile, testparam, repeat_count,
                 repeat_delay, lcov_bin, lcov_data, lcov_out,
                 genhtml_bin, lcov_nosrc, lcov_baseurl,
                 tc_failure_threshold, cumulative_tc_failure_threshold,
                 use_cur_setup):
        if paramfile is not None:
            _pf = open(paramfile, 'r')
            _params_from_file = _pf.readlines()
            _pf.close()
            _nparams = []
            for l in range(len(_params_from_file)):
                if _params_from_file[l].startswith('#'):
                    continue
                else:
                    _nparams.append(_params_from_file[l])
            _f = ','.join([l.strip('\r\n') for l in _nparams])
            if testparam is not None:
                testparam += ',' + _f
            else:
                testparam = _f
        self.param = testparam
        self.repeat_count = repeat_count
        self.repeat_delay = repeat_delay
        self.use_cur_setup = use_cur_setup
        self.lcov_bin = lcov_bin
        self.lcov_data = lcov_data
        self.lcov_out = lcov_out
        self.genhtml_bin = genhtml_bin
        self.lcov_nosrc = lcov_nosrc
        self.lcov_baseurl = lcov_baseurl
        self.tc_failure_threshold = tc_failure_threshold
        self.cumulative_tc_failure_threshold = cumulative_tc_failure_threshold

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options
        """
        self.config = config
        self.enabled = True
        self.param_dict = self.__get_param_dictionary()

    def prepareTestRunner(self, runner):
        """
        Prepare test runner
        """
        return PtlTextTestRunner(verbosity=3, config=self.config,
                                 repeat_count=self.repeat_count,
                                 repeat_delay=self.repeat_delay)

    def prepareTestResult(self, result):
        """
        Prepare test result
        """
        self.result = result

    def startContext(self, context):
        context.param = self.param
        context.use_cur_setup = self.use_cur_setup
        context.start_time = datetime.datetime.now()
        if isclass(context) and issubclass(context, unittest.TestCase):
            self.result.logger.info(self.result.separator1)
            self.result.logger.info('suite name: ' + context.__name__)
            doc = context.__doc__
            if doc is not None:
                self.result.logger.info('suite docstring: \n' + doc + '\n')
            self.result.logger.info(self.result.separator1)
            self.__failed_tc_count = 0
            self.__failed_tc_count_msg = False

    def __get_timeout(self, test):
        _test = None
        if hasattr(test, 'test'):
            _test = test.test
        elif hasattr(test, 'context'):
            _test = test.context
        if _test is None:
            return MINIMUM_TESTCASE_TIMEOUT
        dflt_timeout = int(getattr(_test,
                                   'conf',
                                   {}).get('default-testcase-timeout',
                                           MINIMUM_TESTCASE_TIMEOUT))
        tc_timeout = int(getattr(getattr(_test,
                                         getattr(_test, '_testMethodName', ''),
                                         None),
                                 TIMEOUT_KEY,
                                 0))
        return max([dflt_timeout, tc_timeout])

    def __set_test_end_data(self, test, err=None):
        if self.hardware_report_timer is not None:
            self.hardware_report_timer.cancel()
        if not hasattr(test, 'start_time'):
            test = test.context
        if err is not None:
            is_skip = issubclass(err[0], SkipTest)
            is_tctr = issubclass(err[0], TCThresholdReached)
            if not (is_skip or is_tctr):
                self.__failed_tc_count += 1
                self.__tf_count += 1
            try:
                test.err_in_string = self.result._exc_info_to_string(err,
                                                                     test)
            except BaseException:
                etype, value, tb = err
                test.err_in_string = ''.join(format_exception(etype, value,
                                                              tb))
        else:
            test.err_in_string = 'None'
        test.end_time = datetime.datetime.now()
        test.duration = test.end_time - test.start_time
        test.captured_logs = self.result.handler.get_logs()

    def __get_param_dictionary(self):
        """
        Method to convert data in param into dictionary of cluster
        information
        """
        def get_bool(v):
            if v is None or v == '':
                return False
            if v in PTL_TRUE:
                return True
            if v in PTL_FALSE:
                return False
            raise ValueError("Need boolean value, not %s" % v)

        tparam_contents = {}
        nomomlist = []
        shortname = (socket.gethostname()).split('.', 1)[0]
        for key in ['servers', 'moms', 'comms', 'clients', 'nomom']:
            tparam_contents[key] = []
        tparam_contents['mom_on_server'] = False
        tparam_contents['no_mom_on_server'] = False
        tparam_contents['no_comm_on_server'] = False
        tparam_contents['no_comm_on_mom'] = False
        if self.param is not None:
            for h in self.param.split(','):
                if '=' in h:
                    k, v = h.split('=', 1)
                    hosts = [x.split('@')[0] for x in v.split(':')]
                    if (k == 'server' or k == 'servers'):
                        tparam_contents['servers'].extend(hosts)
                    elif (k == 'mom' or k == 'moms'):
                        tparam_contents['moms'].extend(hosts)
                    elif k == 'comms':
                        tparam_contents['comms'] = hosts
                    elif k == 'client':
                        tparam_contents['clients'] = hosts
                    elif k == 'nomom':
                        nomomlist = hosts
                    elif k == 'mom_on_server':
                        tparam_contents['mom_on_server'] = get_bool(v)
                    elif k == 'no_mom_on_server':
                        tparam_contents['no_mom_on_server'] = get_bool(v)
                    elif k == 'no_comm_on_mom':
                        tparam_contents['no_comm_on_mom'] = get_bool(v)
        for pkey in ['servers', 'moms', 'comms', 'clients']:
            if not tparam_contents[pkey]:
                tparam_contents[pkey] = set([shortname])
            else:
                tparam_contents[pkey] = set(tparam_contents[pkey])
        if nomomlist:
            tparam_contents['nomom'] = set(nomomlist)
        return tparam_contents

    @staticmethod
    def __are_requirements_matching(param_dic=None, test=None):
        """
        Validates test requirements against test cluster information
        returns True on match or error message otherwise None

        :param param_dic: dictionary of cluster information from data passed
                          to param list
        :param_dic type: dic
        :param test: test object
        :test type: object

        :returns True or error message or None
        """
        logger = logging.getLogger(__name__)
        ts_requirements = {}
        tc_requirements = {}
        param_count = {}
        _servers = set(param_dic['servers'])
        _moms = set(param_dic['moms'])
        _comms = set(param_dic['comms'])
        _nomom = set(param_dic['nomom'])
        _mom_on_server = param_dic['mom_on_server']
        _no_mom_on_server = param_dic['no_mom_on_server']
        _no_comm_on_mom = param_dic['no_comm_on_mom']
        _no_comm_on_server = param_dic['no_comm_on_server']
        shortname = (socket.gethostname()).split('.', 1)[0]
        if test is None:
            return None
        test_name = getattr(test.test, '_testMethodName', None)
        if test_name is not None:
            method = getattr(test.test, test_name, None)
        if method is not None:
            tc_requirements = getattr(method, REQUIREMENTS_KEY, {})
            cls = method.__self__.__class__
            ts_requirements = getattr(cls, REQUIREMENTS_KEY, {})
        if not tc_requirements:
            if not ts_requirements:
                return None
        eff_tc_req = get_effective_reqs(ts_requirements, tc_requirements)
        setattr(test.test, 'requirements', eff_tc_req)
        for key in ['servers', 'moms', 'comms', 'clients']:
            param_count['num_' + key] = len(param_dic[key])
        for pk in param_count:
            if param_count[pk] < eff_tc_req[pk]:
                _msg = 'available ' + pk + " ("
                _msg += str(param_count[pk]) + ") is less than required " + pk
                _msg += " (" + str(eff_tc_req[pk]) + ")"
                logger.error(_msg)
                return _msg

        if hasattr(test, 'test'):
            _test = test.test
        elif hasattr(test, 'context'):
            _test = test.context
        else:
            return None

        name = 'moms'
        if (hasattr(_test, name) and
                (getattr(_test, name, None) is not None)):
            for mc in getattr(_test, name).values():
                platform = mc.platform
                if platform not in ['linux', 'shasta',
                                    'cray'] and mc.hostname in _moms:
                    _moms.remove(mc.hostname)
        for hostname in _moms:
            si = SystemInfo()
            si.get_system_info(hostname)
            available_sys_ram = getattr(si, 'system_ram', None)
            if available_sys_ram is None:
                _msg = 'failed to get ram info on host: ' + hostname
                logger.error(_msg)
                return _msg
            elif eff_tc_req['min_mom_ram'] >= available_sys_ram:
                _msg = hostname + ': available ram (' + str(available_sys_ram)
                _msg += ') is less than the minimum required ram ('
                _msg += str(eff_tc_req['min_mom_ram'])
                _msg += ') for test execution'
                logger.error(_msg)
                return _msg
            available_sys_disk = getattr(si, 'system_disk', None)
            if available_sys_disk is None:
                _msg = 'failed to get disk info on host: ' + hostname
                logger.error(_msg)
                return _msg
            elif eff_tc_req['min_mom_disk'] >= available_sys_disk:
                _msg = hostname + ': available disk space ('
                _msg += str(available_sys_disk)
                _msg += ') is less than the minimum required disk space ('
                _msg += str(eff_tc_req['min_mom_disk'])
                _msg += ') for test execution'
                logger.error(_msg)
                return _msg
        for hostname in param_dic['servers']:
            si = SystemInfo()
            si.get_system_info(hostname)
            available_sys_ram = getattr(si, 'system_ram', None)
            if available_sys_ram is None:
                _msg = 'failed to get ram info on host: ' + hostname
                logger.error(_msg)
                return _msg
            elif eff_tc_req['min_server_ram'] >= available_sys_ram:
                _msg = hostname + ': available ram (' + str(available_sys_ram)
                _msg += ') is less than the minimum required ram ('
                _msg += str(eff_tc_req['min_server_ram'])
                _msg += ') for test execution'
                logger.error(_msg)
                return _msg
            available_sys_disk = getattr(si, 'system_disk', None)
            if available_sys_disk is None:
                _msg = 'failed to get disk info on host: ' + hostname
                logger.error(_msg)
                return _msg
            elif eff_tc_req['min_server_disk'] >= available_sys_disk:
                _msg = hostname + ': available disk space ('
                _msg += str(available_sys_disk)
                _msg += ') is less than the minimum required disk space ('
                _msg += str(eff_tc_req['min_server_disk'])
                _msg += ') for test execution'
                logger.error(_msg)
                return _msg
        if _moms & _servers:
            if eff_tc_req['no_mom_on_server'] or \
               (_nomom - _servers) or \
               _no_mom_on_server:
                _msg = 'no mom on server'
                logger.error(_msg)
                return _msg
        else:
            if eff_tc_req['mom_on_server'] or \
               _mom_on_server:
                _msg = 'mom on server'
                logger.error(_msg)
                return _msg
        if _comms & _servers:
            if eff_tc_req['no_comm_on_server'] or _no_comm_on_server:
                _msg = 'no comm on server'
                logger.error(_msg)
                return _msg
        comm_mom_list = _moms & _comms
        if comm_mom_list and shortname in comm_mom_list:
            # Excluding the server hostname for flag 'no_comm_on_mom'
            comm_mom_list.remove(shortname)
        if comm_mom_list:
            if eff_tc_req['no_comm_on_mom']:
                _msg = 'no comm on mom'
                logger.error(_msg)
                return _msg
        else:
            if not eff_tc_req['no_comm_on_mom']:
                _msg = 'no comm on server'
                logger.error(_msg)
                return _msg

    def check_hardware_status_and_core_files(self, test):
        """
        function checks hardware status and core files
        every 5 minutes
        """
        du = DshUtils()
        systems = list(self.param_dict['servers'])
        systems.extend(self.param_dict['moms'])
        systems.extend(self.param_dict['comms'])
        systems = list(set(systems))

        if hasattr(test, 'test'):
            _test = test.test
        elif hasattr(test, 'context'):
            _test = test.context
        else:
            return None

        for name in ['servers', 'moms', 'comms', 'clients']:
            mlist = None
            if (hasattr(_test, name) and
                    (getattr(_test, name, None) is not None)):
                mlist = getattr(_test, name).values()
            if mlist:
                for mc in mlist:
                    platform = mc.platform
                    if ((platform not in ['linux', 'shasta', 'cray']) and
                            (mc.hostname in systems)):
                        systems.remove(mc.hostname)

        self.hardware_report_timer = Timer(
            300, self.check_hardware_status_and_core_files, args=(test,))
        self.hardware_report_timer.start()

        for hostname in systems:
            hr = SystemInfo()
            hr.get_system_info(hostname)
            # monitors disk
            used_disk_percent = getattr(hr,
                                        'system_disk_used_percent', None)
            if used_disk_percent is None:
                _msg = hostname
                _msg += ": unable to get disk info"
                self.hardware_report_timer.cancel()
                raise SkipTest(_msg)
            elif 70 <= used_disk_percent < 95:
                _msg = hostname + ": disk usage is at "
                _msg += str(used_disk_percent) + "%"
                _msg += ", disk cleanup is recommended."
                self.logger.warning(_msg)
            elif used_disk_percent >= 95:
                _msg = hostname + ":disk usage > 95%, skipping the test(s)"
                self.hardware_report_timer.cancel()
                raise SkipTest(_msg)
            # checks for core files
            pbs_conf = du.parse_pbs_config(hostname)
            mom_priv_path = os.path.join(pbs_conf["PBS_HOME"], "mom_priv")
            if du.isdir(hostname=hostname, path=mom_priv_path):
                mom_priv_files = du.listdir(
                    hostname=hostname,
                    path=mom_priv_path,
                    sudo=True,
                    fullpath=False)
                if fnmatch.filter(mom_priv_files, "core*"):
                    _msg = hostname + ": core files found in "
                    _msg += mom_priv_path
                    self.logger.warning(_msg)
            server_priv_path = os.path.join(
                pbs_conf["PBS_HOME"], "server_priv")
            if du.isdir(hostname=hostname, path=server_priv_path):
                server_priv_files = du.listdir(
                    hostname=hostname,
                    path=server_priv_path,
                    sudo=True,
                    fullpath=False)
                if fnmatch.filter(server_priv_files, "core*"):
                    _msg = hostname + ": core files found in "
                    _msg += server_priv_path
                    self.logger.warning(_msg)
            sched_priv_path = os.path.join(pbs_conf["PBS_HOME"], "sched_priv")
            if du.isdir(hostname=hostname, path=sched_priv_path):
                sched_priv_files = du.listdir(
                    hostname=hostname,
                    path=sched_priv_path,
                    sudo=True,
                    fullpath=False)
                if fnmatch.filter(sched_priv_files, "core*"):
                    _msg = hostname + ": core files found in "
                    _msg += sched_priv_path
                    self.logger.warning(_msg)
            for u in PBS_ALL_USERS:
                user_home_files = du.listdir(hostname=hostname, path=u.home,
                                             sudo=True, fullpath=False,
                                             runas=u.name)
                if user_home_files and fnmatch.filter(
                        user_home_files, "core*"):
                    _msg = hostname + ": user-" + str(u)
                    _msg += ": core files found in "
                    self.logger.warning(_msg + u.home)

    def startTest(self, test):
        """
        Start the test
        """
        if ((self.cumulative_tc_failure_threshold != 0) and
                (self.__tf_count >= self.cumulative_tc_failure_threshold)):
            _msg = 'Total testcases failure count exceeded cumulative'
            _msg += ' testcase failure threshold '
            _msg += '(%d)' % self.cumulative_tc_failure_threshold
            self.logger.error(_msg)
            raise KeyboardInterrupt
        if ((self.tc_failure_threshold != 0) and
                (self.__failed_tc_count >= self.tc_failure_threshold)):
            if self.__failed_tc_count_msg:
                raise TCThresholdReached
            _msg = 'Testcases failure for this testsuite count exceeded'
            _msg += ' testcase failure threshold '
            _msg += '(%d)' % self.tc_failure_threshold
            self.logger.error(_msg)
            self.__failed_tc_count_msg = True
            raise TCThresholdReached
        rv = None
        rv = self.__are_requirements_matching(self.param_dict, test)
        if rv is not None:
            # Below method call is needed in order to get the test case
            # details in the output and to have the skipped test count
            # included in total run count of the test run
            self.result.startTest(test)
            raise SkipTest(rv)
        # function report hardware status and core files
        self.check_hardware_status_and_core_files(test)

        def timeout_handler(signum, frame):
            raise TimeOut('Timed out after %s second' % timeout)
        if PTLTestRunner.timeout is None:
            timeout = self.__get_timeout(test)
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            setattr(test, 'old_sigalrm_handler', old_handler)
            signal.alarm(timeout)

    def stopTest(self, test):
        """
        Stop the test
        """
        old_sigalrm_handler = getattr(test, 'old_sigalrm_handler', None)
        if old_sigalrm_handler is not None:
            signal.signal(signal.SIGALRM, old_sigalrm_handler)
            signal.alarm(0)

    def addError(self, test, err):
        """
        Add error
        """
        if isclass(err[0]) and issubclass(err[0], TCThresholdReached):
            return True
        self.__set_test_end_data(test, err)

    def addFailure(self, test, err):
        """
        Add failure
        """
        self.__set_test_end_data(test, err)

    def addSuccess(self, test):
        """
        Add success
        """
        self.__set_test_end_data(test)

    def _cleanup(self):
        self.logger.info('Cleaning up temporary files')
        du = DshUtils()
        hosts = set(self.param_dict['moms']).union(
            set(self.param_dict['servers']))
        for user in PBS_USERS:
            self.logger.debug('Cleaning %s\'s home directory' % (str(user)))
            runas = PbsUser.get_user(user)
            for host in hosts:
                ret = du.run_cmd(host, cmd=['printenv', 'HOME'], sudo=True,
                                 runas=runas, logerr=False, as_script=False,
                                 level=logging.DEBUG)
                if ret['rc'] == 0:
                    path = ret['out'][0].strip()
                else:
                    return None
                ftd = []
                files = du.listdir(host, path=path, runas=user,
                                   level=logging.DEBUG)
                bn = os.path.basename
                ftd.extend([f for f in files if bn(f).startswith('PtlPbs')])
                ftd.extend([f for f in files if bn(f).startswith('STDIN')])

                if len(ftd) > 1000:
                    for i in range(0, len(ftd), 1000):
                        j = i + 1000
                        du.rm(host, path=ftd[i:j], runas=user,
                              force=True, level=logging.DEBUG)

        root_dir = os.sep
        dirlist = set([os.path.join(root_dir, 'tmp'),
                       os.path.join(root_dir, 'var', 'tmp')])
        # get tmp dir from the environment
        for envname in 'TMPDIR', 'TEMP', 'TMP':
            dirname = os.getenv(envname)
            if dirname:
                dirlist.add(dirname)

        p = re.compile(r'^pbs\.\d+')
        for tmpdir in dirlist:
            # list the contents of each tmp dir and
            # get the file list to be deleted
            self.logger.info('Cleaning up ' + tmpdir + ' dir')
            ftd = []
            files = du.listdir(path=tmpdir)
            bn = os.path.basename
            ftd.extend([f for f in files if bn(f).startswith('PtlPbs')])
            ftd.extend([f for f in files if bn(f).startswith('STDIN')])
            ftd.extend([f for f in files if bn(f).startswith('pbsscrpt')])
            ftd.extend([f for f in files if bn(f).startswith('pbs.conf.')])
            ftd.extend([f for f in files if p.match(bn(f))])
            for f in ftd:
                du.rm(path=f, sudo=True, recursive=True, force=True,
                      level=logging.DEBUG)
        for f in du.tmpfilelist:
            du.rm(path=f, sudo=True, force=True, level=logging.DEBUG)
        del du.tmpfilelist[:]
        tmpdir = tempfile.gettempdir()
        os.chdir(tmpdir)
        tmppath = os.path.join(tmpdir, 'dejagnutemp%s' % os.getpid())
        if du.isdir(path=tmppath):
            du.rm(path=tmppath, recursive=True, sudo=True, force=True,
                  level=logging.DEBUG)

    def begin(self):
        command = sys.argv
        command[0] = os.path.basename(command[0])
        self.logger.info('input command: ' + ' '.join(command))
        self.logger.info('param: ' + str(self.param))
        self.logger.info('ptl version: ' + str(ptl.__version__))
        _m = 'platform: ' + ' '.join(platform.uname()).strip()
        self.logger.info(_m)
        self.logger.info('python version: ' + str(platform.python_version()))
        self.logger.info('user: ' + pwd.getpwuid(os.getuid())[0])
        self.logger.info('-' * 80)

        if self.lcov_data is not None:
            self.lcov_utils = LcovUtils(cov_bin=self.lcov_bin,
                                        html_bin=self.genhtml_bin,
                                        cov_out=self.lcov_out,
                                        data_dir=self.lcov_data,
                                        html_nosrc=self.lcov_nosrc,
                                        html_baseurl=self.lcov_baseurl)
            # Initialize coverage analysis
            self.lcov_utils.zero_coverage()
            # The following 'dance' is done due to some oddities on lcov's
            # part, according to this the lcov readme file at
            # http://ltp.sourceforge.net/coverage/lcov/readme.php that reads:
            #
            # Note that this step only works after the application has
            # been started and stopped at least once. Otherwise lcov will
            # abort with an error mentioning that there are no data/.gcda
            # files.
            self.lcov_utils.initialize_coverage(name='PTLTestCov')
            PBSInitServices().restart()
        self._cleanup()

    def finalize(self, result):
        if self.lcov_data is not None:
            # See note above that briefly explains the 'dance' needed to get
            # reliable coverage data
            PBSInitServices().restart()
            self.lcov_utils.capture_coverage(name='PTLTestCov')
            exclude = ['"*work/gSOAP/*"', '"*/pbs/doc/*"', 'lex.yy.c',
                       'pbs_ifl_wrap.c', 'usr/include/*', 'unsupported/*']
            self.lcov_utils.merge_coverage_traces(name='PTLTestCov',
                                                  exclude=exclude)
            self.lcov_utils.generate_html()
            self.lcov_utils.change_baseurl()
            self.logger.info('\n'.join(self.lcov_utils.summarize_coverage()))
        self._cleanup()
