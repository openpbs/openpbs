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


/**
 * @file    dedtime.c
 *
 * @brief
 * 		dedtime.c - This file contains functions related to dedicated time.
 *
 * Functions included are:
 * 	parse_ded_file()
 * 	cmp_ded_time()
 * 	is_ded_time()
 *
 */

#include <algorithm>

#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <memory.h>
#include <errno.h>

#include <log.h>

#include "data_types.h"
#include "misc.h"
#include "dedtime.h"
#include "globals.h"


/**
 * @brief
 *		parse_ded_file - read in dedicated times from file
 *
 * @param[in]	filename	-	filename of dedicated time file
 *
 * @return	0	: on success non-zero on failure
 *
 * @par NOTE:
 * 		modifies conf data structure
 *
 * @note
 *	FORMAT:      start         finish
 *		MM/DD/YY HH:MM MM/DD/YYYY HH:MM
 */
int
parse_ded_file(const char *filename)
{
	FILE *fp;			/* file pointer for the dedtime file */
	char line[256];		/* a buffer for a line from the file */
	int error = 0;		/* boolean: is there an error? */
	struct tm tm_from, tm_to;	/* tm structs used to convert to time_t */
	time_t from, to;		/* time_t values for dedtime start - end */

	if ((fp = fopen(filename, "r")) == NULL) {
		sprintf(log_buffer, "Error opening file %s", filename);
		log_err(errno, "parse_ded_file", log_buffer);
		return 1;
	}

	// We are rereading the dedtime file.  The current dedtime might not exist any more.
	cstat.is_ded_time = false;
	conf.ded_time.clear();

	while (fgets(line, 256, fp) != NULL) {
		if (!skip_line(line)) {
			/* mktime() will figure out if it is dst or not if tm_isdst == -1 */
			memset(&tm_from, 0, sizeof(struct tm));
			tm_from.tm_isdst = -1;

			memset(&tm_to, 0, sizeof(struct tm));
			tm_to.tm_isdst = -1;

			if (sscanf(line, "%d/%d/%d %d:%d %d/%d/%d %d:%d", &tm_from.tm_mon, &tm_from.tm_mday, &tm_from.tm_year, &tm_from.tm_hour, &tm_from.tm_min, &tm_to.tm_mon, &tm_to.tm_mday, &tm_to.tm_year, &tm_to.tm_hour, &tm_to.tm_min) != 10)
				error = 1;
			else {
				/* tm_mon starts at 0, where the file will start at 1 */
				tm_from.tm_mon--;

				/* the MM/DD/YY is the wrong date format, but we will accept it anyways */
				/* if year is less then 90, assume year is > 2000 */
				if (tm_from.tm_year < 90)
					tm_from.tm_year += 100;

				/* MM/DD/YYYY is the correct date format */
				if (tm_from.tm_year > 1900)
					tm_from.tm_year -= 1900;
				from = mktime(&tm_from);

				tm_to.tm_mon--;
				if (tm_from.tm_year < 90)
					tm_from.tm_year += 100;
				if (tm_to.tm_year > 1900)
					tm_to.tm_year -= 1900;
				to = mktime(&tm_to);

				/* ignore all dedtime which has passed */
				if (!(from < cstat.current_time && to < cstat.current_time))
					conf.ded_time.emplace_back(from, to);

				if (from > to) {
					snprintf(log_buffer, LOG_BUF_SIZE-1, "From date is greater than To date in the line - '%s'.", line);
					log_err(-1, "Dedicated Time Conflict", log_buffer);
					error = 1;
				}

			}
			if (error) {
				printf("Error: %s\n", line);
				error = 0;
			}
		}
	}
	/* sort dedtime in ascending order with all 0 elements at the end */
	std::sort(conf.ded_time.begin(), conf.ded_time.end(), cmp_ded_time);
	fclose(fp);
	return 0;
}

/**
 * @brief
 *		cmp_ded_time - compare function for qsort for the ded time array
 *
 * @param[in]	v1	-	value 1
 * @param[in]	v2	-	value 2
 *
 * @par
 *	  Sort Keys:
 *	    - zero elements to the end of the array
 *	    - descending by the start time
 *
 */
bool
cmp_ded_time(const timegap& t1, const timegap& t2)
{
	if (t1.from == 0 && t2.from != 0)
		return 0;
	else if (t2.from == 0 && t1.from != 0)
		return 1;

	return t1.from < t2.from;
}

/**
 * @brief
 * 		checks if it is dedicated time at time t
 *
 * @param[in]	t	-	the time to check
 *
 * @return	bool
 * @retval	true if it is currently ded time
 * @retval	false if it is not ded time
 *
 */
bool
is_ded_time(time_t t)
{
	if (t == 0)
		t = cstat.current_time;

	struct timegap ded = find_next_dedtime(t);

	if (t >= ded.from && t < ded.to)
		return true;
	else
		return false;
}


/**
 * @brief
 * 		find the next dedtime after time t
 *
 * @param[in]	t	-	a time to find the next dedtime after
 *
 * @return	the next dedtime or empty timegap if no dedtime
 */
struct timegap find_next_dedtime(time_t t)
{
	for (const auto& dt : conf.ded_time)
		if (dt.to >= t)
			return dt;

	return {0, 0};
}
