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
 * @file    pbskill_win.c
 *
 * @brief
 * 		pbskill_win.c - Functions related to kill pbs on Windows.
 *
 * Functions included are:
 * 	killproc()
 * 	main()
 */
#include <pbs_config.h>   /* the master config generated by configure */

#include <stdio.h>
#include <stdlib.h>
#include <win.h>
/**
 * @brief
 * 		killproc - kill the process having that pid.
 *
 * @param[in]	pid	-	process id o be killed
 */
void
killproc(DWORD pid)
{
	HANDLE	ph;

	if ((ph=OpenProcess(PROCESS_TERMINATE, TRUE, pid)) == NULL) {
		printf("Can't open pid=%d, error=%d\n", pid, GetLastError());
		return;
	}
	if (processtree_op_by_handle(ph, TERMINATE, 1) == -1) {
		printf("Can't terminate pid=%d, error=%d\n", pid,
			GetLastError());
	} else {
		printf("pid=%d killed\n", pid);
	}
	CloseHandle(ph);
}
/**
 * @brief
 * 		main - the entry point in hostn.c
 *
 * @param[in]	argc	-	argument count.
 * @param[in]	argv	-	argument variables.
 * @param[in]	env	-	environment values.
 *
 * @return	int
 * @retval	1	: argument count is one
 */
int
main(int argc, char *argv[], char *env[])
{
	int i;

	ena_privilege(SE_DEBUG_NAME);

	if (argc == 1) {
		fprintf(stderr, "%s proc-id1 [proc-id2 [proc-id3] ...]\n",
			argv[0]);
		exit(1);
	}

	for (i=1; i < argc; i++) {
		killproc(atoi(argv[i]));
	}
}