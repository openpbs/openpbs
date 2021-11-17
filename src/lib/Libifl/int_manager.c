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
 * @file	int_manager.c
 *
 * @brief
 * The function that underlies most of the job manipulation
 * routines...
 */

#include <pbs_config.h> /* the master config generated by configure */

#include <stdio.h>
#include "libpbs.h"
#include "pbs_ecl.h"
#include "cmds.h"

/**
 * @brief
 *	-send manager request and read reply to a possibly multi-svr connection
 *
 * @param[in] c - communication handle
 * @param[in] rq_type - req type
 * @param[in] command - command
 * @param[in] objtype - object type
 * @param[in] objname - object name
 * @param[in] aoplp - attribute list
 * @param[in] extend - extend string for req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
PBSD_manager(int c, int rq_type, int command, int objtype, const char *objname, struct attropl *aoplp, const char *extend)
{
	struct batch_reply *reply;
	int rc;

	/* initialize the thread context data, if not initialized */
	if (pbs_client_thread_init_thread_context() != 0)
		return pbs_errno;

	/* verify the object name if creating a new one */
	if (command == MGR_CMD_CREATE)
		if (pbs_verify_object_name(objtype, objname) != 0)
			return pbs_errno;

	/* now verify the attributes, if verification is enabled */
	if ((pbs_verify_attributes(c, rq_type, objtype, command, aoplp)) != 0)
		return pbs_errno;

	/* lock pthread mutex here for this connection */
	/* blocking call, waits for mutex release */
	if (pbs_client_thread_lock_connection(c) != 0)
		return pbs_errno;

	/* send the manage request */
	rc = PBSD_mgr_put(c, rq_type, command, objtype, objname, aoplp, extend, PROT_TCP, NULL);
	if (rc) {
		pbs_client_thread_unlock_connection(c);
		return rc;
	}

	/* read reply from stream into presentation element */
	reply = PBSD_rdrpy(c);
	PBSD_FreeReply(reply);

	rc = get_conn_errno(c);

	/* unlock the thread lock and update the thread context data */
	if (pbs_client_thread_unlock_connection(c) != 0)
		return pbs_errno;

	return rc;
}
