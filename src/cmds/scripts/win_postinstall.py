import sys
import getopt
import os
import subprocess
import socket
from tempfile import mkstemp
from shutil import move
import time

install_path = ''
pbs_path = ''


def replace(file_path, pattern, subst):
    fh, abs_path = mkstemp()
    with os.fdopen(fh, 'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                new_file.write(line.replace(pattern, subst))
    # Remove original file
    os.remove(file_path)
    # Move new file
    move(abs_path, file_path)


def ValidateCredentials(username, password):
    if (username != '' and password != ''):
        with open(os.devnull, 'w') as fp:
            pbs_account_binary = os.path.join(
                pbs_path, "exec", "bin", "pbs_account.exe")
            theproc = subprocess.Popen(
                [pbs_account_binary,
                    "-c", "-s", "-a", username, "-p", password],
                stdout=fp,
                stderr=fp)
            theproc.communicate()
            if theproc.returncode > 0:
                print "Invalid credentials"
                sys.exit(3)
            else:
                print "Post install process started..."
                print "User Validation Success"
    else:
        print "Usage error: \n post_install.py -u <username> -p <password>"
        sys.exit(4)


def CreatePbsConfFile():
    pbsconffile = os.path.join(pbs_path, 'pbs.conf')
    with open(pbsconffile, 'w') as fp:
        fp.write("PBS_SERVER=" + socket.gethostname() + "\r\n")
        fp.write("PBS_EXEC=" + pbs_path + "exec\r\n")
        fp.write("PBS_HOME=" + pbs_path + "home\r\n")
        fp.write("PBS_START_SERVER=1\r\n")
        fp.write("PBS_START_COMM=1\r\n")
        fp.write("PBS_START_MOM=1\r\n")
        fp.write("PBS_START_SCHED=1\r\n")
        fp.close()
        print "pbs.conf file created"


def RunPbsmkdirs():
    os.system('pbs_mkdirs')
    print 'Securing and recreating pbs_home directories'


def InstallingVcredist():
    print 'Installing Visual C++ Redist..'
    redist_path = os.path.join(install_path, "vcredist_x86.exe")
    install_redist = '"' + redist_path + '"' + ' /passive /norestart'
    if (os.path.exists(redist_path)):
        os.system(install_redist)
        print 'Installation done..'
    else:
        print "Visual C++ Redist is not available"
        sys.exit(5)


def UpdateDSconfig():
    postgresql_file_path = os.path.join(
        pbs_path, "home", "datastore", "postgresql.conf")
    if (os.path.exists(postgresql_file_path)):
        # change port to 15007
        replace(postgresql_file_path, "#port = 5432", "port = 15007")
        # change listen address to *
        replace(
            postgresql_file_path,
            "#listen_addresses = 'localhost'",
            "listen_addresses = '*'")
        # change escape sequence parsing
        replace(
            postgresql_file_path,
            "#standard_conforming_strings = on",
            "standard_conforming_strings = on")
        # change logging collector
        replace(
            postgresql_file_path,
            "#logging_collector = off",
            "logging_collector = on")
        # change logging directory
        replace(
            postgresql_file_path,
            "#log_directory = 'pg_log'",
            "log_directory = 'pg_log'")
        # change logging filename
        replace(
            postgresql_file_path,
            "#log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'",
            "log_filename = 'pbs_dataservice_log.%a'")
        # change logging truncate
        replace(
            postgresql_file_path,
            "#log_truncate_on_rotation = off",
            "log_truncate_on_rotation = on")
        # change logging rotation age
        replace(
            postgresql_file_path,
            "#log_rotation_age = 1d",
            "log_rotation_age = 1440")
        # change logging format to add timestamp
        replace(
            postgresql_file_path,
            "#log_line_prefix = ''",
            "log_line_prefix = '%t'")
        print "postgresql file Successfully configured"
    else:
        print "postgresqlfile is not available to configure"
        exit(7)
    # Configuring pg_hba.conf file
    pg_hba_file_path = os.path.join(
        pbs_path, "home", "datastore", "pg_hba.conf")
    if (os.path.exists(pg_hba_file_path)):
        replace(
            pg_hba_file_path,
            "# IPv4 local connections:",
            "# IPv4 connections:")
        # Change localaddress values for all users
        original_str = "host    all             all             " + \
            "127.0.0.1/32            trust"
        replacement_str = "host    all         all         " + \
            "127.0.0.1/32          md5\nhost       all         " + \
            "all        0.0.0.0/0      md5"
        replace(pg_hba_file_path, original_str, replacement_str)
        # Change user specific config
        original_str = "# Allow replication connections from localhost,\
        by a user with the"
        replacement_str = "host     all         all         localhost\
        md5"
        replace(pg_hba_file_path, original_str, replacement_str)
        print "pg_hba file Successfully configured"
    else:
        print "pg_hba file is not available to configure"
        exit(8)


def InstallDataService(username, password):
    pbs_pathquote = "\"" + pbs_path
    # Create server_priv directory
    server_priv_path = os.path.join(pbs_path, 'home', 'server_priv')
    if not os.path.exists(server_priv_path):
        os.makedirs(server_priv_path)
    # Creation of db_user file at PBS_HOME\server_priv directory
    dbuserfile = os.path.join(pbs_path, 'home', 'server_priv', 'db_user')
    with open(dbuserfile, 'w') as db:
        db.write(username)
        db.close()
    # Creation of createdb.bat script at PBS_EXEC\etc directory
    DBpath = "\"" + os.path.join(pbs_path, "home", "datastore") + "\""
    createdbfile = os.path.join(pbs_path, "exec", "etc", "createdb.bat")
    ErrChk = "IF %ERRORLEVEL% NEQ 0 GOTO ERR\r\n"
    with open(createdbfile, 'w') as crtdb:
        buffer = "@echo off \r\n"
        crtdb.write(buffer)
        # echo PBS_CONF_FILE
        buffer = "set PBS_CONF_FILE=" + os.path.join(pbs_path, "pbs.conf\r\n")
        crtdb.write(buffer)
        # initialize database cluster
        buffer = "\"" + os.path.join(
            pbs_path,
            "exec",
            "pgsql",
            "bin",
            "initdb.exe") + "\" -D " + DBpath + " -E SQL_ASCII --locale=C\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # start database
        buffer = "call " + "\"" + \
            os.path.join(pbs_path, "exec", "sbin",
                         "pbs_dataservice") + "\" start\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # create db
        buffer = "\"" + os.path.join(pbs_path,
                                     "exec",
                                     "pgsql",
                                     "bin",
                                     "createdb.exe") \
                      + "\" -p 15007 pbs_datastore\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # install schema
        buffer = "\"" + os.path.join(
            pbs_path,
            "exec",
            "pgsql",
            "bin",
            "psql.exe") + "\" -p 15007 -d pbs_datastore -f " \
                        + "\"" + os.path.join(pbs_path,
                                              "exec",
                                              "etc",
                                              "pbs_db_schema.sql") \
                        + "\"\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # create superuser
        buffer = "\"" + os.path.join(pbs_path,
                                     "exec",
                                     "pgsql",
                                     "bin",
                                     "psql.exe") \
                      + "\" -p 15007 -d pbs_datastore -c \"create user \\\""\
                      + username + "\\\" SUPERUSER LOGIN\"\r\n"
        crtdb.write(buffer)
        # run Pbs_ds_password
        buffer = "\"" + os.path.join(pbs_path,
                                     "exec",
                                     "sbin",
                                     "pbs_ds_password.exe") + "\" -r\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # stop database
        buffer = "call \"" + \
            os.path.join(pbs_path, "exec", "sbin",
                         "pbs_dataservice") + "\" stop\r\n"
        crtdb.write(buffer)
        crtdb.write(ErrChk)
        # error handling
        crtdb.write("exit /b 0\r\n")
        crtdb.write(":ERR\r\n")
        # stop database
        buffer = "call \"" + \
            os.path.join(pbs_path, "exec", "sbin",
                         "pbs_dataservice") + "\" stop\r\n"
        crtdb.write(buffer)
        crtdb.write("exit /b 1\r\n")
        crtdb.close()
        print "Executing createdbfile as install user"
        with open(os.devnull, 'w') as fd:
            theproc = subprocess.Popen([createdbfile], stdout=fd, stderr=fd)
            theproc.communicate()
            if theproc.returncode > 0:
                print "Failed to initilize database"
                sys.exit(6)
            else:
                print "Database intialization is success"
        UpdateDSconfig()
        print "InstallDataService completed "


def CreateServerdbFile():
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen(
            ["net", "stop", "pbs_server"], stdout=fd, stderr=fd)
        theproc.communicate()
    # Creating PBS Server database...
    ServerPath = os.path.join(pbs_path, "exec", "sbin", "pbs_server.exe")
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen([ServerPath, "-C"], stdout=fd, stderr=fd)
        theproc.communicate()
        # print theproc.returncode
        if theproc.returncode > 0:
            print "Failed to create server database..."
            sys.exit(13)
        else:
            print "PBS Server database created..."
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen(
            ["net", "start", "pbs_server"], stdout=fd, stderr=fd)
        theproc.communicate()
        if theproc.returncode > 0:
            cmd = subprocess.Popen(
                ["sc", "query", "pbs_server"],
                stdout=subprocess.PIPE, stderr=fd)
            for line in cmd.stdout:
                if "_PENDING" in line:
                    time.sleep(30)
                    for i in range(5):
                        stat = subprocess.Popen(
                            ["sc", "query", "pbs_server"],
                            stdout=subprocess.PIPE, stderr=fd)
                        for eachline in stat.stdout:
                            if "_PENDING" in eachline:
                                time.sleep(30)
                            elif "RUNNING" in eachline:
                                break
                    finalcheck = subprocess.Popen(
                        ["sc", "query", "pbs_server"],
                        stdout=subprocess.PIPE, stderr=fd)
                    for everyline in finalcheck.stdout:
                        if "_PENDING" in everyline:
                            print "Failed to start Server"
                            sys.exit(14)
                        elif "RUNNING" in everyline:
                            print "Server started"
                            break
                elif "RUNNING" in line:
                    print "Server started"
                    break
    # create server default file
    Serverdfltfile = os.path.join(
        pbs_path, "home", "spool", "createsvrdefaults.bat")
    QmgrPath = os.path.join(pbs_path, "exec", "bin", "qmgr.exe")
    if (os.path.exists(QmgrPath)):
        pass
    else:
        print "Qmgr not available"
        sys.exit(15)
    quotedQmgrPath = "\"" + QmgrPath + "\""
    ErrChk = "IF %ERRORLEVEL% NEQ 0 GOTO ERR\r\n"
    with open(Serverdfltfile, 'w') as svrfd:
        svrfd.write("@echo off\r\n")
        content = quotedQmgrPath + " -c \"create queue workq\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set queue workq queue_type = Execution\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set server single_signon_password_enable = True\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath + " -c \"set queue workq enabled = True\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath + " -c \"set queue workq started = True\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath + " -c \"set server scheduling = True\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set server default_queue = workq\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath + " -c \"set server log_events = 511\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath + " -c \"set server mail_from = adm\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set server query_other_jobs = True\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set server scheduler_iteration = 600\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"set server resources_default.ncpus = 1\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        content = quotedQmgrPath \
            + " -c \"create node " + socket.gethostname() + \
            "\"\r\n"
        svrfd.write(content)
        svrfd.write(ErrChk)
        svrfd.write("exit /b 0\r\n")
        svrfd.write(":ERR\r\n")
        svrfd.write("exit /b %ERRORLEVEL%\r\n")
        svrfd.close()
        print "Executing serverdbfile as installing user"
        with open(os.devnull, 'w') as fd:
            theproc = subprocess.Popen([Serverdfltfile])
            theproc.communicate()
            if theproc.returncode > 0:
                print "Failed to set server defaults value"
                with open(os.devnull, 'w') as fd:
                    theproc = subprocess.Popen(
                        ["sc", "stop", "pbs_server"], stdout=fd, stderr=fd)
                    theproc.communicate()
                    time.sleep(60)
                sys.exit(16)
            else:
                print "Server defaults configs are done"


def RegistingAndStartingServices(username, password):
    # Check existence of the daemons
    ServerPath = os.path.join(pbs_path, "exec", "sbin", "pbs_server.exe")
    CommPath = os.path.join(pbs_path, "exec", "sbin", "pbs_comm.exe")
    MomPath = os.path.join(pbs_path, "exec", "sbin", "pbs_mom.exe")
    SchedPath = os.path.join(pbs_path, "exec", "sbin", "pbs_sched.exe")
    if (os.path.exists(ServerPath)):
        pass
    else:
        print ServerPath + " is missing"
    # Renaming sched priv config files
    pbs_dedicated_file = os.path.join(
        pbs_path, "home", "sched_priv", "pbs_dedicated")
    dedicated_file = os.path.join(pbs_path, "home", "sched_priv", "dedicated")
    if (os.path.exists(pbs_dedicated_file)):
        os.rename(pbs_dedicated_file, dedicated_file)
    else:
        print pbs_dedicated_file + " is missing"
    pbs_holidays_file = os.path.join(
        pbs_path, "home", "sched_priv", "pbs_holidays")
    holidays_file = os.path.join(pbs_path, "home", "sched_priv", "holidays")
    if (os.path.exists(pbs_holidays_file)):
        os.rename(pbs_holidays_file, holidays_file)
    else:
        print pbs_dedicated_file + " is missing"
    pbs_resource_group_file = os.path.join(
        pbs_path, "home", "sched_priv", "pbs_resource_group")
    resource_group_file = os.path.join(
        pbs_path, "home", "sched_priv", "resource_group")
    if (os.path.exists(pbs_resource_group_file)):
        os.rename(pbs_resource_group_file, resource_group_file)
    else:
        print pbs_resource_group_file + " is missing"
    pbs_sched_config_file = os.path.join(
        pbs_path, "home", "sched_priv", "pbs_sched_config")
    sched_config_file = os.path.join(
        pbs_path, "home", "sched_priv", "sched_config")
    if (os.path.exists(pbs_sched_config_file)):
        os.rename(pbs_sched_config_file, sched_config_file)
    else:
        print pbs_sched_config_file + " is missing"
    # Register and Start Sched - start this first since Server now always
    # contact this
    print "Registering and starting PBS services..."
    pbs_account_binary = os.path.join(
        pbs_path, "exec", "bin", "pbs_account.exe")
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen(
            [pbs_account_binary, "--unreg", SchedPath], stdout=fs, stderr=fs)
        theproc.communicate()
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen([pbs_account_binary,
                                    "--reg",
                                    SchedPath,
                                    "-a",
                                    username,
                                    "-p",
                                    password],
                                   stdout=fs,
                                   stderr=fs)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to register Scheduler"
            sys.exit(9)
        else:
            print "Scheduler service registered"
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen(
            ["net", "start", "pbs_sched"], stdout=fd, stderr=fd)
        theproc.communicate()
        if theproc.returncode > 0:
            cmd = subprocess.Popen(
                ["sc", "query", "pbs_sched"],
                stdout=subprocess.PIPE, stderr=fd)
            for line in cmd.stdout:
                if "_PENDING" in line:
                    time.sleep(30)
                    for i in range(5):
                        stat = subprocess.Popen(
                            ["sc", "query", "pbs_sched"],
                            stdout=subprocess.PIPE, stderr=fd)
                        for eachline in stat.stdout:
                            if "_PENDING" in eachline:
                                time.sleep(30)
                            elif "RUNNING" in eachline:
                                break
                    finalcheck = subprocess.Popen(
                        ["sc", "query", "pbs_sched"],
                        stdout=subprocess.PIPE, stderr=fd)
                    for everyline in finalcheck.stdout:
                        if "_PENDING" in everyline:
                            print "Failed to start Scheduler"
                            sys.exit(10)
                        elif "RUNNING" in everyline:
                            print "Scheduler started"
                            break
                elif "RUNNING" in line:
                    print "Scheduler started"
                    break
    # Register Comm
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen(
            [pbs_account_binary, "--unreg", CommPath], stdout=fs, stderr=fs)
        theproc.communicate()
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen([pbs_account_binary,
                                    "--reg",
                                    CommPath,
                                    "-a",
                                    username,
                                    "-p",
                                    password],
                                   stdout=fs,
                                   stderr=fs)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to register Comm"
            sys.exit(11)
        else:
            print "Comm service registered"
    # Register Server and create server database with default values
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen(
            [pbs_account_binary, "--unreg", ServerPath], stdout=fs, stderr=fs)
        theproc.communicate()
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen([pbs_account_binary,
                                    "--reg",
                                    ServerPath,
                                    "-a",
                                    username,
                                    "-p",
                                    password],
                                   stdout=fs,
                                   stderr=fs)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to register Server"
            sys.exit(12)
        else:
            print "Server service registered"
    CreateServerdbFile()
    # Register and Start Mom
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen(
            [pbs_account_binary, "--unreg", MomPath], stdout=fs, stderr=fs)
        theproc.communicate()
    with open(os.devnull, 'w') as fs:
        theproc = subprocess.Popen([pbs_account_binary,
                                    "--reg",
                                    MomPath,
                                    "-a",
                                    username,
                                    "-p",
                                    password],
                                   stdout=fs,
                                   stderr=fs)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to register Mom"
            sys.exit(17)
        else:
            print "Mom service registered"
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen(
            ["sc", "start", "pbs_mom"], stdout=fd, stderr=fd)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to start mom "
            sys.exit(18)
        cmd = subprocess.Popen(["sc", "query", "pbs_mom"],
                               stdout=subprocess.PIPE, stderr=fd)
        for line in cmd.stdout:
            if "_PENDING" in line:
                time.sleep(30)
                for i in range(5):
                    stat = subprocess.Popen(
                        ["sc", "query", "pbs_mom"],
                        stdout=subprocess.PIPE, stderr=fd)
                    for eachline in stat.stdout:
                        if "_PENDING" in eachline:
                            time.sleep(30)
                        elif "RUNNING" in eachline:
                            break
                finalcheck = subprocess.Popen(
                    ["sc", "query", "pbs_mom"],
                    stdout=subprocess.PIPE, stderr=fd)
                for everyline in finalcheck.stdout:
                    if "_PENDING" in everyline:
                        print "Failed to start Mom"
                        sys.exit(19)
                    elif "RUNNING" in everyline:
                        print "MoM started"
                        break
            elif "RUNNING" in line:
                print "Mom started"
                break
    # Start comm
    with open(os.devnull, 'w') as fd:
        theproc = subprocess.Popen(
            ["net", "start", "pbs_comm"], stdout=fd, stderr=fd)
        theproc.communicate()
        if theproc.returncode > 0:
            print "Failed to start comm "
            sys.exit(20)


def main(argv):
    username = ''
    password = ''
    try:
        opts, args = getopt.getopt(
            argv, "h:u:p:", [
                "type=", "user=", "passwd="])
    except getopt.GetoptError:
        print 'post_install.py -u <username> -p <password>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'post_install.py -u <username> -p <password>'
            sys.exit()
        elif opt in ("-u", "--user"):
            username = arg
        elif opt in ("-p", "--passwd"):
            password = arg
    ValidateCredentials(username, password)
    CreatePbsConfFile()
    InstallingVcredist()
    InstallDataService(username, password)
    RunPbsmkdirs()
    RegistingAndStartingServices(username, password)
    print "Successfully installed"


if __name__ == "__main__":
    install_path = os.path.dirname(os.path.realpath(__file__))
    exec_etc_path = os.path.join("exec", "etc")
    position_of_exec = install_path.find(exec_etc_path)
    if position_of_exec:
        pbs_path = install_path[:position_of_exec]
    else:
        print "Error while finding the PBS Pro installation path"
        sys.exit(1)
    main(sys.argv[1:])
