/* 
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
#include "log.h"

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

/**
 *
 * @brief
 *      Free allocated memory for pointer.
 *
 * @par Side Effects:
 *      None
 *
 * @par MT-safe: Yes
 *
 * @param[in]   names - target pointer array to be freed
 *
 * @return void
 */
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
/**
 *
 * @brief
 *      Return family type for socket address.
 *
 * @par Side Effects:
 *      None
 *
 * @par MT-safe: Yes
 *
 * @param[in]		sockaddr - structure holding information 
 *					about particular address
 * @param[out]		family   - holds the socket's family type
 *					"ipv4" or "ipv6"
 *
 * @return void
 */
void
get_sa_family(struct sockaddr *saddr, char *family)
{
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
/**
 *
 * @brief
 *      Returns array of names related to interfaces.
 *
 * @par Side Effects:
 *      None
 *
 * @par MT-safe: Yes
 *
 * @param[in]   sockaddr - structure holding information 
 *				about addresses
 *
 * @return char**
 */
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
/**
 *
 * @brief
 *      Returns structure holding network information.
 *
 * @par Side Effects:
 *      None
 *
 * @par MT-safe: Yes
 *
 * @param[out]   ni - linked list holding interface name, family,
 *			hostnames returned from system
 * @param[out]   msg - error message returned if system calls not successful
 *
 * @return void
 */
void
get_if_info(struct log_net_info *ni, char *msg)
{
	
	char inet_family[10];
	struct log_net_info *curr,*prev;
	
#if defined(linux)
	
	int c, i, ret;
	char **hostnames;
	struct ifaddrs *ifp, *listp;	

	curr = ni;

	ret = getifaddrs(&ifp);

	if ((ret != 0) || (ifp == NULL)) {
		strncpy(msg, "Failed to obtain interface names", 2048);
		free(ni);
		ni = NULL;
		return;
	}
	for (listp = ifp; listp; listp = listp->ifa_next) {
		hostnames = get_if_hostnames(listp->ifa_addr);
		if(!hostnames)
			continue;

		curr->next = NULL;
		curr->iffamily = (char*)malloc(10*sizeof(char));
		curr->ifname = (char*)malloc(256*sizeof(char));
		
		get_sa_family(listp->ifa_addr, curr->iffamily);
		strncpy(curr->ifname, listp->ifa_name, 256);

		for(c = 0; hostnames[c] ; c++);
		curr->ifhostnames = (char**)malloc((c+1)*sizeof(char*));
		for(i = 0; i < (c + 1); i++){
			if(i == c) {
				curr->ifhostnames[i] = NULL;
				break;
			}					
			curr->ifhostnames[i] = (char*)malloc(256*sizeof(char));
			strncpy(curr->ifhostnames[i], hostnames[i], 256);
		}

		free_if_hostnames(hostnames);

		curr->next = (struct log_net_info*)malloc(sizeof(struct log_net_info));
		if (curr->next == NULL) {
			strncpy(msg, "Out of memory", 2048);
			ni = NULL;
			return;		
		}
		prev = curr;
		curr = curr->next;
	}
	free(curr);

	prev->next = NULL;
	freeifaddrs(ifp);

#elif defined(WIN32)

	int c, i;
	char **hostnames;
	PIP_ADAPTER_ADDRESSES addrlistp, addrp;
	PIP_ADAPTER_UNICAST_ADDRESS ucp;
	DWORD size = 8192;
	DWORD ret;
	WSADATA wsadata;

	curr = ni;

	addrlistp = (IP_ADAPTER_ADDRESSES *)malloc(size);
	if (!addrlistp) {
		strncpy(msg, "Out of memory", 2048);
		free(ni);
		ni = NULL;
		return;
	}
	ret = GetAdaptersAddresses(AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, NULL, addrlistp, &size);
	if (ret == ERROR_BUFFER_OVERFLOW) {
		addrlistp = realloc(addrlistp, size);
		if (!addrlistp) {
			strncpy(msg, "Out of memory", 2048);
			free(ni);
			ni = NULL;
			return;
		}
	ret = GetAdaptersAddresses(AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, NULL, addrlistp, &size);
	}
	if (ret == ERROR_NO_DATA) {
		strncpy(msg, "No addresses found", 2048);
		free(addrlistp);
		free(ni);
		ni = NULL;
		return;
	}
	if (ret != NO_ERROR) {
		strncpy(msg, "Failed to obtain adapter addresses", 2048);
		free(addrlistp);
		free(ni);
		ni = NULL;
		return;
	}
	if (WSAStartup(MAKEWORD(2, 2), &wsadata) != 0) {
		strncpy(msg, "Failed to initialize network", 2048);
		free(addrlistp);
		free(ni);
		ni = NULL;
		return;
	}
	for (addrp = addrlistp; addrp; addrp = addrp->Next) {
		for (ucp = addrp->FirstUnicastAddress; ucp; ucp = ucp->Next) {
			hostnames = get_if_hostnames((struct sockaddr *)ucp->Address.lpSockaddr);
			
			if (!hostnames)
				continue;

			curr->next = NULL;

			curr->iffamily = (char*)malloc(10*sizeof(char));
			if(addrlistp->Flags & 0x0100 && addrlistp->Flags & 0x0080)
				strncpy(curr->iffamily, "ipv4/ipv6", 10);
			else if(addrlistp->Flags & 0x0100)
				strncpy(curr->iffamily, "ipv6", 10);
			else if(addrlistp->Flags & 0x0080)
				strncpy(curr->iffamily, "ipv4", 10);

			curr->ifname = (char*)malloc(256*sizeof(char));
			strncpy(curr->ifname, addrp->AdapterName, 256);
			

			for(c = 0; hostnames[c] ; c++);
			curr->ifhostnames = (char**)malloc((c+1)*sizeof(char*));
			for(i = 0; i < c+1 ; i++){
				if( i == c){
					curr->ifhostnames[i] = NULL;
					break;
				}
				curr->ifhostnames[i] = (char*)malloc(256*sizeof(char));
				strncpy(curr->ifhostnames[i], hostnames[i], 256);
			}

			curr->next = (struct log_net_info*)malloc(sizeof(struct log_net_info));
			if (curr->next == NULL) {
				strncpy(msg, "Out of memory", 2048);
				ni = NULL;
				return;				
			}
			prev = curr;
			curr = curr->next;
			
			free_if_hostnames(hostnames);
		}
	}
	free(curr);
	prev->next = NULL;
	WSACleanup();
	free(addrlistp);

#else /* AIX, Solaris, etc. */

	int i, ret;
	char **hostnames;
	int sock;
	struct ifconf ifc;
	struct ifreq *ifrp;

	memset(&ifc, 0, sizeof(ifc));
	sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
	if (sock < 0) {
		strncpy(msg, "Failed to create socket", LOG_BUF_SIZE);
		return NULL;
	}
	ifc.ifc_req = NULL;

#ifdef _AIX
	ret = ioctl(sock, SIOCGSIZIFCONF, (caddr_t)&ifc.ifc_len);
	if (ret != 0) {
		strncpy(msg, "Error: %s\n", strerror(errno), LOG_BUF_SIZE);
		close(sock);
		return NULL;
	}
	if (ifc.ifc_len < 1) {
		strncpy(msg, "Invalid interface data size", LOG_BUF_SIZE);
		close(sock);
		return NULL;
	}
	ifc.ifc_req = malloc(ifc.ifc_len);
	if (!ifc.ifc_req) {
		strncpy(msg, "Out of memory", LOG_BUF_SIZE);
		close(sock);
		return NULL;
	}
	memset(ifc.ifc_req, 0, ifc.ifc_len);
#else
	ifc.ifc_len = sizeof(struct ifreq) * 64;
	ifc.ifc_req = (struct ifreq *)calloc((ifc.ifc_len / sizeof(struct ifreq)), sizeof(struct ifreq));
	if (!ifc.ifc_req) {
		strncpy(msg, "Out of memory", LOG_BUF_SIZE);
		close(sock);
		return NULL;
	}
#endif

	ret = ioctl(sock, SIOCGIFCONF, (caddr_t)&ifc);
	if (ret != 0) {
		strncpy(msg, "Error: %s\n", strerror(errno), LOG_BUF_SIZE);
		free(ifc.ifc_req);
		close(sock);
		return NULL;
	}

	ifrp = ifc.ifc_req;
	while (ifrp < (struct ifreq *)((caddr_t)ifc.ifc_req + ifc.ifc_len)) {
		hostnames = get_if_hostnames(&ifrp->ifr_addr);

		if (hostnames) {
			curr->iffamily = (char*)malloc(10*sizeof(char));
			curr->ifname = (char*)malloc(256*sizeof(char));

			get_sa_family(listp->ifa_addr, curr->iffamily);
			strncpy(curr->ifname,  ifrp->ifr_name, 256);

			for(c = 0; hostnames[c] ; c++);
			curr->ifhostnames = (char**)malloc((c+1)*sizeof(char*));
			for(i = 0; i < c+1; i++){
				if( i == c){
					curr->ifhostnames[i] = NULL;
					break;
				}
				curr->ifhostnames[i] = (char*)malloc(256*sizeof(char));
				strncpy(curr->ifhostnames[i], hostnames[i], 256);
			}

			curr->next = (struct log_net_info*)malloc(sizeof(struct log_net_info));
			if (curr->next == NULL) {
				strncpy(msg, "Out of memory", 2048);
				ni = NULL;
				return;				
			}
			prev = curr;
			curr = curr->next;
		}
#ifdef _AIX
		{
			caddr_t p = (caddr_t)ifrp;
			p += sizeof(ifrp->ifr_name);
			if (sizeof(ifrp->ifr_addr) > ifrp->ifr_addr.sa_len)
				p += sizeof(ifrp->ifr_addr);
			else
				p += ifrp->ifr_addr.sa_len;
			ifrp = (struct ifreq *)p;
		}
#else
		ifrp++;
#endif
	}

	free(curr);
	prev->next = NULL;

	free(ifc.ifc_req);
	close(sock);

#endif /* AIX, Solaris, etc. */

	return;
}
