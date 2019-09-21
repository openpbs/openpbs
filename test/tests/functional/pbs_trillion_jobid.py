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

from tests.functional import *


class TestTrillionJobid(TestFunctional):
    """
    This test suite tests the Trillion Job ID and sequence jobid
    """

    update_svr_db_script = """#!/bin/bash
. %s
. ${PBS_EXEC}/libexec/pbs_pgsql_env.sh

DATA_PORT=${PBS_DATA_SERVICE_PORT}
if [ -z ${DATA_PORT} ]; then
    DATA_PORT=15007
fi

sudo ls ${PBS_HOME}/server_priv/db_user &>/dev/null
if [ $? -eq 0 ]; then
    DATA_USER=`sudo cat ${PBS_HOME}/server_priv/db_user`
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

sudo ${PBS_EXEC}/sbin/pbs_ds_password test
if [ $? -eq 0 ]; then
    sudo ${PBS_EXEC}/sbin/pbs_dataservice stop
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

sudo ${PBS_EXEC}/sbin/pbs_dataservice status
if [ $? -eq 0 ]; then
    sudo ${PBS_EXEC}/sbin/pbs_dataservice stop
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

sudo ${PBS_EXEC}/sbin/pbs_dataservice start
if [ $? -ne 0 ]; then
    exit 1
fi

args="-U ${DATA_USER} -p ${DATA_PORT} -d pbs_datastore"
PGPASSWORD=test ${PGSQL_BIN}/psql ${args} <<-EOF
    UPDATE pbs.server SET sv_jobidnumber = %d;
EOF

ret=$?
if [ $ret -eq 0 ]; then
    echo "Server sv_jobidnumber attribute has been updated successfully"
fi

sudo ${PBS_EXEC}/sbin/pbs_dataservice stop
if [ $? -ne 0 ]; then
    exit 1
fi

exit 0

"""

    def set_svr_sv_jobidnumber(self, num=0):
        """
        This function is to set the next jobid into server database
        """
        # Stop the PBS server
        self.server.stop()
        stop_msg = 'Failed to stop PBS'
        self.assertFalse(self.server.isUp(), stop_msg)
        # Create a shell script file and update the database
        conf_path = self.du.get_pbs_conf_file()
        fn = self.du.create_temp_file(
            body=self.update_svr_db_script %
            (conf_path, num))
        self.du.chmod(path=fn, mode=0o755)
        fail_msg = 'Failed to set sequence id in database'
        ret = self.du.run_cmd(cmd=fn)
        self.assertEqual(ret['rc'], 0, fail_msg)
        # Start the PBS server
        start_msg = 'Failed to restart PBS'
        self.server.start()
        self.assertTrue(self.server.isUp(), start_msg)

    def stop_and_restart_svr(self, restart_type):
        """
            Abruptly/Gracefully stop and restart the server

        """
        try:
            if(restart_type == 'kill'):
                self.server.stop('-KILL')
            else:
                self.server.stop()
        except PbsServiceError as e:
            # The server failed to stop
            raise self.failureException("Server failed to stop:" + e.msg)
        try:
            self.server.start()
        except PbsServiceError as e:
            # The server failed to start
            raise self.failureException("Server failed to start:" + e.msg)
        restart_msg = 'Failed to restart PBS'
        self.assertTrue(self.server.isUp(), restart_msg)

    def submit_job(self, sleep=10, lower=0,
                   upper=0, job_id=None, job_msg=None, verify=False):
        """
        Helper method to submit a normal/array job
        and also checks the R state and particular jobid if success,
        else log the error message

        :param sleep   : Sleep time in seconds for the job
        :type  sleep   : int

        :param lower   : Lower limit for the array job
        :type  lower   : int

        :param upper   : Upper limit for the array job
        :type  upper   : int

        :param job_id  : Expected jobid upon submission
        :type  job_id  : string

        :param job_msg : Expected message upon submission failure
        :type  job_msg : int

        :param verify : Checks Job status R
        :type  verify : boolean(True/False)

        """
        arr_flag = False
        j = Job(TEST_USER)
        if((lower >= 0) and (upper > lower)):
            j.set_attributes({ATTR_J: '%d-%d' % (lower, upper)})
            arr_flag = True
            total_jobs = upper - lower + 1
        j.set_sleep_time(sleep)
        try:
            jid = self.server.submit(j)
            if job_id is not None:
                self.assertEqual(jid.split('.')[0], job_id)
            if arr_flag:
                if verify:
                    self.server.expect(JOB, {'job_state': 'B'}, id=jid)
                    self.server.expect(
                        JOB,
                        {'job_state=R': total_jobs},
                        count=True, id=jid, extend='t')
            else:
                if verify:
                    self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        except PbsSubmitError as e:
            if job_msg is not None:
                # if JobId already exist
                self.assertEqual(e.msg[0], job_msg)
            else:
                # Unable to submit Job
                self.logger.info('Error in submitting job:', e.msg)

    def submit_resv(self, resv_dur=2, resv_id=None, resv_msg=None):
        """
        Helper method to submit a reservation and checks the
        reservation id if success, else log the error message.

        :param resv_dur : Reservation duration in seconds
        :type  resv_dur : int

        :param resv_id  : Expected resvid upon submission
        :type  resv_id  : string

        :param resv_msg : Expected message upon reservation failure
        :type  resv_msg : string

        """
        resv_start = int(time.time()) + 2
        a = {'reserve_start': int(resv_start),
             'reserve_duration': int(resv_dur)
             }
        r = Reservation(TEST_USER, attrs=a)
        try:
            rid = self.server.submit(r)
            if resv_id is not None:
                self.assertEqual(rid.split('.')[0], resv_id)
        except PbsSubmitError as e:
            if resv_msg is not None:
                # if ResvId already exist
                self.assertEqual(e.msg[0], resv_msg)
            else:
                # Unable to submit reservation
                self.logger.info('Error in submitting reservation:', e.msg)

    def test_set_unset_max_job_sequence_id(self):
        """
        Set/Unset max_job_sequence_id attribute and
        also verify the attribute value after server qterm/kill
        """
        # Set as Non-admin user
        seq_id = {ATTR_max_job_sequence_id: 123456789}
        try:
            self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=TEST_USER1)
        except PbsManagerError as e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        # Set as Admin User and also check the value after server restart
        self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
        self.server.expect(SERVER, seq_id)
        self.server.log_match('svr_max_job_sequence_id set to '
                              'val %d' % (seq_id[ATTR_max_job_sequence_id]),
                              starttime=self.server.ctime)
        # Abruptly kill the server
        self.stop_and_restart_svr('kill')
        self.server.expect(SERVER, seq_id)
        # Gracefully stop the server
        self.stop_and_restart_svr('normal')
        self.server.expect(SERVER, seq_id)

        # Unset as Non-admin user
        try:
            self.server.manager(
                MGR_CMD_UNSET,
                SERVER,
                'max_job_sequence_id',
                runas=TEST_USER1)
        except PbsManagerError as e:
            self.assertTrue('Unauthorized Request' in e.msg[0])

        # Unset as Admin user
        self.server.manager(MGR_CMD_UNSET, SERVER, 'max_job_sequence_id',
                            runas=ROOT_USER)
        self.server.log_match('svr_max_job_sequence_id reverting back '
                              'to default val 9999999',
                              starttime=self.server.ctime)

    def test_max_job_sequence_id_values(self):
        """
        Test to check valid/invalid values for the
        max_job_sequence_id server attribute
        """
        # Invalid Values
        invalid_values = [-9999999, '*456879846',
                          23545.45, 'ajndd', '**45', 'asgh456']
        for val in invalid_values:
            try:
                seq_id = {ATTR_max_job_sequence_id: val}
                self.server.manager(
                    MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
            except PbsManagerError as e:
                self.assertTrue(
                    'Illegal attribute or resource value' in e.msg[0])
        # Less than or Greater than the attribute limit
        min_max_values = [120515, 999999, 1234567891234, 9999999999999]
        for val in min_max_values:
            try:
                seq_id = {ATTR_max_job_sequence_id: val}
                self.server.manager(
                    MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
            except PbsManagerError as e:
                self.assertTrue('Cannot set max_job_sequence_id < 9999999, '
                                'or > 999999999999' in e.msg[0])
        # Valid values
        valid_values = [9999999, 123456789, 100000000000, 999999999999]
        for val in valid_values:
            seq_id = {ATTR_max_job_sequence_id: val}
            self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)

    def test_max_job_sequence_id_wrap(self):
        """
        Test to check the jobid's/resvid's are wrapping it to zero or not,
        after reaching to the given limit
        """
        # Check default limit(9999999) and wrap it 0
        a = {'resources_available.ncpus': 20}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        self.submit_job(verify=True)
        self.submit_job(lower=1, upper=2, verify=True)
        self.submit_resv()
        sv_jobidnumber = 9999999  # default
        self.set_svr_sv_jobidnumber(sv_jobidnumber)
        self.submit_job(job_id='%s' % (sv_jobidnumber), verify=True)
        self.submit_job(lower=1, upper=2, job_id='0[]',
                        verify=True)  # wrap it
        self.submit_resv(resv_id='R1')

        # Check max limit (999999999999) and wrap it 0
        sv_jobidnumber = 999999999999  # max limit
        seq_id = {ATTR_max_job_sequence_id: sv_jobidnumber}
        self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
        self.server.expect(SERVER, seq_id)
        self.submit_job(verify=True)
        self.submit_job(lower=1, upper=2, verify=True)
        self.submit_resv()
        self.set_svr_sv_jobidnumber(sv_jobidnumber)
        self.submit_job(job_id='%s' % (sv_jobidnumber), verify=True)
        self.submit_job(lower=1, upper=2, job_id='0[]',
                        verify=True)  # wrap it
        self.submit_resv(resv_id='R1')

        # Someone set the max_job_sequence_id less than current jobid then also
        # wrap it 0
        sv_jobidnumber = 1234567890
        seq_id = {ATTR_max_job_sequence_id: sv_jobidnumber}
        self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
        self.server.expect(SERVER, seq_id)
        sv_jobidnumber = 123456789
        self.set_svr_sv_jobidnumber(sv_jobidnumber)
        self.submit_job(job_id='%s' % (sv_jobidnumber), verify=True)
        self.submit_job(lower=1, upper=2, job_id='123456790[]', verify=True)
        self.submit_resv(resv_id='R123456791')
        # Set smaller(12345678) than current jobid(123456790)
        sv_jobidnumber = 12345678
        seq_id = {ATTR_max_job_sequence_id: sv_jobidnumber}
        self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
        self.server.expect(SERVER, seq_id)
        self.submit_job(job_id='0', verify=True)  # wrap it to zero
        self.submit_job(lower=1, upper=2, job_id='1[]', verify=True)
        self.submit_resv(resv_id='R2')

    def test_verify_sequence_window(self):
        """
        Tests the sequence window scenario in which jobid
        number save to the database once in a 1000 time
        """
        # Abruptly kill the server so next jobid should be 1000 after server
        # start
        self.set_svr_sv_jobidnumber(0)
        self.submit_job(job_id='0')
        self.submit_job(lower=1, upper=2, job_id='1[]')
        self.submit_resv(resv_id='R2')
        # kill the server forcefully
        self.stop_and_restart_svr('kill')
        self.submit_job(job_id='1000')
        self.submit_job(lower=1, upper=2, job_id='1001[]')
        self.submit_resv(resv_id='R1002')
        # if server gets killed again abruptly then next jobid would be 2000
        self.stop_and_restart_svr('kill')
        self.submit_job(job_id='2000')
        self.submit_job(lower=1, upper=2, job_id='2001[]')
        self.submit_resv(resv_id='R2002')

        # Gracefully stop the server so jobid's will continue from the last
        # jobid
        self.stop_and_restart_svr('normal')
        self.submit_job(job_id='2003')
        self.submit_job(lower=1, upper=2, job_id='2004[]')
        self.submit_resv(resv_id='R2005')

        # Verify the sequence window, incase of submitting more than 1001 jobs
        # and all jobs should submit successfully without any duplication error
        for _ in range(1010):
            j = Job(TEST_USER)
            self.server.submit(j)

    def test_jobid_duplication(self):
        """
                Tests the JobId/ResvId duplication after wrap
                Job/Resv shouldn't submit because previous
                jobs with the same id's are still running
        """
        seq_id = {ATTR_max_job_sequence_id: 99999999}
        self.server.manager(MGR_CMD_SET, SERVER, seq_id, runas=ROOT_USER)
        self.set_svr_sv_jobidnumber(0)
        self.submit_job(sleep=1000, job_id='0')
        self.submit_job(sleep=1000, lower=1, upper=2, job_id='1[]')
        self.submit_resv(resv_dur=300, resv_id='R2')
        sv_jobidnumber = 99999999
        self.set_svr_sv_jobidnumber(sv_jobidnumber)
        self.submit_job(sleep=1000, job_id='%s' % (sv_jobidnumber))

        # Now job/resv shouldn't submit because same id's are already occupied
        msg = "qsub: Job with requested ID already exists"
        self.submit_job(job_msg=msg)
        self.submit_job(lower=1, upper=2, job_msg=msg)
        msg = 'pbs_rsub: Reservation with '\
              'requested ID already exists'
        self.submit_resv(resv_msg=msg)
        # Job should submit successfully because all existing id's has been
        # passed
        self.submit_job(lower=1, upper=2, job_id='3[]')

    def test_jobid_resvid_after_multiple_restart(self):
        """
        Test to check the Jobid/Resvid should not wrap to 0 during
        server restart multiple times consecutively either gracefully/abruptly
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        curr_id = int(jid.split('.')[0])
        self.submit_job(job_id='%s' % str(curr_id + 1))
        self.submit_job(lower=1, upper=2, job_id='%s[]' % str(curr_id + 2))
        self.submit_resv(resv_id='R%s' % str(curr_id + 3))
        # Gracefully stop and start the server twice consecutively
        self.stop_and_restart_svr('normal')
        self.stop_and_restart_svr('normal')
        self.submit_job(job_id='%s' % str(curr_id + 4))
        self.submit_job(lower=1, upper=2, job_id='%s[]' % str(curr_id + 5))
        self.submit_resv(resv_id='R%s' % str(curr_id + 6))
        # Abruptly kill and start the server twice consecutively
        self.stop_and_restart_svr('kill')
        self.stop_and_restart_svr('kill')
        # Adding 1000 in current jobid for the sequence window buffer and
        # 4 for the jobs that ran already after server start
        curr_id += 1000 + 4
        self.submit_job(job_id='%s' % str(curr_id))
        self.submit_job(lower=1, upper=2, job_id='%s[]' % str(curr_id + 1))
        self.submit_resv(resv_id='R%s' % str(curr_id + 2))

    def tearDown(self):
        self.server.cleanup_jobs()
        TestFunctional.tearDown(self)
