# base image
FROM centos:7
LABEL maintainer="mliu@altair.com"
LABEL description="PBS Professional Open Source"
# install dependencies for building
RUN yum install -y gcc make rpm-build libtool hwloc-devel libX11-devel libXt-devel libedit-devel libical-devel ncurses-devel perl postgresql-devel python-devel tcl-devel  tk-devel swig expat-devel openssl-devel libXext libXft
# install dependiencies for running
RUN yum install -y expat libedit postgresql-server python sendmail sudo tcl tk libical
# useful tools
RUN yum install -y git epel-release which net-tools
# install pip after epel
RUN yum install -y python-pip
# get latest pbspro code
WORKDIR /src
RUN git clone https://github.com/pbspro/pbspro.git
WORKDIR /src/pbspro
# build
RUN ./autogen.sh
RUN ./configure -prefix=/opt/pbs
RUN make
RUN make dist
# directories for rpm build must be ~/rpmbuild
RUN mkdir /root/rpmbuild
RUN mkdir /root/rpmbuild/SOURCES
RUN mkdir /root/rpmbuild/SPECS
RUN cp pbspro-*.tar.gz /root/rpmbuild/SOURCES
RUN cp pbspro.spec /root/rpmbuild/SPECS
# build rpms
WORKDIR /root/rpmbuild/SPECS
RUN rpmbuild -ba pbspro.spec
# install pbspro
WORKDIR /root/rpmbuild/RPMS/x86_64
RUN yum install -y pbspro-server-*.rpm
# cd to root dir
WORKDIR /
