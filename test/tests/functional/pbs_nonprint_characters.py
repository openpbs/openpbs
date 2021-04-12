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
import os


class TestNonprintingCharacters(TestFunctional):
    """
    Test to check passing non-printable environment variables
    """

    def setUp(self):
        TestFunctional.setUp(self)
        a = {'job_history_enable': 'True'}
        self.server.manager(MGR_CMD_SET, SERVER, a)
        # Mapping of ASCII non-printable character to escaped representation
        self.npcat = {
            "\x00": "^@", "\x01": "^A", "\x02": "^B", "\x03": "^C",
            "\x04": "^D", "\x05": "^E", "\x06": "^F", "\x07": "^G",
            "\x08": "^H", "\x09": "^I", "\x0A": "^J", "\x0B": "^K",
            "\x0C": "^L", "\x0D": "^M", "\x0E": "^N", "\x0F": "^O",
            "\x10": "^P", "\x11": "^Q", "\x12": "^R", "\x13": "^S",
            "\x14": "^T", "\x15": "^U", "\x16": "^V", "\x17": "^W",
            "\x18": "^X", "\x19": "^Y", "\x1A": "^Z", "\x1B": "^[",
            "\x1C": "^\\", "\x1D": "^]", "\x1E": "^^", "\x1F": "^_"
        }

        # Exclude these:
        # NULL(\0) causes qsub error, LINE FEED(\n) causes error in expect()
        self.npch_exclude = ['\x00', '\x0A']

        # Characters displayed as is: TAB (\t), LINE FEED(\n)
        self.npch_asis = ['\x09', '\x0A']

        # Terminal control characters used in the tests
        self.bold = "\u001b[1m"
        self.red = "\u001b[31m"
        self.reset = "\u001b[0m"
        # Mapping of terminal control character to escaped representation
        self.bold_esc = "^[[1m"
        self.red_esc = "^[[31m"
        self.reset_esc = "^[[0m"

        self.ATTR_V = 'Full_Variable_List'
        api_to_cli.setdefault(self.ATTR_V, 'V')

        # Check if ShellShock fix for exporting shell function in bash exists
        # on this system and what "BASH_FUNC_" format to use
        foo_scr = """#!/bin/bash
foo() { a=B; echo $a; }
export -f foo
env | grep foo
unset -f foo
exit 0
"""
        self.script = """#PBS -V
env | grep -A2 BASH_FUNC_foo
foo
sleep 5
"""
        fn = self.du.create_temp_file(body=foo_scr)
        self.du.chmod(path=fn, mode=0o755)
        foo_msg = 'Failed to run foo_scr'
        ret = self.du.run_cmd(self.server.hostname, cmd=fn)
        self.assertEqual(ret['rc'], 0, foo_msg)
        msg = 'BASH_FUNC_'
        self.n = 'foo'
        for m in ret['out']:
            if m.find(msg) != -1:
                self.n = m.split('=')[0]
                continue

        # Client commands full path
        self.qstat_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                      'bin', 'qstat')
        self.qmgr_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                     'bin', 'qmgr')
        self.pbsnodes_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                         'bin', 'pbsnodes')

    def create_and_submit_job(self, user=None, attribs=None, content=None,
                              content_interactive=None, preserve_env=False,
                              set_env={}):
        """
        Create the job object and submit it to the server as 'user',
        attributes list 'attribs' script 'content' or 'content_interactive',
        and to 'preserve_env' if interactive job.
        """
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
        return self.server.submit(retjob, env=set_env)

    def check_jobout(self, chk_var, jid, job_outfile, host=None):
        """
        Check if unescaped variable is in job output
        """
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)
        ret = self.du.cat(hostname=host, sudo=True, filename=job_outfile,
                          option="-v")
        j_output = ""
        if len(ret['out']) > 0:
            if len(ret['out']) > 1:
                j_output = '\n'.join(ret['out'])
            else:
                j_output = ret['out'][0].strip()
        self.assertEqual(j_output, chk_var)
        self.logger.info('job output has: %s' % chk_var)

    def check_qstatout(self, chk_var, jid):
        """
        Check if escaped variable is in qstat -f output
        """
        cmd = [self.qstat_cmd, '-xf', jid]
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd)
        if '\t' in chk_var:
            job_str = ''.join(ret['out']).replace('\t\t', '\t')
        else:
            job_str = ''.join(ret['out']).replace('\t', '')
        self.assertIn(chk_var, job_str)
        self.logger.info('qstat -xf output has: %s' % chk_var)

    def test_nonprint_character_qsubv(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (x00), and LINE FEED (x0A) which will cause a qsub error,
        submit a job script with
        qsub -v "var1='A,B,<non-printable character>,C,D'"
        and check that the value with the character is passed correctly
        """
        uhost = PbsUser.get_user(TEST_USER).host
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = r'var1=A\,B\,%s\,C\,D' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = r'var1=A\,B\,%s\,C\,D' % ch
            if uhost is None or self.du.is_localhost(uhost):
                a = {ATTR_v: "var1=\'A,B,%s,C,D\'" % ch}
            else:
                a = {ATTR_v: r"var1=\'A\,B\,%s\,C\,D\'" % ch}
            script = ['sleep 10']
            script += ['env | grep var1']
            jid = self.create_and_submit_job(attribs=a, content=script)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Check if job output contains the character as is
            qstat = self.server.status(JOB, ATTR_o, id=jid)
            job_outfile = qstat[0][ATTR_o].split(':')[1]
            job_host = qstat[0][ATTR_o].split(':')[0]
            if ch == '\x09':
                chk_var = "var1=A,B,%s,C,D" % ch
            else:
                chk_var = "var1=A,B,%s,C,D" % self.npcat[ch]
            self.check_jobout(chk_var, jid, job_outfile, job_host)

    def test_nonprint_character_directive(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        submit a job script with PBS directive
        -v "var1='A,B,<non-printable character>,C,D'"
        and check that the value with the character is passed correctly
        """
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = r'var1=A\,B\,%s\,C\,D' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = r'var1=A\,B\,%s\,C\,D' % ch
            script = ['#PBS -v "var1=\'A,B,%s,C,D\'"' % ch]
            script += ['sleep 1']
            script += ['env | grep var1']
            jid = self.create_and_submit_job(content=script)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Check if job output contains the character
            qstat = self.server.status(JOB, ATTR_o, id=jid)
            job_outfile = qstat[0][ATTR_o].split(':')[1]
            job_host = qstat[0][ATTR_o].split(':')[0]
            if ch == '\x09':
                chk_var = "var1=A,B,%s,C,D" % ch
            else:
                chk_var = "var1=A,B,%s,C,D" % self.npcat[ch]
            self.check_jobout(chk_var, jid, job_outfile, job_host)

    def test_nonprint_character_qsubV(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        test exporting the character in environment variable
        when -V is passed through command line.
        """
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            script = ['sleep 5']
            script += ['env | grep NONPRINT_VAR']
            a = {self.ATTR_V: None, ATTR_S: '/bin/bash'}
            j = Job(TEST_USER, attrs=a)
            j.create_script(body=script)
            xval = "X%sY" % ch
            env_to_set = {"NONPRINT_VAR": xval}
            jid = self.server.submit(j, env=env_to_set)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Check if job output contains the character
            qstat = self.server.status(JOB, ATTR_o, id=jid)
            job_outfile = qstat[0][ATTR_o].split(':')[1]
            job_host = qstat[0][ATTR_o].split(':')[0]
            if ch == '\x09':
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            else:
                chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            self.check_jobout(chk_var, jid, job_outfile, job_host)

    def test_nonprint_character_default_qsubV(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        test exporting the character in environment variable
        when -V is in the server's default_qsub_arguments.
        """
        user = PbsUser.get_user(TEST_USER)
        host = user.host
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            os.environ["NONPRINT_VAR"] = "X%sY" % ch
            self.server.manager(MGR_CMD_SET, SERVER,
                                {'default_qsub_arguments': '-V'})
            script = ['sleep 5']
            script += ['env | grep NONPRINT_VAR']
            j = Job(TEST_USER, attrs={ATTR_S: '/bin/bash'})
            j.create_script(body=script)
            xval = "X%sY" % ch
            env_to_set = {"NONPRINT_VAR": xval}
            jid = self.server.submit(j, env=env_to_set)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Check if job output contains the character
            qstat = self.server.status(JOB, ATTR_o, id=jid)
            job_outfile = qstat[0][ATTR_o].split(':')[1]
            job_host = qstat[0][ATTR_o].split(':')[0]
            if ch == '\x09':
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            else:
                chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            self.check_jobout(chk_var, jid, job_outfile, job_host)

    def test_nonprint_shell_function(self):
        """
        Export a shell function with a non-printable character and check
        that the function is passed correctly.
        Using each of the non-printable ASCII characters, except
        NULL (hex 00), SOH (hex 01), TAB (hex 09), LINE FEED (hex 0A)
        which will cause problems in the exported shell function.
        """
        self.npch_exclude += ['\x01', '\x09']

        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            func = '{ a=%s; echo XX${a}YY}; }' % ch
            # Adjustments in bash due to ShellShock malware fix in various OS
            env_vals = {"foo()": func}
            chk_var = (self.n + '=() {  a=%s; echo XX${a}YY}}' %
                       self.npcat[ch])
            if ch in self.npch_asis:
                chk_var = self.n + '=() {  a=%s; echo XX${a}YY}}' % ch
            out = (self.n + '=() {  a=%s;\n echo XX${a}YY}\n}\nXX%sYY}' %
                   (self.npcat[ch], self.npcat[ch]))
            jid = self.create_and_submit_job(content=self.script,
                                             set_env=env_vals)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Check if job output contains the character
            qstat = self.server.status(JOB, ATTR_o, id=jid)
            job_outfile = qstat[0][ATTR_o].split(':')[1]
            job_host = qstat[0][ATTR_o].split(':')[0]
            self.check_jobout(out, jid, job_outfile, job_host)

    def test_terminal_control_in_qsubv(self):
        """
        Using terminal control in environment variable
        submit a job script with qsub
        -v "var1='X<terminal control>Y'"
        and check that the value with the character is passed correctly
        """
        chk_var = "var1=X%s%sY" % (self.bold_esc, self.red_esc)
        a = {ATTR_v: "var1=\'X%s%sY\'" % (self.bold, self.red)}
        script = ['env | grep var1']
        script += ['sleep 5']
        jid = self.create_and_submit_job(attribs=a, content=script)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check if job output contains the character
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        match = "var1=X%s%sY" % (self.bold_esc, self.red_esc)
        self.check_jobout(match, jid, job_outfile, job_host)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def test_terminal_control_in_directive(self):
        """
        Using terminal control in environment variable
        submit a job script with PBS directive
        -v "var1='X<terminal control>Y'"
        and check that the value with the character is passed correctly
        """
        chk_var = "var1=X%s%sY" % (self.bold_esc, self.red_esc)
        script = ['#PBS -v "var1=\'X%s%sY\'"' % (self.bold, self.red)]
        script += ['env | grep var1']
        script += ['sleep 5']
        jid = self.create_and_submit_job(content=script)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check if job output contains the character
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        match = "var1=X%s%sY" % (self.bold_esc, self.red_esc)
        self.check_jobout(match, jid, job_outfile, job_host)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def test_terminal_control_qsubV(self):
        """
        Test exporting terminal control in environment variable
        when -V is passed through command line.
        """
        exp = "X" + self.bold + self.red + "Y"
        chk_var = 'VAR_IN_TERM=X%s%sY' % (self.bold_esc, self.red_esc)
        job_script = ['sleep 5']
        job_script += ['env | grep VAR_IN_TERM']
        a = {self.ATTR_V: None, ATTR_S: '/bin/bash'}
        j = Job(TEST_USER, attrs=a)
        file_n = j.create_script(body=job_script)
        env_vals = {"VAR_IN_TERM": exp}
        jid = self.server.submit(j, env=env_vals)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check if job output contains the character
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        chk_var = 'VAR_IN_TERM=X%s%sY' % (self.bold_esc, self.red_esc)
        self.check_jobout(chk_var, jid, job_outfile, job_host)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def test_terminal_control_default_qsubV(self):
        """
        Test exporting terminal control in environment variable
        when -V is in the server's default_qsub_arguments.
        """
        chk_var = 'VAR_IN_TERM=X%s%sY' % (self.bold_esc, self.red_esc)
        exp = "X%s%sY" % (self.bold, self.red)
        self.server.manager(MGR_CMD_SET, SERVER,
                            {'default_qsub_arguments': '-V'})
        script = ['sleep 5']
        script += ['env | grep VAR_IN_TERM']
        env_to_set = {"VAR_IN_TERM": exp}
        j = Job(TEST_USER, attrs={ATTR_S: '/bin/bash'})
        j.create_script(body=script)
        jid = self.server.submit(j, env=env_to_set)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check if job output contains the character
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        chk_var = 'VAR_IN_TERM=X%s%sY' % (self.bold_esc, self.red_esc)
        self.check_jobout(chk_var, jid, job_outfile, job_host)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def test_terminal_control_shell_function(self):
        """
        Export a shell function with terminal control
        characters and check that the function is passed correctly
        """
        func = '{ a=$(%s; %s); echo XX${a}YY; }' % (self.bold, self.red)
        # Adjustments in bash due to ShellShock malware fix in various OS
        env_vals = {"foo()": func}
        chk_var = self.n + '=() {  a=$(%s; %s); echo XX${a}YY}' % (
            self.bold_esc, self.red_esc)
        out = self.n + '=() {  a=$(%s; %s);\n echo XX${a}YY\n}\nXXYY' % (
            self.bold_esc, self.red_esc)
        jid = self.create_and_submit_job(content=self.script, set_env=env_vals)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check if job output contains the character
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        self.check_jobout(out, jid, job_outfile, job_host)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def find_in_tracejob(self, msg, jid):
        """
        Find msg in tracejob output of jid.
        """
        rc = 0
        tracejob_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                    'bin', 'tracejob')
        cmd = [tracejob_cmd, jid]
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
        self.assertEqual(ret['rc'], 0)
        for m in ret['out']:
            if m.find(msg) != -1:
                self.logger.info('Found \"%s\" in tracejob output' % msg)
                rc += 1
                continue
        return rc

    def find_in_printjob(self, msg, jid):
        """
        Find msg in printjob output of jid.
        """
        self.server.expect(JOB, {ATTR_state: 'R'}, offset=1, id=jid)
        rc = 0
        jbfile = os.path.join(self.mom.pbs_conf['PBS_HOME'], 'mom_priv',
                              'jobs', jid + '.JB')
        printjob_cmd = os.path.join(self.server.pbs_conf['PBS_EXEC'],
                                    'bin', 'printjob')
        cmd = [printjob_cmd, jbfile]
        ret = self.du.run_cmd(self.mom.hostname, cmd=cmd, sudo=True)
        self.assertEqual(ret['rc'], 0)
        for m in ret['out']:
            if m.find(msg) != -1:
                self.logger.info('Found \"%s\" in printjob output' % msg)
                rc += 1
                continue
        return rc

    def test_nonprint_character_in_qsubA(self):
        """
        Using each of the non-printable ASCII characters, except
        NULL (hex 00) and LINE FEED (hex 0A),
        submit a job script with Account_Name containing the character
        qsub -A "J<non-printable character>K"
        and check that the value with the character is passed correctly
        """
        uhost = PbsUser.get_user(TEST_USER).host
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            if uhost is None or self.du.is_localhost(uhost):
                a = {ATTR_A: "J%sK" % ch}
            else:
                a = {ATTR_A: "'J%sK'" % ch}
            j = Job(TEST_USER, a)
            jid = self.server.submit(j)
            job_stat = self.server.status(JOB, id=jid)
            acct_name = job_stat[0]['Account_Name']
            self.logger.info("job Account_Name: %s" % repr(acct_name))
            exp_name = 'J%sK' % self.npcat[ch]
            if ch in self.npch_asis:
                exp_name = 'J%sK' % ch
            self.logger.info("exp Account_Name: %s" % repr(exp_name))
            self.assertEqual(acct_name, exp_name)
            # Check printjob output
            msg = 'Account_Name = %s' % exp_name
            rc = self.find_in_printjob(msg, jid)
            self.assertEqual(rc, 1)
            # Check tracejob output
            msg = 'account="%s"' % exp_name
            rc = self.find_in_tracejob(msg, jid)
            self.assertGreaterEqual(rc, 1)
            self.server.delete(jid)
            self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)

    def test_terminal_control_in_qsubA(self):
        """
        Using terminal control in environment variable
        submit a job script with Account_Name
        qsub -A "J<terminal control>K"
        and check that the value with the character is passed correctly
        """
        j = Job(TEST_USER, {ATTR_A: "J%s%sK" % (self.bold, self.red)})
        jid = self.server.submit(j)
        job_stat = self.server.status(JOB, id=jid)
        acct_name = job_stat[0]['Account_Name']
        self.logger.info("job Account_Name: %s" % repr(acct_name))
        exp_name = 'J%s%sK' % (self.bold_esc, self.red_esc)
        self.logger.info("exp Account_Name: %s" % exp_name)
        self.assertEqual(acct_name, exp_name)
        # Check printjob output
        msg = 'Account_Name = %s' % exp_name
        rc = self.find_in_printjob(msg, jid)
        self.assertEqual(rc, 1)
        # Check tracejob output
        msg = 'account="%s"' % exp_name
        rc = self.find_in_tracejob(msg, jid)
        self.assertGreaterEqual(rc, 1)
        self.logger.info('%sReset terminal' % self.reset)

    def find_in_json_valid(self, cmd, msg, jid):
        """
        Check if qstat json output is valid of jid and find msg in output.
        Returns 2 or greater on success (valid + found).
        """
        rc = 0
        if cmd == 'qstat':
            qstat_cmd_json = self.qstat_cmd + ' -f -F json ' + str(jid)
            ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_json)
        elif cmd == 'nodes':
            nodes_cmd_json = self.pbsnodes_cmd + ' -av -F json'
            ret = self.du.run_cmd(self.server.hostname, cmd=nodes_cmd_json)
        ret_out = "\n".join(ret['out'])
        try:
            json.loads(ret_out)
        except ValueError as err:
            self.assertFalse(err)
        rc += 1
        self.logger.info('json output is valid')
        # Check msg is in output
        for m in ret['out']:
            if m.find(msg) != -1:
                self.logger.info('Found \"%s\" in json output' % msg)
                rc += 1
                continue
        return rc

    @skipOnShasta
    def test_nonprint_character_in_qstat_json_valid(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        and File Separator (hex 1C) which will cause invalid json,
        submit a job script with
        qsub -v "var1='A,B,<non-printable character>,C,D'"
        and check that the qstat -f -F json output is valid
        """
        uhost = PbsUser.get_user(TEST_USER).host
        self.npch_exclude += ['\x1C']
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            if self.du.is_localhost(uhost):
                a = {ATTR_v: "var1=\'A,B,%s,C,D\'" % ch, ATTR_S: '/bin/bash'}
            else:
                a = {ATTR_v: r"var1=\'A\,B\,%s\,C\,D\'" % ch}
            msg = 'A,B,%s,C,D' % self.npcat[ch]
            npch_msg = {
                '\x08': 'A,B,\\b,C,D',
                '\x09': 'A,B,\\t,C,D',
                '\x0C': 'A,B,\\f,C,D',
                '\x0D': 'A,B,\\r,C,D'
            }
            if ch in npch_msg:
                msg = npch_msg[ch]
            script = ['env | grep var1']
            script += ['sleep 5']
            jid = self.create_and_submit_job(attribs=a, content=script)
            rc = self.find_in_json_valid('qstat', msg, jid)
            self.assertGreaterEqual(rc, 2)

    def test_terminal_control_in_qstat_json_valid(self):
        """
        Using terminal control in environment variable
        submit a job script with qsub
        -v "var1='<terminal control>XY<terminal control>'"
        and check that the qstat -f -F json output is valid
        """
        a = {ATTR_v: "var1=\'%s%sXY%s\'" % (self.bold, self.red, self.reset)}
        msg = "%s%sXY%s" % (self.bold_esc, self.red_esc, self.reset_esc)
        script = ['env | grep var1']
        script += ['sleep 5']
        jid = self.create_and_submit_job(attribs=a, content=script)
        rc = self.find_in_json_valid('qstat', msg, jid)
        self.assertGreaterEqual(rc, 2)

    def test_nonprint_character_in_qstat_dsv(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        submit a job script with
        qsub -v "var1='AB<non-printable character>CD'"
        and check that the 'qstat -f -F dsv' output contains proper var1
        """
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            a = {ATTR_v: "var1=\'AB%sCD\'" % ch}
            script = ['env | grep var1']
            jid = self.create_and_submit_job(attribs=a, content=script)
            qstat_cmd_dsv = self.qstat_cmd + ' -f -F dsv ' + str(jid)
            ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_dsv)
            qstat_out = "\n".join(ret['out'])
            match = 'var1=AB%sCD' % self.npcat[ch]
            if qstat_out.find(match) != -1:
                self.logger.info('Found %s in qstat -f -F dsv output' % match)

    def test_terminal_control_in_qstat_dsv(self):
        """
        Using terminal control in environment variable
        submit a job script with qsub
        -v "var1='<terminal control>XY<terminal control>'"
        and check that the 'qstat -f -F dsv' output contains proper var1
        """
        a = {ATTR_v: "var1=\'%s%sXY%s\'" % (self.bold, self.red, self.reset)}
        script = ['env | grep var1']
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat_cmd_dsv = self.qstat_cmd + ' -f -F dsv ' + str(jid)
        ret = self.du.run_cmd(self.server.hostname, cmd=qstat_cmd_dsv)
        qstat_out = "\n".join(ret['out'])
        match = 'var1=%s%sXY%s' % (self.bold_esc, self.red_esc, self.reset_esc)
        if qstat_out.find(match) != -1:
            self.logger.info('Found %s in qstat -f -F dsv output' % match)

    @timeout(1200)
    def test_nonprint_character_job_array(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        test exporting the character in environment variable of
        job array when qsub -V is passed through command line.
        """
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            exp = "X%sY" % ch
            set_env = {"NONPRINT_VAR": exp}
            script = ['sleep 5']
            script += ['env | grep NONPRINT_VAR']
            a = {self.ATTR_V: None, ATTR_J: '1-2', ATTR_S: '/bin/bash'}
            j = Job(TEST_USER, attrs=a)
            j.create_script(body=script)
            jid = self.server.submit(j, env=set_env)
            subj1 = jid.replace('[]', '[1]')
            subj2 = jid.replace('[]', '[2]')
            # Check if qstat -f output contains the escaped character
            ja = [jid, subj1, subj2]
            for j in ja:
                # Check if qstat -f output contains the escaped character
                self.check_qstatout(chk_var, j)
            qstat1 = self.server.status(JOB, ATTR_o, id=subj1, extend='x')
            job_outfile1 = qstat1[0][ATTR_o].split(':')[1]
            job_host = qstat1[0][ATTR_o].split(':')[0]
            if job_outfile1.split('.')[2] == '^array_index^':
                job_outfile1 = job_outfile1.replace('^array_index^', '1')
            job_outfile2 = job_outfile1.replace('.1', '.2')
            # Check if job array output contains the character as is
            if ch == '\x09':
                chk_var = 'NONPRINT_VAR=X%sY' % ch
            else:
                chk_var = 'NONPRINT_VAR=X%sY' % self.npcat[ch]
            self.check_jobout(chk_var, subj1, job_outfile1, job_host)
            self.check_jobout(chk_var, subj2, job_outfile2, job_host)

    def test_terminal_control_job_array(self):
        """
        Using terminal control in environment variable of
        job array when qsub -V is passed through command line.
        """
        # variable to check if with escaped nonprinting character
        chk_var = 'NONPRINT_VAR=X%s%sY' % (self.bold_esc, self.red_esc)
        env_vals = {"NONPRINT_VAR": "X%s%sY" % (self.bold, self.red)}
        script = ['sleep 5']
        script += ['env | grep NONPRINT_VAR']
        a = {self.ATTR_V: None, ATTR_J: '1-2', ATTR_S: '/bin/bash'}
        j = Job(TEST_USER, attrs=a)
        j.create_script(body=script)
        jid = self.server.submit(j, env=env_vals)
        subj1 = jid.replace('[]', '[1]')
        subj2 = jid.replace('[]', '[2]')
        # Check if qstat -f output contains the escaped character
        ja = [jid, subj1, subj2]
        for j in ja:
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, j)
        qstat1 = self.server.status(JOB, ATTR_o, id=subj1)
        job_outfile1 = qstat1[0][ATTR_o].split(':')[1]
        job_host = qstat1[0][ATTR_o].split(':')[0]
        if job_outfile1.split('.')[2] == '^array_index^':
            job_outfile1 = job_outfile1.replace('^array_index^', '1')
        job_outfile2 = job_outfile1.replace('.1', '.2')
        # Check if job array output contains the character as is
        chk_var = 'NONPRINT_VAR=X%s%sY' % (self.bold_esc, self.red_esc)
        self.check_jobout(chk_var, subj1, job_outfile1, job_host)
        self.logger.info('%sReset terminal' % self.reset)
        self.check_jobout(chk_var, subj2, job_outfile2, job_host)
        self.logger.info('%sReset terminal' % self.reset)

    @checkModule("pexpect")
    def test_nonprint_character_interactive_job(self):
        """
        Using each of the non-printable ASCII characters, except NULL
        (hex 00) and LINE FEED (hex 0A) which will cause a qsub error,
        test exporting the character in environment variable of
        interactive job when qsub -V is passed through command line.
        """
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # variable to check if with escaped nonprinting character or not
            chk_var = r'NONPRINT_VAR=X\,%s\,Y' % self.npcat[ch]
            if ch in self.npch_asis:
                chk_var = r'NONPRINT_VAR=X\,%s\,Y' % ch
            os.environ["NONPRINT_VAR"] = "X,%s,Y" % ch
            fn = self.du.create_temp_file(prefix="job_out1")
            self.job_out1_tempfile = fn
            # submit an interactive job
            cmd = 'env > ' + self.job_out1_tempfile
            a = {self.ATTR_V: None, ATTR_inter: ''}
            interactive_script = [('hostname', '.*'), (cmd, '.*'),
                                  ('sleep 5', '.*')]
            jid = self.create_and_submit_job(
                attribs=a,
                content_interactive=interactive_script,
                preserve_env=True)
            # Check if qstat -f output contains the escaped character
            self.check_qstatout(chk_var, jid)
            # Once all commands sent and matched, job exits
            self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)
            # Check for the non-printable character in the output file
            with open(self.job_out1_tempfile, newline="") as fd:
                pkey = ""
                penv = {}
                for line in fd:
                    fields = line.split('=', 1)
                    if len(fields) == 2:
                        pkey = fields[0]
                        penv[pkey] = fields[1]
            np_var = penv['NONPRINT_VAR']
            np_char = np_var.split(',')[1]
            self.assertEqual(ch, np_char)
            self.logger.info(
                "non-printable %s was in interactive job environment"
                % repr(np_char))

    @checkModule("pexpect")
    def test_terminal_control_interactive_job(self):
        """
        Using terminal control characters test exporting them
        in environment variable of interactive job
        when qsub -V is passed through command line.
        """
        # variable to check if with escaped nonprinting character
        chk_var = r'NONPRINT_VAR=X\,%s\,%s\,Y' % (self.bold_esc, self.red_esc)
        var = "X,%s,%s,Y" % (self.bold, self.red)
        os.environ["NONPRINT_VAR"] = var
        fn = self.du.create_temp_file(prefix="job_out1")
        self.job_out1_tempfile = fn
        # submit an interactive job
        cmd = 'env > ' + self.job_out1_tempfile
        a = {self.ATTR_V: None, ATTR_inter: ''}
        interactive_script = [('hostname', '.*'), (cmd, '.*'),
                              ('sleep 5', '.*')]
        jid = self.create_and_submit_job(
            attribs=a,
            content_interactive=interactive_script,
            preserve_env=True)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Once all commands sent and matched, job exits
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=1)
        # Parse for the non-printable character in the output file
        with open(self.job_out1_tempfile) as fd:
            pkey = ""
            penv = {}
            for line in fd:
                fields = line.split('=', 1)
                if len(fields) == 2:
                    pkey = fields[0]
                    penv[pkey] = fields[1]
        np_var = penv['NONPRINT_VAR']
        self.logger.info("np_var: %s" % repr(np_var))
        np_char1 = np_var.split(',')[1]
        np_char2 = np_var.split(',')[2]
        var_env = "X,%s,%s,Y" % (np_char1, np_char2)
        self.logger.info(
            "np_chars are: %s and %s" % (repr(np_char1), repr(np_char2)))
        self.assertEqual(var, var_env)
        self.logger.info(
            "non-printables were in interactive job environment %s"
            % repr(var_env))

    def test_terminal_control_begin_launch_hook(self):
        """
        Using terminal control characters test exporting them
        in environment variable of job having hooks execjob_begin and
        execjob_launch when qsub -V is passed through command line.
        """
        # variable to check if with escaped nonprinting character
        chk_var = 'NONPRINT_VAR=X\,%s\,%s\,Y' % (self.bold_esc, self.red_esc)
        var = "X,%s,%s,Y" % (self.bold, self.red)
        env_vals = {"NONPRINT_VAR": var}
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 3,
             self.ATTR_V: None}
        script = ['env\n']
        script += ['sleep 5\n']
        # hook1: execjob_begin
        hook_body = """
import pbs
e=pbs.event()
e.job.Variable_List["BEGIN_NONPRINT"] = "AB"
pbs.logmsg(pbs.LOG_DEBUG,"Variable List is %s" % (e.job.Variable_List,))
"""
        hook_name = "begin"
        a2 = {'event': "execjob_begin", 'enabled': 'True', 'debug': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a2,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)
        # hook2: execjob_launch
        hook_body = """
import pbs
e=pbs.event()
e.env["LAUNCH_NONPRINT"] = "CD"
"""
        hook_name = "launch"
        a2 = {'event': "execjob_launch", 'enabled': 'True', 'debug': 'True'}
        rv = self.server.create_import_hook(
            hook_name,
            a2,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        # Submit a job with hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script,
                                         set_env=env_vals)
        # Check if qstat -f output contains the escaped character
        self.check_qstatout(chk_var, jid)
        # Check for the non-printable character in the job output file
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        job_host = qstat[0][ATTR_o].split(':')[0]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=3)
        ret = self.du.cat(
            hostname=job_host,
            filename=job_outfile,
            sudo=True,
            option="-v")
        j_output = ret['out']
        penv = {}
        for line in j_output:
            fields = line.split('=', 1)
            if len(fields) == 2:
                pkey = fields[0]
                penv[pkey] = fields[1]
        np_var = penv['NONPRINT_VAR']
        self.logger.info("np_var: %s" % repr(np_var))
        np_char1 = np_var.split(',')[1]
        np_char2 = np_var.split(',')[2]
        var_env = "X,%s,%s,Y" % (np_char1, np_char2)
        var = "X,%s,%s,Y" % (self.bold_esc, self.red_esc)
        self.logger.info(
            "np_chars are: %s and %s" % (repr(np_char1), repr(np_char2)))
        self.assertEqual(var, var_env)
        self.logger.info(
            "non-printables were in interactive job environment %s"
            % repr(var_env))

    def check_print_list_hook(self, hook_name, hook_name_esc):
        """
        Check if the hook_name_esc is displayed in the output of qmgr
        'print hook' and 'list hook'
        """
        # Print hook displays escaped nonprinting characters
        phook = 'create hook %s' % hook_name_esc
        cmd = [self.qmgr_cmd, '-c', 'print hook']
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
        self.assertEqual(ret['rc'], 0)
        if phook in ret['out']:
            self.logger.info('Found \"%s\" in print hook output' % phook)
        # List hook displays escaped nonprinting characters
        lhook = 'Hook %s' % hook_name_esc
        cmd = [self.qmgr_cmd, '-c', 'list hook']
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
        self.assertEqual(ret['rc'], 0)
        if lhook in ret['out']:
            self.logger.info('Found \"%s\" in list hook output' % lhook)

    def test_terminal_control_hook_name(self):
        """
        Test using terminal control characters in hook name. Qmgr
        'print hook' and 'list hook' displays the escaped nonprint character.
        """
        hook_name = "h%s%sd" % (self.bold, self.red)
        create_hook = [self.qmgr_cmd, '-c', 'create hook %s' % hook_name]
        delete_hook = [self.qmgr_cmd, '-c', 'delete hook %s' % hook_name]
        list_hook = [self.qmgr_cmd, '-c', 'list hook %s' % hook_name]
        # Delete hook if hook already exists
        ret = self.du.run_cmd(self.server.hostname, cmd=list_hook, sudo=True)
        if ret['rc'] == 0:
            ret = self.du.run_cmd(self.server.hostname,
                                  cmd=delete_hook, sudo=True)
            self.assertEqual(ret['rc'], 0)
        # Create hook. Qmgr print,list hook output will have escaped chars
        ret = self.du.run_cmd(self.server.hostname, cmd=create_hook, sudo=True)
        self.assertEqual(ret['rc'], 0)
        hook_name_esc = "h%s%sd" % (self.bold_esc, self.red_esc)
        self.check_print_list_hook(hook_name, hook_name_esc)
        # Delete the hook
        ret = self.du.run_cmd(self.server.hostname, cmd=delete_hook, sudo=True)
        self.assertEqual(ret['rc'], 0)
        # Reset the terminal
        self.logger.info('%sReset terminal' % self.reset)

    def test_nonprint_character_hook_name(self):
        """
        Use in a hook name each of the non-printable ASCII characters, except
        NULL (x00), TAB (x09), LINE FEED (x0A), VT (x0B), FF (x0C), CR (x0D)
        which will cause a qmgr create hook error. Qmgr 'print hook' and
        'list hook' displays the escaped nonprint character.
        """
        self.npch_exclude += ['\x09', '\x0B', '\x0C', '\x0D']
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            # Create hook
            hk_name = 'h%sd' % ch
            a = {'event': "execjob_begin", 'enabled': 'True', 'debug': 'True'}
            try:
                rv = self.server.create_hook(hk_name, a)
            except PbsManagerError:
                # Delete pre-existing hook first then create the hook
                self.server.manager(MGR_CMD_DELETE, HOOK, id=hk_name)
                rv = self.server.create_hook(hk_name, a)
            self.assertTrue(rv)
            hk_name_esc = "h%sd" % self.npcat[ch]
            self.check_print_list_hook(hk_name, hk_name_esc)
            self.server.manager(MGR_CMD_DELETE, HOOK, id=hk_name)

    def test_terminal_control_in_rsubH(self):
        """
        Using terminal control in authorized hostnames submit a reservation
        pbs_rsub -H "h<terminal control>d" and check that the escaped
        representation is displayed in pbs_rstat correctly.
        """
        r = Reservation(TEST_USER, {"-H": "h%s%sd" % (self.bold, self.red)})
        rid = self.server.submit(r)
        resv_stat = self.server.status(RESV, id=rid)
        auth_hname = resv_stat[0]['Authorized_Hosts']
        self.logger.info("job Authorized_Hosts: %s" % auth_hname)
        exp_name = 'h%s%sd' % (self.bold_esc, self.red_esc)
        self.logger.info("expected Authorized_Hosts: %s" % exp_name)
        self.assertEqual(auth_hname, exp_name)
        self.logger.info('%sReset terminal' % self.reset)

    def test_nonprint_character_in_rsubH(self):
        """
        Using each of the non-printable ASCII characters, except NULL (hex 00)
        and LINE FEED (hex 0A), submit a reservation with authorized hostnames
        pbs_rsub -H "h<terminal control>d" and check that the escaped
        representation is displayed in pbs_rstat correctly.
        """
        uhost = PbsUser.get_user(TEST_USER).host
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            if uhost is None or self.du.is_localhost(uhost):
                h = {"-H": "h%sd" % ch}
            else:
                h = {"-H": "'h%sd'" % ch}
            r = Reservation(TEST_USER, h)
            rid = self.server.submit(r)
            resv_stat = self.server.status(RESV, id=rid)
            auth_hname = resv_stat[0]['Authorized_Hosts']
            self.logger.info("job Authorized_Hosts: %s" % auth_hname)
            exp_name = 'h%sd' % self.npcat[ch]
            if ch in self.npch_asis:
                exp_name = 'h%sd' % ch
            self.logger.info("expected Authorized_Hosts: %s" % exp_name)
            self.assertEqual(auth_hname, exp_name)
            self.server.delete(rid)

    def test_terminal_control_in_node_comment(self):
        """
        Test if pbsnodes -C with terminal control characters results in
        valid json and escaped representation id displayed correctly.
        """
        comment = 'h%s%sd%s' % (self.bold, self.red, self.reset)
        cmd = [self.pbsnodes_cmd, '-C', '%s' % comment, self.mom.shortname]
        self.du.run_cmd(self.server.hostname, cmd=cmd)
        # Check json output
        comm1 = 'h%s%sd%s' % (self.bold_esc, self.red_esc, self.reset_esc)
        rc = self.find_in_json_valid('nodes', comm1, None)
        self.assertGreaterEqual(rc, 2)
        # Check qmgr -c 'list node @default' output
        comm2 = '    comment = %s' % comm1
        cmd = [self.qmgr_cmd, '-c', 'list node @default']
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
        self.assertEqual(ret['rc'], 0)
        if comm2 in ret['out']:
            self.logger.info('Found \"%s\" in qmgr list node output' % comm2)
        # Check pbsnodes -a output
        comm3 = '     comment = %s' % comm1
        cmd = [self.pbsnodes_cmd, '-a']
        ret = self.du.run_cmd(self.server.hostname, cmd=cmd)
        self.assertEqual(ret['rc'], 0)
        if comm3 in ret['out']:
            self.logger.info('Found \"%s\" in pbsnodes -a output' % comm3)

    def test_nonprint_character_in_node_comment(self):
        """
        Using each of the non-printable ASCII characters, except NULL (hex 00),
        LINE FEED (hex 0A), and File Separator (hex 1C) which will cause
        invalid json, test if pbsnodes -C with special characters results in
        valid json and escaped representation id displayed correctly.
        """
        self.npch_exclude += ['\x1C']
        for ch in self.npcat:
            self.logger.info('##### non-printable char: %s #####' % repr(ch))
            if ch in self.npch_exclude:
                self.logger.info('##### excluded char: %s' % repr(ch))
                continue
            comment = 'h%sd' % ch
            cmd = [self.pbsnodes_cmd, '-C', '%s' % comment, self.mom.shortname]
            self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
            comm1 = 'h%sd' % self.npcat[ch]
            if ch in self.npch_asis:
                comm1 = 'h%sd' % ch
            json_msg = {
                '\x08': 'h\\bd',
                '\x09': 'h\\td',
                '\x0C': 'h\\fd',
                '\x0D': 'h\\rd'
            }
            if ch in json_msg:
                comm1 = json_msg[ch]
            # Check json output
            rc = self.find_in_json_valid('nodes', comm1, None)
            self.assertGreaterEqual(rc, 2)
            # Check qmgr -c 'list node @default' output
            comm2 = '    comment = %s' % comm1
            cmd = [self.qmgr_cmd, '-c', 'list node @default']
            ret = self.du.run_cmd(self.server.hostname, cmd=cmd, sudo=True)
            self.assertEqual(ret['rc'], 0)
            if comm2 in ret['out']:
                self.logger.info('Found \"%s\" in qmgr list node out' % comm2)
            # Check pbsnodes -a output
            comm3 = '     comment = %s' % comm1
            cmd = [self.pbsnodes_cmd, '-a']
            ret = self.du.run_cmd(self.server.hostname, cmd=cmd)
            self.assertEqual(ret['rc'], 0)
            if comm3 in ret['out']:
                self.logger.info('Found \"%s\" in pbsnodes -a output' % comm3)
