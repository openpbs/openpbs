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

#include <pbs_config.h>
#include <stdio.h>
#include <stdlib.h>
#include "win.h"
#include "log.h"

/**
 * @file	winnet.c
 * @brief
 *	exits of WSAStartup fails; otherwise, proceeds normally.
 *
 * @return error code
 * @retval 0 Success
 * @retval 1 Failure
 *
 */
int
winsock_init()
{	
	WSADATA	data;
	int ret;

	save_env(); 	/* need certain environment variables set in order */
	/* make network calls like socket() or gethostbyname()*/
	ret = WSAStartup(MAKEWORD(2, 2), &data);
	if (ret) {
		log_eventf(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ERR, __func__, "winsock_init failed with errno %d",
				ret);
		return 1;
	}
	return 0;
}

/**
 * @brief
 *	returns 0 for success; otherwise, result of WSAGetLastError()
 *
 */
void
winsock_cleanup()
{
	if (WSACleanup()) {
		log_eventf(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ERR, __func__, "winsock_cleanup failed with errrno %d", 
				WSAGetLastError());
	}
}
