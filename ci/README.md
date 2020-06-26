Instant-CI is a developer tool which aims at providing continous integration to the developers locally on their development systems.
Users can build and install pbs and run PTL tests with a single command on the pbs of the users repository, for all this the user may not worry about underlying dependencies or any caveats.
It also supports build and test history in the form of logs.

Dependincies for this tool are:
* python3.5 or above
* docker
* docker-compose

***How to setup:***

Simply invoke the following command:

` ./ci --run`

***CLI interface for ci:***

* **./ci --run:** This is the primary command for ci. It starts the container (if not already running), builds pbs dependencies. Will configure(if required), make and install pbs. If the tests option are given it will run PTL with the same. It does not take any argument.
```bash
./ci --run
 ```

* **./ci --set:** This option will be used to set ci configurations. The following options can be set via this command.
| OS | nodes | configure | tests | It will take a single string argument.

```bash
./ci --set

# When the set command is called without any arguments it will display the currently set options.


./ci --set 'configure=CFLAGS=" -O2 -Wall -Werror" --prefix=/tmp/pbs --enable-ptl'

# The above command is an example of how to define a custom configure option for pbs.

./ci --set 'tests=-f pbs_smoketest.py'
./ci --set 'tests=--tags=smoke'

# The above method are examples how to define a custom test case for pbs_benchpress.
# NOTE: The string is passed to pbs_benchpress command therefore one can use all available options of pbs_benchpress here.

./ci --set 'tests='
# If you wish to not run any PTL tests then use the above command. This will set tests as empty thus not invoking PTL.

./ci --set 'os=centos:7'
# This is an example of setting the container operating system. This will setup a single container running pbs server.
# NOTE: ci uses cached image to increase performance of dependecy build. These cached images are saved on the local system
#		with the suffix '_ci_pbs'. If you wish to use the base image delete any such images.
# OS platform can be defined by any image from docker-hub

./ci --set 'nodes=nodes=mom=centos:7;server=ubuntu:16.04;comm=ubuntu:18.04'
# This is an example of how to define multi node setup for pbs.
# You can define multiple 'mom' or 'comm' nodes but only one 'server' node

```


* **./ci --build-pkgs:** Invoke this command to build pbs packages. By default it will build packages for the platform ci container is started for.
Optionally accepts argument for other platform. The packages can be found in 'ci/packages' folder.

```bash
./ci --build-pkgs
# Above command builds package for the platform ci was started/currently running on.

./ci --build-pkgs='ubuntu:16.04'
# This will build package on ubuntu:16.04 platform, it will restart ci services and build for the specified platform
```

* **./ci --delete:** will delete any running containers and take a backup of logs. Does not take any arguments.

```bash
./ci --delete

# If you want to get rid of the container simply invoke this command.
```
