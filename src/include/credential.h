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

#ifndef _CREDENTIAL_H
#define _CREDENTIAL_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * credential.h - header file for default authentication system provided
 *	with PBS.
 *
 * Other Requrired Header Files:
 *	"portability.h"
 *	"libpbs.h"
 *
 */

/*
 * a full ticket (credential) as passed from the client to the server
 * is of the following size: 8 for the pbs_iff key + 8 for the timestamp +
 * space for user and host name rounded up to multiple of 8 which is the
 * sub-credential size
 */
#define PBS_KEY_SIZE 8
#define PBS_TIMESTAMP_SZ 8
#define PBS_SUBCRED_SIZE ((PBS_MAXUSER + PBS_MAXHOSTNAME + 7) / 8 * 8)
#define PBS_SEALED_SIZE (PBS_SUBCRED_SIZE + PBS_TIMESTAMP_SZ)
#define PBS_TICKET_SIZE (PBS_KEY_SIZE + PBS_SEALED_SIZE)

#define CREDENTIAL_LIFETIME 1800
#define CREDENTIAL_TIME_DELTA 300
#define ENV_AUTH_KEY "PBS_AUTH_KEY"

#ifdef __cplusplus
}
#endif
#endif /* _CREDENTIAL_H */
