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
 * @file	tpp_router.c
 *
 * @brief	Router part of the TCP router based network
 *
 * @par		Functionality:
 *
 *		TPP = TCP based Packet Protocol. This layer uses TCP in a multi-
 *		hop router based network topology to deliver packets to desired
 *		destinations. LEAF (end) nodes are connected to ROUTERS via
 *		persistent TCP connections. The ROUTER has intelligence to route
 *		packets to appropriate destination leaves or other routers.
 *
 *		This is the router part in the tpp network topology.
 *		This compiles into the router process, and is
 *		linked to the PBS comm.
 *
 */
#include <pbs_config.h>
#if RWLOCK_SUPPORT == 2
#if !defined (_XOPEN_SOURCE)
#define _XOPEN_SOURCE 500
#endif
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#ifdef PBS_COMPRESSION_ENABLED
#include <zlib.h>
#endif
#include "pbs_idx.h"
#include "tpp_internal.h"
#include "auth.h"

#define RLIST_INC 100

struct tpp_config *tpp_conf; /* copy of the global tpp_config */

pthread_rwlock_t router_lock; /* rw lock for router avl trees, searches over avl should be thread safe now */
pthread_mutex_t lj_lock;

/* index of routers connected to this router */
void *routers_idx = NULL;

/* index of all leaves in the cluster */
void *cluster_leaves_idx = NULL;

/* index of special routers who need to be notified for join updates */
void *my_leaves_notify_idx = NULL;
time_t router_last_leaf_joined = 0;

static int router_send_ctl_join(int tfd, void *data, void *c);

/* forward declarations */
static int router_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *c, void *extra);
static int router_pkt_handler(int phy_fd, void *data, int len, void *c, void *extra);
static int router_pkt_handler_inner(int tfd, void *buf, void **data_out, int len, void *c, void *extra);
static int router_close_handler(int phy_con, int error, void *c, void *extra);
static int send_leaves_to_router(tpp_router_t *parent, tpp_router_t *target);
static tpp_router_t *get_preferred_router(tpp_leaf_t *l, tpp_router_t *this_router, int *fd);
static int add_route_to_leaf(tpp_leaf_t *l, tpp_router_t *r, int index);
static tpp_router_t *del_router_from_leaf(tpp_leaf_t *l, int tfd);
static int leaf_get_router_index(tpp_leaf_t *l, tpp_router_t *r);
static int router_timer_handler(time_t now);
static int router_post_connect_handler(int tfd, void *data, void *c, void *extra);

/* structure identifying this router */
static tpp_router_t *this_router = NULL;

static tpp_router_t *
alloc_router(char *name, tpp_addr_t *address)
{
	tpp_router_t *r;
	tpp_addr_t *addrs = NULL;
	int count = 0;
	void *unused;
	void *p_r_addr;

	/* add self name to tree */
	r = (tpp_router_t *) calloc(1, sizeof(tpp_router_t));
	if (!r) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating pbs_comm data");
		return NULL;
	}

	r->conn_fd = -1;
	r->router_name = name;
	r->initiator = 0;
	r->index = 0; /* index is not used between routers */
	r->state = TPP_ROUTER_STATE_DISCONNECTED;

	if (address == NULL) {
		/* do name resolution on the supplied name */
		addrs = tpp_get_addresses(r->router_name, &count);
		if (!addrs) {
			tpp_log(LOG_CRIT, __func__, "Failed to resolve address, pbs_comm=%s", r->router_name);
			free_router(r);
			return NULL;
		}
		memcpy(&r->router_addr, addrs, sizeof(tpp_addr_t));
		free(addrs);
	} else {
		memcpy(&r->router_addr, address, sizeof(tpp_addr_t));
	}

	/* initialize the routers leaf tree */
	r->my_leaves_idx = pbs_idx_create(0, sizeof(tpp_addr_t));
	if (r->my_leaves_idx == NULL) {
		tpp_log(LOG_CRIT, __func__, "Failed to create index for my leaves");
		free_router(r);
		return NULL;
	}

	p_r_addr = &r->router_addr;
	if (pbs_idx_find(routers_idx, &p_r_addr, &unused, NULL) == PBS_IDX_RET_OK) {
		tpp_log(LOG_CRIT, __func__, "Duplicate router %s in router list", r->router_name);
		free_router(r);
		return NULL;
	}

	if (pbs_idx_insert(routers_idx, &r->router_addr, r) != PBS_IDX_RET_OK) {
		tpp_log(LOG_CRIT, __func__, "Failed to add router %s in routers index", r->router_name);
		free_router(r);
		return NULL;
	}

	return r;
}

/*
 * Convenience function to log a no route message in the logs
 */
void
log_noroute(tpp_addr_t *src_host, tpp_addr_t *dest_host, int src_sd, char *msg)
{
	char src[TPP_MAXADDRLEN + 1];
	char dest[TPP_MAXADDRLEN + 1];

	strncpy(src, tpp_netaddr(src_host), TPP_MAXADDRLEN);
	strncpy(dest, tpp_netaddr(dest_host), TPP_MAXADDRLEN);

	tpp_log(LOG_ERR, NULL, "Pkt from src=%s[%d], noroute to dest=%s, %s", src, src_sd, dest, msg);
}

/**
 * @brief
 *	When a router joins, send all the leaves connected to that router to
 *	other routers.
 *
 * @param[in] parent - router whose leaves are to be sent
 * @param[in] target - router to which the leaves must be sent
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	This routine expects to be called with the "router_lock" and
 *	will unlock the router_lock before exiting.
 *
 * @par MT-safe: Yes
 *
 */
static int
send_leaves_to_router(tpp_router_t *parent, tpp_router_t *target)
{
	tpp_leaf_t *l;
	tpp_que_t leaf_packets;
	tpp_packet_t *pkt = NULL;
	int index;
	tpp_join_pkt_hdr_t *hdr = NULL;
	void *idx_ctx = NULL;

	TPP_QUE_CLEAR(&leaf_packets);

	TPP_DBPRT("Sending leaves to router=%s", target->router_name);

	/* traverse my leaves tree, there is only one record per leaf */
	while (pbs_idx_find(parent->my_leaves_idx, NULL, (void **)&l, &idx_ctx) == PBS_IDX_RET_OK) {
		index = leaf_get_router_index(l, this_router);
		if (index == -1) {
			tpp_log(LOG_CRIT, __func__, "Could not find index of my router in leaf's pbs_comm list");
			goto err;
		}

		/* create a new pkt and add the dhdr chunk first */
		pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_join_pkt_hdr_t), 1, (void **) &hdr);
		if (!pkt) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			goto err;
		}
		/* save hdr and addrs to be sent outside of locks */
		hdr->type = TPP_CTL_JOIN;
		hdr->node_type = l->leaf_type;
		hdr->hop = 2;
		hdr->index = index;
		hdr->num_addrs = l->num_addrs;

		/* add the addresses */
		if (!tpp_bld_pkt(pkt, l->leaf_addrs, sizeof(tpp_addr_t) * l->num_addrs, 1, NULL)) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			goto err;
		}

		if (tpp_enque(&leaf_packets, pkt) == NULL) {
			tpp_log(LOG_CRIT, __func__, "Out of memory enqueuing to leaf_packets");
			goto err;
		}
	}
	pbs_idx_free_ctx(idx_ctx);
	
	while ((pkt = (tpp_packet_t *) tpp_deque(&leaf_packets))) {
		if (tpp_transport_vsend(target->conn_fd, pkt) != 0) {
			tpp_log(LOG_ERR, __func__, "Send leaves to pbs_comm %s failed", target->router_name);
			/* let the dequeue continue to happen and attempt to send happen */
			/* vsend will free packets even in case of failure */
		}
	}

	return 0;

err:
	/* we jump to the error block only before starting to send, so safe to clear the queue */
	tpp_log(LOG_CRIT, __func__, "Error sending leaves to router %s", target->router_name);

	pbs_idx_free_ctx(idx_ctx);

	while ((pkt = (tpp_packet_t *) tpp_deque(&leaf_packets))) /* drain the list and free packets */
		tpp_free_pkt(pkt);

	return -1;
}

/**
 * @brief
 *	Broadcast the given data packet to all the routers connected to this
 *	router
 *
 * @param[in] - chunks - Chunks of data that needs to be sent to routers
 * @param[in] - count  - Number of chunks in the count array
 * @param[in] - origin_tfd - This routers physical connection descriptor
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	This function is not guarded by an lock around it. So it should be called 
 *  under a lock
 *
 * @par MT-safe: No
 *
 */
static int
broadcast_to_my_routers(tpp_chunk_t *chunks, int count, int origin_tfd)
{
	tpp_router_t *r;
	tpp_que_t router_list;
	void *idx_ctx = NULL;

	TPP_QUE_CLEAR(&router_list);

	while (pbs_idx_find(routers_idx, NULL, (void **)&r, &idx_ctx) == PBS_IDX_RET_OK) {
		if (r->conn_fd == -1 || r == this_router || r->conn_fd == origin_tfd || r->state != TPP_ROUTER_STATE_CONNECTED) {
			continue; /* don't send to self, or to originating router */
		}
		if (tpp_enque(&router_list, r) == NULL) {
			tpp_log(LOG_CRIT, __func__, "Out of memory enqueuing to router_list");
			pbs_idx_free_ctx(idx_ctx);
			goto err;
		}
	}
	pbs_idx_free_ctx(idx_ctx);

	while ((r = (tpp_router_t *) tpp_deque(&router_list))) {
		int j;
		tpp_packet_t *pkt = NULL;

		for (j = 0; j < count; j++) {
			pkt = tpp_bld_pkt(pkt, chunks[j].data, chunks[j].len, 1, NULL);
			if (!pkt) {
				tpp_log(LOG_CRIT, __func__, "Failed to build packet");
				goto err;
			}
		}

		if (tpp_transport_vsend(r->conn_fd, pkt) != 0) {
			TPP_DBPRT("Broadcasting leaf to router %s", r->router_name);
			if (errno != ENOTCONN) {
				tpp_log(LOG_ERR, __func__, "send failed");
				goto err;
			}
			/* vsend will free packets even in case of failure */
		}
	}
	return 0;

err:
	tpp_log(LOG_CRIT, __func__, "Error broadcasting to my routers");
	while (tpp_deque(&router_list)); /* drain the list, dont free packets, transport will free */
	return -1;
}

