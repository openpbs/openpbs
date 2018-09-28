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

import os
import ptl
import sys
import pwd
import logging
import platform
import traceback
import time
import json
import ptl.utils.pbs_logutils as lu
from ptl.lib.pbs_testlib import PbsTypeDuration
from ptl.utils.plugins.ptl_test_tags import TAGKEY
from ptl.utils.pbs_dshutils import DshUtils
from ptl.utils.plugins.ptl_report_json import PTLJsonData

# Following dance require because PTLTestDb().process_output() from this file
# is used in pbs_loganalyzer script which is shipped with PBS package
# through unsupported directory where we might not have nose installed
try:
    from nose.util import isclass
    from nose.plugins.base import Plugin
    from nose.plugins.skip import SkipTest
    from ptl.utils.plugins.ptl_test_runner import TimeOut
    log = logging.getLogger('nose.plugins.PTLTestDb')
except ImportError:
    class Plugin(object):
        pass

    def isclass(obj):
        pass

    class SkipTest(Exception):
        pass

    class TimeOut(Exception):
        pass
    log = logging.getLogger('PTLTestDb')

# Table names
_DBVER_TN = 'ptl_db_version'
_TESTRESULT_TN = 'ptl_test_results'
_SCHEDM_TN = 'ptl_scheduler_metrics'
_SVRM_TN = 'ptl_server_metrics'
_MOMM_TN = 'ptl_mom_metrics'
_ACCTM_TN = 'ptl_accounting_metrics'
_PROCM_TN = 'ptl_proc_metrics'
_CYCLEM_TN = 'ptl_cycle_metrics'
_ESTINFOSUM_TN = 'ptl_estimated_info_summary'
_ESTINFO_TN = 'ptl_estimated_info'
_JOBM_TN = 'ptl_job_metrics'


class PTLDbError(Exception):

    """
    PTL database error class

    :param rv: Return value for the database error
    :type rv: str or None
    :param rc: Return code for the database error
    :type rc: str or None
    :param msg: Error message
    :type msg: str or None
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


class DBType(object):

    """
    Base class for each database type
    Any type of database must inherit from me

    :param dbtype: Database type
    :type dbtype: str
    :param dbpath: Path to database
    :type dbpath: str
    :param dbaccess: Path to a file that defines db options
    :type dbaccess: str
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        if dbpath is None:
            dn = _TESTRESULT_TN + '.db'
            dbdir = os.getcwd()
            dbpath = os.path.join(dbdir, dn)
        elif os.path.isdir(dbpath):
            dn = _TESTRESULT_TN + '.db'
            dbdir = dbpath
            dbpath = os.path.join(dbdir, dn)
        else:
            dbdir = os.path.dirname(dbpath)
            dbpath = dbpath
        self.dbtype = dbtype
        self.dbpath = dbpath
        self.dbdir = dbdir
        self.dbaccess = dbaccess

    def write(self, data, logfile=None):
        """
        :param data: Data to write
        :param logfile: Can be one of ``server``, ``scheduler``, ``mom``,
                        ``accounting`` or ``procs``
        :type logfile: str or None
        """
        _msg = 'write method must be implemented in'
        _msg += ' %s' % (str(self.__class__.__name__))
        raise PTLDbError(rc=1, rv=False, msg=_msg)

    def close(self, result=None):
        """
        Close the database
        """
        _msg = 'close method must be implemented in'
        _msg += ' %s' % (str(self.__class__.__name__))
        raise PTLDbError(rc=1, rv=False, msg=_msg)


