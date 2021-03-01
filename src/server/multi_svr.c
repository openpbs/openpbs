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
 *
 * @brief
 *		Functions associated with peersvr structure
 *
 */

#include "avltree.h"
#include "batch_request.h"
#include "pbs_error.h"
#include "pbs_nodes.h"
#include "server.h"
#include "svrfunc.h"
#include "tpp.h"
#include <arpa/inet.h>
#include <netdb.h>

pbs_list_head peersvrl;
static void *alien_node_idx;

/**
 * @brief
 *	Get the peer server structure corresponding to the addr
 *
 * @param[in]	addr	- addr contains ip and port
 *
 * @return	server_t
 * @retval	NULL	- Could not find peer server corresponing to the addr
 * @retval	!NULL	- svrinfo structure
 */
void *
get_peersvr(struct sockaddr_in *addr)
{
	server_t *psvr;

	psvr = tfind2(ntohl(addr->sin_addr.s_addr),
		      ntohs(addr->sin_port), &ipaddrs);
	if (psvr && psvr->mi_rmport == psvr->mi_port)
		return psvr;

	return NULL;
}

/**
 * @brief Get the peersvr from host & port values
 * 
 * @param[in] hostname 
 * @param[in] port 
 * @return peer server object, NULL if not found
 */
void *
get_peersvr_from_host_port(char *hostname, uint port)
{
	server_t *psvr;

	for (psvr = GET_NEXT(peersvrl);
	     psvr; psvr = GET_NEXT(psvr->mi_link)) {
		if (!strncmp(psvr->mi_host, hostname,
			     sizeof(psvr->mi_host)) &&
		    psvr->mi_port == port)
			return psvr;
	}

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
 * @return	server_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
void *
create_svr_entry(char *hostname, unsigned int port)
{
	server_t *psvr = NULL;

	psvr = calloc(1, sizeof(server_t));
	if (!psvr)
		goto err;

	pbs_strncpy(psvr->mi_host, hostname, sizeof(psvr->mi_host));
	psvr->mi_port = port;
	psvr->mi_rmport = port;
	CLEAR_LINK(psvr->mi_link);
	append_link(&peersvrl, &psvr->mi_link, psvr);
	psvr->mi_rsc_idx = NULL;
	CLEAR_HEAD(psvr->mi_node_list);

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
 *	Create server struct from hostname and port.
 *	
 * @param[in]	addr	- addr contains ip and port
 * @param[in]	hostname - hostname if available
 *
 * @return	server_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
void *
create_svr_struct(struct sockaddr_in *addr, char *hostname)
{
	server_t *psvr = NULL;
	u_long *pul = NULL;

	if (!hostname && (hostname = get_hostname_from_addr(addr->sin_addr)) == NULL) {
		log_errf(-1, __func__, "Failed initialization for peer server");
		return NULL;
	}

	if (make_host_addresses_list(hostname, &pul))
		return NULL;
	if ((psvr = create_svrmom_entry(hostname, addr->sin_port, pul, 1)) == NULL) {
		free(pul);
		log_errf(-1, __func__, "Failed initialization for peer server %s", hostname);
		return NULL;
	}

	return psvr;
}

/**
 * @brief free the resource update structure
 * 
 * @param[in,out] ru_head - head of the resource update object list
 */
void
free_ru(psvr_ru_t *ru_head)
{
	psvr_ru_t *ru_cur;
	psvr_ru_t *ru_nxt;

	for (ru_cur = ru_head; ru_cur; ru_cur = ru_nxt) {
		ru_nxt = GET_NEXT(ru_cur->ru_link);
		free(ru_cur->jobid);
		free(ru_cur->execvnode);
		free(ru_cur);
	}
}

/**
 * @brief initialize resource usage stucture based on parameters
 * 
 * @param[in] pjob - job pointer
 * @param[in] op - operation performed - INCR/DECR
 * @param exec_vnode - exec_vnode string
 * @return psvr_ru_t* 
 * @retval NULL - on failure
 */
psvr_ru_t *
init_ru(job *pjob, int op, char *exec_vnode)
{
	psvr_ru_t *psvr_ru = pbs_calloc(1, sizeof(psvr_ru_t));

	psvr_ru->jobid = strdup(pjob->ji_qs.ji_jobid);
	psvr_ru->execvnode = strdup(exec_vnode);
	psvr_ru->op = op;
	psvr_ru->share_job = get_job_share_type(pjob);
	CLEAR_LINK(psvr_ru->ru_link);

	return psvr_ru;
}

/**
 * @brief reverse any resource update in the resource usage list
 * 
 * @param[in] ru_head - head of the resource update object list
 */
static void
reverse_resc_update(psvr_ru_t *ru_head)
{
	psvr_ru_t *ru_cur;
	attribute pexech;

	for (ru_cur = ru_head; ru_cur;
	     ru_cur = GET_NEXT(ru_cur->ru_link)) {
		log_eventf(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
			   "Reversing resc update jobid=%s, op=%d, execvnode=%s",
			   ru_cur->jobid, ru_cur->op, ru_cur->execvnode);
		update_jobs_on_node(ru_cur->jobid, ru_cur->execvnode, DECR, ru_cur->share_job);
		job_attr_def[JOB_ATR_exec_vnode].at_decode(&pexech, job_attr_def[JOB_ATR_exec_vnode].at_name, NULL, ru_cur->execvnode);
		update_node_rassn(&pexech, DECR);
	}
}

/**
 * @brief delete saved resources for the corresponding idx
 * 
 * @param[in] idx - id of the resource update which needs to be freed 
 */
void
clean_saved_rsc(void *idx)
{
	psvr_ru_t *ru_cur;
	void *idx_ctx = NULL;

	while (pbs_idx_find(idx, NULL, (void **) &ru_cur, &idx_ctx) == PBS_IDX_RET_OK) {
		reverse_resc_update(ru_cur);
		free(ru_cur);
	}
	avl_destroy_index(idx);
}

/**
 * @brief send resource update for all the jobs
 * which has an update for peer server.
 * Reset the pending_replies to zero before sending all updates.
 * 
 * @param[in] mtfd - multiplexed fd where resouce update needs to be sent
 * @return int 
 * @retval 0 - success
 * @retval !0 - DIS_ error code
 */
int
send_job_resc_updates(int mtfd)
{
	job *pjob;
	psvr_ru_t *psvr_ru;
	pbs_list_head ru_head;
	int ct = 0;
	int rc = 0;
	int count;
	int *strms;
	server_t *psvr;
	svrinfo_t *psvr_info;
	int i;

	CLEAR_HEAD(ru_head);

	strms = tpp_mcast_members(mtfd, &count);
	for (i = 0; i < count; i++) {
		if ((psvr = tfind2((u_long) strms[i], 0, &streams)) != NULL) {
			psvr_info = psvr->mi_data;
			psvr_info->pending_replies = 0;
		}
	}

	for (pjob = GET_NEXT(svr_alljobs); pjob;
	     pjob = GET_NEXT(pjob->ji_alljobs)) {
		if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_Broadcast_Rqd) &&
		    (pjob->ji_qs.ji_svrflags & JOB_SVFLG_RescAssn)) {
			psvr_ru = init_ru(pjob, INCR, pjob->ji_wattr[JOB_ATR_exec_vnode].at_val.at_str);
			append_link(&ru_head, &psvr_ru->ru_link, psvr_ru);
			ct++;
		}
	}

	if (ct == 0)
		return 0;

	if ((rc = ps_compose(mtfd, PS_RSC_UPDATE_FULL)) != DIS_SUCCESS) {
		close_streams(mtfd, rc);
		return rc;
	}

	rc = send_resc_usage(mtfd, GET_NEXT(ru_head), ct, ct);
	if (rc != DIS_SUCCESS)
		close_streams(mtfd, rc);
	free_ru(GET_NEXT(ru_head));

	return rc;
}

