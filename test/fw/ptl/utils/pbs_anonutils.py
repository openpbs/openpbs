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

import logging
import os
import copy
import shlex
import re

from ptl.lib.pbs_testlib import BatchUtils,  PbsTypeFGCLimit
from ptl.lib.pbs_ifl_mock import *
from ptl.utils.pbs_dshutils import DshUtils


ANON_USER_K = "user"
ANON_GROUP_K = "group"
ANON_HOST_K = "host"
ANON_JOBNAME_K = ATTR_name
ANON_ACCTNAME_K = ATTR_A


class PBSAnonymizer(object):

    """
    Holds and controls anonymizing operations of PBS data

    The anonymizer operates on attributes or resources.
    Resources operate on the resource name itself rather than
    the entire name, for example, to obfuscate the values associated
    to a custom resource "foo" that could be set as resources_available.
    foo resources_default.foo or Resource_List.foo, all that needs to be
    passed in to the function is "foo" in the list to obfuscate.

    :param attr_key: Attributes for which the attribute names themselves
                    should be obfuscated
    :type attr_key: list or None
    :param attr_val: Attributes for which the values should be obfuscated
    :type attr_val: list or None
    :param resc_key: Resources for which the resource names themselves should
                    be obfuscated
    :type resc_key: list or None
    :param resc_val: Resources for which the values should be obfuscated
    :type resc_val: list or None
    """

    logger = logging.getLogger(__name__)
    utils = BatchUtils()
    du = DshUtils()

    def __init__(self, attr_delete=None, resc_delete=None,
                 attr_key=None, attr_val=None,
                 resc_key=None, resc_val=None):

        # special cases
        self._entity = False
        self.job_sort_formula = None
        self.schedselect = None
        self.select = None

        self.set_attr_delete(attr_delete)
        self.set_resc_delete(resc_delete)
        self.set_attr_key(attr_key)
        self.set_attr_val(attr_val)
        self.set_resc_key(resc_key)
        self.set_resc_val(resc_val)
        self.anonymize = self.anonymize_batch_status

        # global anonymized mapping data
        self.gmap_attr_val = {}
        self.gmap_resc_val = {}
        self.gmap_attr_key = {}
        self.gmap_resc_key = {}
        self.num_bad_acct_records = 0

    def __get_anon_key(self, key, attr_map):
        """
        Get an anonymized string for the 'key' belonging to attr_map

        :param key: the key to anonymize
        :type key: String
        :param attr_map: the attr_map to which the key belongs
        :type attr_map: dict

        :returns: an anonymized string for the key
        """
        key = self.__refactor_key(key)

        if key in list(attr_map.keys()):
            anon_key = attr_map[key]
        else:
            anon_key = self.utils.random_str(len(key))
            attr_map[key] = anon_key

        return anon_key

    @staticmethod
    def __refactor_key(key):
        """
        There are some attributes which are aliases of each other
        and others which are lists like user/group lists, lists of hosts etc.
        Set a common key for them.
        """
        key_lower = key.lower()
        if "user" in key_lower or key == "requestor":
            key = ANON_USER_K
        elif "group" in key_lower:
            key = ANON_GROUP_K
        elif "host" in key_lower:
            key = ANON_HOST_K
        elif key == "Name" or key == "Jobname":
            key = ANON_JOBNAME_K
        elif key == "account":
            key = ANON_ACCTNAME_K

        return key

    def __get_anon_value(self, key, value, kv_map):
        """
        Get an anonymied string for the 'value' belonging to the kv_map
        provided.
        The kv_map will be in the following format:
            key:{val1:anon_val1, val2:anon_val2, ...}

        :param key: the key for this value
        :type key: String
        :param value: the value to anonymize
        :type value: String
        :param kv_map: the kv_map to which the key belongs
        :type kv_map: dict

        :returns: an anonymized string for the value
        """

        if key == "project" and value == "_pbs_project_default":
            return "_pbs_project_default"

        # Deal with attributes which have a list of values
        if key in (ATTR_u, ATTR_managers, ATTR_M, ATTR_g, ATTR_aclResvhost,
                   ATTR_aclhost, ATTR_auth_g, ATTR_auth_u):
            value_temp = "".join(value.split())
            value_list = value_temp.split(",")
        elif key == ATTR_exechost:
            value_list = []
            value_list_temp = value.split("+")
            for item in value_list_temp:
                value_list.append(item.split("/")[0])
        else:
            value_list = [value]

        key = self.__refactor_key(key)

        # Go through the list of values and anonymize each in the value string
        for val in value_list:
            if "@" in val:
                # value if of type "user@host"
                # anonymize the user and host parts separately
                if ANON_HOST_K in self.attr_val:
                    try:
                        user, host = val.split("@")
                        host = self.__get_anon_value(ANON_HOST_K, host,
                                                     self.gmap_attr_val)
                        user = self.__get_anon_value(ANON_USER_K, user,
                                                     self.gmap_attr_val)
                        anon_val = user + "@" + host
                        value = value.replace(val, anon_val)
                        continue
                    except Exception:
                        pass

            if key in kv_map:
                value_map = kv_map[key]
                anon_val = self.__get_anon_key(val, value_map)
            else:
                anon_val = self.utils.random_str(len(val))
                kv_map[key] = {val: anon_val}
            value = value.replace(val, anon_val)

        return value

    def _initialize_key_map(self, keys):
        k = {}
        if keys is not None:
            if isinstance(keys, dict):
                return keys
            elif isinstance(keys, list):
                for i in keys:
                    k[i] = None
            elif isinstance(keys, str):
                for i in keys.split(","):
                    k[i] = None
            else:
                self.logger.error("unhandled map type")
                k = {None: None}
        return k

    def _initialize_value_map(self, keys):
        k = {}
        if keys is not None:
            if isinstance(keys, dict):
                return keys
            elif isinstance(keys, list):
                for i in keys:
                    k[i] = {}
            elif isinstance(keys, str):
                for i in keys.split(","):
                    k[i] = {}
            else:
                self.logger.error("unhandled map type")
                k = {None: None}
        return k

    def set_attr_delete(self, ad):
        """
        Name of attributes to delete

        :param ad: Attributes to delete
        :type ad: str or list or dictionary
        """
        self.attr_delete = self._initialize_value_map(ad)

    def set_resc_delete(self, rd):
        """
        Name of resources to delete

        :param rd: Resources to delete
        :type rd: str or list or dictionary
        """
        self.resc_delete = self._initialize_value_map(rd)

    def set_attr_key(self, ak):
        """
        Name of attributes to obfuscate.

        :param ak: Attribute keys
        :type ak: str or list or dictionary
        """
        self.attr_key = self._initialize_key_map(ak)

    def set_attr_val(self, av):
        """
        Name of attributes for which to obfuscate the value

        :param av: Attributes value to obfuscate
        :type av: str or list or dictionary
        """
        self.attr_val = self._initialize_value_map(av)
        if ("euser" or "egroup" or "project") in self.attr_val:
            self._entity = True

    def set_resc_key(self, rk):
        """
        Name of resources to obfuscate

        :param rk: Resource key
        :type rk: str or list or dictionary
        """
        self.resc_key = self._initialize_key_map(rk)

    def set_resc_val(self, rv):
        """
        Name of resources for which to obfuscate the value

        :param rv: Resource value to obfuscate
        :type rv: str or list or dictionary
        """
        self.resc_val = self._initialize_value_map(rv)

    def set_anon_map_file(self, name):
        """
        Name of file in which to store anonymized map data.
        This file is meant to remain private to a site as it
        contains the sensitive anonymized data.

        :param name: Name of file to which anonymized data to store.
        :type name: str
        """
        self.anon_map_file = name

    def anonymize_resource_group(self, filename):
        """
        Anonymize the user and group fields of a resource
        group filename

        :param filename: Resource group filename
        :type filename: str
        """
        anon_rg = []

        try:
            f = open(filename)
            lines = f.readlines()
            f.close()
        except IOError:
            self.logger.error("Error processing " + filename)
            return None

        for data in lines:
            data = data.strip()
            if data:
                if data[0] == "#":
                    continue

                _d = data.split()
                ug = _d[0]
                if ":" in ug:
                    (euser, egroup) = ug.split(":")
                else:
                    euser = ug
                    egroup = None

                if "euser" not in self.attr_val:
                    anon_euser = euser
                else:
                    anon_euser = None
                    if ANON_USER_K in self.gmap_attr_val:
                        if euser in self.gmap_attr_val[ANON_USER_K]:
                            anon_euser = self.gmap_attr_val[ANON_USER_K][euser]
                    else:
                        self.gmap_attr_val[ANON_USER_K] = {}

                if euser is not None and anon_euser is None:
                    anon_euser = self.utils.random_str(len(euser))
                    self.gmap_attr_val[ANON_USER_K][euser] = anon_euser

                if "egroup" not in self.attr_val:
                    anon_egroup = egroup
                else:
                    anon_egroup = None

                    if egroup is not None:
                        if ANON_GROUP_K in self.gmap_attr_val:
                            if egroup in self.gmap_attr_val[ANON_GROUP_K]:
                                anon_egroup = (self.gmap_attr_val[ANON_GROUP_K]
                                               [egroup])
                        else:
                            self.gmap_attr_val[ANON_GROUP_K] = {}

                if egroup is not None and anon_egroup is None:
                    anon_egroup = self.utils.random_str(len(egroup))
                    self.gmap_attr_val[ANON_GROUP_K][egroup] = anon_egroup

                # reconstruct the fairshare info by combining euser and egroup
                out = [anon_euser]
                if anon_egroup is not None:
                    out[0] += ":" + anon_egroup
                # and appending the rest of the original line
                out.append(_d[1])
                if len(_d) > 1:
                    p = _d[2].strip()
                    if (ANON_USER_K in self.gmap_attr_val and
                            p in self.gmap_attr_val[ANON_USER_K]):
                        out.append(self.gmap_attr_val[ANON_USER_K][p])
                    else:
                        out.append(_d[2])
                if len(_d) > 2:
                    out += _d[3:]
                anon_rg.append(" ".join(out))

        return anon_rg

    def anonymize_resource_def(self, resources):
        """
        Anonymize the resource definition
        """
        if not self.resc_key:
            return resources

        for curr_anon_resc, val in self.resc_key.items():
            if curr_anon_resc in resources:
                tmp_resc = copy.copy(resources[curr_anon_resc])
                del resources[curr_anon_resc]
                if val is None:
                    if curr_anon_resc in self.gmap_resc_key:
                        val = self.gmap_resc_key[curr_anon_resc]
                    else:
                        val = self.utils.random_str(len(curr_anon_resc))
                elif curr_anon_resc not in self.gmap_resc_key:
                    self.gmap_resc_key[curr_anon_resc] = val
                tmp_resc.set_name(val)
                resources[val] = tmp_resc
        return resources

    def __anonymize_fgc(self, d, attr, ar, val):
        """
        Anonymize an FGC limit value
        """

        m = {"u": "euser", "g": "egroup", "p": "project"}

        if "," in val:
            fgc_lim = val.split(",")
        else:
            fgc_lim = [val]

        nfgc = []
        for lim in fgc_lim:
            _fgc = PbsTypeFGCLimit(attr, lim)
            ename = _fgc.entity_name
            if ename in ("PBS_GENERIC", "PBS_ALL"):
                nfgc.append(lim)
                continue

            obf_ename = ename
            for etype, nm in m.items():
                if _fgc.entity_type == etype:
                    if nm not in self.gmap_attr_val:
                        if nm in ar and ename in ar[nm]:
                            obf_ename = ar[nm][ename]
                        else:
                            obf_ename = self.utils.random_str(len(ename))
                        self.gmap_attr_val[nm] = {ename: obf_ename}
                    elif ename in self.gmap_attr_val[nm]:
                        if ename in self.gmap_attr_val[nm]:
                            obf_ename = self.gmap_attr_val[nm][ename]
                    break
            _fgc.entity_name = obf_ename
            nfgc.append(_fgc.__val__())

        d[attr] = ",".join(nfgc)

    def __anonymize_attr_val(self, d, attr, ar, name, val):
        """
        Obfuscate an attribute/resource values
        """

        # don't obfuscate default project
        if attr == "project" and val == "_pbs_project_default":
            return

        nstr = []
        if "." in attr:
            m = self.gmap_resc_val
        else:
            m = self.gmap_attr_val

        if val in ar[name]:
            nstr.append(ar[name][val])
            if name in self.lmap:
                self.lmap[name][val] = ar[name][val]
            else:
                self.lmap[name] = {val: ar[name][val]}
            if name not in m:
                m[name] = {val: ar[name][val]}
            elif val not in m[name]:
                m[name][val] = ar[name][val]
        else:
            # Obfuscate by randomizing with a value of the same length
            tmp_v = val.split(",")
            for v in tmp_v:
                if v in ar[name]:
                    r = ar[name][v]
                elif name in m and v in m[name]:
                    r = m[name][v]
                else:
                    r = self.utils.random_str(len(v))
                    if not isinstance(ar[name], dict):
                        ar[name] = {}
                    ar[name][v] = r
                self.lmap[name] = {v: r}
                if name not in m:
                    m[name] = {v: r}
                elif v not in m[name]:
                    m[name][v] = r

                nstr.append(r)

        if d is not None:
            d[attr] = ",".join(nstr)

    def __anonymize_attr_key(self, d, attr, ar, name, res):
        """
        Obfuscate an attribute/resource key
        """

        if res is not None:
            m = self.gmap_resc_key
        else:
            m = self.gmap_attr_key

        if not ar[name]:
            if name in m:
                ar[name] = m[name]
            else:
                randstr = self.utils.random_str(len(name))
                ar[name] = randstr
                m[name] = randstr

        if d is not None:
            tmp_val = d[attr]
            del d[attr]

            if res is not None:
                d[res + "." + ar[name]] = tmp_val
            else:
                d[ar[name]] = tmp_val

        if name not in self.lmap:
            self.lmap[name] = ar[name]

        if name not in m:
            m[name] = ar[name]

    def anonymize_batch_status(self, data=None):
        """
        Anonymize arbitrary batch_status data

        :param data: Batch status data
        :type data: List or dictionary
        """
        if not isinstance(data, (list, dict)):
            self.logger.error("data expected to be dict or list")
            return None

        if isinstance(data, dict):
            dat = [data]
        else:
            dat = data

        # Local mapping data used to store obfuscation mapping data for this
        # specific item, d
        self.lmap = {}

        # loop over each "batch_status" entry to obfuscate
        for d in dat:

            if self.attr_delete is not None:
                for todel in self.attr_delete:
                    if todel in d:
                        del d[todel]

            if self.resc_delete is not None:
                for todel in self.resc_delete:
                    for tmpk in d.keys():
                        if "." in tmpk and todel == tmpk.split(".")[1]:
                            del d[tmpk]

            # Loop over each object's attributes, this is where the special
            # cases are handled (e.g., FGC limits, formula, select spec...)
            for attr in d:
                val = d[attr]

                if "." in attr:
                    (res_type, res_name) = attr.split(".")
                else:
                    res_type = None
                    res_name = attr

                if res_type is not None:
                    if self._entity and (attr.startswith("max_run") or
                                         attr.startswith("max_queued")):
                        self.__anonymize_fgc(d, attr, self.attr_val,
                                             val)

                    if res_name in self.resc_val:
                        if (attr.startswith("max_run") or
                                attr.startswith("max_queued")):
                            self.__anonymize_fgc(d, attr, self.attr_val,
                                                 val)
                        self.__anonymize_attr_val(d, attr, self.resc_val,
                                                  res_name, val)

                    if res_name in self.resc_key:
                        self.__anonymize_attr_key(d, attr, self.resc_key,
                                                  res_name, res_type)
                else:
                    if attr in self.attr_val:
                        self.__anonymize_attr_val(d, attr, self.attr_val,
                                                  attr, val)

                    if attr in self.attr_key:
                        self.__anonymize_attr_key(d, attr, self.attr_key,
                                                  attr, None)

                    if ((attr in ("job_sort_formula", "schedselect",
                                  "select")) and self.resc_key):
                        for r in self.resc_key:
                            if r in val:
                                if r not in self.gmap_resc_key:
                                    self.gmap_resc_key[
                                        r] = self.utils.random_str(len(r))
                                val = val.replace(r, self.gmap_resc_key[r])
                                setattr(self, attr, val)

                        d[attr] = val

    @staticmethod
    def __verify_key(line, key):
        """
        Verify that a given key is actually a key in the context of the line
        given.

        :param line: the line to check in
        :type line: String
        :param key: the key to find
        :type key: String

        :returns a tuple of (key index, 1st character of key's value)
        :returns None if the key is invalid
        """
        line_len = len(line)
        key_len = len(key)
        key_index = line.find(key, 0, line_len)
        line_nospaces = "".join(line.split())
        len_nospaces = len(line_nospaces)
        key_idx_nospaces = line_nospaces.find(key, 0, len_nospaces)
        value_char = None

        # Find all instances of the string representing key in the line
        # Find the instance which is a valid key
        while key_index >= 0 and key_index < line_len:
            valid_key = True

            # Make sure that the characters before & after are not alpanum
            if key_index != 0:
                index_before = key_index - 1
                char_before = line[index_before]
                if char_before.isalnum() is True:
                    valid_key = False
            else:
                char_before = None
            if valid_key is True:
                if key_index < line_len:
                    index_after = key_index + key_len
                    char_after = line[index_after]
                    if char_after.isalnum() is True:
                        valid_key = False
                else:
                    char_after = None
                if valid_key is True:
                    # if 'char_after' is not "=", then the characters before
                    # and after should be the delimiter, and be equal
                    if char_before is not None and char_after is not None:
                        if char_after != "=":
                            if char_before != char_after:
                                valid_key = False
                    if valid_key is True:
                        # Now, let's look at the whitespace stripped line
                        index_after = key_idx_nospaces + key_len
                        if index_after >= len_nospaces:
                            # Nothing after the key, can't be a key
                            valid_key = False
                        else:
                            # Find a valid operator after the key
                            # valid operators: =, +=, -=, ==
                            if line_nospaces[index_after] != "=":
                                # Check for this case: "key +=/-=/== value"
                                if line_nospaces[index_after] in ("+", "-"):
                                    index_after = index_after + 1
                                    if line_nospaces[index_after] != "=":
                                        valid_key = False
                                else:
                                    valid_key = False
                            if valid_key is True:
                                val_idx_nospaces = index_after + 1
                                if val_idx_nospaces >= len_nospaces:
                                    # There's no value!, can't be a valid key
                                    valid_key = False

            if valid_key is False:
                # Find the next instance of the key
                key_index = line.find(key, key_index + len(key), line_len)
                key_idx_nospaces = line_nospaces.find(key,
                                                      key_idx_nospaces +
                                                      len(key),
                                                      len_nospaces)
            else:
                # Seems like a valid key!
                # Break out of the loop
                value_char = line_nospaces[val_idx_nospaces]
                break

        if key_index == -1 or key_idx_nospaces == -1:
            return None

        return (key_index, value_char)

    def __get_value(self, line, key):
        """
        Get the 'value' of a kv pair for the key given, from the line given

        :param line: the line to search in
        :type line: String
        :param key: the key for the value
        :type key: String

        :returns: String containing the value or None
        """
        # Check if the line is of type:
        #     <attribute name> = <value>
        line_list_spaces = line.split()
        if line_list_spaces is not None:
            first_word = line_list_spaces[0]
            if key == first_word:
                # Check that this word is followed by an '=' sign
                equals_sign = line_list_spaces[1]
                if equals_sign == "=":
                    # Ok, we are going to assume that this is enough to
                    # determine that this is the correct type
                    # return everything after the '=" as value
                    val_index = line.index("=") + 1
                    value = line[val_index:].strip()
                    return value

        # Check that a valid instance of this key exists in the string
        kv = self.__verify_key(line, key)
        if kv is None:
            return None
        key_index, val_char = kv

        # Assumption: the character before the key is the delimiter
        # for the k-v pair
        delimiter = line[key_index - 1]
        if delimiter is None:
            # Hard luck, now there's no way to know, let's just assume
            # that space is the delimiter and hope for the best
            delimiter = " "

        # Determine the value's start index
        index_after_key = key_index + len(key)
        value_index = line[index_after_key:].find(val_char) + index_after_key

        # Get the value
        lexer = shlex.shlex(line[value_index:], posix=True)
        lexer.whitespace = delimiter
        lexer.whitespace_split = True
        try:
            value = lexer.get_token()
        except ValueError:
            # Sometimes, the data can be incoherent with things like
            # Unclosed quotes, which makes get_token() throw an exception
            # Just return None
            return None

        # Strip the value of any trailing whitespaces (like newlines)
        value = value.rstrip()

        return value

    @staticmethod
    def __delete_kv(line, key, value):
        """
        Delete a key-value pair from a line
        If after deleting the k-v pair, the left over string has
        no alphanumeric characters, then delete the line

        :param line: the line in question
        :type line: String
        :param key: the key ofo the kv pair
        :type key: String
        :param value: the value of the kv pair
        :type value: String

        :returns: the line without the kv pair
        :returns: None if the line should be deleted
        """
        key_index = line.find(key)
        index_after_key = key_index + len(key)
        line_afterkey = line[index_after_key:]
        value_index = line_afterkey.find(value) + index_after_key

        # find the index of the last character of value
        end_index = value_index + len(value)

        # Find the start index of the kv pair
        # Also include the character before the key
        # This will remove an extra delimiter that would be
        # left after the kv pair is deleted
        start_index = key_index - 1
        if start_index < 0:
            start_index = 0

        # Remove the kv pair
        line = line[:start_index] + line[end_index:]

        # Check if there's any alphanumeric characters left in the line
        if re.search("[A-Za-z0-9]", line) is None:
            # Delete the whole line
            return None

        return line

    def __add_alias_attr(self, key, alias_key):
        """
        Some attributes have aliases. Added alias for a given attribute to the
        global maps

        :param key: the original attribute
        :type key: str
        :param alias_key: the alias
        :type alias_key: str
        """
        if key in self.attr_delete:
            self.attr_delete[alias_key] = self.attr_delete[key]
        if key in self.attr_key:
            self.attr_key[alias_key] = self.attr_key[key]
        if key in self.attr_val:
            self.attr_val[alias_key] = self.attr_val[key]
        if key in self.resc_delete:
            self.resc_delete[alias_key] = self.resc_delete[key]
        if key in self.resc_key:
            self.resc_key[alias_key] = self.resc_key[key]
        if key in self.resc_val:
            self.resc_val[alias_key] = self.resc_val[key]

    def anonymize_file_tabular(self, filename, extension=".anon",
                               inplace=False):
        """
        Anonymize pbs short format outputs (tabular form)
        (e.g - qstat, pbsnodes -aS)
        The 'titles' of various columns are used to look up keys inside the
        global attribute maps and they are anonymized/removed accordingly.

        Warning: only works work PBS tabular outputs, not generic.

        :param filename: Name of the file to anonymize
        :type filename: str
        :param delim: delimiter for the table
        :type delim: str
        :param extension: Extension of the anonymized file
        :type extension: str
        :param inplace: If true returns the original file name for
                        which contents have been replaced
        :type inplace: bool

        :returns: a str object containing filename of the anonymized file
        """
        fn = self.du.create_temp_file()

        # qstat outputs sometimes have different names for some attributes
        self.__add_alias_attr(ATTR_euser, "User")
        self.__add_alias_attr(ATTR_euser, "Username")
        self.__add_alias_attr(ATTR_name, "Jobname")
        self.__add_alias_attr(ATTR_name, "Name")

        # pbsnodes -aS output has a 'host' field which should be anonymized
        self.__add_alias_attr(ATTR_NODE_Host, "host")

        header = None
        with open(filename) as f, open(fn, "w") as nf:
            # Get the header and the line with '-'s
            # Also write out the header and dash lines to the output file
            line_num = 0
            for line in f:
                nf.write(line)
                line_num += 1
                line_strip = line.strip()

                if len(line_strip) == 0:
                    continue

                if line_strip[0].isalpha():
                    header = line
                    continue
                # Dash line is the line after header
                if header is not None:
                    dash_line = line
                    break

            if header is None:  # Couldn't find the header
                # Remove the aliases

                return filename

            # The dash line tells us the length of each column
            dash_list = dash_line.split()
            col_length = {}
            # Store each column's length
            col_index = 0
            for item in dash_list:
                col_len = len(item)
                col_length[col_index] = col_len
                col_index += 1

            # Find out the columns to anonymize/delete
            del_columns = []
            anon_columns = {}
            start_index = 0
            end_index = 0
            for col_index, length in enumerate(col_length):
                start_index = end_index
                end_index = start_index + length + 1

                # Get the column's title
                title = header[start_index:end_index]
                title = title.strip()

                if title in list(self.attr_delete.keys()):
                    # Need to delete this whole column
                    del_columns.append(col_index)
                elif title in list(self.attr_val.keys()):
                    # Need to anonymize all values in the column
                    anon_columns[col_index] = title

            anon_col_keys = list(anon_columns.keys())
            # Go through the file and anonymize/delete columns
            for line in f:
                start_index = 0
                end_index = 0
                # Iterate over the different fields
                col_index = 0
                for col_index in range(len(col_length)):
                    length = col_length[col_index]
                    start_index = end_index
                    end_index = start_index + length

                    if col_index in del_columns:
                        # Need to delete the value of this column
                        # Just replace the value by blank spaces
                        line2 = list(line)
                        for i in range(len(line2)):
                            if i >= start_index and i < end_index:
                                line2[i] = " "
                        line = "".join(line2)
                    elif col_index in anon_col_keys:
                        # Need to anonymize this column's value
                        # Get the value
                        value = line[start_index:end_index]
                        value_strip = value.strip()
                        anon_val = self.__get_anon_value(
                            anon_columns[col_index],
                            value_strip,
                            self.gmap_attr_val)
                        line = line.replace(value_strip, anon_val)

                nf.write(line)

        if inplace:
            out_filename = filename

        else:
            out_filename = filename + extension

        os.rename(fn, out_filename)

        return out_filename

    def anonymize_file_kv(self, filename, extension=".anon", inplace=False):
        """
        Anonymize a file which has data in the form of key-value pairs.
        Replace every occurrence of any entry in the global
        map for the given file by its anonymized values.

        :param filename: Name of the file to anonymize
        :type filename: str
        :param extension: Extension of the anonymized file
        :type extension: str
        :param inplace: If true returns the original file name for
                        which contents have been replaced
        :type inplace: bool

        :returns: a str object containing filename of the anonymized file
        """
        if not os.path.isfile(filename):
            self.logger.debug("%s not found, nothing to anonymize" % filename)
            return filename

        fn = self.du.create_temp_file()

        with open(filename) as f, open(fn, "w") as nf:
            delete_line = False
            for line in f:
                # Check if this is a line extension for an attr being deleted
                if delete_line is True and line[0] == "\t":
                    continue

                delete_line = False

                # Check if any of the attributes to delete are in the line
                for key in self.attr_delete.keys():
                    if key in line:
                        value = self.__get_value(line, key)
                        if value is None:
                            continue
                        # Delete the key-value pair
                        line = self.__delete_kv(line, key, value)
                        if line is None:
                            delete_line = True
                            break

                if delete_line is True:
                    continue

                # Anonymize key-value pairs
                for key in self.attr_key.keys():
                    if key in line:
                        if self.__verify_key(line, key) is None:
                            continue
                        anon_key = self.__get_anon_key(key, self.gmap_attr_key)
                        line = line.replace(key, anon_key)

                for key in self.resc_key.keys():
                    if key in line:
                        if self.__verify_key(line, key) is None:
                            continue
                        anon_key = self.__get_anon_key(key, self.gmap_resc_key)
                        line = line.replace(key, anon_key)

                for key in self.attr_val.keys():
                    if key in line:
                        value = self.__get_value(line, key)
                        if value is None:
                            continue
                        anon_value = self.__get_anon_value(key, value,
                                                           self.gmap_attr_val)
                        line = line.replace(value, anon_value)

                for key in self.resc_val.keys():
                    if key in line:
                        value = self.__get_value(line, key)
                        if value is None:
                            continue
                        anon_value = self.__get_anon_value(key, value,
                                                           self.gmap_resc_val)
                        line = line.replace(value, anon_value)

                # Anonymize IP addresses
                pattern = re.compile(
                    "\b*\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b*")
                match_obj = re.search(pattern, line)
                if match_obj:
                    ip = match_obj.group(0)
                    anon_key = self.__get_anon_key(ip, self.gmap_attr_key)
                    line = line.replace(ip, anon_key)

                nf.write(line)

        if inplace:
            out_filename = filename

        else:
            out_filename = filename + extension

        os.rename(fn, out_filename)

        return out_filename

    def anonymize_accounting_log(self, logfile):
        """
        Anonymize the accounting log

        :param logfile: Acconting log file
        :type logfile: str
        """
        try:
            f = open(logfile)
        except IOError:
            self.logger.error("Error processing " + logfile)
            return None

        self.__add_alias_attr(ATTR_euser, "user")
        self.__add_alias_attr(ATTR_euser, "requestor")
        self.__add_alias_attr(ATTR_egroup, "group")
        self.__add_alias_attr(ATTR_A, "account")

        anon_data = []
        for data in f:
            # accounting log format is
            # %Y/%m/%d %H:%M:%S;<Key>;<Id>;<key1=val1> <key2=val2> ...
            curr = data.split(";", 3)
            if curr is None or len(curr) < 4:
                continue
            if curr[1] in ("A", "L"):
                anon_data.append(data.strip())
                continue
            buf = shlex.split(curr[3].strip())

            skip_record = False
            # Split the attribute list into key value pairs
            kvl_list = [n.split("=", 1) for n in buf]
            if kvl_list is None:
                self.num_bad_acct_records += 1
                self.logger.debug("Bad accounting record found:\n" +
                                  data)
                continue
            for kvl in kvl_list:
                try:
                    k, v = kvl
                except ValueError:
                    self.num_bad_acct_records += 1
                    self.logger.debug("Bad accounting record found:\n" +
                                      data)
                    skip_record = True
                    break

                if k in self.attr_val:
                    anon_kv = self.__get_anon_value(k, v, self.gmap_attr_val)
                    kvl[1] = anon_kv

                if k in self.attr_key:
                    anon_ak = self.__get_anon_key(k, self.gmap_attr_key)
                    kvl[0] = anon_ak

                if "." in k:
                    restype, resname = k.split(".")
                    for rv in self.resc_val:
                        if resname == rv:
                            anon_rv = self.__get_anon_value(
                                resname, rv, self.gmap_resc_val)
                            kvl[1] = anon_rv

                    if resname in self.resc_key:
                        anon_rk = self.__get_anon_key(resname,
                                                      self.gmap_resc_key)
                        kvl[0] = restype + "." + anon_rk
            if not skip_record:
                anon_data.append(";".join(curr[:3]) + ";" +
                                 " ".join(["=".join(n) for n in kvl_list]))
        f.close()

        return anon_data

    def anonymize_sched_config(self, scheduler):
        """
        Anonymize the scheduler config

        :param scheduler: PBS scheduler object
        """
        if len(self.resc_key) == 0:
            return

        # when anonymizing we get rid of the comments as they may contain
        # sensitive information
        scheduler._sched_config_comments = {}

        # If resources need to be anonymized then update the resources line
        # job_sort_key and node_sort_key
        sr = scheduler.get_resources()
        if sr:
            for i, sres in enumerate(sr):
                if sres in self.resc_key:
                    if sres in self.gmap_resc_key:
                        sr[i] = self.gmap_resc_key[sres]
                    else:
                        anon_res = self.utils.random_str(len(sres))
                        self.gmap_resc_key[sres] = anon_res
                        sr[i] = anon_res

            scheduler.sched_config["resources"] = ",".join(sr)

        for k in ["job_sort_key", "node_sort_key"]:
            if k in scheduler.sched_config:
                sc_jsk = scheduler.sched_config[k]
                if not isinstance(sc_jsk, list):
                    sc_jsk = list(sc_jsk)

                for r in self.resc_key:
                    for i, key in enumerate(sc_jsk):
                        if r in key:
                            sc_jsk[i] = key.replace(r, self.resc_key[r])

    def __str__(self):
        return ("Attributes Values: " + str(self.gmap_attr_val) + "\n" +
                "Resources Values: " + str(self.gmap_resc_val) + "\n" +
                "Attributes Keys: " + str(self.gmap_attr_key) + "\n" +
                "Resources Keys: " + str(self.gmap_resc_key))