/**
 * @brief
 *	Broadcast the given data packet to all the leaves connected to this
 *	router
 *
 * @param[in] - chunks - Chunks of data that needs to be sent to routers
 * @param[in] - count  - Number of chunks in the count array
 * @param[in] - origin_tfd - This routers physical connection descriptor
 * @param[in] - type  0 - Notify all leaves
 *                    1 - Notify only listen leaves
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @note
 *   This function is not guarded by an lock around it. So it should be called 
 *   under a lock
 *
 * @par MT-safe: No
 *
 */
static int
broadcast_to_my_leaves(tpp_chunk_t *chunks, int count, int origin_tfd, int type)
{
	tpp_leaf_t *l;
	void *traverse_idx = NULL;
	void *idx_ctx = NULL;
	tpp_que_t leaf_list;

	TPP_QUE_CLEAR(&leaf_list);

	if (type == 1)
		traverse_idx = my_leaves_notify_idx;
	else
		traverse_idx = this_router->my_leaves_idx;

	while (pbs_idx_find(traverse_idx, NULL, (void **)&l, &idx_ctx) == PBS_IDX_RET_OK) {
		/*
		 * leaf directly connected to me? and not myself
		 * and is interested in events
		 */
		if (l->conn_fd != -1 && l->conn_fd != origin_tfd) {

			/* if type is 1, notify only listen leaves */
			if (type == 1 && l->leaf_type != TPP_LEAF_NODE_LISTEN)
				continue;

			if (tpp_enque(&leaf_list, l) == NULL) {
				tpp_log(LOG_CRIT, __func__, "Out of memory enqueuing to leaf_list");
				pbs_idx_free_ctx(idx_ctx);
				goto err;
			}
		}
	}
	pbs_idx_free_ctx(idx_ctx);

	while ((l = (tpp_leaf_t *) tpp_deque(&leaf_list))) {
		int j;
		tpp_packet_t *pkt = NULL;

		for (j = 0; j < count; j++) {
			pkt = tpp_bld_pkt(pkt, chunks[j].data, chunks[j].len, 1, NULL);
			if (!pkt) {
				tpp_log(LOG_CRIT, __func__, "Failed to build packet");
				goto err;
			}
		}

		if (tpp_transport_vsend(l->conn_fd, pkt) != 0) {
			if (errno != ENOTCONN) {
				tpp_log(LOG_ERR, __func__, "send failed");
				goto err;
			}
			/* vsend will free packets even in case of failure */
		}
	}
	return 0;

err:
	tpp_log(LOG_CRIT, __func__, "Error broadcasting to my leaves");
	while (tpp_deque(&leaf_list)); /* drain the list, dont free pacets, transport will free */
	return -1;
}

static int
router_send_ctl_join(int tfd, void *data, void *c)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	int rc = 0;

	if (!ctx)
		return 0;

	if (ctx->type == TPP_ROUTER_NODE) {
		tpp_router_t *r = NULL;
		tpp_join_pkt_hdr_t *hdr = NULL;
		tpp_packet_t *pkt = NULL;

		r = (tpp_router_t *) ctx->ptr;

		/* send a TPP_CTL_JOIN message */
		pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_join_pkt_hdr_t), 1, (void **) &hdr);
		if (!pkt) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			return -1;
		}

		hdr->type = TPP_CTL_JOIN;
		hdr->node_type = TPP_ROUTER_NODE;
		hdr->hop = 1;
		hdr->index = 0;
		hdr->num_addrs = 0;

		rc = tpp_transport_vsend(r->conn_fd, pkt);
		if (rc == 0) {
			tpp_read_lock(&router_lock);

			r->state = TPP_ROUTER_STATE_CONNECTED;

			tpp_log(LOG_CRIT, NULL, "tfd=%d, pbs_comm %s accepted connection", tfd, r->router_name);

			rc = send_leaves_to_router(this_router, r);

			tpp_unlock_rwlock(&router_lock);
		} else {
			tpp_log(LOG_CRIT, __func__, "Failed to send JOIN packet/send leaves to pbs_comm %s", this_router->router_name);
			tpp_transport_close(r->conn_fd);
			return 0;
		}
	}

	return rc;
}

/**
 * @brief
 *	The router post connect handler
 *
 * @par Functionality
 *	When the connection between this router and another is dropped, the IO
 *	thread continuously attempts to reconnect to it. If the connection is
 *	restored, then this prior registered function is called.
 *
 * @param[in] tfd - The actual IO connection on which data was about to be
 *			sent (unused)
 * @param[in] data - Any data the IO thread might want to pass to this function.
 *		     (unused)
 * @param[in] extra - The extra data associated with IO connection
 *
 * @return Error code
 * @retval 0 - Success
 * @retval -1 - Failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
router_post_connect_handler(int tfd, void *data, void *c, void *extra)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	conn_auth_t *authdata = (conn_auth_t *)extra;
	int rc = 0;

	if (!ctx)
		return 0;

	if (ctx->type != TPP_ROUTER_NODE)
		return 0;

	if (tpp_conf->auth_config->encrypt_method[0] != '\0' ||
		strcmp(tpp_conf->auth_config->auth_method, AUTH_RESVPORT_NAME) != 0) {

		/*
		 * Since either auth is not resvport or encryption is enabled,
		 * initiate handshakes for them
		 *
		 * If encryption is enabled then first initiate handshake for it
		 * else for authentication
		 *
		 * Here we are only initiating handshake, if any handshake needs
		 * continuation then it will be handled in leaf_pkt_handler
		 */

		int conn_fd = ((tpp_router_t *) ctx->ptr)->conn_fd;
		authdata = tpp_make_authdata(tpp_conf, AUTH_CLIENT, tpp_conf->auth_config->auth_method, tpp_conf->auth_config->encrypt_method);
		if (authdata == NULL) {
			/* tpp_make_authdata already logged error */
			return -1;
		}
		authdata->conn_initiator = 1;
		tpp_transport_set_conn_extra(tfd, authdata);

		if (authdata->config->encrypt_method[0] != '\0') {
			rc = tpp_handle_auth_handshake(tfd, conn_fd, authdata, FOR_ENCRYPT, NULL, 0);
			if (rc != 1)
				return rc;
		}

		if (strcmp(authdata->config->auth_method, AUTH_RESVPORT_NAME) != 0) {
			if (strcmp(authdata->config->auth_method, authdata->config->encrypt_method) != 0) {
				rc = tpp_handle_auth_handshake(tfd, conn_fd, authdata, FOR_AUTH, NULL, 0);
				if (rc != 1)
					return rc;
			} else {
				authdata->authctx = authdata->encryptctx;
				authdata->authdef = authdata->encryptdef;
				tpp_transport_set_conn_extra(tfd, authdata);
			}
		}
	}

	/*
	 * Since we are in post conntect handler
	 * and we have completed authentication
	 * so send TPP_CTL_JOIN
	 */
	return router_send_ctl_join(tfd, data, c);
}

