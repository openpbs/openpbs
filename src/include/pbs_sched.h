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

#ifndef _PBS_SCHED_H
#define _PBS_SCHED_H

#ifdef __cplusplus
extern "C" {
#endif

#include "pbs_config.h"
#include "pbs_ifl.h"
#include "libpbs.h"
#include "list_link.h"
#include "attribute.h"
#include "resource.h"
#include "pbs_ifl.h"
#include "server_limits.h"
#include "sched_cmds.h"
#include "work_task.h"
#include "net_connect.h"
#include "resv_node.h"
#include "queue.h"
#include "batch_request.h"
#include "job.h"
#include "reservation.h"

#define PBS_SCHED_CYCLE_LEN_DEFAULT 1200

/* Default value of preempt_queue_prio */
#define PBS_PREEMPT_QUEUE_PRIO_DEFAULT 150

#define SC_STATUS_LEN 10

/*
 * Attributes for the server's sched object
 * Must be the same order as listed in sched_attr_def (master_sched_attr_def.xml)
 */
enum sched_atr {
#include "sched_attr_enum.h"
#include "site_sched_attr_enum.h"
	/* This must be last */
	SCHED_ATR_LAST
};

extern void *sched_attr_idx;
extern attribute_def sched_attr_def[];

typedef struct pbs_sched {
	pbs_list_link sc_link;					      /* link to all scheds known to server */
	int sc_primary_conn;					      /* primary connection to sched */
	int sc_secondary_conn;					      /* secondary connection to sched */
	int svr_do_schedule;					      /* next sched command which will be sent to sched */
	int svr_do_sched_high;					      /* next high prio sched command which will be sent to sched */
	pbs_net_t sc_conn_addr;					      /* sched host address */
	time_t sch_next_schedule;				      /* time when to next run scheduler cycle */
	char sc_name[PBS_MAXSCHEDNAME + 1];			      /* name of sched this sched */
	struct preempt_ordering preempt_order[PREEMPT_ORDER_MAX + 1]; /* preempt order for this sched */
	int sc_cycle_started;					      /* indicates whether sched cycle is started or not, 0 - not started, 1 - started */
	attribute sch_attr[SCHED_ATR_LAST];			      /* sched object's attributes  */
	short newobj;						      /* is this new sched obj? */
} pbs_sched;

extern pbs_sched *dflt_scheduler;
extern pbs_list_head svr_allscheds;
extern void set_scheduler_flag(int flag, pbs_sched *psched);
extern int find_assoc_sched_jid(char *jid, pbs_sched **target_sched);
extern int find_assoc_sched_pque(pbs_queue *pq, pbs_sched **target_sched);
extern pbs_sched *find_sched_from_sock(int sock, conn_origin_t which);
extern pbs_sched *find_sched(char *sched_name);
extern int validate_job_formula(attribute *pattr, void *pobject, int actmode);
extern pbs_sched *find_sched_from_partition(char *partition);
extern int recv_sched_cycle_end(int sock);
extern void handle_deferred_cycle_close(pbs_sched *psched);

attribute *get_sched_attr(const pbs_sched *psched, int attr_idx);
char *get_sched_attr_str(const pbs_sched *psched, int attr_idx);
struct array_strings *get_sched_attr_arst(const pbs_sched *psched, int attr_idx);
pbs_list_head get_sched_attr_list(const pbs_sched *psched, int attr_idx);
long get_sched_attr_long(const pbs_sched *psched, int attr_idx);
int set_sched_attr_generic(pbs_sched *psched, int attr_idx, char *val, char *rscn, enum batch_op op);
int set_sched_attr_str_slim(pbs_sched *psched, int attr_idx, char *val, char *rscn);
int set_sched_attr_l_slim(pbs_sched *psched, int attr_idx, long val, enum batch_op op);
int set_sched_attr_b_slim(pbs_sched *psched, int attr_idx, long val, enum batch_op op);
int set_sched_attr_c_slim(pbs_sched *psched, int attr_idx, char val, enum batch_op op);
int is_sched_attr_set(const pbs_sched *psched, int attr_idx);
void free_sched_attr(pbs_sched *psched, int attr_idx);
void clear_sched_attr(pbs_sched *psched, int attr_idx);

#ifdef __cplusplus
}
#endif
#endif /* _PBS_SCHED_H */
