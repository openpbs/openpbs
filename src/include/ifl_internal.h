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


#ifndef _IFL_INTERNAL_H
#define	_IFL_INTERNAL_H

#ifdef	__cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"

/* IFL functions */
int __pbs_asyrunjob(int, char *, char *, char *);

int __pbs_asyrunjob_ack(int c, char *jobid, char *location, char *extend);

int __pbs_alterjob(int, char *, struct attrl *, char *);

int __pbs_asyalterjob(int, char *, struct attrl *, char *);

int __pbs_confirmresv(int, char *, char *, unsigned long, char *);

int __pbs_connect(char *);

int __pbs_connect_extend(char *, char *);

char *__pbs_default(void);

int __pbs_deljob(int, char *, char *);

int __pbs_disconnect(int);

char *__pbs_geterrmsg(int);

int __pbs_holdjob(int, char *, char *, char *);

int __pbs_loadconf(int);

char *__pbs_locjob(int, char *, char *);

int __pbs_manager(int, int, int, char *, struct attropl *, char *);

int __pbs_movejob(int, char *, char *, char *);

int __pbs_msgjob(int, char *, int, char *, char *);

int __pbs_orderjob(int, char *, char *, char *);

int __pbs_rerunjob(int, char *, char *);

int __pbs_rlsjob(int, char *, char *, char *);

int __pbs_runjob(int, char *, char *, char *);

char **__pbs_selectjob(int, struct attropl *, char *);

int __pbs_sigjob(int, char *, char *, char *);

void __pbs_statfree(struct batch_status *);

struct batch_status *__pbs_statrsc(int, char *, struct attrl *, char *);

struct batch_status *__pbs_statjob(int, char *, struct attrl *, char *);

struct batch_status *__pbs_selstat(int, struct attropl *, struct attrl *, char *);

struct batch_status *__pbs_statque(int, char *, struct attrl *, char *);

struct batch_status *__pbs_statserver(int, struct attrl *, char *);

struct batch_status *__pbs_statsched(int, struct attrl *, char *);

struct batch_status *__pbs_stathost(int, char *, struct attrl *, char *);

struct batch_status *__pbs_statnode(int, char *, struct attrl *, char *);

struct batch_status *__pbs_statvnode(int, char *, struct attrl *, char *);

struct batch_status *__pbs_statresv(int, char *, struct attrl *, char *);

struct batch_status *__pbs_stathook(int, char *, struct attrl *, char *);

struct ecl_attribute_errors * __pbs_get_attributes_in_error(int);

char *__pbs_submit(int, struct attropl *, char *, char *, char *);

char *__pbs_submit_resv(int, struct attropl *, char *);

int __pbs_delresv(int, char *, char *);

int __pbs_terminate(int, int, char *);

preempt_job_info *__pbs_preempt_jobs(int, char **);

#ifdef	__cplusplus
}
#endif

#endif	/* _IFL_INTERNAL_H */
