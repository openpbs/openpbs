/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */

/**
 * @file
 *		pbs_mkdirs_win.c
 *
 * @brief
 *		This file contains functions related to creating directories on Windows.
 *
 * Functions included are:
 * 	main()
 *
 */
#include <pbs_config.h>
#include <stdio.h>
#include <pbs_ifl.h>
#include <sys/stat.h>
#include <windows.h>
#include "win.h"
#include "pbs_internal.h"
#include "log.h"

enum action_mode {
	All,
	Server,
	Mom,
	Sched
};
/**
 * @Brief
 *      This is main function of pbs_mkdirs_win process.
 *
 * @return	int
 *
 * @retval	0	: On Success
 * @retval	!=0	: failure
 *
 */
main(int argc, char *argv[])
{
	char	*conf_filename = NULL;
	char	pbs_dest[MAX_PATH+1] = {'\0'};
	char	*p = NULL;
	char	psave = '\0';
	enum	action_mode mode = All;
	extern char *pbs_conf_env;

	if(set_msgdaemonname("pbs_mkdirs")) {
		fprintf(stderr, "Out of memory\n");
		return 1;
	}
	if (argc > 3) {
		fprintf(stderr, "%s [all|server|mom|sched] [pbs_conf_env]", argv[0]);
		exit(1);
	}

	if (argc > 1) {
		if (strcmp(argv[1], "server") == 0)
			mode = Server;
		else if (strcmp(argv[1], "mom") == 0)
			mode = Mom;
		else if (strcmp(argv[1], "sched") == 0)
			mode = Sched;
		else if (strcmp(argv[1], "all") == 0)
			mode = All;
		else {
			fprintf(stderr, "%s [all|server|mom|sched] [pbs_conf_env]", argv[0]);
			exit(2);
		}
	}

	if (argc > 2) {
		pbs_conf_env = (char*) malloc(strlen(argv[2]) + 1);
		strncpy(pbs_conf_env, argv[2], strlen(argv[2]));
	}

	if (pbs_conf_env == NULL) {
		if ((conf_filename = getenv("PBS_CONF_FILE")) == NULL)
			conf_filename = PBS_CONF_FILE;
	} else {
		if ((conf_filename = getenv(pbs_conf_env)) == NULL)
			conf_filename = PBS_CONF_FILE;
	}

	if (pbs_loadconf(0) == 0) {
		printf("Unable to decipher %s\n", conf_filename);
		exit(1);
	}

	if ((p=strrchr(pbs_conf.pbs_conf_file, '/')) ||
		(p=strrchr(pbs_conf.pbs_conf_file, '\\'))) {
		psave = *p;
		*p = '\0';
		strcpy(pbs_dest, pbs_conf.pbs_conf_file);
		*p = psave;
	}

	secure_file2(pbs_dest,
		"Administrators", READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED,
		"\\Everyone", READS_MASK | READ_CONTROL);
	printf("securing %s for read access by Everyone\n", pbs_dest);

	secure_file2(pbs_conf.pbs_conf_file,
		"Administrators", READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED,
		"\\Everyone", READS_MASK | READ_CONTROL);
	printf("securing %s for read access by Everyone\n",
		pbs_conf.pbs_conf_file);

	secure_file2(pbs_conf.pbs_exec_path,
		"Administrators", READS_MASK|WRITES_MASK|STANDARD_RIGHTS_REQUIRED,
		"\\Everyone", READS_MASK | READ_CONTROL);
	printf("securing %s for read access by Everyone\n",
		pbs_conf.pbs_exec_path);

	secure_misc_files();

	if (mode == All) {
		secure_exec_files();
	}

	if ((mode == All) || (mode == Server)) {
		secure_server_files();
	}

	if ((mode == All) || (mode == Mom)) {
		secure_mom_files();
		secure_rshd_files();
	}

	if ((mode == All) || (mode == Sched)) {
		secure_sched_files();
	}

	return 0;
}
