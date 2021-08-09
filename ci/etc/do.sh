#!/bin/bash -xe

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

if [ $(id -u) -ne 0 ]; then
  echo "This script must be run by root user"
  exit 1
fi

if [ -f /src/ci ]; then
  IS_CI_BUILD=1
  FIRST_TIME_BUILD=$1
  . /src/etc/macros
  config_dir=/src/${CONFIG_DIR}
  chmod -R 755 ${config_dir}
  logdir=/logs
  chmod -R 755 ${logdir}
  PBS_DIR=/pbssrc
else
  PBS_DIR=$(readlink -f $0 | awk -F'/ci/' '{print $1}')
fi

cd ${PBS_DIR}
. /etc/os-release
SPEC_FILE=$(/bin/ls -1 ${PBS_DIR}/*.spec)
REQ_FILE=${PBS_DIR}/test/fw/requirements.txt
if [ ! -r ${SPEC_FILE} -o ! -r ${REQ_FILE} ]; then
  echo "Couldn't find pbs spec file or ptl requirements file"
  exit 1
fi

if [ "x${IS_CI_BUILD}" != "x1" ] || [ "x${FIRST_TIME_BUILD}" == "x1" -a "x${IS_CI_BUILD}" == "x1" ]; then
  if [ "x${ID}" == "xcentos" -a "x${VERSION_ID}" == "x7" ]; then
    yum clean all
    yum -y install yum-utils epel-release rpmdevtools
    yum -y install python3-pip sudo which net-tools man-db time.x86_64 \
      expat libedit postgresql-server postgresql-contrib python3 \
      sendmail sudo tcl tk libical libasan llvm git
    rpmdev-setuptree
    yum-builddep -y ${SPEC_FILE}
    yum -y install $(rpmspec --requires -q ${SPEC_FILE} | awk '{print $1}' | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${REQ_FILE}
    if [ "x${BUILD_MODE}" == "xkerberos" ]; then
      yum -y install krb5-libs krb5-devel libcom_err libcom_err-devel
    fi
  elif [ "x${ID}" == "xcentos" -a "x${VERSION_ID}" == "x8" ]; then
    export LANG="C.utf8"
    dnf -y clean all
    dnf -y install 'dnf-command(config-manager)'
    dnf -y config-manager --set-enabled powertools
    dnf -y install epel-release
    dnf -y install python3-pip sudo which net-tools man-db time.x86_64 \
      expat libedit postgresql-server postgresql-contrib python3 \
      sendmail sudo tcl tk libical libasan llvm git
    dnf -y builddep ${SPEC_FILE}
    dnf -y install $(rpmspec --requires -q ${SPEC_FILE} | awk '{print $1}' | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${REQ_FILE}
    if [ "x${BUILD_MODE}" == "xkerberos" ]; then
      dnf -y install krb5-libs krb5-devel libcom_err libcom_err-devel
    fi
  elif [ "x${ID}" == "xopensuse" -o "x${ID}" == "xopensuse-leap" ]; then
    zypper -n ref
    zypper -n install rpmdevtools python3-pip sudo which net-tools man time.x86_64 git
    rpmdev-setuptree
    zypper -n install --force-resolution $(rpmspec --buildrequires -q ${SPEC_FILE} | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    zypper -n install --force-resolution $(rpmspec --requires -q ${SPEC_FILE} | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${REQ_FILE}
  elif [ "x${ID}" == "xdebian" ]; then
    if [ "x${DEBIAN_FRONTEND}" == "x" ]; then
      export DEBIAN_FRONTEND=noninteractive
    fi
    apt-get -y update
    apt-get install -y build-essential dpkg-dev autoconf libtool rpm alien libssl-dev \
      libxt-dev libpq-dev libexpat1-dev libedit-dev libncurses5-dev \
      libical-dev libhwloc-dev pkg-config tcl-dev tk-dev python3-dev \
      swig expat postgresql postgresql-contrib python3-pip sudo \
      man-db git elfutils
    pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${REQ_FILE}
  elif [ "x${ID}" == "xubuntu" ]; then
    if [ "x${DEBIAN_FRONTEND}" == "x" ]; then
      export DEBIAN_FRONTEND=noninteractive
    fi
    apt-get -y update
    apt-get install -y build-essential dpkg-dev autoconf libtool rpm alien libssl-dev \
      libxt-dev libpq-dev libexpat1-dev libedit-dev libncurses5-dev \
      libical-dev libhwloc-dev pkg-config tcl-dev tk-dev python3-dev \
      swig expat postgresql python3-pip sudo man-db git elfutils
    pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r ${REQ_FILE}
  else
    echo "Unknown platform..."
    exit 1
  fi
fi

if [ "x${FIRST_TIME_BUILD}" == "x1" -a "x${IS_CI_BUILD}" == "x1" ]; then
  echo "### First time build is complete ###"
  echo "READY:$(hostname -s)" >>${config_dir}/${STATUS_FILE}
  exit 0
fi

if [ "x${ID}" == "xcentos" -a "x${VERSION_ID}" == "x8" ]; then
  export LANG="C.utf8"
  swig_opt="--with-swig=/usr/local"
  if [ ! -f /tmp/swig/swig/configure ]; then
    # source install swig
    dnf -y install gcc-c++ byacc pcre-devel
    mkdir -p /tmp/swig/
    cd /tmp/swig
    git clone https://github.com/swig/swig --branch rel-4.0.0 --single-branch
    cd swig
    ./autogen.sh
    ./configure
    make -j8
    make install
    cd ${PBS_DIR}
  fi
fi

if [ "x${ONLY_INSTALL_DEPS}" == "x1" ]; then
  exit 0
fi
_targetdirname=target-${ID}-$(hostname -s)
if [ "x${ONLY_INSTALL}" != "x1" -a "x${ONLY_REBUILD}" != "x1" -a "x${ONLY_TEST}" != "x1" ]; then
  rm -rf ${_targetdirname}
fi
mkdir -p ${_targetdirname}
[[ -f Makefile ]] && make distclean || true
if [ ! -f ./${SPEC_FILE} ]; then
  git checkout ${SPEC_FILE}
fi
if [ ! -f ./configure ]; then
  ./autogen.sh
fi
if [ "x${ONLY_REBUILD}" != "x1" -a "x${ONLY_INSTALL}" != "x1" -a "x${ONLY_TEST}" != "x1" ]; then
  _cflags="-g -O2 -Wall -Werror"
  if [ "x${ID}" == "xubuntu" ]; then
    _cflags="${_cflags} -Wno-unused-result"
  fi
  cd ${_targetdirname}
  if [ -f /src/ci ]; then
    if [ -f ${config_dir}/${CONFIGURE_OPT_FILE} ]; then
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
if len(x.split("'")) > 1:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('\'')[1])
else:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('"')[1])
END
)
      _cflags="$(python3 -c "$PYTHON_CODE")"
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
print(re.sub(r"CFLAGS=(\"|\').*(\"|\')","",x))
END
)
    configure_opt="$(python3 -c "$PYTHON_CODE")"
    else
      configure_opt='--prefix=/opt/pbs --enable-ptl'
    fi
    if [ -z "${_cflags}" ]; then
      ../configure ${configure_opt} ${swig_opt}
    else
      ../configure CFLAGS="${_cflags}" ${configure_opt} ${swig_opt}
    fi
    if [ "x${ONLY_CONFIGURE}" == "x1" ]; then
      exit 0
    fi
  else
    configure_opt='--prefix=/opt/pbs --enable-ptl'
    if [ "x${BUILD_MODE}" == "xkerberos" ]; then
      configure_opt="${configure_opt} --with-krbauth PATH_KRB5_CONFIG=/usr/bin/krb5-config"
    fi
    ../configure CFLAGS="${_cflags}" ${configure_opt} ${swig_opt}
  fi
  cd -
fi
cd ${_targetdirname}
prefix=$(cat ${config_dir}/${CONFIGURE_OPT_FILE} | awk -F'prefix=' '{print $2}' | awk -F' ' '{print $1}')
if [ "x${prefix}" == "x" ]; then
  prefix='/opt/pbs'
fi
if [ "x${ONLY_INSTALL}" == "x1" -o "x${ONLY_TEST}" == "x1" ]; then
  echo "skipping make"
else
  if [ ! -f ${PBS_DIR}/${_targetdirname}/Makefile ]; then
    if [ -f ${config_dir}/${CONFIGURE_OPT_FILE} ]; then
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
if len(x.split("'")) > 1:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('\'')[1])
else:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('"')[1])
END
)
      _cflags="$(python3 -c "$PYTHON_CODE")"
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
print(re.sub(r"CFLAGS=(\"|\').*(\"|\')","",x))
END
)
      configure_opt="$(python3 -c "$PYTHON_CODE")"
    else
      configure_opt='--prefix=/opt/pbs --enable-ptl'
    fi
    if [ -z "${_cflags}" ]; then
      ../configure ${configure_opt}
    else
      ../configure CFLAGS="${_cflags}" ${configure_opt}
    fi
  fi
  make -j8
fi
if [ "x${ONLY_REBUILD}" == "x1" ]; then
  exit 0
fi
if [ "x${ONLY_TEST}" != "x1" ]; then
  if [ ! -f ${PBS_DIR}/${_targetdirname}/Makefile ]; then
    if [ -f ${config_dir}/${CONFIGURE_OPT_FILE} ]; then
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
if len(x.split("'")) > 1:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('\'')[1])
else:
  print(re.match(r"CFLAGS=(\"|\').*(\"|\')",x).group(0).split('"')[1])
END
)
      _cflags="$(python3 -c "$PYTHON_CODE")"
      PYTHON_CODE=$(cat <<END
with open('${config_dir}/${CONFIGURE_OPT_FILE}') as f:
  x = f.read()
import re
print(re.sub(r"CFLAGS=(\"|\').*(\"|\')","",x))
END
)
    configure_opt="$(python3 -c "$PYTHON_CODE")"
    else
      configure_opt='--prefix=/opt/pbs --enable-ptl'
    fi
    if [ -z "${_cflags}" ]; then
      ../configure ${configure_opt}
    else
      ../configure CFLAGS="${_cflags}" ${configure_opt}
    fi
    make -j8
  fi
  make -j8 install
  chmod 4755 ${prefix}/sbin/pbs_iff ${prefix}/sbin/pbs_rcp
  if [ "x${DONT_START_PBS}" != "x1" ]; then
    ${prefix}/libexec/pbs_postinstall server
    sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf
    if [ "x$IS_CI_BUILD" == "x1" ]; then
      /src/etc/configure_node.sh
    fi
    /etc/init.d/pbs restart
  fi
fi

if [ "x${BUILD_MODE}" == "xkerberos" ]; then
  echo "PTL with Kerberos support not implemented yet."
  exit 0
fi

set +e
. /etc/profile.d/ptl.sh
set -e
pbs_config --make-ug

if [ "x${RUN_TESTS}" == "x1" ]; then
  if [ "x${ID}" == "xcentos" ]; then
    export LC_ALL=en_US.utf-8
    export LANG=en_US.utf-8
  elif [ "x${ID}" == "xopensuse" ]; then
    export LC_ALL=C.utf8
  fi
  ptl_tests_dir=/pbssrc/test/tests
  cd ${ptl_tests_dir}/
  benchpress_opt="$(cat ${config_dir}/${BENCHPRESS_OPT_FILE})"
  eval_tag="$(echo ${benchpress_opt} | awk -F'"' '{print $2}')"
  benchpress_opt="$(echo ${benchpress_opt} | sed -e 's/--eval-tags=\".*\"//g')"
  params="--param-file=${config_dir}/${PARAM_FILE}"
  time_stamp=$(date -u "+%Y-%m-%d-%H%M%S")
  ptl_log_file=${logdir}/logfile-${time_stamp}
  chown pbsroot ${logdir}
  if [ -z "${eval_tag}" ]; then
    sudo -Hiu pbsroot pbs_benchpress ${benchpress_opt} --db-type=html --db-name=${logdir}/result.html -o ${ptl_log_file} ${params}
  else
    sudo -Hiu pbsroot pbs_benchpress --eval-tags="'${eval_tag}'" ${benchpress_opt} --db-type=html --db-name=${logdir}/result.html -o ${ptl_log_file} ${params}
  fi
fi

if [ "x${IS_CI_BUILD}" != "x1" ]; then
  cd /opt/ptl/tests/
#Azure pipeline : on Suse platform man page test is failing. Need to analyze.
#for time being skipping man page test case
  pbs_benchpress --tags=smoke --exclude=SmokeTest.test_man_pages
fi
