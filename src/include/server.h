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

#ifndef	_SERVER_H
#define	_SERVER_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * server.h - definitions for the server object (structure)
 *
 * Other include files required:
 *	<sys/types.h>
 *	"attribute.h"
 *	"list_link.h"
 *	"server_limits.h"
 *
 * The server object (structure) contains the parameters which
 * control the operation of the server itself.  This includes
 * the server attributes and resource (limits).
 */
#ifndef	_GRUNT_H
#include "grunt.h"
#endif
#include "pbs_sched.h"
#include "server_limits.h"

#define SYNC_SCHED_HINT_NULL	0
#define SYNC_SCHED_HINT_FIRST	1
#define SYNC_SCHED_HINT_OTHER	2

enum srv_atr {
#include "svr_attr_enum.h"
#include "site_svr_attr_enum.h"
	/* This must be last */
	SVR_ATR_LAST
};

extern char *pbs_server_name;
extern uint pbs_server_port_dis;
extern void *svr_attr_idx;
extern attribute_def svr_attr_def[];
/* for trillion job id */
extern long long svr_max_job_sequence_id;

/* for history jobs*/
extern long svr_history_enable;
extern long svr_history_duration;

struct server {
	struct server_qs {
		int sv_numjobs;		  /* number of job owned by server   */
		int sv_numque;		  /* number of queues managed  */
		long long sv_jobidnumber; /* next number to use in new jobid  */
		long long sv_lastid;	  /* block increment to avoid many saves */
	} sv_qs;
	attribute sv_attr[SVR_ATR_LAST]; /* the server attributes */
	short newobj;
	time_t sv_started;		       /* time server started */
	time_t sv_hotcycle;		       /* if RECOV_HOT,time of last restart */
	time_t sv_next_schedule;	   /* when to next run scheduler cycle */
	int sv_jobstates[PBS_NUMJOBSTATE]; /* # of jobs per state */
	int sv_nseldft;		         /* num of elems in sv_seldft */
	key_value_pair *sv_seldft;   /* defelts for job's -l select	*/

	int sv_trackmodifed;		     /* 1 if tracking list modified	    */
	int sv_tracksize;		         /* total number of sv_track entries */
	struct tracking *sv_track;	     /* array of track job records	    */
	int sv_provtrackmodifed;	     /* 1 if prov_tracking list modified */
	int sv_provtracksize;		     /* total number of sv_prov_track entries */
	struct prov_tracking *sv_prov_track; /* array of provision records */
	int sv_cur_prov_records;	     /* number of provisiong requests currently running */
};

extern struct server	server;
extern	pbs_list_head	svr_alljobs;
extern	pbs_list_head	svr_allresvs;	/* all reservations in server */

/* degraded reservations globals */
extern	long	resv_retry_time;


/*
 * server state values
 */
#define SV_STATE_DOWN    0
#define SV_STATE_INIT	 1
#define SV_STATE_HOT	 2
#define SV_STATE_RUN     3
#define SV_STATE_SHUTDEL 4
#define SV_STATE_SHUTIMM 5
#define SV_STATE_SHUTSIG 6
#define SV_STATE_SECIDLE 7
#define SV_STATE_PRIMDLY 0x10

/*
 * Other misc defines
 */
#define SVR_HOSTACL "svr_hostacl"
#define PBS_DEFAULT_NODE "1"

#define SVR_SAVE_QUICK 0
#define SVR_SAVE_FULL  1
#define SVR_SAVE_NEW   2

#define SVR_HOT_CYCLE	15	/* retry mom every n sec on hot start     */
#define SVR_HOT_LIMIT	300	/* after n seconds, drop out of hot start */

#define PBS_SCHED_DAEMON_NAME "Scheduler"
#define WALLTIME "walltime"
#define MIN_WALLTIME "min_walltime"
#define MAX_WALLTIME "max_walltime"
#define SOFT_WALLTIME "soft_walltime"
#define MCAST_WAIT_TM	2

/*
 * Server failover role
 */
enum failover_state {
	FAILOVER_NONE,		/* Only Server, no failover */
	FAILOVER_PRIMARY,       /* Primary in failover configuration */
	FAILOVER_SECONDARY,	/* Secondary in failover */
	FAILOVER_CONFIG_ERROR,	/* error in configuration */
};

/*
 * Server job history defines & globals
 */
#define SVR_CLEAN_JOBHIST_TM		120	/* after 2 minutes, reschedule the work task */
#define SVR_CLEAN_JOBHIST_SECS	5	/* never spend more than 5 seconds in one sweep to clean hist */
#define SVR_JOBHIST_DEFAULT		1209600	/* default time period to keep job history: 2 weeks */
#define SVR_MAX_JOB_SEQ_NUM_DEFAULT	9999999	/* default max job id is 9999999 */

