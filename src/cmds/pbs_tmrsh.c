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
 * @file	pbs_tmrsh.c
 * @brief
 * pbs_tmrsh - a replacement for rsh using the Task Management API
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <pwd.h>
#include <netdb.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include "cmds.h"
#include "tm.h"
#include "pbs_version.h"

char		*host = NULL;

extern char *get_ecname(int rc);

/**
 * @brief
 * 	displays how to use pbs_tmrsh
 *
 * @param[in] id - command name i.e pbs_tmrsh
 *
 * @return Void
 *
 */
void
usage(char *id)
{
	fprintf(stderr, "usage: %s [-n][-l username] host [-n][-l username] command\n", id);
	fprintf(stderr, "       %s --version\n", id);
	exit(255);
}

/**
 * @brief
 *  	returns the username
 *
 * @return string
 * @retval "username"
 *
 */
char *
myname(void)
{
	uid_t		me = getuid();
	struct passwd	*pent;

	if ((pent = getpwuid(me)) == NULL)
		return "";
	else
		return pent->pw_name;
}

#ifndef INADDR_NONE
#define INADDR_NONE	(in_addr_t)0xFFFFFFFF
#endif

/**
 * @brief
 *	Check the host to a line read from PBS_NODEFILE.
 *	The PBS_NODEFILE will contain node names.  We want to be able
 *	to accept IP addresses for the host.
 *
 * @param[in] line - line from PBS_NODEFILE
 *
 * @return  	Error code
 * @retval	1 - Success i.e matched
 * @retval	0 - Failure i.e not matched
 *
 */
int
host_match(char *line)
{
	int	len = strlen(line);
	static	char	domain[PBS_MAXHOSTNAME+1];
	char	fullhost[PBS_MAXHOSTNAME+1];
	static	struct in_addr	addr;
	static	int		addrvalid = -1;

	if (line[len-1] == '\n')
		line[len-1] = '\0';

	if (strcmp(line, host) == 0)
		return 1;

	if (addrvalid == -1) {
		addr.s_addr = inet_addr(host);
		addrvalid = (addr.s_addr == INADDR_NONE) ? 0 : 1;
	}

	if (addrvalid) {	/* compare IP addresses */
		struct	hostent	*hp = gethostbyname(line);
		int	i;

		if (hp == NULL)
			return 0;

		for (i=0; hp->h_addr_list[i]; i++) {
			if (memcmp(&addr, hp->h_addr_list[i],
				hp->h_length) == 0)
				return 1;
		}
		return 0;
	}

	if (domain[0] == '\0') {
		if (getdomainname(domain, (sizeof(domain) - 1)) == -1) {
			perror("getdomainname");
			exit(255);
		}
		if (domain[0] == '\0') {
			int	i;
			char	*dot;

			if (gethostname(domain, (sizeof(domain) - 1)) == -1) {
				perror("getdomainname");
				exit(255);
			}
			if (domain[0] == '\0')
				return 0;
			if ((dot = strchr(domain, '.')) == NULL)
				return 0;
			for (i=0, dot++; *dot; i++, dot++)
				domain[i] = *dot;
			domain[i] = '\0';
		}
	}
	pbs_strncpy(fullhost, line, sizeof(fullhost));
	strcat(fullhost, ".");
	strcat(fullhost, domain);

	if (strcmp(fullhost, host) == 0)
		return 1;

	return 0;
}

