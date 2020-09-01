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
 * @file    prime.c
 *
 * @brief
 * 		prime.c -  contains functions which are related to prime time.
 *
 * Functions included are:
 * 	is_prime_time()
 * 	check_prime()
 * 	is_holiday()
 * 	parse_holidays()
 * 	load_day()
 * 	end_prime_status_rec()
 * 	end_prime_status()
 * 	init_prime_time()
 * 	init_non_prime_time()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>

#include <pbs_ifl.h>
#include <log.h>

#include "constant.hpp"
#include "globals.hpp"
#include "prime.hpp"
#include "misc.hpp"


/**
 * @brief
 * 		return the status of primetime
 *
 * @param[in]	date	-	the date to check if its primetime
 *
 * @return	int
 * @retval 	PRIME	: if prime time
 * @retval	NON_PRIME	: if non_prime
 *
 * @par NOTE: Holidays are considered non-prime
 *
 */
enum prime_time is_prime_time(time_t date)
{
	enum prime_time ret = PRIME;		/* return code */
	struct tm  *tmptr;			/* current time in a struct tm */

	tmptr = localtime(&date);

	/* check for holiday: Holiday == non_prime */
	if (conf.holiday_year != 0) { /* year == 0: no prime-time */

		/* tm_yday starts at 0, and Julian date starts at 1 */
		if (is_holiday(tmptr->tm_yday + 1))
			ret = NON_PRIME;

		/* is_holiday() calls localtime() which returns a static ptr.  Our tmptr
		 * now no longer points to what we think it points to
		 */
		tmptr = localtime(&date);

		/* if ret still equals PRIME then it is not a holiday, we need to check
		 * and see if we are in non-prime or prime
		 */
		if (ret == PRIME) {
			if (tmptr->tm_wday == 0)
				ret = check_prime(SUNDAY, tmptr);
			else if (tmptr->tm_wday == 1)
				ret = check_prime(MONDAY, tmptr);
			else if (tmptr->tm_wday == 2)
				ret = check_prime(TUESDAY, tmptr);
			else if (tmptr->tm_wday == 3)
				ret = check_prime(WEDNESDAY, tmptr);
			else if (tmptr->tm_wday == 4)
				ret = check_prime(THURSDAY, tmptr);
			else if (tmptr->tm_wday == 5)
				ret = check_prime(FRIDAY, tmptr);
			else if (tmptr->tm_wday == 6)
				ret = check_prime(SATURDAY, tmptr);
			else
				ret = check_prime(WEEKDAY, tmptr);
		}
	}

	return ret;
}

/**
 * @brief
 *		check_prime - check if it is prime time for a particular day
 *
 * @param[in]	d	-	days
 * @param[in]	t	-	time represented as tm structure.
 *
 * @return	PRIME if it is in primetime
 * @retval	NON_PRIME	: if not
 */
enum prime_time check_prime(enum days d, struct tm *t)
{
	enum prime_time prime = NON_PRIME;		/* return code */

	/* Nonprime, prime, and current Times are transformed into military time for easier comparison */
	int npt = conf.prime[d][NON_PRIME].hour*100+conf.prime[d][NON_PRIME].min;
	int pt = conf.prime[d][PRIME].hour*100+conf.prime[d][PRIME].min;
	int ct = (t->tm_hour)*100+(t->tm_min);

	/* Case 1: all primetime today */
	if (conf.prime[d][PRIME].all)
		prime = PRIME;

	/* case 2: all nonprime time today */
	else if (conf.prime[d][NON_PRIME].all)
		prime = NON_PRIME;

	/* case 3: no primetime today */
	else if (conf.prime[d][PRIME].none)
		prime = NON_PRIME;

	/* case 4: no nonprime time today */
	else if (conf.prime[d][NON_PRIME].none)
		prime = PRIME;
	/* There are two more cases to handle, if we represent the 24 hours day as:
	 *          0000 ------------------------2400
	 * case 5 is when PRIME starts before NON_PRIME
	 *          0000 -------P----NP----------2400
	 * in which case the current time is PRIME only between P and NP
	 */
	else if (npt > pt) {
		if (pt <= ct && ct < npt)
			prime = PRIME;
		else prime = NON_PRIME;
	}
	/*  case 6 is when NON_PRIME starts before PRIME
	 *          0000 -------NP----P----------2400
	 *  in which case the current time is NONPRIME only between NP and P
	 *  This case also captures the setting of identical Prime and Nonprime times in the "holidays" file
	 */
	else if (npt <= pt) {
		if (npt <= ct && ct < pt)
			prime = NON_PRIME;
		else prime = PRIME;
	}
	/* Catchall case is NON_PRIME */
	else
		prime = NON_PRIME;

