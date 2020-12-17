# coding: utf-8

# Copyright (C) 1994-2020 Altair Engineering, Inc.
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


class PtlException(Exception):

    """
    Generic errors raised by PTL operations.
    Sets a ``return value``, a ``return code``, and a ``message``
    A post function and associated positional and named arguments
    are available to perform any necessary cleanup.

    :param rv: Return value set for the error occured during PTL
               operation
    :type rv: int or None.
    :param rc: Return code set for the error occured during PTL
               operation
    :type rc: int or None.
    :param msg: Message set for the error occured during PTL operation
    :type msg: str or None.
    :param post: Execute given post callable function if not None.
    :type post: callable or None.
    :raises: PTL exceptions
    """

    def __init__(self, rv=None, rc=None, msg=None, post=None, *args, **kwargs):
        self.rv = rv
        self.rc = rc
        self.msg = msg
        if post is not None:
            post(*args, **kwargs)

    def __str__(self):
        return ('rc=' + str(self.rc) + ', rv=' + str(self.rv) +
                ', msg=' + str(self.msg))

    def __repr__(self):
        return (self.__class__.__name__ + '(rc=' + str(self.rc) + ', rv=' +
                str(self.rv) + ', msg=' + str(self.msg) + ')')


class PtlFailureException(AssertionError):

    """
    Generic failure exception raised by PTL operations.
    Sets a ``return value``, a ``return code``, and a ``message``
    A post function and associated positional and named arguments
    are available to perform any necessary cleanup.

    :param rv: Return value set for the failure occured during PTL
               operation
    :type rv: int or None.
    :param rc: Return code set for the failure occured during PTL
               operation
    :type rc: int or None.
    :param msg: Message set for the failure occured during PTL operation
    :type msg: str or None.
    :param post: Execute given post callable function if not None.
    :type post: callable or None.
    :raises: PTL exceptions
    """

    def __init__(self, rv=None, rc=None, msg=None, post=None, *args, **kwargs):
        self.rv = rv
        self.rc = rc
        self.msg = msg
        if post is not None:
            post(*args, **kwargs)

    def __str__(self):
        return ('rc=' + str(self.rc) + ', rv=' + str(self.rv) +
                ', msg=' + str(self.msg))

    def __repr__(self):
        return (self.__class__.__name__ + '(rc=' + str(self.rc) + ', rv=' +
                str(self.rv) + ', msg=' + str(self.msg) + ')')


class PbsServiceError(PtlException):
    pass


class PbsConnectError(PtlException):
    pass


class PbsStatusError(PtlException):
    pass


class PbsSubmitError(PtlException):
    pass


class PbsManagerError(PtlException):
    pass


class PbsDeljobError(PtlException):
    pass


class PbsDelresvError(PtlException):
    pass


class PbsDeleteError(PtlException):
    pass


class PbsRunError(PtlException):
    pass


class PbsSignalError(PtlException):
    pass


class PbsMessageError(PtlException):
    pass


class PbsHoldError(PtlException):
    pass


class PbsReleaseError(PtlException):
    pass


class PbsOrderError(PtlException):
    pass


class PbsRerunError(PtlException):
    pass


class PbsMoveError(PtlException):
    pass


class PbsAlterError(PtlException):
    pass


class PbsResourceError(PtlException):
    pass


class PbsSelectError(PtlException):
    pass


class PbsSchedConfigError(PtlException):
    pass


class PbsMomConfigError(PtlException):
    pass


class PbsFairshareError(PtlException):
    pass


class PbsQdisableError(PtlException):
    pass


class PbsQenableError(PtlException):
    pass


class PbsQstartError(PtlException):
    pass


class PbsQstopError(PtlException):
    pass


class PtlExpectError(PtlFailureException):
    pass


class PbsInitServicesError(PtlException):
    pass


class PbsQtermError(PtlException):
    pass


class PtlLogMatchError(PtlFailureException):
    pass


class PbsResvAlterError(PtlException):
    pass
