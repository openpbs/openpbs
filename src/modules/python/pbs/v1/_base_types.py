# coding: utf-8
"""

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


"""
__doc__ = """
All Python based types mapping to PBS attribute types.
"""

_ATTRIBUTES_KEY_NAME = 'attributes'

__all__ = ['_generic_attr',
           'size',
           'to_bytes',
           'size_to_kbytes',
           'duration',
           'pbs_env',
           'email_list',
           'pbs_list',
           'pbs_bool',
           'pbs_int',
           'pbs_str',
           'pbs_float',
           'acl',
           'select',
           'place',
           'exec_host',
           'exec_vnode',
           'checkpoint',
           'depend',
           'group_list',
           'user_list',
           'path_list',
           'path',
           'sandbox',
           'hold_types',
           'keep_files',
           'mail_points',
           'staging_list',
           'range',
           'state_count',
           'license_count',
           'route_destinations',
           'args',
           'job_sort_formula',
           'node_group_key',
           'version',
           'software',
           'priority',
           'name',
           'project',
           'join_path',
           'PbsAttributeDescriptor',
           'PbsReadOnlyDescriptor',
           'pbs_resource',
           'vchunk',
           'vnode_state',
           'vnode_sharing',
           'vnode_ntype'
           ]

import _pbs_v1
import sys
import math
import weakref
_size = _pbs_v1.svr_types._size
_LOG = _pbs_v1.logmsg
_IS_SETTABLE = _pbs_v1.is_attrib_val_settable


class PbsAttributeDescriptor():
    """This class wraps evey PBS attribute into a *DATA* descriptor AND is
    maintained per instance instead of the default per class.

    Some things to note are:
      - All attributes values are ensured to be an instance of value_type
      - if read_only is set then any attempt to set will raise BadAttributeValueError
      - Add the attribute name to the dictionary 'attributes' on the instance if
        it exists.
      - Since a Descriptor is a class level object, to maintain unique values
        across instances, we maintain an internal dictionary.
    """

    def __init__(self, cls, name, default_value, value_type=None, resc_attr=None, is_entity=0):
        """
        """

        self._name = name
        self._value = default_value
        self._class_name = cls.__name__
        self._is_entity = is_entity

        #: check if we are resource wrapped in a attribute
        self._is_resource = False
        self._resc_attribute = None
        if resc_attr is not None:
            self._is_resource = True
            self._resc_attribute = resc_attr

        #: WARNING value_type must support sequence protocol, see __set__ for
        #: why
        if value_type is None:
            self._value_type = (str,)
        elif isinstance(value_type, (list, tuple)):
            self._value_type = value_type
        else:
            self._value_type = tuple(value_type)
        #:

        #: The below is used to keep track of all the descriptors in a Class
        #: WARNING Purposely not checking exception so as to ensure all Classes
        #: that use this descriptor define a _ATTRIBUTES_KEY_NAME which is of
        #: Mapping type.

        __attributes = getattr(cls, _ATTRIBUTES_KEY_NAME)
        __attributes[name] = None
        #: now we need to maintain a unique value for each object
        self.__per_instance = weakref.WeakKeyDictionary()

    #: m(__init__)

    def __get__(self, obj, cls=None):
        """__get__
        """

        #: if accessing from class then return self
        if obj is None:
            return self

        #: if this attribute has never been accessed or set by the instance then
        #: we just return the default value
        #: NOTE: Doing the more compact:
        #   return self.__per_instance.setdefault(obj,self._get_default_value())
        #  caused pbs_resource to be instantiated every time. Probably due to
        #  _get_default_value() getting evaluatd every time.

        if obj not in self.__per_instance:
            v = self._get_default_value()
            self.__per_instance[obj] = v

        return self.__per_instance[obj]
    #: m(__get__)

    def __set__(self, obj, value):
        """__set___
        """

        if not _IS_SETTABLE(self, obj, value):
            return

        # if in Python (hook script mode), the hook writer has set value to
        # to None, meaning to unset the attribute.

        try:
            basestring
        except Exception:
            basestring = str

        if (value is None) and _pbs_v1.in_python_mode():
            set_value = ""
        elif ((value is None)
              or (isinstance(value, basestring) and value == "")
              or isinstance(value, self._value_type)
              or self._is_entity
              or (hasattr(obj, "_is_entity")
                  and getattr(obj, "_is_entity"))):

            # no instantiation/transformation of value needed if matching
            # one of the following cases:
            #     - value is unset  : (value is None) or (value == "")
            #     - same type as value's type :
            #                       (isinstance(value, self._value_type)
            #     - a special entity resource type : self.is_entity is True
            #                             or parent object is an entity type
            set_value = value
        else:
            if self._is_resource and isinstance(value, str) and (value[0] == "@"):
                # an indirect resource
                set_value = value
            else:
                set_value = self._value_type[0](value)
        #:
        self.__per_instance[obj] = set_value
    #: m(__set__)

    def _set_resc_atttr(self, resc_attr, is_entity=0):
        """
        """
        self._resc_attribute = resc_attr
        self._is_resource = True
        self._is_entity = is_entity

    #: m(_set_resc_atttr)

    def __delete__(self, obj):
        """__delete__, we just set the attribute value to None"""

        self.__per_instance[obj] = None
    #: m(__delete__)

    def _get_default_value(self):
        """ get a default value
        """

        if self._value is None:
            return self._value

        #: otherwise return a new instance of default value
        if self._value_type[0] == pbs_resource:
            # following results in the call
            #	pbs_resource(self._value, self._is_entity)
            # (see class pbs_resource __init__ method)
            s = self._value_type[0](self._value, self._is_entity)
        else:
            s = self._value_type[0](self._value)
        return s

    # the checkValue method here before was rolled into _IS_SETTABLE

#: End Class PbsAttributeDescriptor