/**
 * @brief
 *	Handle a connection close handler
 *
 * @par Functionality:
 *	Identify what type of endpoint dropped the connection, and remove it
 *	from the appropriate indexes (router or leaf). If a leaf or router
 *	was down, inform all the other routers interested about the connection
 *	loss.
 *
 *	If a router went down, then consider all leaves connected directly to
 *	that router to be down, and repeat the process.
 *
 *	This is also called when a leaf sends a LEAVE message, which is
 *	forwarded by the router to other leaves and routers, in this case, the
 *	hop count is > 1.
 *
 *	If hop == 1, it means data came from a direct connection instead of
 *	being forwarded by another router. Leafs that are directly connected
 *	have conn_fd set to the actual socket descriptor. For leafs that are
 *	not connected directly to this router, the conn_fd is -1.
 *
 * @param[in] tfd   - The physical connection that went down
 * @param[in] error - Any error that was captured when the connection went down
 * @param[in] c     - The context that was associated with the connection
 * @param[in] hop   - The hop count - number of times that message traveled
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
router_close_handler_inner(int tfd, int error, void *c, int hop)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_leave_pkt_hdr_t hdr;
	tpp_chunk_t chunks[2];
	int i;

	if (tpp_going_down == 1)
		return 0;

	if (c == NULL) {
		/*
		 * no context available, no join was done, so don't bother
		 * about disconnection
		 */
		TPP_DBPRT("tfd = %d, No context, leaving", tfd);
		return 0;
	}

	if (ctx->type == TPP_LEAF_NODE || ctx->type == TPP_LEAF_NODE_LISTEN) {

		/* connection to a leaf node dropped or a router dropped */
		tpp_leaf_t *l = (tpp_leaf_t *) ctx->ptr;
		tpp_router_t *r = NULL;
		int leaf_type = ctx->type;

		hdr.type = TPP_CTL_LEAVE;
		hdr.hop = hop + 1;
		hdr.ecode = error;
		hdr.num_addrs = l->num_addrs;

		chunks[0].data = (void *) &hdr;
		chunks[0].len = sizeof(tpp_leave_pkt_hdr_t);

		chunks[1].data = (void *) l->leaf_addrs;
		chunks[1].len = l->num_addrs * sizeof(tpp_addr_t);

		if (hop == 1) {
			/* request came directly to me? */
			/*
			 * broadcast leave pkt to other routers,
			 * except from where it came from
			 */
			tpp_read_lock(&router_lock);
			broadcast_to_my_routers(chunks, 2, tfd);
			tpp_unlock_rwlock(&router_lock);

			tpp_log(LOG_CRIT, NULL, "tfd=%d, Connection from leaf %s down", tfd, tpp_netaddr(&l->leaf_addrs[0]));
		}

		tpp_write_lock(&router_lock);

		if ((r = del_router_from_leaf(l, tfd)) == NULL) {
			tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to clear pbs_comm from leaf %s's list", tfd, tpp_netaddr(&l->leaf_addrs[0]));
			tpp_unlock_rwlock(&router_lock);
			return -1;
		}

		/* we had only the first address record stored in the my_leaves tree */
		if (pbs_idx_delete(r->my_leaves_idx, &l->leaf_addrs[0]) != PBS_IDX_RET_OK) {
			tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to delete address from my_leaves %s", tfd, tpp_netaddr(&l->leaf_addrs[0]));
			tpp_unlock_rwlock(&router_lock);
			return -1;
		}

		if (l->num_routers > 0) {
			TPP_DBPRT("tfd=%d, Other pbs_comms for leaf %s present", tfd, tpp_netaddr(&l->leaf_addrs[0]));
			tpp_unlock_rwlock(&router_lock);
			return 0;
		}

		TPP_DBPRT("No more pbs_comms to leaf %s, deleting leaf", tpp_netaddr(&l->leaf_addrs[0]));

		/* delete all of this leaf's addresses from the search tree */
		for (i = 0; i < l->num_addrs; i++) {
			if (pbs_idx_delete(cluster_leaves_idx, &l->leaf_addrs[i]) != PBS_IDX_RET_OK) {
				tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to delete address %s from cluster leaves", tfd, tpp_netaddr(&l->leaf_addrs[i]));
				tpp_unlock_rwlock(&router_lock);
				return -1;
			}
		}

		if (leaf_type == TPP_LEAF_NODE_LISTEN) {
			/*
			 * if it is a notification leaf,
			 * then remove from this tree also
			 */
			pbs_idx_delete(my_leaves_notify_idx, &l->leaf_addrs[0]);
		}

		/* broadcast to all self connected leaves */
		broadcast_to_my_leaves(chunks, 2, tfd, 0);

		free_leaf(l);

		tpp_unlock_rwlock(&router_lock);

		return 0;

	} else if (ctx->type == TPP_ROUTER_NODE) {

		tpp_router_t *r = (tpp_router_t *) ctx->ptr;
		int rc;
		tpp_leaf_t *l;
		tpp_que_t deleted_leaves;
		tpp_que_elem_t *n = NULL;

		if (r->state == TPP_ROUTER_STATE_CONNECTED) {
			void *idx_ctx = NULL;

			/* do any logging or leaf processing only if it was connected earlier */
			tpp_log(LOG_CRIT, NULL, "tfd=%d, Connection %s pbs_comm %s down", tfd, (r->initiator == 1) ? "to" : "from", r->router_name);

			tpp_write_lock(&router_lock);
			TPP_QUE_CLEAR(&deleted_leaves);

			while (pbs_idx_find(r->my_leaves_idx, NULL, (void **)&l, &idx_ctx) == PBS_IDX_RET_OK) {
				if (l->num_routers > 0) {
					del_router_from_leaf(l, tfd);
					if (l->num_routers == 0) {
						/*
						 * delete leaf from the leaf tree, since it
						 * is not connected to any routers now
						 */
						TPP_DBPRT("All routers to leaf %s down, deleting leaf", tpp_netaddr(&l->leaf_addrs[0]));

						if (tpp_enque(&deleted_leaves, l) == NULL) {
							tpp_unlock_rwlock(&router_lock);
							tpp_log(LOG_CRIT, __func__, "Out of memory enqueuing deleted leaves");
							return -1;
						}
					}
				}
			}
			pbs_idx_free_ctx(idx_ctx);

			/* now remove each of the leaf's addresses from clusters index */
			while ((n = TPP_QUE_NEXT(&deleted_leaves, n))) {
				l = (tpp_leaf_t *) TPP_QUE_DATA(n);
				if (l == NULL)
					continue;

				if (l->leaf_type  == TPP_LEAF_NODE_LISTEN) {
					pbs_idx_delete(my_leaves_notify_idx, &l->leaf_addrs[0]);
				}

				for (i = 0; i < l->num_addrs; i++) {
					if (pbs_idx_delete(cluster_leaves_idx, &l->leaf_addrs[i]) != PBS_IDX_RET_OK) {
						tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to delete address %s", tfd, tpp_netaddr(&l->leaf_addrs[i]));
						tpp_unlock_rwlock(&router_lock);

						return -1;
					}
				}
			}

			/* delete all leaf nodes from the my_leaves_idx tree of this router
			 * and finally destroy that index since the router itself had
			 * disconnected
			 */
			pbs_idx_destroy(r->my_leaves_idx);
			r->my_leaves_idx = NULL;
			if (r->initiator == 1) {
				/* initialize the routers leaf tree */
				r->my_leaves_idx = pbs_idx_create(0, sizeof(tpp_addr_t));
				if (r->my_leaves_idx == NULL) {
					tpp_log(LOG_CRIT, __func__, "Failed to create index for my leaves");
					free_router(r);
					tpp_unlock_rwlock(&router_lock);
					return -1;
				}
			}

			/*
			 * set the conn_fd of the router to -1 here and not before
			 * because the del_router_from_leaf function above matches
			 * with the routers conn_fd
			 */
			r->conn_fd = -1;
			r->state = TPP_ROUTER_STATE_DISCONNECTED;

			chunks[0].data = (void *) &hdr;
			chunks[0].len = sizeof(tpp_leave_pkt_hdr_t);

			/* broadcast leave msgs of these leaves to my leaves */
			while ((l = (tpp_leaf_t *) tpp_deque(&deleted_leaves))) {
				hdr.type = TPP_CTL_LEAVE;
				hdr.hop = 2;
				hdr.ecode = error;
				hdr.num_addrs = l->num_addrs;

				chunks[1].data = (void *) l->leaf_addrs;
				chunks[1].len = l->num_addrs * sizeof(tpp_addr_t);

				/* broadcast to all self connected leaves */
				broadcast_to_my_leaves(chunks, 2, tfd, 0);
				free_leaf(l);
			}

			tpp_unlock_rwlock(&router_lock);
		}

		if (r->initiator == 1) {
			void *thrd;
			/*
			 * Attempt reconnects only if we had initiated the
			 * connection ourselves
			 */
			if (r->delay == 0)
				r->delay = TPP_CONNNECT_RETRY_MIN;
			else
				r->delay += TPP_CONNECT_RETRY_INC;
			if (r->delay > TPP_CONNECT_RETRY_MAX)
				r->delay = TPP_CONNECT_RETRY_MAX;

			r->state = TPP_ROUTER_STATE_CONNECTING;

			/* de-associate connection context from current tfd */
			tpp_transport_set_conn_ctx(tfd, NULL);

			/* find the transport thread associated with this connection
			 * that is on its way to be closed, pass the same thrd context
			 * to the special connect call, so that the new connection is
			 * assigned to this same thread instead of new one
			 */
			tpp_log(LOG_INFO, NULL, "Connecting to pbs_comm %s", r->router_name);

			thrd = tpp_transport_get_thrd_context(tfd);
			rc = tpp_transport_connect_spl(r->router_name, r->delay, ctx, &r->conn_fd, thrd);
			if (rc != 0) {
				tpp_log(LOG_CRIT, NULL, "tfd=%d, Failed initiating connection to pbs_comm %s", tfd, r->router_name);
				return -1;
			}

			return 1; /* so caller does not free context or set anything */
		} else {
			/**
			 * remove this router from our list of registered routers
			 * ie, remove from routers_idx tree
			 **/
			tpp_write_lock(&router_lock);
			
			pbs_idx_delete(routers_idx, &r->router_addr);
			/*
			 * context will be freed and deleted by router_close_handler
			 * so just free router structure itself
			 */
			free_router(r);

			tpp_unlock_rwlock(&router_lock);

		}

		return 0;
	}
	return 0;
}

