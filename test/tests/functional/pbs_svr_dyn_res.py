# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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
from ptl.lib.pbs_ifl_mock import *


class TestServerDynRes(TestFunctional):

    dirnames = []

    def setUp(self):
        TestFunctional.setUp(self)
        # Setup node
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a, id=self.mom.shortname)

    def check_access_log(self, fp, exist=True):
        """
        Helper function to check if scheduler logged a file security
        message.
        """
        # adding a second delay because log_match can then start from the
        # correct log message and avoid false positives from previous
        # logs
        time.sleep(1)
        match_from = int(time.time())
        self.scheduler.apply_config(validate=False)
        self.scheduler.get_pid()
        self.scheduler.signal('-HUP')
        self.scheduler.log_match(fp + ' file has a non-secure file access',
                                 starttime=match_from, existence=exist,
                                 max_attempts=10)

    def setup_dyn_res(self, resname, restype, script_body):
        """
        Helper function to setup server dynamic resources
        returns a list of dynamic resource scripts created by the function
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})
        val = []
        scripts = []
        attr = {}
        for i, name in enumerate(resname):
            attr["type"] = restype[i]
            self.server.manager(MGR_CMD_CREATE, RSC, attr, id=name)
            # Add resource to sched_config's 'resources' line
            self.scheduler.add_resource(name)
            dest_file = self.scheduler.add_server_dyn_res(name,
                                                          script_body[i],
                                                          prefix="svr_resc",
                                                          suffix=".scr")
            val.append('"' + name + ' ' + '!' + dest_file + '"')
            scripts.append(dest_file)
        a = {'server_dyn_res': val}
        self.scheduler.set_sched_config(a)

        # The server dynamic resource script gets executed for every
        # scheduling cycle
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})
        return scripts

    def test_invalid_script_out(self):
        """
        Test that the scheduler handles incorrect output from server_dyn_res
        script correctly
        """
        # Create a server_dyn_res of type long
        resname = ["mybadres"]
        restype = ["long"]
        script_body = ['echo abc']

        # Add it as a server_dyn_res that returns a string output
        filenames = self.setup_dyn_res(resname, restype, script_body)

        # Submit a job
        j = Job(TEST_USER)
        jid = self.server.submit(j)

        # Make sure that "Problem with creating server data structure"
        # is not logged in sched_logs
        self.scheduler.log_match("Problem with creating server data structure",
                                 existence=False, max_attempts=10)

        # Also check that "<script> returned bad output"
        # is in the logs
        self.scheduler.log_match("%s returned bad output" % filenames[0])

        # The scheduler uses 0 as the available amount of the dynamic resource
        # if the server_dyn_res script output is bad
        # So, submit a job that requests 1 of the resource
        attr = {"Resource_List." + resname[0]: 1}

        # Submit job
        j = Job(TEST_USER, attrs=attr)
        jid = self.server.submit(j)

        # The job shouldn't run
        self.server.expect(JOB, {'job_state': 'Q'}, id=jid)

        # Check for the expected log message for insufficient resources
        self.scheduler.log_match(
            "Insufficient amount of server resource: %s (R: 1 A: 0 T: 0)"
            % (resname[0]), level=logging.DEBUG2)

    def test_res_long_pos(self):
        """
        Test that server_dyn_res accepts command line arguments to the
        commands it runs. Resource value set to a positive long int.
        """
        # Create a resource of type long. positive value
        resname = ["foobar"]
        restype = ["long"]
        resval = ['/bin/echo 4']

        # Add server_dyn_res entry in sched_config
        self.setup_dyn_res(resname, restype, resval)

        a = {'Resource_List.foobar': 4}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': '4'}
        self.server.expect(JOB, a, id=jid)

    def test_res_long_neg(self):
        """
        Test that server_dyn_res accepts command line arguments to the
        commands it runs. Resource value set to a negative long int.
        """
        # Create a resource of type long. negative value
        resname = ["foobar"]
        restype = ["long"]
        resval = ['/bin/echo -1']

        # Add server_dyn_res entry in sched_config
        self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': '1'}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Check for the expected log message for insufficient resources
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (R: 1 A: -1 T: -1)"

        # The job shouldn't run
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_whitespace(self):
        """
        Test for parse errors when more than one white space
        is added between the resource name and the !<script> in a
        server_dyn_res line. There shouldn't be any errors.
        """
        # Create a resource of type long
        resname = ["foo"]
        restype = ["long"]
        resval = ['echo get_foo > /tmp/PtlPbs_got_foo; echo 1']

        # Prep for server_dyn_resource scripts. Script "PbsPtl_get_foo*"
        # generates file "PbsPtl_got_foo" and returns 1.
        fpath_out = os.path.join(os.sep, "tmp", "PtlPbs_got_foo")

        self.setup_dyn_res(resname, restype, resval)

        # Check if the file "PbsPtl_got_foo" was created
        for _ in range(10):
            self.logger.info("Waiting for the file [%s] to appear",
                             fpath_out)
            if self.du.isfile(path=fpath_out):
                break
            time.sleep(1)
        self.assertTrue(self.du.isfile(path=fpath_out))

        # Submit job
        a = {'Resource_List.foo': '1'}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foo': 1}
        self.server.expect(JOB, a, id=jid)
        # Cleanup dynamically created file
        self.du.rm(fpath_out, sudo=True, force=True)

    def test_multiple_res(self):
        """
        Test multiple dynamic resources specified in resourcedef
        and sched_config
        """
        # Create resources of type long
        resname = ["foobar_small", "foobar_medium", "foobar_large"]
        restype = ["long", "long", "long"]

        # Prep for server_dyn_resource scripts.
        script_body = ["echo 8", "echo 12", "echo 20"]

        self.setup_dyn_res(resname, restype, script_body)

        a = {'Resource_List.foobar_small': '4'}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar_small': 4}
        self.server.expect(JOB, a, id=jid)

        a = {'Resource_List.foobar_medium': '10'}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar_medium': 10}
        self.server.expect(JOB, a, id=jid)

        a = {'Resource_List.foobar_large': '18'}
        # Submit job
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar_large': 18}
        self.server.expect(JOB, a, id=jid)

    def test_res_string(self):
        """
        Test that server_dyn_res accepts a string value returned
        by a script
        """
        # Create a resource of type string
        resname = ["foobar"]
        restype = ["string"]

        # Prep for server_dyn_resource script
        resval = ["echo abc"]

        self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': 'abc'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': 'abc'}
        self.server.expect(JOB, a, id=jid)

        # Submit job
        a = {'Resource_List.foobar': 'xyz'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Check for the expected log message for insufficient resources
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (xyz != abc)"

        # The job shouldn't run
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_string_array(self):
        """
        Test that server_dyn_res accepts string array returned
        by a script
        """
        # Create a resource of type string_array
        resname = ["foobar"]
        restype = ["string_array"]

        # Prep for server_dyn_resource script
        resval = ["echo white, red, blue"]

        self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': 'red'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': 'red'}
        self.server.expect(JOB, a, id=jid)

        # Submit job
        a = {'Resource_List.foobar': 'green'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Check for the expected log message for insufficient resources
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (green != white,red,blue)"

        # The job shouldn't run
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_size(self):
        """
        Test that server_dyn_res accepts type "size" and a "value"
        returned by a script
        """
        # Create a resource of type size
        resname = ["foobar"]
        restype = ["size"]

        # Prep for server_dyn_resource script
        resval = ["echo 100gb"]

        self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': '95gb'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': '95gb'}
        self.server.expect(JOB, a, id=jid1)

        # Submit job
        a = {'Resource_List.foobar': '101gb'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)

        # Check for the expected log message for insufficient resources
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (R: 101gb A: 100gb T: 100gb)"

        # The job shouldn't run
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid2, attrop=PTL_AND)

        # Delete jobs
        self.server.deljob(jid1, wait=True, runas=TEST_USER)
        self.server.deljob(jid2, wait=True, runas=TEST_USER)

        # Submit jobs again
        a = {'Resource_List.foobar': '50gb'}
        j1 = Job(TEST_USER, attrs=a)
        jid1 = self.server.submit(j1)

        a = {'Resource_List.foobar': '50gb'}
        j2 = Job(TEST_USER, attrs=a)
        jid2 = self.server.submit(j2)

        # Both jobs must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': '50gb'}
        self.server.expect(JOB, a, id=jid1)
        self.server.expect(JOB, a, id=jid2)

    def test_res_size_runtime(self):
        """
        Test that server_dyn_res accepts type "size" and a "value"
        returned by a script. Check if the script change during
        job run is correctly considered
        """

        # Create a resource of type size
        resname = ["foobar"]
        restype = ["size"]

        # Prep for server_dyn_resource script
        resval = ["echo 100gb"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': '95gb'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': '95gb'}
        self.server.expect(JOB, a, id=jid)

        # Change script during job run
        cmd = ["echo", "\"echo 50gb\"", " > ", filenames[0]]
        self.du.run_cmd(cmd=cmd, runas=ROOT_USER, as_script=True)

        # Rerun job
        self.server.rerunjob(jid)

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (R: 95gb A: 50gb T: 50gb)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_size_invalid_input(self):
        """
        Test invalid values returned from server_dyn_resource
        script for resource type 'size'.
        Script returns a 'string' instead of type 'size'.
        """
        # Create a resource of type size
        resname = ["foobar"]
        restype = ["size"]

        # Script returns invalid value for resource type 'size'
        resval = ["echo two gb"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foobar': '2gb'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Also check that "<script> returned bad output"
        # is in the logs
        self.scheduler.log_match("%s returned bad output" % filenames[0])

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (R: 2gb A: 0kb T: 0kb)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_float_invalid_input(self):
        """
        Test invalid values returned from server_dyn_resource
        script for resource type 'float'
        Script returns 'string' instead of type 'float'.
        """

        # Create a resource of type float
        resname = ["foo"]
        restype = ["float"]

        # Prep for server_dyn_resource script
        resval = ["echo abc"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foo': '1.2'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Also check that "<script> returned bad output"
        # is in the logs
        self.scheduler.log_match("%s returned bad output" % filenames[0])

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foo (R: 1.2 A: 0 T: 0)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_res_boolean_invalid_input(self):
        """
        Test invalid values returned from server_dyn_resource
        script for resource type 'boolean'.
        Script returns 'non boolean' values
        """

        # Create a resource of type boolean
        resname = ["foo"]
        restype = ["boolean"]

        # Prep for server_dyn_resource script
        resval = ["echo yes"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foo': '"true"'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Also check that "<script> returned bad output"
        # is in the logs
        self.scheduler.log_match("%s returned bad output" % filenames[0])

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foo (True != False)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid)

    def test_res_timeout(self):
        """
        Test server_dyn_res script timeouts after 30 seconds
        """

        # Create a resource of type boolean
        resname = ["foo"]
        restype = ["boolean"]

        # Prep for server_dyn_resource script
        resval = ["sleep 60\necho true"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foo': 'true'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        self.logger.info('Sleeping 30 seconds to wait for script to timeout')
        time.sleep(30)
        self.scheduler.log_match("%s timed out" % filenames[0])
        self.scheduler.log_match("Setting resource foo to 0")

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foo (True != False)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid)

    def test_res_set_timeout(self):
        """
        Test setting server_dyn_res script to timeout after 10 seconds
        """

        self.server.manager(MGR_CMD_SET, SCHED,
                            {ATTR_sched_server_dyn_res_alarm: 10})

        # Create a resource of type boolean
        resname = ["foo"]
        restype = ["boolean"]

        # Prep for server_dyn_resource script
        resval = ["sleep 20\necho true"]

        filenames = self.setup_dyn_res(resname, restype, resval)

        # Submit job
        a = {'Resource_List.foo': 'true'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        self.logger.info('Sleeping 10 seconds to wait for script to timeout')
        time.sleep(10)
        self.scheduler.log_match("%s timed out" % filenames[0])
        self.scheduler.log_match("Setting resource foo to 0")

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foo (True != False)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)

    def test_svr_dyn_res_permissions(self):
        """
        Test whether scheduler rejects the server_dyn_res script when the
        permission of the script are open to write for others and group
        """

        # Create a new resource
        attr = {'type': 'long', 'flag': 'q'}
        self.server.manager(MGR_CMD_CREATE, RSC, attr, id='foo')
        self.scheduler.add_resource('foo')

        scr_body = ['echo "10"', 'exit 0']
        home_dir = os.path.expanduser("~")
        fp = self.scheduler.add_server_dyn_res("foo", scr_body,
                                               dirname=home_dir,
                                               validate=False)

        # give write permission to group and others
        self.du.chmod(path=fp, mode=0o766, sudo=True)
        self.check_access_log(fp)

        # give write permission to group
        self.du.chmod(path=fp, mode=0o764, sudo=True)
        self.check_access_log(fp)

        # give write permission to others
        self.du.chmod(path=fp, mode=0o746, sudo=True)
        self.check_access_log(fp)

        # give write permission to user only
        self.du.chmod(path=fp, mode=0o744, sudo=True)
        if os.getuid() != 0:
            self.check_access_log(fp, exist=True)
        else:
            self.check_access_log(fp, exist=False)

        # Create script in a directory which has more open privileges
        # This should make loading of this file fail in all cases
        # Create the dirctory name with a space in it, to make sure PBS parses
        # it correctly.
        dir_temp = self.du.create_temp_dir(mode=0o766, dirname=home_dir,
                                           suffix=' tmp')
        fp = self.scheduler.add_server_dyn_res("foo", scr_body,
                                               dirname=dir_temp,
                                               validate=False)

        # Add to dirnames for cleanup
        self.dirnames.append(dir_temp)

        # give write permission to group and others
        self.du.chmod(path=fp, mode=0o766, sudo=True)
        self.check_access_log(fp)

        # give write permission to group
        self.du.chmod(path=fp, mode=0o764, sudo=True)
        self.check_access_log(fp)

        # give write permission to others
        self.du.chmod(path=fp, mode=0o746, sudo=True)
        self.check_access_log(fp)

        # give write permission to user only
        self.du.chmod(path=fp, mode=0o744, sudo=True)
        self.check_access_log(fp)

        # Create dynamic resource script in PBS_HOME directory and check
        # file permissions
        # self.scheduler.add_mom_dyn_res by default creates the script in
        # PBS_HOME as root
        fp = self.scheduler.add_server_dyn_res("foo", scr_body, perm=0o766,
                                               validate=False)

        self.check_access_log(fp)

        # give write permission to group
        self.du.chmod(path=fp, mode=0o764, sudo=True)
        self.check_access_log(fp)

        # give write permission to others
        self.du.chmod(path=fp, mode=0o746, sudo=True)
        self.check_access_log(fp)

        # give write permission to user only
        self.du.chmod(path=fp, mode=0o744, sudo=True)
        self.check_access_log(fp, exist=False)

    def tearDown(self):
        # removing all files creating in test
        if len(self.dirnames) != 0:
            self.du.rm(path=self.dirnames, sudo=True, force=True,
                       recursive=True)
            self.dirnames[:] = []
        TestFunctional.tearDown(self)
