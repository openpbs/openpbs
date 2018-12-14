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
 * @file    pbs_db.h
 *
 * @brief
 * PBS database interface. (Functions declarations and structures)
 *
 * This header file contains functions to access the PBS data store
 * Only these functions should be used by PBS code. Actual implementation
 * of these functions are database specific and are implemented in Libdb.
 *
 * In most cases, the size of the fields in the structures correspond
 * one to one with the column size of the respective tables in database.
 * The functions/interfaces in this header are PBS Private.
 */

#ifndef _PBS_DB_H
#define	_PBS_DB_H

#include <pbs_ifl.h>
#include <sys/types.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef	__cplusplus
extern "C" {
#endif

#ifndef	MIN
#define	MIN(x, y)	(((x) < (y)) ? (x) : (y))
#endif
#ifndef	MAX
#define	MAX(x, y)	(((x) > (y)) ? (x) : (y))
#endif

#define PBS_MAXATTRNAME 64
#define PBS_MAXATTRRESC 64
#define MAX_SQL_LENGTH 8192
#define PBS_DB_COMMIT   0
#define PBS_DB_ROLLBACK 1
#define PBS_MAX_DB_CONN_INIT_ERR  500
#define MAX_SCHEMA_VERSION_LEN 9

#define PBS_UPDATE_DB_FULL 0
#define PBS_UPDATE_DB_QUICK 1
#define PBS_INSERT_DB 2

/**
 * @brief
 *  Structure used to maintain the database connection information
 *
 *  All elements of this structure are generic and are not bound to any
 *  particular database
 */
struct pbs_db_connection {
	void    *conn_db_handle;        /* opaque database handle  */
	char    *conn_info;             /* database connect string */
	char    *conn_host;             /* host */
	int     conn_timeout;           /* connection timeout (async connects) */
	int     conn_state;             /* connected? */
	int     conn_internal_state;    /* internal connection state (async connects) */
	int     conn_have_db_control;   /* can start db? */
	int     conn_db_state;          /* db up? down? starting? (async connects) */
	time_t  conn_connect_time;      /* when was connection initiated */
	int     conn_trx_nest;          /* incr/decr with each begin/end trx */
	int     conn_trx_rollback;      /* rollback flag in case of nested trx */
	int     conn_result_format;     /* 0 - text, 1 - binary */
	int     conn_trx_async;		/* 1 - async, 0 - sync, one-shot reset */
	void    *conn_db_err;           /* opaque database error store */
	void    *conn_data;             /* any other db specific data */
	void    *conn_resultset;        /* point to any results data */
	char    conn_sql[MAX_SQL_LENGTH]; /* sql buffer */
};
typedef struct pbs_db_connection pbs_db_conn_t;

/**
 * @brief
 *  Resizable sql buffer structure.
 *
 *  Used in multi inserts, reduces number of parameters in many functions
 */
struct pbs_db_sql_buffer {
	char *buff;
	int buf_len;
};
typedef struct pbs_db_sql_buffer pbs_db_sql_buffer_t;

/**
 * @brief
 * Following are a set of mapping of DATABASE vs C data types. These are
 * typedefed here to allow mapping the database data types easily.
 */
typedef short     SMALLINT;
typedef int       INTEGER;
typedef long long BIGINT;
typedef char      *TEXT;

/**
 * @brief
 *  Structure used to map database attr structure to C
 *
 */
struct pbs_db_attr_info {
	char	attr_name[PBS_MAXATTRNAME+1];
	char	attr_resc[PBS_MAXATTRRESC+1];
	TEXT    attr_value;
	INTEGER attr_flags;
};

typedef struct pbs_db_attr_info pbs_db_attr_info_t;

struct pbs_db_attr_list {
	int attr_count;
	pbs_db_attr_info_t *attributes;
};

typedef struct pbs_db_attr_list pbs_db_attr_list_t;


/**
 * @brief
 *  Structure used to map database job structure to C
 *
 */
struct pbs_db_job_info {
	char     ji_jobid[PBS_MAXSVRJOBID + 1]; /* job identifier */
	INTEGER  ji_state; /* INTEGERernal copy of state */
	INTEGER  ji_substate; /* job sub-state */
	INTEGER  ji_svrflags; /* server flags */
	INTEGER  ji_numattr; /* not used */
	INTEGER  ji_ordering; /* special scheduling ordering */
	INTEGER  ji_priority; /* INTEGERernal priority */
	BIGINT   ji_stime; /* time job started execution */
	BIGINT   ji_endtBdry; /* estimate upper bound on end time */
	char     ji_queue[PBS_MAXQUEUENAME + 1]; /* name of current queue */
	char     ji_destin[PBS_MAXROUTEDEST + 1]; /* dest from qmove/route */
	INTEGER  ji_un_type;
	INTEGER  ji_momaddr; /* host addr of Server */
	INTEGER  ji_momport; /* port # */
	INTEGER  ji_exitstat; /* job exit status from MOM */
	BIGINT   ji_quetime; /* time entered queue */
	BIGINT   ji_rteretry; /* route retry time */
	INTEGER  ji_fromsock; /* socket job coming over */
	BIGINT   ji_fromaddr; /* host job coming from   */
	char     ji_4jid[8];
	char     ji_4ash[8];
	INTEGER  ji_credtype;
	INTEGER  ji_qrank;
	BIGINT   ji_savetm;
	BIGINT   ji_creattm;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_job_info pbs_db_job_info_t;

/**
 * @brief
 *  Structure used to map database resv structure to C
 *
 */
struct pbs_db_resv_info {
	char    ri_resvid[PBS_MAXSVRJOBID + 1];
	char    ri_queue[PBS_MAXQUEUENAME + 1];
	INTEGER ri_state;
	INTEGER ri_substate;
	INTEGER ri_type;
	BIGINT  ri_stime;
	BIGINT  ri_etime;
	BIGINT  ri_duration;
	INTEGER ri_tactive;
	INTEGER ri_svrflags;
	INTEGER ri_numattr;
	INTEGER ri_resvTag;
	INTEGER ri_un_type;
	INTEGER ri_fromsock;
	BIGINT  ri_fromaddr;
	BIGINT  ri_creattm;
	BIGINT  ri_savetm;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_resv_info pbs_db_resv_info_t;

/**
 * @brief
 *  Structure used to map database server structure to C
 *
 */
struct pbs_db_svr_info {
	INTEGER sv_numjobs;
	INTEGER sv_numque;
	BIGINT  sv_jobidnumber;
	BIGINT  sv_svraddr; /* host addr of Server */
	INTEGER sv_svrport; /* port of host server */
	BIGINT  sv_creattm;
	BIGINT  sv_savetm;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_svr_info pbs_db_svr_info_t;

/**
 * @brief
 *  Structure used to map database scheduler structure to C
 *
 */
struct pbs_db_sched_info {
	char    sched_name[PBS_MAXSCHEDNAME+1];
	BIGINT  sched_creattm;
	BIGINT  sched_savetm;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_sched_info pbs_db_sched_info_t;

/**
 * @brief
 *  Structure used to map database queue structure to C
 *
 */
struct pbs_db_que_info {
	char    qu_name[PBS_MAXQUEUENAME +1];
	INTEGER qu_type;
	BIGINT  qu_ctime;
	BIGINT  qu_mtime;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_que_info pbs_db_que_info_t;

/**
 * @brief
 *  Structure used to map database node structure to C
 *
 */
struct pbs_db_node_info {
	char	nd_name[PBS_MAXSERVERNAME+1];
	INTEGER nd_index;
	BIGINT	mom_modtime;
	char	nd_hostname[PBS_MAXSERVERNAME+1];
	INTEGER nd_state;
	INTEGER nd_ntype;
	char	nd_pque[PBS_MAXSERVERNAME+1];
	BIGINT  nd_creattm;
	BIGINT  nd_svtime;
	pbs_db_attr_list_t attr_list; /* list of attributes */
};
typedef struct pbs_db_node_info pbs_db_node_info_t;

/**
 * @brief
 *  Structure used to map database mominfo_time structure to C
 *
 */
struct pbs_db_mominfo_time {
	BIGINT	mit_time;
	INTEGER mit_gen;
};
typedef struct pbs_db_mominfo_time pbs_db_mominfo_time_t;

/**
 * @brief
 *  Structure used to map database job script to C
 *
 */
struct pbs_db_jobscr_info {
	char     ji_jobid[PBS_MAXSVRJOBID + 1]; /* job identifier */
	TEXT     script;
};
typedef struct pbs_db_jobscr_info pbs_db_jobscr_info_t;

/**
 * @brief
 *  Structure used to pass database query options to database functions
 *
 *  Flags field can be used to pass any flags to a query function.
 *  Timestamp field can be used to pass a timestamp, to return rows that have
 *  a modification timestamp newer (more recent) than the timestamp passed.
 *  (Basically to return rows that have been modified since a point of time)
 *
 */
struct pbs_db_query_options {
	int	flags;
	time_t	timestamp;
};
typedef struct pbs_db_query_options pbs_db_query_options_t;

#define PBS_DB_JOB 			0
#define PBS_DB_RESV			1
#define PBS_DB_SVR			2
#define PBS_DB_NODE			3
#define PBS_DB_QUEUE			4
#define PBS_DB_JOBSCR			5
#define PBS_DB_SCHED			6
#define PBS_DB_MOMINFO_TIME		7
#define PBS_DB_NUM_TYPES		8


/* connection error code */
#define	PBS_DB_SUCCESS			0
#define PBS_DB_CONNREFUSED		1
#define PBS_DB_AUTH_FAILED		2
#define PBS_DB_CONNFAILED		3
#define PBS_DB_NOMEM			4
#define PBS_DB_STILL_STARTING	5

/* asynchronous connection states */
#define PBS_DB_CONNECT_STATE_NOT_CONNECTED	1
#define PBS_DB_CONNECT_STATE_CONNECTING		2
#define PBS_DB_CONNECT_STATE_CONNECTED		3
#define PBS_DB_CONNECT_STATE_FAILED			4

/* Database states */
#define PBS_DB_DOWN					1
#define PBS_DB_STARTING				2
#define PBS_DB_STARTED				3

/**
 * @brief
 *  Wrapper object structure. Contains a pointer to one of the several database
 *  structures.
 *
 *  Most of the database manipulation/query functions take this structure as a
 *  parmater. Depending on the contained structure type, an appropriate internal
 *  database manipulation/query function is eventually called. This allows to
 *  keep the interace simpler and generic.
 *
 */
struct pbs_db_obj_info {
	int 	pbs_db_obj_type; /* identifies the contained object type */
	union {
		pbs_db_job_info_t	*pbs_db_job;
		pbs_db_jobscr_info_t	*pbs_db_jobscr;
		pbs_db_resv_info_t	*pbs_db_resv;
		pbs_db_svr_info_t	*pbs_db_svr;
		pbs_db_que_info_t	*pbs_db_que;
		pbs_db_node_info_t	*pbs_db_node;
		pbs_db_sched_info_t	*pbs_db_sched;
		pbs_db_mominfo_time_t	*pbs_db_mominfo_tm;
	} pbs_db_un;
};
typedef struct pbs_db_obj_info pbs_db_obj_info_t;

#define PBS_DB_CNT_TIMEOUT_NORMAL		30
#define PBS_DB_CNT_TIMEOUT_INFINITE		0


/* Database start stop control commands */
#define PBS_DB_CONTROL_STATUS			"status"
#define PBS_DB_CONTROL_START			"start"
#define PBS_DB_CONTROL_STARTASYNC		"startasync"
#define PBS_DB_CONTROL_STOP			"stop"
#define PBS_DB_CONTROL_STOPASYNC		"stopasync"

/**
 * @brief
 *	Initialize a database connection structure
 *      - creates a database connection structure
 *      - Initializes various fields of the connection structure
 *      - Retrieves connection password and sets the database
 *        connect string
 *
 * @param[in]   host         - The name of the host on which database resides
 * @param[in]   timeout      - The timeout value in seconds to attempt the connection
 * @param[in]   can_start_db - Whether the database can be started, if down?
 * @param[out]  failcode     - Failure error code
 * @param[out]  errmsg       - Details of the error
 * @param[in]   len          - length of error messge variable
 *
 * @return      Initialized connection structure
 * @retval      NULL  - Failure
 * @retval      !NULL - Success, address initialized connection structure is returned
 *
 */
pbs_db_conn_t * pbs_db_init_connection(char * host, int timeout, int can_start_db, int *failcode, char *errmsg, int len);

/**
 * @brief
 *      Destroys a previously created connection structure
 *      and frees all memory associated with it.
 *
 * @param[in]   conn - Previously initialized connection structure
 *
 */
void pbs_db_destroy_connection(pbs_db_conn_t *conn);

/**
 * @brief
 *	Creates the database connect string by retreiving the
 *      database password and appending the other connection
 *      parameters
 *
 * @param[in]   host     - The hostname to connect to
 * @param[in]   timeout  - The timeout parameter of the connection
 * @param[in]   err_code - The error code in case of failure
 * @param[out]  errmsg   - Details of the error
 * @param[in]   len      - length of error messge variable
 *
 * @return      The newly allocated and populated connection string
 * @retval      NULL  - Failure
 * @retval      !NULL - Success
 *
 */
char *pbs_get_connect_string(char *host, int timeout, int *err_code, char *errmsg, int len);

/**
 * @brief
 *	Translates the error code to an error message
 *
 * @param[in]   err_code - Error code to translate
 * @param[out]  err_msg  - The translated error message (newly allocated memory)
 *
 */
void get_db_errmsg(int err_code, char **err_msg);

/**
 * @brief
 *	Connect to the database synchronously
 *
 * @param[in]   conn   - Previously initialized connection structure
 *
 * @return      Failure code
 * @retval      PBS_DB_SUCCESS  - Success
 * @retval      !PBS_DB_SUCCESS - Database error code
 *
 */
int pbs_db_connect(pbs_db_conn_t *conn);

/**
 * @brief
 *	Connect to the database asynchronously. This
 *  function needs to be called repeatedly till a connection
 *  success or failure happens.
 *
 * @param[in]   conn   - Previously initialized connection structure
 *
 * @return      Failure code
 * @retval      PBS_DB_SUCCESS  - Success
 * @retval      !PBS_DB_SUCCESS - Database error code
 *
 */
int pbs_db_connect_async(pbs_db_conn_t *conn);

/**
 * @brief
 *	Disconnect from the database and frees all allocated memory.
 *
 * @param[in]   conn - Connected database handle
 *
 */
void pbs_db_disconnect(pbs_db_conn_t *conn);


/**
 * @brief
 *	Initializes all the sqls before they can be used
 *
 * @param[in]   conn - Connected database handle
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int pbs_db_prepare_sqls(pbs_db_conn_t *conn);

/**
 * @brief
 *	Start a database transaction
 *	If a transaction is already on, just increment the transactioin nest
 *	count in the database handle object
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	isolation_level - Isolation level to set for the transaction
 * @param[in]	async - Set synchronous/asynchronous commit behavior
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int pbs_db_begin_trx(pbs_db_conn_t *conn, int isolation_level, int async);

/**
 * @brief
 *	End a database transaction
 *	Decrement the transaction nest count in the connection object. If the
 *	count reaches zero, then end the database transaction.
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	commit - If commit is PBS_DB_COMMIT, then the transaction is
 *			    commited. If commi tis PBS_DB_ROLLBACK, then the
 *			    transaction is rolled back.
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int pbs_db_end_trx(pbs_db_conn_t *conn, int commit);


/**
 * @brief
 *	Initialize a multirow database cursor
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - The pointer to the wrapper object which
 *              describes the PBS object (job/resv/node etc) that is wrapped
 *              inside it.
 * @param[in]	pbs_db_query_options_t - Pointer to the options object that can
 *              contain the flags or timestamp which will effect the query.
 *
 * @return      void *
 * @retval      Not NULL  - success. Returns the opaque cursor state handle
 * @retval      NULL      - Failure
 *
 */
void *
pbs_db_cursor_init(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj,
	pbs_db_query_options_t *opts);

/**
 * @brief
 *	Get the next row from the cursor. It also is used to get the first row
 *	from the cursor as well.
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	state - The cursor state handle that was obtained using the
 *                   	pbs_db_cursor_init call.
 * @param[out]	pbs_db_obj_info_t - The pointer to the wrapper object which
 *              describes the PBS object (job/resv/node etc) that is wrapped
 *              inside it. The row data is loaded into this parameter.
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 * @retval       1  -  Success but no more rows
 *
 */
int
pbs_db_cursor_next(pbs_db_conn_t *conn, void *state,
	pbs_db_obj_info_t *obj);

/**
 * @brief
 *	Close a cursor that was earlier opened using a pbs_db_cursor_init call.
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	state - The cursor state handle that was obtained using the
 *                      pbs_db_cursor_init call.
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
void pbs_db_cursor_close(pbs_db_conn_t *conn, void *state);

/**
 * @brief
 *	Get the number of rows from a cursor
 *
 * @param[in]	state - The opaque cusor state handle
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int pbs_db_get_rowcount(void *state);

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
int pbs_db_execute_str(pbs_db_conn_t *conn, char *sql);

/**
 * @brief
 *	Insert a new object into the database
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 *              (and data) to insert
 * @param[in]   savetype - Update or Insert
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 *
 */
int pbs_db_save_obj(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, int savetype);

/**
 * @brief
 *	Delete an existing object from the database
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 *              (and data) to delete
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 * @retval       1 -  Success but no rows deleted
 *
 */
int pbs_db_delete_obj(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/**
 * @brief
 *	Delete attributes of an existing object from the database
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 * @param[in]   obj_id - The object id of the parent (jobid, node-name etc)
 * @param[in]	attr_list - List of attributes to remove
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 * @retval       1 -  Success but no rows deleted
 *
 */

int pbs_db_delete_attr_obj(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);

/**
 * @brief
 *	Update/add attributes of an existing object to the database
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 * @param[in]   obj_id - The object id of the parent (jobid, node-name etc)
 * @param[in]	attr_list - List of attributes to Update/add
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 * @retval       1 -  Success but no rows deleted
 *
 */
int pbs_db_add_update_attr_obj(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj, void *obj_id, pbs_db_attr_list_t *attr_list);

/**
 * @brief
 *	Load a single existing object from the database
 *
 * @param[in]     conn - Connected database handle
 * @param[in/out] pbs_db_obj_info_t - Wrapper object that describes the object
 *                (and data) to load. This parameter used to return the data about
 *                the object loaded
 *
 * @return      int
 * @retval      -1  - Failure
 * @retval       0  - success
 * @retval       1 -  Success but no rows loaded
 *
 */
int pbs_db_load_obj(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/**
 * @brief
 *	Cleans up memory associated with a resultset (tht was returned from a
 *	call to a query)
 *
 * @param[in]	conn - Connected database handle
 *
 * @return      void
 *
 */
void pbs_db_cleanup_resultset(pbs_db_conn_t *conn);

/**
 * @brief
 *	Initialize a multi-attribute insert operation
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 *              (and data) to insert
 * @param[in]	pbs_db_sql_buffer_t - Simple resizable buffer that is created
 *              by the caller and used by internal functions
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int
pbs_db_insert_multiattr_start(pbs_db_conn_t *conn,
	pbs_db_obj_info_t *obj,
	pbs_db_sql_buffer_t *buff);

/**
 * @brief
 *	Add an attribute to the multi-attribute insert statment created eariler
 *
 * @param[in]	  conn - Database connection handle
 * @param[in]	  firsttime - Is it being called for the firsttime?
 * @param[in]	  info - The database object to be inserted
 * @param[in/out] sql  - The buffer to used to hold the final sql query that
 *                       is being formed by calling this function multiple times.
 *
 * @param[in]	part - This buffer is used for hold the a "part" of the whole
 *              sql query. This is eventually added to the sql buffer.
 *	            Thus, part is a "work" buffer, and "sql" hold the final
 *              sql formed, that would be executed at the end.
 *
 * @return      Error code
 * @retval	-1 - Failure
 * @retval	 0 - Success
 *
 */
int
pbs_db_insert_multiattr_add(pbs_db_conn_t *conn, pbs_db_obj_info_t *info,
	int firsttime, pbs_db_sql_buffer_t *sql,
	pbs_db_sql_buffer_t *part);

/**
 * @brief
 *	Execute the multi-line insert statement that has been created earlier.
 *
 * @param[in]	conn - Connected database handle
 * @param[in]	pbs_db_obj_info_t - Wrapper object that describes the object
 *              (and data) to insert
 * @param[in]	pbs_db_sql_buffer_t - Simple resizable buffer that is created
 *              by the caller and used by internal functions
 *
 * @return      int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int
pbs_db_insert_multiattr_execute(pbs_db_conn_t *conn,
	pbs_db_obj_info_t *obj,
	pbs_db_sql_buffer_t *buff);

/**
 * @brief
 *	Delete ALL data from the pbs database, used in RECOV_CREATE mode
 *
 * @param[in]	conn - Connected database handle
 *
 * @return	    int
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
int pbs_db_truncate_all(pbs_db_conn_t *conn);

/**
 * @brief
 *	Function to check whether data-service is running
 *
 * @return      Error code
 * @retval	-1 - Error in routine
 * @retval	0  - Data service running
 * @retval	1  - Data service not running
 *
 */
int pbs_status_db(char **errmsg);

/**
 * @brief
 *	Start the database daemons/service in synchronous mode.
 *  This function waits for the database to complete startup.
 *
 * @param[out]	errmsg - returns the startup error message if any
 *
 * @return	    int
 * @retval       0     - success
 * @retval       !=0   - Failure
 *
 */
int pbs_startup_db(char **errmsg);

/**
 * @brief
 *	Start the database daemons/service in asynchronous mode.
 * This function does not wait for the database to complete startup.
 *
 * @param[out]	errmsg - returns the startup error message if any
 *
 * @return	    int
 * @retval       0     - success
 * @retval       !=0   - Failure
 *
 */
int pbs_startup_db_async(char **errmsg);

/**
 * @brief
 *	Stop the database daemons/service
 *
 * @param[out]	errmsg - returns the db  error message if any
 *
 * @return      Error code
 * @retval      !=0 - Failure
 * @retval       0  - Success
 *
 */
int pbs_shutdown_db(char **errmsg);

/**
 * @brief
 *	Function to stop the database service/daemons
 *	in an asynchronous manner.
 *	This passes the parameter STOPASYNC to the
 *	pbs_dataservice script, which initiates the
 *	the database stop and returns without waiting.
 *
 * @param[out]	errmsg - returns the db error message if any
 *
 * @return      Error code
 * @retval       !=0 - Failure
 * @retval        0  - Success
 *
 */
int pbs_shutdown_db_async(char **errmsg);

/**
 * @brief
 *	Retrieves the database user. The database user-id is retrieved from
 *	the file under server_priv, called db_user.
 *	If a db_user file is not found under server_priv, then pbsdata is
 *	returned as the default db user.
 *
 * @param[out]  errmsg - Details of the error
 * @param[in]   len    - length of error messge variable
 *
 * @return      dbuser String
 * @retval	 NULL - Failed to retrieve user-id
 * @retval	!NULL - Pointer to allocated memory with user-id string.
 *			Caller should free this memory after usage.
 *
 */
char *pbs_get_dataservice_usr(char *errmsg, int len);

/**
 * @brief
 *	Retrieve (after decrypting) the database password for a database user
 *
 * @param[in]	user - The name of the user whose password to retrieve
 * @param[out]  errmsg - Details of the error
 * @param[in]   len    - length of error messge variable
 *
 * @return      char * - The password of the user.
 *                       Caller should free returned address
 * @retval       0  - success
 * @retval      -1  - Failure
 *
 */
char *pbs_get_dataservice_password(char *user, char *errmsg, int len);


/**
 * @brief
 *	Check whether connection to pbs dataservice is fine
 *
 * @param[in]	conn - Connected database handle
 *
 * @return      Connection status
 * @retval      -1 - Connection down
 * @retval       0 - Connection fine
 *
 */
int pbs_db_is_conn_ok(pbs_db_conn_t *conn);


/**
 * @brief
 *	Function to escape special characters in a string
 *	before using as a column value in the database
 *
 * @param[in]	conn - handle to the database connection
 * @param[in]	str - the string to escape
 *
 * @return     escaped string
 * @retval     NULL - failure to escape string
 * @retval     !NULL - newly allocated area holding escaped string,
 *                     caller needs to free
 *
 */
char *pbs_db_escape_str(pbs_db_conn_t *conn, char *str);

/**
 * @brief
 *	Free the connect string associated with a connection
 *
 * @param[in]   conn - Previously initialized connection structure
 *
 */
void pbs_db_free_conn_info(pbs_db_conn_t *conn);


/**
 * @brief
 *	Retrieve the Datastore schema version (maj, min)
 *
 * @param[out]   db_maj_ver - return the major schema version
 * @param[out]   db_min_ver - return the minor schema version
 *
 * @return     Error code
 * @retval     -1 - Failure
 * @retval     0  - Success
 *
 */
int pbs_db_get_schema_version(pbs_db_conn_t *conn, int *db_maj_ver, int *db_min_ver);

/**
 * @brief
 *	Attempt to mail a message to "mail_from" (administrator), shut down
 *	the database, close the log and exit the Server.   Called when a
 *	database save fails
 *
 * @param[in]	txt  - message to send via mail
 */
void panic_stop_db(char *txt);


/**
 * @brief
 *	Get the svrid corresponding to the given svr hostname
 *
 * @param[in]	conn - The database connection handle
 * @param[in]	hostname - The svr hostname
 *
 * @return      The database svrid (to be freed by caller)
 * @retval	-NULL  - Failure
 *		-!NULL - Success
 *
 */
char* pbs_db_get_svr_id(pbs_db_conn_t *conn, char *hostname);

/**
 * @brief
 *	Delete all the server attributes from the database
 *
 * @param[in]	conn - Connection handle
 * @param[in]	obj  - server information
 *
 * @return      Error code
 * @retval	-1 - Failure
 * @retval	 0 - Success
 * @retval	 1 - Success but no rows deleted
 *
 */
int pg_db_delete_svrattr(pbs_db_conn_t *conn, pbs_db_obj_info_t *obj);

/**
 * @brief
 *	resize a buffer. The buffer structure stores the current size of the
 *	buffer. This function determines how much of that buffer size is
 *	free and expands the buffer accordingly
 *
 * @param[in]	dest - buffer to resize
 * @param[in]	size - Size of buffer required
 *
 * @return      int Error code
 * @retval	 0 - Success
 * @retval	-1 - Failure to allocate new memory
 *
 */
int resize_buff(pbs_db_sql_buffer_t *dest, int size);

/**
 * @brief
 *	Resets database object
 *
 * @param[in]	obj - db object
 *
 * @return      None
 *
 */
void pbs_db_reset_obj(pbs_db_obj_info_t *obj);

#ifdef	__cplusplus
}
#endif

#endif	/* _PBS_DB_H */