/**
 * @brief
 *	Wrapper to the close handle function. This is the one registered to be
 *	called from the IO thread when the IO thread detects a connection loss.
 *
 *	It calls the wrapper "router_close_handler_inner" with a hop count to 1,
 *	since its called "first hand" by the registered function.
 *
 * @par Functionality:
 *	Identify what type of endpoint dropped the connection, and remove it
 *	from the appropriate index (router or leaf). If a leaf or router
 *	was down, inform all the other routers interested about the connection
 *	loss.
 *
 *	If a router went down, then consider all leaves connected directly to
 *	that router to be down, and repeat the process.
 *
 * @param[in] tfd   - The physical connection that went down
 * @param[in] error - Any error that was captured when the connection went down
 * @param[in] c     - The context that was associated with the connection
 * @param[in] extra - The extra data associated with IO connection
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
router_close_handler(int tfd, int error, void *c, void *extra)
{
	int rc;

	if (extra) {
		conn_auth_t *authdata = (conn_auth_t *)extra;
		if (authdata->authctx && authdata->authdef)
			authdata->authdef->destroy_ctx(authdata->authctx);
		if (authdata->authdef != authdata->encryptdef && authdata->encryptctx && authdata->encryptdef)
			authdata->encryptdef->destroy_ctx(authdata->encryptctx);
		if (authdata->config)
			free_auth_config(authdata->config);
		/* DO NOT free authdef here, it will be done in unload_auths() */
		free(authdata);
		tpp_transport_set_conn_extra(tfd, NULL);
	}

	/* set hop to 1 and send to inner */
	if ((rc = router_close_handler_inner(tfd, error, c, 1)) == 0) {
		tpp_transport_set_conn_ctx(tfd, NULL);
		TPP_DBPRT("Freeing context=%p for tfd=%d", c, tfd);
		free(c);
	}
	return rc;
}

/**
 * @brief
 *	The timer handler function registered with the IO thread.
 *
 * @par Functionality
 *	This function is called periodically (after the amount of time as
 *	specified by router_next_event_expiry() function) by the IO thread. This
 *	drives sending notifications to any leaf listen nodes.
 *
 * @retval - next event time
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
router_timer_handler(time_t now)
{
	tpp_ctl_pkt_hdr_t hdr;
	tpp_chunk_t chunks[1];
	int send_update = 0;
	int ret = -1;

	tpp_lock(&lj_lock);
	if (router_last_leaf_joined > 0) {
		if ((now - router_last_leaf_joined) < 3) {
			ret = 3; /* time not yet over, retry in the next 3 seconds */
		} else {
			send_update = 1;
			router_last_leaf_joined = 0;
		}
	}
	tpp_unlock(&lj_lock);

	if (send_update == 1) {
		int len;

		memset(&hdr, 0, sizeof(tpp_ctl_pkt_hdr_t)); /* only to satisfy valgrind */
		hdr.type = TPP_CTL_MSG;
		hdr.code = TPP_MSG_UPDATE;

		len = sizeof(tpp_ctl_pkt_hdr_t);
		chunks[0].data = (void *) &hdr;
		chunks[0].len = len;

		/* broadcast to self connected leaves asking for notification */
		tpp_read_lock(&router_lock);
		broadcast_to_my_leaves(chunks, 1, -1, 1);
		tpp_unlock_rwlock(&router_lock);
	}

	return ret;
}

/**
 * @brief
 *	The pre-send handler registered with the IO thread.
 *
 * @par Functionality
 *	When the IO thread is ready to send out a packet over the wire, it calls
 *	a prior registered "pre-send" handler. This pre-send handler (for routers)
 *	takes care of encrypting data and save unencrypted data for "post-send" handler
 *	in extra data associated with IO connection
 *
 * @param[in] tfd - The actual IO connection on which data was sent (unused)
 * @param[in] pkt - The data packet that is sent out by the IO thrd
 * @param[in] extra - The extra data associated with IO connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
router_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *c, void *extra)
{
	conn_auth_t *authdata = (conn_auth_t *)extra;

	/*
	 * if presend handler is called from handle_disconnect()
	 * then extra will be NULL and this is just a sending simulation
	 * so no encryption needed
	 */
	if (authdata == NULL || authdata->encryptdef == NULL || pkt == NULL)
		return 0;

	return (tpp_encrypt_pkt(authdata, pkt));
}

