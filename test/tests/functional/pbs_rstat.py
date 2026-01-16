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


from tests.functional import *
import json


class TestPbsRstat(TestFunctional):
    """
    This test suite validates output of pbs_rstat
    """

    def test_rstat_missing_resv(self):
        """
        Test that checks if pbs_rstat will continue to display
        reservations after not locating one reservation
        """

        now = int(time.time())
        a = {'Resource_List.select': '1:ncpus=1',
             'reserve_start': now + 1000,
             'reserve_end': now + 2000}
        r = Reservation(TEST_USER)
        r.set_attributes(a)
        rid = self.server.submit(r)
        exp = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp, id=rid)

        a2 = {'Resource_List.select': '1:ncpus=1',
              'reserve_start': now + 3000,
              'reserve_end': now + 4000}
        r2 = Reservation(TEST_USER)
        r.set_attributes(a2)
        rid2 = self.server.submit(r)
        self.server.expect(RESV, exp, id=rid2)

        self.server.delresv(rid, wait=True)

        rstat_cmd = \
            os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_rstat')
        rstat_opt = [rstat_cmd, '-B', rid, rid2]
        ret = self.du.run_cmd(self.server.hostname, cmd=rstat_opt,
                              logerr=False)

        self.assertEqual(ret['rc'], 0,
                         'pbs_rstat returned with non-zero exit status')

        rstat_out = '\n'.join(ret['out'])
        self.assertIn(rid2, rstat_out)

    def parse_json(self, dictitems, pbs_rstat_attr):
        """
        Common function for parsing all values in json output
        """
        for key, val in dictitems.items():
            pbs_rstat_attr.append(str(key))
            if isinstance(val, dict):
                self.parse_json(val, pbs_rstat_attr)
        return pbs_rstat_attr
    
    def get_pbs_rstat_attribs(self, resv_id):
        """
        Common function to get the pbs_rstat attributes in default format.
        Attributes returned by this function are used to validate the
        '-F json' format output.
        The dictionary of attributes as returned by status() can not
        be used directly because some attributes are printed differently
        in '-F json' format.  Hence this function returns a modified
        attributes list.
        resv_id: reservation ID to pass to pbs_rstat -f
        """
        attrs = self.server.status(RESV, id=resv_id)
        rstat_attrs = []

        for key, val in attrs[0].items():
            # pbs_rstat -F json output does not
            # print the 'id' attribute. Its value
            # is printed instead.
            if key.lower() in ['id', 'resv id']:
                rstat_attrs.append(str(val))
                continue
            else:
                # handle dotted attributes like resource_List.ncpus
                k = key.split('.')
                if k[0] not in rstat_attrs:
                    rstat_attrs.append(str(k[0]))
                if len(k) == 2:
                    rstat_attrs.append(str(k[1]))

            if key == ATTR_v:
                rstat_attrs.append(str(key)) # only add main key and not sub-keys
                continue
        return rstat_attrs


    def test_json(self):
        """
        Check whether the pbs_rstat json output can be parsed using
        python json module
        """
        now = int(time.time())
        a = {
            'Resource_List.select': '1:ncpus=1',
            'reserve_start': now + 1000,
            'reserve_end': now + 2000
        }
        r = Reservation(TEST_USER)
        r.set_attributes(a)
        rid = self.server.submit(r)
        [pbs_rstat_json_script, pbs_rstat_json_out] = [DshUtils().create_temp_file()
                                                    for _ in range(2)]

        pbs_rstat_cmd = os.path.join(
            self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_rstat')
        
        with open(pbs_rstat_json_script, 'w') as f:
            f.write(pbs_rstat_cmd + ' -f -F json ' + str(rid) + ' > ' + pbs_rstat_json_out)
        f.close()
        self.du.chmod(path=pbs_rstat_json_script, mode=0o755)

        run_script = 'sh ' + pbs_rstat_json_script
        ret = self.du.run_cmd(
            self.server.hostname, cmd=run_script)
        self.assertEqual(ret['rc'], 0, "pbs_rstat returned non-zero exit code")

        data = open(pbs_rstat_json_out, 'r').read()
        map(os.remove, [pbs_rstat_json_script, pbs_rstat_json_out])

        try:
            json_data = json.loads(data)
        except json.JSONDecodeError as e:
            self.fail(f"Failed to parse JSON: {e}\nOutput was:\n{data}")

        # sanity checks
        self.assertIn("restrictions", json_data)
        self.assertIn(rid, json_data["restrictions"])

    @tags('smoke')
    def test_rstat_fF_json(self):
        '''
        Validate basic structure and JSON validity of pbs_rstat -fF JSON
        '''  

        now = int(time.time())
        a = {
            'Resource_List.select': '1:ncpus=1',
            'reserve_start': now + 1000,
            'reserve_end': now + 2000
        }

        r = Reservation(TEST_USER)
        r.set_attributes(a)
        rid = self.server.submit(r)
        exp = {'reserve_state': (MATCH_RE, "RESV_CONFIRMED|2")}
        self.server.expect(RESV, exp, id=rid)

        rstat_cmd = \
            os.path.join(self.server.pbs_conf['PBS_EXEC'], 'bin', 'pbs_rstat')
        rstat_opt = [rstat_cmd, '-fF', 'JSON', rid]
        ret = self.du.run_cmd(self.server.hostname, cmd=rstat_opt,
                              logerr=False)

        self.assertEqual(ret['rc'], 0,
                         'pbs_rstat returned with non-zero exit status')
        
        json_out = '\n'.join(ret['out'])
        try:
            json_object = json.loads(json_out)
        except json.JSONDecodeError as e:
            self.fail(f"Failed to parse JSON: {e}")

        json_only_attrs = ["restrictions", 'timestamp', 'pbs_version', 'pbs_server']
        attrs_pbs_rstatf = self.get_pbs_rstat_attribs(rid)
        pbs_rstat_json_attr = []

        for key, val in json_object.items():
            pbs_rstat_json_attr.append(str(key))
            if isinstance(val, dict):
                self.parse_json(val, pbs_rstat_json_attr)
        
        for attr in attrs_pbs_rstatf:
            self.assertIn(attr, pbs_rstat_json_attr, f"\n{attr} is missing")

        for attr in json_only_attrs:
            self.assertIn(attr, pbs_rstat_json_attr, f"\n{attr} is missing")