	return prime;
}

/**
 * @brief
 *		is_holiday - returns true if 'date' is a holiday
 *
 * @param[in]	date	-	amount of days since the beginning of the year
 *							starting with Jan 1 == 1 or a time_t.
 *
 * @return	TRUE/FALSE
 * @retval	TRUE	: if today is a holiday
 * @retval	FALSE	: if not
 *
 */
int
is_holiday(long date)
{
	int i;
	int jdate;
	struct tm *tmptr;

	if (date > 366) {
		tmptr = localtime((time_t *) &date);
		jdate = tmptr->tm_yday + 1;
	}
	else
		jdate = date;


	for (i = 0; i < conf.num_holidays && conf.holidays[i] != jdate; i++)
		;

	if (i == conf.num_holidays)
		return 0;

	return 1;
}

/**
 * @brief	Set conf.prime values to reflect "ALL PRIME" before we start parsing
 * 			the holidays file
 *
 * @param	void
 *
 * @return void
 */
static void
handle_missing_prime_info(void)
{
	//enum days d;
	int d;

	for (d = SUNDAY; d < HIGH_DAY; d++) {
		if (conf.prime[d][PRIME].all + conf.prime[d][PRIME].none
				+ conf.prime[d][PRIME].hour + conf.prime[d][PRIME].min == 0) {
			conf.prime[d][PRIME].all = TRUE;
			conf.prime[d][PRIME].none = FALSE;
			conf.prime[d][PRIME].hour = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][PRIME].min = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][NON_PRIME].none = TRUE;
			conf.prime[d][NON_PRIME].all = FALSE;
			conf.prime[d][NON_PRIME].hour = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][NON_PRIME].min = static_cast<unsigned int>(UNSPECIFIED);
		}
	}
}

/**
 * @brief
 *		parse_holidays - parse the holidays file.  It should be in UNICOS 8
 *			 format.
 *
 * @param[in]	fname	-	name of holidays file
 *
 * @return	success/failure
 *
 */
