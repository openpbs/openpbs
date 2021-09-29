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

#ifndef	_FIFO_H
#define	_FIFO_H

#include <string>

#include  <limits.h>
#include "data_types.h"
#include "sched_cmds.h"

/**
 * @brief Gets the Scheduler Command sent by the Server
 *
 * @param[in]     sock - secondary connection to the server
 * @param[in,out] cmd  - pointer to sched cmd to be filled with received cmd
 *
 * @return	int
 * @retval	0	: for EOF
 * @retval	+1	: for success
 * @retval	-1	: for error
 */
int get_sched_cmd(int sock, sched_cmd *cmd);

/**
 * @brief This is non-blocking version of get_sched_cmd()
 *
 * @param[in]     sock - secondary connection to the server
 * @param[in,out] cmd  - pointer to sched cmd to be filled with received cmd
 *
 * @return	int
 * @retval	0	no super high priority command
 * @retval	+1	for success
 * @retval	-1	for error
 * @retval	-2	for EOF
 *
 * @note this function uses different return code (-2) for EOF than get_sched_cmd() (-1)
 */
int get_sched_cmd_noblk(int sock, sched_cmd *cmd);

/*
 *      schedinit - initialize conf struct and parse conf files
 */
int schedinit(int nthreads);

/*
 *	intermediate_schedule - responsible for starting/restarting scheduling
 *				cycle
 */

int intermediate_schedule(int sd, const sched_cmd *cmd);

/*
 *      scheduling_cycle - the controling function of the scheduling cycle
 */

int scheduling_cycle(int sd, const sched_cmd *cmd);

/*
 *	init_scheduling_cycle - run things that need to be set up every
 *				scheduling cycle
 *	NOTE: failure of this function will cause schedule() to exit
 */
int init_scheduling_cycle(status *policy, int pbs_sd, server_info *sinfo);

/*
 *
 *      next_job - find the next job to be run by the scheduler
 *
 *        policy - policy info.
 *        sinfo - the server the jobs are on
 *        flag - whether or not to initialize, sort jobs.
 *
 *      returns the next job to run or NULL when there are no more jobs
 *              to run, or on error
 *
 */

resource_resv *next_job(status *policy, server_info *sinfo, int flag);

/*
 *      find_runnable_job_ind - find the index of the next runnable job in a job array
 *  		Jobs are runnable if:
 *	   	in state 'Q'
 *		suspended by the scheduler
 *		is job array in state 'B' and there is a queued subjob
 *
 *		Reservations are runnable if they are in state RESV_CONFIRMED
 */
int find_runnable_resresv_ind(resource_resv **resresv_arr, int start_index);

/*
 *	find_non_normal_job_ind - find the index of the next runnable express,preempted
 */
int find_non_normal_job_ind(resource_resv **jobs, int start_index);

/*
 *
 *      sim_run_update_resresv - simulate the running of a job
 */
bool sim_run_update_resresv(status *policy, resource_resv *resresv, std::vector<nspec *>& ns_arr, unsigned int flags);
bool sim_run_update_resresv(status *policy, resource_resv *resresv, unsigned int flags);

/*
 *
 *	run_update_resresv - run a resource_resv (job or reservation) and
 *				update the local cache if it was successfully
 *				run.  Currently we only simulate the running
 *				of reservations.
 *
 *	  pbs_sd - connection descriptor to pbs_server or
 *			  SIMULATE_SD if we're simulating
 *	  sinfo  - server job is on
 *	  qinfo  - queue job resides in or NULL if reservation
 *	  rresv  - the job/reservation to run
 *	  flags  - flags to modify procedure
 *		RURR_ADD_END_EVENT - add an end event to calendar for this job
 *
 *	return 1 for success
 *	return 0 for failure (see pbs_errno for more info)
 *	return -1 on error
 *
 */
bool run_update_job(status *policy, int pbs_sd, server_info *sinfo, queue_info *qinfo,
		    resource_resv *resresv, std::vector<nspec *> &nspec_arr, unsigned int flags, schd_error *err);

bool
run_update_job(status *policy, int pbs_sd, server_info *sinfo, queue_info *qinfo,
		   resource_resv *rr, unsigned int flags, schd_error *err);

/*
 *	update_job_can_not_run - do post job 'can't run' processing
 *				 mark it 'can_not_run'
 *				 update the job comment and log the reason why
 *				 take care of deleting a 'can_never_run job
 */
int update_job_can_not_run(int pbs_sd, resource_resv *job, schd_error *err);

/*
 *	end_cycle_tasks - stuff which needs to happen at the end of a cycle
 */
void end_cycle_tasks(server_info *sinfo);

/*
 *	add_job_to_calendar - find the most top job and init all the
 *		correct variables in sinfo to correctly backfill around it
 */
int add_job_to_calendar(int pbs_sd, status *policy, server_info *sinfo, resource_resv *topjob, int use_buckets);

/*
 * 	run_job - handle the running of a pbs job.  If it's a peer job
 *	       first move it to the local server and then run it.
 *	       if it's a local job, just run it.
 */
int run_job(int pbs_sd, resource_resv *rjob, char *execvnode, schd_error *err);

/*
 *	should_backfill_with_job - should we call add_job_to_calendar() with job
 *	returns 1: we should backfill 0: we should not
 */
int should_backfill_with_job(status *policy, server_info *sinfo, resource_resv *resresv, int num_topjobs);

/*
 *
 *	update_cycle_status - update global status structure which holds
 *			      status information used by the scheduler which
 *			      can change from cycle to cycle
 *
 *	  policy - status structure to update
 *	  current_time - current time or 0 to call time()
 *
 *	return nothing
 *
 */
void update_cycle_status(status& policy, time_t current_time);


/*
 *
 *	the main scheduler loop
 *			  Loop until njob = next_job() returns NULL
 *			   if njob can run now, run it
 *			   if not, attempt preemption
 *				if successful, run njob
 *			   njob can't run:
 *			     if we can backfill
 *				add job to calendar
 *			     deal with normal job can't run stuff

 */
int main_sched_loop(status *policy, int sd, server_info *sinfo, schd_error **rerr);

/*
 *
 *	scheduler_simulation_task - offline simulation task to calculate
 *		       estimated information for all jobs in the system.
 *
 *	  pbs_sd - connection descriptor to pbs server
 *
 *	return success 1 or error 0
 */
int scheduler_simulation_task(int pbs_sd, int debug);

int set_validate_sched_attrs(int);

int validate_running_user(char *exename);

int send_run_job(int virtual_sd, int has_runjob_hook, const std::string& jobid, char *execvnode);

struct batch_status *send_statsched(int virtual_fd, struct attrl *attrib, char *extend);

#endif	/* _FIFO_H */
