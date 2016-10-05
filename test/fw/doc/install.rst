Installation
============

Prerequisite
------------
    - Python >= 2.6
    - `Pip`_ >= 8

Install
-------
To install package run following::

    pip install -r requirements.txt .

To install package in non-default location run following::

    pip install -r requirements.txt --prefix=/path/to/install/location .

If you install in non-default location then export `PYTHONPATH` variable before using PTL as follow::

    export PYTHONPATH=</path/to/install/location>/lib/python<python version>/site-packages

::

    </path/to/install/location/bin>/pbs_benchpress -h


Upgrade
-------

To upgrade package run following::

    pip install -U -r requirements.txt .

Uninstall
---------

To uninstall package run following::

    pip uninstall PbsTestLab

If you have installed in non-default location then export `PYTHONPATH` first before running uninstall command like::

    export PYTHONPATH=</path/to/install/location>/lib/python<python version>/site-packages
    pip uninstall PbsTestLab

.. _Pip: https://pip.pypa.io/en/stable
