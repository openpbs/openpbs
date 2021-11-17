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
 * @file	pbs_attach.c
 * @brief
 * pbs_attach - attach a session to a job.
 *
 */
#include <pbs_config.h>

#include "cmds.h"
#include "pbs_version.h"

extern char *getoptargstr;

extern void usage(char *);

extern void attach(int use_cmd, int newsid, int port, int doparent, pid_t pid, char *jobid, char *host, int argc, char *argv[]);

int
main(int argc, char *argv[])
{
	char *jobid = NULL;
	char *host = NULL;
	int c;
	int newsid = 0;
	int port = 0;
	int err = 0;
	int use_cmd = FALSE; /* spawn the process using a new cmd shell */
	extern char *optarg;
	extern int optind;
	pid_t pid = 0;
	char *end;
	int doparent = 0;

	/*test for real deal or just version and exit*/

	PRINT_VERSION_AND_EXIT(argc, argv);

	if (initsocketlib())
		return 1;

	while ((c = getopt(argc, argv, getoptargstr)) != EOF) {
		switch (c) {
			case 'j':
				jobid = optarg;
				break;

			case 'p':
				pid = strtol(optarg, &end, 10);
				if (pid <= 0 || *end != '\0') {
					fprintf(stderr, "bad pid: %s\n", optarg);
					err = 1;
				}
				break;

			case 'P':
				doparent = 1;
				break;

			case 'h':
				host = optarg;
				break;

			case 'c':
				use_cmd = TRUE;
				break;

			case 'm':
				port = strtol(optarg, &end, 10);
				if (port <= 0 || *end != '\0') {
					fprintf(stderr, "bad port: %s\n", optarg);
					err = 1;
				}
				break;

			case 's':
				newsid = 1;
				break;

			default:
				err = 1;
				break;
		}
	}

	if (pid != 0) {
		if (newsid) {
			fprintf(stderr, "cannot specify pid and session\n");
			err = 1;
		}
		if (doparent) {
			fprintf(stderr, "cannot specify pid and parent\n");
			err = 1;
		}
		if (optind < argc) {
			fprintf(stderr, "cannot specify pid and command\n");
			err = 1;
		}
	} else if (optind == argc) {
		fprintf(stderr, "must specify pid or command\n");
		err = 1;
	}

	if (err)
		usage(argv[0]);

	if (port == 0) {
		pbs_loadconf(0);
		port = pbs_conf.manager_service_port;
	}

	attach(use_cmd, newsid, port, doparent, pid, jobid, host, argc, argv);

	return 0;
}