class PbsReadOnlyDescriptor():
    """This class wraps a generic read only data descriptor. This is a class
    level descriptor.
    """

    def __init__(self, name, value):
        """

        """
        self._name = name
        self._value = value
    #: m(__init__)

    def __get__(self, obj, cls=None):
        """get """

        return self._value
    #: m(__get__)

    def __set__(self, obj, value):
        """set"""
        raise BadAttributeValueError("<%s> is readonly" % (self._name,))
    #: m(__set__)

    def __delete__(self, obj):
        """delete, we just set the attribute value to None"""
        raise BadAttributeValueError("cannot delete <%s>" % (self._name,))
    #: m(__delete__)

    def __str__(self):
        if isinstance(self._value, dict):
            return ",".join(list(self._value.keys()))
        else:
            return str(self._value)
        #
    #: m(__str__)
    __repr__ = __str__

#: End Class PbsReadOnlyDescriptor


#
from ._exc_types import *


class _generic_attr():
    """A generic attribute"""

    # _derived_types: What type other than '_generic_attr' will be accepted
    _derived_types = (str,)

    def __init__(self, value):

        self._value = None
        if value is not None:
            if isinstance(value, (str, _generic_attr)):
                self._value = value
            else:
                self._value = value.__class__(value)

        super().__init__()
    #: m(__init__)

    def __str__(self):
        """String representation of the object"""
        return str(self._value)
    #: m(__str__)

    __repr__ = __str__

#: C(_generic_attr)

#: ---------------------  VALUE TYPES         ---------------------
# to_bytes: given a _size 'sz' value, returns an integer which is the
# equivalent number of bytes.


def to_bytes(sz):

    s_str = str(sz).rstrip("bB")
    sl = len(s_str)
    wordsz = 1
    if (s_str[sl - 1] == "w") or (s_str[sl - 1] == "W"):
        s_str = s_str.rstrip("wW")
        wordsz = _pbs_v1.wordsize()

    sl = len(s_str)
    if (s_str[sl - 1] == "k") or (s_str[sl - 1] == "K"):
        s_num = int(s_str.rstrip("kK")) * 1024
    elif (s_str[sl - 1] == "m") or (s_str[sl - 1] == "M"):
        s_num = int(s_str.rstrip("mM")) * 1024 * 1024
    elif (s_str[sl - 1] == "g") or (s_str[sl - 1] == "G"):
        s_num = int(s_str.rstrip("gG")) * 1024 * 1024 * 1024
    elif (s_str[sl - 1] == "t") or (s_str[sl - 1] == "T"):
        s_num = int(s_str.rstrip("tT")) * 1024 * 1024 * 1024 * 1024
    elif (s_str[sl - 1] == "p") or (s_str[sl - 1] == "P"):
        s_num = int(s_str.rstrip("pP")) * 1024 * 1024 * 1024 * 1024 * 1024
    else:
        s_num = int(s_str)

    s_num *= wordsz
    return s_num

# transform_sizes: return _size transformation of 'sz1' and 'sz2' that
# can be fed to the richcompare functions of _size without causing an
# overflow or rounding up inherent in small values.


def transform_sizes(sz1, sz2):

    s_num = -1
    s = sz1
    if isinstance(sz1, (int, size)):
        s = _size(str(sz1))
        if s.__le__(_size("10kb")):
            # make all values at least 10kb to prevent rounding up errors
            # in normalize_size().  Here, we make it relative to 1gb.
            s_num = to_bytes(s) + 1073741824
            s = _size(s_num)

    o_num = -1
    o = sz2
    if isinstance(sz2, (int, size)):
        o = _size(str(sz2))
        if o.__le__(_size("10kb")):
            # make all values at least 10kb to prevent rounding up errors
            # in normalize_size()
            o_num = to_bytes(o) + 1073741824
            o = _size(o_num)

    if s_num == -1 and isinstance(s, _size):
        s = _size(s.__add__(_size("1gb")))
    if o_num == -1 and isinstance(o, _size):
        o = _size(o.__add__(_size("1gb")))

    l = [s, o]
    return l


def size_to_kbytes(sz):
    """
    Given a pbs.size value 'sz', return the actual
    # of kbytes representing the value.
    """
    return _pbs_v1.size_to_kbytes(sz)


class size(_size):
    """
    This represents a PBS size type.
    pbs.size(int)
    pbs.size("int[suffix]") where suffix is:

         b or  w     bytes or words.
         kb or kw    Kilo (1024) bytes or words.
         mb or mw    Mega (1,048,576) bytes or words.
         gb or gw    Giga (1,073,741,824) bytes or words.
         tb or tw    Tera (1024  gigabytes) bytes or words.
         pb or pw    Peta  (1,048,576 gigabytes) bytes or words

    pbs.size instances can be operated on by +, - operators, and can be
    can be compared using the operators ==, !=, >, <, >=, and <=.

        Ex.
        >> sz = pbs.size(10gb)

        # the sizes are normalize to the lower of
        # the 2 suffixes.
        # In this case, 10gb becomes 10240mb
        # and added to 10mb
        >> sz = sz + 10mb
        10250mb

        # following returns true as sz is greater
        # than 100 bytes.
        >> if  sz > 100:
        print  true
    """

    _derived_types = (_size,)

    def __lt__(self, other):
        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) < int(o_str))

        # uses _size's richcompare
        return s.__lt__(o)

    def __le__(self, other):
        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) <= int(o_str))

        # uses _size's richcompare
        return s.__le__(o)

    def __gt__(self, other):
        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) > int(o_str))

        # uses _size's richcompare
        return s.__gt__(o)

    def __ge__(self, other):
        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) >= int(o_str))

        # uses _size's richcompare
        return s.__ge__(o)

    def __eq__(self, other):
        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) == int(o_str))

        # uses _size's richcompare
        return s.__eq__(o)

    def __ne__(self, other):
        """
        This is called on a <self> != <other> comparison, where
        <self> is of size type.
        """
        if not isinstance(other, (int, size)):
            # if <other> object is not of type 'int', 'long', or 'size',
            # then it cannot be transformed into size type.
            # So automatically this != comparison should return
            # True  - yes, they're not equal.
            return True

        so = transform_sizes(self, other)
        s = so[0]
        o = so[1]

        s_str = str(s).rstrip("bB")
        o_str = str(o).rstrip("bB")

        if s_str.isdigit() and o_str.isdigit():
            return(int(s_str) != int(o_str))

        # uses _size's richcompare
        return s.__ne__(o)

    def __add__(self, other):
        s = self
        o = other
        if isinstance(self, (int, size)):
            s = _size(str(self))
        if isinstance(other, (int, size)):
            o = _size(str(other))
        # uses _size's add function, but trick is return
        # the "size" type so that any comparisons with the
        # return would look in here for comparison operators
        # and not in _size's richcompare.
        return size(s.__add__(o))

    def __sub__(self, other):
        s = self
        o = other
        if isinstance(self, (int, size)):
            s = _size(str(self))
        if isinstance(other, (int, size)):
            o = _size(str(other))
        # uses _size's subtract function, but trick is return
        # the "size" type so that any comparisons with the
        # return would look in here for comparison operators
        # and not in _size's richcompare.
        return size(s.__sub__(o))

    def __deepcopy__(self, mem):
        return size(str(self))


