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

* **./ci :** This is the primary command for ci. It starts the container (if not already running), builds PBS dependencies. Will configure(if required), make and install PBS. If the tests option are given it will run PTL with the same. It does not take any argument.
```bash
./ci
 ```

* **./ci --params:** The params option can be used to run ci with a custom configuration.
Following parameters can be set.
| os | nodes | configure | tests |
> os: used to set OS platform of the container (single node) <br>
> nodes: used to define multi-node configuration for container <br>
> configure: will hold the value of configure options for PBS <br>
> tests: will hold the value for pbs_benchpress argument for PTL; if set empty will skip PTL tests <br>

```bash
# When the params command is called without any arguments it will display the currently set "configuration" and then proceed to run ci
# as the following example.
./ci --params
# or
./ci -p


# The following command is an example of how to provide a custom configure option for PBS. Everything to the right of the first '=' after configure will
# be taken as it is and given as an argument to the configure file in PBS. The same convention follows for other configuration options as well
./ci --params 'configure=CFLAGS=" -O2 -Wall -Werror" --prefix=/tmp/pbs --enable-ptl'

# You can also pass multiple parameter with this option for example
./ci -p 'configure=--enable-ptl --prefix=/opt/pbs' -p 'tests=-t SmokeTest.test_basic'


# The following are examples how to define a custom test case for pbs_benchpress.
# NOTE: The string is passed to pbs_benchpress command therefore one can use all available options of pbs_benchpress here.
# By default the test option is set to '-t SmokeTest'
./ci --params 'tests=-f pbs_smoketest.py'
./ci --params 'tests=--tags=smoke'


# If you wish to not run any PTL tests then use the below command. This will set tests as empty thus not invoking PTL.
./ci --params 'tests='


# Below is an example of setting the container operating system. This will setup a single container running PBS server.
# NOTE: ci uses cached image to increase performance. These cached images are saved on the local system
#		with the suffix '-ci-pbs'. If you do not wish to use the cached image(s) delete them using <docker rmi {image_name}>.
# OS platform can be defined by any image from docker-hub
./ci --params 'os=centos:7'


# Following is an example of how to define multi node setup for PBS.
# You can define multiple 'mom' or 'comm' nodes but only one 'server' node
./ci --params 'nodes=mom=centos:7;server=ubuntu:16.04;comm=ubuntu:18.04;mom=centos:8'

```


* **./ci --build-pkgs:** Invoke this command to build PBS packages. By default it will build packages for the platform ci container is started for.
Optionally accepts argument for other platform. The packages can be found in 'ci/packages' folder.

```bash
# Below command builds package for the platform ci was started/currently running on.
./ci --build-pkgs
# or
./ci -b

```

* **./ci --delete:** This will delete any containers created by this tool and take a backup of logs. The current logs can be found in the "logs" folder in the ci folder. The backup of previous sessions logs can be can be found in the ci/logs/session-{date}-{timestamp} folder.

```bash
# If you want to delete the container simply invoke this command.
./ci --delete
# or
./ci -d
```

* **./ci --local:** This will build, install PBS, and run smoke tests on the local machine. This option can not be combined with other options. It does not take configurations from params but runs with predefined params(as run in travis).
```bash
# The command to run
./ci --local
#or
./ci -l

# Optionally one can run the sanitize version (works only on centos:7) with the following argument
./ci --local sanitize
```
