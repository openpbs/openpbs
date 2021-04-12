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

extern char	server_host[PBS_MAXHOSTNAME + 1];
extern unsigned int	pbs_server_port_dis;
extern	time_t	time_now;

static int svridx = -1;
pbs_list_head peersvrl;
static void *alien_node_idx;
static msvr_stat_t msvr_stat = {0};

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
 * @brief Get the peersvr from svrid object
 * 
 * @param[in] sv_id - server instance id
 * 
 * @return void*
 * @retval !NULL - success; peer svr object
 * @retval NULL - failure
 */
void *
get_peersvr_from_svrid(char *sv_id)
{
	psi_t psi;
	server_t *psvr;

	if (!sv_id)
		return NULL;

	if (frame_psi(&psi, sv_id) != 0)
		log_errf(PBSE_INTERNAL, __func__,
			 "Failed to parse server instance id %s", sv_id);

	for (psvr = GET_NEXT(peersvrl); psvr; psvr = GET_NEXT(psvr->mi_link)) {
		
		if (is_same_host(psi.name, psvr->mi_host) &&
		    psi.port == psvr->mi_port)
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
 * 	destroy a server_t element
 *
 * @param[in]	psvr	- pointer to peersvr structure
 */
static void
delete_peersvr_entry(server_t *psvr)
{
	svrinfo_t *psvrinfo = psvr->mi_data;

	if (psvrinfo) {
		pbs_idx_destroy(psvrinfo->ps_rsc_idx);
		CLEAR_HEAD(psvrinfo->ps_node_list);
		free(psvrinfo);
	}
	psvr->mi_data = NULL;

	delete_daemon_info(psvr);
	free(psvr);
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
	svrinfo_t *psvr_info;
	server_t *psvr = NULL;
	u_long *pul = NULL;

	if (!hostname && (hostname = get_hostname_from_addr(addr->sin_addr)) == NULL)
		return NULL;

	if (make_host_addresses_list(hostname, &pul))
		return NULL;

	psvr = create_svr_entry(hostname, addr->sin_port);

	if (psvr == NULL) {
		free(pul);
		return psvr;
	}

	if (psvr->mi_data) {
		free(pul);
		return psvr;	/* already there */
	}

	psvr_info = malloc(sizeof(svrinfo_t));
	if (!psvr_info) {
		log_err(PBSE_SYSTEM, __func__, "malloc failed!");
		delete_mom_entry(psvr);
		return NULL;
	}

	psvr_info->ps_pending_replies = 0;
	psvr_info->ps_rsc_idx = pbs_idx_create(0, 0);
	CLEAR_HEAD(psvr_info->ps_node_list);

	psvr->mi_data = psvr_info;

	if (psvr->mi_dmn_info) {
		free(pul);
		return psvr;	/* already there */
	}

	psvr->mi_dmn_info = init_daemon_info(pul, addr->sin_port, psvr);
	if (!psvr->mi_dmn_info) {
		log_err(PBSE_SYSTEM, __func__, "Failed to allocate memory");
		delete_peersvr_entry(psvr);
		return NULL;
	}

	return psvr;
}

/**
 * @brief Get the day avg value for the msvr stat type passed
 * 
 * @param[in] type - msvr stat type
 * @return ulong - day avg rounded off
 */
static ulong
get_day_avg(msvr_stat_type_t type)
{
	return (msvr_stat.stat[type] / ((time_now - msvr_stat.last_logged_tm) / HOUR_IN_SEC)) * 24;
}

/**
 * @brief log multi-server statitistics at most once in a day
 * 
 * @return int
 * @retval 1 - not logged
 * @retval 0 - logged
 */
static int
log_msvr_stat()
{
	if ((time_now - msvr_stat.last_logged_tm) < STAT_LOG_INTL)
		return 1;

	log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
		   "Average msvr statistical info for last 24 hours\n"
		   "{\n\t\"CACHE_MISS\" : %ld,\n"
		   "\t\"CACHE_REFRESH_TM\" : %ld,\n"
		   "\t\"NUM_RESC_UPDATE\" : %ld,\n"
		   "\t\"NUM_MOVE_RUN\" : %ld,\n"
		   "\t\"NUM_SCHED_MISS\" : %ld\n}",
		   get_day_avg(CACHE_MISS),
		   get_day_avg(CACHE_REFR_TM),
		   get_day_avg(NUM_RESC_UPDATE),
		   get_day_avg(NUM_MOVE_RUN),
		   get_day_avg(NUM_SCHED_MISS));

	msvr_stat = (const msvr_stat_t){0};
	msvr_stat.last_logged_tm = time_now;

	return 0;
}

/**
 * @brief update multi-svr stat with the value and for the type provided.
 * This function is event driven and should not be invoked in a non-msvr case.
 * 
 * @param[in] val - stat value
 * @param[in] type - msvr stat type
 */
void
update_msvr_stat(ulong val, msvr_stat_type_t type)
{
	msvr_stat.stat[type] += val;

	log_msvr_stat();
}

/**
 * @brief free the resource update structure
 * 
 * @param[in,out] ru_head - head of the resource update object list
 */
void
free_psvr_ru(psvr_ru_t *ru_head)
{
	psvr_ru_t *ru_cur;
	psvr_ru_t *ru_nxt;

	if (!ru_head)
		return;

	for (ru_cur = ru_head; ru_cur; ru_cur = ru_nxt) {
		ru_nxt = GET_NEXT(ru_cur->ru_link);
		free(ru_cur->jobid);
		free(ru_cur->execvnode);
		free(ru_cur);
	}
}

/**
 * @brief initialize resource usage structure based on parameters
 * 
 * @param[in] pjob - job pointer
 * @param[in] op - operation performed - INCR/DECR
 * @param[in] exec_vnode - exec_vnode string
 * @param[in] broadcast - whether request needs to be broadcasted
 * @return psvr_ru_t* 
 * @retval NULL - on failure
 */
psvr_ru_t *
init_psvr_ru(job *pjob, int op, char *exec_vnode, bool broadcast)
{
	psvr_ru_t *psvr_ru = calloc(1, sizeof(psvr_ru_t));
	if (!psvr_ru)
		goto err;

	psvr_ru->jobid = strdup(pjob->ji_qs.ji_jobid);
	if (!psvr_ru->jobid)
		goto err;

	psvr_ru->execvnode = strdup(exec_vnode);
	if (!psvr_ru->execvnode)
		goto err;

	psvr_ru->op = op;
	psvr_ru->share_job = get_job_share_type(pjob);
	CLEAR_LINK(psvr_ru->ru_link);
	psvr_ru->broadcast = broadcast;

	return psvr_ru;

err:
	free_psvr_ru(psvr_ru);
	log_err(PBSE_SYSTEM, __func__, "Failed to allocate memory!!");
	return NULL;
}

/**
 * @brief reverse any resource update in the resource usage list
 * 
 * This happens when we receive a full update from one of the peer server.
 * We need to reverse any udate from that server before applying
 * to avoid duplicate updates.
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
		log_eventf(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG, ru_cur->jobid,
			   "Reversing resc update op=%d, execvnode=%s", ru_cur->op, ru_cur->execvnode);
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
	int i;

	CLEAR_HEAD(ru_head);

	strms = tpp_mcast_members(mtfd, &count);
	for (i = 0; i < count; i++) {
		if ((psvr = tfind2((u_long) strms[i], 0, &streams)) != NULL)
			((svrinfo_t *) psvr->mi_data)->ps_pending_replies = 0;
	}

	for (pjob = GET_NEXT(svr_alljobs); pjob;
	     pjob = GET_NEXT(pjob->ji_alljobs)) {
		if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_RescUpdt_Rqd) &&
		    (pjob->ji_qs.ji_svrflags & JOB_SVFLG_RescAssn)) {
			psvr_ru = init_psvr_ru(pjob, INCR, pjob->ji_wattr[JOB_ATR_exec_vnode].at_val.at_str, FALSE);
			if (psvr_ru) {
				append_link(&ru_head, &psvr_ru->ru_link, psvr_ru);
				ct++;
			}
		}
	}

	if (ct == 0)
		return 0;

	rc = ps_compose(mtfd, PS_RSC_UPDATE_FULL);
	if (rc != DIS_SUCCESS)
		goto end;

	/* 
	* passing both incr_ct and tot_ct as ct as we only send INCR here
	* This is done for a full update where we only send values peer-svr
	* needs to account for, hence INCR.
	*/
	rc = send_resc_usage(mtfd, GET_NEXT(ru_head), ct, ct);

end:
	if (rc != DIS_SUCCESS)
		close_streams(mtfd, rc);
	free_psvr_ru(GET_NEXT(ru_head));
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

	if ((psvr = tfind2(conn, 0, &streams)) != NULL) {
		pending_rply = &((svrinfo_t *) psvr->mi_data)->ps_pending_replies;
		if (*pending_rply)
			*pending_rply -= 1;
		else
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ALERT, __func__,
				  "pending_rply went negative... Re-setting to zero");
	} else {
		log_errf(-1, __func__, "Resource update from unknown stream %d", conn);
		return;
	}

	if (*pending_rply == 0 && pending_ack_svr() == NULL) {
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

	return (psvr && (psvr->mi_port == psvr->mi_rmport));
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
send_connect(server_t *psvr)
{
	int rc;
	dmn_info_t *dmn_info = psvr->mi_dmn_info;
	int stream = dmn_info->dmn_stream;

	if (!(dmn_info->dmn_state & INUSE_NEEDS_HELLOSVR))
		return 0;

	rc = send_command(stream, PS_CONNECT);
	if (rc != DIS_SUCCESS)
		goto err;

	dmn_info->dmn_state &= ~INUSE_NEEDS_HELLOSVR;
	log_eventf(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_NOTICE,
		   msg_daemonname, "CONNECT sent to peer server %s at stream:%d", psvr->mi_host, stream);
	return 0;

err:
	log_errf(errno, msg_daemonname, "Failed to send CONNECT to peer server %s at stream:%d", psvr->mi_host, stream);
	stream_eof(stream, rc, "write_err");
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
	svrinfo_t *svr_info;
	dmn_info_t *dmn_info;
	bool resc_upd_reqd = 0;

	if (!psvr)
		return -1;

	svr_info = ((server_t *) psvr)->mi_data;
	dmn_info = ((server_t *) psvr)->mi_dmn_info;

	if (dmn_info->dmn_stream < 0 ||
	    (dmn_info->dmn_state & INUSE_NEEDS_HELLOSVR))
		resc_upd_reqd = 1;

	if (open_conn_stream(psvr) < 0)
		return -1;

	if (send_connect(psvr) < 0)
		return -1;

	if (resc_upd_reqd && svr_info->ps_pending_replies)
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

		if (pbs_conf.psi[i].port == pbs_server_port_dis &&
		    is_same_host(pbs_conf.psi[i].name, server_host)) {
			svridx = i;
			continue;
		    }

		addr.sin_addr.s_addr = 0;
		addr.sin_port = pbs_conf.psi[i].port;

		if ((psvr = create_svr_struct(&addr, pbs_conf.psi[i].name)) == NULL) {
			log_errf(PBSE_INTERNAL, __func__, "Failed initialization for peer server; name: %s, port: %d",
				 pbs_conf.psi[i].name, pbs_conf.psi[i].port);
			return -1;
		}

		if (connect_to_peersvr(psvr) != 0) {
			log_errf(PBSE_INTERNAL, __func__, "Failed to connect to peer server; host=%s, port=%d",
				 pbs_conf.psi[i].name, pbs_conf.psi[i].port);
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
 * @retval !NULL - pointer to server_instance_id (do NOT free the return value)
 */
char *
gen_svr_inst_id(void)
{
	static char *svr_inst_id = NULL;

	if (svr_inst_id == NULL) {
		unsigned int svr_inst_port;
		char svr_inst_name[PBS_MAXHOSTNAME + 1];

		if (gethostname(svr_inst_name, PBS_MAXHOSTNAME) == 0)
			get_fullhostname(svr_inst_name, svr_inst_name, PBS_MAXHOSTNAME);

		svr_inst_port = pbs_conf.batch_service_port;
		pbs_asprintf(&svr_inst_id, "%s:%d", svr_inst_name, svr_inst_port);
	}

	return svr_inst_id;
}

/**
 * @brief	Calculate the index of the current server
 *
 * @param	void
 *
 * @return	int
 * @retval	index of the server
 * @retval	-1 if couldn't be determined (see init_msi)
 */
int
get_server_index(void)
{
	return svridx;
}

/**
 * @brief return the first peer-svr with pending replies
 * 
 * @return server_t *
 * @retval !NULL - peer-svr
 * @retval NULL - no reply pending
 */
void *
pending_ack_svr(void)
{
	server_t *psvr;

	for (psvr = GET_NEXT(peersvrl);
	     psvr; psvr = GET_NEXT(psvr->mi_link)) {
		if (((svrinfo_t *) psvr->mi_data)->ps_pending_replies)
			return psvr;
	}

	return NULL;
}

/**
 * @brief Go through peer server list and
 * poke if any of them is down.
 * 
 * If the application layer came to know about the network failure,
 * it will close the peer server connection.
 * The server will periodically attempt to re-connect and
 * the initial exchange will get triggered upon reconnecting.
 * 
 * poke is one such re-connecting mechanism.
 * Peer-server will also attempts to reconnect when it has some data
 * to be sent to peer server in the form of resource usage / commands.
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
 * set_resc_assigned() will sent a DECR corresponding to every INCR.
 * This logic is based on the above assumption.
 * This function logs dupilcate resource update if it receives same operation
 * consecutively.
 * 
 * @param[in,out] pobj - pointer to peer server struct
 * @param[in,out] ru_new  - resource update which needs to be saved
 * @return int 
 * @retval !0 - error code
 * @retval 0 - success
 */
static int
save_resc_update(void *pobj, psvr_ru_t *ru_new)
{
	psvr_ru_t *ru_old = NULL;
	int rc = 0;
	svrinfo_t *psvr_info = ((server_t *)pobj)->mi_data;

	if (!ru_new || !ru_new->jobid)
		return -1;

	pbs_idx_find(psvr_info->ps_rsc_idx, (void **) &ru_new->jobid, (void **) &ru_old, NULL);
	if (!ru_old && ru_new->op == INCR) {
		if (!psvr_info->ps_rsc_idx)
			psvr_info->ps_rsc_idx = pbs_idx_create(0, 0);
		rc = pbs_idx_insert(psvr_info->ps_rsc_idx, ru_new->jobid, ru_new);
	} else if (ru_old && ru_new->op == DECR) {
		pbs_idx_delete(psvr_info->ps_rsc_idx, ru_old->jobid);
		delete_clear_link(&ru_old->ru_link);
		free_psvr_ru(ru_old);
	} else {
		rc = PBSE_DUPRESC;
		log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_WARNING, ru_new->jobid,
			   "Duplicate resource update received with op=%d", ru_new->op);
		delete_clear_link(&ru_new->ru_link);
		free_psvr_ru(ru_new);
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
		log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, ru_cur->jobid,
			   "received update op=%d, execvnode=%s", ru_cur->op, ru_cur->execvnode);

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
			free_psvr_ru(ru_cur);
		}
	}

	/*
	* Unacknowleged INCR will result in over-consumption and DECR results in under-utilization.
	* But an under-utilization can be filled in the very next scheduling cycle.
	* So we are only bothered about INCR while sending an ACK.
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

	for (psvr = GET_NEXT(peersvrl); psvr; psvr = GET_NEXT(psvr->mi_link)) {
		if (psvr->mi_dmn_info->dmn_stream < 0) {
			if (connect_to_peersvr(psvr) < 0)
				continue;
		}

		mcast_add(psvr, &mtfd, FALSE);
	}

	return mtfd;
}

/**
 * @brief multicast single job's resource usage
 * to all peer servers
 * 
 * @param[in] psvr_ru - resource usage structure
 * @param[in] mtfd - mutlicast fd
 */
void
mcast_resc_usage(psvr_ru_t *psvr_ru, int mtfd)
{
	int ret;
	int incr_ct = 0;

	if (!psvr_ru)
		return;

	if (mtfd == -1 || psvr_ru->broadcast) {
		tpp_mcast_close(mtfd);
		mtfd = open_ps_mtfd();
	}

	/* only INCR's added to pending acks count */
	if (psvr_ru->op == INCR)
		incr_ct++;

	if ((ret = ps_compose(mtfd, PS_RSC_UPDATE)) != DIS_SUCCESS) {
		close_streams(mtfd, ret);
		return;
	}

	/* broadcast resc usage */
	if ((ret = send_resc_usage(mtfd, psvr_ru, 1, incr_ct)) != DIS_SUCCESS) {
		close_streams(mtfd, ret);
		return;
	}

	tpp_mcast_close(mtfd);
}

/**
 * @brief adding an alien node to the cache
 * 
 * @param[in,out] psvr - peer server where the node belongs to
 * @param[in,out] pnode - alien node structure
 */
static void
add_node_to_psvr_cache(server_t *psvr, pbs_node *pnode)
{
	if (!psvr || !pnode)
		return;

	svrinfo_t *psvrinfo = psvr->mi_data;

	CLEAR_LINK(pnode->nd_link);
	append_link(&psvrinfo->ps_node_list, &pnode->nd_link, pnode);
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
	int rc = 0;

	for (cur = bstat; cur; cur = cur->next) {

		pnode = calloc(1, sizeof(pbs_node));
		if (!pnode) {
			log_errf(PBSE_SYSTEM, __func__, "Failed to allocate memory for pnode");
			rc = -1;
			continue;
		}

		pnode->nd_name = strdup(cur->name);
		if (!pnode->nd_name) {
			free(pnode);
			log_errf(PBSE_SYSTEM, __func__, "Failed to strdup");
			rc = -1;
			continue;
		}

		pnode->nd_svrflags |= NODE_ALIEN;
		convert_attrl_to_svrattrl(cur->attribs, &attrs);
		if ((decode_attr_db(pnode, &attrs, node_attr_idx, node_attr_def, pnode->nd_attr, ND_ATR_LAST, 0)) != 0) {
			log_errf(PBSE_INTERNAL, __func__, "Decoding of node %s received from peer server has failed!",
				 pnode->nd_name);
			free(pnode);
			free_attrlist(&attrs);
			pbs_statfree(bstat);
			rc = -1;
		}

		add_node_to_psvr_cache(psvr, pnode);
		free_attrlist(&attrs);
	}

	pbs_statfree(bstat);
	return rc;
}

/**
 * @brief clears all nodes belongs to this server
 * from the cache and delete those nodes.
 * 
 * @param[in,out] psvr - peer server struct
 */
static void
clear_node_cache(server_t *psvr)
{
	pbs_node *pnode;
	pbs_node *nd_next;
	svrinfo_t *psvrinfo = psvr->mi_data;

	for (pnode = GET_NEXT(psvrinfo->ps_node_list); pnode; pnode = nd_next) {
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

	log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__,
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
 * @see find_nodebyname
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
	time_t time_start = time(NULL);

	if ((bstat = PBSD_status_get(c, NULL, &obj_type, PROT_TPP)) == NULL)
		return pbs_errno;

	switch (obj_type) {

	case MGR_OBJ_NODE:
		update_node_cache(c, bstat);
		break;

	default:
		break;
	}

	update_msvr_stat(time(NULL) - time_start, CACHE_REFR_TM);

	return 0;
}
