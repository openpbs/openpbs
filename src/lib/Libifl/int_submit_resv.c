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
 * @file	int_submit_resv.c
 */
#include <pbs_config.h>   /* the master config generated by configure */

#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include "portability.h"
#include "libpbs.h"
#include "dis.h"


/**
 * @brief
 *	This function sends the Submit Reservation request
 *
 * @param[in] c - socket descriptor
 * @param[in] resv_id - reservation identifier
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extention string for req encode
 *
 * @return      string
 * @retval      resvn id	Success
 * @retval      NULL		error
 *
 */

char *
PBSD_submit_resv(int connect, char *resv_id, struct attropl *attrib, char *extend)
{
	struct batch_reply *reply;
	char  *return_resv_id = NULL;
	int    rc;

	DIS_tcp_funcs();

	/* first, set up the body of the Submit Reservation request */

	if ((rc = encode_DIS_ReqHdr(connect, PBS_BATCH_SubmitResv, pbs_current_user)) ||
		(rc = encode_DIS_SubmitResv(connect, resv_id, attrib)) ||
		(rc = encode_DIS_ReqExtend(connect, extend))) {
		if (set_conn_errtxt(connect, dis_emsg[rc]) != 0) {
			pbs_errno = PBSE_SYSTEM;
			return NULL;
		}
		pbs_errno = PBSE_PROTOCOL;
		return return_resv_id;
	}
	if (dis_flush(connect)) {
		pbs_errno = PBSE_PROTOCOL;
		return return_resv_id;
	}

	/* read reply from stream into presentation element */

	reply = PBSD_rdrpy(connect);
	if (reply == NULL) {
		pbs_errno = PBSE_PROTOCOL;
	} else if (!pbs_errno && reply->brp_choice &&
		reply->brp_choice != BATCH_REPLY_CHOICE_Text) {
		pbs_errno = PBSE_PROTOCOL;
	} else if (get_conn_errno(connect) == 0 && reply->brp_code == 0) {
		if (reply->brp_choice == BATCH_REPLY_CHOICE_Text) {
			return_resv_id = strdup(reply->brp_un.brp_txt.brp_str);
			if (return_resv_id == NULL) {
				pbs_errno = PBSE_SYSTEM;
			}
		}
	}

	PBSD_FreeReply(reply);
	return return_resv_id;
}
