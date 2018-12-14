/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */

/**
 * @file    db_postgres.h
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
#define	_DB_POSTGRES_H

#ifdef	__cplusplus
extern "C" {
#endif

#include <libpq-fe.h>
#include <netinet/in.h>
#ifndef WIN32
#include <sys/types.h>
#include <inttypes.h>
#endif
#include "net_connect.h"
#include "list_link.h"
#include "portability.h"
#include "attribute.h"

/* work around strtoll on some platforms */
#if defined(WIN32)
#define strtoll(n, e, b)	_strtoi64((n), (e), (b))
typedef __int32 int32_t;
typedef __int64 int64_t;
typedef unsigned __int32 uint32_t;
typedef unsigned __int64 uint64_t;
#endif


/*
 * Conversion macros for long long type
 */
#if !defined(ntohll)
#define ntohll(x) pbs_ntohll(x)
#endif
#if !defined(htonll)
#define htonll(x) ntohll(x)
#endif

/* job sql statement names */
#define STMT_SELECT_JOB "select_job"
#define STMT_INSERT_JOB "insert_job"
#define STMT_UPDATE_JOB "update_job"
#define STMT_UPDATE_JOB_QUICK "update_job_quick"
#define STMT_FINDJOBS_ORDBY_QRANK   "findjobs_ordby_qrank"
#define STMT_FINDJOBS_BYQUE_ORDBY_QRANK "findjobs_byque_ordby_qrank"
#define STMT_DELETE_JOB "delete_job"
#define STMT_REMOVE_JOBATTRS "remove_jobattrs"

/* JOBSCR stands for job script */
#define STMT_INSERT_JOBSCR  "insert_jobscr"
#define STMT_SELECT_JOBSCR  "select_jobscr"
#define STMT_DELETE_JOBSCR  "delete_jobscr"



/* reservation statement names */
#define STMT_INSERT_RESV "insert_resv"
#define STMT_UPDATE_RESV "update_resv"
#define STMT_SELECT_RESV "select_resv"
#define STMT_DELETE_RESV "delete_resv"
#define STMT_REMOVE_RESVATTRS "remove_resvattrs"

/* creattm is the table field that holds the creation time */
#define STMT_FINDRESVS_ORDBY_CREATTM "findresvs_ordby_creattm"


/* server & seq statement names */
#define STMT_INSERT_SVR "insert_svr"
#define STMT_UPDATE_SVR_FULL "update_svr_full"
#define STMT_UPDATE_SVR_QUICK "update_svr_quick"
#define STMT_SELECT_SVR "select_svr"
#define STMT_SELECT_DBVER "select_dbver"
#define STMT_SELECT_NEXT_SEQID "select_nextseqid"
#define STMT_REMOVE_SVRATTRS "remove_svrattrs"

/* queue statement names */
#define STMT_INSERT_QUE "insert_que"
#define STMT_UPDATE_QUE_FULL "update_que_full"
#define STMT_SELECT_QUE "select_que"
#define STMT_DELETE_QUE "delete_que"
#define STMT_FIND_QUES_ORDBY_CREATTM "find_ques_ordby_creattm"
#define STMT_REMOVE_QUEATTRS "remove_queattrs"

/* node statement names */
#define STMT_INSERT_NODE "insert_node"
#define STMT_UPDATE_NODE "update_node"
#define STMT_SELECT_NODE "select_node"
#define STMT_DELETE_NODE "delete_node"
#define STMT_REMOVE_NODEATTRS "remove_nodeattrs"
#define STMT_UPDATE_NODEATTRS "update_nodeattrs"
#define STMT_FIND_NODES_ORDBY_CREATTM "find_nodes_ordby_creattm"
#define STMT_FIND_NODES_ORDBY_INDEX "find_nodes_ordby_index"
#define STMT_SELECT_MOMINFO_TIME "select_mominfo_time"
#define STMT_INSERT_MOMINFO_TIME "insert_mominfo_time"
#define STMT_UPDATE_MOMINFO_TIME "update_mominfo_time"

/* scheduler statement names */
#define STMT_INSERT_SCHED "insert_sched"
#define STMT_UPDATE_SCHED_FULL "update_sched_full"
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
 *  This structure is used to represent the cursor state for a multirow query
 *  result. The row field keep track of which row is the current row (or was
 *  last returned to the caller). The count field contains the total number of
 *  rows that are available in the resultset.
 *
 */