class duration(int):
    """
    Represents an interval or elapsed time object in number of seconds. This is
    actually derived from a Python int type.

    pbs.duration([[intHours:]intMinutes:]intSeconds[.intMilliseconds])
    pbs.duration(int)
    """
    # alternate form (i.e. what type can be used for pbs attribute of this
    # type. For example, walltime is pbs.duration type, but can also be set
    # using the given _derived_types:
    _derived_types = (int,)

    def __new__(cls, value):
        valstr = str(value)
        # validates against the 'walltime' attribute entry of the
        # the server 'resource' table
        _pbs_v1.validate_input("resc", "walltime", valstr)
        return int.__new__(cls, _pbs_v1.duration_to_secs(valstr))

    def __init__(self, value):
        self.duration_str = str(value)

    def __str__(self):
        return self.duration_str


def replace_char_not_before(str, chr, repl_substr, chr_after_list):
    """
    Given 'str', replace all occurences of single character 'chr' with
    replacement  substr 'repl_substr', only if 'chr' in 'str' is not
    succeeded by any of the characters in 'chr_after_list'.
    Ex. Given str = "ab\,c\d\'\e\"\f\\,
              # replace occurences of "\" with  "\\" as long as it is
              # not followed by <,>, <'>, <">,  or <\>
              replace_char_not_after(str, "\", "\\",
                                        [ ',', '\'', '\"', '\\'])  =
                "ab\,c\\d\'\\e\"\\f\\"
        Here are sample transformations:

         str= ab\,c\d\'\e\"\f\
        rstr= ab\,c\\d\'\\e\"\\f\\

         str= \ab\,c\d\'\e\"\f\
        rstr= \\ab\,c\\d\'\\e\"\\f\\

         str= \ab\,c\d\'\e\"\f\
        rstr= \\ab\,c\\d\'\\e\"\\f\\

         str= \\ab\,c\d\'\e\"\f\
        rstr= \\ab\,c\\d\'\\e\"\\f\\

         str= \\ab\,c\\d\'\e\"\f\
        rstr= \\ab\,c\\d\'\\e\"\\f\\
    """
    i = 0
    l = len(str)
    end_index = l - 1
    s = ""
    while i < l:
        if (str[i] != chr) or \
            ((i > 0) and (str[i - 1] == chr) and (str[i] in chr_after_list)) or \
                ((i < end_index) and (str[i + 1] in chr_after_list)):
            s += str[i]
        else:
            s += repl_substr
        i = i + 1
    return s


class pbs_env(dict):
    # a list of path where "\" will be converted to "/"
    _attributes_readonly = PbsReadOnlyDescriptor('_attributes_readonly',
                                                 ['PBS_ENVIRONMENT',
                                                  'PBS_JOBDIR',
                                                  'PBS_JOBID',
                                                  'PBS_JOBNAME',
                                                  'PBS_NODEFILE',
                                                  'TMPDIR',
                                                  'PBS_O_HOME',
                                                  'PBS_O_HOST',
                                                  'PBS_O_LANG',
                                                  'PBS_O_LOGNAME',
                                                  'PBS_O_MAIL',
                                                  'PBS_O_PATH',
                                                  'PBS_O_QUEUE',
                                                  'PBS_O_SHELL',
                                                  'PBS_O_SYSTEM',
                                                  'PBS_O_TZ',
                                                  'PBS_O_WORKDIR',
                                                  'PBS_QUEUE'
                                                  ])

    def __init__(self, value, generic=False):
        # if generic is True, this means to use pbs_env() type in a
        # generic way, so that the PBS-related variables (e.g. PBS_O*)
        # are allowed to be modified.
        self._generic = generic
        if isinstance(value, str):
            # temporarily replace "<esc_char>," with something we
            # don't expect to see: two etx <ascii code 3>
            # since ',' is used as a separator among env variables.
            # NOTE: We take care here of also catching "\\," which is
            #       legal as in:  DPATH=\\a\\b\\,MP_MSG_API=MPI\,LAPI
            #       which must break down to:
            #           v['DPATH'] = "\\a\\b\\"
            #	       v['MP_MSG_API'] = "MPI\,LAPI"
            if (sys.platform == "win32"):
                esc_char = "^"
            else:
                esc_char = "\\"
            double_stx = "\x02\x02"
            double_etx = "\x03\x03"
            value1 = value.replace(
                esc_char + esc_char, double_stx).replace(esc_char + ",", double_etx)
            vals = value1.split(",")
            ev = {}
            for v in vals:
                # now restore "<esc_char>,"
                v1 = v.replace(double_etx, esc_char +
                               ",").replace(double_stx, esc_char + esc_char)
                e = v1.split("=", 1)

                if len(e) == 2:

                    vue = e[1]
                    if isinstance(e[1], str):
                        if (_pbs_v1.get_python_daemon_name() != "pbs_python") \
                                or (sys.platform != "win32"):
                            # replace \ with \\ if not used to escape special chars
                            # note: no need to do this under a Windows mom since
                            #       backslash is recognized as path character
                            vue = replace_char_not_before(e[1],
                                                          '\\', '\\\\', [',', '\'', '\"', '\\'])
                    ev.update({e[0]: vue})
        else:
            ev = value
        super().__init__(ev)
    #: m(__init__)

    def __setitem__(self, name, value):
        """__setitem__"""
        # pbs builtin variables are off limits except under a PBS hook
        if name in pbs_env._attributes_readonly and \
                _pbs_v1.in_python_mode() and _pbs_v1.in_site_hook() and \
                not getattr(self, "_generic"):
            raise BadAttributeValueError(
                "env variable '%s' is readonly" % (name,))
        v = value
        if isinstance(value, str):
            if (_pbs_v1.get_python_daemon_name() != "pbs_python") \
                    or (sys.platform != "win32"):
                # replace \ with \\ if not used to escape special chars
                # note: no need to do this on a Windows mom
                #       since backslash is recognized as path character
                v = replace_char_not_before(value, '\\', '\\\\',
                                            [',', '\'', '\"', '\\'])
        super().__setitem__(name, v)

    def __str__(self):
        """String representation of the object"""
        rv = ""
        for k in self.keys():
            if self[k] != None:
                rv += "%s=%s," % (k, self[k])
        return rv.rstrip(",")
    #: m(__str__)


