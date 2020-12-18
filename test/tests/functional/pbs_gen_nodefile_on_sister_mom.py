# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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

@requirements(num_moms=2)
class TestGenNodefileOnSisterMom(TestFunctional):
    """
    This test suite tests the PBS_NODEFILE creation on
    sister moms of job.
    """
    def test_gen_nodefile_on_sister_mom_default(self):
        """
        This test case verifies PBS_NODEFILE gets created on
        sister mom by default
        """
        # Skip test if number of mom provided is not equal to two
        if not len(self.moms) == 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        ms = self.moms.keys()[0]
        sister_mom = self.moms.keys()[1]
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2:ncpus=1',
                          'Resource_List.place': 'scatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodefile = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                "aux", jid)

        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertTrue(file_exists, "PBS_NODEFILE not created in "
                                     "sister mom %s" % sister_mom)
        sister_nodes = "\n".join(self.du.cat(sister_mom, nodefile,
                                             sudo=True)['out'])
        ms_nodes = "\n".join(self.du.cat(ms, nodefile, sudo=True)['out'])
        self.assertEqual(ms_nodes, sister_nodes)
        self.server.log_match(jid + ";Exit_status=0", interval=4,
                              max_attempts=30)
        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertFalse(file_exists, "PBS_NODEFILE not deleted in "
                                      "sister mom %s" % sister_mom)

    def test_gen_nodefile_on_sister_mom_config_enabled(self):
        """
        This test case verifies PBS_NODEFILE gets created on
        sister mom on setting gen_nodefile_on_sister_mom mom
        config parameter to true.
        """
        # Skip test if number of mom provided is not equal to two
        if not len(self.moms) == 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        ms = self.moms.keys()[0]
        sister_mom = self.moms.keys()[1]
        sister_mom_obj = self.moms.values()[1]
        sister_mom_obj.add_config({'$gen_nodefile_on_sister_mom': 1})

        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2:ncpus=1',
                          'Resource_List.place': 'scatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodefile = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                "aux", jid)

        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertTrue(file_exists, "PBS_NODEFILE not created in "
                                     "sister mom %s" % sister_mom)
        sister_nodes = "\n".join(self.du.cat(sister_mom, nodefile,
                                             sudo=True)['out'])
        ms_nodes = "\n".join(self.du.cat(ms, nodefile, sudo=True)['out'])
        self.assertEqual(ms_nodes, sister_nodes)
        self.server.log_match(jid + ";Exit_status=0", interval=4,
                              max_attempts=30)
        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertFalse(file_exists, "PBS_NODEFILE not deleted in "
                                      "sister mom %s" % sister_mom)

    def test_gen_nodefile_on_sister_mom_config_disabled(self):
        """
        This test case verifies PBS_NODEFILE does not get created
        on sister mom on setting gen_nodefile_on_sister_mom mom
        config parameter to false.
        """
        # Skip test if number of mom provided is not equal to two
        if not len(self.moms) == 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")

        sister_mom = self.moms.keys()[1]
        sister_mom_obj = self.moms.values()[1]
        sister_mom_obj.add_config({'$gen_nodefile_on_sister_mom': 0})
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2:ncpus=1',
                          'Resource_List.place': 'scatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodefile = os.path.join(self.server.pbs_conf['PBS_HOME'],
                                "aux", jid)

        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertFalse(file_exists, "PBS_NODEFILE created in "
                                      "sister mom %s" % sister_mom)

    def test_gen_nodefile_on_sister_mom_hup(self):
        """
        This test suite verifies PBS_NODEFILE does not get created
        on sister mom on setting gen_nodefile_on_sister_mom mom
        config parameter to false and then HUP the mom to verify if
        PBS_NODEFILE is created on sister.
        """
        # Skip test if number of mom provided is not equal to two
        if not len(self.moms) == 2:
            self.skipTest("test requires two MoMs as input, " +
                          "use -p moms=<mom1:mom2>")
        ms = self.moms.keys()[0]
        sister_mom = self.moms.keys()[1]
        sister_mom_obj = self.moms.values()[1]
        sister_mom_obj.add_config({'$gen_nodefile_on_sister_mom': 0})
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2:ncpus=1',
                          'Resource_List.place': 'scatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodefile = os.path.join(self.server.pbs_conf['PBS_HOME'], "aux", jid)

        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertFalse(file_exists, "PBS_NODEFILE created in "
                                      "sister mom %s" % sister_mom)
        self.server.delete(jid)
        config = {'$clienthost': self.server.hostname}
        sister_mom_obj.config = config
        sister_mom_obj.apply_config(config)
        j = Job(TEST_USER)
        j.set_attributes({'Resource_List.select': '2:ncpus=1',
                          'Resource_List.place': 'scatter'})
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        nodefile = os.path.join(self.server.pbs_conf['PBS_HOME'], "aux", jid)
        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertTrue(file_exists, "PBS_NODEFILE not created in "
                                     "sister mom %s" % sister_mom)
        sister_nodes = "\n".join(self.du.cat(sister_mom, nodefile,
                                             sudo=True)['out'])
        ms_nodes = "\n".join(self.du.cat(ms, nodefile, sudo=True)['out'])
        self.assertEqual(ms_nodes, sister_nodes)
        self.server.log_match(jid + ";Exit_status=0", interval=4,
                              max_attempts=30)
        file_exists = self.du.isfile(hostname=sister_mom, path=nodefile,
                                     sudo=True)
        self.assertFalse(file_exists, "PBS_NODEFILE not deleted in "
                                      "sister mom %s" % sister_mom)
