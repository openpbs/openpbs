#!/bin/bash -xe

if [ $(id -u) -ne 0 ]; then
  echo "This script must be run by root user"
  exit 1
fi

if [ -f /src/ci ]; then
  IS_CI_BUILD=1
  FIRST_TIME_BUILD=$1
  workdir=/src
  logdir=/logs
  PBS_DIR=/pbspro
else
  PBS_DIR=$( readlink -f $0 | awk -F'/ci/' '{print $1}' )
fi

cd ${PBS_DIR}
. /etc/os-release
SPEC_FILE=${PBS_DIR}/pbspro.spec
REQ_FILE=${PBS_DIR}/test/fw/requirements.txt
if [ ! -r ${SPEC_FILE} -o ! -r ${REQ_FILE} ]; then
  echo "Couldn't find pbspro.spec or requirement.txt"
  exit 1
fi

if [ "x${IS_CI_BUILD}" != "x1" ] || [ "x${FIRST_TIME_BUILD}" == "x1" -a "x${IS_CI_BUILD}" == "x1" ]; then
  if [ "x${ID}" == "xcentos" ]; then
    yum clean all
    yum -y update
    yum -y install yum-utils epel-release rpmdevtools
    yum -y install python3-pip sudo which net-tools man-db time.x86_64 \
                    expat libedit postgresql-server postgresql-contrib python3 \
                    sendmail sudo tcl tk libical libasan llvm git
    rpmdev-setuptree
    yum-builddep -y ${SPEC_FILE}
    yum -y install $(rpmspec --requires -q ${SPEC_FILE} | awk '{print $1}'| sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    pip3 install -r ${REQ_FILE}
  elif [ "x${ID}" == "xopensuse" -o "x${ID}" == "xopensuse-leap" ]; then
    _PRETTY_NAME=$(echo ${PRETTY_NAME} | awk -F[=\"] '{print $1}')
    _PRETTY_NAME=${_PRETTY_NAME# }
    _PRETTY_NAME=${_PRETTY_NAME% }
    _PRETTY_NAME=${_PRETTY_NAME// /_}
    _base_link="http://download.opensuse.org/repositories"
    zypper -n ar -f -G ${_base_link}/devel:/tools/${_PRETTY_NAME}/devel:tools.repo
    zypper -n ar -f -G ${_base_link}/devel:/libraries:/c_c++/${_PRETTY_NAME}/devel:libraries:c_c++.repo
    zypper -n ref
    zypper -n update
    zypper -n install rpmdevtools python3-pip sudo which net-tools man time.x86_64 git
    rpmdev-setuptree
    zypper -n install --force-resolution $(rpmspec --buildrequires -q ${SPEC_FILE} | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    zypper -n install --force-resolution $(rpmspec --requires -q ${SPEC_FILE} | sort -u | grep -vE '^(/bin/)?(ba)?sh$')
    pip3 install -r ${REQ_FILE}
  elif [ "x${ID}" == "xdebian" ]; then
    if [ "x${DEBIAN_FRONTEND}" == "x" ]; then
      export DEBIAN_FRONTEND=noninteractive
    fi
    apt-get -y update
    apt-get -y upgrade
    apt-get install -y build-essential dpkg-dev autoconf libtool rpm alien libssl-dev \
                        libxt-dev libpq-dev libexpat1-dev libedit-dev libncurses5-dev \
                        libical-dev libhwloc-dev pkg-config tcl-dev tk-dev python3-dev \
                        swig expat postgresql postgresql-contrib python3-pip sudo man-db git
    pip3 install -r ${REQ_FILE}
  elif [ "x${ID}" == "xubuntu" ]; then
    if [ "x${DEBIAN_FRONTEND}" == "x" ]; then
      export DEBIAN_FRONTEND=noninteractive
    fi
    apt-get -y update
    apt-get -y upgrade
    apt-get install -y build-essential dpkg-dev autoconf libtool rpm alien libssl-dev \
                        libxt-dev libpq-dev libexpat1-dev libedit-dev libncurses5-dev \
                        libical-dev libhwloc-dev pkg-config tcl-dev tk-dev python3-dev \
                        swig expat postgresql python3-pip sudo man-db git
    pip3 install -r ${REQ_FILE}
  else
    echo "Unknown platform..."
    exit 1
  fi
fi

if [ "x${FIRST_TIME_BUILD}" == "x1" -a "x${IS_CI_BUILD}" == "x1" ]; then
  echo "### First time build is complete ###"
  exit 0
fi

if [ "x${ONLY_INSTALL_DEPS}" == "x1" ]; then
  exit 0
fi

_targetdirname=target-${ID}
if [ "x${ONLY_INSTALL}" != "x1" -a "x${ONLY_REBUILD}" != "x1" -a "x${ONLY_TEST}" != "x1" ]; then
  rm -rf ${_targetdirname}
fi
mkdir -p ${_targetdirname}
if [ "x${ONLY_REBUILD}" != "x1" -a "x${ONLY_INSTALL}" != "x1" -a "x${ONLY_TEST}" != "x1" ]; then
  [[ -f Makefile ]] && make distclean || true
  ./autogen.sh
  _cflags="-g -O2 -Wall -Werror"
  if [ "x${ID}" == "xubuntu" ]; then
    _cflags="${_cflags} -Wno-unused-result"
  fi
  cd ${_targetdirname}
  if [ -f /src/ci ];then
    if [ -f ${workdir}/.configure_opt ]; then
      configure_opt="$(cat ${workdir}/.configure_opt)"
      _cflags="$(echo ${configure_opt} | awk -F'"' '{print $2}')"
      configure_opt="$(echo ${configure_opt} | sed -e 's/CFLAGS=\".*\"//g')"
    else 
      configure_opt='--prefix=/opt/pbs --enable-ptl'
    fi
    ../configure CFLAGS="${_cflags}" ${configure_opt}
    if [ "x${ONLY_CONFIGURE}" == "x1" ];then
      exit 0
    fi
  else
    ../configure CFLAGS="${_cflags}" --prefix /opt/pbs --enable-ptl
  fi
  cd -
fi
cd ${_targetdirname}
prefix=$(cat ${workdir}/.configure_opt | awk -F'prefix=' '{print $2}' | awk -F' ' '{print $1}')
if [ "x${prefix}" == "x" ];then
  prefix='/opt/pbs'
fi
if [ "x${ONLY_INSTALL}" == "x1" -o "x${ONLY_TEST}" == "x1" ];then
  echo "skipping make"
else
  make -j8
fi
if [ "x$ONLY_REBUILD" == "x1" ];then
  exit 0
fi
if [ "x${ONLY_TEST}" != "x1" ];then
  make -j8 install
  chmod 4755 ${prefix}/sbin/pbs_iff ${prefix}/sbin/pbs_rcp
  if [ "x${DONT_START_PBS}" != "x1" ]; then
    ${prefix}/libexec/pbs_postinstall server
    sed -i "s@PBS_START_MOM=0@PBS_START_MOM=1@" /etc/pbs.conf
    /etc/init.d/pbs restart
  fi
fi

set +e
. /etc/profile.d/ptl.sh
set -e
pbs_config --make-ug

if [ "x${RUN_TESTS}" == "x1" ];then
  ptl_tests_dir=$(dirname ${prefix})/ptl/tests
  cd ${ptl_tests_dir}/
  benchpress_opt="$( cat ${workdir}/.benchpress_opt )"
  eval_tag="$(echo ${benchpress_opt} | awk -F'"' '{print $2}')"
  benchpress_opt="$(echo ${benchpress_opt} | sed -e 's/--eval-tags=\".*\"//g')"
  if [ -z "${eval_tag}" ];then
    pbs_benchpress ${benchpress_opt} --db-type=html --db-name=${logdir}/result.html -o ${logdir}/logfile
  else
    pbs_benchpress --eval-tags="'${eval_tag}'" ${benchpress_opt} --db-type=html --db-name=${logdir}/result.html -o ${logdir}/logfile
  fi
fi

if [ "x$IS_CI_BUILD" != "x1" ];then
  cd /opt/ptl/tests/
  pbs_benchpress --tags=smoke
fi