class email_list(_generic_attr):
    """
    Represents the set of users to whom mail may be sent when a job makes
    certain state changes. Ex. Jobs Mail_Users attribute.
    Format: pbs.email_list(<email_address1>, <email address2>)
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Mail_Users", value)
        super().__init__(value)

# pbs_list is like email_list except less strict - "str" is allowed as a
# derived type.


class pbs_list(_generic_attr):
    _derived_types = (_generic_attr, str)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Mail_Users", value)
        super().__init__(value)


class pbs_bool(_generic_attr):
    _derived_types = (bool,)

    def __init__(self, value):
        if value in ("true", "True", "TRUE", "t", "T", "y", "1", 1):
            v = 1
        elif value in ("false", "False", "FALSE", "f", "F", "n", "0", 0):
            v = 0
        else:
            # should not end up here
            v = -1
        # validates against the 'Rerunable' attribute entry of the
        # the server 'job' table
        _pbs_v1.validate_input("job", "Rerunable", str(v))
        super().__init__(v)

    def __cmp__(self, value):
        iself = int(str(self))

        if value == None:
            return 1

        ivalue = int(value)

        if iself == ivalue:
            return 0
        elif iself > ivalue:
            return 1
        else:
            return -1

    def __bool__(self):
        if int(str(self)) == 1:
            return True
        else:
            return False

    def __int__(self):
        return int(str(self))


class pbs_int(int):
    _derived_types = (int, int, float)

    def __init__(self, value):
        # empty  string ("") also matched
        if value != "":
            _pbs_v1.validate_input("job", "ctime", str(int(value)))
        super().__init__()


class vnode_state(int):
    _derived_types = (int, int, float)

    def __init__(self, value):
        # empty  string ("") also matched
        if value != "":
            if _pbs_v1.vnode_state_to_str(int(value)) == "":
                raise BadAttributeValueError(
                    "invalid vnode state value '%s'" % (value,))

        super().__init__()

    def __add__(self, val):
        if _pbs_v1.vnode_state_to_str(val) == "":
            raise BadAttributeValueError(
                "invalid vnode state value '%d'" % (val,))
        return (self | val)

    def __sub__(self, val):
        if _pbs_v1.vnode_state_to_str(val) == "":
            raise BadAttributeValueError(
                "invalid vnode state value '%d'" % (val,))
        return (self & ~val)


class pbs_str(str):
    _derived_types = (str,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Job_Owner", value)
        super().__init__()


class pbs_float(float):
    _derived_types = (int, int, float)

    def __init__(self, value):
        _pbs_v1.validate_input("float", "", str(value))
        super().__init__()

#: ---------------------  SPECIAL VALUE TYPES ---------------------


class server_state(int):
    _derived_types = (int,)

    def __new__(cls, value):
        v = value
        if isinstance(value, str):
            # convert to the internal long value
            if value == "Hot_Start":
                v = _pbs_v1.SV_STATE_HOT
            elif value == "Active":
                v = _pbs_v1.SV_STATE_ACTIVE
            elif value == "Terminating_Delay":
                v = _pbs_v1.SV_STATE_SHUTDEL
            elif value == "Terminating":
                v = _pbs_v1.SV_STATE_SHUTIMM
            else:
                # not all server states are captured in this function,
                # so just default to 0 (instead of -1)
                v = 0
        return super().__new__(cls, v)


class queue_type(int):
    _derived_types = (int,)

    def __new__(cls, value):
        v = value
        if isinstance(value, str):
            # convert to the internal long value
            if (value == "Execution") or (value == "E"):
                v = _pbs_v1.QTYPE_EXECUTION
            elif value == "Route":
                v = _pbs_v1.QTYPE_ROUTE
            else:
                # should not get here
                v = -1
        return super().__new__(cls, v)


class job_state(int):
    _derived_types = (int,)

    def __new__(cls, value):
        v = value
        if isinstance(value, str):
            # convert to the internal long value
            if value == "T":
                v = _pbs_v1.JOB_STATE_TRANSIT
            elif value == "Q":
                v = _pbs_v1.JOB_STATE_QUEUED
            elif value == "H":
                v = _pbs_v1.JOB_STATE_HELD
            elif value == "W":
                v = _pbs_v1.JOB_STATE_WAITING
            elif value == "R":
                v = _pbs_v1.JOB_STATE_RUNNING
            elif value == "E":
                v = _pbs_v1.JOB_STATE_EXITING
            elif value == "X":
                v = _pbs_v1.JOB_STATE_EXPIRED
            elif value == "B":
                v = _pbs_v1.JOB_STATE_BEGUN
            elif value == "S":
                v = _pbs_v1.JOB_STATE_SUSPEND
            elif value == "U":
                v = _pbs_v1.JOB_STATE_SUSPEND_USERACTIVE
            elif value == "M":
                v = _pbs_v1.JOB_STATE_MOVED
            elif value == "F":
                v = _pbs_v1.JOB_STATE_FINISHED
            else:
                # should not get here
                v = -1
        return super().__new__(cls, v)


class acl(_generic_attr):
    """
    Represents a PBS ACL type.
    Format: pbs.acl("[+|-]<entity>][,...]")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("resv", "Authorized_Users", value)
        super().__init__(value)


