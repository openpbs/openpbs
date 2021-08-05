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


#include <pbs_config.h>   /* the master config generated by configure */

#include <string.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include "portability.h"
#include "libpbs.h"
#include "dis.h"
#include "tpp.h"

/**
 * @brief Sends the Modify Reservation request
 *
 * @param[in] connect - socket descriptor for the connection.
 * @param[in] resv-Id - Reservation Identifier
 * @param[in] attrib  - list of attributes to be modified.
 * @param[in] extend  - extended options
 *
 * @return - reply from server on no error.
 * @return - NULL on error.
 */

char *
PBSD_modify_resv(int connect, const char *resv_id, struct attropl *attrib, const char *extend)
{
	struct batch_reply	*reply = NULL;
	int			rc = -1;
	char			*ret = NULL;

	/* initialize the thread context data, if not initialized */
	if (pbs_client_thread_init_thread_context() != 0)
		return NULL;

	/*
	 * lock pthread mutex here for this connection
	 * blocking call, waits for mutex release
	 */
	if (pbs_client_thread_lock_connection(connect) != 0)
		return NULL;


	DIS_tcp_funcs();

	/* first, set up the body of the Modify Reservation request */

	if ((rc = encode_DIS_ReqHdr(connect, PBS_BATCH_ModifyResv, pbs_current_user)) ||
		(rc = encode_DIS_ModifyResv(connect, resv_id, attrib)) ||
		(rc = encode_DIS_ReqExtend(connect, extend))) {
			if (set_conn_errtxt(connect, dis_emsg[rc]) != 0) {
				pbs_errno = PBSE_SYSTEM;
				pbs_client_thread_unlock_connection(connect);
				return NULL;
			}
			if (pbs_errno == PBSE_PROTOCOL) {
				pbs_client_thread_unlock_connection(connect);
				return NULL;
			}
	}
	if (dis_flush(connect)) {
		pbs_errno = PBSE_PROTOCOL;
		pbs_client_thread_unlock_connection(connect);
		return NULL;
	}

	reply = PBSD_rdrpy(connect);
	if (reply == NULL)
		pbs_errno = PBSE_PROTOCOL;
	else {
		if ((reply->brp_code == PBSE_NONE) && (reply->brp_un.brp_txt.brp_str)) {
			ret = strdup(reply->brp_un.brp_txt.brp_str);
			if (!ret)
				pbs_errno = PBSE_SYSTEM;
		}
		PBSD_FreeReply(reply);
	}

	/* unlock the thread lock and update the thread context data */
	if (pbs_client_thread_unlock_connection(connect) != 0)
		return NULL;

	return ret;
}