/* function prototypes */

extern int			svr_recov_db();
extern int			svr_save_db(struct server *);
extern pbs_sched *	sched_recov_db(char *, pbs_sched *ps);
extern int			sched_save_db(pbs_sched *);
extern enum failover_state	are_we_primary(void);
extern int			have_licensed_nodes(void);
extern void			unlicense_nodes(void);
extern void			set_sched_default(pbs_sched *, int from_scheduler);
extern void			memory_debug_log(struct work_task *ptask);


/* Multi-server specific structures */

/* Resource update from peer server */
struct peersvr_resc_update {
	char *jobid;	/* job id of the resource update */
	int op;		/* operation which is performed; INCR/DECR */
	char *execvnode;	/* execvnode of the job */
	int share_job;	/* job share type based on job's placement directive */
	int broadcast; /* whether to broadcast the resc update to all the peer servers */
	pbs_list_link ru_link;	/* Link to the next element in the list */
};
typedef struct peersvr_resc_update psvr_ru_t;

/*
 * enums indicating stat update flag
 */
enum msvr_stats_type {
	CACHE_MISS,		/* Number of node cache miss */
	CACHE_REFR_TM,		/* time spent in refreshing node cache */
	NUM_RESC_UPDATE,	/* number of peer server resource updates */
	NUM_MOVE_RUN,		/* number of move and run */
	NUM_SCHED_MISS,		/* number of times when acks were not received by the next sched cycle */
	END_OF_STAT		/* Indicates end of types */
};
typedef enum msvr_stats_type msvr_stat_type_t;

/* Multi-svr statistical logging */
struct msvr_stats {
	time_t last_logged_tm;	/* Time when we logged last */
	unsigned long stat[END_OF_STAT];	/* Number of node cache miss */
};
typedef struct msvr_stats msvr_stat_t;

#define HOUR_IN_SEC	60 * 60
#define STAT_LOG_INTL	24 * HOUR_IN_SEC /* 24 hours */

/* multi-server gloabls and functions */

extern pbs_list_head peersvrl;

struct svrinfo {
	int		ps_pending_replies; /* number of unacknowledged replies from this server */
	void		*ps_rsc_idx; /* avl of resc updates based on job_id as the key and psvr_ru_t as value */
	pbs_list_head	ps_node_list; /* list of nodes corresponding to this server. Useful for clearing the nodes in case of an update */
};
typedef struct svrinfo svrinfo_t;

void *get_peersvr(struct sockaddr_in *);
void *create_svr_entry(char *, unsigned int);
int init_msi();
void *create_svr_struct(struct sockaddr_in *, char *);
int connect_to_peersvr(void *);
bool is_peersvr(void *);
void mcast_resc_usage(psvr_ru_t *, int);
int open_ps_mtfd(void);
void send_nodestat_req(void);
void req_peer_svr_ack(int);
void *pending_ack_svr(void);
psvr_ru_t *init_psvr_ru(job *, int, char *, bool);
void free_psvr_ru(psvr_ru_t *);
int send_job_resc_updates(int);
int send_command(int, int);
int send_resc_usage(int, psvr_ru_t *, int, int);
void req_resc_update(int, pbs_list_head *, void *);
void replyhello_psvr(struct work_task *);
void poke_peersvr(void);
void mcast_resc_update_all(void *);
void clean_saved_rsc(void*);
int process_status_reply(int);
void *get_peersvr_from_svrid(char *);
void update_msvr_stat(unsigned long, msvr_stat_type_t);

/* end of multi-svr functions */

attribute *get_sattr(int attr_idx);
char *get_sattr_str(int attr_idx);
struct array_strings *get_sattr_arst(int attr_idx);
pbs_list_head get_sattr_list(int attr_idx);
long get_sattr_long(int attr_idx);
int set_sattr_generic(int attr_idx, char *val, char *rscn, enum batch_op op);
int set_sattr_str_slim(int attr_idx, char *val, char *rscn);
int set_sattr_l_slim(int attr_idx, long val, enum batch_op op);
int set_sattr_b_slim(int attr_idx, long val, enum batch_op op);
int set_sattr_c_slim(int attr_idx, char val, enum batch_op op);
int is_sattr_set(int attr_idx);
void free_sattr(int attr_idx);

#ifdef	__cplusplus
}
#endif
#endif	/* _SERVER_H */
