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
 * @file
 *		pbs_sleep.c
 *
 * @brief
 *		This file contains functions related to sleep of PBS.
 *
 * Functions included are:
 * 	main()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <signal.h>

/**
 * @Brief
 *      This is main function of pbs_sleep process.
 *      It calls sleep internally for the number of seconds passed to it, -1 for sleep indefinitely.
 *
 */


int
main(int argc, char *argv[])
{
	int i;
	int forever = 0;
	int secs = 0;

	if (argc != 2) {
		fprintf(stderr, "%s secs\n", argv[0]);
		exit(1);
	}


	/* if argv[1] is -1, loop with sleep 1 indefinitely */
	if (strcmp(argv[1], "-1") == 0)
		forever = 1;
	else
		secs = atoi(argv[1]);

	for (i = 0; i < secs || forever; i++)
		sleep(1);

	return 0;

}
