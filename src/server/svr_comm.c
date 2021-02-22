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
 *		Functions related to peer server communications.
 *
 */


#include	"dis.h"
#include	"server.h"
#include	"batch_request.h"
#include	"tpp.h"
#include	"log.h"
#include	"pbs_nodes.h"
#include	"svrfunc.h"


extern	time_t	time_now;


static int mtfd_replyhello_psvr = -1;


/**
 * @brief send a command using peer server protocol
 * 
 * @param[in] c - connection stream
 * @param[in] command - command which needs to be sent
 * @return int
 * @retval 0 : success
 * @retval PBSE_* : pbs error number
 */
int
send_command(int c, int command)
{
	int rc;

	rc = ps_compose(c, command);
	if (rc != DIS_SUCCESS)
		goto err;

	pbs_errno = PBSE_NONE;
	if ((rc = dis_flush(c)) != DIS_SUCCESS) {
		pbs_errno = PBSE_PROTOCOL;
		goto err;
	}

	return 0;

err:
	log_errf(pbs_errno, __func__, "%s from stream %d",
		 dis_emsg[rc], c);
	stream_eof(c, rc, "write_err");
	return pbs_errno;
}

/**
 * @brief mcast all the resource update to the needy
 * 
 * @param psvr 
 */
void
mcast_resc_update_all(void *psvr)
{
	struct work_task *ptask;

	if (mtfd_replyhello_psvr == -1) {
		ptask = set_task(WORK_Immed, 0, mcast_msg, NULL);
		ptask->wt_aux = PS_CONNECT;
	}

	mcast_add(psvr, &mtfd_replyhello_psvr);
}

/**
 * @brief encodes and send resource usage
 * 
 * @param[in] c - connection stream
 * @param[in] psvr_ru - peer server update
 * @param[in] ct - count of total resource update packets
 * @param incr_ct - count of increment packets
 * @return int
 * @retval !0 : DIS error code
 */
int
send_resc_usage(int c, psvr_ru_t *psvr_ru, int ct, int incr_ct)
{
	int rc;
	psvr_ru_t *ru_cur = NULL;
	server_t *psvr;

	/* account messages sent */
        for (psvr = GET_NEXT(peersvrl);
	     psvr; psvr = GET_NEXT(psvr->mi_link)) {
		((svrinfo_t *) (psvr->mi_data))->num_pending_rply += (incr_ct ? 1 : 0);
	}

	if ((rc = diswsi(c, ct)) != 0)
		goto err;

	for (ru_cur = psvr_ru; ru_cur; ru_cur = GET_NEXT(ru_cur->ru_link)) {
		log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
			   __func__, "sending resc update jobid=%s, op=%d, execvnode=%s",
			   ru_cur->jobid, ru_cur->op, ru_cur->execvnode);
		if ((rc = diswcs(c, ru_cur->jobid, strlen(ru_cur->jobid)) != 0) ||
		    (rc = diswsi(c, ru_cur->op) != 0) ||
		    (rc = diswcs(c, ru_cur->execvnode, strlen(ru_cur->execvnode)) != 0) ||
		    (rc = diswsi(c, ru_cur->share_job) != 0))
			goto err;
	}

	if ((rc = dis_flush(c)) != DIS_SUCCESS) {
		pbs_errno = PBSE_PROTOCOL;
		goto err;
	}

	return 0;
err:
	log_errf(pbs_errno, __func__, "%s from stream %d",
		 dis_emsg[rc], c);
	close_streams(c, rc);
	return rc;
}

/**
 * @brief read resource update info from socket
 * 
 * @param[in] sock - connection socket
 * @param[in] ru_head - head of resource update head
 * @return int
 * @retval -1 : for error
 */
static int
read_resc_update(int sock, pbs_list_head *ru_head)
{
	int rc;
	int ct;
	size_t sz;
	int i;
        psvr_ru_t *ru_cur = NULL;

        CLEAR_HEAD((*ru_head));

	ct = disrsi(sock, &rc);

	for (i = 0; i < ct; i++) {
                ru_cur = calloc(1, sizeof(psvr_ru_t));
		ru_cur->jobid = disrcs(sock, &sz, &rc);
		if (rc)
                        goto err;

		ru_cur->op = disrsi(sock, &rc);
		if (rc)
			goto err;

		ru_cur->execvnode = disrcs(sock, &sz, &rc);
		if (rc)
                        goto err;

		ru_cur->share_job = disrsi(sock, &rc);
		if (rc)
			goto err;

                CLEAR_LINK(ru_cur->ru_link);
                append_link(ru_head, &ru_cur->ru_link, ru_cur);
	}

        return 0;

err:
        free_ru(ru_cur);
        free_ru(GET_NEXT(*ru_head));
	return -1;
}

/**
 * @brief reply to connect message from peer server
 * sends all the resource update which needs to be updated
 * 
 */
void
replyhello_psvr(void)
{
        int rc;

        if (mtfd_replyhello_psvr != -1) {
                rc = send_job_resc_updates(mtfd_replyhello_psvr);
		if (rc != DIS_SUCCESS)
                        close_streams(mtfd_replyhello_psvr, rc);
	}

        tpp_mcast_close(mtfd_replyhello_psvr);
        mtfd_replyhello_psvr = -1;
}

/**
 * @brief send a node stat request to peer server
 * 
 */