int
main(int argc, char *argv[], char *envp[])
{
	char		*id;
	char		*jobid;
	int		i, arg;
	FILE		*fp;
	int		numnodes;
	int		err = 0;
	int		rc, exitval;
	struct tm_roots	rootrot;
	char		*nodefile;
	tm_node_id	*nodelist;
	tm_event_t	event;
	tm_task_id	tid;
	char		line[256], *cp;

	/*test for real deal or just version and exit*/

	PRINT_VERSION_AND_EXIT(argc, argv);

	if (initsocketlib())
		return 1;

	id = argv[0];
	if (argc < 3)
		usage(id);

	for (arg=1; arg<argc; arg++) {
		char	*c = argv[arg];
		char	lopt[] = "-l";
		int	len = sizeof(lopt)-1;

		if (*c == '-') {	/* option */
			if (strcmp(c, "-n") == 0)	/* noop */
				continue;

			if (strncmp(c, lopt, len) == 0) {	/* login name */
				if (strlen(c) == len) {
					arg++;
					if (arg == argc) {
						err = 1; /* no args left */
						break;
					}
					c = argv[arg];
				} else			/* -lname */
					c += len;

				if (strcmp(c, myname()) != 0) {
					fprintf(stderr, "%s: bad user \"%s\"\n",
						id, c);
					err = 1;
				}
			}
			else {		/* unknown option */
				err = 1;
				break;
			}
		} else if (host == NULL)
			host = c;	/* first non-option is host */
		else
			break;		/* host is set, must be command */
	}

	/*
	 **	If there was an error processing arguments or there is
	 **	no command, exit.
	 */
	if (err || (argc == arg) || (host == NULL))
		usage(id);

	if (getenv("PBS_ENVIRONMENT") == 0) {
		fprintf(stderr, "%s: not executing under PBS\n", id);
		return 255;
	}
	if ((jobid = getenv("PBS_JOBID")) == NULL) {
		fprintf(stderr, "%s: PBS jobid not in environment\n", id);
		return 255;
	}

	/*
	 **	Set up interface to the Task Manager
	 */
	if ((rc = tm_init(NULL, &rootrot)) != TM_SUCCESS) {
		fprintf(stderr, "%s: tm_init: %s\n", id, get_ecname(rc));
		return 255;
	}

	if ((rc = tm_nodeinfo(&nodelist, &numnodes)) != TM_SUCCESS) {
		fprintf(stderr, "%s: tm_nodeinfo: %s\n", id, get_ecname(rc));
		return 255;
	}

	/*
	 ** Check which node number the host is.
	 */
	if ((nodefile = getenv("PBS_NODEFILE")) == NULL) {
		fprintf(stderr, "%s: cannot find PBS_NODEFILE\n", id);
		return 255;
	}
	if ((fp = fopen(nodefile, "r")) == NULL) {
		perror(nodefile);
		return 255;
	}

	for (i=0; (cp = fgets(line, sizeof(line), fp)) != NULL; i++) {
		if (host_match(line))
			break;
	}
	fclose(fp);
	if (cp == NULL) {
		fprintf(stderr, "%s: host \"%s\" is not a node in job <%s>\n",
			id, host, jobid);
		return 255;
	}
	if (i >= numnodes) {
		fprintf(stderr, "%s: PBS_NODEFILE contains %d entries, "
			"only %d nodes in job\n", id, i, numnodes);
		return 255;
	}

	if ((rc = tm_spawn(argc-arg, argv+arg, NULL,
		nodelist[i], &tid, &event)) != TM_SUCCESS) {
		fprintf(stderr, "%s: tm_spawn: host \"%s\" err %s\n",
			id, host, get_ecname(rc));
	}

	rc = tm_poll(TM_NULL_EVENT, &event, 1, &err);
	if (rc != TM_SUCCESS || event == TM_ERROR_EVENT) {
		fprintf(stderr, "%s: tm_poll(spawn): host \"%s\" err %s %d\n",
			id, host, get_ecname(rc), err);
		return 255;
	}

	if ((rc = tm_obit(tid, &exitval, &event)) != TM_SUCCESS) {
		fprintf(stderr, "%s: obit: host \"%s\" err %s\n",
			id, host, get_ecname(rc));
		return 255;
	}

	rc = tm_poll(TM_NULL_EVENT, &event, 1, &err);
	if (rc != TM_SUCCESS || event == TM_ERROR_EVENT) {
		fprintf(stderr, "%s: tm_poll(obit): host \"%s\" err %s %d\n",
			id, host, get_ecname(rc), err);
		return 255;
	}

	tm_finalize();

	return exitval;
}