/**
 * @brief
 *	Wrapper function for the router to handle incoming data. This
 *  wrapper exists only to detect if the inner function
 *  allocated memory in data_out and free that memory in a
 *  clean way, so that we do not have to add a goto or free
 *  in every return path of the inner function.
 *
 * @param[in] tfd - The physical connection over which data arrived
 * @param[in] buf - The pointer to the received data packet
 * @param[in] len - The length of the received data packet
 * @param[in] c   - The context associated with this physical connection
 * @param[in] extra - The extra data associated with IO connection
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
router_pkt_handler(int tfd, void *buf, int len, void *c, void *extra)
{
	void *data_out = NULL;
	int rc = router_pkt_handler_inner(tfd, buf, &data_out, len, c, extra);
	free(data_out);
	return rc;
}

/**
 * @brief
 *	Inner handler function for the router to handle incoming data. When data
 *	packet arrives, it determines what is the intended destination and
 *	forwards the data packet to that destination.
 *
 * @param[in] tfd - The physical connection over which data arrived
 * @param[in] buf - The pointer to the received data packet
 * @param[out] data_out - The pointer to the newly allocated data buffer, if any
 * @param[in] len - The length of the received data packet
 * @param[in] c   - The context associated with this physical connection
 * @param[in] extra - The extra data associated with IO connection
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
router_pkt_handler_inner(int tfd, void *buf, void **data_out, int len, void *c, void *extra)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_data_pkt_hdr_t *dhdr = buf;
	enum TPP_MSG_TYPES type;
	tpp_chunk_t chunks[2];
	tpp_router_t *target_router = NULL;
	int target_fd = -1;
	tpp_addr_t connected_host;
	conn_auth_t *authdata = (conn_auth_t *)extra;
	tpp_addr_t *addr = tpp_get_connected_host(tfd);
	char msg[TPP_GEN_BUF_SZ];
	short rc = -1;

	if (!addr)
		return -1;

	memcpy(&connected_host, addr, sizeof(tpp_addr_t));
	free(addr);

again:
	type = dhdr->type;
	errno = 0;

	if(type >= TPP_LAST_MSG)
		return -1;

	switch (type) {
		case TPP_ENCRYPTED_DATA: {
			int len_out;
			int sz = sizeof(tpp_encrypt_hdr_t);
			if (authdata == NULL) {
				tpp_log(LOG_CRIT, __func__, "tfd=%d, No auth data found", tfd);
				return -1;
			}

			if (authdata->encryptdef == NULL) {
				tpp_log(LOG_CRIT, __func__, "connetion doesn't support decryption of data");
				return -1;
			}

			if (authdata->encryptdef->decrypt_data(authdata->encryptctx, (void *)((char *)buf + sz), (size_t)len - sz, data_out, (size_t *) &len_out) != 0) {
				return -1;
			}

			if ((len - sz) > 0 && len_out <= 0) {
				tpp_log(LOG_CRIT, __func__, "invalid decrypted data len: %d, pktlen: %d", len_out, len - sz);
				return -1;
			}
			dhdr = *data_out;
			len = len_out;
			goto again;
		}
		break;

		case TPP_AUTH_CTX: {
			tpp_auth_pkt_hdr_t ahdr = {0};
			size_t len_in = 0;
			void *data_in = NULL;
			conn_auth_t *authdata = (conn_auth_t *)extra;

			memcpy(&ahdr, dhdr, sizeof(tpp_auth_pkt_hdr_t));

			if (authdata == NULL) {
				msg[0] = '\0';
				if (!is_string_in_arr(tpp_conf->supported_auth_methods, ahdr.auth_method))
					snprintf(msg, sizeof(msg), "tfd=%d, Authentication method %s not allowed in connection %s", tfd, ahdr.auth_method, tpp_netaddr(&connected_host));

				else if (strcmp(ahdr.auth_method, AUTH_RESVPORT_NAME) != 0 && get_auth(ahdr.auth_method) == NULL)
					snprintf(msg, sizeof(msg), "tfd=%d, Authentication method not supported in connection %s", tfd, tpp_netaddr(&connected_host));

				else if (ahdr.encrypt_method[0] != '\0' && get_auth(ahdr.encrypt_method) == NULL)
					snprintf(msg, sizeof(msg), "tfd=%d, Encryption method not supported in connection %s", tfd, tpp_netaddr(&connected_host));

				if (msg[0] != '\0') {
					/* error message was set, to take action */
					tpp_log(LOG_CRIT, NULL, msg);
					tpp_send_ctl_msg(tfd, TPP_MSG_AUTHERR, &connected_host, &this_router->router_addr, -1, 0, msg);
					return 0; /* let connection be alive, so we can send error */
				}
			}

			len_in = (size_t)len - sizeof(tpp_auth_pkt_hdr_t);
			data_in = calloc(1, len_in);
			if (data_in == NULL) {
				tpp_log(LOG_CRIT, __func__, "Out of memory allocating authdata credential");
				return -1;
			}
			memcpy(data_in, (char *)dhdr + sizeof(tpp_auth_pkt_hdr_t), len_in);

			if (authdata == NULL) {
				authdata = tpp_make_authdata(tpp_conf, AUTH_SERVER, ahdr.auth_method, ahdr.encrypt_method);
				if (authdata == NULL) {
					/* tpp_make_authdata already logged error */
					free(data_in);
					return -1;
				}
				tpp_transport_set_conn_extra(tfd, authdata);
			}

			rc = tpp_handle_auth_handshake(tfd, tfd, authdata, ahdr.for_encrypt, data_in, len_in);
			if (rc != 1) {
				free(data_in);
				return rc;
			}

			free(data_in);

			if (ahdr.for_encrypt == FOR_ENCRYPT &&
				strcmp(authdata->config->auth_method, AUTH_RESVPORT_NAME) != 0) {

				if (strcmp(authdata->config->auth_method, authdata->config->encrypt_method) != 0) {
					if (authdata->conn_initiator) {
						rc = tpp_handle_auth_handshake(tfd, tfd, authdata, FOR_AUTH, NULL, 0);
						if (rc != 1) {
							return rc;
						}
					} else
						return 0;
				} else {
					authdata->authctx = authdata->encryptctx;
					authdata->authdef = authdata->encryptdef;
					tpp_transport_set_conn_extra(tfd, authdata);
				}
			}

			if (ctx == NULL) {
				if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
					tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
					return -1;
				}
				ctx->ptr = NULL;
				ctx->type = TPP_AUTH_NODE; /* denoting that this is an authenticated connection */
			}

			/*
			* associate this router structure (information) with
			* this physical connection
			*/
			tpp_transport_set_conn_ctx(tfd, ctx);

			/* send TPP_CTL_JOIN msg to fellow router */
			return router_send_ctl_join(tfd, dhdr, c);

		}
		break;

		case TPP_CTL_JOIN: {
			unsigned char hop;
			unsigned char node_type;
			tpp_join_pkt_hdr_t *hdr = (tpp_join_pkt_hdr_t *) dhdr;

			hop = hdr->hop;
			node_type = hdr->node_type;

			if (ctx == NULL) { /* connection not yet authenticated */
				msg[0] = '\0';
				if (extra && strcmp(((conn_auth_t *)extra)->config->auth_method, AUTH_RESVPORT_NAME) != 0) {
					/*
					 * In case of external authentication, ctx must already be set
					 * so error out if ctx is not set.
					 */
					snprintf(msg, sizeof(msg), "tfd=%d Unauthenticated connection from %s", tfd, tpp_netaddr(&connected_host));
				} else {
					if (!is_string_in_arr(tpp_conf->supported_auth_methods, AUTH_RESVPORT_NAME))
						snprintf(msg, sizeof(msg), "tfd=%d, Authentication method %s not allowed in connection %s", tfd, AUTH_RESVPORT_NAME, tpp_netaddr(&connected_host));

					else if (tpp_transport_isresvport(tfd) != 0) /* reserved port based authentication, and is not yet authenticated, so check resv port */
						snprintf(msg, sizeof(msg), "Connection from non-reserved port, rejected");
				}
				if (msg[0] != '\0') {
					/* error message was set above, take action */
					tpp_log(LOG_CRIT, NULL, msg);
					tpp_send_ctl_msg(tfd, TPP_MSG_AUTHERR, &connected_host, &this_router->router_addr, -1, 0, msg);
					return 0; /* let connection be alive, so we can send error */
				}
			}

			/* check if type was router or leaf */
			if (node_type == TPP_ROUTER_NODE) {
				tpp_router_t *r = NULL;
				void *pconn_host = &connected_host;

				TPP_DBPRT("Recvd TPP_CTL_JOIN from pbs_comm node %s, len=%d", tpp_netaddr(&connected_host), len);

				tpp_write_lock(&router_lock);

				/* find associated router */
				pbs_idx_find(routers_idx, &pconn_host, (void **)&r, NULL);
				if (r) {
					if (r->conn_fd != -1) {
						/* this router had not yet disconnected,
						 * so close the existing connection
						 */
						tpp_log(LOG_CRIT, NULL, "tfd=%d, pbs_comm %s is still connected while "
							 "another connect arrived, dropping existing connection %d", tfd, r->router_name, r->conn_fd);
						tpp_transport_close(r->conn_fd);
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
				} else {
					r = alloc_router(strdup(tpp_netaddr(&connected_host)), &connected_host);
					if (!r) {
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
				}
				r->conn_fd = tfd;
				r->initiator = 0;
				r->state = TPP_ROUTER_STATE_CONNECTED;

				tpp_log(LOG_CRIT, NULL, "tfd=%d, pbs_comm %s connected", tfd, tpp_netaddr(&r->router_addr));

				if (ctx == NULL) {
					if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
						tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
				}
				ctx->ptr = r;
				ctx->type = TPP_ROUTER_NODE;

				/*
				 * associate this router structure (information) with
				 * this physical connection
				 */
				tpp_transport_set_conn_ctx(tfd, ctx);

				/* now send new router info about all leaves I have */
				send_leaves_to_router(this_router, r);

				tpp_unlock_rwlock(&router_lock);
				return 0;

			} else if (node_type == TPP_LEAF_NODE || node_type == TPP_LEAF_NODE_LISTEN) {
				tpp_leaf_t *l = NULL;
				tpp_router_t *r = NULL;
				int found;
				int i;
				int index = (int) hdr->index;
				tpp_addr_t *addrs;
				void *paddr;

				TPP_DBPRT("Recvd TPP_CTL_JOIN FOR LEAF from pbs_comm node %s, len=%d, hop=%d", tpp_netaddr(&connected_host), len, hop);

				if (hdr->num_addrs == 0) {
					/* error, must have atleast one address associated */
					tpp_log(LOG_CRIT, NULL, "tfd=%d, No address associated with join msg from leaf", tfd);
					return -1;
				}
				addrs = (tpp_addr_t *) (((char *) dhdr) + sizeof(tpp_join_pkt_hdr_t));

				tpp_write_lock(&router_lock);

				if (ctx == NULL || ctx->ptr == NULL) {
					/* router is myself */
					r = this_router;
				} else {
					void *pconn_host = &connected_host;
					/* must be a router forwarding leaves from its database to me */

					/* find associated router */
					pbs_idx_find(routers_idx, &pconn_host, (void **)&r, NULL);
					if (!r) {
						char rname[TPP_MAXADDRLEN + 1];

						strcpy(rname, tpp_netaddr(&connected_host));
						tpp_log(LOG_CRIT, NULL, "tfd=%d, Failed to find pbs_comm %s in join for leaf %s", tfd, rname, tpp_netaddr(&addrs[0]));
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
				}

				/* find the leaf */
				found = 1;
				paddr = &addrs[0];
				pbs_idx_find(cluster_leaves_idx, &paddr, (void **)&l, NULL);
				if (!l) {
					found = 0;
					l = (tpp_leaf_t *) calloc(1, sizeof(tpp_leaf_t));
					if (l)
						l->leaf_addrs = malloc(sizeof(tpp_addr_t) * hdr->num_addrs);

					if (!l || !l->leaf_addrs) {
						free_leaf(l);
						tpp_log(LOG_CRIT, __func__, "Out of memory allocating leaf");
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}

					l->leaf_type = node_type;
					memcpy(l->leaf_addrs, addrs, sizeof(tpp_addr_t) * hdr->num_addrs);
					l->num_addrs = hdr->num_addrs;

					l->conn_fd = -1;
				}

				if (hop == 1) {

					for (i = 0; i < l->num_addrs; i++) {
						tpp_log(LOG_CRIT, NULL, "tfd=%d, Leaf registered address %s", tfd, tpp_netaddr(&l->leaf_addrs[i]));
					}

					if (l->conn_fd != -1) {
						/* this leaf had not yet disconnected,
						 * so close the existing connection.
						 */
						tpp_log(LOG_CRIT, NULL, "tfd=%d, Leaf %s still connected while "
							 "another leaf connect arrived, dropping existing connection %d",
							 tfd, tpp_netaddr(&l->leaf_addrs[0]), l->conn_fd);
						tpp_transport_close(l->conn_fd);
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
					l->conn_fd = tfd;

					/*
					 * Set a context only if the JOIN came from a direct connection
					 * from a leaf (hop == 1), and not a forwarded JOIN message.
					 * In case of a forwarded JOIN message, the tfd is associated
					 * with the routers context
					 */
					if (ctx == NULL) {
						if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
							tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
							tpp_unlock_rwlock(&router_lock);
							return -1;
						}
					}
					ctx->ptr = l;
					ctx->type = l->leaf_type;
					tpp_transport_set_conn_ctx(tfd, ctx);
				}

				TPP_DBPRT("tfd=%d, Router name = %s, address leaf = %p, leaf name=%s, index=%d, hop=%d", tfd, r->router_name, (void *) l, tpp_netaddr(&l->leaf_addrs[0]), (int) index, hop);

				/*
				 * router is not part of leaf's list
				 * of routers already, so add
				 */
				i = add_route_to_leaf(l, r, index);
				if (i == -1) {
					tpp_log(LOG_CRIT, NULL, "tfd=%d, Leaf %s exists!", tfd, tpp_netaddr(&l->leaf_addrs[0]));
					tpp_unlock_rwlock(&router_lock);
					return 0;
				}

				if (pbs_idx_insert(r->my_leaves_idx, &l->leaf_addrs[0], l) != PBS_IDX_RET_OK) {
					tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to add address %s to index of my leaves", tfd, tpp_netaddr(&l->leaf_addrs[0]));
					tpp_unlock_rwlock(&router_lock);
					return -1;
				}

				if (found == 0) {
					int fatal = 0;
					/* add each address to the cluster_leaves_idx tree
					 * since this is the primary "routing table"
					 */
					for (i = 0; i < l->num_addrs; i++) {
						if (pbs_idx_insert(cluster_leaves_idx, &l->leaf_addrs[i], l) != PBS_IDX_RET_OK) {
							void *unused;
							void *pleaf_addr = &l->leaf_addrs[i];
							if (pbs_idx_find(cluster_leaves_idx, &pleaf_addr, &unused, NULL) == PBS_IDX_RET_OK) {
								int k;
								tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to add address %s to cluster-leaves index "
										"since address already exists, dropping duplicate", tfd, tpp_netaddr(&l->leaf_addrs[i]));
								/* remove this address from the list of addresses of the leaf */
								for (k = i; k < (l->num_addrs - 1); k++) {
									l->leaf_addrs[k] = l->leaf_addrs[k + 1];
								}
								l->num_addrs--;

							} else {
								tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to add address %s to cluster-leaves index", tfd, tpp_netaddr(&l->leaf_addrs[i]));
								fatal++;
							}
						}
					}

					if (fatal > 0 || l->num_addrs == 0) {
						tpp_log(LOG_CRIT, NULL, "tfd=%d, Leaf %s had %s problem adding addresses, rejecting connection",
								 tfd, tpp_netaddr(&l->leaf_addrs[0]), (fatal > 0)? "fatal" : "all duplicates");
						tpp_unlock_rwlock(&router_lock);
						return -1;
					}
				}

				if (r == this_router) {
					if (l->leaf_type == TPP_LEAF_NODE_LISTEN) {
						if (pbs_idx_insert(my_leaves_notify_idx, &l->leaf_addrs[0], l) != PBS_IDX_RET_OK) {
							tpp_log(LOG_CRIT, __func__, "tfd=%d, Failed to add address %s to notify-leaves index", tfd, tpp_netaddr(&l->leaf_addrs[0]));
							tpp_unlock_rwlock(&router_lock);
							return -1;
						}
					}
				}

				if (l->leaf_type != TPP_LEAF_NODE_LISTEN) {
					/* listen type leaf nodes might be interested to hear about
					 * the other joined leaves. However don't send it updates
					 * for each leaf; rather set a timer, postponing it each time
					 * we get an update by 2 seconds
					 */
					tpp_lock(&lj_lock);
					router_last_leaf_joined = time(0);
					tpp_unlock(&lj_lock);
				}

				if (hop == 1) {
					/* broadcast to other routers if the hop is 1
					 * while forwarding to next routers, they will
					 * see incremented hop and will only update
					 * their own data structures and will not
					 * forward any further
					 */
					hop++; /* increment hop */
					hdr->hop = hop;

					chunks[0].data = (char *)dhdr;
					chunks[0].len = len;

					/*
					 * broadcast JOIN pkt to other routers,
					 * except from where it came from
					 */
					broadcast_to_my_routers(chunks, 1, tfd);
				}
				
				tpp_unlock_rwlock(&router_lock);
				return 0;
			}
			return 0;
		}
		break; /* TPP_CTL_JOIN */

		case TPP_CTL_LEAVE: {
			unsigned char hop;
			tpp_leave_pkt_hdr_t *hdr = (tpp_leave_pkt_hdr_t *) dhdr;

			hop = hdr->hop;

			if (ctx == NULL) {
				TPP_DBPRT("tfd=%d, No context, leaving", tfd);
				return 0;
			}

			TPP_DBPRT("Recvd TPP_CTL_LEAVE message tfd=%d from src=%s, hop=%d, type=%d", tfd, tpp_netaddr(&connected_host), hop, ctx->type);

			if (ctx->type == TPP_LEAF_NODE || ctx->type == TPP_LEAF_NODE_LISTEN) {
				tpp_log(LOG_CRIT, __func__, "tfd=%d, Internal error! TPP_CTL_LEAVE arrived with a leaf context", tfd);
				return -1;

			} else if (ctx->type == TPP_ROUTER_NODE) {
				/*
				 * If a TPP_CTL_LEAVE message comes, its basically
				 * from a leaf, but fd is routers context
				 */
				tpp_leaf_t *l = NULL;
				tpp_addr_t *src_addr = (tpp_addr_t *) (((char *) dhdr) + sizeof(tpp_leave_pkt_hdr_t));

				tpp_write_lock(&router_lock);

				/* find the leaf context to pass to close handler */
				pbs_idx_find(cluster_leaves_idx, (void **)&src_addr, (void **)&l, NULL);
				if (!l) {
					TPP_DBPRT("No leaf %s found", tpp_netaddr(src_addr));
					tpp_unlock_rwlock(&router_lock);
					return 0;
				}

				tpp_unlock_rwlock(&router_lock);

				if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
					tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
					return -1;
				}
				ctx->ptr = l;
				ctx->type = l->leaf_type;

				router_close_handler_inner(tfd, 0, ctx, hop);

				/* we created the fake context here, so delete it here */
				free(ctx);
			}
			return 0;
		}
		break; /* TPP_CTL_LEAVE */

		case TPP_MCAST_DATA: {
			int i, k;
			tpp_addr_t *src_host;
			typedef struct {
				int target_fd; /* target comm fd */
				int num_streams; /* actual number of destination streams */
				char *router_name;
				void *cmpr_ctx;
				void *minfo_buf; /* allocate size for total members */
			} target_comm_struct_t;

			target_comm_struct_t *rlist = NULL;
			int rsize = 0;
			int csize = 0;
			void *tmp;

			/* find the fd to forward to via the associated router */
			tpp_mcast_pkt_hdr_t *mhdr = (tpp_mcast_pkt_hdr_t *) dhdr;
			unsigned char orig_hop;
			tpp_mcast_pkt_info_t *minfo;
			void *minfo_base = NULL;
			void *info_start = (char *) dhdr + sizeof(tpp_mcast_pkt_hdr_t);
			unsigned int payload_len;
			void *payload;
			unsigned int cmprsd_len = ntohl(mhdr->info_cmprsd_len);
			unsigned int num_streams = ntohl(mhdr->num_streams);
			unsigned int info_len = ntohl(mhdr->info_len);

			if (cmprsd_len > 0) {
				payload_len = len - sizeof(tpp_mcast_pkt_hdr_t) - cmprsd_len;
				payload = ((char *) mhdr) + sizeof(tpp_mcast_pkt_hdr_t) + cmprsd_len;
			} else {
				payload_len = len - sizeof(tpp_mcast_pkt_hdr_t) - info_len;
				payload = ((char *) mhdr) + sizeof(tpp_mcast_pkt_hdr_t) + info_len;
				minfo_base = info_start;
			}

			src_host = &mhdr->src_addr;
			orig_hop = mhdr->hop;

			tpp_log(LOG_INFO, NULL, "tfd=%d, MCAST packet from %s, %u member streams, cmprsd_len=%d, info_len=%d, len=%d",
				tfd, tpp_netaddr(src_host), num_streams, cmprsd_len, info_len, payload_len);

#ifdef PBS_COMPRESSION_ENABLED
			if (cmprsd_len > 0) {
				minfo_base = tpp_inflate(info_start, cmprsd_len, info_len);
				if (minfo_base == NULL) {
					tpp_log(LOG_CRIT, __func__, "Decompression of mcast hdr failed");
					return -1;
				}
			}
#endif

			mhdr->hop = 1; /* set hop=1 to forward, use orig_hop for checking */

			tpp_log(LOG_INFO, __func__, "Total mcast member streams=%d", num_streams);

			/*
			 * go backwards in an attempt to distribute mcast packet
			 * first to other routers and then to local nodes
			 */
			for (k = num_streams - 1; k >= 0; k--) {
				tpp_addr_t *dest_host;
				unsigned int src_sd;
				tpp_leaf_t *l = NULL;

				minfo = (tpp_mcast_pkt_info_t *)(((char *) minfo_base) + k * sizeof(tpp_mcast_pkt_info_t));

				dest_host = &minfo->dest_addr;
				src_sd = ntohl(minfo->src_sd);

				TPP_DBPRT("MCAST data on fd=%u", src_sd);

				tpp_read_lock(&router_lock);
				pbs_idx_find(cluster_leaves_idx, (void **)&dest_host, (void **)&l, NULL);
				if (l == NULL) {
					tpp_unlock_rwlock(&router_lock);
					snprintf(msg, sizeof(msg), "pbs_comm:%s: Dest not found at pbs_comm", tpp_netaddr(&this_router->router_addr));
					log_noroute(src_host, dest_host, src_sd, msg);
					tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, src_host, dest_host, src_sd, 0, msg);
					continue;
				}

				/* find a router that is still connected */
				target_router = get_preferred_router(l, this_router, &target_fd);
				tpp_unlock_rwlock(&router_lock);

				if (target_router == NULL) {
					snprintf(msg, sizeof(msg), "pbs_comm:%s: No target pbs_comm found", tpp_netaddr(&this_router->router_addr));
					log_noroute(src_host, dest_host, src_sd, msg);
					tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, src_host, dest_host, src_sd, 0, msg);
					continue;
				}

				if (target_router == this_router) {
					tpp_packet_t *pkt = NULL;
					tpp_data_pkt_hdr_t *shdr = NULL;

					pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_data_pkt_hdr_t), 1, (void **) &shdr);
					if (!pkt) {
						tpp_log(LOG_CRIT, __func__, "Failed to build packet");
						goto mcast_err;
					}

					shdr->type = TPP_DATA;
					shdr->src_sd = minfo->src_sd;
					shdr->src_magic = minfo->src_magic;
					shdr->dest_sd = minfo->dest_sd;
					shdr->totlen = mhdr->totlen;
					memcpy(&shdr->src_addr, &mhdr->src_addr, sizeof(tpp_addr_t));
					memcpy(&shdr->dest_addr, &minfo->dest_addr, sizeof(tpp_addr_t));

					if (!tpp_bld_pkt(pkt, payload, payload_len, 1, NULL)) {
						tpp_log(LOG_CRIT, __func__, "Failed to build packet");
						goto mcast_err;
					}

					TPP_DBPRT("Send mcast indiv packet to %s", tpp_netaddr(&shdr->dest_addr));

					if (tpp_transport_vsend(target_fd, pkt) != 0) {
						tpp_log(LOG_ERR, __func__, "Failed to send mcast indiv pkt");
						tpp_transport_close(target_fd);
						goto mcast_err;
					}
				} else if (orig_hop == 0) {
					/* add this to list of routers to whom we need to send */
					/**
					 * now walk list backwards checking if router was already added.
					 * Rationale for checking backwards is that the last router
					 * that we added data to, is probably the one that the next
					 * few nodes are attached to as well.
					 * Might be able to use a hash here for faster search
					 **/
					int found = -1;
					for (i = csize - 1; i >= 0; i--) {
						if (rlist[i].target_fd == target_fd) {
							found = i;
							break;
						}
					}

					if (found == -1) {
						int c_minfo_len;
						if (csize == rsize) {
							/* got to add, but no space */
							tmp = realloc(rlist, sizeof(target_comm_struct_t) * (rsize + RLIST_INC));
							if (!tmp) {
								tpp_log(LOG_CRIT, __func__, "Out of memory resizing pbs_comm list to %lu bytes", (unsigned long)(sizeof(int) * rsize));
								goto mcast_err;
							}
							rsize += RLIST_INC;
							rlist = tmp;
						}
						found = csize++; /* the last index, and increment post */
						memset(&rlist[found], 0, sizeof(target_comm_struct_t));
						rlist[found].target_fd = target_fd; /* add this fd to the list of fds to send to */
						rlist[found].router_name = target_router->router_name; /* keep a pointer to the router name */

						/* allocate minfo_buf for this target comm */
						c_minfo_len = sizeof(tpp_mcast_pkt_info_t) * num_streams;
						if (tpp_conf->compress == 1 && c_minfo_len > TPP_COMPR_SIZE) {
							rlist[found].cmpr_ctx = tpp_multi_deflate_init(c_minfo_len);
							if (rlist[found].cmpr_ctx == NULL)
								goto mcast_err;
						} else {
							rlist[found].minfo_buf = malloc(c_minfo_len);
							if (!rlist[found].minfo_buf) {
								tpp_log(LOG_CRIT, __func__, "Out of memory allocating mcast buffer of %d bytes", c_minfo_len);
								goto mcast_err;
							}
						}
					} /* if entry not found */

					/* at this point to have the entry particular target comm */
					/* copy (or compress) the minfo for the target leaf */
					if (rlist[found].cmpr_ctx == NULL) { /* no compression */
						tpp_mcast_pkt_info_t *c_minfo =
							(tpp_mcast_pkt_info_t *)((char *) rlist[found].minfo_buf + (rlist[found].num_streams * sizeof(tpp_mcast_pkt_info_t)));
						memcpy(c_minfo, minfo, sizeof(tpp_mcast_pkt_info_t));
					} else {
						if (tpp_multi_deflate_do(rlist[found].cmpr_ctx, 0, minfo, sizeof(tpp_mcast_pkt_info_t)) != 0)
							goto mcast_err;
					}

					rlist[found].num_streams++;
				}
			} /* for k streams */

			if (csize > 0) {
				tpp_log(LOG_INFO, __func__, "Total target comms=%d", csize);

				/* finish up the MCAST packets for each target comm and send */
				for (k = 0; k < csize; k++) {
					void *t_minfo_buf = NULL;
					unsigned int t_minfo_len = 0;
					tpp_mcast_pkt_hdr_t *t_mhdr = NULL;
					tpp_packet_t *pkt = NULL;

					pkt = tpp_bld_pkt(NULL, mhdr, sizeof(tpp_mcast_pkt_hdr_t), 1, (void **) &t_mhdr);
					if (!pkt) {
						tpp_log(LOG_CRIT, __func__, "Failed to build packet");
						goto mcast_err;
					}

					t_mhdr->num_streams = htonl(rlist[k].num_streams);
					t_minfo_len = rlist[k].num_streams * sizeof(tpp_mcast_pkt_info_t);
					t_mhdr->info_len = htonl(t_minfo_len);

					/* the router information has been collected in rlist[k] */
					if (rlist[k].cmpr_ctx != NULL) {
						if (tpp_multi_deflate_do(rlist[k].cmpr_ctx, 1, NULL, 0) != 0) /* finish the compression */
							goto mcast_err;
						t_minfo_buf = tpp_multi_deflate_done(rlist[k].cmpr_ctx, &t_minfo_len);
						if (t_minfo_buf == NULL)
							goto mcast_err;
						t_mhdr->info_cmprsd_len = htonl(t_minfo_len);
						rlist[k].cmpr_ctx = NULL; /* done with compression */
					} else {
						t_minfo_buf = rlist[k].minfo_buf;
						t_mhdr->info_cmprsd_len = 0;
					}

					if (!tpp_bld_pkt(pkt, t_minfo_buf, t_minfo_len, 0, NULL)) {
						tpp_log(LOG_CRIT, __func__, "Failed to build packet");
						goto mcast_err;
					}

					if (!tpp_bld_pkt(pkt, payload, payload_len, 1, NULL)) {
						tpp_log(LOG_CRIT, __func__, "Failed to build packet");
						goto mcast_err;
					}

					tpp_log(LOG_INFO, __func__, "Sending MCAST packet to %s, num_streams=%d", rlist[k].router_name, rlist[k].num_streams);
					if (tpp_transport_vsend(rlist[k].target_fd, pkt) != 0)
						tpp_log(LOG_ERR, __func__, "send failed: errno = %d", errno);
				}
			}