class select(_generic_attr):
    """
    This represents the select resource specification when submitting a job.
    Format: pbs.select([N:]res=val[:res=val][+[N:]res=val[:res=val] ... ]")

    Ex. sel = pbs.select("2:ncpus=1:mem=5gb+3:ncpus=2:mem=5gb")
        s = repr(sel)	 or s = `sel`
        print s[2]  prints n
        s = s + "+5:scratch=10gb"  append to string
        sel = pbs.select(s)  reset the value of sel

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("resc", "select", value)
        super().__init__(value)

    def increment_chunks(self, increment_spec):
        """
        Given a pbs.select value (i.e. <num>:r1=v1:r2=v2+...+<num>:rn=vN),
        increase the number of chunks for each of the pbs.select chunk
        specs (except for the first chunk assigned to primary mom)
        by the 'increment' specification.
        The first chunk is the single chunk inside the first item
        in the plus-separated specs that is assigned to the
        primary mom. It is left as is.
        For instance, given a chunk specs of "3:ncpus=2+2:ncpus=4",
        this is viewed as "(1:ncpus=2+2:ncpus=2)+(2:ncpus=4)", and
        the increment specs described below would apply to the
        chunk after the initial, single chunk "1:ncpus=2".

        if 'increment_spec' is a number (int or long) or a numeric
        string,  then it will be the amount to add to the number of
        chunks spcified for each chunk that is not the first chunk
        in the pbs.select spec.

        if 'increment_spec' is a numeric string that ends with a percent
        sign (%), then this will be the percent amount of chunks to
        increase each chunk (except the first chunk) in the pbs.select spec.
        The resulting amount is rounded up (i.e. ceiling)
        (e.g. 1.23 rounds up to 2).

        Finally, if 'increment_spec' is a dictionary with elements of the
        form:
               {<chunk_index_to_select_spec> : <increment>, ...}
        where <chunk_index_to_select_spec> starts at 0 for the first
        chunk appearing in the plus-separated spec list,
        and <increment> can be numeric, numeric string or
        a percent increase value. This allow for individually
        specifying the number of chunks to increase original value.
        Note that for the first chunk in the list (0th index), the
        increment will apply to the chunks beyond the first chunk, which is
        assigned to the primary mom.

        Ex. Given:
            sel=pbs.select("ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb")

            Calling sel.increment_chunks(2) would return a string:
                "1:ncpus=3:mem=1gb+3:ncpus=2:mem=2gb+4:ncpus=1:mem=3gb"

            Calling sel.increment_chunks("3") would return a string:
                "1:ncpus=3:mem=1gb+4:ncpus=2:mem=2gb+5:ncpus=1:mem=3gb"

            Calling sel.increment_chunks("23.5%"), would return a
            pbs.select value mapping to:
                "1:ncpus=3:mem=1gb+2:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb"

            with the first chunk, which is a single chunk, is left as is,
            and the second and third chunks are increased by 23.5 %
            resulting in 1.24 rounded up to 2 and 2.47 rounded up to 3.

            Calling sel.increment_chunks({0: 0, 1: 4, 2: "50%"}), would
            return a pbs.select value mapping to:
                "1:ncpus=3:mem=1gb+5:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb"

            where no increase (0) for chunk 1, additional 4
            chunks for chunk 2, 50% increase for chunk 3 resulting in
            3.

            Given:
                sel=pbs.select("5:ncpus=3:mem=1gb+1:ncpus=2:mem=2gb+2:ncpus=1:mem=3gb")

            Then calling sel.increment_chunks("50%") or
            sel.increment_chunks({0: "50%", 1: "50%", 2: "50%}) would return a
            pbs.select value mapping to:
                "7:ncpus=3:mem=1gb+2:ncpus=2:mem=2gb+3:ncpus=1:mem=3gb"
            as for the first chunk, the initial single chunk of
            "1:ncpus=3:mem=1gb" is left as is, with the "50%" increase applied to
            the remaining chunks "4:ncpus=3:mem=1gb", and then added back to the
            single chunk to make 7, while chunks 2 and 3 are increased to 2 and 3,
            respectively.
        """
        increment = None
        percent_inc = None
        increment_dict = None
        if isinstance(increment_spec, (int, int)):
            increment = increment_spec
        elif isinstance(increment_spec, str):
            if increment_spec.endswith('%'):
                percent_inc = float(increment_spec[:-1]) / 100 + 1.0
            else:
                increment = int(increment_spec)
        elif isinstance(increment_spec, dict):
            increment_dict = increment_spec
        else:
            raise ValueError("bad increment specs")

        ret_str = ""
        i = 0  # index to each chunk in the + separated spec
        for chunk in str(self).split("+"):
            if i != 0:
                ret_str += '+'
            j = 0  # index to items within a chunk separated by ':'
            for subchunk in chunk.split(":"):
                c_str = subchunk
                if j == 0:
                    # given <chunk_ct>:<res1>=<val1>:<res2>=<val2> or
                    # <res1>=<val1>:<res2>:<val2> (without <chunk_ct>),
                    # here we're looking at the first field:
                    # subchunk=<chunk_ct> or subchunk=<res1>=<val1>
                    save_str = None
                    if not subchunk.isdigit():
                        # detected a first field that is not
                        # a <chunk_ct>, so default to 1
                        subchunk = "1"
                        save_str = c_str
                    chunk_ct = int(subchunk)

                    if i == 0:
                        chunk_ct -= 1  # don't touch the first chunk which lands in MS

                    if chunk_ct <= 0:
                        num = 0
                    elif increment:
                        num = chunk_ct + increment
                    elif percent_inc:
                        num = int(math.ceil(chunk_ct * percent_inc))
                    elif increment_dict is not None and i in increment_dict:
                        if isinstance(increment_dict[i], (int, int)):
                            inc = increment_dict[i]
                            num = chunk_ct + inc
                        elif isinstance(increment_dict[i], str):
                            if increment_dict[i].endswith('%'):
                                p_inc = float(
                                    increment_dict[i][:-1]) / 100 + 1.0
                                num = int(math.ceil(chunk_ct * p_inc))
                            else:
                                inc = int(increment_dict[i])
                                num = chunk_ct + inc
                    else:
                        raise ValueError("bad increment specs")

                    if (i == 0):
                        num += 1  # put back the decremented count

                    if save_str:
                        c_str = "%s:%s" % (num, save_str)
                    else:
                        c_str = "%s" % (num)
                else:
                    ret_str += ":"
                ret_str += c_str
                j += 1

            i += 1

        return select(ret_str)


class place(_generic_attr):
    """
    the place specification when submitting a job.
    Format: pbs.place("[arrangement]:[sharing]:[group]")
            where 	[arrangement] can be pack, scatter, free,
                        [sharing] can be shared, excl, and
                        [group] can be of the form group=<resource>.
                        [arrangement], [sharing], and [group] can be given
                        in any order or combination.
    Ex.	pl = pbs.place("pack:excl")
        s = repr(pl)	 or s = `pl`
        print pl[0]  returns p
        s = s + :group=host  append to string
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("resc", "place", value)
        super().__init__(value)


class vnode_sharing(int):
    _derived_types = (int, int, float)

    def __init__(self, value):
        if _pbs_v1.vnode_sharing_to_str(int(value)) == "":
            raise BadAttributeValueError(
                "invalid vnode sharing value '%s'" % (value,))
        super().__init__()


class vnode_ntype(int):
    _derived_types = (int, int, float)

    def __init__(self, value):
        if _pbs_v1.vnode_ntype_to_str(int(value)) == "":
            raise BadAttributeValueError(
                "invalid vnode ntype value '%s'" % (value,))
        super().__init__()


class exec_host(_generic_attr):
    """
    Represents a PBS exec_host.
    Format: pbs.exec_host("host/N[*C][+...]")
            where N are C are ints.
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "exec_host", value)
        super().__init__(value)


class checkpoint(_generic_attr):
    """
    Represents a job's checkpoint attribute.
    Format: pbs.checkpoint( <chkpnt_string> )
                where <chkpnt_string> must be one of "n", "s", "c", or "c=mmm"

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Checkpoint", value)
        super().__init__(value)


class depend(_generic_attr):
    """
    Represents a job's dependency attribute.
    Format: pbs.depend("<depend_string>")
                Creates a PBS dependency specification object out of
                the given <depend_string>. <depend_string> must be of
                "<type>:<jobid>[,<jobid>...]", or on:<count>.
                <type> is one of "after", "afterok",
                afterany", "before", "beforeok", and "beforenotok.
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "depend", value)
        super().__init__(value)


class group_list(_generic_attr):
    """
    Represents a list of group names.
    Format: pbs.group_list("<group_name>[@<host>][,<group_name>[@<host>]..]")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "group_list", value)
        super().__init__(value)


class user_list(_generic_attr):
    """
    Represents a list of user names.
    Format: pbs.user_list("<user>[@<host>][,<user>@<host>...]")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "User_List", value)
        super().__init__(value)


class path(_generic_attr):
    _derived_types = (_generic_attr, str)

    def __init__(self, value):
        # for windows
        val = value
        if isinstance(value, str):
            val = value.replace("\\", "/")
        _pbs_v1.validate_input("job", "Output_Path", val)
        super().__init__(val)


class sandbox(_generic_attr):
    _derived_types = (_generic_attr, str)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "sandbox", value)
        super().__init__(value)


class priority(_generic_attr):
    _derived_types = (_generic_attr, int)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Priority", str(value))
        super().__init__(value)


class name(_generic_attr):
    _derived_types = (_generic_attr, str)

    def __init__(self, value):
        # Validate only if set inside a hook script and not internally
        # by PBS.
        if _pbs_v1.in_python_mode():
            _pbs_v1.validate_input("job", "Job_Name", value)
        super().__init__(value)


class project(_generic_attr):
    _derived_types = (_generic_attr, str)

    def __init__(self, value):
        # Validate only if set inside a hook script and not internally
        # by PBS.
        if _pbs_v1.in_python_mode():
            _pbs_v1.validate_input("job", "project", value)
        super().__init__(value)


class join_path(_generic_attr):
    """
    Represents how the output and error files are merged.
    Format: pbs.join_path({oe|eo|n})
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Join_Path", value)
        super().__init__(value)


class path_list(_generic_attr):
    """
    Represents a list of pathnames.
    Format: pbs.path_list("<path>[@<host>][,<path>@<host> ...]")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        # for windows
        val = value
        if isinstance(value, str):
            val = value.replace("\\", "/")
        _pbs_v1.validate_input("job", "Shell_Path_List", val)
        super().__init__(val)


class hold_types(_generic_attr):
    """
    Represents the Hold_Types attribute of a job.
    Format: pbs.hold_types(<hold_type_str>)
                where <hold_type_str> is one of "u", "o", "s",  or ("n" or "p").

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        """
        Instantiates an pbs.holdtypes() value.
        """
        _pbs_v1.validate_input("job", "Hold_Types", value)
        self.opval = "__init__"
        super().__init__(value)

    def __add__(self, val):
        """
        Returns a new value containing the Hold_Types values in
        self._value plus the the Hold_Types values in val.
        This also ensures that each character in val will appear
        only once in the new value.
        Example:
                Given: pbs.event().job.Hold_types = "o"
                        pbs.event().job.Hold_Types += pbs.hold_types("uos")
                -> pbs.event().job.Hold_Types = uos
        """
        sdict = {}
        for c in self._value:
            sdict[c] = ""
        for c in str(val):
            sdict[c] = ""
        nval = "".join(list(sdict.keys()))

        # nval will get validated inside hold_types instantiation
        h = hold_types(nval)
        h.opval = "__add__"
        return h

    def __sub__(self, val):
        """
        Returns a new value containing the Hold_Types values
        in self._value, but with the Hold_Types values in val
        taken out.
        Example:
            Given: pbs.event().job.Hold_types = os
                   pbs.event().job.Hold_Types  -= pbs.hold_types("us")
                                         -> pbs.event().job.Hold_types = o
        """
        sdict = {}
        # string that holds deleted Hold_Types values
        deleted_vals = ""
        for c in self._value:
            sdict[c] = ""
        for c in str(val):
            if c in list(sdict.keys()):
                del sdict[c]
                deleted_vals += c
        nval = "".join(list(sdict.keys()))

        # nval will get validated inside hold_types instantiation
        if nval == "":
            nval = "n"
        h = hold_types(nval)
        h.opval = "__sub__"
        h.delval = deleted_vals
        return h


class keep_files(_generic_attr):
    """
    Represents the Keep_Files job attribute.
    Format: pbs.keep_files(<keep_files_str>)
                where <keep_files_str> is one of "o", "e", "oe", "eo".

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Keep_Files", value)
        super().__init__(value)


class mail_points(_generic_attr):
    """
    Represents the Mail_Points attribute of a job.
    Format: pbs.mail_points("<mail_points_string>")
                Creates a PBS Mail_Points object, where
                <mail_points_string> is "a", "b", and/or "e", or n.
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "Mail_Points", value)
        super().__init__(value)


