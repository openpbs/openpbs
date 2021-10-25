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


#include <stdio.h>

#include "pbs_ifl.h"
#include "ifl_internal.h"

int (*pfn_pbs_asyrunjob)(int, const char *, const char *, const char *) = __pbs_asyrunjob;
int (*pfn_pbs_asyrunjob_ack)(int, const char *, const char *, const char *) = __pbs_asyrunjob_ack;
int (*pfn_pbs_alterjob)(int, const char *, struct attrl *, const char *) = __pbs_alterjob;
int (*pfn_pbs_asyalterjob)(int, const char *, struct attrl *, const char *) = __pbs_asyalterjob;
int (*pfn_pbs_confirmresv)(int, const char *, const char *, unsigned long, const char *) = __pbs_confirmresv;
int (*pfn_pbs_connect)(const char *) = __pbs_connect;
int (*pfn_pbs_connect_extend)(const char *, const char *) = __pbs_connect_extend;
char *(*pfn_pbs_default)(void) = __pbs_default;
int (*pfn_pbs_deljob)(int, const char *, const char *) = __pbs_deljob;
struct batch_deljob_status *(*pfn_pbs_deljoblist)(int, char **, int, const char *) = __pbs_deljoblist;
int (*pfn_pbs_disconnect)(int) = __pbs_disconnect;
char *(*pfn_pbs_geterrmsg)(int) = __pbs_geterrmsg;
int (*pfn_pbs_holdjob)(int, const char *, const char *, const char *) = __pbs_holdjob;
int (*pfn_pbs_loadconf)(int) = __pbs_loadconf;
char *(*pfn_pbs_locjob)(int, const char *, const char *) = __pbs_locjob;
int (*pfn_pbs_manager)(int, int, int, const char *, struct attropl *, const char *) = __pbs_manager;
int (*pfn_pbs_movejob)(int, const char *, const char *, const char *) = __pbs_movejob;
int (*pfn_pbs_msgjob)(int, const char *, int, const char *, const char *) = __pbs_msgjob;
int (*pfn_pbs_orderjob)(int, const char *, const char *, const char *) = __pbs_orderjob;
int (*pfn_pbs_rerunjob)(int, const char *, const char *) = __pbs_rerunjob;
int (*pfn_pbs_rlsjob)(int, const char *, const char *, const char *) = __pbs_rlsjob;
int (*pfn_pbs_runjob)(int, const char *, const char *, const char *) = __pbs_runjob;
char **(*pfn_pbs_selectjob)(int, struct attropl *, const char *) = __pbs_selectjob;
int (*pfn_pbs_sigjob)(int, const char *, const char *, const char *) = __pbs_sigjob;
void (*pfn_pbs_statfree)(struct batch_status *) = __pbs_statfree;
void (*pfn_pbs_delstatfree)(struct batch_deljob_status *) = __pbs_delstatfree;
struct batch_status *(*pfn_pbs_statrsc)(int, const char *, struct attrl *, const char *) = __pbs_statrsc;
struct batch_status *(*pfn_pbs_statjob)(int, const char *, struct attrl *, const char *) = __pbs_statjob;
struct batch_status *(*pfn_pbs_selstat)(int, struct attropl *, struct attrl *, const char *) = __pbs_selstat;
struct batch_status *(*pfn_pbs_statque)(int, const char *, struct attrl *, const char *) = __pbs_statque;
struct batch_status *(*pfn_pbs_statserver)(int, struct attrl *, const char *) = __pbs_statserver;
struct batch_status *(*pfn_pbs_statsched)(int, struct attrl *, const char *) = __pbs_statsched;
struct batch_status *(*pfn_pbs_stathost)(int, const char *, struct attrl *, const char *) = __pbs_stathost;
struct batch_status *(*pfn_pbs_statnode)(int, const char *, struct attrl *, const char *) = __pbs_statnode;
struct batch_status *(*pfn_pbs_statvnode)(int, const char *, struct attrl *, const char *) = __pbs_statvnode;
struct batch_status *(*pfn_pbs_statresv)(int, const char *, struct attrl *, const char *) = __pbs_statresv;
struct batch_status *(*pfn_pbs_stathook)(int, const char *, struct attrl *, const char *) = __pbs_stathook;
struct ecl_attribute_errors * (*pfn_pbs_get_attributes_in_error)(int) = __pbs_get_attributes_in_error;
char *(*pfn_pbs_submit)(int, struct attropl *, const char *, const char *, const char *) = __pbs_submit;
char *(*pfn_pbs_submit_resv)(int, struct attropl *, const char *) = __pbs_submit_resv;
char *(*pfn_pbs_modify_resv)(int, const char *, struct attropl *, const char *) = __pbs_modify_resv;
int (*pfn_pbs_delresv)(int, const char *, const char *) = __pbs_delresv;
int (*pfn_pbs_relnodesjob)(int, const char *, const char *, const char *) = __pbs_relnodesjob;
int (*pfn_pbs_terminate)(int, int, const char *) = __pbs_terminate;
preempt_job_info *(*pfn_pbs_preempt_jobs)(int, char**) = __pbs_preempt_jobs;
int (*pfn_pbs_register_sched)(const char *, int, int) = __pbs_register_sched;
