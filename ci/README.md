Instant-CI is a developer tool which aims at providing continous integration to the developers locally on their development systems.
Users can build, install PBS and run PTL tests with a single command. For this, the user need not worry about any underlying dependencies.
It also supports build and test history in the form of logs.

Dependencies for this tool are:
* python3.5 or above
* docker (17.12.0+)
* docker-compose

***How to setup:***

Simply invoke the following command:

` ./ci`

***CLI interface for ci:***

* **./ci :** This is the primary command for ci. It starts the container (if not already running), builds pbs dependencies. Will configure(if required), make and install pbs. If the tests option are given it will run PTL with the same. It does not take any argument.
```bash
./ci
 ```

* **./ci --params:** The params option can be used run ci with a custom configuration.
Following parameters can be set.
| os | nodes | configure | tests |

```bash
# When the params command is called without any arguments it will display the currently set "configuration" and then proceed to run ci
# as the following example.
./ci --params
# or
./ci -p


# The following command is an example of how to define a custom configure option for pbs. Everything to the right of the first '=' after configure will
# be taken as it is and given as an argument to the configure file in pbs. The same convention follows for other configuration options as well
./ci --params 'configure=CFLAGS=" -O2 -Wall -Werror" --prefix=/tmp/pbs --enable-ptl'


# The following are examples how to define a custom test case for pbs_benchpress.
# NOTE: The string is passed to pbs_benchpress command therefore one can use all available options of pbs_benchpress here.
./ci --params 'tests=-f pbs_smoketest.py'
./ci --params 'tests=--tags=smoke'


# If you wish to not run any PTL tests then use the above command. This will set tests as empty thus not invoking PTL.
# By default the test option is set to '-t SmokeTest'
./ci --params 'tests='


# Below is an example of setting the container operating system. This will setup a single container running pbs server.
# NOTE: ci uses cached image to increase performance of dependecy build. These cached images are saved on the local system
#		with the suffix '_ci_pbs'. If you wish to use the base image delete any such images.
# OS platform can be defined by any image from docker-hub
./ci --params 'os=centos:7'


# Following is an example of how to define multi node setup for pbs.
# You can define multiple 'mom' or 'comm' nodes but only one 'server' node
./ci --params 'nodes=mom=centos:7;server=ubuntu:16.04;comm=ubuntu:18.04;mom=centos:8'

```


* **./ci --build-pkgs:** Invoke this command to build pbs packages. By default it will build packages for the platform ci container is started for.
Optionally accepts argument for other platform. The packages can be found in 'ci/packages' folder.

```bash
# Below command builds package for the platform ci was started/currently running on.
./ci --build-pkgs

```

* **./ci --delete:** will delete any running containers and take a backup of logs. Does not take any arguments. The current logs can be found in the "logs" folder in the ci folder. The backup logs can be found in session-{date}-{timestamp} format folder inside "logs" folder.

```bash
# If you want to get rid of the container simply invoke this command.
./ci --delete
```
