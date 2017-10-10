# multi-stage build
# use pbsbase image as builder
# build script will be triggered
FROM pbspro/pbsbase:centos7 AS builder
# get latest PBS Pro source code
RUN git clone https://github.com/pbspro/pbspro.git /src/pbspro && \
    bash /src/pbspro/docker/centos7/build.sh

# base image 
FROM centos:7
LABEL maintainer="mliu@altair.com"
LABEL description="PBS Professional Open Source"
# copy rpm and entrypoint script from builder
COPY --from=builder /root/rpmbuild/RPMS/x86_64/pbspro-server-*.rpm .
COPY --from=builder /src/pbspro/docker/centos7/entrypoint.sh /
# install pbspro
RUN yum install -y pbspro-server-*.rpm
# run entrypoint script
ENTRYPOINT ["bash", "/entrypoint.sh"]
