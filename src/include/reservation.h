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

#ifndef _RESERVATION_H
#define _RESERVATION_H
#ifdef __cplusplus
extern "C" {
#endif
/*
 * reservation.h - structure definations for reservation objects
 *
 * Include Files Required:
 *	<sys/types.h>
 *	"list_link.h"
 *	"attribute.h"
 *	"server_limits.h"
 *	"batch_request.h"
 *	"pbs_nodes.h"
 *	"job.h"
 */

#ifndef _RESV_NODE_H
#include "resv_node.h"
#endif

#define JOB_OBJECT 1
#define RESC_RESV_OBJECT 2

#define RESV_START_TIME_MODIFIED 0x1
#define RESV_END_TIME_MODIFIED 0x2
#define RESV_DURATION_MODIFIED 0x4
#define RESV_SELECT_MODIFIED 0x8
#define RESV_ALTER_FORCED 0x10

/*
 * The following resv_atr enum provide an index into the array of
 * decoded reservation attributes, for quick access.
 * Most of the attributes here are "public", but some are Read Only,
 * Private, or even Internal data items; maintained here because of
 * their variable size.
 *
 * "RESV_ATR_LAST" must be the last value as its number is used to
 * define the size of the array.
 */

enum resv_atr {
#include "resv_attr_enum.h"
	RESV_ATR_UNKN,
	RESV_ATR_LAST
};

enum resvState_discrim {
	RESVSTATE_gen_task_Time4resv,
	RESVSTATE_Time4resv,
	RESVSTATE_req_deleteReservation,
	RESVSTATE_add_resc_resv_to_job,
	RESVSTATE_is_resv_window_in_future,
	RESVSTATE_req_resvSub,
	RESVSTATE_alter_failed
};

/*
 * The "definations" for the reservation attributes are in the following array,
 * it is also indexed by the RESV_ATR_... enums.
 */

extern void *resv_attr_idx;
extern attribute_def resv_attr_def[];
extern int index_atrJob_to_atrResv[][2];

/* linked list of vnodes associated to the soonest reservation */
typedef struct pbsnode_list_ {
	struct pbsnode *vnode;
	struct pbsnode_list_ *next;
} pbsnode_list_t;

/* Structure used to revert reservation back if the ralter failed */
struct resv_alter {
	long ra_state;
	unsigned long ra_flags;
};

/*
 * THE RESERVATION
 *
 * This structure is used by the server to maintain internal
 * quick access to the state and status of each reservation.
 * There is one instance of this structure per reservation known by the server.
 *
 * This information must be PRESERVED and is done so by updating the
 * reservation file in the reservation subdirectory which corresponds to this
 * reservation.
 *
 * ri_state is the state of the reservation.  It is kept up front to provide
 * for a "quick" update of the reservation state with minimum rewritting of the
 * reservation file.
 * Which is why the sub-struct ri_qs exists, that is the part which is
 * written on the "quick" save.  If in the future the format of this area
 * is modified the value of RSVERSION needs to be be bumped.
 *
 * The unparsed string set forms of the attributes (including resources)
 * are maintained in the struct attrlist as discussed above.
 */

#define RSVERSION 500
struct resc_resv {

	/* Note: these members, upto ri_qs, are not saved to disk */

	pbs_list_link ri_allresvs; /* links this resc_resv into the
							 * server's global list
							 */

	struct pbs_queue *ri_qp; /* pbs_queue that got created
							 * to support this "reservation
							 * note: for a "reservation job"
							 * this value is NULL
							 */

	int ri_futuredr; /* non-zero if future delete resv
							 * task placed on "task_list_timed
							 */

	job *ri_jbp;	      /* for a "reservation job" this
							 * points to the associated job
							 */
	resc_resv *ri_parent; /* reservation in a reservation */

	int ri_giveback; /*flag, return resources to parent */

	int ri_vnodes_down; /* the number of vnodes that are unavailable */
	int ri_vnodect;	    /* the number of vnodes associated to an advance
							 * reservation or a standing reservation occurrence
							 */

	pbs_list_head ri_svrtask; /* place to keep work_task struct that
							 * are "attached" to this reservation
							 */

	pbs_list_head ri_rejectdest; /* place to keep badplace structs that
							 * are "attached" to this reservation
							 * Will only be useful if we later make
							 */

	struct batch_request *ri_brp; /* NZ if choose interactive (I) mode */

	/*resource reservations routeable objs*/
	int ri_downcnt; /* used when deleting the reservation*/

	long ri_resv_retry; /* time at which the reservation will be reconfirmed */

	long ri_degraded_time; /* a tentative time to reconfirm the reservation */

	pbsnode_list_t *ri_pbsnode_list; /* vnode list associated to the reservation */

	/* objects used while altering a reservation. */
	struct resv_alter ri_alter; /* object used to alter a reservation */

	/* Reservation start and end tasks */
	struct work_task *resv_start_task;
	struct work_task *resv_end_task;
	int resv_from_job;

	/* A count to keep track of how many schedulers have been requested and
	 * responsed to this reservation request
	 */
	int req_sched_count;
	int rep_sched_count;

	/*
	 * fixed size internal data - maintained via "quick save"
	 * some of the items are copies of attributes, if so this
	 * internal version takes precendent
	 */
#ifndef PBS_MOM
	char qs_hash[DIGEST_LENGTH];
#endif
	struct resvfix {
		int ri_rsversion;			   /* reservation struct verison#, see RSVERSION */
		int ri_state; /* internal copy of state */ // FIXME: can we remove this like we did for job?
		int ri_substate;			   /* substate of resv state */
		time_t ri_stime;			   /* left window boundry  */
		time_t ri_etime;			   /* right window boundry */
		time_t ri_duration;			   /* reservation duration */
		time_t ri_tactive;			   /* time reservation became active */
		int ri_svrflags;			   /* server flags */
		char ri_resvID[PBS_MAXSVRRESVID + 1];	   /* reservation identifier */
		char ri_fileprefix[PBS_RESVBASE + 1];	   /* reservation file prefix */
		char ri_queue[PBS_MAXQRESVNAME + 1];	   /* queue used by reservation */
	} ri_qs;

	/*
	 * The following array holds the decode	 format of the attributes.
	 * Its presence is for rapid access to the attributes.
	 */
	attribute ri_wattr[RESV_ATR_LAST]; /*reservation's attributes*/
	short newobj;
};

/*
 * server flags (in ri_svrflags)
 */
#define RESV_SVFLG_HERE 0x01	   /* SERVER: job created here */
#define RESV_SVFLG_HASWAIT 0x02	   /* job has timed task entry for wait time*/
#define RESV_SVFLG_HASRUN 0x04	   /* job has been run before (being rerun */
#define RESV_SVFLG_Suspend 0x200   /* job suspended (signal suspend) */
#define RESV_SVFLG_HasNodes 0x1000 /* job has nodes allocated to it */

#define RESV_FILE_COPY ".RC"   /* tmp copy while updating */
#define RESV_FILE_SUFFIX ".RB" /* reservation control file */
#define RESV_BAD_SUFFIX ".RBD" /* save bad reservation file */

#define RESV_UNION_TYPE_NEW 0

#define RESV_RETRY_DELAY 10	/* for degraded standing reservation retries */
#define RESV_ASAP_IDLE_TIME 600 /* default delete_idle_time for ASAP reservations */

/* reservation hold (internal) types */

#define RHOLD_n 0
#define RHOLD_u 1
#define RHOLD_o 2
#define RHOLD_s 4
#define RHOLD_bad_password 8

/* other symbolic constants */
#define Q_CHNG_ENABLE 0
#define Q_CHNG_START 1

extern void *resvs_idx;
extern resc_resv *find_resv(char *);
extern resc_resv *resv_alloc(char *);
extern resc_resv *resv_recov(char *);
extern void resv_purge(resc_resv *);
extern int start_end_dur_wall(resc_resv *);

#ifdef _BATCH_REQUEST_H
extern resc_resv *chk_rescResv_request(char *, struct batch_request *);
extern void resv_mailAction(resc_resv *, struct batch_request *);
extern int chk_resvReq_viable(resc_resv *);
#endif /* _BATCH_REQUEST_H */

#ifdef _WORK_TASK_H
extern int gen_task_Time4resv(resc_resv *);
extern int gen_task_EndresvWindow(resc_resv *);
extern int gen_future_deleteResv(resc_resv *, long);
extern int gen_future_reply(resc_resv *, long);
extern int gen_negI_deleteResv(resc_resv *, long);
extern void time4resvFinish(struct work_task *);
extern void Time4resvFinish(struct work_task *);
extern void Time4_I_term(struct work_task *);
extern void tickle_for_reply(void);
extern void remove_deleted_resvs();
extern void add_resv_beginEnd_tasks();
extern void resv_retry_handler(struct work_task *);
extern void set_idle_delete_task(resc_resv *presv);
#endif /* _WORK_TASK_H */

extern int change_enableORstart(resc_resv *, int, char *);
extern void unset_resv_retry(resc_resv *);
extern void set_resv_retry(resc_resv *, long);
extern void eval_resvState(resc_resv *, enum resvState_discrim, int, int *, int *);
extern void free_resvNodes(resc_resv *);
extern int act_resv_add_owner(attribute *, void *, int);
extern void svr_mailownerResv(resc_resv *, int, int, char *);
extern void resv_free(resc_resv *);
extern void set_old_subUniverse(resc_resv *);
extern int assign_resv_resc(resc_resv *, char *, int);
extern void resv_exclusive_handler(resc_resv *);
extern long determine_resv_retry(resc_resv *presv);

extern resc_resv *resv_recov_db(char *resvid, resc_resv *presv);
extern int resv_save_db(resc_resv *presv);
extern void pbsd_init_resv(resc_resv *presv, int type);

attribute *get_rattr(const resc_resv *presv, int attr_idx);
char *get_rattr_str(const resc_resv *presv, int attr_idx);
struct array_strings *get_rattr_arst(const resc_resv *presv, int attr_idx);
pbs_list_head get_rattr_list(const resc_resv *presv, int attr_idx);
long get_rattr_long(const resc_resv *presv, int attr_idx);
int set_rattr_generic(resc_resv *presv, int attr_idx, char *val, char *rscn, enum batch_op op);
int set_rattr_str_slim(resc_resv *presv, int attr_idx, char *val, char *rscn);
int set_rattr_l_slim(resc_resv *presv, int attr_idx, long val, enum batch_op op);
int set_rattr_b_slim(resc_resv *presv, int attr_idx, long val, enum batch_op op);
int set_rattr_c_slim(resc_resv *presv, int attr_idx, char val, enum batch_op op);
int is_rattr_set(const resc_resv *presv, int attr_idx);
void free_rattr(resc_resv *presv, int attr_idx);
void clear_rattr(resc_resv *presv, int attr_idx);

#ifdef __cplusplus
}
#endif
#endif /* _RESERVATION_H */