mcast_err:
			if (cmprsd_len > 0)
				free(minfo_base);

			free(rlist); /* minfo_buf which was allocated will be freed when sent */

			tpp_log(LOG_INFO, NULL, "mcast done");

			return 0;
		}
		break; /* TPP_MCAST_DATA */

		case TPP_DATA:
		case TPP_CLOSE_STRM: {
			tpp_leaf_t *l = NULL;
			tpp_addr_t *src_host, *dest_host;
			tpp_packet_t *pkt = NULL;
			unsigned int src_sd;

			src_host = &dhdr->src_addr;
			dest_host = &dhdr->dest_addr;
			src_sd = ntohl(dhdr->src_sd);

			tpp_read_lock(&router_lock);

			pbs_idx_find(cluster_leaves_idx, (void **)&dest_host, (void **)&l, NULL);
			if (l == NULL) {
				tpp_unlock_rwlock(&router_lock);
				snprintf(msg, sizeof(msg), "tfd=%d, pbs_comm:%s: Dest not found", tfd, tpp_netaddr(&this_router->router_addr));
				log_noroute(src_host, dest_host, src_sd, msg);
				tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, src_host, dest_host, src_sd, 0, msg);
				return 0;
			}

			/* find a router that is still connected */
			target_router = get_preferred_router(l, this_router, &target_fd);
			tpp_unlock_rwlock(&router_lock);

			if (target_router == NULL) {
				snprintf(msg, sizeof(msg), "tfd=%d, pbs_comm:%s: No target pbs_comm found", tfd, tpp_netaddr(&this_router->router_addr));
				log_noroute(src_host, dest_host, src_sd, msg);
				tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, src_host, dest_host, src_sd, 0, msg);
				return 0;
			}

			pkt = tpp_bld_pkt(NULL, dhdr, len, 1, NULL);
			if (!pkt) {
				tpp_log(LOG_CRIT, __func__, "Failed to build packet");
				return 0;
			}

			rc = tpp_transport_vsend(target_fd, pkt);
			if (rc == -1)  {
				tpp_log(LOG_ERR, __func__, "Failed to send TPP_DATA/TPP_CLOSE_STRM");
				tpp_transport_close(target_fd);
			}

			return rc; /* 0 - success, -1 failed, -2 app mbox full */
		}
		break; /* TPP_DATA, TPP_CLOSE_STRM */

		case TPP_CTL_MSG: {
			tpp_ctl_pkt_hdr_t *ehdr = (tpp_ctl_pkt_hdr_t *) dhdr;
			tpp_leaf_t *l = NULL;
			int subtype = ehdr->code;

			if (subtype == TPP_MSG_NOROUTE) {
				char lbuf[TPP_MAXADDRLEN + 1];
				tpp_packet_t *pkt = NULL;
				tpp_addr_t *dest_host = &ehdr->dest_addr;
				char *msg = ((char *) ehdr) + sizeof(tpp_ctl_pkt_hdr_t);

				strcpy(lbuf, tpp_netaddr(&ehdr->dest_addr));
				tpp_log(LOG_WARNING, __func__, "tfd=%d, Recvd TPP_CTL_NOROUTE for message, %s(sd=%d) -> %s: %s",
							tfd, lbuf, ntohl(ehdr->src_sd), tpp_netaddr(&ehdr->src_addr), msg);

				/* find the fd to forward to via the associated router */
				tpp_read_lock(&router_lock);

				pbs_idx_find(cluster_leaves_idx, (void **)&dest_host, (void **)&l, NULL);
				if (l == NULL) {
					tpp_unlock_rwlock(&router_lock);
					return 0;
				}
				/* find a router that is still connected */
				target_router = get_preferred_router(l, this_router, &target_fd);

				tpp_unlock_rwlock(&router_lock);
				if (target_router == NULL) {
					tpp_log(LOG_WARNING, NULL, "tfd=%d, No connections to send TPP_CTL_NOROUTE", tfd);
					return 0;
				}

				pkt = tpp_bld_pkt(NULL, dhdr, len, 1, NULL);
				if (!pkt) {
					tpp_log(LOG_CRIT, __func__, "Failed to build packet");
					return 0;
				}
				if (tpp_transport_vsend(target_fd, pkt) != 0) {
					tpp_log(LOG_ERR, NULL, "tfd=%d, Failed to send pkt type TPP_CTL_NOROUTE", tfd);
					tpp_transport_close(target_fd);
				}
				return 0;
			}
		}
		break; /* TPP_CTL_MSG */

		default:
			/* no known message type, log and close connection by returning error code */
			tpp_log(LOG_CRIT, __func__, "tfd=%d, Unknown message type = %d", tfd, type);
	} /* switch */

	return -1;
}

