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
 * @file    hostn.c
 *
 * @brief
 * 		hostn.c - Functions related to get host by name.
 *
 * Functions included are:
 * 	usage()
 * 	main()
 * 	prt_herrno()
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <netdb.h>
#include <string.h>

#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "cmds.h"
#include "pbs_version.h"

#if !defined(H_ERRNO_DECLARED)
extern int h_errno;
#endif

/**
 * @brief
 * 		usage - shows the usage of the module
 *
 * @param[in]	name	-	hostname
 */
void
usage(char *name)
{
	fprintf(stderr, "Usage: %s [-v] hostname\n", name);
	fprintf(stderr, "\t -v turns on verbose output\n");
	fprintf(stderr, "       %s --version\n", name);
}
/**
 * @brief
 * 		main - the entry point in hostn.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 * @param[in]	env	-	environment values.
 *
 * @return	int
 * @retval	0	: success
 * @retval	!=0	: error code
 */
int
main(int argc, char *argv[], char *env[])
{
	int i;
	struct hostent *host;
	struct hostent *hosta;
	struct in_addr *ina;
	int naddr;
	int vflag = 0;
	void prt_herrno();
	extern int optind;

	/*the real deal or output pbs_version and exit?*/
	PRINT_VERSION_AND_EXIT(argc, argv);

	if (initsocketlib())
		return 1;

	while ((i = getopt(argc, argv, "v-:")) != EOF) {
		switch (i) {
			case 'v':
				vflag = 1;
				break;
			default:
				usage(argv[0]);
				return 1;
		}
	}

	if (optind != argc - 1) {
		usage(argv[0]);
		return 1;
	}

#ifndef WIN32
	h_errno = 0;
#endif

	i = 0;
	while (env[i]) {
		if (!strncmp(env[i], "LOCALDOMAIN", 11)) {
			printf("%s\n", env[i]);
			env[i] = "";
			break;
		}
		++i;
	}

	host = gethostbyname(argv[optind]);
	if (host) {
		if (vflag)
			printf("primary name: ");
		printf("%s", host->h_name);
		if (vflag)
			printf(" (from gethostbyname())");
		printf("\n");
		if (vflag) {
			if (host->h_aliases && *host->h_aliases) {
				for (i = 0; host->h_aliases[i]; ++i)
					printf("aliases:           %s\n",
					       host->h_aliases[i]);
			} else {
				printf("aliases:            -none-\n");
			}

			printf("     address length:  %d bytes\n", host->h_length);
		}

		/* need to save address because they will be over writen on */
		/* next call to gethostby*()				    */

		naddr = 0;
		for (i = 0; host->h_addr_list[i]; ++i) {
			++naddr;
		}
		ina = (struct in_addr *) malloc(sizeof(struct in_addr) * naddr);
		if (ina == NULL) {
			fprintf(stderr, "%s: out of memory\n", argv[0]);
			return 1;
		}

		for (i = 0; i < naddr; ++i) {
			(void) memcpy((char *) (ina + i), host->h_addr_list[i],
				      host->h_length);
		}
		if (vflag) {
			for (i = 0; i < naddr; ++i) {
				printf("     address:      %15.15s  ", inet_ntoa(*(ina + i)));
				printf(" (%u dec)  ", (int) (ina + i)->s_addr);

#ifndef WIN32
				h_errno = 0;
#endif
				hosta = gethostbyaddr((char *) (ina + i), host->h_length,
						      host->h_addrtype);
				if (hosta) {
					printf("name:  %s", host->h_name);
				} else {
					printf("name:  -null-");
					prt_herrno();
				}
				printf("\n");
			}
		}

	} else {
		fprintf(stderr, "no name entry found for %s\n", argv[optind]);
		prt_herrno();
	}
	return 0;
}
/**
 * @brief
 * 		prt_herrno - assigns error descriptions corresponding to error number.
 */
void
prt_herrno()
{
	char *txt;

	switch (h_errno) {
		case 0:
			return;

		case HOST_NOT_FOUND:
			txt = "Answer Host Not Found";
			break;

		case TRY_AGAIN:
			txt = "Try Again";
			break;

		case NO_RECOVERY:
			txt = "No Recovery";
			break;

		case NO_DATA:
			txt = "No Data";
			break;

		default:
			txt = "unknown error";
			break;
	}
	fprintf(stderr, " ** h_errno is %d %s\n", h_errno, txt);
}
