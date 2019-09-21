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
import unittest
from nose.plugins.base import Plugin
import collections

log = logging.getLogger('nose.plugins.PTLTestTags')

TAGKEY = '__PTL_TAGS_LIST__'


def tags(*args, **kwargs):
    """
    Decorator that adds tags to classes or functions or methods
    """
    def wrap_obj(obj):
        tagobj = getattr(obj, TAGKEY, [])
        for name in args:
            tagobj.append(name)
            PTLTestTags.tags_list.append(name)
            setattr(obj, name, True)
        for name, value in kwargs.items():
            tagobj.append('%s=%s' % (name, value))
            PTLTestTags.tags_list.append(name)
            setattr(obj, name, value)
        setattr(obj, TAGKEY, sorted(set(tagobj)))
        return obj
    return wrap_obj


def get_tag_value(method, cls, tag_name, default=False):
    """
    Look up an tag on a ``method/function``.
    If the tag isn't found there, looking it up in the
    method's class, if any.
    """
    Missing = object()
    value = getattr(method, tag_name, Missing)
    if value is Missing and cls is not None:
        value = getattr(cls, tag_name, Missing)
    if value is Missing:
        return default
    return value


class EvalHelper(object):

    """
    Object that can act as context dictionary for eval and looks up
    names as attributes on a method/function and its class.
    """

    def __init__(self, method, cls):
        self.method = method
        self.cls = cls

    def __getitem__(self, name):
        return get_tag_value(self.method, self.cls, name)


class FakeRunner(object):

    def __init__(self, matched, tags_list, list_tags, verbose):
        self.matched = matched
        self.tags_list = tags_list
        self.list_tags = list_tags
        self.verbose = verbose

    def run(self, test):
        if self.list_tags:
            print(('\n'.join(sorted(set(self.tags_list)))))
            sys.exit(0)
        suites = sorted(set(self.matched.keys()))
        if not self.verbose:
            print(('\n'.join(suites)))
        else:
            for k in suites:
                v = sorted(set(self.matched[k]))
                for _v in v:
                    print((k + '.' + _v))
        sys.exit(0)


class PTLTestTags(Plugin):

    """
    Load test cases from given parameter
    """
    name = 'PTLTestTags'
    score = sys.maxsize - 3
    logger = logging.getLogger(__name__)
    tags_list = []

    def __init__(self):
        Plugin.__init__(self)
        self.tags_to_check = []
        self.tags = []
        self.eval_tags = []
        self.tags_info = False
        self.list_tags = False
        self.verbose = False
        self.matched = {}
        self._test_marker = 'test_'

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, tags, eval_tags, tags_info=False, list_tags=False,
                 verbose=False):
        self.tags.extend(tags)
        self.eval_tags.extend(eval_tags)
        self.tags_info = tags_info
        self.list_tags = list_tags
        self.verbose = verbose

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options.

        attr and eval_attr may each be lists.

        self.attribs will be a list of lists of tuples. In that list, each
        list is a group of attributes, all of which must match for the rule to
        match.
        """
        self.tags_to_check = []
        for tag in self.eval_tags:
            def eval_in_context(expr, obj, cls):
                return eval(expr, None, EvalHelper(obj, cls))
            self.tags_to_check.append([(tag, eval_in_context)])
        for tags in self.tags:
            tag_group = []
            for tag in tags.strip().split(','):
                if not tag:
                    continue
                items = tag.split('=', 1)
                if len(items) > 1:
                    key, value = items
                else:
                    key = items[0]
                    if key[0] == '!':
                        key = key[1:]
                        value = False
                    else:
                        value = True
                tag_group.append((key, value))
            self.tags_to_check.append(tag_group)
        if (len(self.tags_to_check) > 0) or self.list_tags:
            self.enabled = True

    def is_tags_matching(self, method, cls=None):
        """
        Verify whether a method has the required tags
        The method is considered a match if it matches all tags
        for any tag group.
        """
        any_matched = False
        for group in self.tags_to_check:
            group_matched = True
            for key, value in group:
                tag_value = get_tag_value(method, cls, key)
                if isinstance(value, collections.Callable):
                    if not value(key, method, cls):
                        group_matched = False
                        break
                elif value is True:
                    if not bool(tag_value):
                        group_matched = False
                        break
                elif value is False:
                    if bool(tag_value):
                        group_matched = False
                        break
                elif type(tag_value) in (list, tuple):
                    value = str(value).lower()
                    if value not in [str(x).lower() for x in tag_value]:
                        group_matched = False
                        break
                else:
                    if ((value != tag_value) and
                            (str(value).lower() != str(tag_value).lower())):
                        group_matched = False
                        break
            any_matched = any_matched or group_matched
        if not any_matched:
            return False

    def prepareTestRunner(self, runner):
        """
        Prepare test runner
        """
        if (self.tags_info or self.list_tags):
            return FakeRunner(self.matched, self.tags_list, self.list_tags,
                              self.verbose)

    def wantClass(self, cls):
        """
        Accept the class if its subclass of TestCase and has at-least one
        test case
        """
        if not issubclass(cls, unittest.TestCase):
            return False
        has_test = False
        for t in dir(cls):
            if t.startswith(self._test_marker):
                has_test = True
                break
        if not has_test:
            return False

    def wantFunction(self, function):
        """
        Accept the function if its tags match.
        """
        return False

    def wantMethod(self, method):
        """
        Accept the method if its tags match.
        """
        try:
            cls = method.__self__.__class__
        except AttributeError:
            return False
        if not method.__name__.startswith(self._test_marker):
            return False
        rv = self.is_tags_matching(method, cls)
        if rv is None:
            cname = cls.__name__
            if cname not in self.matched.keys():
                self.matched[cname] = []
            self.matched[cname].append(method.__name__)
        return rv
