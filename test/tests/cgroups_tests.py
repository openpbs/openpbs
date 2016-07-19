# coding: utf-8

from ptl.utils.pbs_testsuite import *

import os
import time
addons_dir = "/root/pbspro/test/tests/cgroups"


class CgroupsTests(PBSTestSuite):

    """
    This tests Linux Cgroups functionality.
    Date: July 8, 2016

    """

    __author__ = "Jon Shelley <jshelley@altair.com>"
    hostname = socket.gethostname().split('.')[0]

    def setUp(self):

        PBSTestSuite.setUp(self)
        self.server.set_op_mode(PTL_CLI)
        self.server.expect(SERVER, {'pbs_version': (MATCH_RE, '.*14.*')})
        self.clean_hooks()

        a = {'log_events': '2047'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)

        # Configure the scheduler to schedule using vmem
        a = {'resources': 'ncpus,mem,host,vnode,vmem'}
        self.scheduler.set_sched_config(a)

        # Configure the mom
        self.momA = self.moms.values()[0]
        c = {'$logevent': '0xffffffff','$clienthost': self.server.name,
             '$min_check_poll': 8, '$max_check_poll': 12 }
        self.momA.add_config(c)

        # create resource as root
        u = "root"
        attr = {'type': 'long', 'flag': 'nh'}
        rc = self.server.manager(
                MGR_CMD_CREATE, RSC, attr, id='nmics', runas=u, logerr=False)

        rc = self.server.manager(
                MGR_CMD_CREATE, RSC, attr, id='ngpus', runas=u, logerr=False)

        # setup a user and group
        self.TSTGRP0 = PbsGroup('tstgrp00', gid=1900)
        self.TEST_USER = PbsUser('pbsuser', uid=1002, groups=[TSTGRP0])

        self.hook_init()

    def hook_init(self):
        """ Set up the queuejob hook for testing """

        print os.getcwd()
        self.t1_py = open(addons_dir + os.sep + 'pbs_cgroups.py').read()
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups.json'

        run_once = False
        if not run_once:
            hook_name = "t1_l1"
            hook_type = '"'
            hook_type += "execjob_begin,"
            hook_type += "execjob_launch,"
            hook_type += "execjob_attach,"
            hook_type += "execjob_epilogue,"
            hook_type += "execjob_end,"
            hook_type += "exechost_startup,"
            hook_type += "exechost_periodic"
            hook_type += '"'

            self.logger.info(
                "Test Summary: test_" +
                hook_name +
                " tests " +
                hook_type +
                " cgroup hook"
            )
            a = {'event': hook_type, 'enabled': 'True', 'freq': 2}
            rv = self.server.create_import_hook(
                hook_name,
                a,
                self.t1_py,
                overwrite=True)
            self.assertTrue(rv)

            a = {'content-type': 'application/x-config',
                 'content-encoding': 'default',
                 'input-file': self.t1_cfg}
            self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)

