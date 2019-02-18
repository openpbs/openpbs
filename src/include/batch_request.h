/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
#ifndef	_BATCH_REQUEST_H
#define	_BATCH_REQUEST_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * Definition of basic batch request and reply strutures
 *
 * The basic batch request structure holds certain useful information
 * and a union of the "encode method" independent batch request data.
 *
 * This data is obtained by the encode dependent routine.
 *
 * Other required header files:
 *	"list_link.h"
 *	"server_limits.h"
 *	"attribute.h"
 *	"credential.h"
 *
 * First we define the reply structure as it is contained within the
 * request structure.
 */

#include "libpbs.h"

/*
 * The rest of this stuff is for the Batch Request Structure
 */

#define PBS_SIGNAMESZ 16

/*
 * The following strutures make up the union of encode independent
 * request data.
 *
 * The list of attributes, used in QueueJob, SelectJobs, PullJobs, and
 * Manager is an svrattrlist structure defined in "attribute.h"
 */

/* QueueJob */

struct rq_queuejob {
	char		   rq_destin[PBS_MAXDEST+1];
	char		   rq_jid[PBS_MAXSVRJOBID+1];
	pbs_list_head	   rq_attr;	/* svrattrlist */
};

/* JobCredential */

struct rq_jobcred {
	int		   rq_type;
	long		   rq_size;
	char		  *rq_data;
};

/* UserCredential */

struct rq_usercred {
	char 	  	   rq_user[PBS_MAXUSER+1];
	int		   rq_type;
	long		   rq_size;
	char		  *rq_data;
};

/* UserMigrate */

struct rq_user_migrate {
	char		   rq_tohost[PBS_MAXHOSTNAME+1];
};

/* Job File */

struct rq_jobfile {
	int	 rq_sequence;
	int	 rq_type;
	long	 rq_size;
	char	 rq_jobid[PBS_MAXSVRJOBID+1];
	char	*rq_data;
};

/* Hook File */

struct rq_hookfile {
	int	 rq_sequence;
	long	 rq_size;
	char	 rq_filename[MAXPATHLEN+1];
	char	*rq_data;
};

/*
 * job or destination id - used by RdyToCommit, Commit, RerunJob,
 * status ..., and locate job - is just a char *
 *
 * Manage - used by Manager, DeleteJob, ReleaseJob, ModifyJob
 */

struct rq_manage {
	int	     rq_cmd;
	int	     rq_objtype;
	char	     rq_objname[PBS_MAXSVRJOBID+1];
	pbs_list_head    rq_attr;	/* svrattrlist */
};

/* HoldJob -  plus preference flag */

struct rq_hold {
	struct rq_manage rq_orig;
	int		 rq_hpref;
};

/* MessageJob */

struct rq_message  {
	int	 rq_file;
	char	 rq_jid[PBS_MAXSVRJOBID+1];
	char	*rq_text;
};

/* RelnodesJob */

struct rq_relnodes  {
	char	 rq_jid[PBS_MAXSVRJOBID+1];
	char	*rq_node_list;
};

/* PySpawn */

struct rq_py_spawn  {
	char	rq_jid[PBS_MAXSVRJOBID+1];
	char	**rq_argv;
	char	**rq_envp;
};

/* MoveJob */

struct rq_move {
	char	rq_jid[PBS_MAXSVRJOBID+1];
	char	rq_destin[(PBS_MAXSVRJOBID > PBS_MAXDEST ? PBS_MAXSVRJOBID:PBS_MAXDEST)+1];
};

/* Resource Query/Reserve/Free */

struct rq_rescq {
	int     rq_rhandle;
	int     rq_num;
	char  **rq_list;
};

/* RunJob */

struct rq_runjob {
	char	rq_jid[PBS_MAXSVRJOBID+1];
	char   *rq_destin;
	unsigned long rq_resch;
};


/* SignalJob */

struct rq_signal {
	char	rq_jid[PBS_MAXSVRJOBID+1];
	char	rq_signame[PBS_SIGNAMESZ+1];
};