int
parse_holidays(const char *fname)
{
	FILE *fp;		/* file pointer to holidays file */
	char buf[256];	/* buffer to read lines of the file into */
	char *config_name;	/* the first word of the line */
	char *tok;		/* used with strtok() to parse the rest of the line */
	char *endp;		/* used with strtol() */
	int num;		/* used to convert string -> integer */
	char error = 0;	/* boolean: is there an error ? */
	int linenum = 0;	/* the current line number */
	int hol_index = 0;	/* index into the holidays array in global var conf */

	if ((fp = fopen(fname, "r")) == NULL) {
		sprintf(log_buffer, "Error opening file %s", fname);
		log_err(errno, "parse_holidays", log_buffer);
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, HOLIDAYS_FILE,
			"Warning: cannot open holidays file; assuming 24hr primetime");
		return 0;
	}

	while (fgets(buf, 256, fp) != NULL) {
		linenum++;
		if (buf[strlen(buf)-1] == '\n')
			buf[strlen(buf)-1] = '\0';
		if (!skip_line(buf)) {
			config_name = strtok(buf, "	 ");

			/* this tells us if we have the correct file format.  Its ignored since
			 * lots of error messages will be printed if the file format is wrong
			 * and if the file format is correct but just not this, we really
			 * shouldn't complain
			 */
			if (!strcmp(config_name, "HOLIDAYFILE_VERSION1"))
				;
			/* the current year - if the file is old, we want to know to log errors
			 * later about it
			 *
			 * FORMAT EXAMPLE
			 *
			 * YEAR 1998
			 */
			else if (!strcmp(config_name, "YEAR")) {
				tok = strtok(NULL, " 	");
				if (tok == NULL)
					error = 1;
				else {
					num = strtol(tok, &endp, 10);
					if (*endp != '\0')
						error = 1;
					else
						conf.holiday_year = num;
				}
			}
			/* primetime hours for saturday
			 * first number is primetime start, second is nonprime start
			 *
			 * FORMAT EXAMPLE
			 *
			 *  saturday 	0400	1700
			 */
			else if (!strcmp(config_name, "saturday")) {
				tok = strtok(NULL, " 	");
				if (load_day(SATURDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(SATURDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime hours for sunday  - same format as saturday */
			else if (!strcmp(config_name, "sunday")) {
				tok = strtok(NULL, " 	");
				if (load_day(SUNDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(SUNDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for weekday - same format as saturday */
			else if (!strcmp(config_name, "weekday")) {
				tok = strtok(NULL, " 	");
				if (load_day(WEEKDAY, PRIME, tok) < 0)
					error = 1;
				else if (load_day(MONDAY, PRIME, tok) < 0)
					error = 1;
				else if (load_day(TUESDAY, PRIME, tok) < 0)
					error = 1;
				else if (load_day(WEDNESDAY, PRIME, tok) < 0)
					error = 1;
				else if (load_day(THURSDAY, PRIME, tok) < 0)
					error = 1;
				else if (load_day(FRIDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(WEEKDAY, NON_PRIME, tok) < 0)
						error = 1;
					else if (load_day(MONDAY, NON_PRIME, tok) < 0)
						error = 1;
					else if (load_day(TUESDAY, NON_PRIME, tok) < 0)
						error = 1;
					else if (load_day(WEDNESDAY, NON_PRIME, tok) < 0)
						error = 1;
					else if (load_day(THURSDAY, NON_PRIME, tok) < 0)
						error = 1;
					else  if (load_day(FRIDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for monday - same format as saturday */
			else if (!strcmp(config_name, "monday")) {
				tok = strtok(NULL, " 	");
				if (load_day(MONDAY, PRIME, tok) < 0)
					error = 1;
				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(MONDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for tuesday - same format as saturday */
			else if (!strcmp(config_name, "tuesday")) {
				tok = strtok(NULL, " 	");
				if (load_day(TUESDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(TUESDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for wednesday - same format as saturday */
			else if (!strcmp(config_name, "wednesday")) {
				tok = strtok(NULL, " 	");
				if (load_day(WEDNESDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(WEDNESDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for thursday - same format as saturday */
			else if (!strcmp(config_name, "thursday")) {
				tok = strtok(NULL, " 	");
				if (load_day(THURSDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(THURSDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/* primetime for friday - same format as saturday */
			else if (!strcmp(config_name, "friday")) {
				tok = strtok(NULL, " 	");
				if (load_day(FRIDAY, PRIME, tok) < 0)
					error = 1;

				if (!error) {
					tok = strtok(NULL, " 	");
					if (load_day(FRIDAY, NON_PRIME, tok) < 0)
						error = 1;
				}
			}
			/*
			 * holidays
			 * We only care about the Julian date of the holiday.  It is enough
			 * information to find out if it is a holiday or not
			 *
			 * FORMAT EXAMPLE
			 *
			 *  Julian date	Calendar date	holiday name
			 *    1		Jan 1		New Year's Day
			 */
			else  {
				num = strtol(config_name, &endp, 10);
				conf.holidays[hol_index] = num;
				hol_index++;
			}

			if (error) {
				log_eventf(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, fname,
					"Error on line %d, line started with: %s", linenum, config_name);
			}

		}
		error = 0;
	}

	if (conf.holiday_year != 0) {
		/* Let's make sure that any missing days get marked as 24hr prime-time */
		handle_missing_prime_info();
	}

	conf.num_holidays = hol_index;
	fclose(fp);
	return 0;
}


/**
 * @brief
 *		load_day - fill in the prime time part of the config structure
 *
 * @param[in]	d	-	enum days: can be WEEKDAY, SATURDAY, or SUNDAY
 * @param[in]	pr 	-	enum prime_time: can be PRIME or NON_PRIME
 * @param[in]	tok	-	token
 *
 * @return	int
 * @retval	0	: on success
 * @retval	-1	: on error
 *
 */
int
load_day(enum days d, enum prime_time pr, const char *tok)
{
	int num;		/* used to convert string -> integer */
	int hours;		/* used to convert 4 digit HHMM into hours */
	int mins;		/* used to convert 4 digit HHMM into minutes */
	char *endp;		/* used wtih strtol() */

	if (tok != NULL) {
		if (!strcmp(tok, "all") || !strcmp(tok, "ALL")) {
			if (pr == NON_PRIME && conf.prime[d][PRIME].all == TRUE) {
				log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, HOLIDAYS_FILE,
						"Warning: both prime & non-prime starts are 'all'; assuming 24hr primetime");
				return 0;
			}
			conf.prime[d][pr].all = TRUE;
			conf.prime[d][pr].hour = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][pr].min = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][pr].none = FALSE;
		} else if (!strcmp(tok, "none") || !strcmp(tok, "NONE")) {
			if (pr == NON_PRIME && conf.prime[d][PRIME].none == TRUE) {
				log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, HOLIDAYS_FILE,
						"Warning: both prime & non-prime starts are 'none'; assuming 24hr primetime");
				return load_day(d, PRIME, "all");
			}
			conf.prime[d][pr].all = FALSE;
			conf.prime[d][pr].hour = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][pr].min = static_cast<unsigned int>(UNSPECIFIED);
			conf.prime[d][pr].none = TRUE;
		} else {
			num = strtol(tok, &endp, 10);
			if (*endp == '\0') {
				/* num is a 4 digit number of the time HHMM */
				mins = num % 100;
				hours = num / 100;
				conf.prime[d][pr].hour = hours;
				conf.prime[d][pr].min = mins;
			}
			else
				return -1;
		}
	}
	else
		return -1;
	return 0;
}


/**
 * @brief
 * 		recursive helper for end_prime_status
 *
 * @param[in]	start	-	the time the function starts
 * @param[in]	date	-	the time to check (date = time when we start)
 * @param[in]	prime_status	-	current prime status PRIME, NON_PRIME, or
 *									NONE to have the function calcuate the prime status at date
 *
 * @retval	time_t	-	when the current prime status ends
 * @retval	SCHD_INFINITY	-	if the current prime status never ends
 */
static time_t
end_prime_status_rec(time_t start, time_t date,
	enum prime_time prime_status)
{
	struct tm *tmptr;
	enum days day;

	/* base case: if we're more then 7 days out the current prime status will
	 * never end.  We know this because the only prime settings are weekly.
	 */
	if (date > start + (7 * 24 * 60 * 60))
		return (time_t) SCHD_INFINITY;

	tmptr = localtime(&date);

	switch (tmptr->tm_wday) {
		case 0:
			day = SUNDAY;
			break;
		case 1:
			day = MONDAY;
			break;
		case 2:
			day = TUESDAY;
			break;
		case 3:
			day = WEDNESDAY;
			break;
		case 4:
			day = THURSDAY;
			break;
		case 5:
			day = FRIDAY;
			break;
		case 6:
			day = SATURDAY;
			break;
		default:
			day = WEEKDAY;
	}

	if (prime_status == PRIME) {
		/* We are currently in primetime. */
		/* If there is no non-primetime scheduled today, recurse into tomorrow. */
		if (conf.prime[day][NON_PRIME].none)
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		/* If there is no non-primetime left today, recurse into tomorrow. */
		if (conf.prime[day][NON_PRIME].hour < static_cast<unsigned int>(tmptr->tm_hour))
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		if (conf.prime[day][NON_PRIME].hour == static_cast<unsigned int>(tmptr->tm_hour) &&
			conf.prime[day][NON_PRIME].min < static_cast<unsigned int>(tmptr->tm_min))
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		/* Non-primetime started at the beginning of the day, return it. */
		if (conf.prime[day][NON_PRIME].all || is_holiday(tmptr->tm_yday + 1))
			return date;
		/* Non-primetime will start later today, return the scheduled time. */
		return date + (conf.prime[day][NON_PRIME].hour - tmptr->tm_hour) * 3600
		+ (conf.prime[day][NON_PRIME].min - tmptr->tm_min) * 60
		- tmptr->tm_sec;
	}
	else {
		/* We are currently in non-primetime. */
		/* If there is no primetime scheduled today, recurse into tomorrow. */
		if (conf.prime[day][PRIME].none || is_holiday(tmptr->tm_yday + 1))
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		/* If there is no primetime left today, recurse into tomorrow. */
		if (conf.prime[day][PRIME].hour < static_cast<unsigned int>(tmptr->tm_hour))
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		if (conf.prime[day][PRIME].hour == static_cast<unsigned int>(tmptr->tm_hour) &&
			conf.prime[day][PRIME].min < static_cast<unsigned int>(tmptr->tm_min))
			return end_prime_status_rec(start, date + time_left_today(tmptr),
				prime_status);
		/* Primetime started at the beginning of the day, return it. */
		if (conf.prime[day][PRIME].all)
			return date;
		/* Primetime will start later today, return the scheduled time. */
		return date + (conf.prime[day][PRIME].hour - tmptr->tm_hour) * 3600
		+ (conf.prime[day][PRIME].min - tmptr->tm_min) * 60
		- tmptr->tm_sec;
	}
}

/**
 * @brief
 * 		find the time when the current prime status
 *		   (primetime or nonprimetime) ends.
 *
 * @param[in]	date	-	the time to check (date = time when we start)
 *
 * @par NOTE:	If prime status doesn't end in start + 7 days,
 *				it is considered infinite
 *
 * @return time when the current prime status ends.
 * @retval	time_t	: when the current prime status ends
 * @retval	SCHD_INFINITY	: if  the current prime status never ends
 *
 */
time_t
end_prime_status(time_t date)
{
	enum prime_time p;

	p = is_prime_time(date);

	/* no year means all prime all the time*/
	if (p == PRIME && conf.holiday_year == 0)
		return SCHD_INFINITY;

	return end_prime_status_rec(date, date, p);
}

/**
 * @brief
 * 		do any initializations that need to happen at the
 *			  start of prime time
 *
 * @param[in]	policy	-	policy info
 *
 * @return	int
 * @retval	1	: success
 * @retval	0	: error
 *
 */
int
init_prime_time(struct status *policy, char *arg)
{
	if (policy == NULL)
		return 0;

	policy->is_prime = PRIME;
	policy->round_robin = conf.prime_rr;
	policy->by_queue = conf.prime_bq;
	policy->strict_fifo = conf.prime_sf;
	policy->strict_ordering = conf.prime_so;
	policy->sort_by = conf.prime_sort;
	policy->fair_share = conf.prime_fs;
	policy->help_starving_jobs = conf.prime_hsv;
	policy->backfill = conf.prime_bf;
	policy->sort_nodes = conf.prime_sn;
	policy->backfill_prime = conf.prime_bp;
	policy->preempting = conf.prime_pre;
	policy->node_sort = conf.prime_node_sort;
#ifdef NAS /* localmod 034 */
	policy->shares_track_only = conf.prime_sto;
#endif /* localmod 034 */

	/* we want to know how much we can spill over INTO nonprime time */
	policy->prime_spill = conf.nonprime_spill;
	policy->smp_dist = conf.prime_smp_dist;

	/* policy -> prime_status_end is initially set by the scheduler's first
	 * call to update_cycle_status() at the beginning of the cycle
	 */
	policy->prime_status_end = end_prime_status(policy->prime_status_end);

	return 1;
}

/**
 * @brief
 * 		do any initializations that need to happen at
 *			      the beginning of non prime time
 *
 * @param[in]	policy	-	policy info
 *
 * @return	int
 * @retval	1	: success
 * @retval	0 	: error
 *
 */
int
init_non_prime_time(struct status *policy, char *arg)
{
	if (policy == NULL)
		return 0;

	policy->is_prime = NON_PRIME;
	policy->round_robin = conf.non_prime_rr;
	policy->by_queue = conf.non_prime_bq;
	policy->strict_fifo = conf.non_prime_sf;
	policy->strict_ordering = conf.non_prime_so;
	policy->sort_by = conf.non_prime_sort;
	policy->fair_share = conf.non_prime_fs;
	policy->help_starving_jobs = conf.non_prime_hsv;
	policy->backfill = conf.non_prime_bf;
	policy->sort_nodes = conf.non_prime_sn;
	policy->backfill_prime = conf.non_prime_bp;
	policy->preempting = conf.non_prime_pre;
	policy->node_sort = conf.non_prime_node_sort;
#ifdef NAS /* localmod 034 */
	policy->shares_track_only = conf.non_prime_sto;
#endif /* localmod 034 */

	/* we want to know how much we can spill over INTO primetime */
	policy->prime_spill = conf.prime_spill;
	policy->smp_dist = conf.non_prime_smp_dist;

	/* policy -> prime_status_end is initially set by the scheduler's first
	 * call to update_cycle_status() at the beginning of the cycle
	 */
	policy->prime_status_end = end_prime_status(policy->prime_status_end);

	return 1;
}
