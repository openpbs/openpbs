Instant-CI is a developer tool which aims at providing continous integration to the developers locally on their development systems.
It runs a container which will be running in the background on the users system, the container will pick up on changes done by the user (via commits or manual triggers) and has the capability to build install and 
run PTL tests on the pbs of the users repository, for all this the user may not worry about underlying dependencies or any caveats.
It also supports build and test history in the form of logs.

Dependincies for this tool are:
* python3.5 or above
* docker
* docker-compose

***How to setup:***

Simply invoke the following command:

` ./ci --start`

***CLI interface for ci:***

* **./ci --start:** This will behave as the setup for ci containers to run in the background. User can provide desired platform, which must be present in docker hub. Currently supports ubuntu, centos and opensuse.
```bash
./ci --start
 
# The above command will run ci with centos:7 as it's base container.
 
./ci --start="ubuntu"
 
# This will run ci with container as "ubuntu", all docker hub images are compatible with ci.
 
./ci --start="opensuse/leap:15" --build
 
# The above command will force the container to rebuild all dependencies.
```

* **./ci --configure:** user can provide PBS configure options.

```bash
./ci --configure
  
# The above command will run the pbs configure with default options "--prefix=/opt/pbs --enable-ptl" .
# Note that if you have already specified the configure options and are running it again then 
# simply calling --configure will run the last called options
  
./ci --configure='CFLAGS=" -O2 -Wall -Werror" --prefix=/tmp/pbs --enable-ptl'
  
# The above command is an example of how to call a custom configure command.
```

* **./ci --make:** A command that will simply build PBS and PTL source code (not install).
```bash
./ci --make
 
# This will invoke 'make -j8' for pbs
```

* **./ci --install:** It installs pbs and ptl into the container. For this to run the source must be compiled, it will throw an error if this is not the case.
```bash
./ci --install
 
# This will invoke 'make install' for pbs
```

* **./ci --test:** This command will be used to run PTL test cases inside the container. By default it will run "smoke" tag for PTL, else the user can specify what pbs_benchpress options they need.
```bash
./ci --test
 
# With no options specified this will run "--tags=smoke" for ptl, however if you already 
# ran this command before it will run the last specified options
 
./ci --test="-f pbs_smoketest.py"
./ci --test="--tags=smoke"
 
# The above method are examples how to call a custom test case, 
# keep in mind that benchpress is called from the installed 'tests' dir of PTL
```
* **./ci --run:** This command will manually trigger the build for automatic run of 'build install and test', with last specified options for configure and test (default if no options were specified previously).

```bash
./ci --run
 
# This command will invoke configure(with default options), make, install and test. 
# With no options specified this will run "--tags=smoke" for ptl, 
# however if you have already ran this command before it will run the last specified options
 
./ci --run="-f pbs_smoketest.py"
./ci --run="--tags=smoke"
 
# The above method are examples how to call a custom test case, keep in mind that benchpress is called from the installed 'tests' dir of PTL
```

* **./ci --build-pkgs:** Invoke this command to build pbs packages. By default it will build packages for the platform ci container is started for.
Optionally accepts argument for other platform. The packages can be found in 'ci/packages' folder.

```bash
./ci --build-pkgs
# Above command builds package for the platform ci was started/currently running on.

./ci --build-pkgs='ubuntu:16.04'
# This will build package on ubuntu:16.04 platform, it will restart ci services and build for the specified platform 
```

* **./ci --delete:** which will stop any ongoing build in the container for the moment and remove it build.

```bash
./ci --delete
 
# If you want to get rid of the container simply invoke this command.
```

***The ci container if left running in the background automatically triggers new builds and tests on every new commit to the branch. This info is stored in the 'logs' folder.***