/**
 * @brief process ack for resource update
 * 
 * @param[in] conn - connection stream
 */
void
req_peer_svr_ack(int conn)
{
	server_t *psvr;
	int *pending_rply;
	struct work_task *ptask;
	svrinfo_t *svr_info;

	if ((psvr = tfind2(conn, 0, &streams)) != NULL) {
		svr_info = psvr->mi_data;
		pending_rply = &svr_info->pending_replies;
		if (*pending_rply)
			*pending_rply -= 1;
		else
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ALERT, __func__,
				  "pending_rply went negative... Re-setting to zero");
	} else {
		log_errf(-1, __func__, "Resource update from unknown stream %d", conn);
		return;
	}

	if (*pending_rply == 0 && num_pending_peersvr_rply() == 0) {
		ptask = find_work_task(WORK_Deferred_Reply, NULL, req_stat_svr_ready);
		if (ptask) {
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
				  "All peer server acks received. Processing pbs_server_ready");
			convert_work_task(ptask, WORK_Immed);
		}
	}
}

/**
 * @brief identify whether the object is a peer server one
 * 
 * @param[in] pobj - object which needs to be verified
 * @return bool
 */
bool
is_peersvr(void *pobj)
{
	server_t *psvr = pobj;

	return (psvr->mi_port == psvr->mi_rmport);
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
static int
send_hello(server_t *psvr)
{
	int rc;
	svrinfo_t *svr_info = psvr->mi_data;
	int stream = svr_info->msr_stream;

	if (!(svr_info->msr_state & INUSE_NEEDS_HELLOSVR))
		return 0;

	rc = send_command(stream, PS_CONNECT);
	if (rc != DIS_SUCCESS)
		goto err;

	svr_info->msr_state &= ~INUSE_NEEDS_HELLOSVR;
	log_eventf(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
		   msg_daemonname, "CONNECT sent to peer server %s at stream:%d", psvr->mi_host, stream);
	return 0;

err:
	log_errf(errno, msg_daemonname, "Failed to send CONNECT to peer server %s at stream:%d", psvr->mi_host, stream);
	tpp_close(stream);
	return -1;
}

/**
 * @brief
 *	Connect to peer server if not connected/hello'd
 *	Send resc update upon success
 *	
 *  @param[in]	hostname	- host name of peer server
 *  @param[in]	hostaddr	- host address of peer server
 *  @param[in]	port		- port of peer server service
 * 
 * @note
 * either hostname or hostaddr is required, not both.
 *
 * @return	server_t
 * @retval	NULL	- Failure
 * @retval	!NULL	- Success
 */
int
connect_to_peersvr(void *psvr)
{
	bool resc_upd_reqd = 0;
	svrinfo_t *svr_info = ((server_t *) psvr)->mi_data;

	if (svr_info->msr_stream < 0 ||
	    (svr_info->msr_state & INUSE_NEEDS_HELLOSVR))
		resc_upd_reqd = 1;

	if (open_conn_stream(psvr) < 0)
		return -1;

	if (send_hello(psvr) < 0)
		return -1;

	if (resc_upd_reqd && svr_info->pending_replies)
		mcast_resc_update_all(psvr);

	return 0;
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
	int i;
	struct sockaddr_in addr;
	server_t *psvr;

	CLEAR_HEAD(peersvrl);
	alien_node_idx = pbs_idx_create(0, 0);

	for (i = 0; i < get_num_servers(); i++) {

		if (!strcmp(pbs_conf.psi[i].name, pbs_conf.pbs_server_name) &&
		    (pbs_conf.psi[i].port == pbs_server_port_dis))
			continue;

		addr.sin_addr.s_addr = 0;
		addr.sin_port = pbs_conf.psi[i].port;

		if ((psvr = create_svr_struct(&addr, pbs_conf.psi[i].name)) == NULL)
			return -1;

		if (connect_to_peersvr(psvr) != 0) {
			log_errf(PBSE_INTERNAL, __func__, "Failed initialization for %s", pbs_conf.psi[i].name);
			return -1;
		}
	}

	return 0;
}

/**
 * @brief
 * 	Used to Create serverer_instance_id which is of the form server_instance_name:server_instance_port
 *
 * @return char *
 * @return NULL - failure
 * @retval !NULL - pointer to server_instance_id
 */
char *
gen_svr_inst_id(void)
{
	char svr_inst_name[PBS_MAXHOSTNAME + 1];
	unsigned int svr_inst_port;
	char *svr_inst_id = NULL;

	if (gethostname(svr_inst_name, PBS_MAXHOSTNAME) == 0)
		get_fullhostname(svr_inst_name, svr_inst_name, PBS_MAXHOSTNAME);

	svr_inst_port = pbs_conf.batch_service_port;

	pbs_asprintf(&svr_inst_id, "%s:%d", svr_inst_name, svr_inst_port);

	return svr_inst_id;
}

/**
 * @brief find the number of peer server replies
 * which needs to be ack'd
 * 
 * @return int 
 */
int
num_pending_peersvr_rply(void)
{
	server_t *psvr;
	int ct = 0;
	svrinfo_t *svr_info;

	for (psvr = GET_NEXT(peersvrl);
	     psvr; psvr = GET_NEXT(psvr->mi_link)) {
		svr_info = psvr->mi_data;
		ct += svr_info->pending_replies;
	}

	return ct;
}

/**
 * @brief Go through peer server list and
 * poke if any of them is down.
 */
void
poke_peersvr(void)
{
	server_t *psvr;

	for (psvr = GET_NEXT(peersvrl);
	     psvr; psvr = GET_NEXT(psvr->mi_link)) {
		connect_to_peersvr(psvr);
	}
}

/**
 * @brief save the resource update to the cache
 * DECR requests will free the corresponding INCR from cache
 * 
 * @param[in,out] pobj - pointer to peer server struct
 * @param[in,out] ru_new  - resource update which needs to be saved
 * @return int 
 * @retval !0 - error code
 */
static int
save_resc_update(void *pobj, psvr_ru_t *ru_new)
{
	psvr_ru_t *ru_old = NULL;
	int rc = 0;
	server_t *psvr = pobj;

	if (!ru_new || !ru_new->jobid)
		return -1;

	pbs_idx_find(psvr->mi_rsc_idx, (void **) &ru_new->jobid, (void **) &ru_old, NULL);
	if (!ru_old && ru_new->op == INCR) {
		if (!psvr->mi_rsc_idx)
			psvr->mi_rsc_idx = pbs_idx_create(0, 0);
		rc = pbs_idx_insert(psvr->mi_rsc_idx, ru_new->jobid, ru_new);
	} else if (ru_old && ru_new->op == DECR) {
		pbs_idx_delete(psvr->mi_rsc_idx, ru_old->jobid);
		delete_clear_link(&ru_old->ru_link);
		free_ru(ru_old);
	} else {
		rc = PBSE_DUPRESC;
		log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_WARNING, __func__,
			   "Duplicate resource update received for job %s , op=%d", ru_new->jobid, ru_new->op);
		delete_clear_link(&ru_new->ru_link);
		free_ru(ru_new);
	}

	return rc;
}

