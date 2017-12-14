# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
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
import os
from tests.functional import *


class TestPbsHookSetJobEnv(TestFunctional):
    """
    This test suite to make sure hooks properly
    handle environment variables with special characters,
    values, in particular newline (\n), commas (,), semicolons (;),
    single quotes ('), double quotes ("), and backaslashes (\).
    PRE: Set up currently executing user's environment to have variables
         whose values have the special characters.
         Job A: Submit a job using the -V option (pass current environment)
         where there are NO hooks in the system.
         Introduce execjob_begin and execjob_launch hooks in the system.
         Let the former update pbs.event().job.Variable_List while the latter
         update pbs.event().env.
         Job B: Submit a job using the -V option (pass current environment)
         where there are now mom hooks in the system.
    POST: Job A and Job B would see the same environment variables, with
          Job B also seeing the changes made to the job by the 2 mom hooks.
    """

    # List of environment variables not to compare between
    # job ran without hooks, job ran with hooks.
    exclude_env = []
    env_nohook = {}
    env_nohook_exclude = {}
    env_hook = {}
    env_hook_exclude = {}

    def setUp(self):
        """
        Set environment variables
        """
        TestFunctional.setUp(self)
        # Set environment variables with special characters
        os.environ['TEST_COMMA'] = '1,2,3,4'
        os.environ['TEST_RETURN'] = """'3,
4,
5'"""
        os.environ['TEST_SEMICOLON'] = ';'
        os.environ['TEST_ENCLOSED'] = '\',\''
        os.environ['TEST_COLON'] = ':'
        os.environ['TEST_BACKSLASH'] = '\\'
        os.environ['TEST_DQUOTE'] = '"'
        os.environ['TEST_DQUOTE2'] = 'happy days"are"here to stay'
        os.environ['TEST_DQUOTE3'] = 'nothing compares" to you'
        os.environ['TEST_DQUOTE4'] = '"music makes the people"'
        os.environ['TEST_DQUOTE5'] = 'music "makes \'the\'"people'
        os.environ['TEST_DQUOTE6'] = 'lalaland"'
        os.environ['TEST_SQUOTE'] = '\''
        os.environ['TEST_SQUOTE2'] = 'happy\'days'
        os.environ['TEST_SQUOTE3'] = 'the days\'are here now\'then'
        os.environ['TEST_SQUOTE4'] = '\'the way that was\''
        os.environ['TEST_SQUOTE5'] = 'music \'makes "the\'"people'
        os.environ['TEST_SQUOTE6'] = 'loving\''
        os.environ['TEST_SPECIAL'] = "{}[]()~@#$%^&*!"
        os.environ['TEST_SPECIAL2'] = "<dumb-test_text>"

        # List of environment variables not to compare between
        # job ran without hooks, job ran with hooks.
        self.exclude_env = ['PBS_NODEFILE']
        self.exclude_env += ['PBS_JOBID']
        self.exclude_env += ['PBS_JOBCOOKIE']
        # Each job submitted by default gets a unique jobname
        self.exclude_env += ['PBS_JOBNAME']
        self.exclude_env += ['TMPDIR']
        self.exclude_env += ['happy']

        self.ATTR_V = 'Full_Variable_List'
        api_to_cli.setdefault(self.ATTR_V, 'V')

        # temporary files
        (fd, fn) = tempfile.mkstemp(prefix="job_out1")
        os.close(fd)
        self.job_out1_tempfile = fn

        (fd, fn) = tempfile.mkstemp(prefix="job_out2")
        os.close(fd)
        self.job_out2_tempfile = fn

        (fd, fn) = tempfile.mkstemp(prefix="job_out3")
        os.close(fd)
        self.job_out3_tempfile = fn

    def tearDown(self):
        TestFunctional.tearDown(self)
        try:
            os.remove(self.job_out1_tempfile)
            os.remove(self.job_out2_tempfile)
            os.remove(self.job_out3_tempfile)

        except OSError:
            pass

    def read_env(self, outputfile, ishook):
        """
        Parse the output file and store the
        variable list in a dictionary
        """

        with open(outputfile) as fd:
            pkey = ""
            tmpenv = {}
            penv = {}
            penv_exclude = {}
            for line in fd:
                l = line.split("=", 1)
                if (len(l) == 2):
                    pkey = l[0]
                    if pkey not in self.exclude_env:
                        penv[pkey] = l[1]
                        tmpenv = penv
                    else:
                        penv_exclude[pkey] = l[1]
                        tmpenv = penv_exclude
                elif pkey != "":
                    # append to previous dictionary entry
                    tmpenv[pkey] += l[0]
        if (ishook == "hook"):
            self.env_hook = penv
            self.env_hook_exclude = penv_exclude
        else:
            self.env_nohook = penv
            self.env_nohook_exclude = penv_exclude

    def common_log_match(self, daemon):
        """
        Validate the env variable output in daemon logs
        """
        logmsg = ["TEST_COMMA=1\,2\,3\,4",
                  "TEST_SEMICOLON=;",
                  "TEST_ENCLOSED=\\'\,\\'",
                  "TEST_COLON=:",
                  "TEST_BACKSLASH=\\\\",
                  "TEST_DQUOTE=\\\"",
                  "TEST_DQUOTE2=happy days\\\"are\\\"here to stay",
                  "TEST_DQUOTE3=nothing compares\\\" to you",
                  "TEST_DQUOTE4=\\\"music makes the people\\\"",
                  "TEST_DQUOTE5=music \\\"makes \\'the\\'\\\"people",
                  "TEST_DQUOTE6=lalaland\\\"",
                  "TEST_SQUOTE=\\'",
                  "TEST_SQUOTE2=happy\\'days",
                  "TEST_SQUOTE3=the days\\'are here now\\'then",
                  "TEST_SQUOTE4=\\'the way that was\\'",
                  "TEST_SQUOTE5=music \\'makes \\\"the\\'\\\"people",
                  "TEST_SQUOTE6=loving\\'",
                  "TEST_SPECIAL={}[]()~@#$%^&*!",
                  "TEST_SPECIAL2=<dumb-test_text>"]

        if (daemon == "mom"):
            self.logger.info("Matching in mom logs")
        elif (daemon == "server"):
            self.logger.info("Matching in server logs")
        else:
            self.logger.info("Provide a valid daemon name; server or mom")
            return

        for msg in logmsg:
            if (daemon == "mom"):
                # Match the trailing separator (',')
                self.mom.log_match(msg + ',', max_attempts=3)
            elif (daemon == "server"):
                self.server.log_match(msg, starttime=self.server.ctime)

        # Following lines are commented due to PTL bug PP-1008
        # if (daemon == "mom"):
        #    rv = self.mom.log_match(
        #          msg="TEST_RETURN\=\\\'3\\\,\n4\\\,\n5\\\'", regexp=True)
        #    self.assertTrue(rv)
        # else:
        #    rv = self.server.log_match(
        #            msg="TEST_RETURN\=\\\'3\\\,\n4\\\,\n5\\\'", regexp=True)
        #    self.assertTrue(rv)

    def common_validate(self):
        """
        This is a common function to validate the
        environment values with and without hook
        """

        self.assertEqual(self.env_nohook, self.env_hook)
        self.logger.info("Environment variables are same"
                         " with and without hooks")
        match_str = self.env_hook['TEST_COMMA'].rstrip('\n')
        self.assertEqual(os.environ['TEST_COMMA'], match_str)
        self.logger.info(
            "TEST_COMMA matched - " + os.environ['TEST_COMMA'] +
            " == " + match_str)
        self.assertEqual(os.environ['TEST_RETURN'],
                         self.env_hook['TEST_RETURN'].rstrip('\n'))
        self.logger.info(
            "TEST_RETURN matched - " + os.environ['TEST_RETURN'] +
            " == " + self.env_hook['TEST_RETURN'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SEMICOLON'],
                         self.env_hook['TEST_SEMICOLON'].rstrip('\n'))
        self.logger.info(
            "TEST_SEMICOLON matched - " + os.environ['TEST_SEMICOLON'] +
            " == " + self.env_hook['TEST_SEMICOLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_ENCLOSED'],
            self.env_hook['TEST_ENCLOSED'].rstrip('\n'))
        self.logger.info(
            "TEST_ENCLOSED matched - " + os.environ['TEST_ENCLOSED'] +
            " == " + self.env_hook['TEST_ENCLOSED'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_COLON'],
                         self.env_hook['TEST_COLON'].rstrip('\n'))
        self.logger.info("TEST_COLON matched - " + os.environ['TEST_COLON'] +
                         " == " + self.env_hook['TEST_COLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_BACKSLASH'],
            self.env_hook['TEST_BACKSLASH'].rstrip('\n'))
        self.logger.info(
            "TEST_BACKSLASH matched - " + os.environ['TEST_BACKSLASH'] +
            " == " + self.env_hook['TEST_BACKSLASH'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE'],
                         self.env_hook['TEST_DQUOTE'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE matched - " +
                         os.environ['TEST_DQUOTE'] +
                         " == " + self.env_hook['TEST_DQUOTE'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE2'],
                         self.env_hook['TEST_DQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE2 matched - " +
                         os.environ['TEST_DQUOTE2'] +
                         " == " + self.env_hook['TEST_DQUOTE2'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE3'],
                         self.env_hook['TEST_DQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE3 matched - " +
                         os.environ['TEST_DQUOTE3'] +
                         " == " + self.env_hook['TEST_DQUOTE3'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE4'],
                         self.env_hook['TEST_DQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE4 matched - " +
                         os.environ['TEST_DQUOTE4'] +
                         " == " + self.env_hook['TEST_DQUOTE4'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE5'],
                         self.env_hook['TEST_DQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE5 matched - " +
                         os.environ['TEST_DQUOTE5'] +
                         " == " + self.env_hook['TEST_DQUOTE5'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE6'],
                         self.env_hook['TEST_DQUOTE6'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE6 matched - " +
                         os.environ['TEST_DQUOTE6'] +
                         " == " + self.env_hook['TEST_DQUOTE6'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE'],
                         self.env_hook['TEST_SQUOTE'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE matched - " + os.environ['TEST_SQUOTE'] +
                         " == " + self.env_hook['TEST_SQUOTE'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE2'],
                         self.env_hook['TEST_SQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE2 matched - " +
                         os.environ['TEST_SQUOTE2'] +
                         " == " + self.env_hook['TEST_SQUOTE2'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE3'],
                         self.env_hook['TEST_SQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE3 matched - " +
                         os.environ['TEST_SQUOTE3'] +
                         " == " + self.env_hook['TEST_SQUOTE3'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE4'],
                         self.env_hook['TEST_SQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE4 matched - " +
                         os.environ['TEST_SQUOTE4'] +
                         " == " + self.env_hook['TEST_SQUOTE4'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE5'],
                         self.env_hook['TEST_SQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE5 matched - " +
                         os.environ['TEST_SQUOTE5'] +
                         " == " + self.env_hook['TEST_SQUOTE5'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE6'],
                         self.env_hook['TEST_SQUOTE6'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE6 matched - " +
                         os.environ['TEST_SQUOTE6'] +
                         " == " + self.env_hook['TEST_SQUOTE6'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SPECIAL'],
                         self.env_hook['TEST_SPECIAL'].rstrip('\n'))
        self.logger.info("TEST_SPECIAL matched - " +
                         os.environ['TEST_SPECIAL'] +
                         " == " + self.env_hook['TEST_SPECIAL'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SPECIAL2'],
                         self.env_hook['TEST_SPECIAL2'].rstrip('\n'))
        self.logger.info("TEST_SPECIAL2 matched - " +
                         os.environ['TEST_SPECIAL2'] +
                         " == " + self.env_hook['TEST_SPECIAL2'].rstrip('\n'))

    def create_and_submit_job(self, user=None, attribs=None, content=None,
                              content_interactive=None, preserve_env=False):
        """
        create the job object and submit it to the server
        as 'user', attributes list 'attribs' script
        'content' or 'content_interactive', and to
        'preserve_env' if interactive job.
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

    def test_begin_launch(self):
        """
        Test to verify that job environment variables having special
        characters are not truncated with execjob_launch and
        execjob_begin hook
        """

        self.exclude_env += ['HAPPY']
        self.exclude_env += ['happy']

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10,
             self.ATTR_V: None}
        script = ['env\n']
        script += ['sleep 5\n']

        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # Read the env variables from job output
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(job_outfile, "nohook")

        # Now start introducing hooks
        hook_body = """
import pbs
e=pbs.event()
e.job.Variable_List["happy"] = "days"
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

        hook_body = """
import pbs
e=pbs.event()
e.env["HAPPY"] = "nights"
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
        jid2 = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid2)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid2, offset=10)

        self.env_hook = {}
        self.env_hook_exclude = {}
        self.read_env(job_outfile, "hook")

        # Validate the values printed in job output file
        self.assertTrue('HAPPY' not in self.env_nohook_exclude)
        self.assertTrue('happy' not in self.env_nohook_exclude)
        self.assertEqual(self.env_hook_exclude['HAPPY'], 'nights\n')
        self.assertEqual(self.env_hook_exclude['happy'], 'days\n')
        self.common_validate()

        # Check the values in mom logs as well
        self.common_log_match("mom")

    def test_que(self):
        """
        Test that variable_list do not change with and without
        queuejob hook
        """
        self.exclude_env += ['happy']

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}

        script = ['#PBS -V']
        script += ['env\n']
        script += ['sleep 5\n']

        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # Read the env variable from job output file
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(job_outfile, "nohook")

        # Now start introducing hooks
        hook_body = """
import pbs
e=pbs.event()
e.job.Variable_List["happy"] = "days"
pbs.logmsg(pbs.LOG_DEBUG,"Variable List is %s" % (e.job.Variable_List,))
"""
        hook_name = "qjob"
        a2 = {'event': "queuejob", 'enabled': 'True', 'debug': 'True'}

        rv = self.server.create_import_hook(
            hook_name,
            a2,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        # Submit a job with hooks in the system
        jid2 = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid2)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid2, offset=10)

        self.env_hook = {}
        self.env_hook_exclude = {}
        self.read_env(job_outfile, "hook")

        # Validate the env values from job output file
        # with and without queuejob hook
        self.assertTrue('happy' not in self.env_nohook_exclude)
        self.assertEqual(self.env_hook_exclude['happy'], 'days\n')
        self.common_validate()

        # Validate the output in server_log
        # Following is blocked on PTL bug PP-1008
        # self.common_log_match("server")

    def test_execjob_epi(self):
        """
        Test that Variable_List will contain environment variable
        with commas, newline and all special characters even for
        other mom hooks
        """
        self.exclude_env += ['happy']

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}
        script = ['#PBS -V']
        script += ['env\n']
        script += ['sleep 5\n']

        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # Read the output file and parse the values
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(job_outfile, "nohook")

        # Now start the hooks
        hook_name = "test_epi"
        hook_body = """
import pbs
e = pbs.event()
j = e.job
j.Variable_List["happy"] = "days"
pbs.logmsg(pbs.LOG_DEBUG,"Variable_List is %s" % (j.Variable_List,))
"""

        a2 = {'event': "execjob_epilogue", 'enabled': "true", 'debug': "true"}

        self.server.create_import_hook(
            hook_name,
            a2,
            hook_body,
            overwrite=True)

        # Submit a job with hooks in the system
        jid2 = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid2)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid2, offset=10)

        # read the output file for env with hooks
        self.env_hook = {}
        self.env_hook_exclude = {}
        self.read_env(job_outfile, "hook")

        # Validate
        self.common_validate()

        # Verify the env variables in logs too
        self.common_log_match("mom")

    def test_execjob_pro(self):
        """
        Test that environment variable not gets truncated
        for execjob_prologue hook
        """

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}
        script = ['#PBS -V']
        script += ['env\n']
        script += ['sleep 5\n']

        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # read the output file for env without hook
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(job_outfile, "nohook")

        # Now start the hooks
        hook_name = "test_pro"
        hook_body = """
import pbs
e = pbs.event()
j = e.job
j.Variable_List["happy"] = "days"
pbs.logmsg(pbs.LOG_DEBUG,"Variable_List is %s" % (j.Variable_List,))
"""
        a2 = {'event': "execjob_prologue", 'enabled': "true", 'debug': "true"}

        rv = self.server.create_import_hook(
            hook_name,
            a2,
            hook_body,
            overwrite=True)
        self.assertTrue(rv)

        # Submit a job with hooks in the system
        jid2 = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, ATTR_o, id=jid2)
        job_outfile = qstat[0][ATTR_o].split(':')[1]
        self.server.expect(JOB, 'queue', op=UNSET, id=jid2, offset=10)

        # Read the job ouput file
        self.env_hook = {}
        self.env_hook_exclude = {}
        self.read_env(job_outfile, "hook")

        # Validate the env values with and without hook
        self.common_validate()

        # compare the values in mom_logs as well
        self.common_log_match("mom")

    @checkModule("pexpect")
    def test_interactive(self):
        """
        Test that interactive jobs do not have truncated environment
        variable list with execjob_launch hook
        """

        self.exclude_env += ['happy']

        # submit an interactive job without hook
        cmd = 'env > ' + self.job_out1_tempfile
        a = {ATTR_inter: '', self.ATTR_V: None}

        interactive_script = [('hostname', '.*'), (cmd, '.*')]
        jid = self.create_and_submit_job(
            attribs=a,
            content_interactive=interactive_script,
            preserve_env=True)
        # Once all commands sent and matched, job exits
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # read the environment list from the job without hook
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(self.job_out1_tempfile, "nohook")

        # now do the same with the hook
        hook_name = "launch"
        hook_body = """
import pbs
e = pbs.event()
j = e.job
j.Variable_List["happy"] = "days"
pbs.logmsg(pbs.LOG_DEBUG, "Variable_List is %s" % (j.Variable_List,))
"""

        a2 = {'event': "execjob_launch", 'enabled': 'true', 'debug': 'true'}
        self.server.create_import_hook(hook_name, a2, hook_body)

        # submit an interactive job without hook
        cmd = 'env > ' + self.job_out2_tempfile
        interactive_script = [('hostname', '.*'), (cmd, '.*')]
        jid2 = self.create_and_submit_job(
            attribs=a,
            content_interactive=interactive_script,
            preserve_env=True)
        # Once all commands sent and matched, job exits
        self.server.expect(JOB, 'queue', op=UNSET, id=jid2, offset=10)

        # read the environment list from the job without hook
        self.env_hook = {}
        self.env_hook_exclude = {}
        self.read_env(self.job_out2_tempfile, "hook")

        # validate the environment values
        self.common_validate()

        # verify the env values in logs
        self.common_log_match("mom")

    def test_no_hook(self):
        """
        Test to verify that environment variables are
        not truncated and also not modified by PBS when
        no hook is present
        """

        os.environ['BROL'] = 'hii\\\haha'
        os.environ['BROL1'] = """'hii
haa'"""

        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 10}
        script = ['#PBS -V']
        script += ['env\n']
        script += ['sleep 5\n']

        # Submit a job without hooks in the system
        jid = self.create_and_submit_job(attribs=a, content=script)
        qstat = self.server.status(JOB, id=jid)
        job_outfile = qstat[0]['Output_Path'].split(':')[1]
        job_var = qstat[0]['Variable_List']
        self.logger.info("job variable list is %s" % job_var)
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # Read the env variable from job output file
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(job_outfile, "nohook")

        # Verify the output with and without job
        self.assertEqual(os.environ['TEST_COMMA'],
                         self.env_nohook['TEST_COMMA'].rstrip('\n'))
        self.logger.info(
            "TEST_COMMA matched - " + os.environ['TEST_COMMA'] +
            " == " + self.env_nohook['TEST_COMMA'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_RETURN'],
                         self.env_nohook['TEST_RETURN'].rstrip('\n'))
        self.logger.info(
            "TEST_RETURN matched - " + os.environ['TEST_RETURN'] +
            " == " + self.env_nohook['TEST_RETURN'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SEMICOLON'],
                         self.env_nohook['TEST_SEMICOLON'].rstrip('\n'))
        self.logger.info(
            "TEST_SEMICOLON macthed - " + os.environ['TEST_SEMICOLON'] +
            " == " + self.env_nohook['TEST_SEMICOLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_ENCLOSED'],
            self.env_nohook['TEST_ENCLOSED'].rstrip('\n'))
        self.logger.info(
            "TEST_ENCLOSED matched - " + os.environ['TEST_ENCLOSED'] +
            " == " + self.env_nohook['TEST_ENCLOSED'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_COLON'],
                         self.env_nohook['TEST_COLON'].rstrip('\n'))
        self.logger.info("TEST_COLON macthed - " + os.environ['TEST_COLON'] +
                         " == " + self.env_nohook['TEST_COLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_BACKSLASH'],
            self.env_nohook['TEST_BACKSLASH'].rstrip('\n'))
        self.logger.info(
            "TEST_BACKSLASH matched - " + os.environ['TEST_BACKSLASH'] +
            " == " + self.env_nohook['TEST_BACKSLASH'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE'],
                         self.env_nohook['TEST_DQUOTE'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE - " + os.environ['TEST_DQUOTE'] +
                         " == " + self.env_nohook['TEST_DQUOTE'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE2'],
                         self.env_nohook['TEST_DQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE2 - " + os.environ['TEST_DQUOTE2'] +
                         " == " + self.env_nohook['TEST_DQUOTE2'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE3'],
                         self.env_nohook['TEST_DQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE3 - " + os.environ['TEST_DQUOTE3'] +
                         " == " + self.env_nohook['TEST_DQUOTE3'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE4'],
                         self.env_nohook['TEST_DQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE4 - " + os.environ['TEST_DQUOTE4'] +
                         " == " + self.env_nohook['TEST_DQUOTE4'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE5'],
                         self.env_nohook['TEST_DQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE5 - " + os.environ['TEST_DQUOTE5'] +
                         " == " + self.env_nohook['TEST_DQUOTE5'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE6'],
                         self.env_nohook['TEST_DQUOTE6'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE6 - " + os.environ['TEST_DQUOTE6'] +
                         " == " + self.env_nohook['TEST_DQUOTE6'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE'],
                         self.env_nohook['TEST_SQUOTE'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE - " + os.environ['TEST_SQUOTE'] +
                         " == " + self.env_nohook['TEST_SQUOTE'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE2'],
                         self.env_nohook['TEST_SQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE2 - " + os.environ['TEST_SQUOTE2'] +
                         " == " + self.env_nohook['TEST_SQUOTE2'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE3'],
                         self.env_nohook['TEST_SQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE3 - " + os.environ['TEST_SQUOTE3'] +
                         " == " + self.env_nohook['TEST_SQUOTE3'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE4'],
                         self.env_nohook['TEST_SQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE4 - " + os.environ['TEST_SQUOTE4'] +
                         " == " + self.env_nohook['TEST_SQUOTE4'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE5'],
                         self.env_nohook['TEST_SQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE5 - " + os.environ['TEST_SQUOTE5'] +
                         " == " + self.env_nohook['TEST_SQUOTE5'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SQUOTE6'],
                         self.env_nohook['TEST_SQUOTE6'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE6 - " + os.environ['TEST_SQUOTE6'] +
                         " == " + self.env_nohook['TEST_SQUOTE6'].rstrip('\n'))
        self.assertEqual(os.environ['BROL'],
                         self.env_nohook['BROL'].rstrip('\n'))
        self.logger.info("BROL - " + os.environ['BROL'] + " == " +
                         self.env_nohook['BROL'].rstrip('\n'))
        self.assertEqual(os.environ['BROL1'],
                         self.env_nohook['BROL1'].rstrip('\n'))
        self.logger.info("BROL - " + os.environ['BROL1'] + " == " +
                         self.env_nohook['BROL1'].rstrip('\n'))

        # match the values in qstat -f Variable_List
        # Following is blocked on PTL bug PP-1008
        # self.assertTrue("TEST_COMMA=1\,2\,3\,4" in job_var)
        # self.assertTrue("TEST_SEMICOLON=\;" in job_var)
        # self.assertTrue("TEST_COLON=:" in job_var)
        # self.assertTrue("TEST_DQUOTE=\"" in job_var)
        # self.assertTrue("TEST_SQUOTE=\'" in job_var)
        # self.assertTrue("TEST_BACKSLASH=\\" in job_var)
        # self.assertTrue("BROL=hii\\\\\\haha" in job_var)
        # self.assertTrue("TEST_ENCLOSED=\," in job_var)
        # self.assertTrue("BROL1=hii\nhaa" in job_var)
        # self.assertTrue("TEST_RETURN=3\,\n4\,\n5\," in job_var)

    @checkModule("pexpect")
    def test_interactive_no_hook(self):
        """
        Test to verify that environment variable values
        are not truncated or escaped wrongly whithin a
        job even when there is no hook present
        """

        os.environ['BROL'] = 'hii\\\haha'
        os.environ['BROL1'] = """'hii
haa'"""

        # submit an interactive job without hook
        cmd = 'env > ' + self.job_out3_tempfile
        a = {ATTR_inter: '', self.ATTR_V: None}
        interactive_script = [('hostname', '.*'), (cmd, '.*')]
        jid = self.create_and_submit_job(
            attribs=a,
            content_interactive=interactive_script,
            preserve_env=True)
        # Once all commands sent and matched, job exits
        self.server.expect(JOB, 'queue', op=UNSET, id=jid, offset=10)

        # read the environment list from the job without hook
        self.env_nohook = {}
        self.env_nohook_exclude = {}
        self.read_env(self.job_out3_tempfile, "nohook")

        # Verify the output with and without job
        self.logger.info("job Variable list is ")
        self.assertEqual(os.environ['TEST_COMMA'],
                         self.env_nohook['TEST_COMMA'].rstrip('\n'))
        self.logger.info(
            "TEST_COMMA matched - " + os.environ['TEST_COMMA'] +
            " == " + self.env_nohook['TEST_COMMA'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_RETURN'],
                         self.env_nohook['TEST_RETURN'].rstrip('\n'))
        self.logger.info(
            "TEST_RETURN matched - " + os.environ['TEST_RETURN'] +
            " == " + self.env_nohook['TEST_RETURN'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_SEMICOLON'],
                         self.env_nohook['TEST_SEMICOLON'].rstrip('\n'))
        self.logger.info(
            "TEST_SEMICOLON macthed - " + os.environ['TEST_SEMICOLON'] +
            " == " + self.env_nohook['TEST_SEMICOLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_ENCLOSED'],
            self.env_nohook['TEST_ENCLOSED'].rstrip('\n'))
        self.logger.info(
            "TEST_ENCLOSED matched - " + os.environ['TEST_ENCLOSED'] +
            " == " + self.env_nohook['TEST_ENCLOSED'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_COLON'],
                         self.env_nohook['TEST_COLON'].rstrip('\n'))
        self.logger.info("TEST_COLON macthed - " + os.environ['TEST_COLON'] +
                         " == " + self.env_nohook['TEST_COLON'].rstrip('\n'))
        self.assertEqual(
            os.environ['TEST_BACKSLASH'],
            self.env_nohook['TEST_BACKSLASH'].rstrip('\n'))
        self.logger.info(
            "TEST_BACKSLASH matched - " + os.environ['TEST_BACKSLASH'] +
            " == " + self.env_nohook['TEST_BACKSLASH'].rstrip('\n'))
        self.assertEqual(os.environ['TEST_DQUOTE'],
                         self.env_nohook['TEST_DQUOTE'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE - " + os.environ['TEST_DQUOTE'] +
                         " == " + self.env_nohook['TEST_DQUOTE'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE2 - " + os.environ['TEST_DQUOTE2'] +
                         " == " + self.env_nohook['TEST_DQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE3 - " + os.environ['TEST_DQUOTE3'] +
                         " == " + self.env_nohook['TEST_DQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE4 - " + os.environ['TEST_DQUOTE4'] +
                         " == " + self.env_nohook['TEST_DQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE5 - " + os.environ['TEST_DQUOTE5'] +
                         " == " + self.env_nohook['TEST_DQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_DQUOTE6 - " + os.environ['TEST_DQUOTE6'] +
                         " == " + self.env_nohook['TEST_DQUOTE6'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE - " + os.environ['TEST_SQUOTE'] +
                         " == " + self.env_nohook['TEST_SQUOTE'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE2 - " + os.environ['TEST_SQUOTE2'] +
                         " == " + self.env_nohook['TEST_SQUOTE2'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE3 - " + os.environ['TEST_SQUOTE3'] +
                         " == " + self.env_nohook['TEST_SQUOTE3'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE4 - " + os.environ['TEST_SQUOTE4'] +
                         " == " + self.env_nohook['TEST_SQUOTE4'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE5 - " + os.environ['TEST_SQUOTE5'] +
                         " == " + self.env_nohook['TEST_SQUOTE5'].rstrip('\n'))
        self.logger.info("TEST_SQUOTE6 - " + os.environ['TEST_SQUOTE6'] +
                         " == " + self.env_nohook['TEST_SQUOTE6'].rstrip('\n'))
        self.assertEqual(os.environ['BROL'],
                         self.env_nohook['BROL'].rstrip('\n'))
        self.logger.info("BROL - " + os.environ['BROL'] + " == " +
                         self.env_nohook['BROL'].rstrip('\n'))
        self.assertEqual(os.environ['BROL1'],
                         self.env_nohook['BROL1'].rstrip('\n'))
        self.logger.info("BROL - " + os.environ['BROL1'] + " == " +
                         self.env_nohook['BROL1'].rstrip('\n'))

    def test_execjob_epi2(self):
        """
        Test that Variable_List will contain environment variable
        with commas, newline and all special characters for a job
        that has been recovered from a prematurely killed mom. This
        is a test from an execjob_epilogue hook's view.
        PRE: Set up currently executing user's environment to have variables
             whose values have the special characters.
             Submit a job using the -V option (pass current environment)
             where there is an execjob_epilogue hook that references
             Variable_List value.
             Now kill -9 pbs_mom and then restart it.
             This causes pbs_mom to read in job data from the *.JB file on
             disk, and pbs_mom immediately kills the job causing
             execjob_epilogue hook to execute.
        POST: The epilogue hook should see the proper value to the
              Variable_List.
        """
        a = {'Resource_List.select': '1:ncpus=1',
             'Resource_List.walltime': 60}
        j = Job(attrs=a)
        script = ['#PBS -V']
        script += ['env\n']
        script += ['sleep 30\n']
        j.create_script(body=script)

        # Now create/start the hook
        hook_name = "test_epi"
        hook_body = """
import pbs
import time
e = pbs.event()
j = e.job
pbs.logmsg(pbs.LOG_DEBUG,"Variable_List is %s" % (j.Variable_List,))
pbs.logmsg(pbs.LOG_DEBUG,
    "PBS_O_LOGNAME is %s" % j.Variable_List["PBS_O_LOGNAME"])
"""

        a = {'event': "execjob_epilogue", 'enabled': "true", 'debug': "true"}

        self.server.create_import_hook(
            hook_name,
            a,
            hook_body,
            overwrite=True)

        # Submit a job with hooks in the system
        jid = self.server.submit(j)

        # Wait for the job to start running.
        self.server.expect(JOB, {ATTR_state: 'R'}, id=jid)

        # kill -9 mom
        self.mom.signal('-KILL')

        # now restart mom
        self.mom.start()

        self.mom.log_match("Restart sent to server", max_attempts=5)

        # Verify the env variables are seen in logs
        self.common_log_match("mom")
        self.mom.log_match(
            "PBS_O_LOGNAME is %s" % (self.du.get_current_user()))
