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

from tests.functional import *
from ptl.lib.pbs_ifl_mock import *


class TestServerDynRes(TestFunctional):

    def setUp(self):
        TestFunctional.setUp(self)
        # Setup node
        a = {'resources_available.ncpus': 4}
        self.server.manager(MGR_CMD_SET, NODE, a,
                            id=self.mom.shortname, expect=True)

    def setup_dyn_res(self, resname, restype, resval, resflag=None):
        """
        Helper function to setup server dynamic resources
        """
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'False'})

        for i in resname:
            if resflag:
                attr = {"type": restype[0], "flag": resflag[0]}
            else:
                attr = {"type": restype[0]}
            self.server.manager(MGR_CMD_CREATE, RSC, attr, id=i, expect=True)
            # Add resource to sched_config's 'resources' line
            self.scheduler.add_resource(i)

        # Add server_dyn_res entry in sched_config
        if len(resval) > 1:  # Mutliple resources
            # To create multiple server dynamic resources in sched_config
            # from PTL, a list containing "resource !<script>" should be
            # supplied as value to the key 'server_dyn_res' when calling
            # set_sched_config().
            # But this workaround works only if sched_config already has a
            # server_dyn_res entry.
            # HACK: So adding a single resource first and then the list.
            # There wouldn't be any duplicate entries though.
            a = {'server_dyn_res': resval[0]}
            self.scheduler.set_sched_config(a)
            a = {'server_dyn_res': resval}
        else:
            a = {'server_dyn_res': resval[0]}

        self.scheduler.set_sched_config(a)

        # The server dynamic resource script gets executed for every
        # scheduling cycle
        self.server.manager(MGR_CMD_SET, SERVER, {'scheduling': 'True'})

    def test_invalid_script_out(self):
        """
        Test that the scheduler handles incorrect output from server_dyn_res
        script correctly
        """
        # Create a server_dyn_res of type long
        resname = ["mybadres"]
        restype = ["long"]
        script_body = "echo abc"
        (fd, fn) = self.du.mkstemp(prefix="PtlPbs_badoutfile",
                                   body=script_body)

        self.du.chmod(path=fn, mode=0755, sudo=True)
        os.close(fd)
        resval = ['"' + resname[0] + ' ' + '!' + fn + '"']

        # Add it as a server_dyn_res that returns a string output
        self.setup_dyn_res(resname, restype, resval)

        # Submit a job
        j = Job(TEST_USER)
        jid = self.server.submit(j)

        # Make sure that "Problem with creating server data structure"
        # is not logged in sched_logs
        self.scheduler.log_match("Problem with creating server data structure",
                                 existence=False, max_attempts=10)

        # Also check that "Script %s returned bad output"
        # is logged
        self.scheduler.log_match("%s returned bad output" % (fn))

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
            % (resname[0]))

    def test_res_long_pos(self):
        """
        Test that server_dyn_res accepts command line arguments to the
        commands it runs. Resource value set to a positive long int.
        """
        # Create a resource of type long. positive value
        resname = ["foobar"]
        restype = ["long"]
        resval = ['"' + resname[0] + ' ' + '!/bin/echo 4' + '"']

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
        resval = ['"' + resname[0] + ' ' + '!/bin/echo -1' + '"']

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

        # Prep for server_dyn_resource scripts. Script "PbsPtl_get_foo*"
        # generates file "PbsPtl_got_foo" and returns 1.
        script_body = "echo get_foo > /tmp/PtlPbs_got_foo; echo 1"

        fpath_out = os.path.join(os.sep, "tmp", "PtlPbs_got_foo")

        (fd_in, fn_in) = self.du.mkstemp(prefix="PtlPbs_get_foo",
                                         body=script_body)
        self.du.chmod(path=fn_in, mode=0755, sudo=True)
        os.close(fd_in)

        # Add additional white space between resource name and the script
        resval = ['"' + resname[0] + '  ' + ' !' + fn_in + '"']

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

    def test_multiple_res(self):
        """
        Test multiple dynamic resources specified in resourcedef
        and sched_config
        """
        # Create resources of type long
        resname = ["foobar_small", "foobar_medium", "foobar_large"]
        restype = ["long", "long", "long"]

        # Prep for server_dyn_resource scripts.
        script_body_s = "echo 8"
        script_body_m = "echo 12"
        script_body_l = "echo 20"

        (fd_s, fn_s) = self.du.mkstemp(prefix="PtlPbs_small", suffix=".scr",
                                       body=script_body_s)
        (fd_m, fn_m) = self.du.mkstemp(prefix="PtlPbs_medium", suffix=".scr",
                                       body=script_body_m)
        (fd_l, fn_l) = self.du.mkstemp(prefix="PtlPbs_large", suffix=".scr",
                                       body=script_body_l)

        self.du.chmod(path=fn_s, mode=0755, sudo=True)
        self.du.chmod(path=fn_m, mode=0755, sudo=True)
        self.du.chmod(path=fn_l, mode=0755, sudo=True)

        # Close file handles, else scheduler cannot execute them
        os.close(fd_s)
        os.close(fd_m)
        os.close(fd_l)

        resval = ['"' + resname[0] + ' ' + '!' + fn_s + '"',
                  '"' + resname[1] + ' ' + '!' + fn_m + '"',
                  '"' + resname[2] + ' ' + '!' + fn_l + '"']

        self.setup_dyn_res(resname, restype, resval)

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
        script_body = "echo abc"

        (fd, fn) = self.du.mkstemp(prefix="PtlPbs_check", suffix=".scr",
                                   body=script_body)
        self.du.chmod(path=fn, mode=0755, sudo=True)
        os.close(fd)

        resval = ['"' + resname[0] + ' ' + '!' + fn + '"']

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
        script_body = "echo white, red, blue"

        (fd, fn) = self.du.mkstemp(prefix="PtlPbs_color", suffix=".scr",
                                   body=script_body)
        self.du.chmod(path=fn, mode=0755, sudo=True)
        os.close(fd)

        resval = ['"' + resname[0] + ' ' + '!' + fn + '"']

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
        resflag = ["q"]

        # Prep for server_dyn_resource script
        script_body = "echo 100gb"

        (fd, fn) = self.du.mkstemp(prefix="PtlPbs_size", suffix=".scr",
                                   body=script_body)
        self.du.chmod(path=fn, mode=0755, sudo=True)
        os.close(fd)

        resval = ['"' + resname[0] + ' ' + '!' + fn + '"']

        self.setup_dyn_res(resname, restype, resval, resflag)

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
        resflag = ["q"]

        # Prep for server_dyn_resource script
        script_body = "echo 100gb"

        (fd, fn) = self.du.mkstemp(prefix="PtlPbs_size", suffix=".scr",
                                   body=script_body)
        self.du.chmod(path=fn, mode=0755, sudo=True)
        os.close(fd)

        resval = ['"' + resname[0] + ' ' + '!' + fn + '"']

        self.setup_dyn_res(resname, restype, resval, resflag)

        # Submit job
        a = {'Resource_List.foobar': '95gb'}
        j = Job(TEST_USER, attrs=a)
        jid = self.server.submit(j)

        # Job must run successfully
        a = {'job_state': 'R', 'Resource_List.foobar': '95gb'}
        self.server.expect(JOB, a, id=jid)

        # Change script during job run
        with open(fn, "rw+") as fd:
            fd.truncate()
            fd.write("echo 50gb")

        # Rerun job
        self.server.rerunjob(jid)

        # The job shouldn't run
        job_comment = "Can Never Run: Insufficient amount of server resource:"
        job_comment += " foobar (R: 95gb A: 50gb T: 50gb)"
        a = {'job_state': 'Q', 'comment': job_comment}
        self.server.expect(JOB, a, id=jid, attrop=PTL_AND)
