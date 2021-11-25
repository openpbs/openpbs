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

#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "log.h"
#include "pbs_ifl.h"
#include "pbs_internal.h"

#if defined(linux)

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <ifaddrs.h>
#include <netdb.h>

#elif defined(WIN32)

#pragma comment(lib, "Ws2_32.lib")
#pragma comment(lib, "Iphlpapi.lib")

#else

#include <arpa/inet.h>
#include <netinet/in.h>
#include <net/if.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/socketvar.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <netdb.h>

#endif

extern char *netaddr(struct sockaddr_in *);
#define NETADDR_BUF 80

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
	if (!family)
		return;
	*family = '\0';
	if (!saddr)
		return;

	switch (saddr->sa_family) {
		case AF_INET:
			strncpy(family, "ipv4", IFFAMILY_MAX);
			break;
		case AF_INET6:
			strncpy(family, "ipv6", IFFAMILY_MAX);
			break;
	}
	family[IFFAMILY_MAX - 1] = '\0';
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
	int aliases = 0;
	char **names;
	const void *addr;
	size_t addr_size;
	struct hostent *hostp;
	struct sockaddr_in *saddr_in;
	struct sockaddr_in6 *saddr_in6;
	char buf[INET6_ADDRSTRLEN];
	const char *bufp = NULL;
#ifdef WIN32
	char host[NI_MAXHOST] = {'\0'};
	int ret = 0;
#endif /* WIN32 */

	if (!saddr)
		return NULL;

	switch (saddr->sa_family) {
		case AF_INET:
			saddr_in = (struct sockaddr_in *) saddr;
#ifdef WIN32
			saddr_in->sin_family = AF_INET;
#endif /* WIN32 */
			addr = &saddr_in->sin_addr;
			addr_size = sizeof(saddr_in->sin_addr);
			bufp = inet_ntop(AF_INET, addr, buf, INET_ADDRSTRLEN);
			if (!bufp)
				return NULL;
#ifdef WIN32
			ret = getnameinfo(saddr_in, sizeof(struct sockaddr_in), host, NI_MAXHOST, NULL, NULL, 0);
			if (ret != 0 || host[0] == '\0')
				return NULL;
#else
			hostp = gethostbyaddr(addr, addr_size, saddr_in->sin_family);
			if (!hostp)
				return NULL;
#endif /* WIN32 */
			break;
		case AF_INET6:
			saddr_in6 = (struct sockaddr_in6 *) saddr;
#ifdef WIN32
			saddr_in6->sin6_family = AF_INET6;
#endif /* WIN32 */
			addr = &saddr_in6->sin6_addr;
			addr_size = sizeof(saddr_in6->sin6_addr);
			bufp = inet_ntop(AF_INET6, addr, buf, INET6_ADDRSTRLEN);
			if (!bufp)
				return NULL;
#ifdef WIN32
			ret = getnameinfo(saddr_in6, sizeof(struct sockaddr_in6), host, NI_MAXHOST, NULL, NULL, 0);
			if (ret != 0 || host[0] == '\0')
				return NULL;
#else
			hostp = gethostbyaddr(addr, addr_size, saddr_in6->sin6_family);
			if (!hostp)
				return NULL;
#endif /* WIN32 */
			break;
		default:
			return NULL;
	}

#ifdef WIN32
	names = (char **) calloc(2, sizeof(char *));
	if (!names)
		return NULL;
	names[0] = strdup(host);
#else
	/* Count the aliases. */
	for (aliases = 0; hostp->h_aliases[aliases]; aliases++)
		;
	names = (char **) calloc((aliases + 2), sizeof(char *));
	if (!names)
		return NULL;
	names[0] = strdup(hostp->h_name);
	for (i = 0; i < aliases; i++) {
		names[i + 1] = strdup(hostp->h_aliases[i]);
	}
#endif /* WIN32 */
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
 * @param[out]   msg - error message returned if system calls not successful
 *
 * @return struct log_net_info * - Linked list of log_net_info structures
 */
