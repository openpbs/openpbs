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

#ifndef _MOM_SERVER_H
#define _MOM_SERVER_H
#ifdef __cplusplus
extern "C" {
#endif

#include "list_link.h"

/*
 * Definition of basic structures and functions used for Mom -> Server
 * TPP communication.
 *
 * Job Obituary/Resource Usage requests...
 *
 * These are from Mom to Server only and only via TPP
 */

typedef struct resc_used_update ruu;
struct resc_used_update {
	ruu *ru_next;
	char *ru_pjobid;       /* pointer to job id */
	char *ru_comment;      /* a general message */
	int ru_status;	       /* job exit status (or zero) */
	int ru_hop;	       /* hop/run count of job	*/
	pbs_list_head ru_attr; /* list of svrattrl */
#ifdef PBS_MOM
	time_t ru_created_at;	  /* time in epoch at which this ruu was created */
	job *ru_pjob;		  /* pointer to job structure for this ruu */
	int ru_cmd;		  /* cmd for this ruu */
	pbs_list_link ru_pending; /* link to mom_pending_ruu list */
#endif
};

#ifdef PBS_MOM
#define FREE_RUU(x)                                        \
	do {                                               \
		if (x->ru_pjob) {                          \
			x->ru_pjob->ji_pending_ruu = NULL; \
			x->ru_pjob = NULL;                 \
		}                                          \
		delete_link(&x->ru_pending);               \
		free_attrlist(&x->ru_attr);                \
		if (x->ru_pjobid)                          \
			free(x->ru_pjobid);                \
		if (x->ru_comment)                         \
			free(x->ru_comment);               \
		free(x);                                   \
	} while (0)
#else
#define FREE_RUU(x)                          \
	do {                                 \
		free_attrlist(&x->ru_attr);  \
		if (x->ru_pjobid)            \
			free(x->ru_pjobid);  \
		if (x->ru_comment)           \
			free(x->ru_comment); \
		free(x);                     \
	} while (0)
#endif

extern int job_obit(ruu *, int);
extern int enqueue_update_for_send(job *, int);
extern void send_resc_used(int cmd, int count, ruu *rud);
extern void send_pending_updates(void);
extern char mom_short_name[];

#ifdef _PBS_JOB_H
extern u_long resc_used(job *, char *, u_long (*func)(resource *pres));
#endif /* _PBS_JOB_H */
#ifdef __cplusplus
}
#endif
#endif /* _MOM_SERVER_H */
