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

#include "pbs_config.h"
#include "pbs_ifl.h"
#include "pbs_internal.h"
#include "pbs_version.h"
#include "pbs_error.h"
#include "attribute.h"
#include "job.h"
#include "reservation.h"
#include "server.h"
#include "pbs_nodes.h"
#include "pbs_sched.h"
#include "pbs_python_private.h"
#include <Python.h>

/* #define MODULE_NAME "_pbs_v1_module" */
#define MODULE_NAME "pbs_python"

struct python_interpreter_data svr_interp_data;

void *job_attr_idx = NULL;
void *resv_attr_idx = NULL;
void *node_attr_idx = NULL;
void *que_attr_idx = NULL;
void *svr_attr_idx = NULL;
void *sched_attr_idx = NULL;

char server_name[PBS_MAXSERVERNAME+1] = "";
char server_host[PBS_MAXHOSTNAME+1] = "";
char *pbs_server_name = NULL;
struct server server;


PyMODINIT_FUNC
PyInit__pbs_v1(void) {
	int i;
	PyObject * module = NULL;
	PyObject *py_sys_modules = NULL;

	memset(&server, 0, sizeof(server));

	if (set_msgdaemonname(MODULE_NAME)) {
		return PyErr_Format(PyExc_MemoryError,
			 "set_msgdaemonname() failed to allocate memory");
	}

	if (pbs_loadconf(0) == 0) {
		return PyErr_Format(PyExc_Exception, "Failed to load pbs.conf!");
	}

	set_log_conf(pbs_conf.pbs_leaf_name, pbs_conf.pbs_mom_node_name,
			pbs_conf.locallog, pbs_conf.syslogfac,
			pbs_conf.syslogsvr, pbs_conf.pbs_log_highres_timestamp);

	pbs_python_set_use_static_data_value(0);

	/* by default, server_name is what is set in /etc/pbs.conf */
	strncpy(server_name, pbs_conf.pbs_server_name, PBS_MAXSERVERNAME);

	/* determine the actual server name */
	pbs_server_name = pbs_default();
	if ((!pbs_server_name) || (*pbs_server_name == '\0')) {
		return PyErr_Format(PyExc_Exception,
			 "pbs_default() failed acquire the server name");
	}

	/* determine the server host name */
	if (get_fullhostname(pbs_server_name, server_host, PBS_MAXSERVERNAME) != 0) {
		return PyErr_Format(PyExc_Exception,
			 "get_fullhostname() failed to acqiure the server host name");
	}

	if ((job_attr_idx = cr_attrdef_idx(job_attr_def, JOB_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating job attribute search index");
	}
	if ((node_attr_idx = cr_attrdef_idx(node_attr_def, ND_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating node attribute search index");
	}
	if ((que_attr_idx = cr_attrdef_idx(que_attr_def, QA_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating queue attribute search index");
	}
	if ((svr_attr_idx = cr_attrdef_idx(svr_attr_def, SVR_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating server attribute search index");
	}
	if ((sched_attr_idx = cr_attrdef_idx(sched_attr_def, SCHED_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating sched attribute search index");
	}
	if ((resv_attr_idx = cr_attrdef_idx(resv_attr_def, RESV_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating resv attribute search index");
	}
	if (cr_rescdef_idx(svr_resc_def, svr_resc_size) != 0) {
		return PyErr_Format(PyExc_Exception,
			"Failed creating resc definition search index");
	}

	/* initialize the pointers in the resource_def array */
	for (i = 0; i < (svr_resc_size - 1); ++i) {
		svr_resc_def[i].rs_next = &svr_resc_def[i+1];
	}

	/* set python interp data */
	svr_interp_data.init_interpreter_data = NULL;
	svr_interp_data.destroy_interpreter_data = NULL;
	svr_interp_data.interp_started = 1;
	svr_interp_data.pbs_python_types_loaded = 0;
	if (gethostname(svr_interp_data.local_host_name, PBS_MAXHOSTNAME) == -1) {
		return PyErr_Format(PyExc_Exception,
			"gethostname() failed to acquire the local host name");
	}
	svr_interp_data.daemon_name = strdup(MODULE_NAME);
	svr_interp_data.data_initialized = 1;

	/* construct _pbs_v1 module */
	module = pbs_v1_module_init();
	if (module == NULL) {
		return PyErr_Format(PyExc_Exception,
			 PBS_PYTHON_V1_MODULE_EXTENSION_NAME
			 " module initialization failed");
	}

	/*
	 * get a borrowed reference to sys.modules and add our module to it in order
	 * to prevent an import cycle while loading the PBS python types
	 */
	py_sys_modules = PyImport_GetModuleDict();
	if (PyDict_SetItemString(py_sys_modules,
			PBS_PYTHON_V1_MODULE_EXTENSION_NAME, module)) {
		return PyErr_Format(PyExc_Exception,
			"failed to addd the " PBS_PYTHON_V1_MODULE_EXTENSION_NAME
			" module to sys.modules");
	}

	/* load python types into the _pbs_v1 module */
	if ((pbs_python_load_python_types(&svr_interp_data) == -1)) {
		PyDict_DelItemString(py_sys_modules,
			PBS_PYTHON_V1_MODULE_EXTENSION_NAME);
		return PyErr_Format(PyExc_Exception,
			"pbs_python_load_python_types() failed to load Python types");
	}

	return module;
}

/*
 * The following are a set of unused "dummy" functions and global variables
 * needed to link the loadable pbs_v1 Python module.
 */

time_t time_now = 0;
struct pbsnode **pbsndlist = NULL;
int svr_totnodes = 0;
int svr_delay_entry = 0;
char *path_hooks = NULL;
char *path_hooks_workdir = NULL;
char *resc_in_err = NULL;
char *path_rescdef = NULL;

pbs_list_head task_list_immed;
pbs_list_head task_list_timed;
pbs_list_head task_list_event;
pbs_list_head svr_queues;
pbs_list_head svr_alljobs;
pbs_list_head svr_allresvs;
pbs_list_head svr_allhooks;
pbs_list_head svr_queuejob_hooks;
pbs_list_head svr_modifyjob_hooks;
pbs_list_head svr_resvsub_hooks;
pbs_list_head svr_movejob_hooks;
pbs_list_head svr_runjob_hooks;
pbs_list_head svr_management_hooks;
pbs_list_head svr_provision_hooks;
pbs_list_head svr_periodic_hooks;
pbs_list_head svr_resv_end_hooks;
pbs_list_head svr_execjob_begin_hooks;
pbs_list_head svr_execjob_prologue_hooks;
pbs_list_head svr_execjob_epilogue_hooks;
pbs_list_head svr_execjob_preterm_hooks;
pbs_list_head svr_execjob_launch_hooks;
pbs_list_head svr_execjob_end_hooks;
pbs_list_head svr_exechost_periodic_hooks;
pbs_list_head svr_exechost_startup_hooks;
pbs_list_head svr_execjob_attach_hooks;
pbs_list_head svr_execjob_resize_hooks;
pbs_list_head svr_execjob_abort_hooks;
pbs_list_head svr_execjob_postsuspend_hooks;
pbs_list_head svr_execjob_preresume_hooks;

PyObject *
PyInit__pbs_ifl(void) {
	return NULL;
}

int
set_resources_min_max(attribute *old, attribute *new, enum batch_op op) {
	return (0);
}

void
set_scheduler_flag(int flag, pbs_sched *psched) {
	return;
}

job	*
find_job(char *jobid) {
	return NULL;
}

resc_resv *
find_resv(char *resvid) {
	return NULL;
}

pbs_queue *
find_queuebyname(char *qname) {
	return NULL;
}

struct pbsnode *find_nodebyname(char *nname) {
	return NULL;
}

void
write_node_state(void) {
	return;
}

void
mgr_log_attr(char *msg, struct svrattrl *plist, int logclass,
		char *objname, char *hookname) {
	return;
}

int
mgr_set_attr(attribute *pattr, void *pidx, attribute_def *pdef, int limit,
		svrattrl *plist, int privil, int *bad, void *parent, int mode) {
	return (0);
}

int
svr_chk_history_conf(void) {
	return (0);
}

int
save_nodes_db(int flag, void *pmom) {
	return (0);
}

void
update_state_ct(attribute *pattr, int *ct_array, char *buf) {
	return;
}

void
update_license_ct(attribute *pattr, char *buf) {
	return;
}

int
is_job_array(char *jobid) {
	return (0);
}

job *
find_arrayparent(char *subjobid) {
	return NULL;
}

int
ck_chkpnt(attribute *pattr, void *pobject, int mode) {
	return (0);
}

int
cred_name_okay(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
poke_scheduler(attribute *attr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
action_sched_port(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_priv(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_log(attribute *pattr, void *pobj, int actmode) {
	return 0;
}
int
action_sched_log_events(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_iteration(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_user(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_queue_partition(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_preempt_order(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_sched_preempt_common(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
action_reserve_retry_time(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
action_reserve_retry_init(attribute *pattr, void *pobj, int actmode) {
        return PBSE_NONE;
}

int
set_rpp_retry(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
set_rpp_highwater(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
is_valid_resource(attribute *pattr, void *pobject, int actmode) {

	return PBSE_NONE;
}

int
deflt_chunk_action(attribute *pattr, void *pobj, int mode) {

	return 0;
}

int
action_svr_iteration(attribute *pattr, void *pobj, int mode) {
	return 0;
}

int
set_license_location(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

void
unset_license_location(void) {
	return;
}

int
set_node_fail_requeue(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

void
unset_node_fail_requeue(void) {
	return;
}

int
action_node_partition(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

int
set_license_min(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

void
unset_license_min(void) {
	return;
}

int
set_license_max(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

void
unset_license_max(void) {
	return;
}

int
set_license_linger(attribute *pattr, void *pobject, int actmode) {

	return (PBSE_NONE);
}

void
unset_license_linger(void) {
	return;
}

void
unset_job_history_enable(void) {
	return;
}

int
set_job_history_enable(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

int
set_job_history_duration(attribute *pattr, void *pobject, int actmode) {

	return (PBSE_NONE);
}

void
unset_job_history_duration(void) {
	return;
}

int
set_max_job_sequence_id(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

void
unset_max_job_sequence_id(void) {
	return;
}

int
eligibletime_action(attribute *pattr, void *pobject, int actmode) {
	return 0;
}

int
decode_formula(attribute *patr, char *name, char *rescn, char *val) {
	return PBSE_NONE;
}

int
action_entlim_chk(attribute *pattr, void *pobject, int actmode) {
	return PBSE_NONE;
}

int
action_entlim_ct(attribute *pattr, void *pobject, int actmode) {
	return PBSE_NONE;
}

int
action_entlim_res(attribute *pattr, void *pobject, int actmode) {
	return PBSE_NONE;
}

int
check_no_entlim(attribute *pattr, void *pobject, int actmode) {
	return 0;
}

int
default_queue_chk(attribute *pattr, void *pobj, int actmode) {
	return (PBSE_NONE);
}

void
set_vnode_state(struct pbsnode *pnode, unsigned long state_bits,
		 enum vnode_state_op type) {
	return;
}

int
ctcpus(char *buf, int *hascpp) {
	return 0;
}

int
validate_nodespec(char *str) {
	return 0;
}

int
check_que_enable(attribute *pattr, void *pque, int mode) {
	return (0);
}

int
set_queue_type(attribute *pattr, void *pque, int mode) {
	return (0);
}

int
manager_oper_chk(attribute *pattr, void *pobject, int actmode) {
	return (0);
}

int
node_comment(attribute *pattr, void *pobj, int act) {
	return 0;
}

int
node_prov_enable_action(attribute *new, void *pobj, int act) {
	return PBSE_NONE;
}

int
set_log_events(attribute *new, void *pobj, int act) {
	return PBSE_NONE;
}

int
node_current_aoe_action(attribute *new, void *pobj, int act) {
	return PBSE_NONE;
}

int
action_sched_host(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
action_throughput_mode(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
action_job_run_wait(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
action_opt_bf_fuzzy(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
action_sched_partition(attribute *new, void *pobj, int act)
{
	return PBSE_NONE;
}

int
decode_rcost(struct attribute *patr, char *name, char *rescn, char *val) {
	return 0;
}

int
encode_rcost(const attribute *attr, pbs_list_head *phead, char *atname,
		char *rsname, int mode, svrattrl **rtnl) {
	return (1);
}

int
set_rcost(struct attribute *old, struct attribute *new, enum batch_op op) {
	return (0);
}

void
free_rcost(attribute *pattr) {
	return;
}

int
svr_max_conc_prov_action(attribute *new, void *pobj, int act) {
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
queuestart_action(attribute *pattr, void *pobject, int actmode) {
	return 0;
}

int
set_cred_renew_enable(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
set_cred_renew_period(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
set_cred_renew_cache_period(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
encode_svrstate(const attribute *pattr, pbs_list_head *phead, char *atname,
		char *rsname, int mode, svrattrl **rtnl) {
	return (1);
}

int
comp_chkpnt(attribute *attr, attribute *with) {
	return 0;
}

int
decode_depend(struct attribute *patr, char *name, char *rescn, char *val) {
	return (0);
}

int
encode_depend(const attribute *attr, pbs_list_head *phead, char *atname,
		char *rsname, int mode, svrattrl **rtnl) {
	return 0;
}

int
set_depend(struct attribute *attr, struct attribute *new, enum batch_op op) {
	return (0);
}

int
comp_depend(struct attribute *attr, struct attribute *with) {
	return (-1);
}

void
free_depend(struct attribute *attr) {
	return;
}

int
depend_on_que(attribute *pattr, void *pobj, int mode) {
	return 0;
}

int
job_set_wait(attribute *pattr, void *pjob, int mode) {
	return (0);
}

int
alter_eligibletime(attribute *pattr, void *pobject, int actmode) {
	return PBSE_NONE;
}

int
keepfiles_action(attribute *pattr, void *pobject, int actmode) {
    return PBSE_NONE;
}

int
removefiles_action(attribute *pattr, void *pobject, int actmode) {
    return PBSE_NONE;
}

int
action_est_start_time_freq(attribute *pattr, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
setup_arrayjob_attrs(attribute *pattr, void *pobj, int mode) {
	return (PBSE_NONE);
}

int
fixup_arrayindicies(attribute *pattr, void *pobj, int mode) {
	return (PBSE_NONE);
}

int
decode_Mom_list(struct attribute *patr, char *name, char *rescn, char *val) {
	return (0);
}

int
node_queue_action(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
set_node_host_name(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
set_node_mom_port(attribute *pattr, void *pobj, int actmode) {
	return 0;
}

int
node_np_action(attribute *new, void *pobj, int actmode) {
	return PBSE_NONE;
}

int
node_pcpu_action(attribute *new, void *pobj, int actmode) {
	return (0);
}

char*
find_aoe_from_request(resc_resv *presv) {
	return NULL;
}

int
force_qsub_daemons_update_action(attribute *pattr, void *pobject,
	int actmode) {
	return (PBSE_NONE);
}

int
set_node_topology(attribute *pattr, void *pobject, int actmode) {

	return (PBSE_NONE);
}

int
chk_vnode_pool(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}

int
validate_job_formula(attribute *pattr, void *pobject, int actmode) {
	return (PBSE_NONE);
}