struct log_net_info *
get_if_info(char *msg)
{
	struct log_net_info *head = NULL;
	struct log_net_info *curr = NULL;
	struct log_net_info *prev = NULL;

#if defined(linux)

	int c, i, ret;
	char **hostnames;
	struct ifaddrs *ifp, *listp;

	if (!msg)
		return NULL;
	ret = getifaddrs(&ifp);
	if ((ret != 0) || (ifp == NULL)) {
		strncpy(msg, "Failed to obtain interface names", LOG_BUF_SIZE);
		msg[LOG_BUF_SIZE - 1] = '\0';
		return NULL;
	}
	for (listp = ifp; listp; listp = listp->ifa_next) {
		hostnames = get_if_hostnames(listp->ifa_addr);
		if (!hostnames)
			continue;
		curr = (struct log_net_info *) calloc(1, sizeof(struct log_net_info));
		if (!curr) {
			free_if_info(head);
			free_if_hostnames(hostnames);
			strncpy(msg, "Out of memory", LOG_BUF_SIZE);
			msg[LOG_BUF_SIZE - 1] = '\0';
			return NULL;
		}
		if (prev)
			prev->next = curr;
		if (!head)
			head = curr;
		get_sa_family(listp->ifa_addr, curr->iffamily);
		pbs_strncpy(curr->ifname, listp->ifa_name, IFNAME_MAX);
		/* Count the hostname entries and allocate space */
		for (c = 0; hostnames[c]; c++)
			;
		curr->ifhostnames = (char **) calloc(c + 1, sizeof(char *));
		if (!curr->ifhostnames) {
			free_if_info(head);
			free_if_hostnames(hostnames);
			strncpy(msg, "Out of memory", LOG_BUF_SIZE);
			msg[LOG_BUF_SIZE - 1] = '\0';
			return NULL;
		}
		for (i = 0; i < c; i++) {
			curr->ifhostnames[i] = (char *) calloc(PBS_MAXHOSTNAME, sizeof(char));
			if (!curr->ifhostnames[i]) {
				free_if_info(head);
				free_if_hostnames(hostnames);
				strncpy(msg, "Out of memory", LOG_BUF_SIZE);
				msg[LOG_BUF_SIZE - 1] = '\0';
				return NULL;
			}
			strncpy(curr->ifhostnames[i], hostnames[i], (PBS_MAXHOSTNAME - 1));
		}
		curr->ifhostnames[i] = NULL;
		free_if_hostnames(hostnames);
		prev = curr;
		curr->next = NULL;
	}
	freeifaddrs(ifp);

#elif defined(WIN32)

	int c, i;
	char **hostnames;
	PIP_ADAPTER_ADDRESSES addrlistp, addrp;
	PIP_ADAPTER_UNICAST_ADDRESS ucp;
	DWORD size = 8192;
	DWORD ret;
	WSADATA wsadata;

	if (!msg)
		return NULL;
	addrlistp = (IP_ADAPTER_ADDRESSES *) malloc(size);
	if (!addrlistp) {
		strncpy(msg, "Out of memory", LOG_BUF_SIZE);
		msg[LOG_BUF_SIZE - 1] = '\0';
		return NULL;
	}
	ret = GetAdaptersAddresses(AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, NULL, addrlistp, &size);
	if (ret == ERROR_BUFFER_OVERFLOW) {
		addrlistp = realloc(addrlistp, size);
		if (!addrlistp) {
			strncpy(msg, "Out of memory", LOG_BUF_SIZE);
			msg[LOG_BUF_SIZE - 1] = '\0';
			return NULL;
		}
		ret = GetAdaptersAddresses(AF_UNSPEC, GAA_FLAG_INCLUDE_PREFIX, NULL, addrlistp, &size);
	}
	if (ret == ERROR_NO_DATA) {
		strncpy(msg, "No addresses found", LOG_BUF_SIZE);
		msg[LOG_BUF_SIZE - 1] = '\0';
		free(addrlistp);
		return NULL;
	}
	if (ret != NO_ERROR) {
		strncpy(msg, "Failed to obtain adapter addresses", LOG_BUF_SIZE);
		msg[LOG_BUF_SIZE - 1] = '\0';
		free(addrlistp);
		return NULL;
	}
	if (WSAStartup(MAKEWORD(2, 2), &wsadata) != 0) {
		strncpy(msg, "Failed to initialize network", LOG_BUF_SIZE);
		msg[LOG_BUF_SIZE - 1] = '\0';
		free(addrlistp);
		return NULL;
	}
	for (addrp = addrlistp; addrp; addrp = addrp->Next) {
		for (ucp = addrp->FirstUnicastAddress; ucp; ucp = ucp->Next) {
			hostnames = get_if_hostnames((struct sockaddr *) ucp->Address.lpSockaddr);
			if (!hostnames)
				continue;
			curr = (struct log_net_info *) calloc(1, sizeof(struct log_net_info));
			if (!curr) {
				free(addrlistp);
				free_if_info(head);
				free_if_hostnames(hostnames);
				strncpy(msg, "Out of memory", LOG_BUF_SIZE);
				msg[LOG_BUF_SIZE - 1] = '\0';
				return NULL;
			}
			if (prev)
				prev->next = curr;
			if (!head)
				head = curr;
			if (addrlistp->Flags & 0x0100 && addrlistp->Flags & 0x0080) {
				strncpy(curr->iffamily, "ipv4/ipv6", IFFAMILY_MAX);
			} else if (addrlistp->Flags & 0x0100) {
				strncpy(curr->iffamily, "ipv6", IFFAMILY_MAX);
			} else if (addrlistp->Flags & 0x0080) {
				strncpy(curr->iffamily, "ipv4", IFFAMILY_MAX);
			} else {
				strncpy(curr->iffamily, "unknown", IFFAMILY_MAX);
			}
			curr->iffamily[IFFAMILY_MAX - 1] = '\0';
			strncpy(curr->ifname, addrp->AdapterName, IFNAME_MAX);
			curr->ifname[IFNAME_MAX - 1] = '\0';
			/* Count the hostname entries and allocate space */
			for (c = 0; hostnames[c]; c++)
				;
			curr->ifhostnames = (char **) calloc(c + 1, sizeof(char *));
			if (!curr->ifhostnames) {
				free(addrlistp);
				free_if_info(head);
				free_if_hostnames(hostnames);
				strncpy(msg, "Out of memory", LOG_BUF_SIZE);
				msg[LOG_BUF_SIZE - 1] = '\0';
				return NULL;
			}
			for (i = 0; i < c; i++) {
				curr->ifhostnames[i] = (char *) calloc(PBS_MAXHOSTNAME, sizeof(char));
				if (!(curr->ifhostnames[i])) {
					free(addrlistp);
					free_if_info(head);
					free_if_hostnames(hostnames);
					strncpy(msg, "Out of memory", LOG_BUF_SIZE);
					msg[LOG_BUF_SIZE - 1] = '\0';
					return NULL;
				}
				strncpy(curr->ifhostnames[i], hostnames[i], (PBS_MAXHOSTNAME - 1));
			}
			curr->ifhostnames[i] = NULL;
			free_if_hostnames(hostnames);
			prev = curr;
			curr->next = NULL;
		}
	}
	WSACleanup();
	free(addrlistp);
#endif

	return (head);
}

