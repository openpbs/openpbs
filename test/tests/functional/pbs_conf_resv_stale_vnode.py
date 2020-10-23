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


class TestResvStaleVnode(TestFunctional):
    """
    Test that the scheduler won't confirm a reservation on stale vnode and
    make sure reservations that have nodes that have gone stale get degreaded
    """

    def setUp(self):
        TestFunctional.setUp(self)
        # Create 3 vnodes named different things in different vnodedef files
        # This allows us to delete a vnodedef file and make that node stale
        self.mom.add_config(conf={'$vnodedef_additive': 'False'})
        a = {'resources_available.ncpus': 1, 'priority': 100}
        self.mom.create_vnodes(a, 1, fname='nat', restart=False,
                               usenatvnode=True, expect=False, vname='foo')
        a['priority'] = 10
        self.mom.create_vnodes(a, 1, fname='fname1', delall=False,
                               restart=False, additive=True,
                               expect=False, vname='vn')
        a['priority'] = 1
        self.mom.create_vnodes(a, 1, fname='fname2', delall=False,
                               additive=True, expect=False, vname='vnode')

        self.scheduler.set_sched_config({'node_sort_key':
                                         '\"sort_priority HIGH\"'})

    def test_conf_resv_stale_vnode(self):
        """
        Test that the scheduler won't confirm a reservation on a stale node.
        """
        # Ensure the hostsets aren't used by associating a node to a queue
        a = {'queue_type': 'Execution', 'enabled': 'True', 'started': 'True'}
        self.server.manager(MGR_CMD_CREATE, QUEUE, a, id='workq2')
        self.server.manager(MGR_CMD_SET, NODE, {'queue': 'workq2'},
                            id=self.mom.shortname)

        # Submit a job that will run on our stale vnode
        a = {'Resource_List.select': '1:vnode=vn[0]',
             'Resource_List.walltime': 3600}
        J = Job(TEST_USER, attrs=a)
        jid = self.server.submit(J)
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        self.mom.delete_vnode_defs(vdefname='fname1')
        self.mom.signal('-HUP')
        self.server.expect(NODE, {'state': (MATCH_RE, 'Stale')}, id='vn[0]')

        now = int(time.time())
        a = {'reserve_start': now + 5400, 'reserve_end': now + 7200}
        R = Reservation(TEST_USER, a)
        rid = self.server.submit(R)

        # Reservation should be confirmed on vnode[0] since vn[0] is Stale
        a = {'resv_nodes': '(vnode[0]:ncpus=1)'}
        a2 = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)
        self.server.expect(RESV, a2, id=rid)

    def test_stale_degraded(self):
        """
        Test that a reservation goes into the degraded state
        when one of its vnodes go stale
        """
        self.server.expect(NODE, {'state=free': 3})
        now = int(time.time())
        a = {'Resource_List.select': '3:ncpus=1',
             'Resource_List.place': 'vscatter',
             'reserve_start': now + 3600, 'reserve_end': now + 7200}

        R = Reservation(TEST_USER, attrs=a)
        rid = self.server.submit(R)

        a = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        self.server.expect(RESV, a, id=rid)

        self.mom.delete_vnode_defs(vdefname='fname1')
        self.mom.signal('-HUP')
        self.server.expect(NODE, {'state': (MATCH_RE, 'Stale')}, id='vn[0]')

        a = {'reserve_state': (MATCH_RE, 'RESV_DEGRADED|10')}
        self.server.expect(RESV, a, id=rid)
