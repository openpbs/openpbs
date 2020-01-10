/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#include <stdio.h>

#include "pbs_ifl.h"
#include "ifl_internal.h"

int (*pfn_pbs_asyrunjob)(int, char *, char *, char *) = __pbs_asyrunjob;
int (*pfn_pbs_alterjob)(int, char *, struct attrl *, char *) = __pbs_alterjob;
int (*pfn_pbs_confirmresv)(int, char *, char *, unsigned long, char *) = __pbs_confirmresv;
int (*pfn_pbs_connect)(char *) = __pbs_connect;
int (*pfn_pbs_connect_extend)(char *, char *) = __pbs_connect_extend;
char *(*pfn_pbs_default)(void) = __pbs_default;
int (*pfn_pbs_deljob)(int, char *, char *) = __pbs_deljob;
int (*pfn_pbs_disconnect)(int) = __pbs_disconnect;
char *(*pfn_pbs_geterrmsg)(int) = __pbs_geterrmsg;
int (*pfn_pbs_holdjob)(int, char *, char *, char *) = __pbs_holdjob;
int (*pfn_pbs_loadconf)(int) = __pbs_loadconf;
char *(*pfn_pbs_locjob)(int, char *, char *) = __pbs_locjob;
int (*pfn_pbs_manager)(int, int, int, char *, struct attropl *, char *) = __pbs_manager;
int (*pfn_pbs_movejob)(int, char *, char *, char *) = __pbs_movejob;
int (*pfn_pbs_msgjob)(int, char *, int, char *, char *) = __pbs_msgjob;
int (*pfn_pbs_orderjob)(int, char *, char *, char *) = __pbs_orderjob;
int (*pfn_pbs_rerunjob)(int, char *, char *) = __pbs_rerunjob;
int (*pfn_pbs_rlsjob)(int, char *, char *, char *) = __pbs_rlsjob;
int (*pfn_pbs_runjob)(int, char *, char *, char *) = __pbs_runjob;
char **(*pfn_pbs_selectjob)(int, struct attropl *, char *) = __pbs_selectjob;
int (*pfn_pbs_sigjob)(int, char *, char *, char *) = __pbs_sigjob;
void (*pfn_pbs_statfree)(struct batch_status *) = __pbs_statfree;
struct batch_status *(*pfn_pbs_statrsc)(int, char *, struct attrl *, char *) = __pbs_statrsc;
struct batch_status *(*pfn_pbs_statjob)(int, char *, struct attrl *, char *) = __pbs_statjob;
struct batch_status *(*pfn_pbs_selstat)(int, struct attropl *, struct attrl *, char *) = __pbs_selstat;
struct batch_status *(*pfn_pbs_statque)(int, char *, struct attrl *, char *) = __pbs_statque;
struct batch_status *(*pfn_pbs_statserver)(int, struct attrl *, char *) = __pbs_statserver;
struct batch_status *(*pfn_pbs_statsched)(int, struct attrl *, char *) = __pbs_statsched;
struct batch_status *(*pfn_pbs_stathost)(int, char *, struct attrl *, char *) = __pbs_stathost;
struct batch_status *(*pfn_pbs_statnode)(int, char *, struct attrl *, char *) = __pbs_statnode;
struct batch_status *(*pfn_pbs_statvnode)(int, char *, struct attrl *, char *) = __pbs_statvnode;
struct batch_status *(*pfn_pbs_statresv)(int, char *, struct attrl *, char *) = __pbs_statresv;
struct batch_status *(*pfn_pbs_stathook)(int, char *, struct attrl *, char *) = __pbs_stathook;
struct ecl_attribute_errors * (*pfn_pbs_get_attributes_in_error)(int) = __pbs_get_attributes_in_error;
char *(*pfn_pbs_submit)(int, struct attropl *, char *, char *, char *) = __pbs_submit;
char *(*pfn_pbs_submit_resv)(int, struct attropl *, char *) = __pbs_submit_resv;
int (*pfn_pbs_delresv)(int, char *, char *) = __pbs_delresv;
int (*pfn_pbs_terminate)(int, int, char *) = __pbs_terminate;
preempt_job_info *(*pfn_pbs_preempt_jobs)(int, char**) = __pbs_preempt_jobs;

