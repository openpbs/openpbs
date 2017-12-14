/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
#ifdef WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <pbs_ifl.h>
#include "pbs_error.h"

#define NUM_LOCAL_INTERFACES 50
struct sockaddr_in *pbs_localIP_list[NUM_LOCAL_INTERFACES];
struct sockaddr_in *pbs_localactiveIP_list[NUM_LOCAL_INTERFACES];
struct sockaddr_in *loopback_addr=NULL;
short pbs_num_localifs = 0;
static short int localip_enumerated = 0;
static INTERFACE_INFO localif_list[NUM_LOCAL_INTERFACES];
static INTERFACE_INFO localUPif_list[NUM_LOCAL_INTERFACES];

/**
 * @brief
 *	Enumerate local ip addresses and get the loopback address.
 *  Fills global array pbs_localIP_list with IP addresses configured on local host.
 *  Fills global array pbs_localactiveIP_list with all active local IP addresses
 *  on local host.
 *  Configured loopback address is stored into global variable loopback_addr.
 *  Should be invoked after winsock_init() or WSAStartup() call.
 *  Returns success if loopback_addr is already intialized(is non-NULL).
 * @see
 *
 * @return	int
 * @retval	0 	- 	Enumeration of local IP addresses successful.
 * @retval	!0 	- 	Enumeration of local IP addresses failed.
 *
 */
int
enum_localIPaddrs(void)
{
	unsigned long nBytesReturned;
	int i;
	SOCKET sd;
	struct sockaddr_in * tmp_sockaddr;

	if (localip_enumerated && loopback_addr != NULL)
		return 0;
	sd = WSASocket(AF_INET, SOCK_DGRAM, 0, 0, 0, 0);

	if (sd == SOCKET_ERROR) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if (WSAIoctl(sd, SIO_GET_INTERFACE_LIST, 0, 0, &localif_list,
		sizeof(localif_list), &nBytesReturned, 0, 0) == SOCKET_ERROR) {
		errno = WSAGetLastError();
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	pbs_num_localifs = nBytesReturned / sizeof(INTERFACE_INFO);

	tmp_sockaddr = (struct sockaddr_in *)realloc(*pbs_localIP_list, \
					 (pbs_num_localifs) * sizeof(struct sockaddr_in *));
	if (tmp_sockaddr == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}
	else
		*pbs_localIP_list = tmp_sockaddr;

	tmp_sockaddr = (struct sockaddr_in *)realloc(*pbs_localactiveIP_list,\
					 (pbs_num_localifs) * sizeof(struct sockaddr_in *));
	if (tmp_sockaddr  == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}
	else
		*pbs_localactiveIP_list = tmp_sockaddr;

	for (i = 0; i < pbs_num_localifs; ++i) {
		u_long nFlags = localif_list[i].iiFlags;
		pbs_localIP_list[i] = (struct sockaddr_in *) & (localif_list[i].iiAddress);
		if (nFlags & IFF_UP) {
			localUPif_list[i] = localif_list[i];
			if (nFlags & IFF_LOOPBACK) {
				loopback_addr = (struct sockaddr_in *) & (localif_list[i].iiAddress);
			}
			pbs_localactiveIP_list[i] = (struct sockaddr_in *) & (localUPif_list[i].iiAddress);
		}
	}
	/*
	 * In Personal mode, this function will be used to get loopback address
	 * Return error if loopback_addr is not configured.
	 * Value of localip_enumerated will remain 0 in this case.
	 */
	if (loopback_addr == NULL) {
		pbs_errno = PBSE_NOLOOPBACKIF;
		return -1;
	}

	localip_enumerated = 1;
	return 0;
}
#endif
