/* 
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */

/**
 * @file	hnls.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#if defined(linux)

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <ifaddrs.h>
#include <netdb.h>

#elif defined(WIN32)

#include <Winsock2.h>
#include <Ws2tcpip.h>
#include <Iphlpapi.h>

#pragma comment(lib,"Ws2_32.lib")
#pragma comment(lib,"Iphlpapi.lib")

#else

#include <arpa/inet.h>
#include <netinet/in.h>
#include <net/if.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/socketvar.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <stropts.h>
#include <netdb.h>
#ifdef sun
#include <sys/sockio.h>
#endif

#endif

void
free_if_hostnames(char **names)
{
	int i;

	if (!names)
		return;

	for (i = 0; names[i]; i++)
		free(names[i]);
	free(names);
}

void
get_sa_family(struct sockaddr *saddr, char *family){

	memset(family, 0, sizeof(family));

	switch(saddr->sa_family){
	case AF_INET:
		strcpy(family, "ipv4");
		break;
	case AF_INET6:
		strcpy(family, "ipv6");
		break;
	default:
		return;
	}

	

}

char **
get_if_hostnames(struct sockaddr *saddr)
{
	int i;
	int aliases;
	char **names;
	const void *addr;
	size_t addr_size;
	struct hostent *hostp;
	struct sockaddr_in *saddr_in;
	struct sockaddr_in6 *saddr_in6;
	char buf[INET6_ADDRSTRLEN];
	const char *bufp = NULL;

	if (!saddr)
		return NULL;

	switch (saddr->sa_family) {
		case AF_INET:
			saddr_in = (struct sockaddr_in *)saddr;
			addr = &saddr_in->sin_addr;
			addr_size = sizeof(saddr_in->sin_addr);
			bufp = inet_ntop(AF_INET, addr, buf, INET_ADDRSTRLEN);
			if (!bufp)
				return NULL;
			hostp = gethostbyaddr(addr, addr_size, saddr_in->sin_family);
			break;
		case AF_INET6:
			saddr_in6 = (struct sockaddr_in6 *)saddr;
			addr = &saddr_in6->sin6_addr;
			addr_size = sizeof(saddr_in6->sin6_addr);
			bufp = inet_ntop(AF_INET6, addr, buf, INET6_ADDRSTRLEN);
			if (!bufp)
				return NULL;
			hostp = gethostbyaddr(addr, addr_size, saddr_in6->sin6_family);
			break;
		default:
			return NULL;
	}

	if (!hostp)
		return NULL;

	/* Count the aliases. */
	for (aliases = 0; hostp->h_aliases[aliases]; aliases++)
		;
	names = (char **)calloc((aliases + 2), sizeof(char *));
	if (!names)
		return NULL;
	names[0] = strdup(hostp->h_name);
	for (i = 0; i < aliases; i++) {
		names[i+1] = strdup(hostp->h_aliases[i]);
	}
	return names;
}
