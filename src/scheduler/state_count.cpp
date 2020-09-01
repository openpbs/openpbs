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


/**
 * @file    state_count.c
 *
 * @brief
 * 		state_count.c - This file contains functions related to state_count struct
 *
 * Functions included are:
 * 	init_state_count()
 * 	count_states()
 * 	total_states()
 * 	state_count_add()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pbs_error.h>
#include <pbs_ifl.h>
#include <log.h>
#include "state_count.hpp"
#include "constant.hpp"
#include "misc.hpp"

/**
 * @brief
 *		init_state_count - initalize state count struct
 *
 * @param[out]	sc - the struct to initalize
 *
 * @return	nothing
 *
 */
void
init_state_count(state_count *sc)
{
	sc->running = 0;
	sc->queued = 0;
	sc->transit = 0;
	sc->exiting = 0;
	sc->held = 0;
	sc->waiting = 0;
	sc->suspended = 0;
	sc->userbusy = 0;
	sc->invalid = 0;
	sc->begin = 0;
	sc->expired = 0;
	sc->total = 0;
}

/**
 * @brief
 *		count_states - count the jobs in each state and set the state counts
 *
 * @param[in]	jobs - array of jobs
 * @param[out]	sc   - state count structure passed by reference
 *
 * @return	nothing
 *
 */
void
count_states(resource_resv **jobs, state_count *sc)
{
	int i;

	if (jobs != NULL) {
		for (i = 0; jobs[i] != NULL; i++) {
			if (jobs[i]->job != NULL) {
				if (jobs[i]->job->is_queued)
					sc->queued++;
				else if (jobs[i]->job->is_running)
					sc->running++;
				else if (jobs[i]->job->is_transit)
					sc->transit++;
				else if (jobs[i]->job->is_exiting)
					sc->exiting++;
				else if (jobs[i]->job->is_held)
					sc->held++;
				else if (jobs[i]->job->is_waiting)
					sc->waiting++;
				else if (jobs[i]->job->is_suspended)
					sc->suspended++;
				else if (jobs[i]->job->is_userbusy)
					sc->userbusy++;
				else if (jobs[i]->job->is_begin)
					sc->begin++;
				else if (jobs[i]->job->is_expired)
					sc->expired++;
				else {
					sc->invalid++;
					log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO, jobs[i]->name, "Job in unknown state");
				}
			}
		}
	}

	sc->total = sc->queued + sc->running + sc->transit +
		sc->exiting + sc->held + sc->waiting +
		sc->suspended + sc->userbusy + sc->begin +
		sc->expired + sc->invalid;

}

/**
 * @brief
 *		total_states - add the states from sc2 to the states in sc1
 *		       i.e. sc1 += sc2
 *
 * @param[out]	sc1 - the accumlator
 * @param[in]	sc2 - what is being totaled
 *
 * @return	nothing
 *
 */
void
total_states(state_count *sc1, state_count *sc2)
{
	sc1->running += sc2->running;
	sc1->queued += sc2->queued;
	sc1->held += sc2->held;
	sc1->waiting += sc2->waiting;
	sc1->exiting += sc2->exiting;
	sc1->transit += sc2->transit;
	sc1->suspended += sc2->suspended;
	sc1->userbusy += sc2->userbusy;
	sc1->begin += sc2->begin;
	sc1->expired += sc2->expired;
	sc1->invalid += sc2->invalid;
	sc1->total += sc2->total;
}

/**
 * @brief
 *		state_count_add - add a certain amount to a a state count element
 *			  based on a job state letter
 *
 * @param[out]	sc	 		- state count
 * @param[in]	job_state 	- state to decrement
 * @param[in]	amount 		- amount to add (it increment, pass 1, to decrement pass -1)
 *
 *
 * @return	nothing
 *
 */
void
state_count_add(state_count *sc, const char *job_state, int amount)
{
	if (sc == NULL || job_state == NULL)
		return;

	switch (job_state[0]) {
		case 'Q':
			sc->queued += amount;
			break;

		case 'R':
			sc->running += amount;
			break;

		case 'T':
			sc->transit += amount;
			break;

		case 'H':
			sc->held += amount;
			break;

		case 'W':
			sc->waiting += amount;
			break;

		case 'E':
			sc->exiting += amount;
			break;

		case 'S':
			sc->suspended += amount;
			break;

		case 'U':
			sc->userbusy += amount;
			break;

		case 'B':
			sc->begin += amount;
			break;

		case 'X':
			sc->expired += amount;
			break;

		default:
			sc->invalid += amount;
			break;
	}
}