/**
 *
 * @brief
 *      Frees structure holding network information.
 *
 * @par Side Effects:
 *      None
 *
 * @par MT-safe: Yes
 *
 * @param[in]   ni - linked list holding interface name, family,
 *			hostnames returned from system
 *
 * @return void
 */
void
free_if_info(struct log_net_info *ni)
{
	struct log_net_info *curr;
	int i;

	curr = ni;
	while (curr) {
		struct log_net_info *temp;
		temp = curr;
		curr = curr->next;
		if (temp->ifhostnames != NULL) {
			for (i = 0; temp->ifhostnames[i]; i++)
				free(temp->ifhostnames[i]);
		}
		free(temp->ifhostnames);
		free(temp);
	}
}

/**
* @brief
	Get a list of all IPs (ipv4) for a given hostname
*
* @return
*	Comma separated list of IPs in string format
*
* @par Side Effects:
*	None
*
* @par MT-safe: Yes
*
* @param[in]    host        - hostname of the current host to resolve IPs for
* @param[out]   msg_buf     - error message returned if system calls not successful
* @param[in]    msg_buf_len - length of the message buffer passed
*
*/
static char *
get_host_ips(char *host, char *msg_buf, size_t msg_buf_len)
{
	struct addrinfo *aip, *pai;
	struct addrinfo hints;
	int rc = 0;
	char buf[NETADDR_BUF] = {'\0'};
	int count = 0;
	char *nodenames = NULL;
	char *tmp;
	int len, hlen;

	errno = 0;

	memset(&hints, 0, sizeof(struct addrinfo));
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_STREAM;
	hints.ai_protocol = IPPROTO_TCP;

	if ((rc = getaddrinfo(host, NULL, &hints, &pai)) != 0) {
		snprintf(msg_buf, msg_buf_len, "Error %d resolving %s\n", rc, host);
		return NULL;
	}

	len = 0;
	count = 0;
	for (aip = pai; aip != NULL; aip = aip->ai_next) {
		if (aip->ai_family == AF_INET) { /* for now only count IPv4 addresses */
			char *p;
			struct sockaddr_in *sa = (struct sockaddr_in *) aip->ai_addr;
			if (ntohl(sa->sin_addr.s_addr) >> 24 == IN_LOOPBACKNET)
				continue;
			sprintf(buf, "%s", netaddr(sa));
			if (!strcmp(buf, "unknown"))
				continue;
			if ((p = strchr(buf, ':')))
				*p = '\0';

			hlen = strlen(buf);
			tmp = realloc(nodenames, len + hlen + 2); /* 2 for comma and null char */
			if (!tmp) {
				strncpy(msg_buf, "Out of memory", msg_buf_len);
				free(nodenames);
				nodenames = NULL;
				break;
			}
			nodenames = tmp;

			if (len == 0)
				strcpy(nodenames, buf);
			else {
				strcat(nodenames, ",");
				strcat(nodenames, buf);
			}
			len += hlen + 2;
			count++;
		}
	}

	freeaddrinfo(pai);

	if (count == 0) {
		snprintf(msg_buf, msg_buf_len, "Could not find any usable IP address for host %s", host);
		return NULL;
	}
	return nodenames;
}

