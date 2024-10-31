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


class Test_passing_environment_variable_via_qsub(TestFunctional):
    """
    Test to check passing environment variables via qsub
    """

    def create_and_submit_job(self, user=None, attribs=None, content=None,
                              content_interactive=None, preserve_env=False):
        """
        create the job object and submit it to the server as 'user',
        attributes list 'attribs' script 'content' or 'content_interactive',
        and to 'preserve_env' if interactive job.
        """
        # A user=None value means job will be executed by current user
        # where the environment is set up
        if attribs is None:
            use_attribs = {}
        else:
            use_attribs = attribs
        retjob = Job(username=user, attrs=use_attribs)

        if content is not None:
            retjob.create_script(body=content)
        elif content_interactive is not None:
            retjob.interactive_script = content_interactive
            retjob.preserve_env = preserve_env

        return self.server.submit(retjob)

    def test_commas_in_custom_variable(self):
        """
        Submit a job with -v "var1='A,B,C,D'" and check that the value
        is passed correctly
        """
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}
        script = ['#PBS -v "var1=\'A,B,C,D\'"']
        script += ['env | grep var1']
        jid = self.create_and_submit_job(user=TEST_USER, content=script,
                                         attribs={ATTR_S: "/bin/bash"})
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]

        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)
        job_output = ""
        ret = self.du.cat(self.server.client, filename=job_outfile,
                          runas=TEST_USER, logerr=False)
        job_output = (' '.join(ret['out'])).strip()
        self.assertEqual(job_output, "var1=A,B,C,D")

    def test_passing_shell_function(self):
        """
        Define a shell function with new line characters and check that
        the function is passed correctly
        """
        # Check if ShellShock fix for exporting shell function in bash exists
        # on this system and what "BASH_FUNC_" format to use
        foo_scr = """#!/bin/bash
foo() { a=B; echo $a; }
export -f foo
env | grep foo
unset -f foo
exit 0
"""
        fn = self.du.create_temp_file(hostname=self.mom.hostname, body=foo_scr)
        self.du.chmod(hostname=self.mom.hostname, path=fn, mode=0o755)
        foo_msg = 'Failed to run foo_scr'
        ret = self.du.run_cmd(self.mom.hostname, cmd=fn)
        self.assertEqual(ret['rc'], 0, foo_msg)
        msg = 'BASH_FUNC_'
        n = 'foo'
        for m in ret['out']:
            if m.find(msg) != -1:
                n = m.split('=')[0]
                break
        # Adjustments in bash due to ShellShock malware fix in various OS
        script = """#!/bin/bash
foo() { if [ /bin/true ]; then\necho hello;\nfi\n}
export -f foo
#PBS -V
env | grep -A 3 foo\n
foo\n
"""
        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(user=TEST_USER, content=script,
                                         attribs={ATTR_S: "/bin/bash"})
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=2)
        job_output = ""
        ret = self.du.cat(self.server.client, filename=job_outfile,
                          runas=TEST_USER, logerr=False)
        job_output = ('\n'.join(ret['out'])).strip()
        match = n + \
            '=() {  if [ /bin/true ]; then\n echo hello;\n fi\n}\nhello'
        self.assertEqual(job_output, match,
                         msg="Environment variable foo content does "
                         "not match original")

    def test_option_V_dfltqsubargs(self):
        """
        Test exporting environment variable when -V is enabled
        in default_qsub_arguments.
        """
        os.environ["SET_IN_SUBMISSION"] = "true"
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'default_qsub_arguments': '-V'})
        j = Job(self.du.get_current_user())
        jid = self.server.submit(j)
        self.server.expect(JOB, {'Variable_List': (MATCH_RE,
                                                   'SET_IN_SUBMISSION=true')},
                           id=jid)

    def test_option_V_cmdline(self):
        """
        Test exporting environment variable when -V is passed
        through command line.
        """
        os.environ["SET_IN_SUBMISSION"] = "true"
        self.ATTR_V = 'Full_Variable_List'
        api_to_cli.setdefault(self.ATTR_V, 'V')
        a = {self.ATTR_V: None}
        j = Job(self.du.get_current_user(), attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'Variable_List': (MATCH_RE,
                                                   'SET_IN_SUBMISSION=true')},
                           id=jid)

    def test_option_V_dfltqsubargs_qsub_daemon(self):
        """
        Test whether the changed value of the exported
        environment variable is reflected if the submitted job
        goes to qsub daemon.
        """
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'default_qsub_arguments': '-V'})
        os.environ["SET_IN_SUBMISSION"] = "true"
        j = Job(self.du.get_current_user())
        jid = self.server.submit(j)
        os.environ["SET_IN_SUBMISSION"] = "false"
        j1 = Job(self.du.get_current_user())
        jid1 = self.server.submit(j1)
        self.server.expect(JOB, {'Variable_List': (MATCH_RE,
                                                   'SET_IN_SUBMISSION=true')},
                           id=jid)
        self.server.expect(JOB, {'Variable_List': (MATCH_RE,
                                                   'SET_IN_SUBMISSION=false')},
                           id=jid1)

    def test_passing_env_special_char_via_qsub(self):
        """
        Submit a job with -v ENV_TEST=N:\\aa\\bb\\cc\\dd\\ee\\ff\\gg\\hh\\ii
        and check that the value is passed correctly

        NOTE: As per the Guide 5.2.4.7 Special Characters
        in Variable_List Job Attribute
        Python requires that double quotes
        and backslashes also be escaped with a backslash
        """
        a = {ATTR_v: 'ENV_TEST="N:\\aa\\bb\\cc\\dd\\ee\\ff\\gg\\hh\\ii"'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid2)
        qstat = self.server.status(JOB, ATTR_v, id=jid2)
        job_outfile = qstat[0]['Variable_List']
        var_list = job_outfile.split(",")
        exp_string = 'ENV_TEST=N:\\\\\\\\aa\\\\\\\\bb\\\\\\\\cc\\\\\\\\dd'
        exp_string += '\\\\\\\\ee\\\\\\\\ff\\\\\\\\gg\\\\\\\\hh\\\\\\\\ii'
        self.assertIn(exp_string, var_list)

    def test_long_env(self):
        """
        Test to verify that job is able to process
        very long env attribute.
        """

        env = "VAR0=foobar"
        for i in range(1, 300):
            env = f"{env},VAR{i}=foobar"

        a = {ATTR_v: env}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)
        self.server.expect(JOB, {'job_state': 'R'}, id=jid)
        qstat = self.server.status(JOB, ATTR_v, id=jid)
        var_list = qstat[0]['Variable_List'].split(",")

        for i in range(0, 300):
            exp_string = f"VAR{i}=foobar"
            self.assertIn(exp_string, var_list)