class staging_list(_generic_attr):
    """
    Represents a list of file stagein or stageout parameters.
    Format: pbs.staging_list("<filespec>[,<filespec>,...]")
                Creates a file staging parameters list object.
                where <filespec> is
                        <local_path>@<remote_host>:<remote_path>
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        val = value
        if isinstance(value, str):
            val = value.replace("\\", "/")
            val = val.replace("/,", "\\,")
        _pbs_v1.validate_input("job", "stagein", val)
        super().__init__(val)


class range(_generic_attr):
    """
    Represents a range of numbers referring to job array.
    Format: pbs.range("<start>-<stop>:<end>")
                Creates a PBS object representing a range of values.
                Ex. pbs.range(1-30:3)

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "array_indices_submitted", value)
        super().__init__(value)


class state_count(_generic_attr):
    """
    Represents a set of job-related state counters.
    Format: pbs.state_count("Transit:<U> Queued:<V> Held:<W> Running:<X> Exiting:<Y> Begun:<Z>")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        # validates against the 'state_account' attribute entry of the
        # the server 'server' table
        _pbs_v1.validate_input("server", "state_count", value)
        super().__init__(value)


class license_count(_generic_attr):
    """
    Represents a set of licensing-related counters.
    Format: pbs.license_count("Avail_Global:<W> Avail_Local:<X> Used:<Y> High_Use:<Z>")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("server", "license_count", value)
        super().__init__(value)