/**
* @brief
*	Get a list of all IPs
*   First it resolves the supplied hostname to determine it's IPs
*	Then it enumerates the interfaces in the host and determines IPs
*	for each of those interfaces.
*
*	Do not supply a remote hostname in this function.
*
* @return
*	Comma separated list of IPs in string format
*
* @par Side Effects:
*	None
*
* @par MT-safe: Yes
*
* @param[in]	hostname    - hostname of the current host to resolve IPs for
* @param[out]   msg_buf     - error message returned if system calls not successful
* @param[in]    msg_buf_len - length of the message buffer passed
*
*/
char *
get_all_ips(char *hostname, char *msg_buf, size_t msg_buf_len)
{
	char *nodenames;
	int len, ret;
	char *tmp;
	char buf[NETADDR_BUF];

#if defined(linux)
	struct ifaddrs *ifp, *listp;
	char *p;
#elif defined(WIN32)
	int i;
	/* Variables used by GetIpAddrTable */
	PMIB_IPADDRTABLE pIPAddrTable;
	DWORD dwSize = 0;
	DWORD dwRetVal = 0;
	IN_ADDR IPAddr;
#endif

	msg_buf[0] = '\0';

	/* prepend the list of IPs with the IPs resolved from the passed hostname */
	nodenames = get_host_ips(hostname, msg_buf, msg_buf_len);
	if (!nodenames) {
		return NULL;
	}

	len = strlen(nodenames);

#if defined(linux)
	ret = getifaddrs(&ifp);

	if ((ret != 0) || (ifp == NULL)) {
		strncpy(msg_buf, "Failed to obtain interface names", msg_buf_len);
		free(nodenames);
		return NULL;
	}

	for (listp = ifp; listp; listp = listp->ifa_next) {
		int hlen;

		if ((listp->ifa_addr == NULL) || (listp->ifa_addr->sa_family != AF_INET))
			continue;
		sprintf(buf, "%s", netaddr((struct sockaddr_in *) listp->ifa_addr));
		if (!strcmp(buf, "unknown"))
			continue;
		if ((p = strchr(buf, ':')))
			*p = '\0';

		hlen = strlen(buf);
		tmp = realloc(nodenames, len + hlen + 2); /* 2 for comma and null char */
		if (!tmp) {
			strncpy(msg_buf, "Out of memory", msg_buf_len);
			free(nodenames);
			nodenames = NULL;
			break;
		}
		nodenames = tmp;

		if (len == 0)
			strcpy(nodenames, buf);
		else {
			strcat(nodenames, ",");
			strcat(nodenames, buf);
		}
		len += hlen + 2;
	}

	freeifaddrs(ifp);

#elif defined(WIN32)

	pIPAddrTable = (MIB_IPADDRTABLE *) malloc(sizeof(MIB_IPADDRTABLE));

	if (pIPAddrTable) {
		// Make an initial call to GetIpAddrTable to get the
		// necessary size into the dwSize variable
		if (GetIpAddrTable(pIPAddrTable, &dwSize, 0) == ERROR_INSUFFICIENT_BUFFER) {
			free(pIPAddrTable);
			pIPAddrTable = (MIB_IPADDRTABLE *) malloc(dwSize);
		}
		if (pIPAddrTable == NULL) {
			strncpy(msg_buf, "Memory allocation failed for GetIpAddrTable", msg_buf_len);
			free(nodenames);
			return NULL;
		}
	}
	// Make a second call to GetIpAddrTable to get the
	// actual data we want
	if ((dwRetVal = GetIpAddrTable(pIPAddrTable, &dwSize, 0)) != NO_ERROR) {
		strncpy(msg_buf, "GetIpAddrTable failed", msg_buf_len);
		free(pIPAddrTable);
		free(nodenames);
		return NULL;
	}

	for (i = 0; i < (int) pIPAddrTable->dwNumEntries; i++) {
		int hlen;
		IPAddr.S_un.S_addr = (u_long) pIPAddrTable->table[i].dwAddr;
		sprintf(buf, "%s", inet_ntoa(IPAddr));
		hlen = strlen(buf);
		tmp = realloc(nodenames, len + hlen + 2); /* 2 for comma and null char */
		if (!tmp) {
			strncpy(msg_buf, "Out of memory", msg_buf_len);
			free(nodenames);
			nodenames = NULL;
			break;
		}
		nodenames = tmp;
		if (len == 0)
			strcpy(nodenames, buf);
		else {
			strcat(nodenames, ",");
			strcat(nodenames, buf);
		}
		len += hlen + 2;
	}

	if (pIPAddrTable) {
		free(pIPAddrTable);
		pIPAddrTable = NULL;
	}

#endif

	return nodenames;
}