/**
 * @brief
 *	Convenience function to get the most preferred route to reach a leaf
 *	If the leaf is directly connected to this router, then the l->conn_fd is
 *	already set, so just use it.
 *	If not, then search in the list of routes for the leaf starting from index
 *	0 (since its sorted on preference), finding a router that is still
 *	connected, i.e., r[i]->conn_fd is not -1.
 *
 * @param[in] - l 	- Pointer to the leaf for which to find route
 * @param[in] - this_router - Pointer to the local router
 * @param[out] - fd - fd of the chosen router
 *
 * @return	Router to be used
 * @retval	NULL  - Could not find a connected router
 * @retval	!NULL  - Success (The router is returned).
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static tpp_router_t *
get_preferred_router(tpp_leaf_t *l, tpp_router_t *this_router, int *fd)
{
	int i;
	tpp_router_t *r = NULL;

	*fd = -1;

	if (l->conn_fd != -1) {
		r = this_router;
		*fd = l->conn_fd;
	} else {

		/*
		 * not directly connected to me, so search for a router
		 * to which it is connected
		 */
		if (l->r) {
			for (i = 0; i < l->tot_routers; i++) {
				if (l->r[i]) {
					if (l->r[i]->conn_fd != -1) {
						r = l->r[i];
						*fd = r->conn_fd;
						break;
					}
				}
			}
		}
	}
	return r;
}

