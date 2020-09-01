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

#ifndef	_PRIME_H
#define	_PRIME_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "time.h"

/*
 *	time_left_today - macro - return the time left today
 *			  The macro will calculate the time between x and
 *			  23:59:59 and then add 1 to make it 00:00:00
 */
#define time_left_today(x) ( (23 - ((x) -> tm_hour)) * 3600 + \
			     (59 - ((x) -> tm_min)) * 60 + \
			     (59 - ((x) -> tm_sec)) + 1)

/*
 *      is_prime_time - will return true if it is currently prime_time
 */
enum prime_time is_prime_time(time_t date);

/*
 *      check_prime - check if it is prime time for a particular day
 */
enum prime_time check_prime(enum days d, struct tm *t);

/*
 *      is_holiday - returns true if argument date is a holiday
 */
int is_holiday(long date);

/*
 *      load_day - fill in the prime time part of the config structure
 */
int load_day(enum days d, enum prime_time pr, const char *tok);

/*
 *      parse_holidays - parse the holidays file.  It should be in UNICOS 8
 *                       format.
 */
int parse_holidays(const char *fname);

/*
 *      init_prime_time - do any initializations that need to happen at the
 *                        start of prime time
 */
int init_prime_time(struct status *, char *);


/*
 *      init_non_prime_time - do any initializations that need to happen at
 *                            the beginning of non prime time
 */
int init_non_prime_time(struct status *, char *);

/*
 *
 *	end_prime_status - find the time when the current prime status
 *			   (primetime or nonprimetime) ends.
 *
 *	  date - the time to check (date = time when we start)
 *
 *	NOTE: If prime status doesn't end in start + 7 days, it is considered
 *		infinite
 *
 *	time_t - when the current prime status ends
 *      SCHD_INFINITY - if the current prime status never ends
 *
 */
time_t end_prime_status(time_t date);


#ifdef	__cplusplus
}
#endif
#endif	/* _PRIME_H */
