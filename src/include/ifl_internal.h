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

#ifndef _IFL_INTERNAL_H
#define _IFL_INTERNAL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"
#include "pbs_internal.h"

/* Used for non blocking connect */
#define NOBLK_FLAG "NOBLK"
#define NOBLK_TOUT 2

/* IFL functions */
int __pbs_asyrunjob(int, const char *, const char *, const char *);

int __pbs_asyrunjob_ack(int c, const char *jobid, const char *location, const char *extend);

int __pbs_alterjob(int, const char *, struct attrl *, const char *);

int __pbs_asyalterjob(int, const char *, struct attrl *, const char *);

int __pbs_confirmresv(int, const char *, const char *, unsigned long, const char *);

int __pbs_connect(const char *);

int __pbs_connect_extend(const char *, const char *);

char *__pbs_default(void);

int __pbs_deljob(int, const char *, const char *);

struct batch_deljob_status *__pbs_deljoblist(int, char **, int, const char *);

int __pbs_disconnect(int);

char *__pbs_geterrmsg(int);

int __pbs_holdjob(int, const char *, const char *, const char *);

int __pbs_loadconf(int);

char *__pbs_locjob(int, const char *, const char *);

int __pbs_manager(int, int, int, const char *, struct attropl *, const char *);

int __pbs_movejob(int, const char *, const char *, const char *);

int __pbs_msgjob(int, const char *, int, const char *, const char *);

int __pbs_orderjob(int, const char *, const char *, const char *);

int __pbs_rerunjob(int, const char *, const char *);

int __pbs_rlsjob(int, const char *, const char *, const char *);

int __pbs_runjob(int, const char *, const char *, const char *);

char **__pbs_selectjob(int, struct attropl *, const char *);

int __pbs_sigjob(int, const char *, const char *, const char *);

void __pbs_statfree(struct batch_status *);

void __pbs_delstatfree(struct batch_deljob_status *);

struct batch_status *__pbs_statrsc(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_statjob(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_selstat(int, struct attropl *, struct attrl *, const char *);

struct batch_status *__pbs_statque(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_statserver(int, struct attrl *, const char *);

struct batch_status *__pbs_statsched(int, struct attrl *, const char *);

struct batch_status *__pbs_stathost(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_statnode(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_statvnode(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_statresv(int, const char *, struct attrl *, const char *);

struct batch_status *__pbs_stathook(int, const char *, struct attrl *, const char *);

struct ecl_attribute_errors *__pbs_get_attributes_in_error(int);

char *__pbs_submit(int, struct attropl *, const char *, const char *, const char *);

char *__pbs_submit_resv(int, struct attropl *, const char *);

char *__pbs_modify_resv(int c, const char *resv_id, struct attropl *attrib, const char *extend);

int __pbs_delresv(int, const char *, const char *);

int __pbs_relnodesjob(int c, const char *jobid, const char *node_list, const char *extend);

int __pbs_terminate(int, int, const char *);

preempt_job_info *__pbs_preempt_jobs(int, char **);

int __pbs_register_sched(const char *sched_id, int primary_conn_id, int secondary_conn_id);

#ifdef __cplusplus
}
#endif

#endif /* _IFL_INTERNAL_H */