/**
 * @brief handler for resource update from a peer server
 * 
 * @param[in] stream - connection stream
 * @param[in] ru_head - head of resource update list
 * @param[in,out] psvr - peer server object
 */
void
req_resc_update(int stream, pbs_list_head *ru_head, void *psvr)
{
	attribute pexech;
	psvr_ru_t *ru_cur;
	psvr_ru_t *ru_nxt;
	int op = 0;
	int rc = 0;

	for (ru_cur = GET_NEXT(*ru_head); ru_cur; ru_cur = ru_nxt) {

		ru_nxt = GET_NEXT(ru_cur->ru_link);
		log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
			   "received update jobid=%s, op=%d, execvnode=%s",
			   ru_cur->jobid, ru_cur->op, ru_cur->execvnode);

		if (ru_cur->op == INCR)
			op = INCR;

		rc = save_resc_update(psvr, ru_cur);
		if (rc == PBSE_DUPRESC)
			continue;

		update_jobs_on_node(ru_cur->jobid, ru_cur->execvnode, ru_cur->op, ru_cur->share_job);
		job_attr_def[JOB_ATR_exec_vnode].at_decode(&pexech, job_attr_def[JOB_ATR_exec_vnode].at_name,
							   NULL, ru_cur->execvnode);
		update_node_rassn(&pexech, ru_cur->op);

		if (ru_cur->op == DECR) {
			delete_clear_link(&ru_cur->ru_link);
			free_ru(ru_cur);
		}
	}

	/*
	* INCR will result in over-consumption and DECR results in under-utilization.
	* But an under-utilization can be filled in the very next scheduling cycle.
	* So we are only bothering about INCR while sending an ACK.
	*/
	if (op == INCR)
		send_command(stream, PS_RSC_UPDATE_ACK);
}