void
send_nodestat(void)
{
	struct attrl *pat;
	struct attrl *head;
	struct attrl *tail;
	struct attrl *tmp;
	int mtfd = open_ps_mtfd();
	int rc;
	static int time_last_sent = 0;

	/* Do not udate the cache too often */
	if (time_now < time_last_sent + 2)
		return;

	time_last_sent = time_now;
	
	if (mtfd == -1)
		return;

	pat = calloc(1, sizeof(struct attrl));
	pat->name = ATTR_NODE_Mom;
	head = tail = pat;
	pat = calloc(1, sizeof(struct attrl));
	pat->name = ATTR_NODE_Port;
	tail->next = pat;
	tail = tail->next;
	pat = calloc(1, sizeof(struct attrl));
	pat->name = ATTR_server_inst_id;
	tail->next = pat;
	tail = tail->next;

	rc =  PBSD_status_put(mtfd,
		PBS_BATCH_StatusNode,
		"", head, NULL, PROT_TPP, NULL);
	if (rc)
		close_streams(mtfd, rc);

	for(pat = head; pat != NULL; pat = tmp) {
		tmp = pat->next;
		free(pat);
	}
	tpp_mcast_close(mtfd);
	mtfd = -1;
}

/**
 * @brief
 * 		Input is coming from peer server over a TPP stream.
 *
 * @par
 *		Read the stream to get a Peer-Server request.
 *
 * @param[in] stream  - TPP stream on which the request is arriving
 * @param[in] version - Version of protocol.
 *
 * @return none
 */
void
ps_request(int stream, int version)
{
        server_t        *psvr;
        int             ret = 0;
	int 		rc = 0;
        int             command;
        struct	sockaddr_in	*addr;
        svrinfo_t *psvr_info;
        pbs_list_head ru_head;

        DBPRT(("%s: stream %d version %d\n", __func__, stream, version))
	addr = tpp_getaddr(stream);
	if (version != PS_PROTOCOL_VER) {
		log_errf(-1, __func__, "protocol version %d unknown from %s",
			version, netaddr(addr));
		stream_eof(stream, 0, NULL);
		return;
	}
	if (addr == NULL) {
		log_err(-1, __func__, "Sender unknown");
		stream_eof(stream, 0, NULL);
		return;
	}

	command = disrsi(stream, &ret);
	if (ret != DIS_SUCCESS)
		goto badcon;

        if (command == PS_CONNECT) {
		if ((psvr = get_peersvr(addr)) == NULL)
                        goto badcon;

                log_eventf(PBSEVENT_SYSTEM, PBS_EVENTCLASS_SERVER, LOG_INFO, __func__, 
                                "Peer server connected from %s", netaddr(addr));
                psvr_info = psvr->mi_data;
		if (psvr_info->msr_stream >= 0 && psvr_info->msr_stream != stream) {
			DBPRT(("%s: stream %d from %s:%d already open on %d\n",
				__func__, stream, pmom->mi_host,
				ntohs(addr->sin_port), psvr_info->msr_stream))
			tpp_close(psvr_info->msr_stream);
			tdelete2((u_long)psvr_info->msr_stream, 0ul, &streams);
		}
		/* we save this stream for future communications */
		psvr_info->msr_stream = stream;
		psvr_info->msr_state &= ~INUSE_NEEDS_HELLOSVR;
                tinsert2((u_long)stream, 0ul, psvr, &streams);
		tpp_eom(stream);
		/* mcast reply togethor, but do not wait */
		mcast_resc_update_all(psvr);
		return;
        } else if ((psvr = tfind2((u_long)stream, 0, &streams)) != NULL)
		goto found;

badcon:
	sprintf(log_buffer, "bad attempt to connect from %s", netaddr(addr));
	log_err(-1, __func__, log_buffer);
	stream_eof(stream, 0, NULL);
	return;

found:

        switch (command) {

		case PS_RSC_UPDATE_ACK:
			req_peer_svr_ack(stream);
			break;

		case PS_RSC_UPDATE_FULL:
			clean_saved_rsc(psvr->mi_rsc_idx);
			rc = read_resc_update(stream, &ru_head);
			if (rc != 0)
				goto err;
                        req_resc_update(stream, &ru_head, psvr);
			break;

		case PS_RSC_UPDATE:
			rc = read_resc_update(stream, &ru_head);
			if (rc != 0)
				goto err;
                        req_resc_update(stream, &ru_head, psvr);
			break;

		case PS_STAT_RPLY:
			rc = process_status_reply(stream);
			if (rc != 0)
				goto err;
			break;

		default:
			sprintf(log_buffer, "unknown command %d sent from %s",
				command, psvr->mi_host);
			log_err(-1, __func__, log_buffer);
			goto err;
	}

	tpp_eom(stream);
	return;

err:
	/*
	 ** We come here if we got a DIS write error.
	 */
	DBPRT(("\nINTERNAL or DIS i/o error\n"))
	if (ret != 0) {
		log_errf(-1, __func__, "%s from %s(%s)",
			 dis_emsg[ret], psvr->mi_host, netaddr(addr));
		stream_eof(stream, ret, "write_err");
	} else {
		log_errf(rc, __func__, "Error processing command %d from peer server %s",
			 command, psvr->mi_host);
		stream_eof(stream, ret, "read_err");
	}

	return;
}