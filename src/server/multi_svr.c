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
 *
 * @brief
 *		all the functions to handle peer server in case of multi-server.
 *
 */

#include	<netdb.h>
#include	<arpa/inet.h>
#include	"pbs_nodes.h"
#include	"pbs_error.h"
#include	"server.h"
#include	"batch_request.h"
#include	"svrfunc.h"
#include	"pbs_nodes.h"
#include	"tpp.h"

typedef struct peersvr_list {
	struct peersvr_list *next;
	svrinfo_t *psvr;
} peersvr_list_t;

static struct peersvr_list *peersvrl;

/**
 * @brief
 *	Get the peer server structure corresponding to the addr
 *
 * @param[in]	addr	- addr contains ip and port
 *
 * @return	svrinfo_t
 * @retval	NULL	- Could not find peer server corresponing to the addr
 * @retval	!NULL	- svrinfo structure
 */
void *
get_peersvr(struct sockaddr_in *addr)
{
	svrinfo_t *psvr;

	psvr = tfind2(ntohl(addr->sin_addr.s_addr),
			ntohs(addr->sin_port), &ipaddrs);
	if (psvr && psvr->mi_rmport == psvr->mi_port)
		return psvr;

	return NULL;
}

/**
 * @brief
 *	Create a peer server entry, 
 *	fill in structure and add to peer svr list
 *
 * @param[in]	hostname	- hostname of peer server
 * @param[in]	port		- port of peer server service
 *
 * @return	svrinfo_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
void *
create_svr_entry(char *hostname, unsigned int port)
{
	svrinfo_t *psvr = NULL;

	psvr = (svrinfo_t *) malloc(sizeof(svrinfo_t));
	if (!psvr)
		goto err;

	pbs_strncpy(psvr->mi_host, hostname, sizeof(psvr->mi_host));
	psvr->mi_host[PBS_MAXHOSTNAME] = '\0';
	psvr->mi_port = port;
	psvr->mi_rmport = port;
	psvr->mi_modtime = (time_t) 0;
	psvr->mi_data = NULL;
	psvr->mi_action = NULL;
	psvr->mi_num_action = 0;

	if (peersvrl) {
		peersvr_list_t *tmp = calloc(1, sizeof(peersvr_list_t));
		if (!tmp)
			goto err;
		tmp->psvr = psvr;
		peersvr_list_t *itr;
		for (itr = peersvrl; itr->next; itr = itr->next)
			;
		itr->next = tmp;
	} else {
		peersvrl = calloc(1, sizeof(peersvr_list_t));
		if (!peersvrl)
			goto err;
		peersvrl->psvr = psvr;
	}

	return psvr;

err:
	log_errf(PBSE_SYSTEM, __func__, "malloc/calloc failed");
	return psvr;
}

/**
 * @brief
 *	Get hostname corresponding to the addr passed
 *
 *  @param[in]	addr	- addr contains ip and port
 * @param[in]	port	- port of peer server service
 *
 * @return	host name
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
char *
get_hostname_from_addr(struct in_addr addr)
{
	struct hostent *hp;

	addr.s_addr = htonl(addr.s_addr);
	hp = gethostbyaddr((void *) &addr, sizeof(struct in_addr), AF_INET);
	if (hp == NULL) {
		log_errf(-1, __func__, "%s: errno=%d, h_errno=%d",
			 inet_ntoa(addr), errno, h_errno);
		return NULL;
	}

	return hp->h_name;
}

/**
 * @brief
 *	Create server struct from addr passed as input.
 *	
 *
 *  @param[in]	addr	- addr contains ip and port
 *
 * @return	svrinfo_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
void *
create_svr_struct(struct sockaddr_in *addr)
{
	char *hostname;
	svrinfo_t *psvr = NULL;
	u_long	*pul = NULL;

	if ((hostname = get_hostname_from_addr(addr->sin_addr))) {
                if (make_host_addresses_list(hostname, &pul)) {
                        return NULL;
                }
		if ((psvr = create_svrmom_entry(hostname, addr->sin_port, pul, 1)) == NULL) {
			free(pul);
			log_errf(-1, __func__, "Failed initialization for peer server %s", hostname);
			return NULL;
		}
	}

	return psvr;
}

/**
 * @brief
 *	Send hello to peer server
 *	
 *  @param[in]	psvr	- server structure
 *
 * @return	int
 * @retval	0	- success
 * @retval	-1	- failure
 */
int
send_hello(svrinfo_t *psvr)
{
	int rc;
	int stream = ((mom_svrinfo_t *)(psvr->mi_data))->msr_stream;

	if ((rc = is_compose(stream, IS_PEERSVR_CONNECT)) != DIS_SUCCESS)
		goto err;

	if ((rc = dis_flush(stream)) != DIS_SUCCESS)
		goto err;

	log_eventf(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
		msg_daemonname, "HELLO sent to peer server %s at stream:%d", psvr->mi_host, stream);
	return 0;

err:
	log_errf(errno, msg_daemonname, "Failed to send HELLO to peer server %s at stream:%d", psvr->mi_host, stream);
	tpp_close(stream);
	return -1;
}

/**
 * @brief
 *	Connect to peer server
 *	
 *  @param[in]	hostaddr	- host address of peer server
 *  @param[in]	port		- port of peer server service
 *
 * @return	svrinfo_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
void *
connect_to_peersvr(pbs_net_t hostaddr, uint port)
{
	struct sockaddr_in addr;
	svrinfo_t *psvr;

	addr.sin_addr.s_addr = hostaddr;
	addr.sin_port = port;

	if ((psvr = create_svr_struct(&addr)) == NULL)
		return NULL;

	if (open_tppstream(psvr) < 0) {
		delete_svrmom_entry(psvr);
		return NULL;
	}

	if (send_hello(psvr) < 0) {
		delete_svrmom_entry(psvr);
		return NULL;
	}

	return psvr;
}

/**
 * @brief
 *	initialize multi server instances
 *
 * @return	int
 * @retval	!0	- Failure
 * @retval	0	- Success
 */
int
init_msi()
{
	peersvrl = NULL;

	return 0;
}
