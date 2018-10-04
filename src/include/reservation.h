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
#ifndef	_RESERVATION_H
#define	_RESERVATION_H
#ifdef	__cplusplus
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

#ifndef	_RESV_NODE_H
#include "resv_node.h"
#endif

#define	JOB_OBJECT		1
#define	RESC_RESV_OBJECT	2
#define RESV_JOB_OBJECT		3

#define RESV_START_TIME_MODIFIED	0x1
#define RESV_END_TIME_MODIFIED		0x2

/*
 * The following resv_atr enum provide an index into the array of
 * decoded reservation attributes, ri_wattr[], for quick access.
 * Most of the attributes here are "public", but some are Read Only,
 * Private, or even Internal data items; maintained here because of
 * their variable size.
 *
 * "RESV_ATR_LAST" must be the last value as its number is used to
 * define the size of the array.
 */

enum resv_atr {
	RESV_ATR_resv_name,
	RESV_ATR_resv_owner,
	RESV_ATR_resv_type,
	RESV_ATR_state,
	RESV_ATR_substate,
	RESV_ATR_reserve_Tag,
	RESV_ATR_reserveID,
	RESV_ATR_start,
	RESV_ATR_end,
	RESV_ATR_duration,
	RESV_ATR_queue,
	RESV_ATR_resource,
	RESV_ATR_SchedSelect,
	RESV_ATR_resc_used,
	RESV_ATR_resv_nodes,
	RESV_ATR_userlst,
	RESV_ATR_grouplst,
	RESV_ATR_auth_u,
	RESV_ATR_auth_g,
	RESV_ATR_auth_h,
	RESV_ATR_at_server,
	RESV_ATR_account,
	RESV_ATR_ctime,
	RESV_ATR_mailpnts,
	RESV_ATR_mailuser,
	RESV_ATR_mtime,
	RESV_ATR_hashname,
	RESV_ATR_hopcount,
	RESV_ATR_priority,
	RESV_ATR_interactive,
	RESV_ATR_variables,
	RESV_ATR_euser,
	RESV_ATR_egroup,
	RESV_ATR_convert,
	RESV_ATR_resv_standing,
	RESV_ATR_resv_rrule,
	RESV_ATR_resv_idx,
	RESV_ATR_resv_count,
	RESV_ATR_resv_execvnodes,
	RESV_ATR_resv_timezone,
	RESV_ATR_retry,
	RESV_ATR_node_set,
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

extern attribute_def resv_attr_def[];
extern int	     index_atrJob_to_atrResv [][2];

/* linked list of vnodes associated to the soonest reservation */
typedef struct pbsnode_list_ {
	struct pbsnode *vnode;
	struct pbsnode_list_ *next;
} pbsnode_list_t;

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

#define	RSVERSION	500
struct resc_resv {

	/* Note: these members, upto ri_qs, are not saved to disk */
	pbs_list_link		ri_allresvs;		/* links this resc_resv into the
							 * server's global list
							 */

	struct pbs_queue	*ri_qp;			/* pbs_queue that got created
							 * to support this "reservation
							 * note: for a "reservation job"
							 * this value is NULL
							 */

	int			ri_futuredr;		/* non-zero if future delete resv
							 * task placed on "task_list_timed
							 */

	job			*ri_jbp;		/* for a "reservation job" this
							 * points to the associated job
							 */
	resc_resv		*ri_parent;		/* reservation in a reservation */

	int			ri_modified;		/*struct changed, needs to be saved*/
	int			ri_giveback;		/*flag, return resources to parent */

	int			ri_vnodes_down;		/* the number of vnodes that are unavailable */
	int			ri_vnodect;		/* the number of vnodes associated to an advance
							 * reservation or a standing reservation occurrence
							 */

	pbs_list_head		ri_svrtask;		/* place to keep work_task struct that
							 * are "attached" to this reservation
							 */

	pbs_list_head		ri_rejectdest;		/* place to keep badplace structs that
							 * are "attached" to this reservation
							 * Will only be useful if we later make
							 */

	struct batch_request	*ri_brp;		/*NZ if choose interactive (I) mode*/

	/*resource reservations routeable objs*/
	int			ri_downcnt;		/*used when deleting the reservation*/

	long			ri_resv_retry;		/* time at which the reservation will be reconfirmed */

	long			ri_degraded_time;	/* a tentative time to reconfirm the reservation */

	pbsnode_list_t		*ri_pbsnode_list;	/* vnode list associated to the reservation */

	/* objects used while altering a reservation. */
	time_t			ri_alter_stime;		/* start time backup while altering a reservation. */
	time_t			ri_alter_etime;		/*   end time backup while altering a reservation. */
	time_t			ri_alter_state;		/* resv state backup while altering a reservation. */
	time_t			ri_alter_standing_reservation_duration;
							/* duration backup while altering a standing reservation. */
	unsigned int		ri_alter_flags;		/* flags used while altering a reservation. */

	/* Reservation start and end tasks */
	struct work_task	*resv_start_task;
	struct work_task	*resv_end_task;

	/*
	 * fixed size internal data - maintained via "quick save"
	 * some of the items are copies of attributes, if so this
	 * internal version takes precendent
	 */

