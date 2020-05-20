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
 * @file	qstop.c
 * @brief
 *  The qstop command directs that a destination should stop scheduling
 *  or routing batch jobs.
 *
 * @par	Synopsis:
 *  qstop destination ...
 *
 * @par Arguments:
 *  destination ...
 *      A list of destinations.  A destination has one of the following
 *      three forms:
 *          queue
 *          @server
 *          queue@server
 *      If queue is specified, the request is to stop the queue at
 *      the default server.  If @server is given, the request is to
 *      stop all queues at the server.  If queue@server is used,
 *      the request is to stop the named queue at the named server.
 *
 *  @author	Bruce Kelly
 *  		National Energy Research Supercomputer Center, Livermore, CA
 *  		May, 1993
 */

#include "cmds.h"
#include <pbs_config.h>   /* the master config generated by configure */
#include <pbs_version.h>


int exitstatus = 0; /* Exit Status */
static void execute(char *, char *);


int
main(int argc, char **argv)
{
	/*
	 *  This routine sends a Manage request to the batch server specified by
	 * the destination.  The STARTED queue attribute is set to {False}.  If the
	 * batch request is accepted, the server will stop scheduling or routing
	 * requests for the specified queue.
	 */

	int dest;		/* Index into the destination array (argv) */
	char *queue;	/* Queue name part of destination */
	char *server;	/* Server name part of destination */

	/*test for real deal or just version and exit*/

	PRINT_VERSION_AND_EXIT(argc, argv);

#ifdef WIN32
	if (winsock_init()) {
		return 1;
	}
#endif

	if (argc == 1) {
		fprintf(stderr, "Usage: qstop [queue][@server] ...\n");
		fprintf(stderr, "       qstop --version\n");
		exit(1);
	}

	/*perform needed security library initializations (including none)*/

	if (CS_client_init() != CS_SUCCESS) {
		fprintf(stderr, "qstop: unable to initialize security library.\n");
		exit(1);
	}

	for (dest=1; dest<argc; dest++)
		if (parse_destination_id(argv[dest], &queue, &server) == 0)
			execute(queue, server);
	else {
		fprintf(stderr, "qstop: illegally formed destination: %s\n",
			argv[dest]);
		exitstatus = 1;
	}

	/*cleanup security library initializations before exiting*/
	CS_close_app();

	exit(exitstatus);
}


/**
 * @brief
 *	disables a destination (queue)
 *
 * @param queue - The name of the queue to disable.
 * @param server - The name of the server that manages the queue.
 *
 * @return - Void
 *
 * @File Variables:
 * exitstatus  Set to two if an error occurs.
 *
 */
static void
execute(char *queue, char *server)
{
	int ct;         /* Connection to the server */
	int merr;       /* Error return from pbs_manager */
	char *errmsg;   /* Error message from pbs_manager */
	/* The disable request */
	static struct attropl attr = {NULL, "started", NULL, "FALSE", SET};

	if ((ct = cnt2server(server)) > 0) {
		merr = pbs_manager(ct, MGR_CMD_SET, MGR_OBJ_QUEUE, queue, &attr, NULL);
		if (merr != 0) {
			errmsg = pbs_geterrmsg(ct);
			if (errmsg != NULL) {
				fprintf(stderr, "qstop: %s ", errmsg);
			} else {
				fprintf(stderr, "qstop: Error (%d) disabling queue ", pbs_errno);
			}
			if (notNULL(queue))
				fprintf(stderr, "%s", queue);
			if (notNULL(server))
				fprintf(stderr, "@%s", server);
			fprintf(stderr, "\n");
			exitstatus = 2;
		}
		pbs_disconnect(ct);
	} else {
		fprintf(stderr, "qstop: could not connect to server %s (%d)\n", server, pbs_errno);
		exitstatus = 2;
	}
}
