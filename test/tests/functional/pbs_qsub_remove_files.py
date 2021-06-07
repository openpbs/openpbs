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


class TestQsub_remove_files(TestFunctional):
    """
    validate qsub remove file option.
    """

    def test_remove_file_when_job_succeeds(self):
        """
        submit a sleep job and make sure that the std_files
        are getting deleted when remove_files option is used.
        """
        j = Job(TEST_USER, attrs={ATTR_R: 'oe'})
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'oe'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(0, file_count)

    def test_remove_file_sandbox_private(self):
        """
        submit a sleep job and make sure that the std_files
        are getting deleted when remove_files option is used
        and job is submitted with -Wsandbox=private.
        """
        j = Job(TEST_USER, attrs={ATTR_R: 'oe', ATTR_sandbox: 'private'})
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'oe'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(0, file_count)

    def test_remove_files_output_file(self):
        """
        submit a job with -Ro option and make sure the output file
        gets deleted after job finishes
        """
        j = Job(TEST_USER, attrs={ATTR_R: 'o'})
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'o'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        for name in os.listdir(sub_dir):
            p = re.search('STDIN.e*', name)
            if p:
                self.logger.info('Match found: ' + p.group())
            else:
                self.assertTrue(False)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(1, file_count)

    @requirements(mom_on_server=True)
    def test_remove_files_error_file(self):
        """
        submit a job with -Re option and make sure the error file
        gets deleted after job finishes and works with direct_write
        """
        j = Job(TEST_USER, attrs={ATTR_k: 'de', ATTR_R: 'e'})
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        mapping_dir = self.du.create_temp_dir(asuser=TEST_USER)
        self.mom.add_config(
            {'$usecp': self.mom.hostname + ':' + sub_dir +
             ' ' + mapping_dir})
        self.mom.restart()
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'e'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        for name in os.listdir(mapping_dir):
            p = re.search('STDIN.o*', name)
            if p:
                self.logger.info('Match found: ' + p.group())
            else:
                self.assertTrue(False)
        file_count = len([name for name in os.listdir(
            mapping_dir) if os.path.isfile(os.path.join(mapping_dir, name))])
        self.assertEqual(1, file_count)

    def test_remove_files_error_custom_path(self):
        """
        submit a sleep job and make sure that the files
        are getting deleted from custom path provided in
        -e and -o option when -Roe is set.
        """
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        err_file = os.path.join(tmp_dir, 'error_file')
        out_file = os.path.join(tmp_dir, 'output_file')
        a = {ATTR_e: err_file, ATTR_o: out_file, ATTR_R: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'oe'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))])
        self.assertEqual(0, file_count)

    def test_remove_files_error_custom_dir(self):
        """
        submit a sleep job and make sure that the files
        are getting deleted from custom directory path
        provided in -e and -o option when -Roe is set.
        """
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        a = {ATTR_e: tmp_dir, ATTR_o: tmp_dir, ATTR_R: 'oe'}
        j = Job(TEST_USER, attrs=a)
        j.set_sleep_time(5)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'oe'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))])
        self.assertEqual(0, file_count)

    def test_remove_files_default_qsub_arguments(self):
        """
        submit a sleep job and make sure that the std_files
        are removed after the job finishes from submission
        directory when default_qsub_arguments is set to -Roe.
        """
        j = Job(TEST_USER)
        j.set_sleep_time(5)
        self.server.manager(MGR_CMD_SET, SERVER, {
                            'default_qsub_arguments': '-Roe'})
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_R: 'oe'}, id=jid)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(0, file_count)

    def test_remove_file_when_job_fails(self):
        """
        submit a job using unavailable binary and make sure
        that the std_files are available when remove_files
        option is used.
        """
        j = Job(TEST_USER, attrs={ATTR_R: 'oe'})
        j.set_execargs('hostname')
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, 'job_state', op=UNSET, id=jid)
        file_count = len([name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))])
        self.assertEqual(2, file_count)

    def test_qalter_remove_files(self):
        """
        submit a job and make sure that it in queued state.
        alter the job with -Roe and check whether it is
        reflecting in qstat -f output.
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)
        attribs = {ATTR_R: 'oe'}
        try:
            self.server.alterjob(jid, attribs)
            self.server.expect(JOB, attribs, id=jid)
        except PbsAlterError as e:
            print(str(e))

    def test_qalter_direct_write_error(self):
        """
        submit a job and after it starts running alter
        the job with -Roe and check whether expected
        error message appears
        """
        j = Job(TEST_USER)
        jid = self.server.submit(j)
        attribs = {ATTR_R: 'oe'}
        self.server.expect(JOB, {'job_state': 'R'})
        try:
            self.server.alterjob(jid, attribs)
        except PbsAlterError as e:
            self.assertTrue(
                'Cannot modify attribute while job'
                ' running  Remove_Files' in e.msg[0])

    def test_remove_file_job_array(self):
        """
        submit job array script that makes subjobs to exit with 0 except for
        subjob[2] and make sure that the std_files for only subjob[2] are
        available when remove_files option is used.
        """
        script = \
            "#!/bin/sh\n"\
            "%s 3;\n"\
            "if [ $PBS_ARRAY_INDEX -eq 2 ]; then\n"\
            "exit 1; fi; exit 0;" % (self.mom.sleep_cmd)
        j = Job(TEST_USER, attrs={ATTR_R: 'oe', ATTR_J: '1-3'},
                jobname='JOB_NAME')
        j.create_script(script)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, ATTR_state, op=UNSET, id=jid)
        file_list = [name for name in os.listdir(
            sub_dir) if os.path.isfile(os.path.join(sub_dir, name))]
        self.assertEqual(2, len(file_list), "expected 2 std files")
        idn = jid[:jid.find('[]')]
        std_files = ['JOB_NAME.o' + idn + '.2', 'JOB_NAME.e' + idn + '.2']
        for f_name in std_files:
            if f_name not in file_list:
                raise self.failureException("std file " + f_name +
                                            " not found")

    def test_remove_file_custom_path_job_array(self):
        """
        submit job array script that makes subjobs to exit with 0 except for
        subjob[2] and make sure that the std_files for only subjob[2] are
        available in custom directory when remove_files option is used with
        -o and -e options.
        """
        script = \
            "#!/bin/sh\n"\
            "%s 3;\n"\
            "if [ $PBS_ARRAY_INDEX -eq 2 ]; then\n"\
            "exit 1; fi; exit 0;" % (self.mom.sleep_cmd)
        tmp_dir = self.du.create_temp_dir(asuser=TEST_USER)
        j = Job(TEST_USER, attrs={ATTR_e: tmp_dir, ATTR_o: tmp_dir,
                                  ATTR_R: 'oe', ATTR_J: '1-3'})
        j.create_script(script)
        sub_dir = self.du.create_temp_dir(asuser=TEST_USER)
        jid = self.server.submit(j, submit_dir=sub_dir)
        self.server.expect(JOB, {ATTR_state: 'B'}, id=jid)
        self.server.expect(JOB, ATTR_state, op=UNSET, id=jid)
        file_list = [name for name in os.listdir(
            tmp_dir) if os.path.isfile(os.path.join(tmp_dir, name))]
        self.assertEqual(2, len(file_list), "expected 2 std files")
        subj2_id = j.create_subjob_id(jid, 2)
        std_files = [subj2_id + '.OU', subj2_id + '.ER']
        for f_name in std_files:
            if f_name not in file_list:
                raise self.failureException("std file " + f_name +
                                            " not found")
