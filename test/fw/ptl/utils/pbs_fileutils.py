# coding: utf-8

# Copyright (C) 1994-2018 Altair Engineering, Inc.
# For more information, contact Altair at www.altair.com.
#
# This file is part of the PBS Professional ("PBS Pro") software.
#
# Open Source License Information:
#
# PBS Pro is free software. You can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Commercial License Information:
#
# For a copy of the commercial license terms and conditions,
# go to: (http://www.pbspro.com/UserArea/agreement.html)
# or contact the Altair Legal Department.
#
# Altair’s dual-license business model allows companies, individuals, and
# organizations to create proprietary derivative works of PBS Pro and
# distribute them - whether embedded or bundled with other software -
# under a commercial license agreement.
#
# Use of Altair’s trademarks, including but not limited to "PBS™",
# "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
# trademark licensing policies.

FILE_HEAD = 'head'
FILE_TAIL = 'tail'


class FileUtils:

    """
    Utility to walk a file from ``'head'`` or ``'tail'`` on the local
    filesystem

    :param f: File to process
    :type f: str
    :param mode: One of FILE_HEAD or FILE_TAIL, which respectively set the
                 file for processing from head or tail. Defaults to head.
    """

    def __init__(self, f, mode=FILE_HEAD):
        self.filename = f
        self.fd = open(f, 'rb')
        self._buf_size = 1024
        self._fseek_ptr = 0
        self._lines_cache = []
        self.set_mode(mode)
        self.num_lines = None

    def get_file_descriptor(self):
        """
        Return the file descriptor associated to the file being processed
        """
        return self.fd

    def set_buf_size(self, bs=1024):
        """
        Set the buffer size to read blocks of file into
        """
        self._buf_size = bs

    def set_mode(self, m=None):
        """
        :param m: ``FILE_TAIL`` if file to be tailed, and ``FILE_HEAD`` to read
                  from head
        """
        if m == FILE_TAIL:
            self._backward = True
            self._bytes = self.get_size()
        else:
            self._backward = False
            self.fd.seek(0, 0)

    def tell(self):
        """
        :returns: The current file ``'cursor'``
        """
        return self.fd.tell()

    def get_size(self):
        """
        :returns: The size of the file
        """
        cur_pos = self.fd.tell()
        self.fd.seek(0, 2)
        size = self.fd.tell()
        self.fd.seek(cur_pos)
        return size

    def get_num_lines(self):
        """
        :returns: No of lines for the file
        """
        if self.num_lines is not None:
            return self.num_lines
        _c = self.fd.tell()
        self.num_lines = sum(1 for _ in self.fd)
        self.fd.seek(_c)
        return self.num_lines

    def next(self, n=1):
        """
        Get the next n lines of the file

        :param n: the numer of lines to retrieve
        :type n: int
        """
        if self._backward:
            return self.tail(n)
        else:
            return self.head(n)

    def get_line(self, n=1):
        """
        :returns: The nth line from file
        """
        self.fd.seek(0, 0)
        i = 0
        while i != (n - 1):
            try:
                self.fd.readline()
            except:
                return None
            i += 1
        return self.fd.readline()

    def get_block(self, from_n=1, to_n=1):
        """
        :returns: A block of lines between ``from_n`` and ``to_n``
        """
        if to_n < from_n:
            return None

        self.fd.seek(0, 0)
        i = 0
        block = []
        while i != (from_n - 1):
            try:
                self.fd.readline()
                i += 1
            except:
                return None

        while i != to_n:
            try:
                block.append(self.fd.readline())
                i += 1
            except:
                del block
                return None
        return block

    def next_head(self, n=1):
        """
        Next line(s) from head
        """
        return self.head(n)

    def next_tail(self, n=1):
        """
        Next line(s) from tail
        """
        if not self._backward:
            self.set_mode(FILE_TAIL)
        return self.tail(n)

    def head(self, n=1):
        """
        :returns: n lines of head
        """
        head_lines = []
        i = 0
        while i != n:
            line = self.fd.readline()
            if line == '':
                break
            head_lines.append(line.strip())
            i += 1
        return head_lines

    def tail(self, n=1):
        """
        :returns: n lines of tail
        """
        if not self._backward:
            self.set_mode(FILE_TAIL)

        ret = []
        n_read = n
        # Retrieve as many lines from the cache as available and as requested
        while len(self._lines_cache) > 0 and n_read > 0:
            ret.append(self._lines_cache.pop())
            n_read -= 1
        if n_read == 0:
            return ret

        # searching backwards, the line may be truncated too early, to avoid
        # returning an incomplete line we look for an additional line and will
        # not return that possibly truncated line as part of our result
        size = n + 1

        data = []
        while size > 0 and self._bytes > 0:
            if (self._bytes - self._buf_size > 0):
                self._fseek_ptr -= self._buf_size
                self.fd.seek(self._fseek_ptr, 2)
                data.append(self.fd.read(self._buf_size))
            else:
                # file too small, start from beginning
                self.fd.seek(0, 0)
                # only read what was not read
                data.append(self.fd.read(self._bytes))
            linesFound = data[-1].count('\n')
            size -= linesFound
            self._bytes -= self._buf_size
        data.reverse()

        tmp_ret = ''.join(data).splitlines()
        if len(tmp_ret) > 0:
            # If we have reached the beginning of the file, we need to
            # include the first line rather than bypass it
            if self._bytes <= 0:
                first_idx = 0
            else:
                first_idx = 1
            self._lines_cache = tmp_ret[first_idx:] + self._lines_cache
            # account for the possibly truncated first line. We will only
            # read back buf_size from that index
            self._fseek_ptr += len(tmp_ret[0])

            # adjust the number of bytes actually read
            self._bytes += len(tmp_ret[0])

            # if the number of lines requested is greater than what is 'there'
            # reset the total number of lines requested to what is available
            if self._bytes <= 0 and len(self._lines_cache) < n_read:
                n_read = len(self._lines_cache)

        while len(self._lines_cache) > 0 and n_read > 0:
            ret.append(self._lines_cache.pop())
            n_read -= 1
        if n_read == 0:
            return ret