class route_destinations(_generic_attr):
    """
    Represents the "route_destinations" attribute of a queue.
    Format: pbs.route_destinations(("<queue_spec>[,<queue_spec>,...]"
                Creates an object that represents route_destinations routing
                queue attribute. <queue_spec> is
                "queue_name[@server_host[:port]]"
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        # validates against the 'state_account' attribute entry of the
        # the server 'queue' table
        _pbs_v1.validate_input("queue", "route_destinations", value)
        super().__init__(value)


class args(_generic_attr):
    """
    Represents a space-separated list of PBS arguments to commands like
    qsub, qdel.
    Format: pbs.args(<space-separated PBS args to commands like qsub, qdel>)
                Ex. pbs.args("-Wsuppress_mail=N r y")
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("server", "default_qsub_arguments", value)
        super().__init__(value)


class job_sort_formula(_generic_attr):
    """
    Represents the job_sort_formula server attribute.
    Format: pbs.job_sort_formula(<string containing math formula>)
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        # treat as string for now
        if not isinstance(value, str):
            raise BadAttributeValueError(
                "job_sort_formula value '%s' not a string" % (value,))
        super().__init__(value)


class node_group_key(_generic_attr):
    """
    Represents the node group key atribute.
    Format: pbs.node_group_key(<resource>)
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("queue", "node_group_key", value)
        super().__init__(value)


