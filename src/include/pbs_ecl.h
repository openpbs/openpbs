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

#ifndef _PBS_ECL_H
#define _PBS_ECL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "portability.h"
#include "list_link.h"
#include "attribute.h"
#include "resource.h"

#define SLOT_INCR_SIZE 10

extern ecl_attribute_def ecl_svr_attr_def[];
extern ecl_attribute_def ecl_node_attr_def[];
extern ecl_attribute_def ecl_que_attr_def[];
extern ecl_attribute_def ecl_job_attr_def[];
extern ecl_attribute_def ecl_svr_resc_def[];
extern ecl_attribute_def ecl_resv_attr_def[];
extern ecl_attribute_def ecl_sched_attr_def[];

extern int ecl_svr_resc_size;
extern int ecl_job_attr_size;
extern int ecl_que_attr_size;
extern int ecl_node_attr_size;
extern int ecl_resv_attr_size;
extern int ecl_svr_attr_size;
extern int ecl_sched_attr_size;

void set_no_attribute_verification(void);

extern int (*pfn_pbs_verify_attributes)(int connect, int batch_request,
					int parent_object, int command, struct attropl *attribute_list);

#define pbs_verify_attributes(connect, batch_request, parent_object, \
			      cmd, attribute_list)                   \
	(*pfn_pbs_verify_attributes)(connect, batch_request,         \
				     parent_object, cmd, attribute_list)

int verify_an_attribute(int, int, int, struct attropl *, int *, char **);
int verify_attributes(int, int, int, struct attropl *, struct ecl_attribute_errors **);

ecl_attribute_def *ecl_find_resc_def(ecl_attribute_def *, char *, int);
struct ecl_attribute_errors *ecl_get_attr_err_list(int);
void ecl_free_attr_err_list(int);

/* verify datatype functions */
int verify_datatype_bool(struct attropl *, char **);
int verify_datatype_short(struct attropl *, char **);
int verify_datatype_long(struct attropl *, char **);
int verify_datatype_size(struct attropl *, char **);
int verify_datatype_float(struct attropl *, char **);
int verify_datatype_time(struct attropl *, char **);
int verify_datatype_nodes(struct attropl *, char **);
int verify_datatype_select(struct attropl *, char **);
int verify_datatype_long_long(struct attropl *, char **);

/* verify value functions */
int verify_value_resc(int, int, int, struct attropl *, char **);
int verify_value_select(int, int, int, struct attropl *, char **);
int verify_value_preempt_targets(int, int, int, struct attropl *, char **);
int verify_value_preempt_queue_prio(int, int, int, struct attropl *, char **);
int verify_value_preempt_prio(int, int, int, struct attropl *, char **);
int verify_value_preempt_order(int, int, int, struct attropl *, char **);
int verify_value_preempt_sort(int, int, int, struct attropl *, char **);
int verify_value_dependlist(int, int, int, struct attropl *, char **);
int verify_value_user_list(int, int, int, struct attropl *, char **);
int verify_value_authorized_users(int, int, int, struct attropl *, char **);
int verify_value_authorized_groups(int, int, int, struct attropl *, char **);
int verify_value_path(int, int, int, struct attropl *, char **);
int verify_value_jobname(int, int, int, struct attropl *, char **);
int verify_value_checkpoint(int, int, int, struct attropl *, char **);
int verify_value_hold(int, int, int, struct attropl *, char **);
int verify_value_credname(int, int, int, struct attropl *, char **);
int verify_value_zero_or_positive(int, int, int, struct attropl *, char **);
int verify_value_non_zero_positive(int, int, int, struct attropl *, char **);
int verify_value_non_zero_positive_long_long(int, int, int, struct attropl *, char **);
int verify_value_maxlicenses(int, int, int, struct attropl *, char **);
int verify_value_minlicenses(int, int, int, struct attropl *, char **);
int verify_value_licenselinger(int, int, int, struct attropl *, char **);
int verify_value_mgr_opr_acl_check(int, int, int, struct attropl *, char **);
int verify_value_queue_type(int, int, int, struct attropl *, char **);
int verify_value_joinpath(int, int, int, struct attropl *, char **);
int verify_value_keepfiles(int, int, int, struct attropl *, char **);
int verify_keepfiles_common(char *value);
int verify_value_mailpoints(int, int, int, struct attropl *, char **);
int verify_value_mailusers(int, int, int, struct attropl *, char **);
int verify_value_removefiles(int, int, int, struct attropl *, char **);
int verify_removefiles_common(char *value);
int verify_value_priority(int, int, int, struct attropl *, char **);
int verify_value_shellpathlist(int, int, int, struct attropl *, char **);
int verify_value_sandbox(int, int, int, struct attropl *, char **);
int verify_value_stagelist(int, int, int, struct attropl *, char **);
int verify_value_jrange(int, int, int, struct attropl *, char **);
int verify_value_state(int, int, int, struct attropl *, char **);
int verify_value_tolerate_node_failures(int, int, int, struct attropl *, char **);

/* verify object name function */
int pbs_verify_object_name(int, const char *);

#ifdef __cplusplus
}
#endif

#endif /* _PBS_ECL_H */
