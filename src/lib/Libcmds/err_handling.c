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
 * @file	err_handling.c
 * @brief
 *	This file is meant for common error handling functions 
 *      within commands
 */

#include <pbs_config.h>

#include <errno.h>
#include <string.h>

#include "libutil.h"
#include "libpbs.h"
#include "libutil.h"


/**
 * @brief
 *	Print the error message returned by the server, if supplied. Otherwise,
 * 	print a default error message.
 *
 * @param[in] cmd - error msg
 * @param[in] connect - fd
 * @param[in] id - error id
 *
 * @return	Void
 *
 */

void
prt_job_err(char *cmd, int connect, char *id)
{
	char *errmsg;
	char *histerrmsg = NULL;

	errmsg = pbs_geterrmsg(connect);
	if (errmsg) {
		if (pbs_geterrno() == PBSE_HISTJOBID) {
			pbs_asprintf(&histerrmsg, errmsg, id);
			if (histerrmsg) {
				fprintf(stderr, "%s: %s\n", cmd, histerrmsg);
				free(histerrmsg);
			} else {
				fprintf(stderr,
					"%s: Server returned error %d for job %s\n",
					cmd, pbs_errno, id);
			}
			return;
		}
		fprintf(stderr, "%s: %s %s\n", cmd, errmsg, id);
	} else {
		fprintf(stderr, "%s: Server returned error %d for job %s\n", cmd, pbs_errno, id);
	}
}