#            rv = self.server.import_hook(
#                hook_name,
#                self.t1_cfg,
#                "x-config")
#            self.assertTrue(rv)
            run_once = True

    def clean_hooks(self):

        hooks_list = [
            "t1_l1"
        ]

        for t in hooks_list:
            if t in self.server.hooks:
                self.server.manager(MGR_CMD_DELETE, HOOK, id=t)

    def test_t1(self):
        """ Test to verify that the job cgroup is created correctly
            Check to see that cpuset.cpus=0, cpuset.mems=0 and that
            memory.limit_in_bytes = 104857600
         """
        hook_name = "t1_l1"
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t1', }
        j = Job(self.TEST_USER, attrs=a)
        j.create_script(script_1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(
            JOB, ['Output_Path', 'Error_Path', 'Keep_Files'],
            jid)

        (o, e) = (j.attributes['Output_Path'], j.attributes['Error_Path'])

        tmp_out = ''
        try:
            self.logger.info(
                "Job .o file: %s" % o
            )
            time.sleep(2)
            tmp_file = o.split(':')[1]
            if os.path.isfile(tmp_file):
                tmp_out = open(tmp_file).read()
                tmp_out = tmp_out.split('\n')
        except:
            self.logger.info(
                "Test Summary: test_" +
                hook_name +
                " Something went wrong in test_t1"
            )
            self.assertTrue(False)
        self.logger.info("test_t1: %s" % tmp_out)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        self.assertTrue("CpuSocket=0" in tmp_out)
        self.logger.info("CpuSocket check passed")
        self.assertTrue("MemorySocket=0" in tmp_out)
        self.logger.info("MemorySocket check passed")
        self.assertTrue("MemoryLimit=314572800" in tmp_out)
        self.logger.info("MemoryLimit check passed")

    def test_t1b(self):
        """ Test to verify that the job cgroup is created correctly
            using the default memory and swap
            Check to see that cpuset.cpus=0, cpuset.mems=0 and that
            memory.limit_in_bytes = 104857600
            memory.memsw.limit_in_bytes = 104857600
         """
        hook_name = "t1_l1"
        a = {'Resource_List.select': '1:ncpus=1',
             'Job_Name': 'test_t1b', }
        j = Job(self.TEST_USER, attrs=a)
        j.create_script(script_1)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(
            JOB, ['Output_Path', 'Error_Path', 'Keep_Files'],
            jid)

        (o, e) = (j.attributes['Output_Path'], j.attributes['Error_Path'])

        tmp_out = ''
        try:
            self.logger.info(
                "Job .o file: %s" % o
            )
            time.sleep(2)
            tmp_file = o.split(':')[1]
            if os.path.isfile(tmp_file):
                tmp_out = open(tmp_file).read()
                tmp_out = tmp_out.split('\n')
        except:
            self.logger.info(
                "Test Summary: test_" +
                hook_name +
                " Something went wrong in test_t1"
            )
            self.assertTrue(False)
        self.logger.info("test_t1: %s" % tmp_out)
        self.assertTrue(jid in tmp_out)
        self.logger.info("job dir check passed")
        self.assertTrue("CpuSocket=0" in tmp_out)
        self.logger.info("CpuSocket check passed")
        self.assertTrue("MemorySocket=0" in tmp_out)
        self.logger.info("MemorySocket check passed")
        self.assertTrue("MemoryLimit=262144000" in tmp_out)
        self.assertTrue("MemswLimit=268435456" in tmp_out)
        self.logger.info("MemoryLimit check passed")

    def test_t1c(self):
        """ Test to verify that the cgroup prefix is set to pbs and that
            only the devices subsystem is enabled with the correct devices
            allowed
         """
        hook_name = "t1_l1"
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups3.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': self.t1_cfg}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)
        self.assertTrue(rv == 0)

        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t2', }
        j = Job(self.TEST_USER, attrs=a)
        j.create_script(script_2)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.server.status(
            JOB, ['Output_Path', 'Error_Path', 'Keep_Files'],
            jid)

        (o, e) = (j.attributes['Output_Path'], j.attributes['Error_Path'])

        tmp_out = ''
        try:
            self.logger.info(
                "Job .o file: %s" % o
            )
            tmp_file = o.split(':')[1]
            icnt = 0
            while not os.path.isfile(tmp_file) and icnt < 5:
                icnt += 1
                time.sleep(1)
            if os.path.isfile(tmp_file):
                tmp_out = open(tmp_file).read()
                tmp_out = tmp_out.split('\n')
                self.logger.info("test_t1b: %s" % tmp_out)
            else:
                self.logger.info("Can't find %s" % tmp_file)
        except:
            self.logger.info(
                "Test Summary: test_" +
                hook_name +
                " Something went wrong in test_t1b"
            )
            self.assertTrue(False)

        check_devices = ['b *:* rwm',
                         'c 5:1 rwm',
                         'c 4:* rwm',
                         'c 1:* rwm',
                         'c 10:* rwm']
        for device in check_devices:
            self.assertTrue(device in tmp_out)
        self.logger.info("device_list check passed")
        self.assertFalse("Disabled cgroup subsystems are populated" in tmp_out)
        self.logger.info("Disabled subsystems check passed")

    def test_t2(self):
        """ Test to verify that the job is killed when it tries to 
            use more memory then it requested
         """
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t2'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*%s;Cgroup mem\w+ limit exceeded.*" % jid,
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t2b(self):
        """ Test to verify that the job is killed when it tries to 
            use more swap then it requested
         """
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb:vmem=320mb',
             'Job_Name': 'test_t2'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        now = int(time.time())
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        self.logger.info("Time: %d" % now)
        self.logger.info("Ctime: %s, type: %s" % (self.server.ctime,self.server.ctime))
        rv = self.mom.log_match(".*%s;update_job_usage: Memory usage: vmem=3208\d{2}kb.*" % jid,
                                regexp=True,
                                max_attempts=3,
                                starttime=now)
#                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t3(self):
        """ Test to verify that the node is offlined when it can't clean up
            the cgroup and brought back online once the cgroup is cleaned up
        """
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Resource_List.walltime': 3, 'Job_Name': 'test_t3'}
        j = Job(self.TEST_USER, attrs=a)
        j.create_script(sleep_5)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        time.sleep(1)
        # Freeze the pids in the cgroup
        cgroups_dirs = ['/cgroup/', '/sys/fs/cgroup/']
        cdir = None
        for dir in cgroups_dirs:
            if os.path.isdir(dir):
                cdir = dir
        tasks = None
        tasks_file = dir + "cpuset/pbspro/%s/tasks" % jid
        if os.path.isfile(tasks_file):
            tasks = open(tasks_file).read()
        self.logger.info("Tasks: %s" % tasks)

        # Make dir in freezer subsystem
        if tasks is not None and os.path.isdir(cdir + "freezer"):
            freeze_dir = dir + "freezer/%s/" % jid
            if not os.path.isdir(freeze_dir):
                os.mkdir(freeze_dir)
        else:
            self.logger.info("No tasks found")
            self.logger.info("unable to file the freezer dir")
            self.assertTrue(False)

        freeze_tasks = freeze_dir + "tasks"
        self.logger.info("Server name: %s" % self.server.name)
        self.logger.info(freeze_tasks)
        self.logger.info("tasks: %s" % tasks)
        tasks = tasks.split()
        for task in tasks[1:]:
            with open(freeze_tasks, "w") as fd:
                fd.write(str(task) + '\n')
        fout1 = open(freeze_dir + "freezer.state", "w")
        fout1.write("FROZEN")
        fout1.close()
        rv1 = self.server.expect(NODE, {'state': (EQ, 'offline')},
                                 id=self.mom.shortname, interval=3)
        fout2 = open(freeze_dir + "freezer.state", "w")
        fout2.write("THAWED")
        fout2.close()
        time.sleep(1)
        os.rmdir(freeze_dir)
        rv2 = self.server.expect(NODE, {'state': (EQ, 'free')},
                                id=self.mom.shortname, interval=3)
        self.assertTrue(rv1)
        self.assertTrue(rv2)
                    
        # rv = self.mom.log_match(".*%s;Cgroup mem\w+ limit exceeded.*" % jid,
        #                        regexp=True,
        #                        max_attempts=5,
        #                        starttime=self.server.ctime)

    def test_t4(self):
        """ Test to verify that cgroups are not enforced on nodes
            that have an exclude vntype file set
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = pbs_home + "/mom_priv/vntype"
        with open(vntype_file, "w") as fd:
            fd.write("no_cgroups")
        
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t4'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*vntype: no_cgroups is in \['no_cgroups'\].*",
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        os.remove(vntype_file)
        self.assertTrue(rv)

    def test_t4b(self):
        """ Test to verify that cgroups are not enforced on nodes
            that have the exclude_hosts set
        """
        tmp_cfg = cfg_json % ('"%s"' % self.mom.shortname, "", "")
        hook_name = "t1_l1"
        tmp_cfg_filename = '/tmp/%s.json' % hook_name
        fout = open(tmp_cfg_filename, "w")
        fout.write(tmp_cfg)
        fout.close()
        self.logger.info("tmp_cfg: %s" % tmp_cfg)
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': tmp_cfg_filename}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)

        # Remove the config file
        os.remove(tmp_cfg_filename)
        
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t4b'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*exclude host %s is in \['%s'\].*" %
                                (self.mom.shortname, self.mom.shortname),
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t4c(self):
        """ Test to verify that cgroups subsystems are not enforced on nodes
            that have the exclude_hosts set
        """
        tmp_cfg = cfg_json % ("", "", '"%s"' % self.mom.shortname)
        hook_name = "t1_l1"
        tmp_cfg_filename = '/tmp/%s.json' % hook_name
        fout = open(tmp_cfg_filename, "w")
        fout.write(tmp_cfg)
        fout.close()
        self.logger.info("tmp_cfg: %s" % tmp_cfg)
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': tmp_cfg_filename}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)

        # Remove the config file
        os.remove(tmp_cfg_filename)
        
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t4c'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*cgroup excluded for subsystem %s on host %s.*" %
                                ("cpuset", self.mom.shortname),
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t4d(self):
        """ Test to verify that the cgroup hook only runs on nodes
            in the run_only_on_hosts
        """
        tmp_cfg = cfg_json % ("", '"SomeNodeOutThere"', "")
        hook_name = "t1_l1"
        tmp_cfg_filename = '/tmp/%s.json' % hook_name
        fout = open(tmp_cfg_filename, "w")
        fout.write(tmp_cfg)
        fout.close()
        self.logger.info("tmp_cfg: %s" % tmp_cfg)
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': tmp_cfg_filename}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)

        # Remove the config file
        os.remove(tmp_cfg_filename)
        
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t4d'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        time.sleep(1)
        rv = self.mom.log_match("%s is not in " % (self.mom.shortname) +
                                "the approved list of hosts: " +
                                "\['SomeNodeOutThere'\]", 
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t5(self):
        """ Test to verify that cgroups are not enforced on nodes
            that have an exclude vntype file set
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = pbs_home + "/mom_priv/vntype"
        with open(vntype_file, "w") as fd:
            fd.write("no_cgroups_mem")
        
        a = {'Resource_List.select': '1:ncpus=1:mem=300mb',
             'Job_Name': 'test_t4'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*cgroup excluded for subsystem memory on " +
                                "vnode type no_cgroups_mem.*",
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        os.remove(vntype_file)
        self.assertTrue(rv)
        rv = self.mom.log_match(".*%s;Cgroup mem\w+ limit exceeded.*" % jid,
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertFalse(rv)

    def test_t6(self):
        """ Test to verify that cgroups are reporting usage for
            cput, mem 
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = pbs_home + "/mom_priv/vntype"
        
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb',
             'Job_Name': 'test_t4'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem2.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        rv = self.mom.log_match(".*%s;update_job_usage: " % jid + 
                                "Memory usage: vmem=3", 
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)
        rv = self.mom.log_match(".*%s;update_job_usage: " % jid,
                                "CPU usage: .*secs",
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)
        time.sleep(5)
        rv = self.mom.log_match(".*%s;update_job_usage: " % jid + 
                                "Memory usage: vmem=4", 
                                regexp=True,
                                max_attempts=5,
                                starttime=self.server.ctime)
        self.assertTrue(rv)

    def test_t6b(self):
        """ Test to verify that cgroups are reporting usage for
            cput, mem, vmem in qstat 
        """
        pbs_home = self.server.pbs_conf['PBS_HOME']
        vntype_file = pbs_home + "/mom_priv/vntype"
        
        a = {'Resource_List.select': '1:ncpus=1:mem=500mb',
             'Job_Name': 'test_t4'}
        j = Job(self.TEST_USER, attrs=a)
        eat_mem = open(addons_dir + os.sep + "eatmem3.py").read()
        j.create_script(eat_mem)
        jid = self.server.submit(j)
        a = {'job_state': 'R'}
        self.server.expect(JOB, a, jid)
        time.sleep(6)
        qstat1 = self.server.status(JOB, 'resources_used.vmem', id=jid)
        mem1 = qstat1[0]['resources_used.vmem']
        
        time.sleep(7)

        qstat2 = self.server.status(JOB, 'resources_used.vmem', id=jid)
        mem2 = qstat2[0]['resources_used.vmem']
        for q in qstat2:
            self.logger.info("Q: %s" % q)
           
        self.logger.info("Mem-1: %s" % mem1)
        self.logger.info("Mem-2: %s" % mem2)
        mem1 = PbsTypeSize(mem1)
        mem2 = PbsTypeSize(mem2)
        self.logger.info("Mem-1: %s" % mem1)
        self.logger.info("Mem-2: %s" % mem2)

    def test_t7(self):
        """ Test to verify that the mom reserve memory for OS
            when there is a reserve mem request in the config
         """
        hook_name = "t1_l1"
        self.t1_cfg = addons_dir + os.sep + 'pbs_cgroups.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': self.t1_cfg}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)
        self.assertTrue(rv == 0)

        self.momA.stop()
        self.momA.start()

        time.sleep(1)

        # cache the node properties as queried from the Server
        self.server.status(NODE)
        self.momA = self.moms.values()[0]
        swap = self.server.status(NODE, 'resources_available.vmem')
        swap1 = PbsTypeSize(swap[0]['resources_available.vmem'])
        mem = self.server.status(NODE, 'resources_available.mem')
        mem1 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-1: %s" % mem1)
        self.logger.info("Swap-1: %s" % swap1)

        hook_name = "t1_l1"
        self.t1_cfg2 = addons_dir + os.sep + 'pbs_cgroups2.json'
        a = {'content-type': 'application/x-config',
             'content-encoding': 'default',
             'input-file': self.t1_cfg2}
        rv = self.server.manager(MGR_CMD_IMPORT, HOOK, a, hook_name)
        self.assertTrue(rv == 0)

        self.momA.stop()
        self.momA.start()

        time.sleep(1)

        swap = self.server.status(NODE, 'resources_available.vmem')
        swap2 = PbsTypeSize(swap[0]['resources_available.vmem'])
        mem = self.server.status(NODE, 'resources_available.mem')
        mem2 = PbsTypeSize(mem[0]['resources_available.mem'])
        self.logger.info("Mem-2: %s" % mem2)
        self.logger.info("Swap-2: %s" % swap2)
        mem_resv = mem1-mem2
        swap_resv = swap1-swap2
        self.assertEqual(mem_resv.value, 51200)
        self.assertEqual(swap_resv.value, 46080)
        self.assertTrue(mem_resv.unit, 'kb')
        self.assertTrue(swap_resv.unit, 'kb')


    def _tearDown(self):
        a = {'log_events': '511'}
        self.server.manager(MGR_CMD_SET, SERVER, a, expect=True)
        self.clean_hooks()
        PBSTestSuite.tearDown(self)

script_1 = """#!/bin/bash
if [ -d /cgroup/cpuset/pbspro/$PBS_JOBID ]; then
    ls -1 /cgroup/cpuset/pbspro
    cpus=`cat /cgroup/cpuset/pbspro/$PBS_JOBID/cpuset.cpus`
    echo "CpuSocket=${cpus}"
    mems=`cat /cgroup/cpuset/pbspro/$PBS_JOBID/cpuset.mems`
    echo "MemorySocket=${mems}"
    if [ -d /cgroup/memory/pbspro/$PBS_JOBID ]; then
       mem_limit=`cat /cgroup/memory/pbspro/$PBS_JOBID/memory.limit_in_bytes`
       memsw_limit=`cat /cgroup/memory/pbspro/$PBS_JOBID/memory.memsw.limit_in_bytes`
       echo "MemoryLimit=${mem_limit}"
       echo "MemswLimit=${memsw_limit}"
    fi
elif [ -d /sys/fs/cgroup/cpuset/pbspro/$PBS_JOBID ]; then
    ls -1 /sys/fs/cgroup/cpuset/pbspro
    cpus=`cat /sys/fs/cgroup/cpuset/pbspro/$PBS_JOBID/cpuset.cpus`
    echo "CpuSocket=${cpus}"
    mems=`cat /sys/fs/cgroup/cpuset/pbspro/$PBS_JOBID/cpuset.mems`
    echo "MemorySocket=${mems}"
    if [ -d /sys/fs/cgroup/memory/pbspro/$PBS_JOBID ]; then
       mem_limit=`cat /sys/fs/cgroup/memory/pbspro/$PBS_JOBID/memory.limit_in_bytes`
       memsw_limit=`cat /sys/fs/cgroup/memory/pbspro/$PBS_JOBID/memory.memsw.limit_in_bytes`
       echo "MemoryLimit=${mem_limit}"
       echo "MemswLimit=${memsw_limit}"
    fi
else
    echo "Unable to find the pbspro directory in the cgroup directory"
fi
sleep 1
"""

script_2 = """#!/bin/bash
if [ -d /cgroup/devices/pbs/$PBS_JOBID ]; then
    device_list=`cat /cgroup/devices/pbs/$PBS_JOBID/devices.list`
    echo "${device_list}"
    if [ -d /cgroup/cpuacct/pbs/$PBS_JOBID ] ||
       [ -d /cgroup/cpuset/pbs/$PBS_JOBID ] ||
       [ -d /cgroup/memory/pbs/$PBS_JOBID ]; then
        echo "Disabled cgroup subsystems are populated with the job id"
    fi
elif [ -d /sys/fs/cgroup/devices/pbs/$PBS_JOBID ]; then
    cat /sys/fs/cgroup/devices/pbs/$PBS_JOBID/devices.list
    device_list=`cat /sys/fs/cgroup/devices/pbs/$PBS_JOBID/devices.list`
    echo "${device_list}"
    if [ -d /sys/fs/cgroup/cpuacct/pbs/$PBS_JOBID ] ||
       [ -d /sys/fs/cgroup/cpuset/pbs/$PBS_JOBID ] ||
       [ -d /sys/fs/cgroup/memory/pbs/$PBS_JOBID ]; then
        echo "Disabled cgroup subsystems are populated with the job id"
    fi

else
    echo "Unable to find the pbs directory in the cgroup directory"
fi
sleep 1
"""

sleep_5 = """#!/bin/bash
sleep 5
"""

eat_cpu = """#!/bin/bash
for i in 1 2 3 4; do while : ; do : ; done & done
"""

cfg_json = """{
        "cgroup_prefix"         : "pbspro",
        "periodic_resc_update"  : true, 
        "exclude_hosts"         : [%s],
        "exclude_vntypes"       : [],
        "run_only_on_hosts"     : [%s],   
        "vnode_per_numa_node"   : false,
        "online_offlined_nodes" : true, 
        "cgroup":
        {
                "cpuacct":
                {
                        "enabled"               : true,
                        "exclude_hosts"         : [],
                        "exclude_vntypes"       : []
                },
                "cpuset":
                {
                        "enabled"               : true,
                        "exclude_hosts"         : [%s],
                        "exclude_vntypes"       : []
                },
                "devices":
                {
                        "enabled"               : false,
                        "exclude_hosts"         : [],
                        "exclude_vntypes"       : [],
                        "allow" : ["b *:* rwm","c *:* rwm", ["mic/scif","rwm"],["nvidiactl","rwm", "*"],["nvidia-uvm","rwm"]]
                },
                "hugetlb":
                {
                        "enabled"               : false,
                        "default"               : "0MB",
                        "exclude_hosts"         : [],
                        "exclude_vntypes"       : []
                },
                "memory":
                {
                        "enabled"               : true,
                        "default"               : "256MB",
                        "reserve_memory"        : "0MB",
                        "exclude_hosts"         : [],
                        "exclude_vntypes"       : []
                },
                "memsw":
                {
                        "enabled"               : true,
                        "default"               : "256MB",
                        "reserve_memory"        : "2gb",
                        "exclude_hosts"         : [],
                        "exclude_vntypes"       : []
                }
        }
}
"""