/**
 * @brief
 *	Convenience function to delete a route from a leaf's list of routers at the
 *	specified preference (specified by the index attribute of the leaf, if not -1).
 *
 * @param[in] - l - Pointer to the leaf for which to find route
 * @param[in] - tfd - The fd of the connection involved
 *
 * @return	Error code
 * @retval	NULL    - Failure (Could not find router).
 * @retval	!=NULL  - Success (The router that was removed is returned).
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static tpp_router_t *
del_router_from_leaf(tpp_leaf_t *l, int tfd)
{
	int i;
	tpp_router_t *r = NULL;

	for (i = 0; i < l->tot_routers; i++) {
		if (l->r[i] && /* router exists in this slot */
			((l->r[i]->conn_fd == tfd) || /* router fd matches tfd */
			(l->conn_fd == tfd && l->r[i]->conn_fd == -1))) {
			TPP_DBPRT("Removing pbs_comm %s from leaf %s", l->r[i]->router_name, tpp_netaddr(&l->leaf_addrs[0]));
			r = l->r[i];
			l->r[i] = NULL;
			l->num_routers--;
			if (l->num_routers == 0)
				free(l->r);
			TPP_DBPRT("pbs_comm count for leaf=%s is %d", tpp_netaddr(&l->leaf_addrs[0]), l->num_routers);
			return r;
		}
	}
	return NULL;
}

/**
 * @brief
 *	Convenience function to add a route to a leaf's list of routes at the
 *	specified preference (specified by the index parameter).
 *
 * @param[in] - l - Pointer to the leaf for which to find route
 * @param[in] - r - Pointer to the router to add
 * @param[in] - index - The preference for this route
 *
 * @return	Error code
 * @retval	-1    - Failure (Another router exists at this index).
 * @retval	!=-1  - Success (The router index is returned).
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
add_route_to_leaf(tpp_leaf_t *l, tpp_router_t *r, int index)
{
	/*
	 * Associate the router with the leaf
	 *
	 * put the router in the list of routers of the leaf
	 * at the specified index. The index is important to know
	 * the priority of the router to reach this leaf
	 */
	if (index == -1)
		return -1; /* error - index must be set before calling add route */

	if (index >= l->tot_routers) {
		int sz;
		int i;

		sz = index + 3;
		l->r = realloc(l->r, sz * sizeof(tpp_router_t *));
		for (i = l->tot_routers; i < sz; i++)
			l->r[i] = NULL;
		l->tot_routers = sz;
	}

	l->r[index] = r;
	l->num_routers++;

#ifdef DEBUG
	{
		int i;

		fprintf(stderr, "Leaf %s:%d routers [", tpp_netaddr(&l->leaf_addrs[0]), l->conn_fd);
		for (i = 0; i < l->tot_routers; i++) {
			if (l->r[i] && l->r[i]->router_name)
				fprintf(stderr, "%s:%d,", l->r[i]->router_name, l->r[i]->conn_fd);
		}
		fprintf(stderr, "],router_count=%d\n", l->num_routers);
	}
#endif

	return index;
}

/**
 * @brief
 *	Convenience function to find the index of a router in the leaf's
 *	list of routers associated
 *
 * @param[in] - l - Pointer to the leaf
 * @param[in] - r - Pointer to the router to find
 *
 * @return	Index of the router
 * @retval	-1    - Failure (router not found)
 * @retval	!=-1  - Success (The router index is returned).
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
leaf_get_router_index(tpp_leaf_t *l, tpp_router_t *r)
{
	int i;
	for (i = 0; i < l->tot_routers; i++) {
		if (l->r[i] == r)
			return i;
	}
	return -1;
}

/**
 * @brief
 *	Initializes the Router
 *
 * @par Functionality:
 *	Creates indexes for routers and leaves connected to this router.
 *	Registers the various handlers to be called from the IO thread.
 *	Finally connect to all other routers listed.
 *
 * @see
 *	tpp_transport_init
 *	tpp_transport_set_handlers
 *
 * @param[in] cnf - The tpp configuration structure
 *
 * @return     - The file descriptor that APP must use to monitor for events
 * @retval  -1 - Function failed
 * @retval !-1 - Success, read end of the pipe is returned to APP to monitor
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_init_router(struct tpp_config *cnf)
{
	int j;
	tpp_router_t *r;
	tpp_context_t *ctx = NULL;

	tpp_conf = cnf;

	/* before doing anything else, initialize the key to the tls */
	if (tpp_init_tls_key() != 0) {
		/* can only use prints since tpp key init failed */
		fprintf(stderr, "Failed to initialize tls key\n");
		return -1;
	}

	tpp_init_lock(&lj_lock);
	tpp_init_rwlock(&router_lock);

	routers_idx = pbs_idx_create(0, sizeof(tpp_addr_t));
	if (routers_idx == NULL) {
		tpp_log(LOG_CRIT, __func__, "Failed to create index for pbs comms");
		return -1;
	}

	cluster_leaves_idx = pbs_idx_create(0, sizeof(tpp_addr_t));
	if (cluster_leaves_idx == NULL) {
		tpp_log(LOG_CRIT, __func__, "Failed to create index for cluster leaves");
		return -1;
	}

	my_leaves_notify_idx = pbs_idx_create(0, sizeof(tpp_addr_t));
	if (my_leaves_notify_idx == NULL) {
		tpp_log(LOG_CRIT, __func__, "Failed to create index for leaves requiring notification");
		return -1;
	}

	r = alloc_router(tpp_conf->node_name, NULL);
	if (!r)
		return -1; /* error already logged */

	this_router = r; /* mark this one as this router */

	/* first set the transport handlers */
	tpp_transport_set_handlers(router_pkt_presend_handler, router_pkt_handler, router_close_handler, router_post_connect_handler, router_timer_handler);

	if ((tpp_transport_init(tpp_conf)) == -1)
		return -1;

	/* initiate connections to sister routers */
	j = 0;
	tpp_write_lock(&router_lock);
	while (tpp_conf->routers && tpp_conf->routers[j]) {
		/* add to connection table */

		r = alloc_router(tpp_conf->routers[j], NULL);
		if (!r) {
			tpp_unlock_rwlock(&router_lock);
			return -1; /* error already logged */
		}
		r->initiator = 1;

		/* since we connected we should add a context */
		if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
			tpp_unlock_rwlock(&router_lock);
			tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
			return -1;
		}
		ctx->ptr = r;
		ctx->type = TPP_ROUTER_NODE;

		tpp_log(LOG_INFO, NULL, "Connecting to pbs_comm %s", tpp_conf->routers[j]);

		if (tpp_transport_connect(tpp_conf->routers[j], 0, ctx, &r->conn_fd) == -1) {
			tpp_unlock_rwlock(&router_lock);
			return -1;
		}

		j++;
	}
	tpp_unlock_rwlock(&router_lock);

	sleep(1);
	return 0;
}

/**
 * @brief
 *	Shuts down the tpp library gracefully
 *
 * @par Functionality
 *	shuts down the IO threads
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_router_shutdown()
{
	tpp_going_down = 1;

	TPP_DBPRT("from pid = %d", getpid());
	tpp_transport_shutdown();

	free_tpp_config(tpp_conf);
}

/**
 * @brief
 *	Terminates (un-gracefully) the tpp library
 *
 * @par Functionality
 *	Typically to be called after a fork. Just a placeholder
 *	function for now. Does not do anything.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_router_terminate()
{
	return;
}