/* Status (job, queue, server, hook) */

struct rq_status {
	char    *rq_id;		/* allow mulitple (job) ids */
	pbs_list_head rq_attr;
};

/* Select Job  and selstat */

struct rq_selstat {
	pbs_list_head rq_selattr;
	pbs_list_head rq_rtnattr;
};


/* TrackJob */

struct rq_track {
	int	 rq_hopcount;
	char	 rq_jid[PBS_MAXSVRJOBID+1];
	char	 rq_location[PBS_MAXDEST+1];
	char	 rq_state[2];
};

/* RegisterDependentJob */

struct rq_register {
	char	rq_owner[PBS_MAXUSER+1];
	char	rq_svr[PBS_MAXSERVERNAME+1];
	char	rq_parent[PBS_MAXSVRJOBID+1];
	char	rq_child[PBS_MAXCLTJOBID+1];	/* need separate entry for */
	int	rq_dependtype;			/* from server_name:port   */
	int	rq_op;
	long	rq_cost;
};


/* Authenticate resv_port */
struct rq_authen_resvport {
	unsigned int    rq_port;
};

/* Authenticate using external mechanism (e.g. Munge/AMS etc) */
struct rq_authen_external {
	unsigned char rq_auth_type;
	union {
		struct {
			char rq_authkey[PBS_AUTH_KEY_LEN];
		} rq_munge;
	} rq_authen_un; /* allows easy adding other external authentications in future */
};

/* Deferred Scheduler Reply */
struct rq_defschrpy {
	int   rq_cmd;
	char *rq_id;
	int   rq_err;
	char *rq_txt;
};

/* Copy/Delete Files (Server -> MOM Only) */

#define STDJOBFILE    1
#define JOBCKPFILE    2
#define STAGEFILE     3

#define STAGE_DIR_IN  0
#define STAGE_DIR_OUT 1

#define STAGE_DIRECTION 	1	/* mask for setting/extracting direction of file copy from rq_dir */
#define STAGE_JOBDIR    	2	/* mask for setting/extracting "sandbox" mode flag from rq_dir */

struct rq_cpyfile {
	char	  rq_jobid[PBS_MAXSVRJOBID+1];	  /* used in Copy & Delete */
	char	  rq_owner[PBS_MAXUSER+1];	  /* used in Copy only	   */
	char 	  rq_user[PBS_MAXUSER+1]; 	  /* used in Copy & Delete */
	char 	  rq_group[PBS_MAXGRPN+1];	  /* used in Copy only     */
	int 	  rq_dir;       		  /* direction and sandbox flags: used in Copy & Delete */
	pbs_list_head rq_pair;	/* list of rqfpair,  used in Copy & Delete */
};

struct rq_cpyfile_cred {
	struct	rq_cpyfile	rq_copyfile;	/* copy/delete info */
	int			rq_credtype;	/* cred type */
	size_t			rq_credlen;	/* credential length bytes */
	char			*rq_pcred;	/* encrpyted credential */
};

struct rq_momrestart {
	char		rq_momhost[PBS_MAXHOSTNAME+1];
	unsigned int	rq_port;
};

struct rqfpair {
	pbs_list_link	 fp_link;
	int		 fp_flag;	/* 1 for std[out|err] 2 for stageout */
	char		*fp_local;	/* used in Copy & Delete */
	char		*fp_rmt;	/* used in Copy only     */
};


/*
 * ok we now have all the individual request structures defined,
 * so here is the union ...
 */

