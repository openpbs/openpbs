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
 * @file	chk_Jrange.c
 *
 * @brief
 * 	chk_Jrange - validate the subjob index range for the J option to qsub/qalter
 */
#include <pbs_config.h>
#include <ctype.h>
#include <limits.h>
#include <stdlib.h>
#include "pbs_ifl.h"
#include "pbs_internal.h"

/**
 * @brief
 * 	chk_Jrange - validate the subjob index range for the J option to qsub/qalter
 *
 * @param[in] arg - argument list
 *
 * @return	int
 * @retval	0 if ok,
 * @retval	1 if invalid form
 * @retval	2 if any of the individual numbers is too large
 */
int
chk_Jrange(char *arg)
{
	char *pc;
	char *s;
	long start;
	long end;
	long step;

	pc = arg;
	if (!isdigit((int) *pc))
		return (1); /* no a positive number */
	s = arg;
	while (*pc && isdigit((int) *pc))
		++pc;
	if (*pc != '-') {
		return (1);
	}
	start = strtol(s, NULL, 10);
	if (start < 0)
		return 1;
	if (start == LONG_MAX)
		return 2;
	s = ++pc;
	if (!isdigit((int) *pc)) {
		return (1);
	}
	while (*pc && isdigit((int) *pc))
		++pc;
	if ((*pc != '\0') && (*pc != ':')) {
		return (1);
	}
	end = strtol(s, NULL, 10);
	if (start >= end)
		return 1;
	if (end == LONG_MAX)
		return 2;

	if (*pc++ == ':') {
		s = pc;
		while (*pc && isdigit((int) *pc))
			++pc;
		if (*pc != '\0') {
			return (1);
		}
		step = strtol(s, NULL, 10);
		if (step < 1)
			return (1);
		if (step == LONG_MAX)
			return (2);
	}
	return 0;
}