/**
 * @brief open a multicast fd for all peer servers which are up
 * 
 * @return int
 * @retval -1 : for failure
 */
int
open_ps_mtfd(void)
{
	int mtfd = -1;
	server_t *psvr;
	svrinfo_t *psvr_info;

	for (psvr = GET_NEXT(peersvrl); psvr; psvr = GET_NEXT(psvr->mi_link)) {
		psvr_info = psvr->mi_data;
		if (psvr_info->msr_stream < 0) {
			if (connect_to_peersvr(psvr) < 0)
				continue;
		}

		mcast_add(psvr, &mtfd);
	}

	return mtfd;
}

/**
 * @brief multicast single job's resource usage
 * to all peer servers
 * 
 * @param[in] psvr_ru - resource usage structure
 */
void
mcast_resc_usage(psvr_ru_t *psvr_ru)
{
	int mtfd;
	int ret;
	int incr_ct = 0;

	mtfd = open_ps_mtfd();

	if (mtfd != -1) {
		if (psvr_ru->op == INCR)
			incr_ct++;

		if ((ret = ps_compose(mtfd, PS_RSC_UPDATE)) != DIS_SUCCESS)
			close_streams(mtfd, ret);

		/* broadcast resc usage */
		if ((ret = send_resc_usage(mtfd, psvr_ru, 1, incr_ct)) != DIS_SUCCESS)
			close_streams(mtfd, ret);

		tpp_mcast_close(mtfd);
		mtfd = -1;
	}
}

