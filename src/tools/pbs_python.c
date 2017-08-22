/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
/**
 * @file
 *		pbs_python.c
 *
 * @brief
 *		This file contains functions related to Pbs  with Python.
 *
 * Functions included are:
 * 	check_que_enable()
 * 	decode_rcost()
 * 	encode_rcost()
 * 	encode_svrstate()
 * 	decode_depend()
 * 	encode_depend()
 * 	node_queue_action()
 * 	node_np_action()
 * 	node_pcpu_action()
 * 	return_external_value()
 * 	return_internal_value()
 * 	pbs_python_populate_svrattrl_from_file()
 * 	pbs_python_populate_server_svrattrl_from_file()
 * 	fprint_svrattrl_list()
 * 	fprint_str_array()
 * 	argv_list_to_str()
 * 	main()
 */
#include <pbs_config.h>

#include <Python.h>

#include <pbs_ifl.h>
#include <pbs_internal.h>
#include <pbs_version.h>

#ifdef NAS /* localmod 005 */
#include <ctype.h>
#endif /* localmod 005 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <pbs_python.h>
#include <pbs_error.h>
#include <pbs_entlim.h>
#include <work_task.h>
#include <resource.h>
#include <list_link.h>
#include <attribute.h>
#include "libpbs.h"
#include "batch_request.h"
#include "hook.h"
#include <signal.h>
#include "job.h"
#include "reservation.h"
#include "server.h"
#include "queue.h"
#include <pbs_nodes.h>
#include "libutil.h"
#include "cmds.h"
#include "svrfunc.h"

#define PBS_PYTHON 1.1
#define MAXBUF	4096
#define PYHOME "PYTHONHOME"
#define PYHOME_EQUAL "PYTHONHOME="

#define HOOK_MODE "--hook"

struct python_interpreter_data  svr_interp_data;

extern 	char		*vnode_state_to_str(int state_bit);
extern	char		*vnode_sharing_to_str(enum vnode_sharing vns);
extern	char		*vnode_ntype_to_str(int type);

extern 	int		str_to_vnode_state(char *state_str);
extern 	int		str_to_vnode_ntype(char *ntype_str);
extern 	enum vnode_sharing str_to_vnode_sharing(char *sharing_str);

char server_name[PBS_MAXSERVERNAME+1];
char server_host[PBS_MAXHOSTNAME+1];	   /* host_name of this svr */
int  have_blue_gene_nodes = 0;
time_t		time_now = 0;
struct pbsnode **pbsndlist;
int		svr_totnodes = 0;
struct server	server;


char            *pbs_server_name;
char            *pbs_server_id;
char		*resc_in_err = NULL;

pbs_list_head	task_list_immed;
pbs_list_head	task_list_timed;
pbs_list_head	task_list_event;
int		svr_delay_entry;

pbs_list_head	svr_queues;
pbs_list_head	svr_alljobs;
pbs_list_head	svr_allresvs;

pbs_list_head	svr_allhooks;
pbs_list_head	svr_queuejob_hooks;
pbs_list_head	svr_modifyjob_hooks;
pbs_list_head	svr_resvsub_hooks;
pbs_list_head	svr_movejob_hooks;
pbs_list_head	svr_runjob_hooks;
pbs_list_head	svr_provision_hooks;
pbs_list_head	svr_periodic_hooks;
pbs_list_head	svr_execjob_begin_hooks;
pbs_list_head	svr_execjob_prologue_hooks;
pbs_list_head	svr_execjob_epilogue_hooks;
pbs_list_head	svr_execjob_preterm_hooks;
pbs_list_head	svr_execjob_launch_hooks;
pbs_list_head	svr_execjob_end_hooks;
pbs_list_head	svr_exechost_periodic_hooks;
pbs_list_head	svr_exechost_startup_hooks;
pbs_list_head	svr_execjob_attach_hooks;

char 		*path_hooks;
char 		*path_hooks_workdir;
char           *path_rescdef = NULL;


/*
 *	BEGIN of the list of "dummy", unused functions needed so that pbs_python
 *	can be linked to svr_attr_def.o, job_attr_def.o, node_attr_def.o,
 *	queue_attr_def.o, resv_attr_def.o
 *
 */


int
set_resources_min_max(attribute *old, attribute *new, enum batch_op op)
{
	return (0);
}

void
set_scheduler_flag(int flag, pbs_sched *psched)
{
	return;
}

job	*
find_job(char *jobid)
{
	return (NULL);
}

resc_resv *
find_resv(char *resvid)
{
	return (NULL);
}

pbs_queue *
find_queuebyname(char *qname)
{
	return (NULL);
}

struct pbsnode *find_nodebyname(char *nname)
{
	return (NULL);
}

void
write_node_state(void)
{
	return;
}


void
save_characteristic(struct pbsnode *pnode)
{
	return;
}

int
chk_characteristic(struct pbsnode *pnode, int *pneed_todo)
{
	return (0);
}


void
mgr_log_attr(char *msg, struct svrattrl *plist, int logclass,
	char *objname, char *hookname)
{
	return;
}

int
mgr_set_attr(attribute *pattr, attribute_def *pdef, int limit,
	svrattrl *plist, int privil, int *bad, void *parent, int mode)
{
	return (0);
}

int
svr_chk_history_conf(void)
{
	return (0);
}

int
save_nodes_db(int flag, void *pmom)
{
	return (0);
}

void
update_state_ct(attribute *pattr, int *ct_array, char *buf)
{
	return;
}

void
update_license_ct(attribute *pattr, char *buf)
{
	return;
}

int
is_job_array(char *jobid)
{
	return (0);
}

job *
find_arrayparent(char *subjobid)
{
	return (NULL);
}

int
ck_chkpnt(pattr, pobject, mode)
attribute *pattr;
void	  *pobject;	/* not used */
int	   mode;	/* not used */
{
	return (0);
}

