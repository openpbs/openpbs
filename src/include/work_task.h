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

#ifndef _WORK_TASK_H
#define _WORK_TASK_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * Server Work Tasks
 *
 * This structure is used by the server to track deferred work tasks.
 *
 * This information need not be preserved.
 *
 * Other Required Header Files
 *	"list_link.h"
 */

enum work_type {
	WORK_Immed,	     /* immediate action: see state */
	WORK_Interleave,     /* immediate action: but allow other work to interleave */
	WORK_Timed,	     /* action at certain time */
	WORK_Deferred_Child, /* On Death of a Child */
	WORK_Deferred_Reply, /* On reply to an outgoing service request */
	WORK_Deferred_Local, /* On reply to a local service request */
	WORK_Deferred_Other, /* various other events */

	WORK_Deferred_Cmp, /* Never set directly, used to indicate that */
	/* a WORK_Deferred_Child is ready            */
	WORK_Deferred_cmd /* used by TPP for deferred
	                        * reply but without a preq attached
	                        */
};

enum wtask_delete_option {
	DELETE_ONE,
	DELETE_ALL
};

struct work_task {
	pbs_list_link wt_linkevent;	     /* link to event type work list */
	pbs_list_link wt_linkobj;	     /* link to others of same object */
	pbs_list_link wt_linkobj2;	     /* link to another set of similarity */
	long wt_event;			     /* event id: time, pid, socket, ... */
	char *wt_event2;		     /* if replies on the same handle, then additional distinction */
	enum work_type wt_type;		     /* type of event */
	void (*wt_func)(struct work_task *); /* function to perform task */
	void *wt_parm1;			     /* obj pointer for use by func */
	void *wt_parm2;			     /* optional pointer for use by func */
	void *wt_parm3;			     /* used to store reply for deferred cmds TPP */
	int wt_aux;			     /* optional info: e.g. child status */
	int wt_aux2;			     /* optional info 2: e.g. *real* child pid (windows), tpp msgid etc */
};

extern struct work_task *set_task(enum work_type, long event, void (*func)(), void *param);
extern int convert_work_task(struct work_task *ptask, enum work_type);
extern void clear_task(struct work_task *ptask);
extern void dispatch_task(struct work_task *);
extern void delete_task(struct work_task *);
extern void delete_task_by_parm1_func(void *parm1, void (*func)(struct work_task *), enum wtask_delete_option option);
extern int has_task_by_parm1(void *parm1);
extern time_t default_next_task(void);
extern struct work_task *find_work_task(enum work_type, void *, void *);

#ifdef __cplusplus
}
#endif
#endif /* _WORK_TASK_H */