/**
 * @brief adding an alien node to the cache
 * 
 * @param[in,out] psvr - peer server where the node belongs to
 * @param[in] pnode - alien node structure
 */
static void
add_node_to_cache(server_t *psvr, pbs_node *pnode)
{
	if (!pnode)
		return;

	CLEAR_LINK(pnode->nd_link);
	append_link(&psvr->mi_node_list, &pnode->nd_link, pnode);
	pbs_idx_insert(alien_node_idx, pnode->nd_name, pnode);
}

/**
 * @brief initialize the node from the batch status
 * 
 * @param[in] bstat - batch status 
 * @param[in,out] psvr - peer server structure
 * @return int
 * @retval -1 : for error
 */
int
init_node_from_bstat(struct batch_status *bstat, server_t *psvr)
{
	pbs_node *pnode;
	pbs_list_head attrs;
	struct batch_status *cur;

	for (cur = bstat; cur; cur = cur->next) {
		pnode = calloc(1, sizeof(pbs_node));
		pnode->nd_name = strdup(cur->name);
		pnode->nd_svrflags |= NODE_ALIEN;
		copy_attrl_to_svrattrl(cur->attribs, &attrs);
		if ((decode_attr_db(pnode, &attrs, node_attr_idx, node_attr_def, pnode->nd_attr, ND_ATR_LAST, 0)) != 0) {
			log_errf(PBSE_INTERNAL, __func__, "Decode of node %s received from peer server has failed!",
				 pnode->nd_name);
			free(pnode);
			free_attrlist(&attrs);
			pbs_statfree(bstat);
			return -1;
		}

		add_node_to_cache(psvr, pnode);
		free_attrlist(&attrs);
	}

	pbs_statfree(bstat);
	return 0;
}

/**
 * @brief clear node from the cache and delete the node
 * 
 * @param[in,out] psvr - peer server struct
 */
static void
clear_node_cache(server_t *psvr)
{
	pbs_node *pnode;
	pbs_node *nd_next;

	for (pnode = GET_NEXT(psvr->mi_node_list);
	     pnode; pnode = nd_next) {
		nd_next = GET_NEXT(pnode->nd_link);
		CLEAR_LINK(pnode->nd_link);
		pbs_idx_delete(alien_node_idx, pnode->nd_name);
		free_pnode(pnode);
	}
}

/**
 * @brief clear the old node cache and update with new information
 * 
 * @param[in] stream - connection stream
 * @param[in] bstat - batch status struct
 * @return int 
 * @retval -1 : for error
 */
static int
update_node_cache(int stream, struct batch_status *bstat)
{
	server_t *psvr;

	psvr = tfind2((u_long) stream, 0, &streams);
	if (!psvr)
		return -1;

	log_eventf(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
		   "node stat update received from server %s port %d",
		   psvr->mi_host, psvr->mi_port);

	/* DIFF_STAT TODO - this logic needs to be optimized after diff-stat */
	clear_node_cache(psvr);

	init_node_from_bstat(bstat, psvr);

	return 0;
}

/**
 * @brief
 * 		find_alien_node() - find an alien node by its name
 * @param[in]	nodename	- node being searched
 *
 * @return	strcut pbsnode *
 * @retval	!NULL - success
 * @retval	NULL  - failure
 */
pbs_node *
find_alien_node(char *nodename)
{
	char *pslash;
	pbs_node *node = NULL;

	if (nodename == NULL)
		return NULL;
	if (*nodename == '(')
		nodename++; /* skip over leading paren */
	if ((pslash = strchr(nodename, (int) '/')) != NULL)
		*pslash = '\0';
	if (alien_node_idx == NULL)
		return NULL;
	if (pbs_idx_find(alien_node_idx, (void **) &nodename, (void **) &node, NULL) != PBS_IDX_RET_OK)
		return NULL;

	return node;
}

/**
 * @brief process the status reply from peer server
 * Reply can for any object such as node, resv, job etc
 * 
 * @param[in] c - connection stream
 * @return int 
 * @retval PBSE_* : for failure
 */
int
process_status_reply(int c)
{
	struct batch_status *bstat;
	int obj_type = -1;

	if ((bstat = PBSD_status_get(c, NULL, &obj_type, PROT_TPP)) == NULL)
		return pbs_errno;

	switch (obj_type) {

	case MGR_OBJ_NODE:
		update_node_cache(c, bstat);
		break;

	default:
		break;
	}

	return 0;
}