int
cred_name_okay(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
poke_scheduler(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
set_sched_throughput_mode(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
action_sched_port(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
action_sched_priv(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
action_sched_log(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
action_sched_iteration(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
action_sched_user(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
action_queue_partition(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
set_reserve_retry_init(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
set_reserve_retry_cutoff(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
set_rpp_retry(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
set_rpp_highwater(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int	   actmode;
{
	return PBSE_NONE;
}

int
is_valid_resource(attribute *pattr, void *pobject, int actmode)
{

	return PBSE_NONE;
}

int
ssignon_transition_okay(attribute *pattr, void *pobject, int actmode)
{
	return (0);

}

int
deflt_chunk_action(attribute *pattr, void *pobj, int mode)
{

	return 0;
}

int
action_svr_iteration(attribute *pattr, void *pobj, int mode)
{
	return 0;
}

int
set_license_location(attribute *pattr, void *pobject, int actmode)
{

	return (PBSE_NONE);
}

void
unset_license_location(void)
{

	return;

}

int
set_node_fail_requeue(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

void
unset_node_fail_requeue(void)
{
	return;
}

int
action_node_partition(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

int
set_license_min(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

void
unset_license_min(void)
{
	return;
}

int
set_license_max(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

void
unset_license_max(void)
{
	return;
}

int
set_license_linger(attribute *pattr, void *pobject, int actmode)
{

	return (PBSE_NONE);
}

void
unset_license_linger(void)
{
	return;
}

void
unset_job_history_enable(void)
{
	return;
}

int
set_job_history_enable(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

int
set_job_history_duration(attribute *pattr, void *pobject, int actmode)
{

	return (PBSE_NONE);
}

void
unset_job_history_duration(void)
{
	return;
}

int
eligibletime_action(attribute *pattr, void *pobject, int actmode)
{
	return 0;
}

int
decode_formula(attribute *patr, char *name, char *rescn, char *val)
{
	return PBSE_NONE;
}

int
action_entlim_chk(attribute *pattr, void *pobject, int actmode)
{
	return PBSE_NONE;
}

int
action_entlim_ct(attribute *pattr, void *pobject, int actmode)
{
	return PBSE_NONE;
}

int
action_entlim_res(attribute *pattr, void *pobject, int actmode)
{
	return PBSE_NONE;
}

int
check_no_entlim(pattr, pobject, actmode)
attribute *pattr;
void *pobject;
int actmode;
{
	return 0;
}

int
default_queue_chk(pattr, pobj, actmode)
attribute *pattr;
void      *pobj;
int        actmode;
{
	return (PBSE_NONE);
}

void
set_vnode_state(struct pbsnode *pnode, unsigned long state_bits, enum vnode_state_op type)
{
	return;
}

int
ctcpus(char *buf, int *hascpp)
{
	return 0;
}

int
validate_nodespec(char *str)
{
	return 0;
}
/**
 * @brief
 * 		check_que_enable - check if it is ok to enable queue
 *
 * @param[in]	pattr	-	pointer to attribute
 * @param[in]	pque	-	pointer to queue
 * @param[in]	mode	-	mode
 *
 * @return	int
 * @retval	0	: ok to enable queue
 */
int
check_que_enable(attribute *pattr, void *pque, int mode)
{
	return (0);
}

int
set_queue_type(pattr, pque, mode)
attribute *pattr;
void      *pque;
int	   mode;
{
	return (0);
}

int
manager_oper_chk(pattr, pobject, actmode)
attribute *pattr;
void      *pobject;
int	   actmode;
{
	return (0);
}

int
node_comment(attribute *pattr, void *pobj, int act)
{
	return 0;
}

int
node_prov_enable_action(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
set_log_events(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
node_current_aoe_action(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

/**
 * @brief
 * 		decode_rcost - decode string into resource cost value
 *
 * @param[in,out]	pattr	-	pointer to attribute
 * @param[in]	name	-	attribute name
 * @param[in]	rescn	-	resource name, unused here
 * @param[in]	val	-	attribute value
 *
 * @return	int
 * @retval	0	: ok to enable queue
 * @retval	>0	: error number if error
 */

int
decode_rcost(struct attribute *patr, char *name, char *rescn, char *val)
{
	return 0;
}

int
encode_rcost(attr, phead, atname, rsname, mode, rtnl)
attribute	*attr;	  /* ptr to attribute */
pbs_list_head	*phead;	  /* head of attrlist list */
char		*atname;  /* attribute name */
char		*rsname;  /* resource name or null */
int		mode;	  /* encode mode, unused here */
svrattrl      **rtnl;	  /* RETURN: ptr to svrattrl */
{
	return (1);
}

int
set_rcost(old, new, op)
struct attribute *old;
struct attribute *new;
enum batch_op op;
{
	return (0);
}

void
free_rcost(pattr)
attribute *pattr;
{
	return;
}

int
svr_max_conc_prov_action(attribute *new, void *pobj, int act)
{
	return 0;
}

int
action_backfill_depth(attribute *pattr, void *pobj, int actmode) {

	return PBSE_NONE;
}

int
action_jobscript_max_size(attribute *pattr, void *pobj, int actmode) {

	return PBSE_NONE;
}

int
action_check_res_to_release(attribute *pattr, void *pobj, int actmode) {

	return PBSE_NONE;
}

int
queuestart_action(attribute *pattr, void *pobject, int actmode)
{
	return 0;
}

int
action_power_provisioning(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

/**
 * @brief
 * 		encode_svrstate - encode string into svrstate value
 *
 * @param[in,out]	pattr	-	pointer to attribute
 * @param[in]	phead	-	head of attrlist list
 * @param[in]	atname	-	attribute name
 * @param[in]	rsname	-	null
 * @param[in]	mode	-	encode mode
 * @param[out]	rtnl	-	RETURN: ptr to svrattrl
 */
int
encode_svrstate(attribute *pattr, pbs_list_head *phead, char *atname, char *rsname, int mode, svrattrl **rtnl)
{
	return (1);
}

int
comp_chkpnt(attr, with)
attribute *attr;
attribute *with;
{
	return 0;
}
/**
 * @brief
 * 		decode_depend - decode dependent resources.
 *
 * @param[in,out]	patr	-	pointer to attribute
 * @param[in]	name	-	attribute name
 * @param[in]	rescn	-	resource name, unused here
 * @param[in]	val	-	attribute value
 */
int
decode_depend(struct attribute *patr, char *name, char *rescn, char *val)
{
	return (0);
}
/**
 * @brief
 * 		encode_depend - decode dependent resources.
 *
 * @param[in,out]	attr	-	ptr to attribute to encode
 * @param[in]	phead	-	ptr to head of attrlist list
 * @param[in]	atname	-	attribute name
 * @param[in]	rsname	-	resource name or null
 * @param[in]	mode	-	encode mode, unused here
 * @param[out]	rtnl	-	Return ptr to svrattrl
 *
 * @return	int
 * @retval	success
 */
int
encode_depend(attribute *attr, pbs_list_head *phead, char *atname, char *rsname, int mode, svrattrl **rtnl)
{
	return 0;
}

int
set_depend(attr, new, op)
struct attribute *attr;
struct attribute *new;
enum batch_op op;
{
	return (0);
}

int
comp_depend(attr, with)
struct attribute *attr;
struct attribute *with;
{

	return (-1);

}

void
free_depend(attr)
struct attribute *attr;
{
	return;
}

int
depend_on_que(pattr, pobj, mode)
attribute *pattr;
void      *pobj;
int        mode;
{
	return 0;
}

int
job_set_wait(attribute *pattr, void *pjob, int mode)
{
	return (0);
}

int
alter_eligibletime(attribute *pattr, void *pobject, int actmode)
{
	return PBSE_NONE;
}

int
keepfiles_action(attribute *pattr, void *pobject, int actmode)
{
    return PBSE_NONE;
}

int
removefiles_action(attribute *pattr, void *pobject, int actmode)
{
    return PBSE_NONE;
}

int
action_est_start_time_freq(attribute *pattr, void *pobj, int actmode)
{
	return PBSE_NONE;
}


int
decode_sandbox(struct attribute *patr, char *name, char *rescn, char *val)
{
	return 0;
}

int
decode_project(struct attribute *patr, char *name, char *rescn, char *val)
{
	return 0;
}


int
setup_arrayjob_attrs(attribute *pattr, void *pobj, int mode)
{
	return (PBSE_NONE);
}

int
fixup_arrayindicies(attribute *pattr, void *pobj, int mode)
{
	return (PBSE_NONE);
}


int
decode_Mom_list(struct attribute *patr, char *name, char *rescn, char *val)
{
	return (0);
}
/**
 * @brief
 * 		action function for node queue.
 *
 * @param[in,out]	pattr	-	attribute
 * @param[in]	pobj	-	pointer to a pbsnode struct
 * @param[in]	actmode	-	action mode; "NEW" or "ALTER"
 */
int
node_queue_action(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
set_node_host_name(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}

int
set_node_mom_port(attribute *pattr, void *pobj, int actmode)
{
	return 0;
}
/**
 * @brief
 * 		node_np_action
 *
 * @param[in]	new	-	newly changed resources_available
 * @param[in]	pobj	-	ointer to a pbsnode struct
 * @param[in]	actmode	-	action mode: "NEW" or "ALTER"
 *
 * @return	int
 * @retval	PBSE_NONE	: no error.
 */
int
node_np_action(attribute *new, void *pobj, int actmode)
{
	return PBSE_NONE;
}
/**
 * @brief
 * 		node_pcpu_action
 *
 * @param[in]	new	-	derive props into this attribute
 * @param[in]	pobj	-	pointer to a pbsnode struct
 * @param[in]	actmode	-	action mode; "NEW" or "ALTER"
 *
 * @return	int
 * @retval	0	: no error.
 */
int
node_pcpu_action(attribute *new, void *pobj, int actmode)
{

	return (0);

}

char*
find_aoe_from_request(resc_resv *presv)
{
	return (NULL);
}

int
force_qsub_daemons_update_action(attribute *pattr, void *pobject,
	int actmode)
{
	return (PBSE_NONE);
}

int
set_node_topology(attribute *pattr, void *pobject, int actmode)
{

	return (PBSE_NONE);
}

int
chk_vnode_pool(attribute *pattr, void *pobject, int actmode)
{
	return (PBSE_NONE);
}

/*
 *	END of "dummy" functions. ---------------------------------------->
 */

/**
 * @brief
 *		Returns the "external" form of the attribute 'val' given 'name'.
 *
 * @param[in]	name	-	attribute name
 * @param[in]	val	-	attribute value
 *
 * @return char *	: the external form for name=state: "3" -> "down,offline"
 * @Note
 *     	Returns a static value that can potentially get cleaned up on next call.
 * 		Must use return value immediately!
 */
static char *
return_external_value(char *name, char *val)
{
	char *vns;


	if ((name == NULL) || (val == NULL))
		return ("");

	if (strcmp(name, ATTR_NODE_state) == 0) {
		return vnode_state_to_str(atoi(val));
	} else if (strcmp(name, ATTR_NODE_Sharing) == 0) {
		vns = vnode_sharing_to_str((enum vnode_sharing)atoi(val));
		return (vns?vns:"");
	} else if (strcmp(name, ATTR_NODE_ntype) == 0) {
		return vnode_ntype_to_str(atoi(val));
	} else {
		return val;
	}
}

/**
 * @brief
 *		Returns the "internal" form of the attribute 'val' given 'name'.
 *
 * @param[in]	name	-	attribute name
 * @param[in]	val	-	attribute value
 *
 * @return char *	: the external form for name=state: "down,offline" -> "3"
 * @Note
 *     	Returns a static value that can potentially get cleaned up on next call.
 * 		Must use return value immediately!
 *
 * @par MT-safe: No
 */
static char *
return_internal_value(char *name, char *val)
{
	static char ret_str[40];
	enum vnode_sharing share;
	int  v;

	if ((name == NULL) || (val == NULL))
		return ("");

	if (strcmp(name, ATTR_NODE_state) == 0) {
		v=str_to_vnode_state(val);
		sprintf(ret_str, "%d", v);
		return (ret_str);
	} else if (strcmp(name, ATTR_NODE_Sharing) == 0) {
		share = str_to_vnode_sharing(val);
		if (share == VNS_UNSET)
			return val;
		sprintf(ret_str, "%d", share);
		return (ret_str);
	} else if (strcmp(name, ATTR_NODE_ntype) == 0) {
		v = str_to_vnode_ntype(val);
		if (v == -1)
			return val;
		sprintf(ret_str, "%d", v);
		return (ret_str);
	} else {
		return val;
	}
}

/**
 * @brief
 *		Takes data from input file or stdin of the form:
 *		<attribute_name>=<attribute value>
 *		<attribute_name>[<resource_name>]=<resource value>
 *		and populate the given various lists with the value obtained.
 *
 * @param[in]	input_file	-	if NULL, will get data from stdin.
 * @param[in]	default_svrattrl	-	the "catch all" list
 * @param[in]	event_svrattrl	-	gets <attribute_name>=EVENT_OBJECT data
 * @param[in]	event_job_svrattrl	-	gets <attribute_name>=EVENT_JOB_OBJECT data
 * @param[in]	event_job_o_svrattrl	-	gets <attribute_name>=EVENT_JOB_O_OBJECT data
 * @param[in]	event_resv_svrattrl	-	gets <attribute_name>=EVENT_RESV_OBJECT data
 * @param[in]	event_vnode_svrattrl	-	gets <attribute_name>=EVENT_VNODE_OBJECT data
 * 			             					Caution: svrattrl values stored in sorted order
 * @param[in]	event_src_queue_svrattrl	-	gets <attribute_name>=EVENT_SRC_QUEUE_OBJECT data
 * @param[in]	event_aoe_svrattrl	-	gets <attribute_name=EVENT_AOE_OBJECT data
 * @param[in]	event_argv_svrattrl	-	gets <attribute_name=EVENT_ARGV_OBJECT data
 *
 * @param[in]	event_jobs_svrattrl	-	gets <attribute_name>=EVENT_JOBLIST_OBJECT data
 * 			            				Caution: svrattrl values stored in sorted order
 * @return	int
 * @retval	0	: success
 * @retval	-1	: failure, and free_attrlist() is used to free the memory
 *					associated with each non-NULL list parameter.
 *
 */
int
pbs_python_populate_svrattrl_from_file(char *input_file,
	pbs_list_head *default_svrattrl, pbs_list_head *event_svrattrl,
	pbs_list_head *event_job_svrattrl, pbs_list_head *event_job_o_svrattrl,
	pbs_list_head *event_resv_svrattrl, pbs_list_head *event_vnode_svrattrl,
	pbs_list_head *event_src_queue_svrattrl, pbs_list_head *event_aoe_svrattrl,
	pbs_list_head *event_argv_svrattrl, pbs_list_head *event_jobs_svrattrl)
{

	char *attr_name;
	char *name_str;
	char name_str_buf[STRBUF+1] = {'\0'};
	char *resc_str;
	char argv_index[STRBUF+1] = {'\0'};
	char *val_str;
	char *obj_name;
	int  rc = -1;
	char *pc, *pc1, *pc2, *pc3, *pc4;
	char *in_data = NULL;
	long int endpos;
	int in_data_sz;
	char *data_value;
	size_t ll;
	FILE *fp = NULL;
	char *p;
	int   vn_obj_len = strlen(EVENT_VNODELIST_OBJECT);
	int   job_obj_len = strlen(EVENT_JOBLIST_OBJECT);
	int   b_triple_quotes = 0;
	int   e_triple_quotes = 0;
	char  buf_data[STRBUF];

	if ((default_svrattrl == NULL) || (event_svrattrl == NULL) ||
		(event_job_svrattrl == NULL) || (event_job_o_svrattrl == NULL) ||
		(event_resv_svrattrl == NULL) || (event_vnode_svrattrl == NULL) ||
		(event_src_queue_svrattrl == NULL) || (event_aoe_svrattrl == NULL) ||
		(event_argv_svrattrl == NULL) ||
		(event_jobs_svrattrl == NULL)) {
		log_err(errno, __func__, "Bad input parameter!");
		rc = -1;
		goto populate_svrattrl_fail;
	}

	if ((input_file != NULL) && (*input_file != '\0')) {
		fp = fopen(input_file, "r");

		if (fp == NULL) {
			snprintf(log_buffer, sizeof(log_buffer),
				"failed to open input file %s", input_file);
			log_err(errno, __func__, log_buffer);
			rc = -1;
			goto populate_svrattrl_fail;
		}
	} else {
		fp = stdin;
	}

	if (default_svrattrl) free_attrlist(default_svrattrl);
	if (event_svrattrl) free_attrlist(event_svrattrl);
	if (event_job_svrattrl) free_attrlist(event_job_svrattrl);
	if (event_job_o_svrattrl) free_attrlist(event_job_o_svrattrl);
	if (event_resv_svrattrl) free_attrlist(event_resv_svrattrl);
	if (event_vnode_svrattrl) free_attrlist(event_vnode_svrattrl);
	if (event_src_queue_svrattrl) free_attrlist(event_src_queue_svrattrl);
	if (event_aoe_svrattrl) free_attrlist(event_aoe_svrattrl);
	if (event_argv_svrattrl) free_attrlist(event_argv_svrattrl);
	if (event_jobs_svrattrl) free_attrlist(event_jobs_svrattrl);


	in_data_sz = STRBUF;
	in_data = (char *)malloc(in_data_sz);
	if (in_data == NULL) {
		log_err(errno, __func__, "malloc failed");
		rc = -1;
		goto populate_svrattrl_fail;
	}
	in_data[0] = '\0';

	if (fseek(fp, 0, SEEK_END) != 0) {
		log_err(errno, __func__, "fseek to end failed");
		rc = 1;
		goto populate_svrattrl_fail;
	}
	endpos = ftell(fp);
	if (fseek(fp, 0, SEEK_SET) != 0) {
		log_err(errno, __func__, "fseek to beginning failed");
		rc = 1;
		goto populate_svrattrl_fail;
	}
	while (fgets(buf_data, STRBUF, fp) != NULL) {

		b_triple_quotes = 0;
		e_triple_quotes = 0;

		if (pbs_strcat(&in_data, &in_data_sz, buf_data) == NULL) {
			goto populate_svrattrl_fail;
		}

		ll = strlen(in_data);
#ifdef WIN32
		/* The file is being read in O_BINARY mode (see _fmode setting) */
		/* so on Windows, there's a carriage return (\r) line feed (\n), */
		/* then the linefeed needs to get processed out */
		if (ll >= 2) {
			if (in_data[ll-2] == '\r') {
				/* remove newline */
				in_data[ll-2] = '\0';
			}
		}
#endif
		if ((p = strchr(in_data, '=')) != NULL) {
			b_triple_quotes = starts_with_triple_quotes(p+1);
		}

		if (in_data[ll-1] == '\n') {
			e_triple_quotes = ends_with_triple_quotes(in_data, 0);

			if (b_triple_quotes && !e_triple_quotes) {
				int	jj;

				while (fgets(buf_data, STRBUF, fp) != NULL) {
					if (pbs_strcat(&in_data, &in_data_sz,
						buf_data) == NULL) {
						goto populate_svrattrl_fail;
					}

					jj = strlen(in_data);
					if ((in_data[jj-1] != '\n') && \
					    (ftell(fp) != endpos)) {
						/* get more input for
						 * current item.
						 */
						continue;
					}
					e_triple_quotes =
					   ends_with_triple_quotes(in_data, 0);

					if (e_triple_quotes) {
						break;
					}
				}

				if ((!b_triple_quotes && e_triple_quotes) ||
					(b_triple_quotes && !e_triple_quotes)) {
					snprintf(log_buffer, sizeof(log_buffer),
						"unmatched triple quotes! Skipping  line %s",
						in_data);
					log_err(PBSE_INTERNAL, __func__, log_buffer);
					/* process a new line */
					in_data[0] = '\0';
					continue;
				}
				in_data[strlen(in_data)-1] = '\0';

			} else {
				/* remove newline */
				in_data[ll-1] = '\0';
			}
		} else if (ftell(fp) != endpos) { /* continued on next line */
			/* get more input for current item.  */
			continue;
		}
		data_value = NULL;
		if ((p=strchr(in_data, '=')) != NULL) {
			int i;
			*p = '\0';
			p++;
			/* Given '<obj_name>=<data_value>' line, */
			/* strip off leading spaces from <data_value> */
			while (isspace(*p))
				p++;
			if (b_triple_quotes) {
				/* strip triple quotes */
				p += 3;
			}
			data_value = p;
			if (e_triple_quotes) {
				(void)ends_with_triple_quotes(p, 1);
			}

			i = strlen(p);
			while (--i > 0) {	/* strip trailing blanks */
				if (!isspace((int)*(p+i)))
					break;
				*(p+i) = '\0';
			}

		}
		obj_name = in_data;

		pc = strrchr(in_data, '.');
		if (pc) {
			*pc = '\0';
			pc++;
		} else {
			pc = in_data;
		}
		name_str = pc;

		pc1 = strchr(pc, '[');
		pc2 = strchr(pc, ']');
		resc_str = NULL;
		if (pc1 && pc2 && (pc2 > pc1)) {
			*pc1 = '\0';
			pc1++;
			resc_str = pc1;
			*pc2 = '\0';
			pc2++;

			/* now let's if there's anything quoted inside */
			pc3 = strchr(pc1, '"');
			if (pc3 != NULL)
				pc4 = strchr(pc3+1, '"');
			else
				pc4 = NULL;

			if (pc3 && pc4 && (pc4 > pc3)) {
				pc3++;
				*pc4 = '\0';
				resc_str = pc3;
			}
		}

		val_str = NULL;
		if (data_value) {
			val_str = data_value;

			if (strcmp(obj_name, EVENT_OBJECT) == 0) {
				if (strcmp(name_str, PY_EVENT_PARAM_ARGLIST) == 0) {
					if (event_argv_svrattrl) {
						/* 'resc_str' holds the */
						/* numeric index to argv (0,1,...). */
						/* enumerating argv[0], argv[1],... */
						/* argv_index is the 'resc_str' value */
						/* that is padded to have a fixed */
						/* length, so that when use as a sort */
						/* key, natural ordering is respected */
						/* in the lexicographical comparison */
						/* done by add_to_svrattrl_list_sorted(). */
						/* Without the padding, the argv index */
						/* would get ordered as 0,1,10,11,12,2,3,.. */
						/* With padding, then the order would be */
						/* 000,001,002,003,...,010,011,... */
						/* respecting natural order. */
						/* leading zeros added up to a length of 8 */
						snprintf(argv_index, sizeof(argv_index)-1,
							"%08d", atoi(resc_str));

						rc = add_to_svrattrl_list_sorted(event_argv_svrattrl, name_str, resc_str, val_str, 0, argv_index);
					}
				} else {
					if (event_svrattrl)
						rc = add_to_svrattrl_list(event_svrattrl, name_str, resc_str, val_str, 0, NULL);
				}
			} else if( event_job_svrattrl && \
			(strcmp(obj_name, EVENT_JOB_OBJECT) == 0) ) {
				rc = add_to_svrattrl_list(event_job_svrattrl, name_str,
					resc_str, val_str, 0, NULL);
			} else if( event_job_o_svrattrl && \
			(strcmp(obj_name, EVENT_JOB_O_OBJECT) == 0) ) {
				rc = add_to_svrattrl_list(event_job_o_svrattrl, name_str,
					resc_str, val_str, 0, NULL);
			} else if( event_resv_svrattrl && \
			     (strcmp(obj_name, EVENT_RESV_OBJECT) == 0) ) {
				rc = add_to_svrattrl_list(event_resv_svrattrl, name_str,
					resc_str, val_str, 0, NULL);
			} else if( event_vnode_svrattrl && \
			(strncmp(obj_name, EVENT_VNODELIST_OBJECT,
				vn_obj_len) == 0)) {

				/* pbs.event().vnode_list[<vnode_name>]\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.event().vnode_list[<vnode_name>]
				 *	  name_str = <attribute name>
				 */

				/* import here to look for the leftmost '[' (using strchr)
				 * and the rightmost ']' (using strrchr)
				 * as we can have:
				 *		pbs.event().vnode_list["altix[5]"].<attr>=<val>
				 * and "altix[5]" is a valid vnode id.
				 */
				if (((pc1=strchr(obj_name, '[')) != NULL) &&
					((pc2=strrchr(obj_name, ']')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <vnode_name> part */

					*pc2 = '.'; /* pbs.event().vnode_list[<vnode_name>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <vnode_name>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <vnode_name>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a vnode name!", obj_name);
					log_err(-1, __func__, log_buffer);
					/* process a new line */
					in_data[0] = '\0';
					continue;
				}
				rc = add_to_svrattrl_list_sorted(event_vnode_svrattrl,
					name_str, resc_str,
					return_internal_value(attr_name, val_str), 0, NULL);
			} else if( event_jobs_svrattrl && \
			(strncmp(obj_name, EVENT_JOBLIST_OBJECT,
				job_obj_len) == 0)) {

				/* pbs.event().job_list[<jobid>]\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.event().job_list[<jobid>]
				 *	  name_str = <attribute name>
				 */

				/* import here to look for the leftmost '[' (using strchr)
				 * and the rightmost ']' (using strrchr)
				 * as we can have:
				 *		pbs.event().job_list["5.altix"].<attr>=<val>
				 * and "5.altix" is a valid job id.
				 */
				if (((pc1=strchr(obj_name, '[')) != NULL) &&
					((pc2=strrchr(obj_name, ']')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <jobid> part */

					*pc2 = '.'; /* pbs.event().job_list[<jobid>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <jobid>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <jobid>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a job name!", obj_name);
					log_err(-1, __func__, log_buffer);
					/* process a new line */
					in_data[0] = '\0';
					continue;
				}
				rc = add_to_svrattrl_list_sorted(event_jobs_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
			} else if( event_src_queue_svrattrl && \
			(strcmp(obj_name, EVENT_SRC_QUEUE_OBJECT) == 0) ) {
				rc = add_to_svrattrl_list(event_src_queue_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
			} else if( event_aoe_svrattrl && \
			 (strcmp(obj_name, EVENT_AOE_OBJECT) == 0) ) {
				rc = add_to_svrattrl_list(event_aoe_svrattrl, name_str,
					resc_str, val_str, 0, NULL);
			} else if ((strcmp(obj_name, PBS_OBJ) == 0) &&
				(strcmp(name_str, GET_NODE_NAME_FUNC) == 0)) {
				strncpy(svr_interp_data.local_host_name, val_str,
					PBS_MAXHOSTNAME);
				rc = 0;
			} else {
				rc = add_to_svrattrl_list(default_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
			}

			if (rc == -1) {
				snprintf(log_buffer, sizeof(log_buffer),
					"failed to add_to_svrattrl_list(%s,%s,%s",
					name_str, resc_str, (val_str?val_str:""));
				log_err(errno, __func__, log_buffer);
				goto populate_svrattrl_fail;
			}
		}
		in_data[0] = '\0';
	}

	if (fp != stdin)
		fclose(fp);

	if (in_data != NULL) {
		free(in_data);
	}
	return (0);

populate_svrattrl_fail:
	if (default_svrattrl) free_attrlist(default_svrattrl);
	if (event_svrattrl) free_attrlist(event_svrattrl);
	if (event_job_svrattrl) free_attrlist(event_job_svrattrl);
	if (event_job_o_svrattrl) free_attrlist(event_job_o_svrattrl);
	if (event_resv_svrattrl) free_attrlist(event_resv_svrattrl);
	if (event_vnode_svrattrl) free_attrlist(event_vnode_svrattrl);
	if (event_src_queue_svrattrl) free_attrlist(event_src_queue_svrattrl);
	if (event_aoe_svrattrl) free_attrlist(event_aoe_svrattrl);
	if (event_argv_svrattrl) free_attrlist(event_argv_svrattrl);
	if (event_jobs_svrattrl) free_attrlist(event_jobs_svrattrl);

	if ((fp != NULL) && (fp != stdin))
		fclose(fp);

	if (in_data != NULL) {
		free(in_data);
	}

	return (rc);
}

/**
 *
 * @brief
 *
 * 		This is like populate_svrattrl_from_file() but data is focused
 * 		on pbs.server() type of data.
 *		Takes data from input file or stdin of the form:
 *		<attribute_name>=<attribute value>
 *		<attribute_name>[<resource_name>]=<resource value>
 *		and populate the given various lists with the value obtained.
 *
 * @param[out]	input_file	-	if NULL, will get data from stdin.
 * @param[out]	default_svrattrl	-	the "catch all" list
 * @param[out]	server_svrattrl	-	gets <attribute_name>=SERVER_OBJECT data
 * @param[out]	server_jobs_svrattrl	-	gets <attribute_name>=SERVER_JOB_OBJECT data
 * 			              					Caution: stored in sorted order.
 * @param[out]	server_jobs_ids_svrattrl	-	gets the list of job ids obtained
 * @param[out]	server_queues_svrattrl	-	gets <attribute_name>=SERVER_QUEUE_OBJECT data
 * 			                				Caution: stored in sorted order.
 * @param[out]	server_queues_names_svrattrl	-	gets list of queue names obtained
 * @param[out]	server_resvs_svrattrl	-	gets <attribute_name>=SERVER_RESV_OBJECT data
 * 			               					Caution: stored in sorted order.
 * @param[out]	server_resvs_resvids_svrattrl	-	gets list of reservation ids obtained
 * @param[out]	server_vnodes_svrattrl	-	gets <attribute_name>=SERVER_VNODE_OBJECT data
 * 			                				Caution: stored in sorted order.
 * @param[out]	server_vnodes_names_svrattrl	-	gets list of vnode names obtained.
 *
 * @return	int
 * @retval	0	: success
 * @retval	-1	: failure, and free_attrlist() is used to free the memory
 *					associated with each non-NULL list parameter.
 */
int
pbs_python_populate_server_svrattrl_from_file(char *input_file,
	pbs_list_head *default_svrattrl,
	pbs_list_head *server_svrattrl,
	pbs_list_head *server_jobs_svrattrl,
	pbs_list_head *server_jobs_ids_svrattrl,
	pbs_list_head *server_queues_svrattrl,
	pbs_list_head *server_queues_names_svrattrl,
	pbs_list_head *server_resvs_svrattrl,
	pbs_list_head *server_resvs_resvids_svrattrl,
	pbs_list_head *server_vnodes_svrattrl,
	pbs_list_head *server_vnodes_names_svrattrl)
{

	char *attr_name;
	char *name_str;
	char name_str_buf[STRBUF+1] = {'\0'};
	char *resc_str;
	char *val_str;
	char *obj_name;
	char *obj_name2;
	int  rc = -1;
	int  rc2 = -1;
	char *pc, *pc1, *pc2, *pc3, *pc4;
	char *in_data = NULL;
	char *tmp_data = NULL;
	long int curpos;
	long int endpos;
	size_t   in_data_sz;
	char *data_value;
	size_t ll;
	FILE *fp = NULL;
	char *p, *p2;
	int   jobs_obj_len = strlen(SERVER_JOB_OBJECT);
	int   queue_obj_len = strlen(SERVER_QUEUE_OBJECT);
	int   resv_obj_len = strlen(SERVER_RESV_OBJECT);
	int   vnode_obj_len = strlen(SERVER_VNODE_OBJECT);

	if ((default_svrattrl == NULL) ||
		(server_svrattrl == NULL) ||
		(server_jobs_svrattrl == NULL) ||
		(server_jobs_ids_svrattrl == NULL) ||
		(server_queues_svrattrl == NULL) ||
		(server_queues_names_svrattrl == NULL) ||
		(server_vnodes_svrattrl  == NULL) ||
		(server_vnodes_names_svrattrl  == NULL) ||
		(server_resvs_svrattrl  == NULL) ||
		(server_resvs_resvids_svrattrl  == NULL)) {
		log_err(errno, __func__, "Bad input parameter!");
		rc = -1;
		goto populate_server_svrattrl_fail;
	}

	if ((input_file != NULL) && (*input_file != '\0')) {
		fp = fopen(input_file, "r");

		if (fp == NULL) {
			snprintf(log_buffer, sizeof(log_buffer),
				"failed to open input file %s", input_file);
			log_err(errno, __func__, log_buffer);
			rc = -1;
			goto populate_server_svrattrl_fail;
		}
	} else {
		fp = stdin;
	}

	if (default_svrattrl) {
		free_attrlist(default_svrattrl);
		CLEAR_HEAD((*default_svrattrl));
	}
	if (server_svrattrl) {
		free_attrlist(server_svrattrl);
		CLEAR_HEAD((*server_svrattrl));
	}
	if (server_jobs_svrattrl) {
		free_attrlist(server_jobs_svrattrl);
		CLEAR_HEAD((*server_jobs_svrattrl));
	}
	if (server_jobs_ids_svrattrl) {
		free_attrlist(server_jobs_ids_svrattrl);
		CLEAR_HEAD((*server_jobs_ids_svrattrl));
	}
	if (server_queues_svrattrl) {
		free_attrlist(server_queues_svrattrl);
		CLEAR_HEAD((*server_queues_svrattrl));
	}
	if (server_queues_names_svrattrl) {
		free_attrlist(server_queues_names_svrattrl);
		CLEAR_HEAD((*server_queues_names_svrattrl));
	}
	if (server_vnodes_svrattrl) {
		free_attrlist(server_vnodes_svrattrl);
		CLEAR_HEAD((*server_vnodes_svrattrl));
	}
	if (server_vnodes_names_svrattrl) {
		free_attrlist(server_vnodes_names_svrattrl);
		CLEAR_HEAD((*server_vnodes_names_svrattrl));
	}
	if (server_resvs_svrattrl) {
		free_attrlist(server_resvs_svrattrl);
		CLEAR_HEAD((*server_resvs_svrattrl));
	}
	if (server_resvs_resvids_svrattrl) {
		free_attrlist(server_resvs_resvids_svrattrl);
		CLEAR_HEAD((*server_resvs_resvids_svrattrl));
	}

	in_data_sz = STRBUF;
	in_data = (char *)malloc(in_data_sz);
	if (in_data == NULL) {
		log_err(errno, __func__, "malloc failed");
		rc = -1;
		goto populate_server_svrattrl_fail;
	}

	if (fseek(fp, 0, SEEK_END) != 0) {
		log_err(errno, __func__, "fseek to end failed");
		rc = 1;
		goto populate_server_svrattrl_fail;
	}
	endpos = ftell(fp);
	if (fseek(fp, 0, SEEK_SET) != 0) {
		log_err(errno, __func__, "fseek to beginning failed");
		rc = 1;
		goto populate_server_svrattrl_fail;
	}
	curpos = ftell(fp);
	while (fgets(in_data, in_data_sz, fp) != NULL) {

		ll = strlen(in_data);
#ifdef WIN32
		/* The file is being read in O_BINARY mode (see _fmode setting) */
		/* so on Windows, there's a carriage return (\r) line feed (\n), */
		/* then the linefeed needs to get processed out */
		if (ll >= 2) {
			if (in_data[ll-2] == '\r') {
				/* remove newline */
				in_data[ll-2] = '\0';
			}
		}
#endif
		if (in_data[ll-1] == '\n') {
			/* remove newline */
			in_data[ll-1] = '\0';
		} else if (ftell(fp) != endpos) { /* continued on next line */
			in_data_sz = 2*in_data_sz;
			tmp_data = (char *)realloc(in_data, in_data_sz);
			if (tmp_data == NULL) {
				log_err(errno, __func__, "realloc failed");
				rc = -1;
				goto populate_server_svrattrl_fail;
			}
			in_data = tmp_data;
			if (fseek(fp, curpos, SEEK_SET) != 0) {
				log_err(errno, __func__, "failed to fseek");
				rc = -1;
				goto populate_server_svrattrl_fail;
			}
			continue;
		}
		curpos = ftell(fp);
		data_value = NULL;
		if ((p=strchr(in_data, '=')) != NULL) {
			int i;
			*p = '\0';
			p++;
			/* Given '<obj_name>=<data_value>' line, */
			/* strip off leading spaces from <data_value> */
			while (isspace(*p))
				p++;
			data_value = p;
			/* and strip off trailing spaces from <data_value> */
			i = strlen(p);
			while (--i > 0) {	/* strip trailing blanks */
				if (!isspace((int)*(p+i)))
					break;
				*(p+i) = '\0';
			}

		}
		obj_name = in_data;

		pc = strrchr(in_data, '.');
		if (pc) {
			*pc = '\0';
			pc++;
		} else {
			pc = in_data;
		}
		name_str = pc;

		pc1 = strchr(pc, '[');
		pc2 = strchr(pc, ']');
		resc_str = NULL;
		if (pc1 && pc2 && (pc2 > pc1)) {
			*pc1 = '\0';
			pc1++;
			resc_str = pc1;
			*pc2 = '\0';
			pc2++;

			/* now let's if there's anything quoted inside */
			pc3 = strchr(pc1, '"');
			if (pc3 != NULL)
				pc4 = strchr(pc3+1, '"');
			else
				pc4 = NULL;

			if (pc3 && pc4 && (pc4 > pc3)) {
				pc3++;
				*pc4 = '\0';
				resc_str = pc3;
			}
		}

		val_str = NULL;
		if (data_value) {
			val_str = data_value;

			if (strcmp(obj_name, SERVER_OBJECT) == 0) {
				if (server_svrattrl) {
					rc = add_to_svrattrl_list(server_svrattrl, name_str, resc_str, val_str, 0, NULL);
				}
				rc2 = 0;
			} else if( server_jobs_svrattrl && \
			(strncmp(obj_name, SERVER_JOB_OBJECT,
				jobs_obj_len) == 0)) {
				obj_name2 = obj_name+jobs_obj_len;

				/* pbs.server().job(<jobid>)\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.server().job(<jobid>)
				 *       obj_name2 = (<jobid>
				 *	  name_str = <attribute name>
				 *
				 */

				/* import here to look for the first '(' (using strrchr)
				 * and the last')' (using strrchr)
				 * as we can have:
				 *		pbs.server().job("23.ricardo").<attr>=<val>
				 * and "23.ricardo" is a valid job id.
				 */
				if (((pc1=strchr(obj_name2, '(')) != NULL) &&
					((pc2=strchr(obj_name2, ')')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <jobid> part */

					*pc2 = '.'; /* pbs.server().job(<jobid>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <jobid>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <jobid>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a job id!", obj_name);
					log_err(-1, __func__, log_buffer);
					continue;
				}
				rc = add_to_svrattrl_list_sorted(server_jobs_svrattrl,
					name_str, resc_str, val_str, 0, NULL);

				if ((p2=strrchr(name_str, '.')) != NULL)
					*p2 = '\0'; /* name_str=<jobid> */

				if (!find_svrattrl_list_entry(server_jobs_ids_svrattrl,
					name_str, NULL))
					rc2 = add_to_svrattrl_list(server_jobs_ids_svrattrl, name_str, NULL, "", 0, NULL);

				if (p2 != NULL)
					*p2 = '.'; /* name_str=<jobid>.<attr> */

			} else if( server_vnodes_svrattrl && \
			(strncmp(obj_name, SERVER_VNODE_OBJECT,
				vnode_obj_len) == 0)) {

				obj_name2 = obj_name+vnode_obj_len;
				/* pbs.server().vnode(<vnode_name>)\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.server().vnode(<vnode_name>)
				 *       obj_name = (<vnode_name>)
				 *	  name_str = <attribute name>
				 */

				/* import here to look for the leftmost '(' (using strchr)
				 * and the rightmost ')' (using strrchr)
				 * as we can have:
				 *		pbs.server().vnode("altix[5]").<attr>=<val>
				 * and "altix[5]" is a valid vnode id.
				 */
				if (((pc1=strchr(obj_name2, '(')) != NULL) &&
					((pc2=strrchr(obj_name2, ')')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <vnode_name> part */

					*pc2 = '.'; /* pbs.server().vnode(<vnode_name>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <vnode_name>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <vnode_name>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a vnode name!", obj_name);
					log_err(-1, __func__, log_buffer);
					continue;
				}
				rc = add_to_svrattrl_list_sorted(server_vnodes_svrattrl,
					name_str, resc_str,
					return_internal_value(attr_name, val_str), 0, NULL);
				if ((p2=strrchr(name_str, '.')) != NULL)
					*p2 = '\0'; /* name_str=<vname> */

				if (!find_svrattrl_list_entry(server_vnodes_names_svrattrl,
					name_str, NULL))
					rc2 = add_to_svrattrl_list(server_vnodes_names_svrattrl, name_str, NULL, "", 0, NULL);

				if (p2 != NULL)
					*p2 = '.'; /* name_str=<vname>.<attr> */

			} else if( server_queues_svrattrl && \
			(strncmp(obj_name, SERVER_QUEUE_OBJECT,
				queue_obj_len) == 0)) {

				obj_name2 = obj_name+queue_obj_len;
				/* pbs.server().queue(<qname>)\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.server().queue(<qname>)
				 * where obj_name = pbs.server().queue(<qname>)
				 *	  name_str = <attribute name>
				 */

				/* import here to look for the leftmost '(' (using strchr)
				 * and the rightmost ')' (using strrchr)
				 * as we can have:
				 *		pbs.server().queue("workq").<attr>=<val>
				 * and "workq" is a valid queue id.
				 */
				if (((pc1=strrchr(obj_name2, '(')) != NULL) &&
					((pc2=strrchr(obj_name2, ')')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <qname> part */

					*pc2 = '.'; /* pbs.server().queue(<qname>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <qname>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <qname>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a queue name!", obj_name);
					log_err(-1, __func__, log_buffer);
					continue;
				}
				rc = add_to_svrattrl_list_sorted(server_queues_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
				if ((p2=strrchr(name_str, '.')) != NULL)
					*p2 = '\0'; /* name_str=<qname> */

				if (!find_svrattrl_list_entry(server_queues_names_svrattrl,
					name_str, NULL))
					rc2 = add_to_svrattrl_list(server_queues_names_svrattrl, name_str, NULL, "", 0, NULL);

				if (p2 != NULL)
					*p2 = '.'; /* name_str=<qname>.<attr> */
			} else if( server_resvs_svrattrl && \
			(strncmp(obj_name, SERVER_RESV_OBJECT,
				resv_obj_len) == 0)) {

				obj_name2 = obj_name+resv_obj_len;
				/* pbs.server().resv(<resv_name>)\0<attribute name>\0<resource name>\0<value>
				 * where obj_name = pbs.server().resv(<resv_name>)
				 * 	 obj_name = (<resv_name>)
				 *	  name_str = <attribute name>
				 */

				/* import here to look for the leftmost '(' (using strchr)
				 * and the rightmost ')' (using strrchr)
				 * as we can have:
				 *		pbs.server().resv("R5").<attr>=<val>
				 * and "R5" is a valid resv id.
				 */
				if (((pc1=strrchr(obj_name2, '(')) != NULL) &&
					((pc2=strrchr(obj_name2, ')')) != NULL) &&
					(pc2 > pc1)) {
					pc1++; /* <resv_name> part */

					*pc2 = '.'; /* pbs.server().resv(<resv_name>. */
					pc2++;

					/* now let's if there's anything quoted inside */
					pc3 = strchr(pc1, '"');
					if (pc3 != NULL)
						pc4 = strchr(pc3+1, '"');
					else
						pc4 = NULL;

					if (pc3 && pc4 && (pc4 > pc3)) {
						pc3++;
						*pc4 = '.';
						pc4++;
						/* we're saving 'name_str' in a separate array (name_str_buf), */
						/* as strcpy() does something odd under rhel6/centos if the */
						/* destination (pc4)  and the source (name_str) are in the same */
						/* memory area, even though non-overlapping. */
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc4, name_str_buf); /* <resv_name>.<attr name> */
						name_str = pc3;
					} else {
						strncpy(name_str_buf, name_str, sizeof(name_str_buf)-1);
						strcpy(pc2, name_str_buf); /* <resv_name>.<attr name> */
						name_str = pc1;
					}
					attr_name=strrchr(name_str, '.');
					if (attr_name == NULL)
						attr_name = name_str;
					else
						attr_name++;


				} else {
					snprintf(log_buffer, sizeof(log_buffer),
						"object '%s' does not have a resv name!", obj_name);
					log_err(-1, __func__, log_buffer);
					continue;
				}
				rc = add_to_svrattrl_list_sorted(server_resvs_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
				if ((p2=strrchr(name_str, '.')) != NULL)
					*p2 = '\0'; /* name_str=<qname> */

				if (!find_svrattrl_list_entry(server_resvs_resvids_svrattrl, name_str, NULL))
					rc2 = add_to_svrattrl_list(server_resvs_resvids_svrattrl, name_str, NULL, "", 0, NULL);

				if (p2 != NULL)
					*p2 = '.'; /* name_str=<qname>.<attr> */
			} else {
				rc = add_to_svrattrl_list(default_svrattrl,
					name_str, resc_str, val_str, 0, NULL);
				rc2 = 0;
			}

			if (rc == -1) {
				snprintf(log_buffer, sizeof(log_buffer),
					"failed to add_to_svrattrl_list(%s,%s,%s)",
					name_str, resc_str, (val_str?val_str:""));
				log_err(errno, __func__, log_buffer);
				goto populate_server_svrattrl_fail;
			}

			if (rc2 == -1) {
				snprintf(log_buffer, sizeof(log_buffer),
					"failed to add %s to list of names",
					name_str);
				log_err(errno, __func__, log_buffer);
				goto populate_server_svrattrl_fail;
			}
		}
	}

	if (fp != stdin)
		fclose(fp);

	if (in_data != NULL) {
		free(in_data);
	}
	return (0);

populate_server_svrattrl_fail:

	if (default_svrattrl) {
		free_attrlist(default_svrattrl);
		CLEAR_HEAD((*default_svrattrl));
	}
	if (server_svrattrl) {
		free_attrlist(server_svrattrl);
		CLEAR_HEAD((*server_svrattrl));
	}
	if (server_jobs_svrattrl) {
		free_attrlist(server_jobs_svrattrl);
		CLEAR_HEAD((*server_jobs_svrattrl));
	}
	if (server_jobs_ids_svrattrl) {
		free_attrlist(server_jobs_ids_svrattrl);
		CLEAR_HEAD((*server_jobs_ids_svrattrl));
	}
	if (server_queues_svrattrl) {
		free_attrlist(server_queues_svrattrl);
		CLEAR_HEAD((*server_queues_svrattrl));
	}
	if (server_queues_names_svrattrl) {
		free_attrlist(server_queues_names_svrattrl);
		CLEAR_HEAD((*server_queues_names_svrattrl));
	}
	if (server_resvs_svrattrl) {
		free_attrlist(server_resvs_svrattrl);
		CLEAR_HEAD((*server_resvs_svrattrl));
	}
	if (server_resvs_resvids_svrattrl) {
		free_attrlist(server_resvs_resvids_svrattrl);
		CLEAR_HEAD((*server_resvs_resvids_svrattrl));
	}
	if (server_vnodes_svrattrl) {
		free_attrlist(server_vnodes_svrattrl);
		CLEAR_HEAD((*server_vnodes_svrattrl));
	}
	if (server_vnodes_names_svrattrl) {
		free_attrlist(server_vnodes_names_svrattrl);
		CLEAR_HEAD((*server_vnodes_names_svrattrl));
	}

	if ((fp != NULL) && (fp != stdin))
		fclose(fp);

	if (in_data != NULL) {
		free(in_data);
	}

	return (rc);
}

/**
 * @brief
 *		Prints out the file on opened stream 'fp', the attribute names or
 *		resources and their values as in:
 *			<attribute_name>=<attribute_value>
 *			<attribute_name>[<resource_name>]=<resource_value>
 *			<vnode_name>.<attribute_name>=<attribute value>
 *			<vnode_name>.<attribute_name>[<resource_name>]=<attribute value>
 * @note
 *		Only prints out values that were set in a hook script.
 *
 * @param[in]	fp	-	the stream pointer of the file to write output into
 * @param[in]	head_str	-	some string to print out the beginning.
 * @param[in]	phead	-	pointer to the head of the list containing data.
 *
 * @return	none
 */
void
fprint_svrattrl_list(FILE *fp, char *head_str, pbs_list_head *phead)
{
	svrattrl *plist = NULL;
	char	*p, *p0;

	if ((fp == NULL) || (head_str == NULL) || (phead == NULL)) {
		log_err(errno, __func__, "Bad input parameter!");
		return;
	}

	plist = (svrattrl *)GET_NEXT(*phead);
	log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_HOOK, LOG_INFO, __func__, head_str);
	while (plist) {
		if (plist->al_flags & ATR_VFLAG_HOOK) {

			p=strrchr(plist->al_name, '.');
			p0 = p;
			if (p != NULL) {
				*p = '\0';
				p++; /* this is the actual attribute name */
			}

			if (plist->al_resc != NULL) {
				if (p != NULL)
					fprintf(fp, "%s[\"%s\"].%s[%s]=%s\n", head_str,
						plist->al_name, p,
						plist->al_resc,
						return_external_value(p, plist->al_value));
				else
					fprintf(fp, "%s.%s[%s]=%s\n", head_str,
						plist->al_name, plist->al_resc,
						return_external_value(plist->al_name,
						plist->al_value));
			} else {
				if (p != NULL) {
					fprintf(fp, "%s[\"%s\"].%s=%s\n", head_str,
						plist->al_name, p,
						return_external_value(p, plist->al_value));
				} else {
					if (strcmp(plist->al_name, ATTR_v) == 0) {
						fprintf(fp, "%s.%s=\"\"\"%s\"\"\"\n",
							head_str,
							plist->al_name,
							return_external_value(
							plist->al_name,
							plist->al_value));
					} else {
						fprintf(fp, "%s.%s=%s\n", head_str,
							plist->al_name,
							return_external_value(
							plist->al_name,
							plist->al_value));
					}
				}
			}
			if (p0 != NULL)
				*p0 = '.';

		}

		plist = (svrattrl *)GET_NEXT(plist->al_link);
	}
}

/**
 *
 * @brief
 *		Prints out to the file opened in stream 'fp', the contents of the
 *		string array 'str_array'.
 *
 * @param[in]	fp	-	the stream pointer of the file to write output into
 * @param[in]	head_str	-	some string to print out the beginning.
 * @param[in]	str_array	-	the array whose contents are being printed.
 *
 * @return	none
 */
void
fprint_str_array(FILE *fp, char *head_str, void **str_array)
{
	int i;

	for (i = 0; str_array[i]; i++)
		fprintf(fp, "%s[%d]=%s\n", head_str, i, (char *)str_array[i]);
}


/**
 * @brief
 * 		Given an 'argv_list', return a malloc-ed
 * 		string, containing the argv_list->al_values separated
 *		by spaces.
 * @note
 *		Need to free() returned value.
 *
 * @param[in]	argv_list	-	an argv list.
 *
 * @return	char *
 * @retval	<string>	-	pointer to a malloced area holding
 *				  			the values of 'argv_list'.
 * @retval	NULL	: error
 *
 */
static char	*
argv_list_to_str(pbs_list_head *argv_list)
{
	int	i, len;
	char	*ret_string = NULL;
	svrattrl *plist = NULL;

	if (argv_list == NULL)
		return (NULL);

	len=0;
	i=0;

	/* calculate the list size */
	len = 0;
	plist = (svrattrl *)GET_NEXT(*argv_list);
	while (plist) {
		if (plist->al_value == NULL) {
			return (NULL);
		}
		len += strlen(plist->al_value);
		len++;	/* for ' ' (space) */
		i++;
		plist = (svrattrl *)GET_NEXT(plist->al_link);
	}

	len++;	/* for trailing '\0' */

	if (len > 1) { /* not an empty list */
		ret_string = (char *)malloc(len);

		if (ret_string == NULL)
			return (NULL);
		i=0;
		plist = (svrattrl *)GET_NEXT(*argv_list);
		while (plist) {
			if (i == 0) {
				strcpy(ret_string, plist->al_value);
			} else {
				strcat(ret_string, " ");
				strcat(ret_string, plist->al_value);
			}
			i++;
			plist = (svrattrl *)GET_NEXT(plist->al_link);
		}
	}
	return (ret_string);

}

/**
 *
 * @brief
 * 		pbs_python is a wrapper to the Python program shipped with
 *      PBS. It will construct a Python search path for modules
 *      (i.e. sys.path/PYTHONPATH) that points to directories in
 *      $PBS_EXEC/python, and then will call the Python interpreter taking
 * 	  	as input arguments from the commandline if they exist; otherwise,
 *	  	the name of the script file to execute as taken from STDIN.
 */

int
main(int argc, char *argv[], char *envp[])
{
	char python_prefix[MAXPATHLEN+1];
	char python_path[MAXPATHLEN+1] = {'\0'};
#ifndef WIN32
	char dirname[MAXPATHLEN+1];
	int  env_len = 0;
	int  found_pyhome;
#endif
	char python_envbuf[MAXBUF+1];
#ifdef WIN32
	char python_cmdline[MAXBUF+1];
#endif
	char **lenvp = NULL;
	int  	i, rc;

	/* python externs */
	extern void pbs_python_svr_initialize_interpreter_data(
		struct python_interpreter_data *interp_data);
	extern void pbs_python_svr_destroy_interpreter_data(
		struct python_interpreter_data *interp_data);
	
	if(set_msgdaemonname("pbs_python")) {
		fprintf(stderr, "Out of memory\n");
		return 1;
	}

#ifdef WIN32
	/* The following needed so that buffered writes (e.g. fprintf) */
	/* won't end up getting ^M */
	_set_fmode(_O_BINARY);

	winsock_init();
#endif

	/*the real deal or output pbs_version and exit?*/
	execution_mode(argc, argv);

	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "Failed to load pbs.conf!\n");
		return 1;
	}

	/* by default, server_name is what is set in /etc/pbs.conf */
	(void)strcpy(server_name, pbs_conf.pbs_server_name);

	/* determine the actual server name */
	pbs_server_name = pbs_default();
	if ((!pbs_server_name) || (*pbs_server_name == '\0')) {
		log_err(-1, "pbs_python", "Unable to get server name");
		return (-1);
	}

	/* determine the server host name */
	if (get_fullhostname(pbs_server_name, server_host, PBS_MAXSERVERNAME) != 0) {
		log_err(-1, "pbs_python", "Unable to get server host name");
		return (-1);
	}

	pbs_server_id = NULL;

	/* initialize the pointers in the resource_def array */

	for (i = 0; i < (svr_resc_size - 1); ++i)
		svr_resc_def[i].rs_next = &svr_resc_def[i+1];
	/* last entry is left with null pointer */

	if ((argv[1] == NULL) || (strcmp(argv[1], HOOK_MODE) != 0)) {
#ifdef WIN32
		/* If this is 64-bit Windows, use 64-bit Python */
		if (TRUE == is_64bit_Windows()) {
			snprintf(python_prefix, MAXPATHLEN, "%s/python_x64",
				pbs_conf.pbs_exec_path);
			/* 64-bit Windows Python install doesn't have bin folder */
			snprintf(python_path, MAXPATHLEN, "%s/python.exe",
				python_prefix);
		}
		else {
			snprintf(python_prefix, MAXPATHLEN, "%s/python",
				pbs_conf.pbs_exec_path);
			snprintf(python_path, MAXPATHLEN, "%s/bin/python.exe",
				python_prefix);
		}
		forward2back_slash(python_path);

		/* Windows: Set environments PYTHONHOME modify PATH to be seen by */
		/* CreateProcess() of python script.                              */
		forward2back_slash(python_prefix);
		SetEnvironmentVariable(PYHOME, python_prefix);
		snprintf(python_envbuf, MAXBUF, "%s;%s\\bin", getenv("PATH"),
			python_prefix);
		SetEnvironmentVariable("PATH", python_envbuf);

		/* Just pass on the command line arguments onto Python */

		snprintf(python_cmdline, MAXBUF, "%s", python_path);
		for (i=1; i < argc; i++) {
			snprintf(python_cmdline, MAXBUF, "%s \"%s\"",
				python_cmdline, argv[i]);
		}
		rc = wsystem(python_cmdline, INVALID_HANDLE_VALUE);
#else
		char in_data[MAXBUF+1];
		char *largv[3];
		int ll;
		char *pc, *pc2;

#ifdef SYSTEM_PYTHON_PATH
		snprintf(python_path, MAXPATHLEN, "%s", SYSTEM_PYTHON_PATH);
		pc = strdup(SYSTEM_PYTHON_PATH);
		if(pc == NULL) {
			fprintf(stderr, "Out of memory\n");
			return 1;
		}
		pc2 = strstr(pc,"bin/python");
		if(pc2 == NULL) {
			fprintf(stderr, "Python executable not found!\n");
			return 1;
		}
		*pc2 = '\0';
		if(strlen(pc) > 0) {
			snprintf(python_prefix, MAXPATHLEN, "%s", pc);
			free(pc);
		} else {
			fprintf(stderr, "Python home not found!\n");
			return 1;
		}
		snprintf(python_envbuf, MAXBUF, "%s=%s", PYHOME, python_prefix);
#else
		snprintf(python_prefix, MAXPATHLEN, "%s/python",
			pbs_conf.pbs_exec_path);
		snprintf(python_path, MAXPATHLEN, "%s/bin/python",
			python_prefix);
		snprintf(python_envbuf, MAXBUF, "%s=%s", PYHOME, python_prefix);
#endif

		/* Linux/Unix: Create a local environment block (i.e. lenvp)    */
		/* containing PYTHONHOME setting, and give to execve() when it	*/
		/* executes the python script.					*/
		lenvp = (char **) envp;
		do
			env_len += 1;
		while (*lenvp++);

		lenvp = (char **) malloc((env_len + 1) * sizeof(char *));
		if (lenvp == NULL) {
			errno = ENOMEM;
			return 1;
		}

		/* Copy envp to lenvp */
		found_pyhome = 0;
		i = 0;
		for (i=0; envp[i] != NULL; i++) {
			if (strncmp(envp[i], PYHOME_EQUAL,
				sizeof(PYHOME_EQUAL)-1) == 0) {
				printf("[%d] found py_home %s resetting to %s\n",
					i, envp[i], python_envbuf);
				lenvp[i] =  python_envbuf;
				found_pyhome = 1;
			} else {
				lenvp[i] = envp[i];
			}
		}

		if (!found_pyhome) {
			lenvp[i] = python_envbuf;
			i++;
		}
		lenvp[i] = (char *)0;


		if (argc == 1) {
			/* If no command line options, just check stdin for input */
			/* name, which is what mom does. Also, under              */
			/* sandbox=private, mom passes                            */
			/* "cd <homedir>;<input script>" so we'll need to extract */
			/* the script name this way.                              */

			if (fgets(in_data, sizeof(in_data), stdin) == NULL) {
				fprintf(stderr, "No python script file found!\n");
				return 1;
			}
			ll = strlen(in_data);

			if (in_data[ll-1] == '\n')
				/* remove newline */
				in_data[ll-1] = '\0';

			pc = strchr(in_data, ';');
			if (pc) {
				pc++;
				while (isspace(*pc))
					pc++;
				largv[1] = pc;

				/* looking for the "cd <homedir>" part */
				if ((pc=strstr(in_data, "cd"))) { /* found a chdir */
					pc2 = in_data+2;
					while (isspace(*pc2))
						pc2++;
					strncpy(dirname, pc2, MAXPATHLEN);
					if ((pc=strrchr(dirname, ';')))
						*pc = '\0';
					if (chdir(dirname) == -1) {
						fprintf(stderr,
							"Failed to chdir to %s (errno %d)\n",
							dirname, errno);
						return 1;
					}
				}
			} else {
				pc = in_data;
				while (isspace(*pc))
					pc++;
				largv[1] = pc;
			}

			if (largv[1][0] == '\0') {

				fprintf(stderr, "Failed to obtain python script\n");
				return 1;
			}

			largv[0] = argv[0];
			largv[2] = (char *)0;

			rc = execve(python_path, largv, lenvp);
		} else {
			rc = execve(python_path, argv, lenvp);
		}
#endif
	} else { /* hook mode */

		char 	**argv2 = NULL;
		int	argc2;
		int	argv_len = 0;
		char    hook_script[MAXPATHLEN+1];
		char	the_input[MAXPATHLEN+1];
		char	the_output[MAXPATHLEN+1];
		char	the_server_output[MAXPATHLEN+1];
		char	the_data[MAXPATHLEN+1];
		char    path_log[MAXPATHLEN+1];
		char    logname[MAXPATHLEN+1];

		char	hook_name[MAXBUF+1];
		char	req_user[PBS_MAXUSER+1];
		char	req_host[PBS_MAXHOSTNAME+1];
		char	hookstr_type[MAXBUF+1];
		char	hookstr_event[MAXBUF+1];
		int	hook_alarm = 0;
		int	c, j;
		int	errflg=0;
		unsigned int hook_event = 0;
		struct python_script	*py_script = NULL;
		pbs_list_head default_list, event, event_job, event_job_o,
		event_resv, event_vnode, event_src_queue,
		event_aoe, event_argv, event_jobs,
		server, server_jobs, server_jobs_ids,
		server_queues, server_queues_names,
		server_resvs, server_resvs_resvids,
		server_vnodes, server_vnodes_names;
		svrattrl *svrattrl_e;
		FILE	 *fp_out = NULL;
		FILE	 *fp_server_out = NULL;
		svrattrl *plist = NULL;
		struct rq_queuejob rqj;
		struct rq_manage  rqm;
		struct rq_move rqmv;
		struct rq_runjob rqrun;
		char	*rej_msg = NULL;
		char	*rerunjob_str = NULL;
		char	*deletejob_str = NULL;
		char	*new_exec_time_str = NULL;
		char	*new_hold_types_str = NULL;
		char	*new_project_str = NULL;
		hook_input_param_t req_params;
		hook_output_param_t req_params_out;
		char	*progname = NULL;
		char	*progname_orig = NULL;
		char	*env_str = NULL;
		char	*env_str_orig = NULL;
		char	*argv_str_orig = NULL;
		char	*argv_str = NULL;
		int	print_progname = 0;
		int	print_argv= 0;
		int	print_env= 0;

		the_input[0] = '\0';
		the_output[0] = '\0';
		the_server_output[0] = '\0';
		the_data[0] = '\0';
		hook_name[0] = '\0';
		req_user[0] = '\0';
		req_host[0] = '\0';
		hookstr_type[0] = '\0';
		hookstr_event[0] = '\0';
		hook_script[0] = '\0';
		logname[0] = '\0';
		strcpy(path_log, ".");

		if (*(argv+2) == NULL) {
			fprintf(stderr, "%s --hook -i <input_file> [-s <data_file>] [-o <output_file>] [-L <path_log>] [-l <logname>] [-r <resourcedef>] [-e <log_event_mask>] [<python_script>]\n", argv[0]);
			exit(2);
		}
		argv2 = (char **) argv;
		do
			argv_len += 1;
		while (*argv2++);

		argv2 = (char **) malloc((argv_len + 1) * sizeof(char *));
		if (argv2 == NULL) {
			return 1;
		}

		argc2 = 0;
		for (i=0, j=0; argv[i] != NULL; i++) {
			if (strncmp(argv[i], HOOK_MODE,
				sizeof(HOOK_MODE)-1) == 0)
				continue;
			argv2[j++] = argv[i];
			argc2++;
		}
		argv2[i] = (char *)0;

		pbs_python_set_use_static_data_value(0);
		while ((c = getopt(argc2, argv2, "i:o:l:L:e:r:s:")) != EOF) {

			switch (c) {
				case 'i':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -i value\n");
						errflg++;
					} else {
						strncpy(the_input, optarg,
							sizeof(the_input)-1);
					}
					break;
				case 'o':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -o value\n");
						errflg++;
					} else {
						strncpy(the_output, optarg,
							sizeof(the_output)-1);
					}
					break;
				case 's':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -s value\n");
						errflg++;
					} else {
						strncpy(the_data, optarg,
							sizeof(the_data)-1);
						pbs_python_set_use_static_data_value(1);
					}
					break;
				case 'L':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -L value\n");
						errflg++;
					} else {
						strncpy(path_log, optarg,
							sizeof(path_log)-1);
					}
					break;
				case 'l':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -l value\n");
						errflg++;
					} else {
						strncpy(logname, optarg,
							sizeof(logname)-1);
					}
					break;
				case 'e':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -e value\n");
						errflg++;
					} else {
						char *bad;

						*log_event_mask = strtol(optarg, &bad, 0);
						if ((*bad != '\0') && !isspace((int)*bad)) {
							fprintf(stderr,
								"pbs_python: bad -e value %s\n",
								optarg);
							errflg++;
						}
					}
					break;
				case 'r':
					while (isspace((int)*optarg)) optarg++;

					if (optarg[0] == '\0') {
						fprintf(stderr, "pbs_python: illegal -r value\n");
						errflg++;
					} else {
						path_rescdef = strdup(optarg);
						if (path_rescdef == NULL) {
							fprintf(stderr,
								"pbs_python: errno %d mallocing path_rescdef\n", errno);
							errflg++;
						}
					}
					break;
				default:
					errflg++;
			}
			if (errflg) {
				fprintf(stderr, "%s --hook -i <hook_input> [-s <data_file>] [-o <hook_output>] [-L <path_log>] [-l <logname>] [-r <resourcedef>] [-e <log_event_mask>] [<python_script>]\n", argv[0]);
				exit(2);
			}

		}

		if (the_input[0] == '\0') {
			fprintf(stderr, "%s: No -i <input_file> given\n",
				argv[0]);
			exit(2);
		}

		if (path_rescdef != NULL) {
			if (setup_resc(1) == -1) {
				fprintf(stderr, "setup_resc() of %s failed!",
					path_rescdef);
				exit(2);
			}
		}

		if ((optind < argc2) && (argv2[optind] != NULL)) {
			strncpy(hook_script, argv2[optind],
				sizeof(hook_script)-1);
		}
		if (log_open_main(logname, path_log, 1) != 0) {  /* use given name */
			fprintf(stderr, "pbs_python: Unable to open logfile\n");
			exit(1);
		}


		CLEAR_HEAD(default_list);
		CLEAR_HEAD(event);
		CLEAR_HEAD(event_job);
		CLEAR_HEAD(event_job_o);
		CLEAR_HEAD(event_resv);
		CLEAR_HEAD(event_vnode);
		CLEAR_HEAD(event_src_queue);
		CLEAR_HEAD(event_aoe);
		CLEAR_HEAD(event_argv);
		CLEAR_HEAD(event_jobs);

		rc = pbs_python_populate_svrattrl_from_file(the_input,
			&default_list,
			&event, &event_job, &event_job_o, &event_resv,
			&event_vnode, &event_src_queue, &event_aoe, &event_argv, &event_jobs);
		if (rc == -1) {
			fprintf(stderr, "%s: failed to populate svrattrl \n", argv[0]);
			exit(2);
		}
		if (the_data[0] != '\0') {
			CLEAR_HEAD(server);
			CLEAR_HEAD(server_jobs);
			CLEAR_HEAD(server_jobs_ids);
			CLEAR_HEAD(server_queues);
			CLEAR_HEAD(server_queues_names);
			CLEAR_HEAD(server_resvs);
			CLEAR_HEAD(server_resvs_resvids);
			CLEAR_HEAD(server_vnodes);
			CLEAR_HEAD(server_vnodes_names);
			pbs_python_unset_server_info();
			pbs_python_unset_server_jobs_info();
			pbs_python_unset_server_queues_info();
			pbs_python_unset_server_resvs_info();
			pbs_python_unset_server_vnodes_info();

			rc = pbs_python_populate_server_svrattrl_from_file(the_data,
				&default_list, &server,
				&server_jobs, &server_jobs_ids,
				&server_queues, &server_queues_names,
				&server_resvs, &server_resvs_resvids,
				&server_vnodes, &server_vnodes_names);
			if (rc == -1) {
				fprintf(stderr,
					"%s: failed to populate svrattrl \n",
					argv[0]);
				exit(2);
			}
			pbs_python_set_server_info(&server);
			pbs_python_set_server_jobs_info(&server_jobs,
				&server_jobs_ids);
			pbs_python_set_server_queues_info(&server_queues,
				&server_queues_names);
			pbs_python_set_server_resvs_info(&server_resvs,
				&server_resvs_resvids);
			pbs_python_set_server_vnodes_info(&server_vnodes,
				&server_vnodes_names);
		}

		plist = (svrattrl *)GET_NEXT(event);
		while (plist) {

			if (strcmp(plist->al_name, "type") == 0) {
				hook_event = \
				     hookstr_event_toint(plist->al_value);
				sprintf(hookstr_event, "%d", hook_event);
			} else if (strcmp(plist->al_name, "hook_name") == 0) {
				strcpy(hook_name, plist->al_value);
			} else if (strcmp(plist->al_name, "requestor") == 0) {
				strcpy(req_user, plist->al_value);
			} else if (strcmp(plist->al_name,
				"requestor_host") == 0) {
				strcpy(req_host, plist->al_value);
			} else if (strcmp(plist->al_name, "hook_type") == 0) {
				strcpy(hookstr_type, plist->al_value);
			} else if (strcmp(plist->al_name, "alarm") == 0) {
				hook_alarm = atoi(plist->al_value);
			} else if (strcmp(plist->al_name, "debug") == 0) {
				strncpy(the_server_output, plist->al_value,
					sizeof(the_server_output)-1);
				fp_server_out = fopen(the_server_output,
					"w");
				if (fp_server_out == NULL) {
					fprintf(stderr,
						"warning: open of server output %s failed!",
						the_server_output);
				} else {
					pbs_python_set_hook_debug_data_fp(fp_server_out);
				}
			} else if ((strcmp(plist->al_name, HOOKATT_USER) != 0) &&
				(strcmp(plist->al_name, HOOKATT_FREQ) != 0) &&
				(strcmp(plist->al_name, PY_EVENT_PARAM_PROGNAME) != 0) &&
				(strcmp(plist->al_name, PY_EVENT_PARAM_ARGLIST) != 0) &&
				(strcmp(plist->al_name, PY_EVENT_PARAM_ENV) != 0) &&
				(strcmp(plist->al_name, PY_EVENT_PARAM_PID) != 0) &&
				(strcmp(plist->al_name, HOOKATT_FAIL_ACTION) != 0)) {
				fprintf(stderr, "%s: unknown event attribute '%s'\n", argv[0], plist->al_name);
				exit(2);
			}

			plist = (svrattrl *)GET_NEXT(plist->al_link);
		}

		if (req_host[0] == '\0')
			gethostname(req_host, PBS_MAXHOSTNAME);

#ifdef WIN32
		forward2back_slash(logname);
#endif
		if ((logname[0] != '\0') && (!is_full_path(logname))) {
			char	curdir[MAXPATHLEN+1];
			char	full_logname[MAXPATHLEN+1];
			char	slash;
#ifdef WIN32
			slash = '\\';
#else
			slash = '/';
#endif
			/* save current working dir before any chdirs */
			if (getcwd(curdir, MAXPATHLEN) == NULL) {
				fprintf(stderr, "getcwd failed\n");
				exit(2);
			}
			snprintf(full_logname, sizeof(full_logname), "%s%c%s", curdir, slash, logname);
			strncpy(logname, full_logname, sizeof(logname)-1);
		}

		/* set python interp data */
		svr_interp_data.data_initialized = 0;
		svr_interp_data.init_interpreter_data =
			pbs_python_svr_initialize_interpreter_data;
		svr_interp_data.destroy_interpreter_data =
			pbs_python_svr_destroy_interpreter_data;

		svr_interp_data.daemon_name = strdup("pbs_python");

		if (svr_interp_data.daemon_name == NULL) { /* should not happen */
			fprintf(stderr, "strdup failed");
			exit(1);
		}

		(void)pbs_python_ext_alloc_python_script(hook_script,
			(struct python_script **) &py_script);

		pbs_python_ext_start_interpreter(&svr_interp_data);
		hook_input_param_init(&req_params);	
		switch (hook_event) {

			case HOOK_EVENT_QUEUEJOB:
				rqj.rq_jid[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqj.rq_jid,
						svrattrl_e->al_value);
				}
				rqj.rq_destin[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					ATTR_queue, NULL)) != NULL) {
					strcpy((char *)rqj.rq_destin,
						svrattrl_e->al_value);
				}
				if (copy_svrattrl_list(&event_job,
					&rqj.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}

				req_params.rq_job = (struct rq_quejob *)&rqj;
				req_params.vns_list = (pbs_list_head *)&event_vnode;
				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_MODIFYJOB:
				rqm.rq_objname[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqm.rq_objname,
						svrattrl_e->al_value);
				}
				if (copy_svrattrl_list(&event_job,
					&rqm.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}

				req_params.rq_manage = (struct rq_manage *)&rqm;
				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_MOVEJOB:
				rqmv.rq_jid[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqmv.rq_jid,
						svrattrl_e->al_value);
				}

				req_params.rq_move = (struct rq_move *)&rqmv;
				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_RUNJOB:
				rqrun.rq_jid[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqrun.rq_jid,
						svrattrl_e->al_value);
				}
				req_params.rq_run = (struct rq_runjob *)&rqrun;

				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_RESVSUB:
				rqj.rq_jid[0] = '\0';
				if ((svrattrl_e=find_svrattrl_list_entry(&event_resv,
					"resvid", NULL)) != NULL) {
					strcpy((char *)rqj.rq_jid,
						svrattrl_e->al_value);
				}
				if (copy_svrattrl_list(&event_resv,
					&rqj.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}
				req_params.rq_job = (struct rq_queuejob *)&rqj;
				req_params.vns_list = (pbs_list_head *)&event_vnode;
				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_EXECJOB_BEGIN:
			case HOOK_EVENT_EXECJOB_PROLOGUE:
			case HOOK_EVENT_EXECJOB_EPILOGUE:
			case HOOK_EVENT_EXECJOB_END:
			case HOOK_EVENT_EXECJOB_PRETERM:

				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqj.rq_jid,
						svrattrl_e->al_value);
				}
				rqj.rq_destin[0] = '\0';

				if (copy_svrattrl_list(&event_job,
					&rqj.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}
				req_params.rq_job = (struct rq_queuejob *)&rqj;
				req_params.vns_list = (pbs_list_head *)&event_vnode;

				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;

			case HOOK_EVENT_EXECJOB_LAUNCH:

				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqj.rq_jid,
						svrattrl_e->al_value);
				}
				rqj.rq_destin[0] = '\0';

				if (copy_svrattrl_list(&event_job,
					&rqj.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}

				req_params.rq_job = (struct rq_queuejob *)&rqj;
				req_params.vns_list = (pbs_list_head *)&event_vnode;

				if ((svrattrl_e=find_svrattrl_list_entry(&event,
					PY_EVENT_PARAM_PROGNAME, NULL)) != NULL) {
					req_params.progname = svrattrl_e->al_value;
					progname_orig = svrattrl_e->al_value;
				} else {
					progname_orig = "";
				}

				req_params.argv_list = (pbs_list_head *)&event_argv;

				argv_str_orig = argv_list_to_str((pbs_list_head *)&event_argv);
				if ((svrattrl_e=find_svrattrl_list_entry(&event,
					PY_EVENT_PARAM_ENV, NULL)) != NULL) {
					req_params.env = svrattrl_e->al_value;
					env_str_orig = svrattrl_e->al_value;
				} else {
					env_str_orig = "";
				}

				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_EXECJOB_ATTACH:

				if ((svrattrl_e=find_svrattrl_list_entry(&event_job,
					"id", NULL)) != NULL) {
					strcpy((char *)rqj.rq_jid,
						svrattrl_e->al_value);
				}
				rqj.rq_destin[0] = '\0';

				if (copy_svrattrl_list(&event_job,
					&rqj.rq_attr) == -1) {
					log_err(errno, "pbs_python",
						"failed to copy event_job");
					rc = 1;
					goto pbs_python_end;
				}

				req_params.rq_job = (struct rq_queuejob *)&rqj;

				if ((svrattrl_e=find_svrattrl_list_entry(&event,
					PY_EVENT_PARAM_PID, NULL)) != NULL) {
					req_params.pid = atoi(svrattrl_e->al_value);
				} else {
					req_params.pid = -1;
				}

				req_params.vns_list = (pbs_list_head *)&event_vnode;


				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}

				break;
			case HOOK_EVENT_EXECHOST_PERIODIC:
			case HOOK_EVENT_EXECHOST_STARTUP:
				req_params.vns_list = &event_vnode;
				if (hook_event == HOOK_EVENT_EXECHOST_PERIODIC) {
					req_params.jobs_list = &event_jobs;
				}
				rc = pbs_python_event_set(hook_event, req_user,
					req_host, &req_params);

				if (rc == -1) { /* internal server code failure */
					log_event(PBSEVENT_DEBUG,
						PBS_EVENTCLASS_HOOK, LOG_ERR,
						hook_name,
						"Encountered an error while setting event");
				}
				break;
			default:
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK, LOG_ERR,
					hook_name, "Unexpected event");
				rc = 1;
				goto pbs_python_end;
		}

		/* This sets Python event object's hook_name value */
		rc = pbs_python_event_set_attrval(PY_EVENT_HOOK_NAME,
			hook_name);

		if (rc == -1) {
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK,
				LOG_ERR, hook_name, "Failed to set event 'hook_name'.");
		}

		rc = pbs_python_event_set_attrval(PY_EVENT_HOOK_TYPE,
			hookstr_type);

		if (rc == -1) {
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK,
				LOG_ERR, hook_name, "Failed to set event 'hook_type'.");
		}

		rc = pbs_python_event_set_attrval(PY_EVENT_TYPE,
			hookstr_event);

		if (rc == -1) {
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK,
				LOG_ERR, hook_name,
				"Failed to set event 'type'.");
		}

		pbs_python_set_mode(PY_MODE); /* hook script mode */

		/* reset global flag to allow modification of             */
		/* attributes and resources for every new hook execution. */
		pbs_python_event_param_mod_allow();

		set_alarm(hook_alarm, pbs_python_set_interrupt);
		if (hook_script[0] == '\0') {
			char *tmp_argv[2];

			tmp_argv[0] = argv[0];
			tmp_argv[1] = (char *)0;

			rc=Py_Main(1, tmp_argv);
		} else {
			rc=pbs_python_run_code_in_namespace(&svr_interp_data,
				py_script, 0);
		}
		set_alarm(0, pbs_python_set_interrupt);

		pbs_python_set_mode(C_MODE);  /* PBS C mode - flexible */

		/* Prepare output file */
		if ((the_output !=  NULL) && (*the_output != '\0')) {
			fp_out = fopen(the_output, "w");

			if (fp_out == NULL) {
				fprintf(stderr, "failed to open event output file %s\n", the_output);
				exit(2);
			}
		} else {
			fp_out = stdout;
		}

		switch (rc) {
			case -1:	/* internal error */
				log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK,
					LOG_ERR, hook_name,
					"Internal server error encountered. Skipping hook.");
				rc = -1; /* should not happen */
				goto pbs_python_end;
			case -2:	/* unhandled exception */
				pbs_python_event_reject(NULL);
				pbs_python_event_param_mod_disallow();

				snprintf(log_buffer, LOG_BUF_SIZE-1,
					"%s hook '%s' encountered an exception, "
					"request rejected",
					hook_event_as_string(hook_event), hook_name);
				log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK,
					LOG_ERR, hook_name, log_buffer);
				rc = -2; /* should not happen */
				break;
			case -3:	/* alarm timeout */
				pbs_python_event_reject(NULL);
				pbs_python_event_param_mod_disallow();

				snprintf(log_buffer, LOG_BUF_SIZE-1,
					"alarm call while running %s hook '%s', "
					"request rejected",
					hook_event_as_string(hook_event), hook_name);
				log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK,
					LOG_ERR, hook_name, log_buffer);
				rc = -3; /* should not happen */
				break;
		}

		hook_output_param_init(&req_params_out);
		switch (hook_event) {

			case HOOK_EVENT_QUEUEJOB:

				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);
				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);

					req_params_out.rq_job = (struct rq_quejob *)&rqj;
					pbs_python_event_to_request(hook_event,
						&req_params_out);

					fprint_svrattrl_list(fp_out, EVENT_JOB_OBJECT,
						&rqj.rq_attr);
				}
				break;

			case HOOK_EVENT_MODIFYJOB:

				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);

				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
					req_params_out.rq_manage = (struct rq_manage *)&rqm;
					pbs_python_event_to_request(hook_event,
						&req_params_out);
					fprint_svrattrl_list(fp_out, EVENT_JOB_OBJECT,
						&rqm.rq_attr);
				}
				break;
			case HOOK_EVENT_MOVEJOB:

				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);

				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
					req_params_out.rq_move = (struct rq_manage *)&rqmv;
					pbs_python_event_to_request(hook_event,
						&req_params_out);
					if ((rqmv.rq_destin != NULL) && \
						(rqmv.rq_destin[0] != '\0'))
						fprintf(fp_out, "%s.%s=%s\n", EVENT_OBJECT,
							PY_EVENT_PARAM_SRC_QUEUE, rqmv.rq_destin);
				}
				break;

			case HOOK_EVENT_RUNJOB:

				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);

					new_exec_time_str =  \
			       pbs_python_event_job_getval_hookset(ATTR_a,
						NULL, 0, NULL, 0);

					if (new_exec_time_str != NULL)
						fprintf(fp_out, "%s.%s=%s\n", EVENT_JOB_OBJECT,
							ATTR_a, new_exec_time_str);

					new_hold_types_str  = \
				  pbs_python_event_job_getval_hookset(ATTR_h,
						NULL, 0, NULL, 0);

					if (new_hold_types_str != NULL)
						fprintf(fp_out, "%s.%s=%s\n", EVENT_JOB_OBJECT,
							ATTR_h, new_hold_types_str);

					new_project_str = \
			      pbs_python_event_job_getval_hookset(ATTR_project,
						NULL, 0, NULL, 0);
					if (new_project_str != NULL)
						fprintf(fp_out, "%s.%s=%s\n", EVENT_JOB_OBJECT,
							ATTR_project, new_project_str);

				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
				}
				break;
			case HOOK_EVENT_RESVSUB:

				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);

				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
					req_params_out.rq_job = (struct rq_quejob *)&rqj;
					pbs_python_event_to_request(hook_event,
						&req_params_out);
					fprint_svrattrl_list(fp_out, EVENT_RESV_OBJECT,
						&rqj.rq_attr);
				}
				break;

			case HOOK_EVENT_EXECJOB_BEGIN:
			case HOOK_EVENT_EXECJOB_PROLOGUE:
			case HOOK_EVENT_EXECJOB_EPILOGUE:
			case HOOK_EVENT_EXECJOB_END:
			case HOOK_EVENT_EXECJOB_PRETERM:

				if (pbs_python_event_get_accept_flag() == FALSE) {

					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL) fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
						rej_msg);


				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
				}

				/* Whether accept or reject, show job, vnode_list changes and job actions */
				free_attrlist(&event_vnode);
				CLEAR_HEAD(event_vnode);

				req_params_out.rq_job = (struct rq_quejob *)&rqj;
				req_params_out.vns_list = (pbs_list_head *)&event_vnode;
				pbs_python_event_to_request(hook_event,
					&req_params_out);
				fprint_svrattrl_list(fp_out, EVENT_JOB_OBJECT,
					&rqj.rq_attr);
				fprint_svrattrl_list(fp_out,
					EVENT_VNODELIST_OBJECT,
					&event_vnode);

				/* job actions */
				rerunjob_str = pbs_python_event_job_getval_hookset(\
					    PY_RERUNJOB_FLAG, NULL, 0, NULL, 0);
				if (rerunjob_str != NULL) {
					fprintf(fp_out, "%s.%s=%s\n", EVENT_JOB_OBJECT,
						PY_RERUNJOB_FLAG, rerunjob_str);
				}
				deletejob_str = pbs_python_event_job_getval_hookset(\
					   PY_DELETEJOB_FLAG, NULL, 0, NULL, 0);
				if (deletejob_str != NULL) {
					fprintf(fp_out, "%s.%s=%s\n", EVENT_JOB_OBJECT,
						PY_DELETEJOB_FLAG,
						deletejob_str);
				}
				break;

			case HOOK_EVENT_EXECJOB_LAUNCH:

				if (pbs_python_event_get_accept_flag() == FALSE) {

					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL) fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
						rej_msg);
					break;
				}
				fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
				fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);

				if (progname != NULL) {
					free(progname);
					progname = NULL;
				}
				free_attrlist(&event_argv);
				CLEAR_HEAD(event_argv);
				if (env_str != NULL) {
					free(env_str);
					env_str = NULL;
				}

				req_params_out.progname = (char **)&progname;
				req_params_out.argv_list = (pbs_list_head *)&event_argv;
				req_params_out.env = (char **)&env_str;

				pbs_python_event_to_request(hook_event,
					&req_params_out);
				fprint_svrattrl_list(fp_out, EVENT_JOB_OBJECT,
					&rqj.rq_attr);
				fprint_svrattrl_list(fp_out,
					EVENT_VNODELIST_OBJECT,
					&event_vnode);
				fprintf(fp_out, "%s=%s\n", EVENT_PROGNAME_OBJECT, progname);
				fprint_svrattrl_list(fp_out, EVENT_OBJECT, &event_argv);
				fprintf(fp_out, "%s=\"\"\"%s\"\"\"\n", EVENT_ENV_OBJECT, env_str);
				if (strcmp(progname_orig, progname) != 0) {
					print_progname = 1;
				}

				argv_str = argv_list_to_str((pbs_list_head *)&event_argv);

				if (((argv_str_orig == NULL) && (argv_str != NULL)) ||
				    ((argv_str_orig != NULL) && (argv_str == NULL)) ||
				    ((argv_str_orig != NULL) && (argv_str != NULL) &&
					(strcmp(argv_str_orig, argv_str) != 0))) {
					print_argv = 1;
				}

				if (!varlist_same(env_str_orig, env_str)) {
					print_env = 1;
				}

				if (print_progname) {
					snprintf(log_buffer, sizeof(log_buffer), "progname orig: %s",  progname_orig);
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
					snprintf(log_buffer, sizeof(log_buffer), "progname new: %s",  progname);
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
				}
				if (print_argv) {
					snprintf(log_buffer, sizeof(log_buffer), "argv orig: %s",  argv_str_orig?argv_str_orig:"");
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
					snprintf(log_buffer, sizeof(log_buffer), "argv new: %s",  argv_str?argv_str:"");
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
				}
				if (print_env) {
					snprintf(log_buffer, sizeof(log_buffer), "env orig: %s",  env_str_orig);
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
					snprintf(log_buffer, sizeof(log_buffer), "env new: %s",  env_str);
					log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_HOOK, LOG_INFO, hook_name, log_buffer);
				}
				if (argv_str_orig != NULL)
					free(argv_str_orig);
				if (argv_str != NULL)
					free(argv_str);
				/* Put something here the modified stuff */
				break;
			case HOOK_EVENT_EXECHOST_PERIODIC:
			case HOOK_EVENT_EXECHOST_STARTUP:
				if (pbs_python_event_get_accept_flag() == FALSE) {
					rej_msg = pbs_python_event_get_reject_msg();
					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL)
						fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
							rej_msg);
				} else {
					fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);

				}
				/* show vnode_list changes whether or not accepted or */
				/*  rejected */
				free_attrlist(&event_vnode);
				CLEAR_HEAD(event_vnode);
				free_attrlist(&event_jobs);
				CLEAR_HEAD(event_jobs);
				req_params_out.vns_list = (pbs_list_head *)&event_vnode;
				if (hook_event == HOOK_EVENT_EXECHOST_PERIODIC) {
					free_attrlist(&event_jobs);
					CLEAR_HEAD(event_jobs);
					req_params_out.jobs_list = (pbs_list_head *)&event_jobs;
				}
				pbs_python_event_to_request(hook_event,
					&req_params_out);

				fprint_svrattrl_list(fp_out, EVENT_VNODELIST_OBJECT,
					&event_vnode);
				if (hook_event == HOOK_EVENT_EXECHOST_PERIODIC) {
					fprint_svrattrl_list(fp_out, EVENT_JOBLIST_OBJECT,
						&event_jobs);
				}
				break;
			case HOOK_EVENT_EXECJOB_ATTACH:

				if (pbs_python_event_get_accept_flag() == FALSE) {

					rej_msg = pbs_python_event_get_reject_msg();

					fprintf(fp_out, "%s=True\n", EVENT_REJECT_OBJECT);
					fprintf(fp_out, "%s=False\n", EVENT_ACCEPT_OBJECT);
					if (rej_msg != NULL) fprintf(fp_out, "%s=%s\n", EVENT_REJECT_MSG_OBJECT,
						rej_msg);
					break;
				}
				fprintf(fp_out, "%s=True\n", EVENT_ACCEPT_OBJECT);
				fprintf(fp_out, "%s=False\n", EVENT_REJECT_OBJECT);
				break;
			default:
				log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_HOOK, LOG_ERR,
					hook_name, "event_to_request: Unexpected event");
				rc = 1;
		}
