/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#ifndef	_GLOBALS_H
#define	_GLOBALS_H
#ifdef	__cplusplus
extern "C" {
#endif
#include <pthread.h>

#include "data_types.h"
#include "limits.h"
#include "queue.h"
#include "sched_cmds.h"

extern sched_svrconn **servers;
extern void *poll_context;
extern ds_queue *sched_cmds;

/* resources to check */
extern const struct rescheck res_to_check[];

/* information about sorting */
extern const struct sort_conv sort_convert[];

/* used to convert string into enum in parsing */
extern const struct enum_conv smp_cluster_info[];
extern const struct enum_conv preempt_prio_info[];

/* info to get from mom */
extern const char *res_to_get[];

/* programs to run to replaced specific resources_assigned values */
extern const char *res_assn[];

extern struct config conf;
extern struct status cstat;

extern const int num_resget;

/* Variables from pbs_sched code */
extern int got_sigpipe;

/* static indexes into allres */
const struct enum_conv resind[RES_HIGH+1];

/* Stuff needed for multi-threading */
extern pthread_mutex_t general_lock;
extern pthread_mutex_t work_lock;
extern pthread_cond_t work_cond;
extern pthread_mutex_t result_lock;
extern pthread_cond_t result_cond;
extern ds_queue *work_queue;
extern ds_queue *result_queue;
extern pthread_t *threads;
extern int threads_die;
extern int num_threads;
extern pthread_key_t th_id_key;
extern pthread_once_t key_once;

extern resdef **allres;
extern resdef **consres;
extern resdef **boolres;

extern char *sc_name;
extern char *logfile;

extern int preempt_normal;			/* preempt priority of normal_jobs */

extern char path_log[_POSIX_PATH_MAX];
extern int dflt_sched;

extern struct schedattrs sc_attrs;

extern time_t last_attr_updates;    /* timestamp of the last time attr updates were sent */

extern int send_job_attr_updates;

/**
 * @brief
 * It is used as a placeholder to store aoe name. This aoe name will be
 * used by sorting routine to compare with vnode's current aoe.
 */
extern char *cmp_aoename;

#ifdef	__cplusplus
}
#endif
#endif	/* _GLOBALS_H */