struct batch_request {
	pbs_list_link rq_link;	/* linkage of all requests 		*/
	struct batch_request * rq_parentbr;
	/* parent request for job array request */
	int	  rq_refct;	/* reference count - child requests     */
	int	  rq_type;	/* type of request			*/
	int	  rq_perm;	/* access permissions for the user	*/
	int	  rq_fromsvr;	/* true if request from another server	*/
	int	  rq_conn;	/* socket connection to client/server	*/
	int	  rq_orgconn;	/* original socket if relayed to MOM	*/
	int	  rq_extsz;	/* size of "extension" data		*/
	long	  rq_time;	/* time batch request created		*/
	char	  rq_user[PBS_MAXUSER+1];     /* user name request is from    */
	char	  rq_host[PBS_MAXHOSTNAME+1]; /* name of host sending request */
	void  	 *rq_extra;	/* optional ptr to extra info		*/
	char	 *rq_extend;	/* request "extension" data		*/
	int		 isrpp; /* is this message from rpp stream      */
	int		 rpp_ack; /* send acks for this? */
	char	 *rppcmd_msgid; /* msg id with rpp commands */

	struct batch_reply  rq_reply;	  /* the reply area for this request */

	union indep_request {
		struct rq_authen_resvport	rq_authen_resvport;
		struct rq_authen_external	rq_authen_external;
		int			rq_connect;
		struct rq_queuejob	rq_queuejob;
		struct rq_jobcred       rq_jobcred;
		struct rq_jobfile	rq_jobfile;
		char		        rq_rdytocommit[PBS_MAXSVRJOBID+1];
		char		        rq_commit[PBS_MAXSVRJOBID+1];
		struct rq_manage	rq_delete;
		struct rq_hold		rq_hold;
		char		        rq_locate[PBS_MAXSVRJOBID+1];
		struct rq_manage	rq_manager;
		struct rq_message	rq_message;
		struct rq_relnodes	rq_relnodes;
		struct rq_py_spawn	rq_py_spawn;
		struct rq_manage	rq_modify;
		struct rq_move		rq_move;
		struct rq_register	rq_register;
		struct rq_manage	rq_release;
		char		        rq_rerun[PBS_MAXSVRJOBID+1];
		struct rq_rescq		rq_rescq;
		struct rq_runjob        rq_run;
		struct rq_selstat       rq_select;
		int			rq_shutdown;
		struct rq_signal	rq_signal;
		struct rq_status        rq_status;
		struct rq_track		rq_track;
		struct rq_cpyfile	rq_cpyfile;
		struct rq_cpyfile_cred	rq_cpyfile_cred;
		int			rq_failover;
		struct rq_usercred      rq_usercred;
		struct rq_user_migrate  rq_user_migrate;
		struct rq_defschrpy     rq_defrpy;
		struct rq_hookfile	rq_hookfile;
		struct rq_momrestart	rq_momrestart;
	} rq_ind;
};


extern struct batch_request *alloc_br(int type);
extern void  reply_ack(struct batch_request *);
extern void  req_reject(int code, int aux, struct batch_request *);
extern void  req_reject_msg(int code, int aux, struct batch_request *, int istcp);
extern void  reply_badattr(int code, int aux, svrattrl *, struct batch_request *);
extern void  reply_badattr_msg(int code, int aux, svrattrl *, struct batch_request *, int);
extern int   reply_text(struct batch_request *, int code, char *text);
extern int   reply_send(struct batch_request *);
extern int   reply_jobid(struct batch_request *, char *, int);
extern int   reply_jobid_msg(struct batch_request *, char *, int, int);
extern void  reply_free(struct batch_reply *);
extern void  dispatch_request(int, struct batch_request *);
extern void  free_br(struct batch_request *);
extern int   isode_request_read(int, struct batch_request *);
extern void  req_stat_job(struct batch_request *);
extern void  req_stat_resv(struct batch_request *);
extern void  req_stat_resc(struct batch_request *);
extern void  req_rerunjob(struct batch_request *req);
extern void  arrayfree(char **array);

#ifdef	PBS_NET_H
extern int   authenticate_user(struct batch_request *, conn_t *);
#endif

