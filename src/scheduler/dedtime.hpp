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

#ifndef	_DEDTIME_H
#define	_DEDTIME_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <time.h>

/*
 *      parse_ded_file - read in dedicated times from file
 *
 *      FORMAT: start - finish
 *              MM/DD/YYYY HH:MM MM/DD/YYYY HH:MM
 */
int parse_ded_file(const char *filename);

/*
 *
 *      cmp_ded_time - compare function for qsort for the ded time array
 *
 */
int cmp_ded_time(const void *v1, const void *v2);

/*
 *      is_ded_time - checks if it is currently dedicated time
 */
int is_ded_time(time_t t);

/*
 *
 *	find_next_dedtime - find the next dedtime.  If t is specified
 *			    find the next dedtime after time t
 *
 *	  t - a time to find the next dedtime after
 *
 *	return the next dedtime or empty timegap if no dedtime
 */
struct timegap find_next_dedtime(time_t t);

#ifdef	__cplusplus
}
#endif
#endif	/* _DEDTIME_H */