class PostgreSQLDb(DBType):

    """
    PostgreSQL type database
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        DBType.__init__(self, dbtype, dbpath, dbaccess)
        if self.dbtype != 'pgsql':
            _msg = 'db type does not match with my type(file)'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        if self.dbaccess is None:
            _msg = 'Db access creds require!'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        try:
            import psycopg2
        except:
            _msg = 'psycopg2 require for %s type database!' % (self.dbtype)
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        try:
            f = open(self.dbaccess)
            creds = ' '.join(map(lambda n: n.strip(), f.readlines()))
            f.close()
            self.__dbobj = psycopg2.connect(creds)
        except Exception, e:
            _msg = 'Failed to connect to database:\n%s\n' % (str(e))
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        self.__username = pwd.getpwuid(os.getuid())[0]
        self.__platform = ' '.join(platform.uname()).strip()
        self.__ptlversion = str(ptl.__version__)
        self.__db_version = '1.0.0'
        self.__index = self.__create_tables()

    def __get_index(self, c):
        idxs = []
        stmt = 'SELECT max(id) from %s;' % (_TESTRESULT_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_SCHEDM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_SVRM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_MOMM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ACCTM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_PROCM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_CYCLEM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ESTINFOSUM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ESTINFO_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_JOBM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        idx = max(idxs)
        if idx is not None:
            return idx
        else:
            return 1

    def __upgrade_db(self, version):
        if version == self.__db_version:
            return

    def __create_tables(self):
        c = self.__dbobj.cursor()

        try:
            stmt = ['CREATE TABLE %s (' % (_DBVER_TN)]
            stmt += ['version TEXT);']
            c.execute(''.join(stmt))
        except:
            stmt = 'SELECT version from %s;' % (_DBVER_TN)
            version = c.execute(stmt).fetchone()[0]
            self.__upgrade_db(version)
            return self.__get_index(c)
        stmt = ['INSERT INTO %s (version)' % (_DBVER_TN)]
        stmt += [' VALUES (%s);' % (self.__db_version)]
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_TESTRESULT_TN)]
        stmt += ['id INTEGER,']
        stmt += ['suite TEXT,']
        stmt += ['testcase TEXT,']
        stmt += ['testdoc TEXT,']
        stmt += ['start_time TEXT,']
        stmt += ['end_time TEXT,']
        stmt += ['duration TEXT,']
        stmt += ['pbs_version TEXT,']
        stmt += ['testparam TEXT,']
        stmt += ['username TEXT,']
        stmt += ['ptl_version TEXT,']
        stmt += ['platform TEXT,']
        stmt += ['status TEXT,']
        stmt += ['status_data TEXT,']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_SCHEDM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NC + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJC + ' INTEGER,']
        stmt += [lu.NJFR + ' INTEGER,']
        stmt += [lu.mCD + '  TIME,']
        stmt += [lu.CD25 + ' TIME,']
        stmt += [lu.CDA + ' TIME,']
        stmt += [lu.CD50 + ' TIME,']
        stmt += [lu.CD75 + ' TIME,']
        stmt += [lu.MCD + ' TIME,']
        stmt += [lu.mCT + ' TIMESTAMP,']
        stmt += [lu.MCT + ' TIMESTAMP,']
        stmt += [lu.TTC + ' TIME,']
        stmt += [lu.DUR + ' TIME,']
        stmt += [lu.SST + ' TIME,']
        stmt += [lu.JRR + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_SVRM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JSR + ' TEXT,']
        stmt += [lu.NUR + ' TEXT,']
        stmt += [lu.JWTm + ' TIME,']
        stmt += [lu.JWT25 + ' TIME,']
        stmt += [lu.JWT50 + ' TIME,']
        stmt += [lu.JWTA + ' TIME,']
        stmt += [lu.JWT75 + ' TIME,']
        stmt += [lu.JWTM + ' TIME,']
        stmt += [lu.JRTm + ' TIME,']
        stmt += [lu.JRT25 + ' TIME,']
        stmt += [lu.JRTA + ' TIME,']
        stmt += [lu.JRT50 + ' TIME,']
        stmt += [lu.JRT75 + ' TIME,']
        stmt += [lu.JRTM + ' TIME);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_MOMM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JSR + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ACCTM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.DUR + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JSR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JWTm + ' TIME,']
        stmt += [lu.JWT25 + ' TIME,']
        stmt += [lu.JWT50 + ' TIME,']
        stmt += [lu.JWTA + ' TIME,']
        stmt += [lu.JWT75 + ' TIME,']
        stmt += [lu.JWTM + ' TIME,']
        stmt += [lu.JRTm + ' TIME,']
        stmt += [lu.JRT25 + ' TIME,']
        stmt += [lu.JRTA + ' TIME,']
        stmt += [lu.JRT50 + ' TIME,']
        stmt += [lu.JRT75 + ' TIME,']
        stmt += [lu.JRTM + ' TIME,']
        stmt += [lu.JNSm + ' INTEGER,']
        stmt += [lu.JNS25 + ' REAL,']
        stmt += [lu.JNSA + ' REAL,']
        stmt += [lu.JNS50 + ' REAL,']
        stmt += [lu.JNS75 + ' REAL,']
        stmt += [lu.JNSM + ' REAL,']
        stmt += [lu.JCSm + ' INTEGER,']
        stmt += [lu.JCS25 + ' REAL,']
        stmt += [lu.JCSA + ' REAL,']
        stmt += [lu.JCS50 + ' REAL,']
        stmt += [lu.JCS75 + ' REAL,']
        stmt += [lu.JCSM + ' REAL,']
        stmt += [lu.CPH + ' INTEGER,']
        stmt += [lu.NPH + ' INTEGER,']
        stmt += [lu.UNCPUS + ' TEXT,']
        stmt += [lu.UNODES + ' TEXT,']
        stmt += [lu.USRS + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_PROCM_TN)]
        stmt += ['id INTEGER, ']
        stmt += ['name TEXT,']
        stmt += ['rss INTEGER,']
        stmt += ['vsz INTEGER,']
        stmt += ['pcpu TEXT,']
        stmt += ['time TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_CYCLEM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.CST + ' TIMESTAMP,']
        stmt += [lu.CD + ' TIME,']
        stmt += [lu.QD + ' TIME,']
        stmt += [lu.NJC + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJFR + ' INTEGER,']
        stmt += [lu.NJCAL + ' INTEGER,']
        stmt += [lu.NJFP + ' INTEGER,']
        stmt += [lu.NJP + ' INTEGER,']
        stmt += [lu.TTC + ' INTEGER,']
        stmt += [lu.SST + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ESTINFOSUM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.NJD + ' INTEGER,']
        stmt += [lu.NJND + ' INTEGER,']
        stmt += [lu.Ds15mn + ' INTEGER,']
        stmt += [lu.Ds1hr + ' INTEGER,']
        stmt += [lu.Ds3hr + ' INTEGER,']
        stmt += [lu.Do3hr + ' INTEGER,']
        stmt += [lu.DDm + ' INTEGER,']
        stmt += [lu.DDM + ' INTEGER,']
        stmt += [lu.DDA + ' INTEGER,']
        stmt += [lu.DD50 + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ESTINFO_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.JID + ' TEXT,']
        stmt += [lu.Eat + ' INTEGER,']
        stmt += [lu.JST + ' INTEGER,']
        stmt += [lu.ESTR + ' INTEGER,']
        stmt += [lu.ESTA + ' INTEGER,']
        stmt += [lu.NEST + ' INTEGER,']
        stmt += [lu.ND + ' INTEGER,']
        stmt += [lu.JDD + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_JOBM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.CST + ' TIMESTAMP,']
        stmt += [lu.JID + ' TEXT,']
        stmt += [lu.T2R + ' INTEGER,']
        stmt += [lu.T2D + ' INTEGER,']
        stmt += [lu.TiS + ' INTEGER,']
        stmt += [lu.TTC + ' INTEGER);']
        c.execute(''.join(stmt))
        self.__dbobj.commit()
        return self.__get_index(c)

    def __write_data(self, tablename, data, logfile):
        keys = ['id']
        values = [str(self.__index)]
        if logfile is not None:
            keys.append('logname')
            values.append('\'' + str(logfile).replace(' ', '_') + '\'')
        for k, v in data.items():
            if k == 'id':
                continue
            keys.append(str(k))
            v = str(v)
            if v.isdigit():
                values.append(v)
            else:
                values.append('\'' + v + '\'')
        _keys = ','.join(keys)
        _values = ','.join(values)
        c = self.__dbobj.cursor()
        s = 'INSERT INTO %s (%s) VALUES (%s)' % (tablename, _keys, _values)
        c.execute(s)
        self.__dbobj.commit()

    def __write_server_data(self, data, logfile=None):
        self.__write_data(_SVRM_TN, data, logfile)

    def __write_mom_data(self, data, logfile=None):
        self.__write_data(_MOMM_TN, data, logfile)

    def __write_sched_data(self, data, logfile=None):
        for k, v in data.items():
            if k == 'summary':
                self.__write_data(_SCHEDM_TN, data, logfile)
                continue
            elif k == lu.EST:
                if lu.ESTS in v:
                    self.__write_estinfosum_data(v[lu.ESTS], logfile)
                if lu.EJ in v:
                    for j in v[lu.EJ]:
                        if lu.EST in j:
                            dt = map(lambda s: str(s), j[lu.Eat])
                            j[lu.Eat] = ','.join(dt)
                        self.__write_estsum_data(j, logfile)
                continue
            if 'jobs' in v:
                for j in v['jobs']:
                    j[lu.CST] = v[lu.CST]
                    self.__write_job_data(j, logfile)
                del v['jobs']
            self.__write_cycle_data(v, logfile)

    def __write_acct_data(self, data, logfile=None):
        self.__write_data(_ACCTM_TN, data, logfile)

    def __write_proc_data(self, data, logfile=None):
        self.__write_data(_PROCM_TN, data, None)

    def __write_cycle_data(self, data, logfile=None):
        self.__write_data(_CYCLEM_TN, data, logfile)

    def __write_estsum_data(self, data, logfile=None):
        self.__write_data(_ESTINFOSUM_TN, data, logfile)

    def __write_estinfosum_data(self, data, logfile=None):
        self.__write_data(_ESTINFO_TN, data, logfile)

    def __write_job_data(self, data, logfile=None):
        self.__write_data(_JOBM_TN, data, logfile)

    def __write_test_data(self, data):
        keys = ['id']
        values = [str(self.__index)]
        keys.append('suite')
        values.append(str(data['suite']))
        keys.append('testcase')
        values.append(str(data['testcase']))
        doc = []
        for l in str(data['testdoc']).strip().split('\n'):
            doc.append(l.strip().replace('\t', ' ').replace('\'', '\'\''))
        doc = ' '.join(doc)
        keys.append('testdoc')
        values.append('\'' + doc + '\'')
        keys.append('start_time')
        values.append(str(data['start_time']))
        keys.append('end_time')
        values.append(str(data['end_time']))
        keys.append('duration')
        values.append(str(data['duration']))
        keys.append('pbs_version')
        values.append(str(data['pbs_version']))
        keys.append('testparam')
        values.append(str(data['testparam']))
        keys.append('username')
        values.append(str(self.__username))
        keys.append('platform')
        values.append(str(self.__platform))
        keys.append('status')
        values.append(str(data['status']))
        sdata = data['status_data']
        sdata = sdata.replace('\'', '\'\'')
        keys.append('status_data')
        values.append('\'' + sdata + '\'')
        _keys = ','.join(keys)
        _values = ','.join(values)
        c = self.__dbobj.cursor()
        s = 'INSERT INTO %s (%s) VALUES (%s)' % (
            _TESTRESULT_TN, _keys, _values)
        c.execute(s)
        self.__dbobj.commit()

    def write(self, data, logfile=None):
        if len(data) == 0:
            return
        if 'testdata' in data.keys():
            self.__write_test_data(data['testdata'])
        if 'metrics_data' in data.keys():
            md = data['metrics_data']
            if 'server' in md.keys():
                self.__write_server_data(md['server'], logfile)
            if 'mom' in md.keys():
                self.__write_mom_data(md['mom'], logfile)
            if 'scheduler' in md.keys():
                self.__write_sched_data(md['scheduler'], logfile)
            if 'accounting' in md.keys():
                self.__write_acct_data(md['accounting'], logfile)
            if 'procs' in md.keys():
                self.__write_proc_data(md['procs'], logfile)
        self.__index += 1

    def close(self, result=None):
        self.__dbobj.commit()
        self.__dbobj.close()
        del self.__dbobj


class SQLiteDb(DBType):

    """
    SQLite type database
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        DBType.__init__(self, dbtype, dbpath, dbaccess)
        if self.dbtype != 'sqlite':
            _msg = 'db type does not match with my type(file)'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        if self.dbpath is None:
            _msg = 'Db path require!'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        try:
            import sqlite3 as db
        except:
            try:
                from pysqlite2 import dbapi2 as db
            except:
                _msg = 'Either sqlite3 or pysqlite2 module require'
                _msg += ' for %s type database!' % (self.dbtype)
                raise PTLDbError(rc=1, rv=False, msg=_msg)
        try:
            self.__dbobj = db.connect(self.dbpath)
        except Exception, e:
            _msg = 'Failed to connect to database:\n%s\n' % (str(e))
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        self.__username = pwd.getpwuid(os.getuid())[0]
        self.__platform = ' '.join(platform.uname()).strip()
        self.__ptlversion = str(ptl.__version__)
        self.__db_version = '1.0.0'
        self.__index = self.__create_tables()

    def __get_index(self, c):
        idxs = []
        stmt = 'SELECT max(id) from %s;' % (_TESTRESULT_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_SCHEDM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_SVRM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_MOMM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ACCTM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_PROCM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_CYCLEM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ESTINFOSUM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_ESTINFO_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        stmt = 'SELECT max(id) from %s;' % (_JOBM_TN)
        idxs.append(c.execute(stmt).fetchone()[0])
        idx = max(idxs)
        if idx is not None:
            return idx
        else:
            return 1

    def __upgrade_db(self, version):
        if version == self.__db_version:
            return

    def __create_tables(self):
        c = self.__dbobj.cursor()

        try:
            stmt = ['CREATE TABLE %s (' % (_DBVER_TN)]
            stmt += ['version TEXT);']
            c.execute(''.join(stmt))
        except:
            stmt = 'SELECT version from %s;' % (_DBVER_TN)
            version = c.execute(stmt).fetchone()[0]
            self.__upgrade_db(version)
            return self.__get_index(c)
        stmt = ['INSERT INTO %s (version)' % (_DBVER_TN)]
        stmt += [' VALUES (%s);' % (self.__db_version)]
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_TESTRESULT_TN)]
        stmt += ['id INTEGER,']
        stmt += ['suite TEXT,']
        stmt += ['testcase TEXT,']
        stmt += ['testdoc TEXT,']
        stmt += ['start_time TEXT,']
        stmt += ['end_time TEXT,']
        stmt += ['duration TEXT,']
        stmt += ['pbs_version TEXT,']
        stmt += ['testparam TEXT,']
        stmt += ['username TEXT,']
        stmt += ['ptl_version TEXT,']
        stmt += ['platform TEXT,']
        stmt += ['status TEXT,']
        stmt += ['status_data TEXT,']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_SCHEDM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NC + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJC + ' INTEGER,']
        stmt += [lu.NJFR + ' INTEGER,']
        stmt += [lu.mCD + '  TIME,']
        stmt += [lu.CD25 + ' TIME,']
        stmt += [lu.CDA + ' TIME,']
        stmt += [lu.CD50 + ' TIME,']
        stmt += [lu.CD75 + ' TIME,']
        stmt += [lu.MCD + ' TIME,']
        stmt += [lu.mCT + ' INTEGER,']
        stmt += [lu.MCT + ' INTEGER,']
        stmt += [lu.TTC + ' TIME,']
        stmt += [lu.DUR + ' TIME,']
        stmt += [lu.SST + ' TIME,']
        stmt += [lu.JRR + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_SVRM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JSR + ' TEXT,']
        stmt += [lu.NUR + ' TEXT,']
        stmt += [lu.JWTm + ' TIME,']
        stmt += [lu.JWT25 + ' TIME,']
        stmt += [lu.JWT50 + ' TIME,']
        stmt += [lu.JWTA + ' TIME,']
        stmt += [lu.JWT75 + ' TIME,']
        stmt += [lu.JWTM + ' TIME,']
        stmt += [lu.JRTm + ' TIME,']
        stmt += [lu.JRT25 + ' TIME,']
        stmt += [lu.JRTA + ' TIME,']
        stmt += [lu.JRT50 + ' TIME,']
        stmt += [lu.JRT75 + ' TIME,']
        stmt += [lu.JRTM + ' TIME);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_MOMM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.VER + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JSR + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ACCTM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.DUR + ' TEXT,']
        stmt += [lu.NJQ + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJE + ' INTEGER,']
        stmt += [lu.JRR + ' TEXT,']
        stmt += [lu.JSR + ' TEXT,']
        stmt += [lu.JER + ' TEXT,']
        stmt += [lu.JWTm + ' TIME,']
        stmt += [lu.JWT25 + ' TIME,']
        stmt += [lu.JWT50 + ' TIME,']
        stmt += [lu.JWTA + ' TIME,']
        stmt += [lu.JWT75 + ' TIME,']
        stmt += [lu.JWTM + ' TIME,']
        stmt += [lu.JRTm + ' TIME,']
        stmt += [lu.JRT25 + ' TIME,']
        stmt += [lu.JRTA + ' TIME,']
        stmt += [lu.JRT50 + ' TIME,']
        stmt += [lu.JRT75 + ' TIME,']
        stmt += [lu.JRTM + ' TIME,']
        stmt += [lu.JNSm + ' INTEGER,']
        stmt += [lu.JNS25 + ' REAL,']
        stmt += [lu.JNSA + ' REAL,']
        stmt += [lu.JNS50 + ' REAL,']
        stmt += [lu.JNS75 + ' REAL,']
        stmt += [lu.JNSM + ' REAL,']
        stmt += [lu.JCSm + ' INTEGER,']
        stmt += [lu.JCS25 + ' REAL,']
        stmt += [lu.JCSA + ' REAL,']
        stmt += [lu.JCS50 + ' REAL,']
        stmt += [lu.JCS75 + ' REAL,']
        stmt += [lu.JCSM + ' REAL,']
        stmt += [lu.CPH + ' INTEGER,']
        stmt += [lu.NPH + ' INTEGER,']
        stmt += [lu.UNCPUS + ' TEXT,']
        stmt += [lu.UNODES + ' TEXT,']
        stmt += [lu.USRS + ' TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_PROCM_TN)]
        stmt += ['id INTEGER, ']
        stmt += ['name TEXT,']
        stmt += ['rss INTEGER,']
        stmt += ['vsz INTEGER,']
        stmt += ['pcpu TEXT,']
        stmt += ['time TEXT);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_CYCLEM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.CST + ' INTEGER,']
        stmt += [lu.CD + ' TIME,']
        stmt += [lu.QD + ' TIME,']
        stmt += [lu.NJC + ' INTEGER,']
        stmt += [lu.NJR + ' INTEGER,']
        stmt += [lu.NJFR + ' INTEGER,']
        stmt += [lu.NJCAL + ' INTEGER,']
        stmt += [lu.NJFP + ' INTEGER,']
        stmt += [lu.NJP + ' INTEGER,']
        stmt += [lu.TTC + ' INTEGER,']
        stmt += [lu.SST + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ESTINFOSUM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.NJD + ' INTEGER,']
        stmt += [lu.NJND + ' INTEGER,']
        stmt += [lu.Ds15mn + ' INTEGER,']
        stmt += [lu.Ds1hr + ' INTEGER,']
        stmt += [lu.Ds3hr + ' INTEGER,']
        stmt += [lu.Do3hr + ' INTEGER,']
        stmt += [lu.DDm + ' INTEGER,']
        stmt += [lu.DDM + ' INTEGER,']
        stmt += [lu.DDA + ' INTEGER,']
        stmt += [lu.DD50 + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_ESTINFO_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.JID + ' TEXT,']
        stmt += [lu.Eat + ' INTEGER,']
        stmt += [lu.JST + ' INTEGER,']
        stmt += [lu.ESTR + ' INTEGER,']
        stmt += [lu.ESTA + ' INTEGER,']
        stmt += [lu.NEST + ' INTEGER,']
        stmt += [lu.ND + ' INTEGER,']
        stmt += [lu.JDD + ' INTEGER);']
        c.execute(''.join(stmt))

        stmt = ['CREATE TABLE IF NOT EXISTS %s (' % (_JOBM_TN)]
        stmt += ['id INTEGER,']
        stmt += ['logname TEXT,']
        stmt += [lu.CST + ' INTEGER,']
        stmt += [lu.JID + ' TEXT,']
        stmt += [lu.T2R + ' INTEGER,']
        stmt += [lu.T2D + ' INTEGER,']
        stmt += [lu.TiS + ' INTEGER,']
        stmt += [lu.TTC + ' INTEGER);']
        c.execute(''.join(stmt))
        self.__dbobj.commit()
        return self.__get_index(c)

    def __write_data(self, tablename, data, logfile):
        keys = ['id']
        values = [str(self.__index)]
        if logfile is not None:
            keys.append('logfile')
            values.append('\'' + str(logfile).replace(' ', '_') + '\'')
        for k, v in data.items():
            if k == 'id':
                continue
            keys.append(str(k))
            v = str(v)
            if v.isdigit():
                values.append(v)
            else:
                values.append('\'' + v + '\'')
        _keys = ','.join(keys)
        _values = ','.join(values)
        c = self.__dbobj.cursor()
        s = 'INSERT INTO %s (%s) VALUES (%s)' % (tablename, _keys, _values)
        c.execute(s)
        self.__dbobj.commit()

    def __write_server_data(self, data, logfile=None):
        self.__write_data(_SVRM_TN, data, logfile)

    def __write_mom_data(self, data, logfile=None):
        self.__write_data(_MOMM_TN, data, logfile)

    def __write_sched_data(self, data, logfile=None):
        for k, v in data.items():
            if k == 'summary':
                self.__write_data(_SCHEDM_TN, data, logfile)
                continue
            elif k == lu.EST:
                if lu.ESTS in v:
                    self.__write_estinfosum_data(v[lu.ESTS], logfile)
                if lu.EJ in v:
                    for j in v[lu.EJ]:
                        if lu.EST in j:
                            dt = map(lambda s: str(s), j[lu.Eat])
                            j[lu.Eat] = ','.join(dt)
                        self.__write_estsum_data(j, logfile)
                continue
            if 'jobs' in v:
                for j in v['jobs']:
                    j[lu.CST] = v[lu.CST]
                    self.__write_job_data(j, logfile)
                del v['jobs']
            self.__write_cycle_data(v, logfile)

    def __write_acct_data(self, data, logfile=None):
        self.__write_data(_ACCTM_TN, data, logfile)

    def __write_proc_data(self, data, logfile=None):
        self.__write_data(_PROCM_TN, data, None)

    def __write_cycle_data(self, data, logfile=None):
        self.__write_data(_CYCLEM_TN, data, logfile)

    def __write_estsum_data(self, data, logfile=None):
        self.__write_data(_ESTINFOSUM_TN, data, logfile)

    def __write_estinfosum_data(self, data, logfile=None):
        self.__write_data(_ESTINFO_TN, data, logfile)

    def __write_job_data(self, data, logfile=None):
        self.__write_data(_JOBM_TN, data, logfile)

    def __write_test_data(self, data):
        keys = ['id']
        values = [str(self.__index)]
        keys.append('suite')
        values.append(str(data['suite']))
        keys.append('testcase')
        values.append(str(data['testcase']))
        doc = []
        for l in str(data['testdoc']).strip().split('\n'):
            doc.append(l.strip().replace('\t', ' ').replace('\'', '\'\''))
        doc = ' '.join(doc)
        keys.append('testdoc')
        values.append('\'' + doc + '\'')
        keys.append('start_time')
        values.append(str(data['start_time']))
        keys.append('end_time')
        values.append(str(data['end_time']))
        keys.append('duration')
        values.append(str(data['duration']))
        keys.append('pbs_version')
        values.append(str(data['pbs_version']))
        keys.append('testparam')
        values.append(str(data['testparam']))
        keys.append('username')
        values.append(str(self.__username))
        keys.append('platform')
        values.append(str(self.__platform))
        keys.append('status')
        values.append(str(data['status']))
        sdata = data['status_data']
        sdata = sdata.replace('\'', '\'\'')
        keys.append('status_data')
        values.append('\'' + sdata + '\'')
        _keys = ','.join(keys)
        _values = ','.join(values)
        c = self.__dbobj.cursor()
        s = 'INSERT INTO %s (%s) VALUES (%s)' % (
            _TESTRESULT_TN, _keys, _values)
        c.execute(s)
        self.__dbobj.commit()

    def write(self, data, logfile=None):
        if len(data) == 0:
            return
        if 'testdata' in data.keys():
            self.__write_test_data(data['testdata'])
        if 'metrics_data' in data.keys():
            md = data['metrics_data']
            if 'server' in md.keys():
                self.__write_server_data(md['server'], logfile)
            if 'mom' in md.keys():
                self.__write_mom_data(md['mom'], logfile)
            if 'scheduler' in md.keys():
                self.__write_sched_data(md['scheduler'], logfile)
            if 'accounting' in md.keys():
                self.__write_acct_data(md['accounting'], logfile)
            if 'procs' in md.keys():
                self.__write_proc_data(md['procs'], logfile)
        self.__index += 1

    def close(self, result=None):
        self.__dbobj.commit()
        self.__dbobj.close()
        del self.__dbobj


class FileDb(DBType):

    """
    File type database
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        DBType.__init__(self, dbtype, dbpath, dbaccess)
        if self.dbtype != 'file':
            _msg = 'db type does not match with my type(file)'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        if self.dbpath is None:
            _msg = 'Db path require!'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        self.__separator1 = '=' * 80
        self.__separator2 = '___m_oo_m___'
        self.__username = pwd.getpwuid(os.getuid())[0]
        self.__platform = ' '.join(platform.uname()).strip()
        self.__ptlversion = str(ptl.__version__)
        self.__dbobj = {}
        self.__index = 1

    def __write_data(self, key, data, logfile):
        if key not in self.__dbobj.keys():
            f = os.path.join(self.dbdir, key + '.db')
            self.__dbobj[key] = open(f, 'w+')
        msg = [self.__separator1]
        msg += ['id = %s' % (self.__index)]
        if logfile is not None:
            msg += ['logfile = %s' % (logfile)]
        for k, v in data.items():
            if k == 'id':
                continue
            msg += [str(k) + ' = ' + str(v)]
        msg += [self.__separator1]
        self.__dbobj[key].write('\n'.join(msg) + '\n')
        self.__dbobj[key].flush()

    def __write_server_data(self, data, logfile=None):
        self.__write_data(_SVRM_TN, data, logfile)

    def __write_mom_data(self, data, logfile=None):
        self.__write_data(_MOMM_TN, data, logfile)

    def __write_sched_data(self, data, logfile=None):
        for k, v in data.items():
            if k == 'summary':
                self.__write_data(_SCHEDM_TN, data, logfile)
                continue
            elif k == lu.EST:
                if lu.ESTS in v:
                    self.__write_estinfosum_data(v[lu.ESTS], logfile)
                if lu.EJ in v:
                    for j in v[lu.EJ]:
                        if lu.EST in j:
                            dt = map(lambda s: str(s), j[lu.Eat])
                            j[lu.Eat] = ','.join(dt)
                        self.__write_estsum_data(j, logfile)
                continue
            if 'jobs' in v:
                for j in v['jobs']:
                    j[lu.CST] = v[lu.CST]
                    self.__write_job_data(j, logfile)
                del v['jobs']
            self.__write_cycle_data(v, logfile)

    def __write_acct_data(self, data, logfile=None):
        self.__write_data(_ACCTM_TN, data, logfile)

    def __write_proc_data(self, data, logfile=None):
        self.__write_data(_PROCM_TN, data, None)

    def __write_cycle_data(self, data, logfile=None):
        self.__write_data(_CYCLEM_TN, data, logfile)

    def __write_estsum_data(self, data, logfile=None):
        self.__write_data(_ESTINFOSUM_TN, data, logfile)

    def __write_estinfosum_data(self, data, logfile=None):
        self.__write_data(_ESTINFO_TN, data, logfile)

    def __write_job_data(self, data, logfile=None):
        self.__write_data(_JOBM_TN, data, logfile)

    def __write_test_data(self, data):
        if _TESTRESULT_TN not in self.__dbobj.keys():
            self.__dbobj[_TESTRESULT_TN] = open(self.dbpath, 'w+')
        msg = [self.__separator1]
        msg += ['id = %s' % (self.__index)]
        msg += ['suite = %s' % (data['suite'])]
        msg += ['testcase = %s' % (data['testcase'])]
        doc = []
        for l in str(data['testdoc']).strip().split('\n'):
            doc.append(l.strip())
        doc = ' '.join(doc)
        msg += ['testdoc = %s' % (doc)]
        msg += ['start_time = %s' % (str(data['start_time']))]
        msg += ['end_time = %s' % (str(data['end_time']))]
        msg += ['duration = %s' % (str(data['duration']))]
        msg += ['pbs_version = %s' % (data['pbs_version'])]
        msg += ['testparam = %s' % (data['testparam'])]
        msg += ['username = %s' % (self.__username)]
        msg += ['ptl_version = %s' % (self.__ptlversion)]
        msg += ['platform = %s' % (self.__platform)]
        msg += ['status = %s' % (data['status'])]
        msg += ['status_data = ']
        msg += [self.__separator2]
        msg += ['%s' % (str(data['status_data']))]
        msg += [self.__separator2]
        msg += [self.__separator1]
        self.__dbobj[_TESTRESULT_TN].write('\n'.join(msg) + '\n')
        self.__dbobj[_TESTRESULT_TN].flush()

    def write(self, data, logfile=None):
        if len(data) == 0:
            return
        if 'testdata' in data.keys():
            self.__write_test_data(data['testdata'])
        if 'metrics_data' in data.keys():
            md = data['metrics_data']
            if 'server' in md.keys():
                self.__write_server_data(md['server'], logfile)
            if 'mom' in md.keys():
                self.__write_mom_data(md['mom'], logfile)
            if 'scheduler' in md.keys():
                self.__write_sched_data(md['scheduler'], logfile)
            if 'accounting' in md.keys():
                self.__write_acct_data(md['accounting'], logfile)
            if 'procs' in md.keys():
                self.__write_proc_data(md['procs'], logfile)
        self.__index += 1

    def close(self, result=None):
        for v in self.__dbobj.values():
            v.write('\n')
            v.flush()
            v.close()


class HTMLDb(DBType):

    """
    HTML type database
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        DBType.__init__(self, dbtype, dbpath, dbaccess)
        if self.dbtype != 'html':
            _msg = 'db type does not match with my type(html)'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        if self.dbpath is None:
            _msg = 'Db path require!'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        elif not self.dbpath.endswith('.html'):
            self.dbpath = self.dbpath.rstrip('.db') + '.html'
        self.__cmd = [os.path.basename(sys.argv[0])]
        self.__cmd += sys.argv[1:]
        self.__username = pwd.getpwuid(os.getuid())[0]
        self.__platform = ' '.join(platform.uname()).strip()
        self.__ptlversion = str(ptl.__version__)
        self.__dbobj = {}
        self.__index = 1

    def __write_test_html_header(self, data):
        _title = 'PTL Test Report of %s' % (data['pbs_version'])
        __s = []
        __s += ['<!DOCTYPE html><head>']
        __s += ['<title>%s</title>' % (_title)]
        __s += ['<style type="text/css">']
        __s += [' * {']
        __s += ['     font-family: verdana;']
        __s += [' }']
        __s += [' h1 {']
        __s += ['     text-align: center;']
        __s += [' }']
        __s += [' .data {']
        __s += ['     font-size: 15px;']
        __s += ['     font-weight: normal;']
        __s += ['     width: 100%;']
        __s += [' }']
        __s += [' .data button {']
        __s += ['     float: left;']
        __s += ['     margin-right: 4px;']
        __s += ['     border: 1px solid #d0d0d0;']
        __s += ['     font-weight: bold;']
        __s += ['     outline: none;']
        __s += ['     width: 30px;']
        __s += ['     height: 30px;']
        __s += ['     cursor: pointer;']
        __s += ['     background-color: #eeeeee;']
        __s += [' }']
        __s += [' .data div {']
        __s += ['     text-align: left;']
        __s += [' }']
        __s += [' .data table {']
        __s += ['     border-spacing: 0px;']
        __s += ['     margin-top: 6px;']
        __s += ['     text-align: center;']
        __s += [' }']
        __s += [' .data th {']
        __s += ['     border: 1px solid #d0d0d0;']
        __s += ['     border-right: 0px;']
        __s += ['     background-color: #eeeeee;']
        __s += ['     font-weight: normal;']
        __s += ['     width: 13%;']
        __s += ['     padding: 5px;']
        __s += [' }']
        __s += [' .data th.innert:last-child {']
        __s += ['     width: 100%;']
        __s += [' }']
        __s += [' .data th.tsname {']
        __s += ['     font-weight: bold;']
        __s += ['     width: 500px;']
        __s += ['     text-align: left;']
        __s += [' }']
        __s += [' .data th.pass {']
        __s += ['     color: #3c763d;']
        __s += ['     background-color: #dff0d8;']
        __s += [' }']
        __s += [' .data th.skip {']
        __s += ['     color: #31708f;']
        __s += ['     background-color: #d9edf7;']
        __s += [' }']
        __s += [' .data th.fail,th.error,th.timedout {']
        __s += ['     color: #a94442;']
        __s += ['     background-color: #f2dede;']
        __s += [' }']
        __s += [' .data table th:last-child {']
        __s += ['     border: 1px solid #d0d0d0;']
        __s += [' }']
        __s += [' .data td {']
        __s += ['     border: 1px solid #d0d0d0;']
        __s += ['     border-top: 0px;']
        __s += ['     border-right: 0px;']
        __s += ['     padding: 5px;']
        __s += [' }']
        __s += [' .data td.pass_td {']
        __s += ['     background-color: #dff0d8;']
        __s += ['     color: #3c763d;']
        __s += [' }']
        __s += [' .data td.skip_td {']
        __s += ['     background-color: #d9edf7;']
        __s += ['     color: #31708f;']
        __s += [' }']
        __s += [' .data td.fail_td,td.error_td,td.timedout_td {']
        __s += ['     color: #a94442;']
        __s += ['     background-color: #f2dede;']
        __s += [' }']
        __s += [' .data tr td:last-child {']
        __s += ['     border: 1px solid #d0d0d0;']
        __s += ['     border-top: 0px;']
        __s += ['     text-align: left;']
        __s += ['     word-break: break-all;']
        __s += ['     white-space: pre-wrap;']
        __s += [' }']
        __s += [' .flt td {']
        __s += ['     padding-right: 25px;']
        __s += ['     padding-bottom: 10px;']
        __s += ['     font-size: 14px;']
        __s += [' }']
        __s += ['</style><script type="text/javascript">']
        __s += ['function toggle(id) {']
        __s += ['    var b = document.getElementById(id);']
        __s += ['    if (b == null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    b.textContent = b.textContent == "+" ? "-" : "+";']
        __s += ['    if (b.textContent == "-") {']
        __s += ['        var table = document.getElementById(id + "_t");']
        __s += ['        table.style.display = "";']
        __s += ['        var i = b.offsetLeft + b.offsetWidth;']
        __s += ['        i = i - b.clientLeft - 1;']
        __s += ['        table.style.marginLeft = i.toString() + "px";']
        __s += ['        sessionStorage.setItem(id, "");']
        __s += ['    } else {']
        __s += ['        var table = document.getElementById(id + "_t");']
        __s += ['        table.style.display = "none";']
        __s += ['        sessionStorage.removeItem(id);']
        __s += ['    }']
        __s += ['}']
        __s += ['function add_ts(tsn, n) {']
        __s += ['    sum = 0;']
        __s += ['    if (tsn == "Summary")']
        __s += ['        sum = 1;']
        __s += ['    if (document.getElementById(tsn + "_d") != null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    var div = document.createElement("div");']
        __s += ['    div.setAttribute("class", "data");']
        __s += ['    div.setAttribute("id", tsn + "_d");']
        __s += ['    if (sum == 1) {']
        __s += ['        div.setAttribute("style", "margin-bottom: 15px;");']
        __s += ['    }']
        __s += ['    document.body.appendChild(div);']
        __s += ['    if (n != null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    var btn = document.createElement("button");']
        __s += ['    btn.appendChild(document.createTextNode("+"));']
        __s += ['    div.appendChild(btn);']
        __s += ['    btn.setAttribute("id", tsn);']
        __s += ['    var t = "toggle(\\"" + tsn + "\\")";']
        __s += ['    btn.setAttribute("onclick", t);']
        __s += ['    if (sum == 1) {']
        __s += ['        btn.setAttribute("style", "visibility: hidden;");']
        __s += ['    }']
        __s += ['    var table = document.createElement("table");']
        __s += ['    div.appendChild(table);']
        __s += ['    table.setAttribute("id", tsn + "_i");']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "tsname");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "text-align: center;");']
        __s += ['    }']
        __s += ['    th.appendChild(document.createTextNode(tsn));']
        __s += ['    table.appendChild(th);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "run");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "pass");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    f = document.createElement("font");']
        __s += ['    f.setAttribute("style", "color: #ade4ad");']
        __s += ['    th.appendChild(f);']
        __s += ['    tsn = document.createTextNode("Passed: 0");']
        __s += ['    f.appendChild(tsn);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "skip");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    f = document.createElement("font");']
        __s += ['    f.setAttribute("style", "color: #b5d7f3");']
        __s += ['    th.appendChild(f);']
        __s += ['    tsn = document.createTextNode("Skipped: 0");']
        __s += ['    f.appendChild(tsn);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "fail");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    f = document.createElement("font");']
        __s += ['    f.setAttribute("style", "color: #efc0bf");']
        __s += ['    th.appendChild(f);']
        __s += ['    tsn = document.createTextNode("Failed: 0");']
        __s += ['    f.appendChild(tsn);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "error");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    f = document.createElement("font");']
        __s += ['    f.setAttribute("style", "color: #efc0bf");']
        __s += ['    th.appendChild(f);']
        __s += ['    tsn = document.createTextNode("Error: 0");']
        __s += ['    f.appendChild(tsn);']
        __s += ['    var th = document.createElement("th");']
        __s += ['    th.setAttribute("class", "timedout");']
        __s += ['    if (sum == 1) {']
        __s += ['        th.setAttribute("style", "font-weight: bold;");']
        __s += ['    }']
        __s += ['    table.appendChild(th);']
        __s += ['    f = document.createElement("font");']
        __s += ['    f.setAttribute("style", "color: #efc0bf");']
        __s += ['    th.appendChild(f);']
        __s += ['    tsn = document.createTextNode("TimedOut: 0");']
        __s += ['    f.appendChild(tsn);']
        __s += ['}']
        __s += ['function add_th(tsn) {']
        __s += ['    if (document.getElementById(tsn + "_t") != null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    var div = document.getElementById(tsn + "_d");']
        __s += ['    var table = document.createElement("table");']
        __s += ['    table.setAttribute("id", tsn + "_t");']
        __s += ['    table.setAttribute("style", "display: none");']
        __s += ['    div.appendChild(table);']
        __s += ['    var tr = document.createElement("tr");']
        __s += ['    table.appendChild(tr);']
        __s += ['    var lenh = datah.length;']
        __s += ['    for (var i = 0; i < lenh; i++) {']
        __s += ['        var th = document.createElement("th");']
        __s += ['        if (i < (lenh-1)) {']
        __s += ['            th.setAttribute("style", "border-right: 0px");']
        __s += ['        }']
        __s += ['        th.setAttribute("class", "innert");']
        __s += ['        var txt = document.createTextNode(datah[i]);']
        __s += ['        th.appendChild(txt);']
        __s += ['        tr.appendChild(th);']
        __s += ['    }']
        __s += ['}']
        __s += ['function restore(tc) {']
        __s += ['    var tco = document.getElementById(tc + "_o");']
        __s += ['    tco.removeAttribute("style");']
        __s += ['    tco.removeAttribute("id");']
        __s += ['    var tc = document.getElementById(tc);']
        __s += ['    tc.parentNode.removeChild(tc);']
        __s += ['}']
        __s += ['function add_row(d, sel) {']
        __s += ['    var s = d.status.toLowerCase();']
        __s += ['    if (s != sel && sel != "all") {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    if (sel == "all") {']
        __s += ['        sel = d.suite;']
        __s += ['    }']
        __s += ['    var table = document.getElementById(sel + "_t");']
        __s += ['    var tr = document.createElement("tr");']
        __s += ['    table.appendChild(tr);']
        __s += ['    var td = document.createElement("td");']
        __s += ['    td.setAttribute("class", s + "_td");']
        __s += ['    var tc = d.suite + "." + d.testcase']
        __s += ['    td.appendChild(document.createTextNode(tc));']
        __s += ['    tr.appendChild(td);']
        __s += ['    var td = document.createElement("td");']
        __s += ['    td.setAttribute("class", s + "_td");']
        __s += ['    var txt = document.createTextNode(d.duration);']
        __s += ['    td.appendChild(txt);']
        __s += ['    tr.appendChild(td);']
        __s += ['    var td = document.createElement("td");']
        __s += ['    td.setAttribute("class", s + "_td");']
        __s += ['    td.appendChild(document.createTextNode(d.status));']
        __s += ['    tr.appendChild(td);']
        __s += ['    tr.setAttribute("class", s);']
        __s += ['    var td = document.createElement("td");']
        __s += ['    td.setAttribute("class", s + "_td");']
        __s += ['    var lines = d.status_data.split("\\n");']
        __s += ['    var llen = lines.length;']
        __s += ['    if (llen > 10) {']
        __s += ['        var fl = lines.slice(0, 3).join("\\n");']
        __s += ['        td.appendChild(document.createTextNode(fl));']
        __s += ['        var a = document.createElement("a");']
        __s += ['        var scr = "javascript:restore(\\"" + tc + "\\")";']
        __s += ['        a.setAttribute("href", scr);']
        __s += ['        var txt = document.createTextNode("\\n...\\n\\n");']
        __s += ['        a.appendChild(txt);']
        __s += ['        td.setAttribute("id", tc);']
        __s += ['        td.appendChild(a);']
        __s += ['        lines = lines.slice(llen - 4, llen).join("\\n");']
        __s += ['        td.appendChild(document.createTextNode(lines));']
        __s += ['        var tdo = document.createElement("td");']
        __s += ['        tdo.setAttribute("class", s + "_td");']
        __s += ['        tdo.setAttribute("id", tc + "_o");']
        __s += ['        tdo.setAttribute("style", "display: none");']
        __s += ['        tr.appendChild(tdo);']
        __s += ['        var txt = document.createTextNode(d.status_data);']
        __s += ['        tdo.appendChild(txt);']
        __s += ['    } else {']
        __s += ['        var txt = document.createTextNode(d.status_data);']
        __s += ['        td.appendChild(txt);']
        __s += ['    }']
        __s += ['    tr.appendChild(td);']
        __s += ['    var tc = document.getElementById(sel + "_i");']
        __s += ['    if (tc == null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    var tt = tc.getElementsByClassName(s)[0];']
        __s += ['    var t = tt.textContent.split(" ");']
        __s += ['    var i = parseInt(t[1]) + 1;']
        __s += ['    tt.textContent = t[0] + " " + i;']
        __s += ['    var tt = tc.getElementsByClassName("run")[0]']
        __s += ['    if (tt.textContent == "") {']
        __s += ['        tt.textContent = "Run: 1";']
        __s += ['    } else {']
        __s += ['        var t = tt.textContent.split(" ");']
        __s += ['        var i = parseInt(t[1]) + 1;']
        __s += ['        tt.textContent = t[0] + " " + i;']
        __s += ['    }']
        __s += ['    var tc = document.getElementById("Summary_i");']
        __s += ['    if (tc == null) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    var tt = tc.getElementsByClassName(s)[0];']
        __s += ['    var t = tt.textContent.split(" ");']
        __s += ['    var i = parseInt(t[1]) + 1;']
        __s += ['    tt.textContent = t[0] + " " + i;']
        __s += ['    var tt = tc.getElementsByClassName("run")[0]']
        __s += ['    if (tt.textContent == "") {']
        __s += ['        tt.textContent = "Run: 1";']
        __s += ['    } else {']
        __s += ['        var t = tt.textContent.split(" ");']
        __s += ['        var i = parseInt(t[1]) + 1;']
        __s += ['        tt.textContent = t[0] + " " + i;']
        __s += ['    }']
        __s += ['}']
        __s += ['function add_dt(sel) {']
        __s += ['    var len = data.length;']
        __s += ['    for (i = 0; i < len; i++) {']
        __s += ['        var d = data[i];']
        __s += ['        if (sel == "all") {']
        __s += ['            add_ts("Summary");']
        __s += ['            add_ts(d.suite);']
        __s += ['            add_th(d.suite);']
        __s += ['        } else {']
        __s += ['            add_ts(sel, 1);']
        __s += ['            add_th(sel, 1);']
        __s += ['        }']
        __s += ['        add_row(d, sel);']
        __s += ['    }']
        __s += ['    var size = "40px";']
        __s += ['    if (len > 0) {']
        __s += ['        var b = document.getElementById(data[0].suite);']
        __s += ['        if (b != null) {']
        __s += ['            var i = b.offsetLeft + b.offsetWidth;']
        __s += ['            i = i - b.clientLeft - 1;']
        __s += ['            size = i.toString() + "px";']
        __s += ['        }']
        __s += ['    }']
        __s += ['    var t = document.getElementById("flt");']
        __s += ['    t.style.marginLeft = size;']
        __s += ['    if (sel != "all") {']
        __s += ['        t = document.getElementById(sel + "_t");']
        __s += ['        t.style.display = "";']
        __s += ['        t.style.marginLeft = size;']
        __s += ['    }']
        __s += ['    sessionStorage.removeItem("_filter_");']
        __s += ['    for (i = 0; i < sessionStorage.length; i++) {']
        __s += ['        toggle(sessionStorage.key(i));']
        __s += ['    }']
        __s += ['    sessionStorage.setItem("_filter_", sel);']
        __s += ['}']
        __s += ['function filter(n) {']
        __s += ['    var sf = sessionStorage.getItem("_filter_");']
        __s += ['    if (sf == null)']
        __s += ['        sf = "all";']
        __s += ['    var map = [sf, "all", "pass", "skip", "fail", "error",']
        __s += ['               "timedout"];']
        __s += ['    var sel = map[n];']
        __s += ['    var rbs = document.getElementsByTagName("input");']
        __s += ['    for (i = 0; i < rbs.length; i++) {']
        __s += ['        if (rbs[i].name == sel) {']
        __s += ['            rbs[i].checked = true;']
        __s += ['        } else {']
        __s += ['            rbs[i].checked = false;']
        __s += ['        }']
        __s += ['    }']
        __s += ['    var els = document.getElementsByClassName("data");']
        __s += ['    while (els.length > 0) {']
        __s += ['        els[0].parentNode.removeChild(els[0]);']
        __s += ['    }']
        __s += ['    add_dt(sel);']
        __s += ['}']
        __s += ['document.addEventListener("keydown", function(event) {']
        __s += ['    if (event.shiftKey || event.ctrlKey || event.altKey']
        __s += ['        || event.metaKey) {']
        __s += ['        return;']
        __s += ['    }']
        __s += ['    //              a,  p,  s,  f,  e,  t']
        __s += ['    var map = [-1, 65, 80, 83, 70, 69, 84]']
        __s += ['    if (map.indexOf(event.keyCode) != -1) {']
        __s += ['        filter(map.indexOf(event.keyCode));']
        __s += ['    }']
        __s += ['});']
        __s += ['</script></head><body onload="filter(0)">']
        __s += ['<h1>%s</h1>' % (_title)]
        _s = 'margin: 30px;margin-bottom: 15px;text-align: left;'
        __s += ['<div style="%s"><table>' % (_s)]
        _s = '<tr><th>%s:</th><td>%s</td></tr>'
        __s += [_s % ('Command', ' '.join(self.__cmd))]
        __s += [_s % ('TestParm', data['testparam'])]
        __s += [_s % ('User', self.__username)]
        __s += [_s % ('PTL Version', self.__ptlversion)]
        __s += [_s % ('Platform', self.__platform)]
        __s += ['</table></div><div id="flt"><table class="flt"><tr>']
        _s = '<td><input name="%s" type="radio" onclick="filter(%d);"/>%s</td>'
        __s += [_s % ('all', 1, 'Show All')]
        __s += [_s % ('pass', 2, 'Show only "Passed"')]
        __s += [_s % ('skip', 3, 'Show only "Skipped"')]
        __s += [_s % ('fail', 4, 'Show only "Failed"')]
        __s += [_s % ('error', 5, 'Show only "Error"')]
        __s += [_s % ('timedout', 6, 'Show only "TimedOut"')]
        __s += ['</tr></table></div><script type="text/javascript">']
        __s += ['datah = ["TestCase", "Duration", "Status", "Status Data"];']
        __s += ['data = [']
        __s += ['];</script></body></html>']
        self.__dbobj[_TESTRESULT_TN].write('\n'.join(__s))
        self.__dbobj[_TESTRESULT_TN].flush()

    def __write_test_data(self, data):
        if _TESTRESULT_TN not in self.__dbobj.keys():
            self.__dbobj[_TESTRESULT_TN] = open(self.dbpath, 'w+')
            self.__write_test_html_header(data)
        d = {}
        d['suite'] = data['suite']
        d['testcase'] = data['testcase']
        d['status'] = data['status']
        d['status_data'] = data['status_data']
        d['duration'] = str(data['duration'])
        self.__dbobj[_TESTRESULT_TN].seek(-27, os.SEEK_END)
        t = self.__dbobj[_TESTRESULT_TN].readline().strip()
        line = ''
        if t != '[':
            line += ',\n'
        else:
            line += '\n'
        line += str(d) + '\n];</script></body></html>'
        self.__dbobj[_TESTRESULT_TN].seek(-26, os.SEEK_END)
        self.__dbobj[_TESTRESULT_TN].write(line)
        self.__dbobj[_TESTRESULT_TN].flush()
        self.__index += 1

    def write(self, data, logfile=None):
        if len(data) == 0:
            return
        if 'testdata' in data.keys():
            self.__write_test_data(data['testdata'])

    def close(self, result=None):
        for v in self.__dbobj.values():
            v.write('\n')
            v.flush()
            v.close()


class JSONDb(DBType):

    """
    JSON type database
    """

    def __init__(self, dbtype, dbpath, dbaccess):
        super(JSONDb, self).__init__(dbtype, dbpath, dbaccess)
        if self.dbtype != 'json':
            _msg = 'db type does not match with my type(json)'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        if not self.dbpath:
            _msg = 'Db path require!'
            raise PTLDbError(rc=1, rv=False, msg=_msg)
        elif not self.dbpath.endswith('.json'):
            self.dbpath = self.dbpath.rstrip('.db') + '.json'
        self.__dbobj = {}
        self.__cmd = [os.path.basename(sys.argv[0])]
        self.__cmd += sys.argv[1:]
        self.__cmd = ' '.join(self.__cmd)
        self.res_data = PTLJsonData(command=self.__cmd)

    def __write_test_data(self, data):
        jdata = None
        if _TESTRESULT_TN not in self.__dbobj.keys():
            self.__dbobj[_TESTRESULT_TN] = open(self.dbpath, 'w+')
        else:
            self.__dbobj[_TESTRESULT_TN].seek(0)
            jdata = json.load(self.__dbobj[_TESTRESULT_TN])
        jsondata = self.res_data.get_json(data=data, prev_data=jdata)
        self.__dbobj[_TESTRESULT_TN].seek(0)
        json.dump(jsondata, self.__dbobj[_TESTRESULT_TN], indent=2)

    def write(self, data, logfile=None):
        if len(data) == 0:
            return
        if 'testdata' in data.keys():
            self.__write_test_data(data['testdata'])

    def close(self, result=None):
        if result is not None:
            self.__dbobj[_TESTRESULT_TN].seek(0)
            df = json.load(self.__dbobj[_TESTRESULT_TN])
            dur = str(result.stop - result.start)
            df['test_summary']['test_duration'] = dur
            self.__dbobj[_TESTRESULT_TN].seek(0)
            json.dump(df, self.__dbobj[_TESTRESULT_TN], indent=2)
        for v in self.__dbobj.values():
            v.write('\n')
            v.flush()
            v.close()


class PTLTestDb(Plugin):

    """
    PTL Test Database Plugin
    """
    name = 'PTLTestDb'
    score = sys.maxint - 5
    logger = logging.getLogger(__name__)

    def __init__(self):
        Plugin.__init__(self)
        self.__dbconn = None
        self.__dbtype = 'JSONDb'
        self.__dbpath = None
        self.__dbaccess = None
        self.__dbmapping = {'file': FileDb,
                            'html': HTMLDb,
                            'json': JSONDb,
                            'sqlite': SQLiteDb,
                            'pgsql': PostgreSQLDb}
        self.__du = DshUtils()

    def options(self, parser, env):
        """
        Register command line options
        """
        pass

    def set_data(self, dbtype, dbpath, dbaccess):
        """
        Set the data
        """
        self.__dbtype = dbtype
        self.__dbpath = dbpath
        self.__dbaccess = dbaccess

    def configure(self, options, config):
        """
        Configure the plugin and system, based on selected options

        :param options: Configuration options for ``plugin`` and ``system``
        """
        if self.__dbconn is not None:
            return
        if self.__dbtype is None:
            self.__dbtype = 'json'
        if self.__dbtype not in self.__dbmapping.keys():
            self.logger.error('Invalid db type: %s' % self.__dbtype)
            sys.exit(1)
        try:
            self.__dbconn = self.__dbmapping[self.__dbtype](self.__dbtype,
                                                            self.__dbpath,
                                                            self.__dbaccess)
        except PTLDbError, e:
            self.logger.error(str(e) + '\n')
            sys.exit(1)
        self.enabled = True

    def __create_data(self, test, err=None, status=None):
        if hasattr(test, 'test'):
            _test = test.test
            sn = _test.__class__.__name__
        elif hasattr(test, 'context'):
            test = _test = test.context
            sn = test.__name__
        else:
            return {}
        testdata = {}
        data = {}
        if (hasattr(_test, 'server') and
                (getattr(_test, 'server', None) is not None)):
            testdata['pbs_version'] = _test.server.attributes['pbs_version']
            testdata['hostname'] = _test.server.hostname
        else:
            testdata['pbs_version'] = 'unknown'
            testdata['hostname'] = 'unknown'
        testdata['machinfo'] = self.__get_machine_info(_test)
        testdata['testparam'] = getattr(_test, 'param', None)
        testdata['suite'] = sn
        testdata['suitedoc'] = str(_test.__class__.__doc__)
        testdata['file'] = _test.__module__.replace('.', '/') + '.py'
        testdata['module'] = _test.__module__
        testdata['testcase'] = getattr(_test, '_testMethodName', '<unknown>')
        testdata['testdoc'] = getattr(_test, '_testMethodDoc', '<unknown>')
        testdata['start_time'] = getattr(test, 'start_time', 0)
        testdata['end_time'] = getattr(test, 'end_time', 0)
        testdata['duration'] = getattr(test, 'duration', 0)
        testdata['tags'] = getattr(_test, TAGKEY, [])
        measurements_dic = getattr(_test, 'measurements', {})
        if measurements_dic:
            testdata['measurements'] = measurements_dic
        additional_data_dic = getattr(_test, 'additional_data', {})
        if additional_data_dic:
            testdata['additional_data'] = additional_data_dic
        if err is not None:
            if isclass(err[0]) and issubclass(err[0], SkipTest):
                testdata['status'] = 'SKIP'
                testdata['status_data'] = 'Reason = %s' % (err[1])
            else:
                if isclass(err[0]) and issubclass(err[0], TimeOut):
                    status = 'TIMEDOUT'
                testdata['status'] = status
                testdata['status_data'] = getattr(test, 'err_in_string',
                                                  '<unknown>')
        else:
            testdata['status'] = status
            testdata['status_data'] = ''
        data['testdata'] = testdata
        md = getattr(_test, 'metrics_data', {})
        if len(md) > 0:
            data['metrics_data'] = md
        return data

    def __get_machine_info(self, test):
        """
        Helper function to return machines dictionary with details

        :param: test
        :test type: object

        returns dictionary with machines information
        """
        mpinfo = {
            'servers': [],
            'moms': [],
            'comms': [],
            'clients': []
        }
        minstall_type = {
            'servers': 'server',
            'moms': 'execution',
            'comms': 'communication',
            'clients': 'client'
        }
        for name in mpinfo:
            mlist = None
            if (hasattr(test, name) and
                    (getattr(test, name, None) is not None)):
                mlist = getattr(test, name).values()
            if mlist:
                for mc in mlist:
                    mpinfo[name].append(mc.hostname)
        machines = {}
        for k, v in mpinfo.items():
            for hst in v:
                if hst not in machines:
                    machines[hst] = {}
                    mshort = machines[hst]
                    mshort['platform'] = self.__du.get_uname(hostname=hst)
                    mshort['os_info'] = self.__du.get_os_info(hostname=hst)
                machines[hst]['pbs_install_type'] = minstall_type[k]
                if ((k == 'moms' or k == 'comms') and
                        hst in mpinfo['servers']):
                    machines[hst]['pbs_install_type'] = 'server'
        return machines

    def addError(self, test, err):
        self.__dbconn.write(self.__create_data(test, err, 'ERROR'))

    def addFailure(self, test, err):
        self.__dbconn.write(self.__create_data(test, err, 'FAIL'))

    def addSuccess(self, test):
        self.__dbconn.write(self.__create_data(test, None, 'PASS'))

    def finalize(self, result):
        self.__dbconn.close(result)
        self.__dbconn = None
        self.__dbaccess = None

    def process_output(self, info={}, dbout=None, dbtype=None, dbaccess=None,
                       name=None, logtype=None, summary=False):
        """
        Send analyzed log information to either the screen or to a database
        file.

        :param info: A dictionary of log analysis metrics.
        :type info: Dictionary
        :param dbout: The name of the database file to send output to
        :type dbout: str or None
        :param dbtype: Type of database
        :param dbaccess: Path to a file that defines db options
                         (PostreSQL only)
        :param name: The name of the log file being analyzed
        :type name: str or None
        :param logtype: The log type, one of ``accounting``, ``schedsummary``,
                        ``scheduler``, ``server``, or ``mom``
        :param summary: If True output summary only
        """
        if dbout is not None:
            try:
                self.set_data(dbtype, dbout, dbaccess)
                self.configure(None, None)
                data = {'metrics_data': {logtype: info}}
                self.__dbconn.write(data, os.path.basename(name))
                self.finalize(None)
            except Exception, e:
                traceback.print_exc()
                sys.stderr.write('Error processing output ' + str(e))
            return

        if lu.CFC in info:
            freq_info = info[lu.CFC]
        elif 'summary' in info and lu.CFC in info['summary']:
            freq_info = info['summary'][lu.CFC]
        else:
            freq_info = None

        if 'matches' in info:
            for m in info['matches']:
                print m,
            del info['matches']

        if freq_info is not None:
            for ((l, m), n) in freq_info:
                b = time.strftime("%m/%d/%y %H:%M:%S", time.localtime(l))
                e = time.strftime("%m/%d/%y %H:%M:%S", time.localtime(m))
                print(b + ' -'),
                if b[:8] != e[:8]:
                    print(e),
                else:
                    print(e[9:]),
                print(': ' + str(n))
            return

        if lu.EST in info:
            einfo = info[lu.EST]
            m = []

            for j in einfo[lu.EJ]:
                m.append('Job ' + j[lu.JID] + '\n\testimated:')
                if lu.Eat in j:
                    for estimate in j[lu.Eat]:
                        m.append('\t\t' + str(time.ctime(estimate)))
                if lu.JST in j:
                    m.append('\tstarted:\n')
                    m.append('\t\t' + str(time.ctime(j[lu.JST])))
                    m.append('\testimate range: ' + str(j[lu.ESTR]))
                    m.append('\tstart to estimated: ' + str(j[lu.ESTA]))

                if lu.NEST in j:
                    m.append('\tnumber of estimates: ' + str(j[lu.NEST]))
                if lu.NJD in j:
                    m.append('\tnumber of drifts: ' + str(j[lu.NJD]))
                if lu.JDD in j:
                    m.append('\tdrift duration: ' + str(j[lu.JDD]))
                m.append('\n')

            if lu.ESTS in einfo:
                m.append('\nsummary: ')
                for k, v in sorted(einfo[lu.ESTS].items()):
                    if 'duration' in k:
                        m.append('\t' + k + ': ' +
                                 str(PbsTypeDuration(int(v))))
                    else:
                        m.append('\t' + k + ': ' + str(v))

            print "\n".join(m)
            return

        sorted_info = sorted(info.items())
        for (k, v) in sorted_info:
            if summary and k != 'summary':
                continue
            print str(k) + ": ",
            if isinstance(v, dict):
                sorted_v = sorted(v.items())
                for (k, val) in sorted_v:
                    print str(k) + '=' + str(val) + ' '
                print
            else:
                print str(v)
        print ''