class version(_generic_attr):
    """
    Represents a version information for PBS.
    Format: pbs.version(<pbs version string>)
    """
    _derived_types = (str, _generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("server", "pbs_version", value)
        super().__init__(value)


class software(_generic_attr):
    """
    Represents a site-dependent software specification resource.
    Format: pbs.software(<software info string>)
    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("resc", "software", value)
        super().__init__(value)


#:-------------------------------------------------------------------------
#                       RESOURCE TYPE
#:-------------------------------------------------------------------------
class pbs_resource():
    """A generic python representation of PBS resource type.

    This leverages the Python descriptor mechanism to expose all the resources
    as attributes.

    """

    __resources = PbsReadOnlyDescriptor('__resources', {})
    attributes = __resources
    _attributes_hook_set = weakref.WeakKeyDictionary()
    _attributes_unknown = weakref.WeakKeyDictionary()

    def __init__(self, name, is_entity=0):
        """__init__"""

        #: name could be an instance of pbs_resource, in that case we are
        #: actually creating a new instance of pbs_resource, this happens
        #: when the attributes are actually setup by parent.
        if isinstance(name, pbs_resource):
            name = name._name
            #: set all the attribute descriptors resc_attr to name
            for a in pbs_resource.attributes:
                #: get the descriptor
                descr = getattr(pbs_resource, a)
                if isinstance(descr, PbsAttributeDescriptor):
                    descr._set_resc_atttr(name, is_entity)
                #:
            #:
        self._name = name
        self._readonly = False
        self._has_value = True
        self._is_entity = is_entity
    #: m(__init__)

    def __str__(self):
        """
        """
        if not self._has_value:
            # return the cached value
            return str(_pbs_v1.resource_str_value(self))

        rv = []

        d = pbs_resource.attributes.copy()

        if self in pbs_resource._attributes_unknown:
            # update pbs_resource list of attribute names to contain the
            # "unknown" names as well.
            d.update(pbs_resource._attributes_unknown[self])

        for resc in d:
            if resc == '_name' or resc == '_has_value':
                continue
            v = getattr(self, resc)
            if (v != None) or (v == ""):
                str_v = str(v)
                if (str_v.find("\"") == -1) and (str_v.find(",") != -1):
                    rv.append("%s=\"%s\"" % (resc, v))
                else:
                    rv.append("%s=%s" % (resc, v))
            #
        #
        return ",".join(rv)
    #: m(__str__)

    def __getitem__(self, resname):
        """__getitem__"""
        if not self._has_value:
            # load the cached resource value
            _pbs_v1.load_resource_value(self)

        return getattr(self, resname)
    #: m(__getitem__)

    def __setitem__(self, resname, resval):
        """__setitem__"""

        if not self._has_value:
            # load the cached resource value
            _pbs_v1.load_resource_value(self)
        setattr(self, resname, resval)
    #: m(__setitem__)

    def __contains__(self, resname):
        """__contains__"""

        return hasattr(self, resname)
    #: m(__contains__)

    def __setattr__(self, nameo, value):
        """__setattr__"""

        name = nameo
        if (nameo == "_readonly"):
            if _pbs_v1.in_python_mode() and \
                    hasattr(self, "_readonly") and not value:
                raise BadResourceValueError(
                    "_readonly can only be set to True!")
        elif (nameo != "_has_value") and (nameo != "_is_entity"):
            # _has_value is a special, resource attribute that tells if a
            # resource instance is already holding its value (i.e. value
            # is not cached somewhere else).
            # _is_entity is also a special attribute that tells if the
            # resource instance is an entity resource type.

            # resource names in PBS are case insensitive,
            # so do caseless matching here.
            found = False
            namel = nameo.lower()
            for resc in pbs_resource.attributes:
                rescl = resc.lower()
                if namel == rescl:
                    # Need to use the matched name stored in PBS Python resource
                    # table, to avoid resource ambiguity later on.
                    name = resc
                    found = True

            if not found:

                if _pbs_v1.in_python_mode():
                    # if attribute name not found,and executing inside Python
                    # script
                    if _pbs_v1.get_python_daemon_name() != "pbs_python":
                        # we're in a server hook
                        raise UnsetResourceNameError(
                            "resource attribute '%s' not found" % (name,))

                    # we're in a mom hook, so no longer raising an exception here since if
                    # it's an unknown resource, we can now tell server to
                    # automatically add a custom resource.
                    if self not in self._attributes_unknown:
                        self._attributes_unknown[self] = {}
                    # add the current attribute name to the "unknown" list
                    self._attributes_unknown[self].update({name: None})
                else:
                    if self not in self._attributes_unknown:
                        self._attributes_unknown[self] = {}
                    # add the current attribute name to the "unknown" list
                    self._attributes_unknown[self].update({name: None})

        super().__setattr__(name, value)

        # attributes that are set in python mode will be reflected in
        # _attributes_hook_set dictionary.
        # For example,
        # _attributes_hook_set[<pbs_resource object>]=['walltime', 'mem']
        # if 'walltime' or 'mem' has been assigned a value within the hook
        # script, or been unset.
        if _pbs_v1.in_python_mode():
            if self not in self._attributes_hook_set:
                self._attributes_hook_set[self] = {}
            # using a dictionary value as easier to search for keys
            self._attributes_hook_set[self].update({name: None})
    #: m(__setattr__)

    def keys(self):
        """
        Returns keys that have non-empty values.
        """
        rv = []
        for resc in pbs_resource.attributes:
            if resc == '_name' or resc == '_has_value':
                continue
            v = getattr(self, resc)
            if v != None:
                rv.append(resc)
        #
        return rv
    #: m(keys)


#: C(pbs_resource)
pbs_resource._name = PbsAttributeDescriptor(pbs_resource, '_name',
                                            "<generic resource>", (str,))


class vchunk():
    """
    This represents a resource chunk assigned to a job.
    Format: pbs.vchunk("<vnodeN>:<res1>=<val1>:<res2>=<val2>:...:<resN>=<valN>")
         where vnodeN is a name of a vnode.
    """

    def __init__(self, achunk):
        """__init__"""

        ch = achunk.split(":")
        self.chunk_resources = pbs_resource("Resource_List")
        for c in ch:
            if c.find("=") == -1:
                self.vnode_name = c
            else:
                rs = c.split("=", 1)
                descr = getattr(pbs_resource, rs[0])
                self.chunk_resources[rs[0]] = descr._value_type[0](rs[1])
    #: m(__init__)


class exec_vnode(_generic_attr):
    """
    Represents a PBS exec_vnodes
    Format: ev = pbs.exec_vnode(
                (vnodeA:ncpus=N:mem=X)+(vnodeB:ncpus=P:mem=Y+vnodeC:mem=Z))
                where vnodeA, ..., vnodeC are names of vnodes.
            ev.chunks returns an array of pbs.vchunk job objects representing
            that will show:
            ev.chunks[0].vnode_name = 'vnodeA'
            ev.chunks[0].vnode_resources = {  'ncpus' : N, 'mem' : pbs.size('X') }

            ev.chunks[1].vnode_name = 'vnodeB'
            ev.chunks[1].vnode_resources = {  'ncpus' : P, 'mem' : pbs.size('Y') }
            ev.chunks[1].vnode_name = 'vnodeC'
            ev.chunks[1].vnode_resources = {  'mem' : pbs.size('Z') }

    """
    _derived_types = (_generic_attr,)

    def __init__(self, value):
        _pbs_v1.validate_input("job", "exec_vnode", value)
        super().__init__(value)
        self.chunks = list()
        vals = value.split("+")
        i = 0
        for v in vals:
            self.chunks.append(vchunk(v.strip("(").strip(")")))
#: --------         EXPORTED TYPES DICTIONARY                      ---------
