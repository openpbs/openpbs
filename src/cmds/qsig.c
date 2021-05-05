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
 * @file	qsig.c
 * @brief
 * 	qsig - (PBS) signal a batch job
 *
 * @author	    Terry Heidelberg
 * 				Livermore Computing
 *
 * @author      Bruce Kelly
 * 				National Energy Research Supercomputer Center
 *
 * @author     	Lawrence Livermore National Laboratory
 * 				University of California
 */

#include "cmds.h"
#include "pbs_ifl.h"
#include <pbs_config.h>   /* the master config generated by configure */
#include <pbs_version.h>


int
main(int argc, char **argv, char **envp) /* qsig */
{
	int c;
	int errflg=0;
	int any_failed=0;

	char job_id[PBS_MAXCLTJOBID];       /* from the command line */

	char job_id_out[PBS_MAXCLTJOBID];
	char server_out[MAXSERVERNAME];
	char rmt_server[MAXSERVERNAME];

#define MAX_SIGNAL_TYPE_LEN 32
	static char sig_string[MAX_SIGNAL_TYPE_LEN+1] = "SIGTERM";

#define GETOPT_ARGS "s:"

	/*test for real deal or just version and exit*/

	PRINT_VERSION_AND_EXIT(argc, argv);

	if (initsocketlib())
		return 1;

	while ((c = getopt(argc, argv, GETOPT_ARGS)) != EOF)
		switch (c) {
			case 's':
				pbs_strncpy(sig_string, optarg, sizeof(sig_string));
				break;
			default :
				errflg++;
		}

	if (errflg || optind >= argc) {
		static char usage[]="usage: qsig [-s signal] job_identifier...\n";
		static char usag2[]="       qsig --version\n";
		fprintf(stderr, "%s", usage);
		fprintf(stderr, "%s", usag2);
		exit(2);
	}

	/*perform needed security library initializations (including none)*/

	if (CS_client_init() != CS_SUCCESS) {
		fprintf(stderr, "qsig: unable to initialize security library.\n");
		exit(2);
	}

	for (; optind < argc; optind++) {
		int connect;
		int stat=0;
		int located = FALSE;

		pbs_strncpy(job_id, argv[optind], sizeof(job_id));
		if (get_server(job_id, job_id_out, server_out)) {
			fprintf(stderr, "qsig: illegally formed job identifier: %s\n", job_id);
			any_failed = 1;
			continue;
		}
cnt:
		connect = cnt2server(server_out);
		if (connect <= 0) {
			fprintf(stderr, "qsig: cannot connect to server %s (errno=%d)\n",
				pbs_server, pbs_errno);
			any_failed = pbs_errno;
			continue;
		} else if (pbs_errno)
			show_svr_inst_fail(connect, argv[0]);

		stat = pbs_sigjob(connect, job_id_out, sig_string, NULL);
		if (stat && (pbs_errno != PBSE_UNKJOBID)) {
			prt_job_err("qsig", connect, job_id_out);
			any_failed = pbs_errno;
		} else if (stat && (pbs_errno == PBSE_UNKJOBID) && !located) {
			located = TRUE;
			if (locate_job(job_id_out, server_out, rmt_server)) {
				pbs_disconnect(connect);
				pbs_strncpy(server_out, rmt_server, sizeof(server_out));
				goto cnt;
			}
			prt_job_err("qsig", connect, job_id_out);
			any_failed = pbs_errno;
		}

		pbs_disconnect(connect);
	}

	/*cleanup security library initializations before exiting*/
	CS_close_app();

	exit(any_failed);
}
