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

/*
 **	Header file defineing the datatypes and library visiable
 **	variables for paralell awareness.
 */

#ifndef _TM_H
#define _TM_H

#include "tm_.h"

/*
 **	The tm_roots structure contains data for the last
 **	tm_init call whose event has been polled.  <Me> is the
 **	caller's identity.  <Daddy> is the identity of the task that
 **	spawned the caller.  If <daddy> is the TM_NULL_TASK, the caller
 **	is the initial task of the job, running on job-relative
 **	node 0.
 */
struct tm_roots {
	tm_task_id tm_me;
	tm_task_id tm_parent;
	int tm_nnodes;
	int tm_ntasks;
	int tm_taskpoolid;
	tm_task_id *tm_tasklist;
};

/*
 **	The tm_whattodo structure contains data for the last
 **	tm_register event polled.  This is not implemented yet.
 */
typedef struct tm_whattodo {
	int tm_todo;
	tm_task_id tm_what;
	tm_node_id tm_where;
} tm_whattodo_t;

/*
 **	Prototypes for all the TM API calls.
 */
int
tm_init(void *info,
	struct tm_roots *roots);

int
tm_poll(tm_event_t poll_event,
	tm_event_t *result_event,
	int wait,
	int *tm_errno);

int tm_notify(int tm_signal);

int
tm_spawn(int argc,
	 char *argv[],
	 char *envp[],
	 tm_node_id where,
	 tm_task_id *tid,
	 tm_event_t *event);

int
tm_kill(tm_task_id tid,
	int sig,
	tm_event_t *event);

int
tm_obit(tm_task_id tid,
	int *obitval,
	tm_event_t *event);

int
tm_nodeinfo(tm_node_id **list,
	    int *nnodes);

int
tm_taskinfo(tm_node_id node,
	    tm_task_id *list,
	    int lsize,
	    int *ntasks,
	    tm_event_t *event);

int
tm_atnode(tm_task_id tid,
	  tm_node_id *node);

int
tm_rescinfo(tm_node_id node,
	    char *resource,
	    int len,
	    tm_event_t *event);

int
tm_publish(char *name,
	   void *info,
	   int nbytes,
	   tm_event_t *event);

int
tm_subscribe(tm_task_id tid,
	     char *name,
	     void *info,
	     int len,
	     int *amount,
	     tm_event_t *event);

int tm_finalize(void);

int
tm_alloc(char *resources,
	 tm_event_t *event);

int
tm_dealloc(tm_node_id node,
	   tm_event_t *event);

int tm_create_event(tm_event_t *event);

int tm_destroy_event(tm_event_t *event);

int
tm_register(tm_whattodo_t *what,
	    tm_event_t *event);

int
tm_attach(char *jobid,
	  char *cookie,
	  pid_t pid,
	  tm_task_id *tid,
	  char *host,
	  int port);

#endif /* _TM_H */
