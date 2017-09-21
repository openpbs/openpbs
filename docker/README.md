# Maintaining PBS Pro Dockerfiles

## Prerequisite
Readers should know how to write Dockerfiles using multi-stage builds. Please refer to the following sources:
1. [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)
2. [Best practices for writing Dockerfile](https://docs.docker.com/engine/userguide/eng-image/dockerfile_best-practices/)
3. [Use multi-stage builds](https://docs.docker.com/engine/reference/builder/)

## Directory Structure
Each directory corresponds to a supported Linux distribution. For example, Dockerfiles for building an image based on CentOS version 7 are under the `centos7` directory. Each directory contains at least three files, a `Dockerfile.base`, a `Dockerfile.build` and `build.sh`. Please adhere to this structure when you create Dockerfiles for a new distribution.

### `Dockerfile.base`
This file defines the base image that will be used to build PBS Pro. It must be based on an official Linux image and have the necessary packages for building PBS Pro installed. It should copy the corresponding `build.sh` to `/` and contain the `ONBUILD RUN bash /build.sh` directive to trigger the PBS Pro build.

### `Dockerfile.build`
This file defines the final PBS Pro image that will be put on Docker Hub. It should have two `FROM` commands, one for the builder and one for an official Linux image. It should use the image defined by `Dockerfile.base` as a builder, copy the produced RPMs from the builder, and install them.

### `build.sh`
This is a shell script that builds PBS Pro. It should be copied into the builder and triggered when the builder is used as a base image.

When in doubt, please use the `centos7` files as references.

## Style Guidelines
1. Add meaningful comments.
2. Avoid using deprecated features of Docker. For example, use `LABEL maintainer` instead of the `MAINTAINER` directive.
