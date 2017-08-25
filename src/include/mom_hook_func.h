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
#ifndef	_MOM_HOOK_FUNC_H
#define	_MOM_HOOK_FUNC_H
#ifdef	__cplusplus
extern "C" {
#endif


#ifdef linux
#define	REBOOT_CMD	"/sbin/reboot"
#elif WIN32
#define REBOOT_CMD	"\\windows\\system32\\shutdown.exe /g /f /t 5"
#else
#define REBOOT_CMD	"/usr/sbin/reboot"
#endif

/* These are attribute names whose value if set from a hook will be */
/* merged withe mom's vnlp list, which is sent to the server upon */
/* receiving IS_HELLO sequeunce.  */
#define HOOK_VNL_PERSISTENT_ATTRIBS  "resources_available sharing pcpus resources_assigned"

/* used to send hook's job delete/requeue request to server */
struct hook_job_action {
	pbs_list_link  hja_link;
	char           hja_jid[PBS_MAXSVRJOBID+1]; /* job id */
	unsigned long  hja_actid;		   /* action id number */
	int            hja_runct;		   /* job's run count */
	enum hook_user hja_huser;		   /* admin or user */
	int            hja_action;		   /* delete or requeue */
};

#ifdef VNL_NODENUM
struct hook_vnl_action {
	pbs_list_link  hva_link;
	unsigned long  hva_actid;		 /* action id number */
	char           hva_euser[PBS_MAXUSER+1]; /* effective hook user */
	vnl_t         *hva_vnl;			 /* vnl updates */
	int	       hva_update_cmd;		 /* e.g. IS_UPDATE_FROM_HOOK */
};
#endif

/**
 * @brief
 * 	The mom_hook_input_t holds the input request parameters
 * 	to the mom_process_hooks() function.
 * @param[in]	pjob - a job for which a hook is executing in behalf.
 * @param[in]	progname - used by execjob_launch hook as the
 * 			pbs.event().progname value.
 * @param[in]	argv - used by execjob_launch hook as the
 * 			pbs.event().argv value.
 * @param[in]	env - used by execjob_launch hook as the
 * 			pbs.event().env value.
 * @param[in]	vnl - a vnl_t * structure used by various hooks
 * 			that enumerate the list of vnodes and
 * 			their attributes/resources assigned to a
 * 			job, or for exechost_periodic and exechost_startup
 * 			hooks, the vnodes managed by the system.
 * @param[in]	vnl_fail - a vnl_t * structure used by various hooks
 * 			that enumerate the list of vnodes and
 * 			their attributes/resources assigned to a
 * 			job, whose parent moms are non-functional.
 * @param[in]	mom_list_fail - a svattrl structure enumerating the
 *			sister mom hosts that have been seen as down.
 * @param[in]	mom_list_good - a svattrl structure enumerating the
 *			sister mom hosts that have been seen as up.
 * @param[in]	pid - used by execjob_atttach hook as the
 * 			pbs.event().pid value.
 * @param[in]	jobs_list - list of jobs and their attributes/resources
 * 			    used by the exechost_periodic hook.
 *
 */
typedef struct mom_hook_input {
	job	*pjob;
	char	*progname;
	char	**argv;
	char	**env;
	void	*vnl;
	void	*vnl_fail;
	void	*mom_list_fail;
	void	*mom_list_good;
	pid_t	pid;
	pbs_list_head	*jobs_list;
} mom_hook_input_t;


/**
 * @brief
 * 	The mom_hook_output_t holds the output request parameters
 * 	that are filled in, after calling mom_process_hooks().
 * @param[out]	reject_errcode - the resultant errorcode
 * 		(e.g. PBSE_HOOKERROR) when job is rejected due
 * 		to hook.
 * @param[out]	last_phook - the most recent hook that executed.
 * @param[out]	fail_action - the accumulation of fail_action
 * 			values seen for the hooks that
 * 			executed; mom_process_hooks() will
 * 			execute all hooks responding to a particular
 * 			event until reject is encountered.
 * @param[out]	progname - the resultant pbs.event().progname value
 * 			 after executing the execjob_launch hooks
 * 			 responding to a particular event.
 * @param[out]	argv - the resultant pbs.event().argv value after
 * 			executing the execjob_launch hooks
 * 			responding to a particular event.
 * @param[out]	env - the resultant pbs.event().env value after
 * 			executing the execjob_launch hooks
 * 			responding to a particular event.
 * @param[in]	vnl - a vnl_t * structure holding the vnode changes
 * 			made after executing mom_process_hooks().
 * @param[in]	vnl_fail - a vnl_t * structure holding the changes to
 * 			failed vnodes made after executing
 *			mom_process_hooks().
 *holding the changes to
 * 			failed vnodes made after executing
 *			mom_process_hooks().
 */
typedef struct mom_hook_output {
	int		*reject_errcode;
	hook		**last_phook;
	unsigned int	*fail_action;
	char		**progname;
	pbs_list_head	*argv;
	char		**env;
	void		*vnl;
	void		*vnl_fail;
} mom_hook_output_t;

extern int
mom_process_hooks(unsigned int hook_event, char *req_user, char *req_host,
	mom_hook_input_t *hook_input, mom_hook_output_t *hook_output, char *hook_msg,
	size_t msg_len, int update_svr);

extern void
cleanup_hooks_in_path_spool(struct work_task *ptask);

extern int
python_script_alloc(const char *script_path, struct python_script **py_script);

extern void python_script_free(struct python_script *py_script);

extern void run_periodic_hook_bg(hook *phook);

extern int
num_eligible_hooks(unsigned int hook_event);

extern int
get_hook_results(char *input_file, int *accept_flag, int *reject_flag,
	char *reject_msg, int reject_msg_size, int *reject_rerunjob,
	int *reject_deletejob, int *reboot_flag, char *reboot_cmd,
	int reboot_cmd_size, pbs_list_head *p_obj, job *pjob, hook *phook,
	int copy_file, mom_hook_output_t *hook_output);

extern void
send_hook_job_action(struct hook_job_action *phja);

extern void
attach_hook_requestor_merge_vnl(hook *phook, void *pnv, job *pjob);

extern void
new_job_action_req(job *pjob, enum hook_user huser, int action);

extern void
send_hook_fail_action(hook *);

extern void
vna_list_free(pbs_list_head);

extern void
mom_hook_input_init(mom_hook_input_t *hook_input);

extern void
mom_hook_output_init(mom_hook_output_t *hook_output);

extern void send_hook_fail_action(hook *);	

#ifdef	__cplusplus
}
#endif
#endif	/* _MOM_HOOK_FUNC_H */
