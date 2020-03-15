/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
#ifndef	_LIBPBS_H
#define	_LIBPBS_H
#ifdef	__cplusplus
extern "C" {
#endif


/*	libpbs.h

 The header file for private information in the pbs command
 interface library

 */

#ifndef _STDLIB_H
#include <stdlib.h>
#endif	/* _STDLIB_H */
#ifndef _STRING_H
#include <string.h>
#endif	/* _STRING_H */
#ifndef _MEMORY_H
#include <memory.h>
#endif	/* _MEMORY_H */
#include <limits.h>

#include "pbs_ifl.h"
#include "list_link.h"
#include "pbs_error.h"
#include "pbs_internal.h"
#include "pbs_client_thread.h"
#include "net_connect.h"
#include "dis.h"

#define PBS_BATCH_PROT_TYPE	2
#define PBS_BATCH_PROT_VER	1
/* #define PBS_REQUEST_MAGIC (56) */
/* #define PBS_REPLY_MAGIC   (57) */
#define SCRIPT_CHUNK_Z (65536)
#ifndef TRUE
#define TRUE 1
#define FALSE 0
#endif
#ifndef EOF
#define EOF (-1)
#endif

/* enums for standard job files */
enum job_file {
	JScript,
	StdIn,
	StdOut,
	StdErr,
	Chkpt
};

#define MH(type) (type *)malloc(sizeof(type))
#define M(var,type) if( (var = MH(type)) == NULL ) \
	{ return PBSE_SYSTEM; }
#define STRLEN(s) ((s==NULL)?0:strlen(s))
#define Str2QB(s) ((s==NULL)?NULL:str2qb(s, strlen(s), 0))
#define QB2Str(q) ((q==NULL)?NULL:qb2str(q))

/* This variable has been moved to Thread local storage
 * The define points to a function pointer which locates
 * the actual variable from the TLS of the calling thread
 */
#ifndef __PBS_CURRENT_USER
#define __PBS_CURRENT_USER
extern char *__pbs_current_user_location(void);
#define pbs_current_user (__pbs_current_user_location ())
#endif

/*
 *time_t	pbs_tcp_timeout = PBS_DIS_TCP_TIMEOUT_SHORT;
 *int           pbs_tcp_interrupt = 0;
 *int           pbs_tcp_errno;
 */

/* These variables have been moved to Thread local storage
 * The defines point to a function pointer which locates
 * the actual variables from the TLS of the calling thread
 */
#ifndef __PBS_TCP_TIMEOUT
#define __PBS_TCP_TIMEOUT
extern time_t * __pbs_tcptimeout_location(void);
#define pbs_tcp_timeout (*__pbs_tcptimeout_location ())
#endif

#ifndef __PBS_TCP_INTERRUPT
#define __PBS_TCP_INTERRUPT
extern int * __pbs_tcpinterrupt_location(void);
#define pbs_tcp_interrupt (*__pbs_tcpinterrupt_location ())
#endif

#ifndef __PBS_TCP_ERRNO
#define __PBS_TCP_ERRNO
extern int * __pbs_tcperrno_location(void);
#define pbs_tcp_errno (*__pbs_tcperrno_location ())
#endif

extern char pbs_current_group[];

#define NCONNECTS 50 /* max connections per client */
#define PBS_MAX_CONNECTIONS 5000 /* Max connections in the connections array */
#define PBS_LOCAL_CONNECTION INT_MAX

typedef struct pbs_conn {
	int ch_errno;			/* last error on this connection */
	char *ch_errtxt;		/* pointer to last server error text	*/
	pthread_mutex_t ch_mutex;	/* serialize connection between threads */
	pbs_tcp_chan_t *ch_chan;	/* pointer tcp chan structure for this connection */
} pbs_conn_t;

int destroy_connection(int);
int set_conn_errtxt(int, const char *);
char * get_conn_errtxt(int);
int set_conn_errno(int, int);
int get_conn_errno(int);
pbs_tcp_chan_t * get_conn_chan(int);
int set_conn_chan(int, pbs_tcp_chan_t *);
pthread_mutex_t * get_conn_mutex(int);


/* max number of preempt orderings */
#define PREEMPT_ORDER_MAX 20

/* PBS Batch Reply Structure		   */
/* structures that make up the reply union */

struct brp_select {		/* reply to Select Job Request */
	struct brp_select *brp_next;
	char		   brp_jobid[PBS_MAXSVRJOBID+1];
};

struct brp_status {		/* reply to Status Job/Queue/Server Request */
	pbs_list_link brp_stlink;
	int	  brp_objtype;
	char	  brp_objname[(PBS_MAXSVRJOBID > PBS_MAXDEST ?
		PBS_MAXSVRJOBID : PBS_MAXDEST) + 1];
	pbs_list_head brp_attr;		/* head of svrattrlist */
};

struct brp_cmdstat {
	struct brp_cmdstat * brp_stlink;
	int	  brp_objtype;
	char	  brp_objname[(PBS_MAXSVRJOBID > PBS_MAXDEST ?
		PBS_MAXSVRJOBID : PBS_MAXDEST) + 1];
	struct attrl *brp_attrl;
};

struct brp_rescq {            /* reply to Resource Query Request */
	int      brq_number;	/* number of items in following arrays */
	int     *brq_avail;
	int     *brq_alloc;
	int     *brq_resvd;
	int     *brq_down;
};

struct rq_preempt {
	int			count;
	preempt_job_info	*ppj_list;
};

typedef struct rq_preempt brp_preempt_jobs;

/*
 * the following is the basic Batch Reply structure
 */

#define BATCH_REPLY_CHOICE_NULL		1	/* no reply choice, just code */
#define BATCH_REPLY_CHOICE_Queue	2	/* Job ID, see brp_jid	  */
#define BATCH_REPLY_CHOICE_RdytoCom	3	/* select, see brp_jid    */
#define BATCH_REPLY_CHOICE_Commit	4	/* commit, see brp_jid	  */
#define BATCH_REPLY_CHOICE_Select	5	/* select, see brp_select */
#define BATCH_REPLY_CHOICE_Status	6	/* status, see brp_status */
#define BATCH_REPLY_CHOICE_Text		7	/* text,   see brp_txt	  */
#define BATCH_REPLY_CHOICE_Locate	8	/* locate, see brp_locate */
#define BATCH_REPLY_CHOICE_RescQuery	9	/* Resource Query         */
#define BATCH_REPLY_CHOICE_PreemptJobs	10	/* Preempt Job            */

struct batch_reply {
	int	brp_code;
	int	brp_auxcode;
	int	brp_choice;	/* the union discriminator */
	union {
		char	  brp_jid[PBS_MAXSVRJOBID+1];
		struct brp_select *brp_select;	/* select replies */
		pbs_list_head 	   brp_status;	/* status (svr) replies */
		struct brp_cmdstat *brp_statc;  /* status (cmd) replies) */
		struct {
			int   brp_txtlen;
			char *brp_str;
		} brp_txt;		/* text and credential reply */
		char	  brp_locate[PBS_MAXDEST+1];
		struct brp_rescq brp_rescq;	/* query resource reply */
		brp_preempt_jobs brp_preempt_jobs;	/* preempt jobs reply */
	} brp_un;
};

/*
 * The Batch Request ID numbers
 */

#define PBS_BATCH_Connect	0
#define PBS_BATCH_QueueJob	1
#if 0	/* 5_2 style cred */
#define PBS_BATCH_JobCred	2
#endif
#define PBS_BATCH_jobscript	3
#define PBS_BATCH_RdytoCommit	4
#define PBS_BATCH_Commit	5
#define PBS_BATCH_DeleteJob	6
#define PBS_BATCH_HoldJob	7
#define PBS_BATCH_LocateJob	8
#define PBS_BATCH_Manager	9
#define PBS_BATCH_MessJob	10
#define PBS_BATCH_ModifyJob	11
#define PBS_BATCH_MoveJob	12
#define PBS_BATCH_ReleaseJob	13
#define PBS_BATCH_Rerun		14
#define PBS_BATCH_RunJob	15
#define PBS_BATCH_SelectJobs	16
#define PBS_BATCH_Shutdown	17
#define PBS_BATCH_SignalJob	18
#define PBS_BATCH_StatusJob	19
#define PBS_BATCH_StatusQue	20
#define PBS_BATCH_StatusSvr	21
#define PBS_BATCH_TrackJob	22
#define PBS_BATCH_AsyrunJob	23
#define PBS_BATCH_Rescq		24
#define PBS_BATCH_ReserveResc	25
#define PBS_BATCH_ReleaseResc	26
#define PBS_BATCH_FailOver	27
#define PBS_BATCH_StageIn	48
/* Unused -- #define PBS_BATCH_AuthenResvPort 49 */
#define PBS_BATCH_OrderJob	50
#define PBS_BATCH_SelStat	51
#define PBS_BATCH_RegistDep	52
#define PBS_BATCH_CopyFiles	54
#define PBS_BATCH_DelFiles	55
#define PBS_BATCH_JobObit	56
#define PBS_BATCH_MvJobFile	57
#define PBS_BATCH_StatusNode	58
#define PBS_BATCH_Disconnect	59
#if 0	/* 5_2 old style cred */
#define PBS_BATCH_CopyFiles_Cred	60
#define PBS_BATCH_DelFiles_Cred 	61
#endif
#define PBS_BATCH_JobCred		62
#define PBS_BATCH_CopyFiles_Cred	63
#define PBS_BATCH_DelFiles_Cred		64
#define PBS_BATCH_GSS_Context		65 /* Deprecated */
#define PBS_BATCH_SubmitResv	70
#define PBS_BATCH_StatusResv	71
#define PBS_BATCH_DeleteResv	72
#define PBS_BATCH_UserCred	73
#define PBS_BATCH_UserMigrate	74
#define PBS_BATCH_ConfirmResv   75
#define PBS_BATCH_DefSchReply   80
#define PBS_BATCH_StatusSched   81
#define PBS_BATCH_StatusRsc	82
#define PBS_BATCH_StatusHook	83
#define PBS_BATCH_PySpawn	84
#define PBS_BATCH_CopyHookFile	85
#define PBS_BATCH_DelHookFile	86
#define PBS_BATCH_MomRestart	87
/* Unused -- #define PBS_BATCH_AuthExternal	88 */
#define PBS_BATCH_HookPeriodic  89
#define PBS_BATCH_RelnodesJob	90
#define PBS_BATCH_ModifyResv	91
#define PBS_BATCH_ResvOccurEnd	92
#define PBS_BATCH_PreemptJobs	93
#define PBS_BATCH_Cred		94
#define PBS_BATCH_Authenticate	95

#define PBS_BATCH_FileOpt_Default	0
#define PBS_BATCH_FileOpt_OFlg		1
#define PBS_BATCH_FileOpt_EFlg		2

#define PBS_IFF_CLIENT_ADDR	"PBS_IFF_CLIENT_ADDR"

/* time out values for tcp_dis read/write */

#define PBS_DIS_TCP_TIMEOUT_CONNECT  10
#define PBS_DIS_TCP_TIMEOUT_REPLY    10
#define PBS_DIS_TCP_TIMEOUT_SHORT    30
#define PBS_DIS_TCP_TIMEOUT_RERUN    45	/* timeout used in pbs_rerunjob() */
#define PBS_DIS_TCP_TIMEOUT_LONG    600
#define PBS_DIS_TCP_TIMEOUT_VLONG 10800

#define FAILOVER_Register        0  /* secondary server register with primary */
#define FAILOVER_HandShake       1  /* handshake from secondary to primary    */
#define FAILOVER_PrimIsBack      2  /* Primary is taking control again        */
#define FAILOVER_SecdShutdown    3  /* Primary going down, secondary go down  */
#define FAILOVER_SecdGoInactive  4  /* Primary down, secondary go inactive    */
#define FAILOVER_SecdTakeOver    5  /* Primary down, secondary take over      */

extern int is_compose(int stream, int command);
extern int is_compose_cmd(int stream, int command, char **msgid);
extern void PBS_free_aopl(struct attropl * aoplp);
extern void advise(char *, ...);
extern int PBSD_rdytocmt(int connect, char *jobid, int rpp, char **msgid);
extern int PBSD_commit(int connect, char *jobid, int rpp, char **msgid);
extern int PBSD_jcred(int connect, int type, char *buf, int len, int rpp, char **msgid);
extern int PBSD_user_migrate(int connect, char *tohost);
extern int PBSD_jscript(int connect, char *script_file, int rpp, char **msgid);
extern int PBSD_jscript_direct(int connect, char *script, int rpp, char **msgid);
extern int PBSD_copyhookfile(int connect, char *hook_filepath, int rpp, char **msgid);
extern int PBSD_delhookfile(int connect, char *hook_filename, int rpp, char **msgid);
extern int PBSD_mgr_put(int connect, int func, int cmd, int objtype,
	char *objname, struct attropl *al, char *extend, int rpp, char **msgid);
extern int PBSD_manager  (int connect, int func, int cmd,
	int objtype, char *objname, struct attropl *al, char *extend);
extern int PBSD_msg_put(int connect, char *jobid, int fileopt,
	char *msg, char *extend, int rpp, char **msgid);
extern int PBSD_relnodes_put(int connect, char *jobid,
	char *node_list, char *extend, int rpp, char **msgid);
extern int PBSD_py_spawn_put(int connect, char *jobid,
	char **argv, char **envp, int rpp, char **msgid);
extern int PBSD_sig_put(int connect, char *jobid, char *signal, char *extend, int rpp, char **msgid);
extern int PBSD_term_put(int connect, int manner, char *extend);
extern int PBSD_jobfile(int connect, int req_type, char *path,
	char *jobid, enum job_file which, int rpp, char **msgid);

extern int PBSD_status_put(int c, int func, char *id,
	struct attrl *attrib, char *extend, int rpp, char **msgid);
extern struct batch_reply *PBSD_rdrpy(int connect);
extern struct batch_reply *PBSD_rdrpy_sock(int sock, int *rc);
struct batch_reply *PBSD_rdrpyRPP(int stream);
extern void PBSD_FreeReply(struct batch_reply *);
extern struct batch_status *PBSD_status(int c, int function,
	char *objid, struct attrl *attrib, char *extend);
extern preempt_job_info *PBSD_preempt_jobs(int c, char **preempt_jobs_list);

extern struct batch_status *PBSD_status_get(int c);
extern char * PBSD_queuejob(int c, char *j, char *d,
	struct attropl *a, char *ex, int rpp, char **msgid);
extern int decode_DIS_svrattrl(int sock, pbs_list_head *phead);
extern int decode_DIS_attrl(int sock, struct attrl **ppatt);
extern int decode_DIS_JobId(int socket, char *jobid);
extern int decode_DIS_replyCmd(int socket, struct batch_reply *);

extern int encode_DIS_JobCred(int socket, int type, char *cred, int len);
extern int encode_DIS_UserCred(int socket, char *user, int type, char *cred, int len);
extern int encode_DIS_UserMigrate(int socket, char *tohost);
extern int encode_DIS_JobFile(int socket, int, char *, int, char *, int);
extern int encode_DIS_JobId(int socket, char *);
extern int encode_DIS_Manage(int socket, int cmd, int objt,
	char *, struct attropl *);
extern int encode_DIS_MessageJob(int socket, char *jid, int fopt, char *m);
extern int encode_DIS_MoveJob(int socket, char *jid, char *dest);
extern int encode_DIS_ModifyResv(int socket, char *resv_id, struct attropl *aoplp);
extern int encode_DIS_RelnodesJob(int socket, char *jid, char *node_list);
extern int encode_DIS_PySpawn(int socket, char *jid, char **argv, char **envp);
extern int encode_DIS_QueueJob(int socket, char *jid,
	char *dest, struct attropl *);
extern int encode_DIS_SubmitResv(int sock, char *resv_id, struct attropl *aoplp);
extern int encode_DIS_JobCredential(int sock, int type, char *buf, int len);
extern int encode_DIS_ReqExtend(int socket, char *extend);
extern int encode_DIS_ReqHdr(int socket, int reqt, char *user);
extern int encode_DIS_Rescq(int socket, char **rlist, int num);
extern int encode_DIS_Run(int socket, char *jid, char *where,
	unsigned long resch);
extern int encode_DIS_ShutDown(int socket, int manner);
extern int encode_DIS_SignalJob(int socket, char *jid, char *sig);
extern int encode_DIS_Status(int socket, char *objid, struct attrl *);
extern int encode_DIS_attrl(int socket, struct attrl *);
extern int encode_DIS_attropl(int socket, struct attropl *);
extern int encode_DIS_CopyHookFile(int, int, char *, int, char *);
extern int encode_DIS_DelHookFile(int, char *);
extern int encode_DIS_PreemptJobs(int socket, char **preempt_jobs_list);

extern char *PBSD_submit_resv(int connect, char *resv_id,
	struct attropl *attrib, char *extend);
extern int DIS_reply_read(int socket, struct batch_reply *preply, int rpp);
extern void pbs_authors(void);
extern int tcp_pre_process(conn_t *);
extern char *PBSD_modify_resv(int connect, char *resv_id,
	struct attropl *attrib, char *extend);

extern int PBSD_cred(int c, char *rq_credid, char *jobid, int cred_type, char *data, long validity, int rpp, char **msgid);

int tcp_send_auth_req(int sock, unsigned int port, char *user);

#ifdef	__cplusplus
}
#endif
#endif /* _LIBPBS_H */