	struct resvfix {
		int		ri_rsversion;		/* reservation struct verison#, see RSVERSION */
		int		ri_state;		/* internal copy of state */
		int		ri_substate;		/* substate of resv state */
		int		ri_type;		/* "reservation" or "reservation job"*/
		time_t		ri_stime;		/* left window boundry  */
		time_t		ri_etime;		/* right window boundry */
		time_t		ri_duration;		/* reservation duration */
		time_t		ri_tactive;		/* time reservation became active */
		int		ri_svrflags;		/* server flags */
		int		ri_numattr;		/* number of attributes in list */
#if 0
		int		ri_ordering;		/* special scheduling ordering */
		int		ri_priority;		/* internal priority */
#endif
		long		ri_resvTag;		/* local numeric reservation ID */
		char		ri_resvID[PBS_MAXSVRRESVID+1]; /* reservation identifier */
		char		ri_fileprefix[PBS_RESVBASE+1]; /* reservation file prefix */
		char		ri_queue[PBS_MAXQRESVNAME+1];  /* queue used by reservation */

		int		ri_un_type;		/* type of struct in "ri_un" area */

		union   {

			struct	{
				int        ri_fromsock;
				pbs_net_t  ri_fromaddr;

			}  ri_newt;

		}	    ri_un;

	} ri_qs;

	/*
	 * The following array holds the decode	 format of the attributes.
	 * Its presence is for rapid access to the attributes.
	 */
	attribute		ri_wattr[RESV_ATR_LAST];  /*reservation's attributes*/

};

/*
 * server flags (in ri_svrflags)
 */
#define RESV_SVFLG_HERE     0x01   /* SERVER: job created here */
#define RESV_SVFLG_HASWAIT  0x02   /* job has timed task entry for wait time*/
#define RESV_SVFLG_HASRUN   0x04   /* job has been run before (being rerun */
#define RESV_SVFLG_Suspend  0x200  /* job suspended (signal suspend) */
#define RESV_SVFLG_HasNodes 0x1000 /* job has nodes allocated to it */

/*
 * Related defines
 */
#define SAVERESV_QUICK 0
#define SAVERESV_FULL  1
#define SAVERESV_NEW   2


#define RESV_FILE_COPY     ".RC"	/* tmp copy while updating */
#define RESV_FILE_SUFFIX   ".RB"	/* reservation control file */
#define RESV_BAD_SUFFIX	   ".RBD"	/* save bad reservation file */

#define RESV_UNION_TYPE_NEW	0

#define RESV_RETRY_DELAY	10  /* for degraded standing reservation retries */

/* reservation hold (internal) types */

#define RHOLD_n 0
#define RHOLD_u 1
#define RHOLD_o 2
#define RHOLD_s 4
#define RHOLD_bad_password 8

/* other symbolic constants */
#define	Q_CHNG_ENABLE		0
#define	Q_CHNG_START		1

extern resc_resv  *find_resv(char *);
extern resc_resv  *resc_resv_alloc(void);
extern void  resv_purge(resc_resv *);
extern int   start_end_dur_wall(void *, int);

#ifdef	_PBS_JOB_H
extern void*  job_or_resv_recov(char *, int);
#endif	/* _PBS_JOB_H */

#ifdef	_BATCH_REQUEST_H
extern resc_resv  *chk_rescResv_request(char *, struct batch_request *);
extern void resv_mailAction(resc_resv*, struct batch_request*);
extern int   chk_resvReq_viable(resc_resv*);
#endif	/* _BATCH_REQUEST_H */

#ifdef	_WORK_TASK_H
extern	int  gen_task_Time4resv(resc_resv*);
extern	int  gen_task_EndresvWindow(resc_resv*);
extern	int  gen_future_deleteResv(resc_resv*, long);
extern	int  gen_future_reply(resc_resv*, long);
extern	int  gen_negI_deleteResv(resc_resv*, long);
extern	void time4resvFinish(struct work_task *);
extern	void Time4resvFinish(struct work_task *);
extern	void Time4_I_term(struct work_task *);
extern	void tickle_for_reply(void);
extern	void remove_deleted_resvs();
extern	void add_resv_beginEnd_tasks();
extern	void resv_retry_handler(struct work_task *);
#endif	/* _WORK_TASK_H */

extern  int  change_enableORstart(resc_resv *, int, char *);
extern	void unset_resv_retry(resc_resv *);
extern	void set_resv_retry(resc_resv *, long);
extern	void eval_resvState(resc_resv *, enum resvState_discrim, int, int *,
	int *);
extern	void cmp_resvStateRelated_attrs(void *pobj, int);
extern	void free_resvNodes(resc_resv *);
extern	int  act_resv_add_owner(attribute*, void*, int);
extern	void svr_mailownerResv(resc_resv*, int, int, char*);
extern	void resv_free(resc_resv*);
extern	void set_old_subUniverse(resc_resv *);
extern	int  assign_resv_resc(resc_resv *, char *, int svr_init); /* Adding svr_init parameter to track whether the server is in init start mode */
extern	void  resv_exclusive_handler(resc_resv *);
#ifdef	__cplusplus
}
#endif
#endif	/* _RESERVATION_H */