struct postgres_query_state {
	PGresult *res;
	int row;
	int count;
};
typedef struct postgres_query_state pg_query_state_t;

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
	int (*pg_db_save_obj)	(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
	int (*pg_db_delete_obj)	(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
	int (*pg_db_load_obj)	(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
	int (*pg_db_find_obj)	(pbs_db_conn_t *conn, void *state,
		pbs_db_obj_info_t *obj,
		pbs_db_query_options_t *opts);
	int (*pg_db_next_obj)	(pbs_db_conn_t *conn, void *state,
		pbs_db_obj_info_t *obj);
	int (*pg_db_del_attr_obj)(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
	int (*pg_db_add_update_attr_obj)(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
	void (*pg_db_reset_obj)(pbs_db_obj_info_t *obj);
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
#define SET_PARAM_STR(conn, itm, i)  \
        ((pg_conn_data_t *) (conn)->conn_data)->paramValues[i] = (itm); \
        if (itm) \
                ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = strlen(itm); \
        else \
                ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = 0; \
        ((pg_conn_data_t *) (conn)->conn_data)->paramFormats[i] = 0;

#define SET_PARAM_STRSZ(conn, itm, size, i)  \
        ((pg_conn_data_t *) (conn)->conn_data)->paramValues[i] = (itm); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = (size); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramFormats[i] = 0;

#define SET_PARAM_INTEGER(conn, itm, i) \
        ((pg_conn_data_t *) (conn)->conn_data)->temp_int[i] = (INTEGER) htonl(itm); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramValues[i] = \
                (char *) &(((pg_conn_data_t *) (conn)->conn_data)->temp_int[i]); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = sizeof(int); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramFormats[i] = 1;

#define SET_PARAM_BIGINT(conn, itm, i) \
        ((pg_conn_data_t *) (conn)->conn_data)->temp_long[i] = (BIGINT) htonll(itm); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramValues[i] = \
                (char *) &(((pg_conn_data_t *) (conn)->conn_data)->temp_long[i]); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = sizeof(BIGINT); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramFormats[i] = 1;

#define SET_PARAM_BIN(conn, itm, len , i)  \
        ((pg_conn_data_t *) (conn)->conn_data)->paramValues[i] = (itm); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramLengths[i] = (len); \
        ((pg_conn_data_t *) (conn)->conn_data)->paramFormats[i] = 1;

#define GET_PARAM_STR(res, row, itm, fnum)  \
		strcpy((itm), PQgetvalue((res), (row), (fnum)));

#define GET_PARAM_INTEGER(res, row, itm, fnum) \
		(itm) = ntohl(*((uint32_t *) PQgetvalue((res), (row), (fnum))));

#define GET_PARAM_BIGINT(res, row, itm, fnum) \
		(itm) = ntohll(*((uint64_t *) PQgetvalue((res), (row), (fnum))));

#define GET_PARAM_BIN(res, row, itm, fnum) \
		(itm) = PQgetvalue((res), (row), (fnum));

#define FIND_JOBS_BY_QUE 1

/* common functions */
int pg_db_prepare_job_sqls(pbs_db_conn_t *conn);
int pg_db_prepare_resv_sqls(pbs_db_conn_t *conn);
int pg_db_prepare_svr_sqls(pbs_db_conn_t *conn);
int pg_db_prepare_node_sqls(pbs_db_conn_t *conn);
int pg_db_prepare_sched_sqls(pbs_db_conn_t *conn);
int pg_db_prepare_que_sqls(pbs_db_conn_t *conn);

void pg_set_error(pbs_db_conn_t *conn, char *msg1, char *msg2);
int
pg_prepare_stmt(pbs_db_conn_t *conn, char *stmt, char *sql,
	int num_vars);
int pg_db_cmd(pbs_db_conn_t *conn, char *stmt, int num_vars);
int pg_db_cmd_ret(pbs_db_conn_t *conn, char *stmt, int num_vars);
int pg_db_query(pbs_db_conn_t *conn, char *stmt, int num_vars, PGresult **res);
unsigned long long pbs_ntohll(unsigned long long);
int convert_array_to_db_attr_list(char *raw_array, pbs_db_attr_list_t *attr_list);
int convert_db_attr_list_to_array(char **raw_array, pbs_db_attr_list_t *attr_list);
void free_db_attr_list(pbs_db_attr_list_t *attr_list);

#ifdef NAS /* localmod 005 */
int resize_buff(pbs_db_sql_buffer_t *dest, int size);
#endif /* localmod 005 */

/* job functions */
int pg_db_save_job(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_job(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
int
pg_db_find_job(pbs_db_conn_t *conn, void *st,
	pbs_db_obj_info_t *obj, pbs_db_query_options_t *opts);
int
pg_db_next_job(pbs_db_conn_t *conn, void *st,
	pbs_db_obj_info_t *obj);
int pg_db_delete_job(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

int
pg_db_save_jobscr(pbs_db_conn_t *conn,
	pbs_db_obj_info_t *obj, int savetype);
int
pg_db_load_jobscr(pbs_db_conn_t *conn,
	pbs_db_obj_info_t *obj);


/* resv functions */
int pg_db_save_resv(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_resv(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
int
pg_db_find_resv(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj,
	pbs_db_query_options_t *opts);
int pg_db_next_resv(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj);
int pg_db_delete_resv(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/* svr functions */
int pg_db_save_svr(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_svr(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/* node functions */
int pg_db_save_node(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_node(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
int
pg_db_find_node(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj,
	pbs_db_query_options_t *opts);
int pg_db_next_node(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj);
int pg_db_delete_node(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/* mominfo_time functions */
int pg_db_save_mominfo_tm(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_mominfo_tm(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);


/* queue functions */
int pg_db_save_que(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_que(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);
int
pg_db_find_que(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj,
	pbs_db_query_options_t *opts);
int pg_db_next_que(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj);
int pg_db_delete_que(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);


/* scheduler functions */
int pg_db_save_sched(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);
int pg_db_load_sched(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

int pg_db_find_sched(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj,
	pbs_db_query_options_t *opts);
int pg_db_next_sched(pbs_db_conn_t *conn, void *st, pbs_db_obj_info_t *obj);
int pg_db_delete_sched(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

int pg_db_del_attr_job(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_del_attr_sched(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_del_attr_resv(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_del_attr_svr(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_del_attr_que(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_del_attr_node(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
int pg_db_add_update_attr_node(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);
void pg_db_reset_job(pbs_db_obj_info_t *obj);
void pg_db_reset_svr(pbs_db_obj_info_t *obj);
void pg_db_reset_que(pbs_db_obj_info_t *obj);
void pg_db_reset_node(pbs_db_obj_info_t *obj);
void pg_db_reset_resv(pbs_db_obj_info_t *obj);
void pg_db_reset_sched(pbs_db_obj_info_t *obj);
void pg_db_reset_mominfo(pbs_db_obj_info_t *obj);



#ifdef	__cplusplus
}
#endif

#endif	/* _DB_POSTGRES_H */

