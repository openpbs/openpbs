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

#include <pbs_config.h>

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <pbs_ifl.h>
#include <rm.h>
#include "pbs_internal.h"
#include "tpp.h"
#include "log.h"

#define SHOW_NONE 0xff

int
main(int argc, char *argv[])
{
	int i;
	char mom_name[PBS_MAXHOSTNAME + 1];
	int mom_port = 0;
	int c, rc;
	int mom_sd;
	char *req;
	struct tpp_config tpp_conf;
	fd_set selset;
	struct timeval tv;

	if (initsocketlib())
		return 1;

	if (gethostname(mom_name, (sizeof(mom_name) - 1)) < 0)
		mom_name[0] = '\0';

	while ((c = getopt(argc, argv, "m:p:")) != EOF) {
		switch (c) {
			case 'm':
				strcpy(mom_name, optarg);
				break;
			case 'p':
				mom_port = atoi(optarg);
				break;
			default:
				fprintf(stderr, "Bad option: %c\n", c);
		}
	}

	if (mom_name[0] == '\0' || optind == argc) {
		fprintf(stderr,
			"Error in usage: pbs_rmget [-m mom name] [-p mom port] <req1>...[reqN]\n");
		return 1;
	}

	if (set_msgdaemonname("pbs_rmget")) {
		fprintf(stderr, "Out of memory\n");
		return 1;
	}

	/* load the pbs conf file */
	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "%s: Configuration error\n", argv[0]);
		return (1);
	}

	set_log_conf(pbs_conf.pbs_leaf_name, pbs_conf.pbs_mom_node_name,
		     pbs_conf.locallog, pbs_conf.syslogfac,
		     pbs_conf.syslogsvr, pbs_conf.pbs_log_highres_timestamp);

	if (!pbs_conf.pbs_leaf_name) {
		char my_hostname[PBS_MAXHOSTNAME + 1];
		if (gethostname(my_hostname, (sizeof(my_hostname) - 1)) < 0) {
			fprintf(stderr, "Failed to get hostname\n");
			return -1;
		}
		pbs_conf.pbs_leaf_name = get_all_ips(my_hostname, log_buffer, sizeof(log_buffer) - 1);
		if (!pbs_conf.pbs_leaf_name) {
			fprintf(stderr, "%s\n", log_buffer);
			fprintf(stderr, "%s\n", "Unable to determine TPP node name");
			return -1;
		}
	}

	/* call tpp_init */
	rc = set_tpp_config(&pbs_conf, &tpp_conf, pbs_conf.pbs_leaf_name, -1, pbs_conf.pbs_leaf_routers);
	if (rc == -1) {
		fprintf(stderr, "Error setting TPP config\n");
		return -1;
	}

	if ((tpp_fd = tpp_init(&tpp_conf)) == -1) {
		fprintf(stderr, "tpp_init failed\n");
		return -1;
	}

	/*
	 * Wait for net to get restored, ie, app to connect to routers
	 */
	FD_ZERO(&selset);
	FD_SET(tpp_fd, &selset);
	tv.tv_sec = 5;
	tv.tv_usec = 0;
	select(FD_SETSIZE, &selset, NULL, NULL, &tv);

	tpp_poll(); /* to clear off the read notification */

	/* get the FQDN of the mom */
	c = get_fullhostname(mom_name, mom_name, (sizeof(mom_name) - 1));
	if (c == -1) {
		fprintf(stderr, "Unable to get full hostname for mom %s\n", mom_name);
		return -1;
	}

	if ((mom_sd = openrm(mom_name, mom_port)) < 0) {
		fprintf(stderr, "Unable to open connection to mom: %s:%d\n", mom_name, mom_port);
		return 1;
	}

	for (i = optind; i < argc; i++)
		addreq(mom_sd, argv[i]);

	for (i = optind; i < argc; i++) {
		req = getreq(mom_sd);
		if (req == NULL) {
			fprintf(stderr, "Error getting response %d from mom.\n", i - optind);
			return 1;
		}
		printf("[%d] %s\n", i - optind, req);
		free(req);
	}

	closerm(mom_sd);

	return 0;
}