#ifndef PBS_MOM
extern void  req_authenResvPort(struct batch_request *req);
extern void  req_confirmresv(struct batch_request *req);
extern void  req_connect(struct batch_request *req);
extern void  req_defschedreply(struct batch_request *req);
extern void  req_locatejob(struct batch_request *req);
extern void  req_manager(struct batch_request *req);
extern void  req_movejob(struct batch_request *req);
extern void  req_register(struct batch_request *req);
extern void  req_releasejob(struct batch_request *req);
extern void  req_rescq(struct batch_request *req);
extern void  req_runjob(struct batch_request *req);
extern void  req_selectjobs(struct batch_request *req);
extern void  req_stat_que(struct batch_request *req);
extern void  req_stat_svr(struct batch_request *req);
extern void  req_stat_sched(struct batch_request *req);
extern void  req_trackjob(struct batch_request *req);
extern void  req_stat_rsc(struct batch_request *req);
#else
extern void  req_cpyfile(struct batch_request *req);
extern void  req_delfile(struct batch_request *req);
extern void  req_copy_hookfile(struct batch_request *req);
extern void  req_del_hookfile(struct batch_request *req);
#endif

/* PBS Batch Request Decode/Encode routines */

extern int decode_DIS_AuthenResvPort(int socket, struct batch_request *);
extern int decode_DIS_AuthExternal(int socket, struct batch_request *);
extern int decode_DIS_CopyFiles(int socket, struct batch_request *);
extern int decode_DIS_CopyFiles_Cred(int socket, struct batch_request *);
extern int decode_DIS_JobCred(int socket, struct batch_request *);
extern int decode_DIS_UserCred(int socket, struct batch_request *);
extern int decode_DIS_UserMigrate(int socket, struct batch_request *);
extern int decode_DIS_JobFile(int socket, struct batch_request *);
extern int decode_DIS_CopyHookFile(int socket, struct batch_request *);
extern int decode_DIS_DelHookFile(int socket, struct batch_request *);
extern int decode_DIS_JobObit(int socket, struct batch_request *);
extern int decode_DIS_Manage(int socket, struct batch_request *);
extern int decode_DIS_MoveJob(int socket, struct batch_request *);
extern int decode_DIS_MessageJob(int socket, struct batch_request *);
extern int decode_DIS_ModifyResv(int socket, struct batch_request *);
extern int decode_DIS_PySpawn(int socket, struct batch_request *);
extern int decode_DIS_QueueJob(int socket, struct batch_request *);
extern int decode_DIS_Register(int socket, struct batch_request *);
extern int decode_DIS_RelnodesJob(int socket, struct batch_request *);
extern int decode_DIS_ReqExtend(int socket, struct batch_request *);
extern int decode_DIS_ReqHdr(int socket, struct batch_request *, int *tp, int *pv);
extern int decode_DIS_Rescl(int socket, struct batch_request *);
extern int decode_DIS_Rescq(int socket, struct batch_request *);
extern int decode_DIS_Run(int socket, struct batch_request *);
extern int decode_DIS_ShutDown(int socket, struct batch_request *);
extern int decode_DIS_SignalJob(int socket, struct batch_request *);
extern int decode_DIS_Status(int socket, struct batch_request *);
extern int decode_DIS_TrackJob(int socket, struct batch_request *);
extern int decode_DIS_replySvr(int socket, struct batch_reply *);
extern int decode_DIS_svrattrl(int socket, pbs_list_head *);

extern int encode_DIS_failover(int socket, struct batch_request *);
extern int encode_DIS_CopyFiles(int socket, struct batch_request *);
extern int encode_DIS_CopyFiles_Cred(int socket, struct batch_request *);
extern int encode_DIS_JobObit(int socket, struct batch_request *);
extern int encode_DIS_Register(int socket, struct batch_request *);
extern int encode_DIS_TrackJob(int socket, struct batch_request *);
extern int encode_DIS_reply(int socket, struct batch_reply *);
extern int encode_DIS_replyRPP(int socket, char *, struct batch_reply *);
extern int encode_DIS_svrattrl(int socket, svrattrl *);

extern int dis_request_read(int socket, struct batch_request *);
extern int dis_reply_read(int socket, struct batch_reply *, int rpp);

#ifdef	__cplusplus
}
#endif
#endif	/* _BATCH_REQUEST_H */
