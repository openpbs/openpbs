/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free
 * Software Foundation, either version 3 of the License, or (at your option) any
 * later version.
 *
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */
#ifndef	_TICKET_H
#define	_TICKET_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * ticket.h - header file for dealing with security systems such as kerberos.
 */

#include <sys/types.h>

#define	PBS_CREDVER		1
#define	PBS_CREDTYPE_NONE	0
#define	PBS_CREDTYPE_DCE_KRB5	1 /* Deprecated */
#define	PBS_CREDTYPE_GRIDPROXY	2 /* Deprecated */
#define PBS_CREDTYPE_AES	3

#define	PBS_GC_BATREQ		100
#define	PBS_GC_CPYFILE		101
#define	PBS_GC_EXEC		102

#define PBS_CREDNAME_AES	"aes"

#ifdef	__cplusplus
}
#endif
#endif	/* _TICKET_H */
