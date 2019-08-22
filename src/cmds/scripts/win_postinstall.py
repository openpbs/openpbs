# -*- coding: utf-8 -*-
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

import os
import re
import sys
import getopt
import ctypes
import subprocess
import string
from socket import gethostname
from string import Template
from shutil import copyfile
from shutil import copytree
from shutil import rmtree

pbs_conf_path = None
pbs_exec = None
pbs_home = None
pbs_bin = None
pbs_sbin = None
installtype = 'client'
server = None

pbs_conf_t = Template(r"""
PBS_SERVER=${pbs_server}
PBS_EXEC=${pbs_exec}
PBS_HOME=${pbs_home}
PBS_START_SERVER=${pbs_start_server}
PBS_START_COMM=${pbs_start_comm}
PBS_START_MOM=${pbs_start_mom}
PBS_START_SCHED=${pbs_start_sched}
""")

def __log_err(msg):
    sys.stderr.write(msg + '\n')
    sys.stderr.flush()


def __log_info(msg):
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def __run_cmd(cmd):
    with open(os.devnull, 'w') as fd:
        p = subprocess.Popen(cmd, stdout=fd, stderr=fd, shell=False)
        p.communicate()
        return p.returncode


def validate_cred(username, password):
    __log_info('Validating given username and password')
    cmd = [os.path.join(pbs_bin, 'pbs_account.exe')]
    cmd += ['-c', '-s', '-a', username, '-p', password]
    if __run_cmd(cmd) > 0:
        __log_err('Invalid credentials!')
        __log_err('please provide correct username and/or password')
        sys.exit(5)
    else:
        __log_info('Successfully validated given username and password')

def create_pbs_conf():
    __log_info('Creating PBSPro configuration at %s' % pbs_conf_path)
    with open(pbs_conf_path, 'w+') as fp:
        if installtype == 'execution':
            pbs_conf_data = pbs_conf_t.substitute(pbs_server=server,
                                                  pbs_exec=pbs_exec,
                                                  pbs_home=pbs_home,
                                                  pbs_start_server=0,
                                                  pbs_start_comm=0,
                                                  pbs_start_mom=1,
                                                  pbs_start_sched=0)
        elif installtype == 'client':
            pbs_conf_data = pbs_conf_t.substitute(pbs_server=server,
                                                  pbs_exec=pbs_exec,
                                                  pbs_home=pbs_home,
                                                  pbs_start_server=0,
                                                  pbs_start_comm=0,
                                                  pbs_start_sched=0,
                                                  pbs_start_mom=0)
        fp.write(pbs_conf_data.lstrip())
    __log_info('Successfully created PBSPro configuration')


def create_home():
    __log_info('Creating PBSPro home')
    # No need to set correct permission here as it will be done by pbs_mkdirs
    try:
        os.makedirs(pbs_home)
    except WindowsError:
        __log_info('PBS_HOME already available, delete & try')
        sys.exit(3)
    __run_cmd(['icacls', pbs_home, '/grant', 'everyone:(OI)(CI)F'])
    os.makedirs(os.path.join(pbs_home, 'spool'))
    os.makedirs(os.path.join(pbs_home, 'undelivered'))
    os.makedirs(os.path.join(pbs_home, 'auxiliary'))
    os.makedirs(os.path.join(pbs_home, 'checkpoint'))
    os.makedirs(os.path.join(pbs_home, 'mom_logs'))
    os.makedirs(os.path.join(pbs_home, 'mom_priv', 'jobs'))
    os.makedirs(os.path.join(pbs_home, 'mom_priv', 'hooks', 'tmp'))
    pbs_env = []
    if 'windir' in os.environ:
        pbs_env.append('windir=%s' % os.environ['windir'])
        pbs_env.append('WINDIR=%s' % os.environ['windir'])
    if 'SystemRoot' in os.environ:
        pbs_env.append('SystemRoot=%s' % os.environ['SystemRoot'])
        pbs_env.append('SYSTEMROOT=%s' % os.environ['SystemRoot'])
    if 'SystemDrive' in os.environ:
        pbs_env.append('SystemDrive=%s' % os.environ['SystemDrive'])
        pbs_env.append('SYSTEMDRIVE=%s' % os.environ['SystemDrive'])
    if 'OS' in os.environ:
        pbs_env.append('OS=%s' % os.environ['OS'])
    if 'LOGONSERVER' in os.environ:
        pbs_env.append('LOGONSERVER=%s' % os.environ['LOGONSERVER'])
    if 'HOMEDRIVE' in os.environ:
        pbs_env.append('HOMEDRIVE=%s' % os.environ['HOMEDRIVE'])
    if 'COMPUTERNAME' in os.environ:
        pbs_env.append('COMPUTERNAME=%s' % os.environ['COMPUTERNAME'])
    pbs_env.append('PBS_CONF_FILE=%s' % pbs_conf_path)
    with open(os.path.join(pbs_home, 'pbs_environment'), 'w+') as fp:
        fp.write('\n'.join(pbs_env) + '\n')
    with open(os.path.join(pbs_home, 'mom_priv', 'config'), 'w+') as fp:
        fp.write('$clienthost %s%s' % (server, '\n'))

