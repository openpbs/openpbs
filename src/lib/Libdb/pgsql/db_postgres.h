/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */

/**
 *
 * @brief
 *  Postgres specific implementation
 *
 * This header file contains Postgres specific data structures and functions
 * to access the PBS postgres database. These structures are used only by the
 * postgres specific data store implementation, and should not be used directly
 * by the rest of the PBS code.
 *
 * The functions/interfaces in this header are PBS Private.
 */

#ifndef _DB_POSTGRES_H
#define _DB_POSTGRES_H

#ifdef __cplusplus
extern "C" {
#endif

#include <libpq-fe.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <inttypes.h>
#include "net_connect.h"
#include "list_link.h"
#include "portability.h"
#include "attribute.h"

/*
 * Conversion macros for long long type
 */
#if !defined(ntohll)
#define ntohll(x) db_ntohll(x)
#endif
#if !defined(htonll)
#define htonll(x) ntohll(x)
#endif

#define PBS_MAXATTRNAME 64
#define PBS_MAXATTRRESC 64
#define MAX_SQL_LENGTH 8192

/* job sql statement names */
#define STMT_SELECT_JOB "select_job"
#define STMT_INSERT_JOB "insert_job"
#define STMT_UPDATE_JOB "update_job"
#define STMT_UPDATE_JOB_ATTRSONLY "update_job_attrsonly"
#define STMT_UPDATE_JOB_QUICK "update_job_quick"
#define STMT_FINDJOBS_ORDBY_QRANK "findjobs_ordby_qrank"
#define STMT_FINDJOBS_BYQUE_ORDBY_QRANK "findjobs_byque_ordby_qrank"
#define STMT_DELETE_JOB "delete_job"
#define STMT_REMOVE_JOBATTRS "remove_jobattrs"

/* JOBSCR stands for job script */
#define STMT_INSERT_JOBSCR "insert_jobscr"
#define STMT_SELECT_JOBSCR "select_jobscr"
#define STMT_DELETE_JOBSCR "delete_jobscr"

/* reservation statement names */
#define STMT_INSERT_RESV "insert_resv"
#define STMT_UPDATE_RESV "update_resv"
#define STMT_UPDATE_RESV_QUICK "update_resv_quick"
#define STMT_UPDATE_RESV_ATTRSONLY "update_resv_attrsonly"
#define STMT_SELECT_RESV "select_resv"
#define STMT_DELETE_RESV "delete_resv"
#define STMT_REMOVE_RESVATTRS "remove_resvattrs"

/* creattm is the table field that holds the creation time */
#define STMT_FINDRESVS_ORDBY_CREATTM "findresvs_ordby_creattm"

/* server & seq statement names */
#define STMT_INSERT_SVR "insert_svr"
#define STMT_UPDATE_SVR "update_svr"
#define STMT_SELECT_SVR "select_svr"
#define STMT_SELECT_DBVER "select_dbver"
#define STMT_SELECT_NEXT_SEQID "select_nextseqid"
#define STMT_REMOVE_SVRATTRS "remove_svrattrs"
#define STMT_INSERT_SVRINST "stmt_insert_svrinst"
#define STMT_UPDATE_SVRINST "stmt_update_svrinst"
#define STMT_SELECT_SVRINST "stmt_select_svrinst"

/* queue statement names */
#define STMT_INSERT_QUE "insert_que"
#define STMT_UPDATE_QUE "update_que"
#define STMT_UPDATE_QUE_QUICK "update_que_quick"
#define STMT_UPDATE_QUE_ATTRSONLY "update_que_attrsonly"
#define STMT_SELECT_QUE "select_que"
#define STMT_DELETE_QUE "delete_que"
#define STMT_FIND_QUES_ORDBY_CREATTM "find_ques_ordby_creattm"
#define STMT_REMOVE_QUEATTRS "remove_queattrs"

/* node statement names */
#define STMT_INSERT_NODE "insert_node"
#define STMT_UPDATE_NODE "update_node"
#define STMT_UPDATE_NODE_QUICK "update_node_quick"
#define STMT_UPDATE_NODE_ATTRSONLY "update_node_attrsonly"
#define STMT_SELECT_NODE "select_node"
#define STMT_DELETE_NODE "delete_node"
#define STMT_REMOVE_NODEATTRS "remove_nodeattrs"
#define STMT_UPDATE_NODEATTRS "update_nodeattrs"
#define STMT_FIND_NODES_ORDBY_CREATTM "find_nodes_ordby_creattm"
#define STMT_FIND_NODES_ORDBY_INDEX "find_nodes_ordby_index"
#define STMT_SELECT_MOMINFO_TIME "select_mominfo_time"
#define STMT_INSERT_MOMINFO_TIME "insert_mominfo_time"
#define STMT_UPDATE_MOMINFO_TIME "update_mominfo_time"

/* node job statements */
#define STMT_SELECT_NODEJOB "select_nodejob"
#define STMT_FIND_NODEJOB_USING_NODEID "select_nodejob_with_nodeid"
#define STMT_INSERT_NODEJOB "insert_nodejob"
#define STMT_UPDATE_NODEJOB "update_nodejob"
#define STMT_UPDATE_NODEJOB_QUICK "update_nodejob_quick"
#define STMT_UPDATE_NODEJOB_ATTRSONLY "update_nodejob_attrsonly"
#define STMT_DELETE_NODEJOB "delete_nodejob"

/* scheduler statement names */
#define STMT_INSERT_SCHED "insert_sched"
#define STMT_UPDATE_SCHED "update_sched"
#define STMT_SELECT_SCHED "select_sched"
#define STMT_SELECT_SCHED_ALL "select_sched_all"
#define STMT_DELETE_SCHED "sched_delete"
#define STMT_REMOVE_SCHEDATTRS "remove_schedattrs"

#define POSTGRES_QUERY_MAX_PARAMS 30

/**
 * @brief
 *  Prepared statements require parameter postion, formats and values to be
 *  supplied to the query. This structure is stored as part of the connection
 *  object and re-used for every prepared statement
 *
 */
struct postgres_conn_data {
	const char *paramValues[POSTGRES_QUERY_MAX_PARAMS];
	int paramLengths[POSTGRES_QUERY_MAX_PARAMS];
	int paramFormats[POSTGRES_QUERY_MAX_PARAMS];

	/* followin are two tmp arrays used for conversion of binary data*/
	INTEGER temp_int[POSTGRES_QUERY_MAX_PARAMS];
	BIGINT temp_long[POSTGRES_QUERY_MAX_PARAMS];
};
typedef struct postgres_conn_data pg_conn_data_t;

/**
 * @brief
 * Postgres transaction management helper structure.
 */
struct pg_conn_trx {
	int conn_trx_nest;     /* incr/decr with each begin/end trx */
	int conn_trx_rollback; /* rollback flag in case of nested trx */
	int conn_trx_async;    /* 1 - async, 0 - sync, one-shot reset */
};
typedef struct pg_conn_trx pg_conn_trx_t;

extern pg_conn_data_t *conn_data;
extern pg_conn_trx_t *conn_trx;

/**
 * @brief
 *  This structure is used to represent the cursor state for a multirow query
 *  result. The row field keep track of which row is the current row (or was
 *  last returned to the caller). The count field contains the total number of
 *  rows that are available in the resultset.
 *
 */
struct db_query_state {
	PGresult *res;
	int row;
	int count;
	query_cb_t query_cb;
};
typedef struct db_query_state db_query_state_t;

/**
 * @brief
 * Each database object type supports most of the following 6 operations:
 *	- insertion
 *	- updation
 *	- deletion
 *	- loading
 *	- find rows matching a criteria
 *	- get next row from a cursor (created in a find command)
 *
 * The following structure has function pointers to all the above described
 * operations.
 *
 */
struct postgres_db_fn {
	int (*pbs_db_save_obj)(void *conn, pbs_db_obj_info_t *obj, int savetype);
	int (*pbs_db_delete_obj)(void *conn, pbs_db_obj_info_t *obj);
	int (*pbs_db_load_obj)(void *conn, pbs_db_obj_info_t *obj);
	int (*pbs_db_find_obj)(void *conn, void *state, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
	int (*pbs_db_next_obj)(void *conn, void *state, pbs_db_obj_info_t *obj);
	int (*pbs_db_del_attr_obj)(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
};

typedef struct postgres_db_fn pg_db_fn_t;

/*
 * The following are defined as macros as they are used very frequently
 * Making them functions would effect performance.
 *
 * SET_PARAM_STR     - Loads null terminated string to postgres parameter at index "i"
 * SET_PARAM_STRSZ   - Same as SET_PARAM_STR, only size of string is provided
 * SET_PARAM_INTEGER - Loads integer to postgres parameter at index "i"
 * SET_PARAM_BIGINT  - Loads BIGINT value to postgres parameter at index "i"
 * SET_PARAM_BIN     - Loads a BINARY value to postgres parameter at index "i"
 *
 * Basically there are 3 values that need to be supplied for every paramter
 * of any prepared sql statement. They are:
 *	1) The value - The value to be "bound/loaded" to the parameter. This
 *			is the adress of the variable which holds the value.
 *			The variable paramValues[i] is used to hold that address
 *			For strings, its the address of the string, for integers
 *			etc, we need to convert the integer value to network
 *			byte order (htonl - and store it in temp_int/long[i],
 *			and pass the address of temp_int/long[i]
 *
 *	2) The length - This is the length of the value that is loaded. It is
 *			loaded to variable paramLengths[i]. For strings, this
 *			is the string length or passed length value (LOAD_STRSZ)
 *			For integers (& bigints), its the sizeof(int) or
 *			sizeof(BIGINT). In case of BINARY data, the len is set
 *			to the length supplied as a parameter.
 *
 *	3) The format - This is the format of the datatype that is being passed
 *			For strings, the value is "0", for binary value is "1".
 *			This is loaded into paramValues[i].
 *
 * The Postgres specific connection structure pg_conn_data_t has the following
 * arrays defined, so that they dont have to be created every time needed.
 * - paramValues - array to hold values of each parameter
 * - paramLengths - Lengths of each of these values (corresponding index)
 * - paramFormats - Formats of the datatype passed for each value (corr index)
 * - temp_int	  - array to use to convert int to network byte order
 * - temp_long	  - array to use to convery BIGINT to network byte order
 */
#define SET_PARAM_STR(conn_data, itm, i)                                       \
	((pg_conn_data_t *) conn_data)->paramValues[i] = (itm);                \
	if (itm)                                                               \
		((pg_conn_data_t *) conn_data)->paramLengths[i] = strlen(itm); \
	else                                                                   \
		((pg_conn_data_t *) conn_data)->paramLengths[i] = 0;           \
	((pg_conn_data_t *) conn_data)->paramFormats[i] = 0;

#define SET_PARAM_STRSZ(conn_data, itm, size, i)                  \
	((pg_conn_data_t *) conn_data)->paramValues[i] = (itm);   \
	((pg_conn_data_t *) conn_data)->paramLengths[i] = (size); \
	((pg_conn_data_t *) conn_data)->paramFormats[i] = 0;

#define SET_PARAM_INTEGER(conn_data, itm, i)                                \
	((pg_conn_data_t *) conn_data)->temp_int[i] = (INTEGER) htonl(itm); \
	((pg_conn_data_t *) conn_data)->paramValues[i] =                    \
		(char *) &(((pg_conn_data_t *) conn_data)->temp_int[i]);    \
	((pg_conn_data_t *) conn_data)->paramLengths[i] = sizeof(int);      \
	((pg_conn_data_t *) conn_data)->paramFormats[i] = 1;

#define SET_PARAM_BIGINT(conn_data, itm, i)                                  \
	((pg_conn_data_t *) conn_data)->temp_long[i] = (BIGINT) htonll(itm); \
	((pg_conn_data_t *) conn_data)->paramValues[i] =                     \
		(char *) &(((pg_conn_data_t *) conn_data)->temp_long[i]);    \
	((pg_conn_data_t *) conn_data)->paramLengths[i] = sizeof(BIGINT);    \
	((pg_conn_data_t *) conn_data)->paramFormats[i] = 1;

#define SET_PARAM_BIN(conn_data, itm, len, i)                    \
	((pg_conn_data_t *) conn_data)->paramValues[i] = (itm);  \
	((pg_conn_data_t *) conn_data)->paramLengths[i] = (len); \
	((pg_conn_data_t *) conn_data)->paramFormats[i] = 1;

#define GET_PARAM_STR(res, row, itm, fnum) \
	strcpy((itm), PQgetvalue((res), (row), (fnum)));

#define GET_PARAM_INTEGER(res, row, itm, fnum) \
	(itm) = ntohl(*((uint32_t *) PQgetvalue((res), (row), (fnum))));

#define GET_PARAM_BIGINT(res, row, itm, fnum) \
	(itm) = ntohll(*((uint64_t *) PQgetvalue((res), (row), (fnum))));

#define GET_PARAM_BIN(res, row, itm, fnum) \
	(itm) = PQgetvalue((res), (row), (fnum));

#define FIND_JOBS_BY_QUE 1

/* common functions */
int db_prepare_job_sqls(void *conn);
int db_prepare_resv_sqls(void *conn);
int db_prepare_svr_sqls(void *conn);
int db_prepare_node_sqls(void *conn);
int db_prepare_sched_sqls(void *conn);
int db_prepare_que_sqls(void *conn);

void db_set_error(void *conn, char **conn_db_err, char *fnc, char *msg, char *msg2);
int db_prepare_stmt(void *conn, char *stmt, char *sql, int num_vars);
int db_cmd(void *conn, char *stmt, int num_vars);
int db_query(void *conn, char *stmt, int num_vars, PGresult **res);
unsigned long long db_ntohll(unsigned long long);
int dbarray_to_attrlist(char *raw_array, pbs_db_attr_list_t *attr_list);
int attrlist_to_dbarray(char **raw_array, pbs_db_attr_list_t *attr_list);
int attrlist_to_dbarray_ex(char **raw_array, pbs_db_attr_list_t *attr_list, int keys_only);

/* job functions */
int pbs_db_save_job(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_job(void *conn, pbs_db_obj_info_t *obj);
int pbs_db_find_job(void *conn, void *st, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int pbs_db_next_job(void *conn, void *st, pbs_db_obj_info_t *obj);
int pbs_db_delete_job(void *conn, pbs_db_obj_info_t *obj);

int pbs_db_save_jobscr(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_jobscr(void *conn, pbs_db_obj_info_t *obj);

/* resv functions */
int pbs_db_save_resv(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_resv(void *conn, pbs_db_obj_info_t *obj);
int pbs_db_find_resv(void *conn, void *st, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int pbs_db_next_resv(void *conn, void *st, pbs_db_obj_info_t *obj);
int pbs_db_delete_resv(void *conn, pbs_db_obj_info_t *obj);

/* svr functions */
int pbs_db_save_svr(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_svr(void *conn, pbs_db_obj_info_t *obj);

/* node functions */
int pbs_db_save_node(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_node(void *conn, pbs_db_obj_info_t *obj);
int pbs_db_find_node(void *conn, void *st, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int pbs_db_next_node(void *conn, void *st, pbs_db_obj_info_t *obj);
int pbs_db_delete_node(void *conn, pbs_db_obj_info_t *obj);

/* mominfo_time functions */
int pbs_db_save_mominfo_tm(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_mominfo_tm(void *conn, pbs_db_obj_info_t *obj);

/* queue functions */
int pbs_db_save_que(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_que(void *conn, pbs_db_obj_info_t *obj);
int pbs_db_find_que(void *conn, void *st, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int pbs_db_next_que(void *conn, void *st, pbs_db_obj_info_t *obj);
int pbs_db_delete_que(void *conn, pbs_db_obj_info_t *obj);

/* scheduler functions */
int pbs_db_save_sched(void *conn, pbs_db_obj_info_t *obj, int savetype);
int pbs_db_load_sched(void *conn, pbs_db_obj_info_t *obj);

int pbs_db_find_sched(void *conn, void *st, pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int pbs_db_next_sched(void *conn, void *st, pbs_db_obj_info_t *obj);
int pbs_db_delete_sched(void *conn, pbs_db_obj_info_t *obj);

int pbs_db_del_attr_job(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
int pbs_db_del_attr_sched(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
int pbs_db_del_attr_resv(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
int pbs_db_del_attr_svr(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
int pbs_db_del_attr_que(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);
int pbs_db_del_attr_node(void *conn, void *obj_id, pbs_db_attr_list_t *attr_list);

/**
 * @brief
 *	Execute a direct sql string on the open database connection
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	sql  - A string describing the sql to execute.
 *
 * @return      int
 * @retval      -1  - Error
 * @retval       0  - success
 * @retval       1  - Execution succeeded but statement did not return any rows
 *
 */
int db_execute_str(void *conn, char *sql);

#ifdef __cplusplus
}
#endif

#endif /* _DB_POSTGRES_H */
