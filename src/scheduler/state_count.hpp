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

#ifndef	_STATE_COUNT_H
#define	_STATE_COUNT_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.hpp"

/*
 *	init_state_count - initalize state count struct
 */
void init_state_count(state_count *sc);

/*
 *      count_states - count the jobs in each state and set the state counts
 */
void count_states(resource_resv **jobs, state_count *sc);

/*
 *	accumulate states from one state_count into another
 */
void total_states(state_count *sc1, state_count *sc2);

/*
 *      state_count_add - add a certain amount to a a state count element
 *                        based on a job state letter
 *                        it increment, pass in 1, to decrement pass in -1
 */
void state_count_add(state_count *sc, const char *job_state, int amount);
#ifdef	__cplusplus
}
#endif
#endif	/* _STATE_COUNT_H */