def __svc_helper(svc, username, password):
    svc_name = os.path.basename(svc).replace('.exe', '').upper()
    cmd = [os.path.join(pbs_bin, 'pbs_account.exe')]
    cmd += ['--reg', svc, '-a', username, '-p', password]
    unregcmd = [os.path.join(pbs_bin, 'pbs_account.exe')]
    unregcmd += ['--unreg', svc]
    ret_code = __run_cmd(cmd)
    if ret_code > 0:
        __run_cmd(unregcmd)
        if __run_cmd(cmd) > 0:
            __log_err('Failed to register service %s' % svc_name)
            sys.exit(9)
        else:
            __log_info('Successfully registered %s service' % svc_name)
    else:
        __log_info('Successfully registered %s service' % svc_name)
    if __run_cmd(['net', 'start', svc_name]) > 0:
        __log_err('Failed to start service %s' % svc_name)
        sys.exit(10)
    else:
        __log_info('Successfully started %s service' % svc_name)


def register_and_start_services(username, password):
    if installtype == 'execution':
        __svc_helper(os.path.join(pbs_sbin, 'pbs_mom.exe'), username, password)


def usage():
    prog = os.path.basename(sys.argv[0])
    _msg = ['%s [Options]\n' % prog]
    _msg += ['Options:\n']
    _msg += ['    -u|--user=<username>\t- ']
    _msg += ['specify PBS Service/database username\n']
    _msg += ['    -p|--passwd=<password>\t- ']
    _msg += ['specify PBS Service/database user\'s password\n']
    _msg += ['    -t|--type=<type>\t\t- specify PBS installation type \n']
    _msg += ['\t\t\t\t  (execution/client)\n']
    _msg += ['    -s|--server=<server>\t- ']
    _msg += ['specify PBS Server value\n']
    _msg += ['    -h|--help\t\t\t- print help message\n']
    print("".join(_msg))


def main():
    global pbs_conf_path
    global pbs_exec
    global pbs_home
    global pbs_bin
    global pbs_sbin
    global installtype
    global server
    username = None
    password = None
    if len(sys.argv) < 2:
        usage()
        sys.exit(3)
    try:
        largs = ['help', 'user=', 'passwd=', 'type=', 'server=']
        opts, _ = getopt.getopt(sys.argv[1:], 'hu:p:t:s:', largs)
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(3)
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif opt in ('-u', '--user'):
            username = arg
        elif opt in ('-p', '--passwd'):
            password = arg
        elif opt in ('-t', '--type'):
            if arg not in ('execution', 'client'):
                usage()
                sys.exit(3)
            installtype = arg
        elif opt in ('-s', '--server'):
            server = arg
        else:
            __log_err('Unrecognized option %s' % opt)
            usage()
            sys.exit(3)
    if username is None or password is None:
        __log_err('No username and/or password provided!')
        usage()
        sys.exit(4)
    if server is None:
        __log_err('\nProvide PBS_SERVER info value using -s|--server \n')
        usage()
        sys.exit(4)

    if not ctypes.windll.shell32.IsUserAnAdmin():
        __log_err('Only user with Administrators privileges can run this script!')
        sys.exit(255)
    __log_info('Post installation process started')
    __log_info('This script may take a few minutes to run')
    pbs_conf_path = os.environ.get('PBS_CONF_FILE', None)
    if pbs_conf_path is None:
        __log_err('Failed to find PBS_CONF_FILE path from environ')
        sys.exit(1)
    pbs_exec = os.path.join(os.path.dirname(pbs_conf_path), 'exec')
    if not os.path.isdir(pbs_exec):
        __log_err('Cound not find PBS_EXEC at %s' % pbs_exec)
        sys.exit(2)
    pbs_bin = os.path.join(os.path.dirname(pbs_conf_path), 'exec', 'bin')
    if not os.path.isdir(pbs_bin):
        __log_err('Cound not find PBS_EXEC\bin at %s' % pbs_bin)
        sys.exit(2)
    pbs_sbin = os.path.join(os.path.dirname(pbs_conf_path), 'exec', 'sbin')
    if not os.path.isdir(pbs_bin):
        __log_err('Cound not find PBS_EXEC\sbin at %s' % pbs_sbin)
        sys.exit(2)
    pbs_home = os.path.join(os.path.dirname(pbs_conf_path), 'home')
    validate_cred(username, password)
    create_pbs_conf()
    if installtype == 'execution':
        create_home()		
    __run_cmd([os.path.join(pbs_bin, 'pbs_mkdirs.exe'), 'mom'])
    cmd = ['mklink', '/H']
    cmd += ['"' + os.path.join(pbs_bin, 'pbs-sleep.exe') + '"']
    cmd += ['"' + os.path.join(pbs_bin, 'pbs_sleep.exe') + '"']
    cmd = " ".join(cmd)
    os.system(cmd)
    register_and_start_services(username, password)
    __log_info('Successfully completed post installation process')


if __name__ == '__main__':
    main()
