# coding: utf-8

# Copyright (C) 2003-2020 Altair Engineering, Inc. All rights reserved.
# Copyright notice does not imply publication.
#
# ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
# Information. Not for use or disclosure outside of Licensee's organization.
# The software and information contained herein may only be used internally and
# is provided on a non-exclusive, non-transferable basis. License may not
# sublicense, sell, lend, assign, rent, distribute, publicly display or
# publicly perform the software or other information provided herein,
# nor is Licensee permitted to decompile, reverse engineer, or
# disassemble the software. Usage of the software and other information
# provided by Altair(or its resellers) is only as explicitly stated in the
# applicable end user license agreement between Altair and Licensee.
# In the absence of such agreement, the Altair standard end user
# license agreement terms shall govern.

from tests.functional import *
import socket


class TestTPP(TestFunctional):
    """
    Test suite consists of tests to check the functionality of pbs_comm daemon
    """

    def setUp(self):
        TestFunctional.setUp(self)
        self.pbs_conf = self.du.parse_pbs_config(self.server.shortname)
        self.exec_path = os.path.join(self.pbs_conf['PBS_EXEC'], "bin")

    def submit_job(self, set_attrib=None, exp_attrib=None, sleep=10,
                   interactive=False):
        j = Job(PBSROOT_USER)
        if set_attrib:
            j.set_attributes(set_attrib)
        if interactive:
            j.interactive_script = [('hostname', '.*'),
                                    ('export PATH=$PATH:%s' %
                                     self.exec_path, '.*'),
                                    ('qstat', '.*')]
        j.set_sleep_time(sleep)
        jid = self.server.submit(j)
        if exp_attrib:
            self.server.expect(JOB, exp_attrib, id=jid)
        return jid

    def submit_resv(self, set_attrib=None, exp_attrib=None):
        r = Reservation(PBSROOT_USER)
        if set_attrib:
            r.set_attributes(set_attrib)
        rid = self.server.submit(r)
        if exp_attrib:
            self.server.expect(RESV, exp_attrib, id=rid)
        return rid

    def test_comm_with_mom(self):
        """
        Test the installation of communication daemon during PBS installation.
        """
        msg = "Need atleast 2 moms as input. use -pmoms=<m1>:<m2>"
        if len(self.moms) < 2:
            self.skip_test(reason=msg)
        log_msgs = ["TPP initialization done",
                    "Single pbs_comm configured, " +
                    "TPP Fault tolerant mode disabled",
                    "Connected to pbs_comm %s.*:17001" % self.server.shortname]
        for msg in log_msgs:
            self.server.log_match(msg, regexp=True)
            self.scheduler.log_match(msg, regexp=True)
            for mom in self.moms.values():
                self.mom.log_match(msg, regexp=True)
        server_ip = socket.gethostbyname(self.server.hostname)
        msg = "Registering address %s:15001 to pbs_comm" % server_ip
        self.server.log_match(msg)
        msg = "Registering address %s:15004 to pbs_comm" % server_ip
        self.scheduler.log_match(msg)
        for mom in self.moms.values():
            ip = socket.gethostbyname(mom.shortname)
            msg1 = "Registering address %s:15003 to pbs_comm" % ip
            msg2 = "Leaf registered address %s:15003" % ip
            mom.log_match(msg1)
            self.comm.log_match(msg2)
        # Submit job
        jid = self.submit_job(exp_attrib={'job_state': 'R'})
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
        self.server.log_match("%s;Exit_status=0" % jid)
        # Submit multi-chunk job
        set_attrib = {'Resource_List.select': '2:ncpus=1'}
        jid = self.submit_job(set_attrib, exp_attrib={'job_state': 'R'})
        self.server.expect(JOB, 'queue', id=jid, op=UNSET, offset=10)
        self.server.log_match("%s;Exit_status=0" % jid)
        # Submit interactive job
        set_attrib = {ATTR_inter: ''}
        jid = self.submit_job(set_attrib, interactive=True)
        # Submit reservation
        set_attrib = {'Resource_List.select': '1:ncpus=1',
                      'reserve_start': int(time.time() + 5),
                      'reserve_end': int(time.time() + 120)}
        exp_attrib = {'reserve_state': (MATCH_RE, 'RESV_CONFIRMED|2')}
        rid = self.submit_resv(set_attrib, exp_attrib)
        resv_que = rid.split('.')[0]
        # Submit job into reservation
        set_attrib = {ATTR_q: resv_que}
        jid = self.submit_job(set_attrib, sleep=60)
        # Wait for reservation to start
        a = {'reserve_state': (MATCH_RE, 'RESV_RUNNING|2')}
        self.server.expect(RESV, a, rid, offset=5)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.delete(rid)
        self.server.expect(JOB, 'queue', id=jid, op=UNSET)