pbs_python_end:
		if (pbs_python_get_reboot_host_flag() == TRUE) {
			char *reboot_cmd = NULL;

			fprintf(fp_out, "%s.%s=True\n", PBS_OBJ,
				PBS_REBOOT_OBJECT);
			reboot_cmd = pbs_python_get_reboot_host_cmd();
			if (reboot_cmd != NULL)
				fprintf(fp_out, "%s.%s=%s\n", PBS_OBJ,
					PBS_REBOOT_CMD_OBJECT, reboot_cmd);
		}
		if (pbs_python_get_scheduler_restart_cycle_flag() == TRUE) {

			fprintf(fp_out, "%s.%s=True\n",
				SERVER_OBJECT,
				PY_SCHEDULER_RESTART_CYCLE_METHOD);
		}
		if ((fp_out != NULL) && (fp_out != stdout))
			fclose(fp_out);

		if ((fp_server_out != NULL) && (fp_server_out != stdout))
			fclose(fp_server_out);

		pbs_python_ext_shutdown_interpreter(&svr_interp_data);

		free_attrlist(&event_vnode);
		CLEAR_HEAD(event_vnode);
		free_attrlist(&event_argv);
		CLEAR_HEAD(event_argv);
		free_attrlist(&event_jobs);
		CLEAR_HEAD(event_jobs);
		if (progname != NULL)
			free(progname);
		if (env_str != NULL)
			free(env_str);
	}

	return rc;
}
