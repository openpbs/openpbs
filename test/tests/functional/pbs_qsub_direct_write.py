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


class TestQsub_direct_write(TestFunctional):
    """
    validate qsub direct write option.
    """

    def setUp(self):
        """
        Default setup and variable declaration
        """
        TestFunctional.setUp(self)
        self.msg = "Job is sleeping for 10 secs as job should  be running"
        self.msg += " at the time we check for directly written files"

    def test_direct_write_when_job_succeeds(self):
        """
        submit a sleep job and make sure that the std_files
        are getting directly written to the mapped directory
        when direct_files option is used.
        """
        j = Job(TEST_USER, attrs={ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(2, file_count)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)

    def test_direct_write_when_job_succeeds_controlled(self):
        """
        submit a sleep job and make sure that the std_files
        are getting directly written to the mapped directory
        when direct_files option is used.

        directory should be
        1) owned by a different user
        2) owned by a group that is not the job user's primary gid
                (but is a gid that the user is a member of)
        3) not accessible via other permissions
        """
        j = Job(TEST_USER4, attrs={ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = self.du.mkdtemp(uid=TEST_USER4.uid)
        mapping_dir = self.du.mkdtemp(
            uid=TEST_USER5.uid, gid=TSTGRP4.gid, mode=0o770)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(2, file_count)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)

    def test_direct_write_output_file(self):
        """
        submit a sleep job and make sure that the output file
        are getting directly written to the mapped directory
        when direct_files option is used with o option.
        """
        j = Job(TEST_USER, attrs={ATTR_k: 'do'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        for name in os.listdir(mapping_dir):
            p = re.search('STDIN.e*', name)
            if p:
                self.logger.info('Match found: ' + p.group())
            else:
                self.assertTrue(False)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(1, file_count)
        self.server.expect(JOB, {ATTR_k: 'do'}, id=jid)

    def test_direct_write_error_file(self):
        """
        submit a sleep job and make sure that the error file
        are getting directly written to the mapped directory
        when direct_files option is used with e option.
        """
        j = Job(TEST_USER, attrs={ATTR_k: 'de'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        for name in os.listdir(mapping_dir):
            p = re.search('STDIN.e*', name)
            if p:
                self.logger.info('Match found: ' + p.group())
            else:
                self.assertTrue(False)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(1, file_count)
        self.server.expect(JOB, {ATTR_k: 'de'}, id=jid)

    def test_direct_write_error_custom_path(self):
        """
        submit a sleep job and make sure that the files
        are getting directly written to the custom path
        provided in -e and -o option even when -doe is set.
        """
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        err_file = os.path.join(tmp_dir, 'error_file')
        out_file = os.path.join(tmp_dir, 'output_file')
        a = {ATTR_e: err_file, ATTR_o: out_file, ATTR_k: 'doe'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))])
        self.assertEqual(2, file_count)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)

    def test_direct_write_error_custom_dir(self):
        """
        submit a sleep job and make sure that the files
        are getting directly written to the custom dir
        provided in -e and -o option even when -doe is set.
        """
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_e: tmp_dir, ATTR_o: tmp_dir, ATTR_k: 'doe'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))])
        self.assertEqual(2, file_count)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)

    def test_direct_write_default_qsub_arguments(self):
        """
        submit a sleep job and make sure that the std_files
        are getting directly written to the mapped directory
        when default_qsub_arguments is set to -kdoe.
        """
        j = Job(TEST_USER)
        j.set_sleep_time(10)
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'default_qsub_arguments': '-kdoe'})
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(2, file_count)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)

    def test_direct_write_without_config_entry(self):
        """
        submit a sleep job and make sure that the std_files
        is directly written to the submission directory when it is
        accessible from mom and direct_files option is used
        but submission directory is not mapped in mom config file.
        """
        j = Job(TEST_USER, attrs={ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(2, file_count)

    def test_qalter_direct_write(self):
        """
        submit a job and make sure that it in queued state.
        alter the job with -koed and check whether it is
        reflecting in qstat -f output.
        """
        mydate = int(time.time()) + 60
        j = Job(TEST_USER)
        attribs = {
            ATTR_a: time.strftime(
                '%m%d%H%M',
                time.localtime(
                    float(mydate)))}
        j.set_attributes(attribs)
        jid = self.server.submit(j)
        attribs = {ATTR_k: 'oed'}
        try:
            self.server.alterjob(jid, attribs)
            if self.server.expect(JOB, {'job_state': 'W'},
                                  id=jid):
                self.server.expect(JOB, attribs,
                                   id=jid)
        except PbsAlterError as e:
            print(str(e))

    def test_qalter_direct_write_error(self):
        """
        submit a job and after it starts running alter
        the job with -koed and check whether expected
        error message appears
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        attribs = {ATTR_k: 'oed'}
        self.server.expect(JOB, {'job_state': 'R'})
        try:
            self.server.alterjob(jid, attribs)
        except PbsAlterError as e:
            self.assertTrue(
                'Cannot modify attribute while job running  Keep_Files'
                in e.msg[0])

    def test_direct_write_qrerun(self):
        """
        submit a sleep job and make sure that the std_files
        are written and when a job is rerun error message
        in logged in mom_log that it is skipping directly
        written/absent spool file as files are already
        present on first run of the job.
        """
        self.mom.add_config({'$logevent': '0xffffffff'})
        j = Job(TEST_USER, attrs={ATTR_k: 'doe'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.logger.info(self.msg)
        self.server.expect(JOB, {ATTR_k: 'doe'}, id=jid)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        self.server.rerunjob(jid)
        self.mom.log_match(
            "stage_file;Skipping directly written/absent spool file",
            max_attempts=10, interval=5)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(2, file_count)

    def test_direct_write_job_array(self):
        """
        submit a job array and make sure that the std_files
        is directly written to the submission directory when it is
        accessible from mom and direct_files option is used
        but submission directory is not mapped in mom config file.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        j = Job(TEST_USER, attrs={ATTR_k: 'doe', ATTR_J: '1-4'})
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, {ATTR_state + '=R': 4}, count=True,
                           id=jid, extend='t')
        self.logger.info('checking for directly written std files')
        file_list = [name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))]
        self.assertEqual(8, len(file_list))
        idn = jid[:jid.find('[]')]
        for std in ['o', 'e']:
            for sub_ind in range(1, 5):
                f_name = 'STDIN.' + std + idn + '.' + str(sub_ind)
                if f_name not in file_list:
                    raise self.failureException("std file " + f_name +
                                                " not found")

    def test_direct_write_job_array_custom_dir(self):
        """
        submit a job array and make sure that the files
        are getting directly written to the custom dir
        provided in -e and -o option even when -doe is set.
        """
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, self.mom.shortname)
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_e: tmp_dir, ATTR_o: tmp_dir, ATTR_k: 'doe', ATTR_J: '1-4'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(10)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.server.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, {ATTR_state + '=R': 4}, count=True,
                           id=jid, extend='t')
        self.logger.info('checking for directly written std files')
        file_list = [name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))]
        self.assertEqual(8, len(file_list))
        for ext in ['.OU', '.ER']:
            for sub_ind in range(1, 5):
                f_name = j.create_subjob_id(jid, sub_ind) + ext
                if f_name not in file_list:
                    raise self.failureException("std file " + f_name +
                                                " not found")
