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

#ifndef _PBS_RELIABLE_H
#define _PBS_RELIABLE_H

#ifdef __cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"
#include "libutil.h"
#include "placementsets.h"
#include "list_link.h"

#define DEFAULT_JOINJOB_ALARM 30
#define DEFAULT_JOB_LAUNCH_DELAY 30
/*
 *
 *  pbs_reliable.h
 *  This file contains all the definitions that are used by
 *  server/mom/hooks for supporting reliable job startup.
 *
 */

/*
 * The reliable_job_node structure is used to keep track of nodes
 * representing mom hosts fore reliable job startup.
 */
typedef struct reliable_job_node {
	pbs_list_link rjn_link;
	int prologue_hook_success;	    /* execjob_prologue hook execution succeeded */
	char rjn_host[PBS_MAXHOSTNAME + 1]; /* mom host name */
} reliable_job_node;

extern reliable_job_node *reliable_job_node_find(pbs_list_head *, char *);
extern int reliable_job_node_add(pbs_list_head *, char *);
extern void reliable_job_node_delete(pbs_list_head *, char *);
extern reliable_job_node *reliable_job_node_set_prologue_hook_success(pbs_list_head *, char *);
extern void reliable_job_node_free(pbs_list_head *);
extern void reliable_job_node_print(char *, pbs_list_head *, int);

/**
 *
 * @brief
 * 	The relnodes_input_t structure contains the input request
 * 	parameters to the pbs_release_nodes_*() function.
 *
 * @param[in]	jobid - pointer to id of the job being released
 * @param[in]	vnodes_data - list of vnodes and their data in the system
 * @param[in]	execvnode - job's exec_vnode value
 * @param[in]	exechost - job's exec_host value
 * @param[in]	exechost2 - job's exec_host2 value
 * @param[in]	schedselect - job's schedselect value
 * @param[out]	p_new_exec_vhode - holds the new exec_vnode value after release
 * @param[out]	p_new_exec_host - holds the new exec_host value after release
 * @param[out]	p_new_exec_host2 - holds the new exec_host2 value after release
 * @param[out]	p_new_schedselect - holds the new schedselect value after release
 *
 */
typedef struct relnodes_input {
	char *jobid;
	void *vnodes_data;
	char *execvnode;
	char *exechost;
	char *exechost2;
	char *schedselect;
	char **p_new_exec_vnode;
	char **p_new_exec_host[2];
	char **p_new_schedselect;
} relnodes_input_t;

/**
 *
 * @brief
 * 	The relnodes_given_nodelist_t structure contains the additional
 * 	input parameters to the pbs_release_nodes(_given_vnodelist) function
 *	when called to release a set of vnodes.
 *
 * @param[in]	vnodelist - list of vnodes to release
 * @param[in]	deallocated_nodes_orig - job's current deallocated_exevnode value
 * @param[out]	p_new_deallocated_execvnode - holds the new deallocated_exec_vnode after release
 */
typedef struct relnodes_input_vnodelist {
	char *vnodelist;
	char *deallocated_nodes_orig;
	char **p_new_deallocated_execvnode;
} relnodes_input_vnodelist_t;

/**
 *
 * @brief
 * 	The relnodes_given_select_t structure contains the input
 * 	parameters to the pbs_release_nodes_given_select() function
 *	when called to satisfy select_str parameter.
 *
 * @param[in]	select_str - job's select value after nodes are released
 * @param[in]	failed_mom_list - list of unhealthy moms
 * @param[in]	succeeded_mom_list - list of healthy moms
 * @param[in]	failed_vnodes - list of vnodes assigned to the job managed by unhealthy moms
 * @param[in]	good_vnodes- list of vnodes assigned to the job managed by healthy moms
 */
typedef struct relnodes_input_select {
	char *select_str;
	pbs_list_head *failed_mom_list;
	pbs_list_head *succeeded_mom_list;
	vnl_t **failed_vnodes;
	vnl_t **good_vnodes;
} relnodes_input_select_t;

extern void relnodes_input_init(relnodes_input_t *r_input);
extern void relnodes_input_vnodelist_init(relnodes_input_vnodelist_t *r_input);
extern void relnodes_input_select_init(relnodes_input_select_t *r_input);
extern int pbs_release_nodes_given_select(relnodes_input_t *r_input, relnodes_input_select_t *r_input2, char *err_msg, int err_msg_sz);

extern int pbs_release_nodes_given_nodelist(relnodes_input_t *r_input, relnodes_input_vnodelist_t *r_input2, char *err_msg, int err_msg_sz);

extern int do_schedselect(char *, void *, void *, char **, char **);

#include "placementsets.h"
extern int prune_exec_vnode(job *pjob, char *select_str, vnl_t **failed_vnodes, vnl_t **good_vnodes, char *err_msg, int err_msg_sz);

// clang-format off
#define FREE_VNLS(vnf, vng) { \
vnl_free(vnf); \
vnf = NULL; \
vnl_free(vng); \
vng = NULL; \
}

// clang-format on

#ifdef __cplusplus
}
#endif

#endif /* _PBS_INTERNAL_H */
