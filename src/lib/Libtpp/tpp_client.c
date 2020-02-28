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

/**
 * @file	tpp_client.c
 *
 * @brief	Client side of the TCP router based network
 *
 * @par		Functionality:
 *
 *		TPP = TCP based Packet Protocol. This layer uses TCP in a multi-
 *		hop router based network topology to deliver packets to desired
 *		destinations. LEAF (end) nodes are connected to ROUTERS via
 *		persistent TCP connections. The ROUTER has intelligence to route
 *		packets to appropriate destination leaves or other routers.
 *
 *		This is the client side (referred to as leaf) in the tpp network
 *		topology. This compiles into the overall tpp library, and is
 *		linked to the PBS daemons. This code file implements the
 *		rpp_ interface functions that the daemons use to communicate
 *		with other daemons.
 *
 *		The code is driven by 2 threads. The Application thread (from
 *		the daemons) calls the main interfaces (rpp/tpp_xxx functions).
 *		When a piece of data is to be transmitted, its queued to a
 *		stream, and another independent thread drives the actual IO of
 *		the data. We refer to these two threads in the comments as
 *		IO thread and APP thread.
 *
 *		This also presents a single fd (a pipe) that can be used
 *		by the application to monitor for incoming data or events on
 *		the transport channel (much like the way a datagram socket works).
 *		This fd can be used by the application using a typical select or
 *		poll system call.
 *
 *		The functions in this code file are clearly de-marked as to which
 *		of the two threads drives them. In certain rare cases, a function
 *		or data structure is used by both the threads, and therefore is
 *		synchronized using a mutex, but in general, most functions are
 *		driven by only one thread. This allows for a minimal contention
 *		design, requiring minimal synchronization primitives.
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <string.h>
#include <sys/time.h>
#ifndef WIN32
#include <stdint.h>
#include <stdlib.h>
#endif

#include "avltree.h"
#include "libpbs.h"
#include "rpp.h"
#include "dis.h"
#include "tpp_common.h"
#include "auth.h"

/*
 * app_mbox is the "monitoring mechanism" for the application
 * send notifications to the application about incoming data
 * or events. THIS IS EDGE TRIGGERED. Once triggered, app must
 * read all the data available, or else, it could end up with
 * a situation where data exists to be read, but there is no
 * notification to wake up waiting app thread from select/poll.
 */
tpp_mbox_t app_mbox;

static int tpp_child_terminated = 0; /* whether a forked child called tpp_terminate or not? */

/* counters for various statistics */
int oopkt_cnt = 0;  /* number of out of order packets received */
int duppkt_cnt = 0; /* number of duplicate packets received */

static struct tpp_config *tpp_conf; /* the global TPP configuration file */

static tpp_addr_t *leaf_addrs = NULL;
static int leaf_addr_count = 0;

/*
 * We maintain queues for acks. When we receive data, we queue an ack with a max
 * expiry time. The ack packet is sent out "piggy-backed" on a outgoing data
 * packet or is sent out by itself, if the timer had expired.
 *
 * While queueing, we add the ack_info to two types of queues.
 * One, the global queue of all acks/retries, another is a per-stream queue.
 * This is done to make the code efficient.
 * There are occasions when we need to walk the list of global
 * acks pending to be sent out to see which ones need to be sent out first. In
 * such a case we walk the global queue. In other cases (like when a stream is
 * being closed), we walk the retry/ack queue associated with
 * the stream to delete pending acks.
 *
 * The memory allocated for the ack or retry info is only one, the
 * pointer to this structure is placed in both the queues (per-stream one and
 * the global one). Consequently, when we remove a ack-info (or retry-info) from
 * one of the queues, we need to remove it from the other queue too. And to be
 * able to do that, we store locations of the structure in either of the queues
 * inside the structure info itself.
 *
 * The above description is true for retry information too.
 *
 */

/*
 * The ack information that is queued to be sent later, possibly
 * piggy backed on an outgoing data packet.
 *
 * The ack info and the ack queues are worked up only by the IO thread.
 */
typedef struct {
	unsigned int sd;     /* the stream to which it belongs */
	unsigned int seq_no; /* the sequence number being acknowledged */
	time_t ack_time;     /* the latest time at which the ack must be sent out */
	tpp_que_elem_t *global_ack_node; /*
					       * pointer to location in a global
					       * queue of all acks
					       */
	tpp_que_elem_t *strm_ack_node;   /*
					       * pointer to location in a queue of
					       * acks for this stream
					       */
} ack_info_t;
tpp_que_t global_ack_queue;           /* global ack queue for all streams */

/*
 * The retry information that is queued to be used later. When a data packet
 * is sent out, we do not know whether it will reach the destination for sure.
 * For resilience (in case of multiple routers) we save the data packet in a
 * retry structure. If we do not get an ack for the sent packet within a
 * specified amount of time, we resend the packet, incrementing the retry count.
 *
 * When a packet is "saved" for resending later, a retry_info structure is
 * attached to it.
 *
 * The retry info and the retry queues are worked up only by the IO thread.
 *
 */
typedef struct {
	time_t retry_time; /* time at which data packet must be resent */
	short acked;       /* this packet is already ack'd, don't resend,
			    * delete when its out of the transport layer
			    */
	short sent_to_transport; /* don't delete a retry packet if it was sent
				  * to the transport layer
				  */
	tpp_packet_t *data_pkt; /* separate data (from hdr) pkt, mcast case */
	short retry_count;           /* number of times this data packet was re-sent */
	tpp_que_elem_t *global_retry_node;
	tpp_que_elem_t *strm_retry_node;
} retry_info_t;
tpp_que_t global_retry_queue; /* global retry queue for all streams */

/*
 * The structure to hold information about the multicast channel
 */
typedef struct {
	int num_fds;   /* number of streams that are part of mcast channel */
	int num_slots; /* number of slots in the channel (for resizing) */
	int *strms;    /* array of member stream descriptors */
	int *seqs;     /* array of sequence number that were used to send */
} mcast_data_t;

/*
 * The stream structure. Information about each stream is maintained in this
 * structure.
 *
 * Various members of the stream structure are accessed by either of the threads
 * IO and APP. Some of the fields are set by the APP thread first time and then
 * on accessed/updated by the IO thread.
 */
typedef struct {
	unsigned char strm_type; /* normal stream or multicast stream */

	unsigned int sd;         /* source stream descriptor, APP thread assigns, IO thread uses */
	unsigned int dest_sd;    /* destination stream descriptor, IO thread only */
	unsigned int src_magic;  /* A magically unique number that identifies src stream uniquely */
	unsigned int dest_magic; /* A magically unique number that identifies dest stream uniquely */

	short used_locally;      /* Whether this stream was accessed locally by the APP, APP thread only */

	unsigned int send_seq_no; /* APP thread only, sequence number of the next packet to be sent */
	unsigned int seq_no_expected; /* IO thread only, sequence number of the next packet expected */

	unsigned short u_state;   /* stream state, APP thread updates, IO thread read-only */
	unsigned short t_state;
	short lasterr;            /* updated by IO thread only, for future use */

	short num_unacked_pkts;   /* IO thread - number of unacked packets on wire */

	tpp_addr_t src_addr;  /* address of the source host */
	tpp_addr_t dest_addr; /* address of destination host - set by APP thread, read-only by IO thread */

	void *user_data;            /* user data set by tpp_dis functions. Basically used for DIS encoding */

	tpp_packet_t *part_recv_pkt; /* buffer to keeping part packets received - IO thread only */
	tpp_que_t recv_queue; /* received packets - APP thread only */
	tpp_que_t oo_queue; /* Out of order packets - IO thread only */

	tpp_que_t ack_queue; /* queued acks - IO thread only */
	tpp_que_t retry_queue; /* list of shelved packets - IO thread only */

	mcast_data_t *mcast_data; /* multicast related data in case of multicast stream type */

	void (*close_func)(int); /* close function to be called when this stream is closed */

	tpp_que_elem_t *timeout_node; /* pointer to myself in the timeout streams queue */
} stream_t;

/*
 * Slot structure - Streams are part of an array of slots
 * Using the stream sd, its easy to index into this slotarray to find the
 * stream structure
 */
typedef struct {
	int slot_state;      /* state of the slot - used, free */
	stream_t *strm; /* pointer to the stream structure at this slot */
} stream_slot_t;
stream_slot_t *strmarray = NULL; /* array of streams */
pthread_mutex_t strmarray_lock;       /* global lock for the streams array */
unsigned int max_strms = 0;           /* total number of streams allocated */

/* the following two variables are used to quickly find out a unused slot */
unsigned int high_sd = UNINITIALIZED_INT; /* the highest stream sd used */
tpp_que_t freed_sd_queue;            /* last freed stream sd */
int freed_queue_count = 0;

/* AVL tree of streams - so that we can search faster inside it */
AVL_IX_DESC *AVL_streams = NULL;

/* following common structure is used to do a timed action on a stream */
typedef struct {
	unsigned int sd;
	time_t strm_action_time;
	void (*strm_action_func)(unsigned int);
} strm_action_info_t;

/* global queue of stream slots to be marked FREE after TPP_CLOSE_WAIT time,
 * or streams with OO packets that need to be closed due to inactivity
 */
tpp_que_t strm_action_queue;

/* leaf specific stream states */
#define TPP_STRM_STATE_OPEN             1   /* stream is open */
#define TPP_STRM_STATE_CLOSE            2   /* stream is closed */

#define TPP_TRNS_STATE_OPEN             1   /* stream open */
#define TPP_TRNS_STATE_PEER_CLOSED      2   /* stream closed by peer */
#define TPP_TRNS_STATE_NET_CLOSED       3   /* network closed (noroute etc) */

#define TPP_MCAST_SLOT_INC              100 /* inc members in mcast group */

/* the physical connection to the router from this leaf */
int router_tfd = -1;
tpp_router_t **routers = NULL;
int max_routers = 0;
int active_router = -1;
int app_thread_active_router = -1;
int no_active_router = 1;

/* forward declarations of functions used by this code file */

/* function pointers */
void (*the_app_net_down_handler)(void *data) = NULL;
void (*the_app_net_restore_handler)(void *data) = NULL;
time_t leaf_next_event_expiry(time_t now);

/* static functions */
static int connect_router(tpp_router_t *r);
static int get_active_router(int index);
static stream_t *get_strm_atomic(unsigned int sd);
static stream_t *get_strm(unsigned int sd);
static stream_t *alloc_stream(tpp_addr_t *src_addr, tpp_addr_t *dest_addr);
static void free_stream(unsigned int sd);
static void free_stream_resources(stream_t *strm);
static void del_retries(stream_t *);
static void del_acks(stream_t *);
static void check_pending_acks(time_t now);
static void check_retries(time_t now);
static void queue_strm_close(stream_t *);
static void strm_timeout_action(unsigned int sd);
static void enque_timeout_strm(stream_t *strm);
static tpp_que_elem_t *enque_retry_sorted(tpp_que_t *q, tpp_packet_t *pkt);
static void queue_strm_free(unsigned int sd);
static void act_strm(time_t now, int force);
static int send_app_strm_close(stream_t *strm, int cmd, int error);
static int shelve_pkt(tpp_packet_t *pkt, tpp_packet_t *data_pkt, time_t retry_time);
static int shelve_mcast_pkt(tpp_mcast_pkt_hdr_t *mcast_hdr, int tfd, int seq, tpp_packet_t *pkt);
static int queue_ack(stream_t *strm, unsigned char type, unsigned int seq_no_recvd);
static int send_ack_packet(ack_info_t *ack);
static int send_retry_packet(tpp_packet_t *pkt);
static int unshelve_pkt(stream_t *strm, int seq_no_acked);
static void *add_part_packet(stream_t *strm, void *data, int sz);
static int send_pkt_to_app(stream_t *strm, unsigned char type, void *data, int sz);
static stream_t *find_stream_with_dest(tpp_addr_t *dest_addr, unsigned int dest_sd, unsigned int dest_magic);
static int tpp_send_inner(int sd, void *data, int len, int full_len, int cmprsd_len);
static int send_spl_packet(stream_t *strm, int type);
static void flush_acks(stream_t *strm);
static void tpp_clr_retry(tpp_packet_t *pkt, stream_t *strm);
static int leaf_send_ctl_join(int tfd, void *data, void *c);

/* externally called functions */
int leaf_pkt_postsend_handler(int tfd, tpp_packet_t *pkt, void *extra);
int leaf_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *extra);
int leaf_pkt_handler(int tfd, void *data, int len, void *ctx, void *extra);
int leaf_close_handler(int tfd, int error, void *ctx, void *extra);
int leaf_timer_handler(time_t now);
int leaf_post_connect_handler(int tfd, void *data, void *c, void *extra);

/*
 * Whether tpp is in fault tolerant mode.
 * Must have multiple routers to be in fault tolerant mode
 * This variable is set to zero by tpp_init if it does not find > 1 routers
 * configured
 *
 */
static int tpp_fault_tolerant_mode = 1;

/**
 * @brief
 *	Helper function to get a stream pointer and slot state in an atomic fashion
 *
 * @par Functionality:
 *	Acquire a lock on the strmarray lock and return the stream pointer
 *
 * @param[in] sd - The stream descriptor
 *
 * @return - Stream pointer
 * @retval NULL - Bad stream index/descriptor
 * @retval !NULL - Associated stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static stream_t *
get_strm_atomic(unsigned int sd)
{
	stream_t *strm = NULL;

	tpp_lock(&strmarray_lock);
	if (sd < max_strms) {
		if (strmarray[sd].slot_state == TPP_SLOT_BUSY)
			strm = strmarray[sd].strm;
	}
	tpp_unlock(&strmarray_lock);

	return strm;
}

/**
 * @brief
 *	Helper function to get a stream pointer from a stream descriptor
 *
 * @par Functionality:
 *	Returns the stream pointer associated to the stream index. Does some
 *	error checking whether the stream slot is busy, and stream itself is
 *	open from an application point of view.
 *
 * @param[in] sd - The stream descriptor
 *
 * @return - Stream pointer
 * @retval NULL - Bad stream index/descriptor
 * @retval !NULL - Associated stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static stream_t *
get_strm(unsigned int sd)
{
	stream_t *strm;

	errno = 0;
	strm = get_strm_atomic(sd);
	if (!strm) {
		errno = EBADF;
		return NULL;
	}
	if (strm->u_state == TPP_STRM_STATE_CLOSE) {
		errno = ENOTCONN;
		return NULL;
	}
	return strm;
}

/**
 * @brief
 *	Sets the APP handler to be called in case the network connection from
 *	the leaf to the router is restored, or comes back up.
 *
 * @par Functionality:
 *	When a previously down connection between the leaf and router is
 *	restored or vice-versa, IO thread sends notification to APP thread. The
 *	APP thread, then, calls the handler prior registered by this setter
 *	function. This function is called by the APP to set such a handler.
 *	For example, in the case of pbs_server, such a handler is "ping_nodes".
 *
 * @see
 *	leaf_pkt_postsend_handler
 *	leaf_close_handler
 *
 * @param[in] - app_net_down_handler - ptr to a function (in the calling APP)
 *	    that must be called when the network link between leaf and router
 *	    goes down.

 * @param[in] - app_net_restore_handler - ptr to function (in the calling APP)
 *	    that must be called when the network link between leaf and router
 *	    is restored.
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_set_app_net_handler(void (*app_net_down_handler)(void *data), void (*app_net_restore_handler)(void *data))
{
	the_app_net_down_handler = app_net_down_handler;
	the_app_net_restore_handler = app_net_restore_handler;
}

static int
leaf_send_ctl_join(int tfd, void *data, void *c)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_router_t *r;
	tpp_join_pkt_hdr_t hdr;
	tpp_chunk_t chunks[2];

	if (!ctx)
		return 0;

	if (ctx->type == TPP_ROUTER_NODE) {
		int len;
		int i;

		r = (tpp_router_t *) ctx->ptr;
		r->state = TPP_ROUTER_STATE_CONNECTING;

		/* send a TPP_CTL_JOIN message */
		memset(&hdr, 0, sizeof(tpp_join_pkt_hdr_t)); /* only to satisfy valgrind */
		hdr.type = TPP_CTL_JOIN;
		hdr.node_type = tpp_conf->node_type;
		hdr.hop = 1;
		hdr.index = r->index;
		hdr.num_addrs = leaf_addr_count;

		/* log my own leaf name to help in troubleshooting later */
		for(i = 0; i < leaf_addr_count; i++) {
			sprintf(tpp_get_logbuf(), "Registering address %s to pbs_comm", tpp_netaddr(&leaf_addrs[i]));
			tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());
		}

		len = sizeof(tpp_join_pkt_hdr_t);
		chunks[0].data = &hdr;
		chunks[0].len = len;

		chunks[1].data = leaf_addrs;
		chunks[1].len = (leaf_addr_count * sizeof(tpp_addr_t));

		if (tpp_transport_vsend(r->conn_fd, chunks, 2) != 0) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_transport_vsend failed, err=%d", errno);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}
	}

	return 0;
}

/**
 * @brief
 *	The leaf post connect handler
 *
 * @par Functionality
 *	When the connection between this leaf and another is dropped, the IO
 *	thread continuously attempts to reconnect to it. If the connection is
 *	restored, then this prior registered function is called.
 *
 * @param[in] tfd - The actual IO connection on which data was about to be
 *			sent (unused)
 * @param[in] data - Any data the IO thread might want to pass to this function.
 *		     (unused)
 * @param[in] c - Context associated with this connection, points us to the
 *                router being connected to
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
int
leaf_post_connect_handler(int tfd, void *data, void *c, void *extra)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	conn_auth_t *authdata = (conn_auth_t *)extra;

	if (!ctx)
		return 0;

	if (ctx->type != TPP_ROUTER_NODE)
		return 0;

	if (strcmp(tpp_conf->auth_config->auth_method, AUTH_RESVPORT_NAME) != 0) {
		void *data_out = NULL;
		size_t len_out = 0;
		int is_handshake_done = 0;
		void *authctx = NULL;
		auth_def_t *authdef = NULL;

		if ((authdata = (conn_auth_t *)calloc(1, sizeof(conn_auth_t))) == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory in post connect handler");
			return -1;
		}

		authdef = get_auth(tpp_conf->auth_config->auth_method);
		if (authdef == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Failed to find authdef in post connect handler");
			return -1;
		}

		authdef->set_config((const pbs_auth_config_t *)tpp_conf->auth_config);

		if (authdef->create_ctx(&authctx, AUTH_CLIENT, tpp_transport_get_conn_hostname(tfd))) {
			tpp_log_func(LOG_CRIT, __func__, "Failed to create client auth context");
			return -1;
		}

		authdata->authctx = authctx;
		authdata->authdef = authdef;
		tpp_transport_set_conn_extra(tfd, authdata);

		if (authdef->process_handshake_data(authctx, NULL, 0, &data_out, &len_out, &is_handshake_done) != 0) {
			if (len_out > 0) {
				tpp_log_func(LOG_CRIT, __func__, (char *)data_out);
				free(data_out);
			}
			return -1;
		}

		if (len_out > 0) {
			tpp_auth_pkt_hdr_t ahdr = {0};
			tpp_chunk_t chunks[2] = {{0}};
			int fd = ((tpp_router_t *) ctx->ptr)->conn_fd;

			ahdr.type = TPP_AUTH_CTX;
			ahdr.for_encrypt = FOR_AUTH;
			strcpy(ahdr.auth_type, authdef->name);

			chunks[0].data = &ahdr;
			chunks[0].len = sizeof(tpp_auth_pkt_hdr_t);

			chunks[1].data = data_out;
			chunks[1].len = len_out;

			if (tpp_transport_vsend(fd, chunks, 2) != 0) {
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_transport_vsend failed, err=%d", errno);
				tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
				free(data_out);
				return -1;
			}
			free(data_out);
		}

		/*
		 * We didn't send any auth handshake data
		 * and auth handshake is not completed
		 * so error out as we should send some auth handshake data
		 * or auth handshake should be completed
		 */
		if (is_handshake_done == 0 && len_out == 0) {
			tpp_log_func(LOG_CRIT, __func__, "Auth handshake failed");
			return -1;
		}

		if (is_handshake_done != 1)
			return 0;
	}

	if (tpp_conf->auth_config->encrypt_mode == ENCRYPT_ALL) {
		if (strcmp(tpp_conf->auth_config->auth_method, tpp_conf->auth_config->encrypt_method) != 0) {
			void *data_out = NULL;
			size_t len_out = 0;
			int is_handshake_done = 0;
			void *authctx = NULL;
			auth_def_t *authdef = NULL;

			if ((authdata = (conn_auth_t *)calloc(1, sizeof(conn_auth_t))) == NULL) {
				tpp_log_func(LOG_CRIT, __func__, "Out of memory in post connect handler");
				return -1;
			}

			authdef = get_auth(tpp_conf->auth_config->encrypt_method);
			if (authdef == NULL) {
				tpp_log_func(LOG_CRIT, __func__, "Failed to find authdef in post connect handler");
				return -1;
			}

			authdef->set_config((const pbs_auth_config_t *)&(tpp_conf->auth_config));

			if (authdef->create_ctx(&authctx, AUTH_CLIENT, tpp_transport_get_conn_hostname(tfd))) {
				tpp_log_func(LOG_CRIT, __func__, "Failed to create client auth context");
				return -1;
			}

			authdata->encryptctx = authctx;
			authdata->encryptdef = authdef;
			tpp_transport_set_conn_extra(tfd, authdata);

			if (authdef->process_handshake_data(authctx, NULL, 0, &data_out, &len_out, &is_handshake_done) != 0) {
				if (len_out > 0) {
					tpp_log_func(LOG_CRIT, __func__, (char *)data_out);
					free(data_out);
				}
				return -1;
			}

			if (len_out > 0) {
				tpp_auth_pkt_hdr_t ahdr = {0};
				tpp_chunk_t chunks[2] = {{0}};
				int fd = ((tpp_router_t *) ctx->ptr)->conn_fd;

				ahdr.type = TPP_AUTH_CTX;
				ahdr.for_encrypt = FOR_ENCRYPT;
				strcpy(ahdr.auth_type, authdef->name);

				chunks[0].data = &ahdr;
				chunks[0].len = sizeof(tpp_auth_pkt_hdr_t);

				chunks[1].data = data_out;
				chunks[1].len = len_out;

				if (tpp_transport_vsend(fd, chunks, 2) != 0) {
					snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_transport_vsend failed, err=%d", errno);
					tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
					free(data_out);
					return -1;
				}
				free(data_out);
			}

			/*
			* We didn't send any auth handshake data
			* and auth handshake is not completed
			* so error out as we should send some auth handshake data
			* or auth handshake should be completed
			*/
			if (is_handshake_done == 0 && len_out == 0) {
				tpp_log_func(LOG_CRIT, __func__, "Auth handshake failed");
				return -1;
			}

			if (is_handshake_done != 1)
				return 0;
		} else {
			authdata->encryptctx = authdata->authctx;
			authdata->encryptdef = authdata->authdef;
			tpp_transport_set_conn_extra(tfd, authdata);
		}
	}

	/*
	 * Since we are in post conntect handler
	 * and we have completed authentication
	 * so send TPP_CTL_JOIN
	 */
	return leaf_send_ctl_join(tfd, data, c);
}

/**
 * @brief
 *	The function initiates a connection from the leaf to a router.
 *
 * @par Functionality:
 *	This function calls tpp_transport_connect (from the transport layer)
 *	and queues a "JOIN" message to be sent to the router once the connection
 *	is established.
 *
 *	The TPP_CONTROL_JOIN message is a control message that identifies the
 *	leaf's properties to the router (registers the leaf to the router).
 *	The properties of the leaf that are sent, are the type of the node, ie,
 *	its a leaf or another router in the network, its name.
 *
 * @see
 *	tpp_transport_connect
 *	tpp_transport_vsend
 *
 * @param[in] r - struct router - info of the router to connect to
 *
 * @return int
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
connect_router(tpp_router_t *r)
{
	tpp_context_t *ctx;

	/* since we connected we should add a context */
	if ((ctx = (tpp_context_t *) malloc(sizeof(tpp_context_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating tpp context");
		return -1;
	}
	ctx->ptr = r;
	ctx->type = TPP_ROUTER_NODE;

	/* initiate connections to the tpp router (single for now) */
	if (tpp_transport_connect(r->router_name, r->delay, ctx, &(r->conn_fd)) == -1) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Connection to pbs_comm %s failed", r->router_name);
		tpp_log_func(LOG_ERR, NULL, tpp_get_logbuf());
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Initializes the client side of the TPP library
 *
 * @par Functionality:
 *	This function creates the fd (pipe) that the APP can monitor for events,
 *	initializes the transport layer by calling tpp_transport_init.
 *	It initializes the various mutexes and global queues of structures.
 *	It also registers a set of "handlers" that the transport layer calls
 *	using the IO thread into the leaf logic code, to drive retries, acks
 *	etc.
 *
 * @see
 *	tpp_transport_init
 *	tpp_transport_set_handlers
 *
 * @param[in] cnf - The tpp configuration structure
 *
 * @return - The file descriptor that APP must use to monitor for events
 * @retval -1   - Function failed
 * @retval !=-1 - Success, read end of the pipe is returned to APP to monitor
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_init(struct tpp_config *cnf)
{
	int rc;
	int i;
	int app_fd;

	tpp_conf = cnf;
	if (tpp_conf->node_name == NULL) {
		snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP leaf node name is NULL");
		tpp_log_func(LOG_CRIT, NULL, log_buffer);
		return -1;
	}

	/* before doing anything else, initialize the key to the tls */
	if (tpp_init_tls_key() != 0) {
		/* can only use prints since tpp key init failed */
		fprintf(stderr, "Failed to initialize tls key\n");
		return -1;
	}

	snprintf(log_buffer, TPP_LOGBUF_SZ, "TPP leaf node names = %s", tpp_conf->node_name);
	tpp_log_func(LOG_CRIT, NULL, log_buffer);

	tpp_init_lock(&strmarray_lock);
	if (tpp_mbox_init(&app_mbox) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to create application mbox");
		return -1;
	}

	/* initialize the app_mbox */
	app_fd = tpp_mbox_getfd(&app_mbox);

	/* initialize the retry and ack queues */
	TPP_QUE_CLEAR(&global_ack_queue);
	TPP_QUE_CLEAR(&global_retry_queue);
	TPP_QUE_CLEAR(&strm_action_queue);
	TPP_QUE_CLEAR(&freed_sd_queue);

	AVL_streams = create_tree(AVL_DUP_KEYS_OK, sizeof(tpp_addr_t));
	if (AVL_streams == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to create AVL tree for leaves");
		return -1;
	}

	/* get the addresses associated with this leaf */
	leaf_addrs = tpp_get_addresses(tpp_conf->node_name, &leaf_addr_count);
	if (!leaf_addrs) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Failed to resolve address, err=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}

	/*
	 * first register handlers with the transport, so these functions are called
	 * from the IO thread from the transport layer
	 */
	tpp_transport_set_handlers(leaf_pkt_presend_handler, /* called before sending pkt */
		leaf_pkt_postsend_handler, /* called after sending a packet */
		leaf_pkt_handler, /* called when a packet arrives */
		leaf_close_handler, /* called when a connection closes */
		leaf_post_connect_handler, /* called when connection restores */
		leaf_timer_handler /* called after amt of time from previous handler */
		);

	/* initialize the tpp transport layer */
	if ((rc = tpp_transport_init(tpp_conf)) == -1)
		return -1;

	max_routers = 0;
	while (tpp_conf->routers[max_routers])
		max_routers++; /* count max_routers */

	if ((routers = calloc(max_routers, sizeof(tpp_router_t *))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating pbs_comms array");
		return -1;
	}
	routers[max_routers - 1] = NULL;

	if (max_routers == 1 && cnf->force_fault_tolerance == 0) {
		/*
		 * If only a single router is found, we cannot do any fault
		 * tolerance, so set tpp_fault_tolerant_mode to off.
		 */
		tpp_fault_tolerant_mode = 0;
		tpp_log_func(LOG_WARNING, NULL, "Single pbs_comm configured, TPP Fault tolerant mode disabled");
	}

	i = 0;

	/* initialize the router structures and initiate connections to them */
	while (tpp_conf->routers[i]) {
		if ((routers[i] = malloc(sizeof(tpp_router_t))) == NULL)  {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating pbs_comm structure");
			return -1;
		}

		routers[i]->router_name = tpp_conf->routers[i];
		routers[i]->conn_fd = -1;
		routers[i]->initiator = 1;
		routers[i]->state = TPP_ROUTER_STATE_DISCONNECTED;
		routers[i]->index = i;
		routers[i]->delay = 0;

		sprintf(tpp_get_logbuf(), "Connecting to pbs_comm %s", routers[i]->router_name);
		tpp_log_func(LOG_INFO, NULL, tpp_get_logbuf());

		/* connect to router and send initial join packet */
		if ((rc = connect_router(routers[i])) != 0)
			return -1;

		i++;
	}

	if (i == 0) {
		tpp_log_func(LOG_CRIT, NULL, "No pbs_comms configured, cannot start");
		return -1;
	}

#ifndef WIN32
	/* for unix, set a pthread_atfork handler */
	if (pthread_atfork(NULL, NULL, tpp_terminate) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "TPP atfork handler registration failed");
		return -1;
	}
#endif

	return (app_fd);
}

/**
 * @brief
 *	tpp/dis support routine for ending a message that was read
 *	Skips over decoding to the next message
 *
 * @param[in] - fd - Tpp channel whose dis read packet has to be purged
 *
 * @retval	0 Success
 * @retval	-1 error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_eom(int fd)
{
	tpp_packet_t *p;
	stream_t *strm;
	pbs_tcp_chan_t *tpp;

	/* check for bad file descriptor */
	if (fd < 0)
		return -1;

	TPP_DBPRT(("sd=%d", fd));
	strm = get_strm(fd);
	if (!strm) {
		TPP_DBPRT(("Bad sd %d", fd));
		return -1;
	}
	p = tpp_deque(&strm->recv_queue);
	tpp_free_pkt(p);
	tpp = tpp_get_user_data(fd);
	if (tpp != NULL) {
		/* initialize read buffer */
		dis_clear_buf(&tpp->readbuf);
	}
	return 0;
}

/**
 * @brief
 *	Opens a virtual connection to another leaf (another PBS daemon)
 *
 * @par Functionality:
 *	This function merely allocates a free stream slot from the array of
 *	streams and sets the destination host and port, and returns the slot
 *	index as the fd for the application to use to read/write to the virtual
 *	connection
 *
 * @param[in] dest_host - Hostname of the destination leaf
 * @param[in] port - The port at which the destination is available
 *
 * @return - The file descriptor that APP must use to do the IO
 * @retval -1   - Function failed
 * @retval !=-1 - Success, the fd for the APP to use is returned
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_open(char *dest_host, unsigned int port)
{
	stream_t *strm;
	char *dest;
	tpp_addr_t *addrs, dest_addr;
	int count;
	AVL_IX_REC *pkey;

	if ((dest = mk_hostname(dest_host, port)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory opening stream");
		return -1;
	}

	addrs = tpp_get_addresses(dest, &count);
	if (!addrs) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Failed to resolve address, err=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		free(dest);
		return -1;
	}
	memcpy(&dest_addr, addrs, sizeof(tpp_addr_t));
	free(addrs);

	tpp_lock(&strmarray_lock);

	/*
	 * Just try to find a fully open stream to use, else fall through
	 * to create a new stream. Any half closed streams will be closed
	 * elsewhere, either when network first dropped or if any message
	 * comes to such a half open stream
	 */

	if ((pkey = avlkey_create(AVL_streams, &dest_addr))) {
		if (avl_find_key(pkey, AVL_streams) == AVL_IX_OK) {
			while (1) {
				strm = pkey->recptr;
				if (strm->u_state == TPP_STRM_STATE_OPEN &&
						strm->t_state == TPP_TRNS_STATE_OPEN &&
						strm->used_locally == 1) {
					tpp_unlock(&strmarray_lock);
					free(pkey);

					TPP_DBPRT(("Stream for dest[%s] returned = %u", dest, strm->sd));
					free(dest);
					return strm->sd;
				}

				if (avl_next_key(pkey, AVL_streams) != AVL_IX_OK)
					break;

				if (memcmp(&pkey->key, &dest_addr, sizeof(tpp_addr_t)) != 0)
					break;
			}
		}
	}
	free(pkey);

	tpp_unlock(&strmarray_lock);

	/* by default use the first address of the host as the source address */
	if ((strm = alloc_stream(&leaf_addrs[0], &dest_addr)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream");
		free(dest);
		return -1;
	}

	/* set the used_locally flag, since the APP is aware of this fd */
	strm->used_locally = 1;

	TPP_DBPRT(("Stream for dest[%s] returned = %d", dest, strm->sd));
	free(dest);

	return strm->sd;
}

/**
 * @brief
 *	Increment a sequence number
 *
 * @par Functionality:
 *	Gets the next value of a sequence number, wrapping at MAX_SEQ_NUMBER.
 *
 * @param[in] seq_no - The current sequence number (of which we want the next)
 *
 * @return - The next value in the sequence
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static unsigned int
get_next_seq(unsigned int seq_no)
{
	seq_no++;
	if (seq_no >= MAX_SEQ_NUMBER)
		seq_no = 1;

	return seq_no;
}

/**
 * @brief
 *	Returns the index of the router which has an established TCP connection
 *
 * @par Functionality:
 *	Loops through the list of routers and returns the first one having
 *	an active TCP connection. Favors the first router index.
 *
 *	Attempts to find a router that has been connected for a while. This is
 *	done to avoid switching back to a primary (first) router immediately on
 *	connection completion, to allow other connections to the router to complete
 *	before we start using that router.
 *
 *	In case no router is found that had been connected for a while, simply
 *	choose from the first available connected router, disregarding connection
 *	age.
 *
 * @param[in] index - The router index that was last used to send messages
 *
 * @return - The index of an active router.
 * @retval -1   - Function failed
 * @retval !=-1 - Success, the index of the active router is returned
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
get_active_router(int index)
{
	int i;
	int oldest_index = -1;
	time_t oldest_time = 0;
	time_t now = time(0);

	if (routers == NULL)
		return -1;

	/*
	 * If the primary (index 0) router is connected, check if the
	 * router connection had aged enough time to ensure everything
	 * else is connected to this router
	 */
	if (routers[0]->state == TPP_ROUTER_STATE_CONNECTED) {
		if ((now - routers[0]->conn_time) > 5*TPP_CONNECT_RETRY_MAX) {
			return 0;
		}
	}

	/*
	 * If we had already been using an alternate router it should be good to use
	 * without checking connection age, since we were already using it
	 */
	if (index >= 0 && index < max_routers && routers[index] && routers[index]->state == TPP_ROUTER_STATE_CONNECTED)
		return index;

	/*
	 * Neither router @ index 0, nor last used router was good, so loop
	 * to find out a router with the connection that has aged fully, or
	 * in the process, find out the oldest connection.
	 */
	oldest_index = -1;
	oldest_time = now + 3600; /* initialize to a future time stamp */
	for (i = 0; i < max_routers; i++) {
		if (routers[i]->state == TPP_ROUTER_STATE_CONNECTED) {
			if ((now - routers[i]->conn_time) > 5*TPP_CONNECT_RETRY_MAX)
				return i;
			if (routers[i]->conn_time < oldest_time) {
				oldest_time = routers[i]->conn_time;
				oldest_index = i;
			}
		}
	}
	if (oldest_index > -1)
		return oldest_index;

	no_active_router = 1;
	return -1;
}

/**
 * @brief
 *	Sends data to a stream
 *
 * @par Functionality:
 *	Basically queues data to be sent by the IO thread to the desired
 *	destination (as specified by the stream descriptor)
 *
 * @param[in] sd - The stream descriptor to which to send data
 * @param[in] data - Pointer to the data block to be sent
 * @param[in] len - Length of the data block to be sent
 *
 * @return - The total length of data that was accepted to be sent
 * @retval -1   - Function failed
 * @retval !=-1 - Success, length of data that was accepted to be sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_send(int sd, void *data, int len)
{
	int to_send;
	void *p;
	unsigned int cmprsd_len = 0;
	tpp_packet_t *pkt = NULL;

	if (!get_strm(sd)) {
		TPP_DBPRT(("Bad sd %d", sd));
		return -1;
	}

	TPP_DBPRT(("Sending: sd=%d, len=%d", sd, len));

	if ((tpp_conf->compress == 1) && (len > TPP_SEND_SIZE)) {
		void *outbuf;

		outbuf = tpp_deflate(data, len, &cmprsd_len);
		if (outbuf == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "tpp deflate failed");
			return -1;
		}
		pkt = tpp_cr_pkt(outbuf, cmprsd_len, 0);
		if (pkt == NULL) {
			free(outbuf);
			return -1;
		}

		p = pkt->data;
		to_send = cmprsd_len;
	} else {
		p = data;
		cmprsd_len = len;
		to_send = len;
	}

	if (to_send > 0) {
		if (tpp_send_inner(sd, p, to_send, len, cmprsd_len) != to_send) {
			tpp_free_pkt(pkt);
			return -1;
		}
	}
	tpp_free_pkt(pkt);
	return len;
}

/**
 * @brief
 *	Helper function to send data to a stream, used by tpp_send to send
 *	each chunk of the larger data block.
 *
 * @par Functionality:
 *	Creates the internal data packet header and sends the data along with
 *	the header. tpp_send breaks the whole data into multiple manageable
 *	chunks and calls tpp_send_inner for each chunk
 *
 * @param[in] sd - The stream descriptor to which to send data
 * @param[in] data - Pointer to the chunk of data
 * @param[in] len - Length of the chunk of data
 * @param[in] full_len - Length of the whole data block to be sent
 * @param[in] cmprsd_len - length of compressed data
 *
 * @return - The total length of data that was accepted to be sent
 * @retval -1   - Function failed
 * @retval !=-1 - Success, length of data that was accepted to be sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
tpp_send_inner(int sd, void *data, int len, int full_len, int cmprsd_len)
{
	stream_t *strm;
	tpp_data_pkt_hdr_t dhdr;
	tpp_chunk_t chunks[2];

	strm = get_strm(sd);
	if (!strm) {
		TPP_DBPRT(("Bad sd %d", sd));
		return -1;
	}

	TPP_DBPRT(("**** sd=%d, len=%d, compr_len=%d, totlen=%d, dest_sd=%u, seq=%u", sd, len, cmprsd_len, full_len, strm->dest_sd, strm->send_seq_no));

	if (strm->strm_type == TPP_STRM_MCAST) {
		/* do other stuff */
		return tpp_mcast_send(sd, data, len, full_len, cmprsd_len);
	}

	/* this memset is not required, its only to satisfy valgrind */
	memset(&dhdr, 0, sizeof(tpp_data_pkt_hdr_t));
	dhdr.type = TPP_DATA;
	dhdr.src_sd = htonl(sd);
	dhdr.src_magic = htonl(strm->src_magic);
	dhdr.dest_sd = htonl(strm->dest_sd);

	dhdr.seq_no = htonl(strm->send_seq_no);
	strm->send_seq_no = get_next_seq(strm->send_seq_no);

	dhdr.ack_seq = htonl(UNINITIALIZED_INT);
	dhdr.dup = 0;
	dhdr.cmprsd_len = htonl(cmprsd_len);
	dhdr.totlen = htonl(full_len);
	memcpy(&dhdr.src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&dhdr.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	chunks[0].data = &dhdr;
	chunks[0].len = sizeof(tpp_data_pkt_hdr_t);

	chunks[1].data = data;
	chunks[1].len = len;

	app_thread_active_router = get_active_router(app_thread_active_router);
	if (app_thread_active_router == -1) {
		TPP_DBPRT(("no active router, sending TPP_CMD_NET_CLOSE sd=%u", strm->sd));
		send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
		return -1;
	}

	if (tpp_transport_vsend(routers[app_thread_active_router]->conn_fd, chunks, 2) == 0)
		return len;

	tpp_log_func(LOG_ERR, __func__, "tpp_transport_vsend failed in tpp_send");
	send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
	return -1;
}

/**
 * @brief
 *	poll function to check if any streams have a message/notification
 *	waiting to be read by the APP.
 *
 * @return - Descriptor of stream which has data/notification to be read
 * @retval -2   - No streams have outstanding/pending data/notifications
 * @retval != -2 - Stream descriptor that has pending data/notifications
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_poll(void)
{
	int tfd;
	if (tpp_ready_fds(&tfd, 1) == 1) {
		return tfd;
	}
	return -2;
}

/**
 * @brief
 *	Function to recv/read data from a tpp stream
 *
 * @par Functionality:
 *	This function reads the requested amount of bytes from the "current"
 *	position of the next available data packet in the "received" queue.
 *
 *	It advances the "current position" in the data packet, so subsequent
 *	reads on this stream reads the next bytes from the data packet.
 *	It never advances the "current position" past the end of the data
 *	packet. To move to the next packet, the APP must call "rpp_eom/tpp_eom".
 *
 * @param[in]  sd   - The stream descriptor to which to read data
 * @param[out] data - Pointer to the buffer to read data into
 * @param[in]  len  - Length of the buffer
 *
 * @return
 * @retval -1    - Error reading the stream (errno set EWOULDBLOCK if no more
 *		   data is available to be read)
 * @retval != -1 - Number of bytes of data actually read from the stream
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_recv(int sd, void *data, int len)
{
	tpp_que_elem_t *n;
	tpp_packet_t *cur_pkt = NULL;
	stream_t *strm;
	int offset, avl_bytes, trnsfr_bytes;

	errno = 0;
	if (len == 0)
		return 0;

	strm = get_strm(sd);
	if (!strm) {
		TPP_DBPRT(("Bad sd %d", sd));
		return -1;
	}

	strm->used_locally = 1;

	if ((n = TPP_QUE_HEAD(&strm->recv_queue)))
		cur_pkt = TPP_QUE_DATA(n);

	/* read from head */
	if (cur_pkt == NULL) {
		errno = EWOULDBLOCK;
		return -1; /* no data currently - would block */
	}

	offset = cur_pkt->pos - cur_pkt->data;
	avl_bytes = cur_pkt->len - offset;
	trnsfr_bytes = (len < avl_bytes) ? len : avl_bytes;

	if (trnsfr_bytes == 0) {
		errno = EWOULDBLOCK;
		return -1; /* no data currently - would block */
	}

	memcpy(data, cur_pkt->pos, trnsfr_bytes);
	cur_pkt->pos = cur_pkt->pos + trnsfr_bytes;

	return trnsfr_bytes;
}

/**
 * @brief
 *	Local function to allocate a stream structure
 *
 * @par Functionality:
 *	Allocates a stream structure and initializes its members. Adds the
 *	stream structure to a free slot on the array of streams. To find a free
 *	slot faster, it uses globals "last_freed_sd" and "high_sd". If it cannot
 *	find a free slot using these two indexes, it does a sequential search
 *	from the start of the streams array to find a free slot.
 *
 * @param[in] src_addr  - The address of the src host.
 * @param[in] dest_addr - The address of the destination host.
 *
 * @return	 - Pointer to the newly allocated stream structure
 * @retval NUll  - Error, out of memory
 * @retval !NULl - Ptr to the new stream
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static stream_t *
alloc_stream(tpp_addr_t *src_addr, tpp_addr_t *dest_addr)
{
	stream_t *strm;
	unsigned int sd = max_strms, i;
	void *data;
	unsigned int freed_sd = UNINITIALIZED_INT;

	errno = 0;

	tpp_lock(&strmarray_lock);

	data = tpp_deque(&freed_sd_queue);
	if (data) {
		freed_sd = (unsigned int)(intptr_t) data;
		freed_queue_count--;
	}

	if (freed_sd != UNINITIALIZED_INT && strmarray[freed_sd].slot_state == TPP_SLOT_FREE) {
		sd = freed_sd;
	} else if (high_sd != UNINITIALIZED_INT && max_strms > 0 && high_sd < max_strms - 1) {
		sd = high_sd + 1;
	} else {
		sd = max_strms;

		TPP_DBPRT(("***Searching for a free slot"));
		/* search for a free sd */
		for (i = 0; i < max_strms; i++) {
			if (strmarray[i].slot_state == TPP_SLOT_FREE) {
				sd = i;
				break;
			}
		}
	}

	if (high_sd == UNINITIALIZED_INT || sd > high_sd) {
		high_sd = sd; /* remember the max sd used */
	}

	strm = calloc(1, sizeof(stream_t));
	if (!strm) {
		tpp_unlock(&strmarray_lock);
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream");
		return NULL;
	}
	strm->strm_type = TPP_STRM_NORMAL;
	strm->sd = sd;
	strm->send_seq_no = 0; /* start with special zero */
	strm->dest_sd = UNINITIALIZED_INT;
	strm->dest_magic = UNINITIALIZED_INT;
	if (src_addr)
		memcpy(&strm->src_addr, src_addr, sizeof(tpp_addr_t));
	if (dest_addr)
		memcpy(&strm->dest_addr, dest_addr, sizeof(tpp_addr_t));
	strm->src_magic = (unsigned int) time(0); /* for now use time as the unique magic number */
	strm->u_state = TPP_STRM_STATE_OPEN;
	strm->t_state = TPP_TRNS_STATE_OPEN;

	strm->close_func = NULL;
	strm->timeout_node = NULL;

	TPP_QUE_CLEAR(&strm->recv_queue);
	TPP_QUE_CLEAR(&strm->oo_queue);
	TPP_QUE_CLEAR(&strm->ack_queue);
	TPP_QUE_CLEAR(&strm->retry_queue);

	/* set to stream array */
	if (max_strms == 0 || sd > max_strms - 1) {
		unsigned int newsize;
		void *p;

		/* resize strmarray */
		newsize = sd + 100;
		p = realloc(strmarray, sizeof(stream_slot_t) * newsize);
		if (!p) {
			free(strm);
			tpp_unlock(&strmarray_lock);
			tpp_log_func(LOG_CRIT, __func__, "Out of memory resizing stream array");
			return NULL;
		}
		strmarray = (stream_slot_t *) p;
		memset(&strmarray[max_strms], 0, (newsize - max_strms) * sizeof(stream_slot_t));
		max_strms = newsize;
	}

	strmarray[sd].slot_state = TPP_SLOT_BUSY;
	strmarray[sd].strm = strm;

	if (dest_addr) {
		/* also add stream to the AVL_streams with the dest as key */
		if (tree_add_del(AVL_streams, &strm->dest_addr, strm, TREE_OP_ADD) != 0) {
			sprintf(tpp_get_logbuf(), "Failed to add strm with sd=%u to streams", strm->sd);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			free(strm);
			tpp_unlock(&strmarray_lock);
			return NULL;
		}
	}

	TPP_DBPRT(("*** Allocated new stream, sd=%u, src_magic=%u", strm->sd, strm->src_magic));

	tpp_unlock(&strmarray_lock);

	return strm;
}

/**
 * @brief
 *	Socket address of the local side for the given sd
 *
 * @param[in] sd - The stream descriptor
 *
 * @return	 - Pointer to a static sockaddr structure
 * @retval NUll  - Error, failed to get socket address or bad stream descriptor
 * @retval !NULl - Ptr to the static sockaddr structure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
struct sockaddr_in *
tpp_localaddr(int fd)
{
	stream_t *strm;
	static struct sockaddr_in sa;

	strm = get_strm(fd);
	if (!strm)
		return NULL;

	memcpy((char *) &sa.sin_addr, &leaf_addrs->ip, sizeof(sa.sin_addr));
	sa.sin_port = htons(leaf_addrs->port);

	return (&sa);
}

/**
 * @brief
 *	Socket address of the remote side for the given sd
 *
 * @param[in] sd - The stream descriptor
 *
 * @return	 - Pointer to a static sockaddr structure
 * @retval NUll  - Error, failed to get socket address or bad stream descriptor
 * @retval !NULl - Ptr to the static sockaddr structure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
struct sockaddr_in *
tpp_getaddr(int fd)
{
	stream_t *strm;
	static struct sockaddr_in sa;

	strm = get_strm(fd);
	if (!strm)
		return NULL;

	memcpy((char *) &sa.sin_addr, &strm->dest_addr.ip, sizeof(sa.sin_addr));
	sa.sin_port = strm->dest_addr.port;

	return (&sa);
}

/**
 * @brief
 *	Convenience function to free router strutures
 *
 * @par MT-safe: yes
 *
 */
static void
free_routers()
{
	int i;

	for (i = 0; i < max_routers; i++)
		free(routers[i]);
	free(routers);

	free(tpp_conf->node_name);
	for (i = 0; tpp_conf->routers[i]; i++)
		free(tpp_conf->routers[i]);

	free(tpp_conf->routers);
}

/**
 * @brief
 *	Shuts down the tpp library gracefully
 *
 * @par Functionality
 *	Closes the APP notification fd, shuts down the IO thread
 *	and destroys all the streams.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_shutdown()
{
	unsigned int i;
	unsigned int sd;

	TPP_DBPRT(("from pid = %d", getpid()));

	tpp_mbox_destroy(&app_mbox, 1);

	tpp_going_down = 1;

	tpp_transport_shutdown();

	DIS_tpp_funcs();

	tpp_lock(&strmarray_lock);
	for (i = 0; i < max_strms; i++) {
		if (strmarray[i].slot_state == TPP_SLOT_BUSY) {
			sd = strmarray[i].strm->sd;
			dis_destroy_chan(sd);
			free_stream_resources(strmarray[i].strm);
			free_stream(sd);
			destroy_connection(sd);
		}
	}
	tpp_unlock(&strmarray_lock);
	if (strmarray)
		free(strmarray);
	tpp_destroy_lock(&strmarray_lock);

	free_routers();
}

/**
 * @brief
 *	Terminates (un-gracefully) the tpp library
 *
 * @par Functionality
 *	Typically to be called after a fork. Threads are not preserved after
 *	fork, so this function does not attempt to stop threads, just destroys
 *	the streams.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_terminate()
{
	/* Warning: Do not attempt to destroy any lock
	 * This is not required since our library is effectively
	 * not used after a fork. The function tpp_mbox_destroy
	 * calls pthread_mutex_destroy, so don't call them.
	 * Also never log anything from a terminate handler.
	 *
	 * Don't bother to free any TPP data as well, as the forked
	 * process is usually short lived and no point spending time
	 * freeing space on a short lived forked process. Besides,
	 * the TPP thread which is lost after fork might have been in
	 * between using these data when the fork happened, so freeing
	 * some structures might be dangerous.
	 *
	 * Thus the only thing we do here is to close file/sockets
	 * so that the kernel can recognize when a close happens from the
	 * main process.
	 *
	 */
	if (tpp_child_terminated == 1)
		return;

	/* set flag so this function is never entered within
	 * this process again, so no fear of double frees
	 */
	tpp_child_terminated = 1;

	tpp_transport_terminate();

	tpp_mbox_destroy(&app_mbox, 0);
}

/* NULL definitions for some unimplemented functions */
int
tpp_bind(unsigned int port)
{
	return 0;
}

/* NULL definitions for some unimplemented functions */
int
tpp_io(void)
{
	return 0;
}

/**
 * @brief
 *	Find which streams have pending notifications/data
 *
 * @param[out] sds    - Arrays to be filled with descriptors of streams
 *                      having pending notifications
 * @param[in] len - Length of supplied array
 *
 * @return Number of ready streams
 * @retval   -1  - Function failed
 * @retval !=-1  - Number of ready streams
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_ready_fds(int *sds, int len)
{
	int strms_found = 0;
	unsigned int sd = 0;
	int cmd = 0;
	void *data = NULL;
	stream_t *strm;

	errno = 0;

	/* tpp_fd works like a level triggered fd */
	while (strms_found < len) {
		data = NULL;
		if (tpp_mbox_read(&app_mbox, &sd, &cmd, &data) != 0) {
			if (errno == EWOULDBLOCK)
				break;
			else
				return -1;
		}

		if (cmd == TPP_CMD_NET_DATA) {
			tpp_packet_t *pkt = data;
			if ((strm = get_strm_atomic(sd))) {
				TPP_DBPRT(("sd=%u, cmd=%d, u_state=%d, t_state=%d, len=%d, dest_sd=%u", sd, cmd, strm->u_state, strm->t_state, pkt->len, strm->dest_sd));

				if (strm->u_state == TPP_STRM_STATE_OPEN) {
					/* add packet to recv queue */
					if (tpp_enque(&strm->recv_queue, pkt) == NULL) {
						tpp_log_func(LOG_CRIT, __func__, "Failed to queue received pkt");
						tpp_free_pkt(pkt);
						return -1;
					}
					sds[strms_found++] = sd;
				} else {
					TPP_DBPRT(("Data recvd on closed stream %u discarded", sd));
					tpp_free_pkt(pkt);
					/* respond back by sending the close packet once more
					 * does not matter if it is a retry anyway
					 */
					send_spl_packet(strm, TPP_CLOSE_STRM);
				}
			} else {
				TPP_DBPRT(("Data recvd on deleted stream %u discarded", sd));
				tpp_free_pkt(pkt);
			}
		} else if (cmd == TPP_CMD_PEER_CLOSE || cmd == TPP_CMD_NET_CLOSE) {

			if ((strm = get_strm_atomic(sd))) {
				TPP_DBPRT(("sd=%u, cmd=%d, u_state=%d, t_state=%d, data=%p", sd, cmd, strm->u_state, strm->t_state, data));

				if (strm->u_state == TPP_STRM_STATE_OPEN) {
					if (cmd == TPP_CMD_PEER_CLOSE) {
						/* ask app to close stream */
						TPP_DBPRT(("Sent peer close to stream sd=%u", sd));
						sds[strms_found++] = sd;

					} else if (cmd == TPP_CMD_NET_CLOSE) {
						/* network closed, so clear all pending data to be
						 * received, and signal that sd
						 */
						TPP_DBPRT(("Sent net close stream sd=%u", sd));
						sds[strms_found++] = sd;
					}
				} else {
					/* app already closed */
					queue_strm_close(strm);
				}
			}
		} else if (cmd == TPP_CMD_NET_RESTORE) {

			if (the_app_net_restore_handler)
				the_app_net_restore_handler(data);

		} else if (cmd == TPP_CMD_NET_DOWN) {

			if (the_app_net_down_handler)
				the_app_net_down_handler(data);
		}
	}
	return strms_found;
}

/**
 * @brief
 *	Get the user buffer pointer associated with the stream
 *
 * @par Functionality
 *	Used by the tpp_dis later to retrieve a previously associated buffer
 *	that is used to DIS encode/decode data before sending/after receiving
 *	Since this is associated with the stream, this eliminates the need for
 *	the dis layer to maintain a separate array of buffers for each stream.
 *
 * @param[in] sd - The stream descriptor
 *
 * @return Ptr to user buffer (previously set with tpp_set_user_data)
 * @retval NULL - Bad descriptor or not user buffer was set
 * @retval !NULL - Pts to user buffer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void *
tpp_get_user_data(int sd)
{
	stream_t *strm;

	errno = 0;
	strm = get_strm_atomic(sd);
	if (!strm) {
		errno = ENOTCONN;
		return NULL;
	}
	return strm->user_data;
}

/**
 * @brief
 *	Associated a user buffer with the stream
 *
 * @par Functionality
 *	Used by the tpp_dis later associate a buffer to the stream.
 *	Used by tppdis_get_user_data to encode/decode data before sending/after receiving
 *	Since this is associated with the stream, this eliminates the need for
 *	the dis layer to maintain a separate array of buffers for each stream.
 *
 * @param[in] sd - The stream descriptor
 * @param[in] user_data - The user buffer allocated by the tpp_dis layer
 *
 * @return Error code
 * @retval -1 - Bad stream descriptor
 * @retval 0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_set_user_data(int sd, void *user_data)
{
	stream_t *strm;

	errno = 0;
	strm = get_strm_atomic(sd);
	if (!strm) {
		errno = ENOTCONN;
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Slot %d freed!", sd);
		tpp_log_func(LOG_WARNING, __func__, tpp_get_logbuf());
		return -1;
	}
	strm->user_data = user_data;
	return 0;
}

/**
 * @brief
 *	Associate a user close function to be called when the stream
 *	is being  closed
 *
 * @par Functionality
 *	When tpp_close is called, the user defined close function is triggered.
 *
 * @param[in] sd - The stream descriptor
 * @param[in] fnc - The function to register as a user defined close function
 *
 * @return Error code
 * @retval -1 - Bad stream descriptor
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
tpp_add_close_func(int sd, void (*func)(int))
{
	stream_t *strm;

	strm = get_strm(sd);
	if (!strm)
		return;

	tpp_lock(&strmarray_lock);
	strm->close_func = func;
	tpp_unlock(&strmarray_lock);
}

/**
 * @brief
 *	Close this side of the communication channel associated with the
 *	stream descriptor.
 *
 * @par Functionality
 *	Queues a close packet to be sent to the peer. The stream state itself
 *	is changed to TPP_STRM_STATE_CLOSE_WAIT signifying that its sent a
 *	close packet to the peer and waiting for the peer to acknowledge it.
 *	Meantime all sends and recvs are disabled on this stream.
 *
 * @param[in] sd - The stream descriptor
 *
 * @return Error code
 * @retval -1 - Failed to close the stream (bad state or bad stream)
 * @retval 0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_close(int sd)
{
	stream_t *strm;
	tpp_packet_t *p;

	strm = get_strm(sd);
	if (!strm) {
		return -1;
	}

	/* call any user defined close function */
	if (strm->close_func)
		strm->close_func(sd);

	tpp_lock(&strmarray_lock);

	TPP_DBPRT(("Closing sd=%d", sd));
	/* free the recv_queue also */
	while ((p = tpp_deque(&strm->recv_queue)))
		tpp_free_pkt(p);

	/* send a close packet */
	strm->u_state = TPP_STRM_STATE_CLOSE;

	tpp_unlock(&strmarray_lock);

	DIS_tpp_funcs();
	dis_destroy_chan(strm->sd);

	if (strm->t_state != TPP_TRNS_STATE_OPEN || send_spl_packet(strm, TPP_CLOSE_STRM) != 0)
		queue_strm_close(strm);

	/* for now we do not pass any data to the peer if this side closed */
	return 0;
}

/**
 * @brief
 *	Open a multicast channel to multiple parties.
 *
 *	Allocates a multicast stream and marks the type as TPP_STRM_MCAST
 *
 * @param[in] key - Any unique identifier to identify the channel with
 *
 * @return The file descriptor of the opened multicast channel
 * @retval   -1 - Failure
 * @retval !=-1 - Success, the opened channel fd
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mcast_open(void)
{
	stream_t *strm;

	if ((strm = alloc_stream(&leaf_addrs[0], NULL)) == NULL) {
		return -1;
	}

	TPP_DBPRT(("tpp_mcast_open called with fd=%u", strm->sd));

	strm->used_locally = 1;
	strm->strm_type = TPP_STRM_MCAST;
	return strm->sd;
}

/**
 * @brief
 *	Add a stream to the multicast channel
 *
 * @param[in] mtfd - The multicast channel to which to add streams to
 * @param[in] tfd - Array of stream descriptors to add to the multicast stream
 *
 * @return	Error code
 * @retval   -1 - Failure
 * @retval    0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mcast_add_strm(int mtfd, int tfd)
{
	void *p;
	stream_t *mstrm;
	stream_t *strm;

	mstrm = get_strm_atomic(mtfd);
	if (!mstrm) {
		errno = ENOTCONN;
		return -1;
	}

	strm = get_strm(tfd);
	if (!strm) {
		errno = ENOTCONN;
		return -1;
	}

	if (!mstrm->mcast_data) {
		mstrm->mcast_data = malloc(sizeof(mcast_data_t));
		if (!mstrm->mcast_data) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating mcast data");
			return -1;
		}
		mstrm->mcast_data->seqs = NULL;
		mstrm->mcast_data->strms = malloc(TPP_MCAST_SLOT_INC * sizeof(int));
		if (!mstrm->mcast_data->strms) {
			free(mstrm->mcast_data);
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
				"Out of memory allocating strm array of %lu bytes",
				(unsigned long)(TPP_MCAST_SLOT_INC * sizeof(int)));
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}
		mstrm->mcast_data->num_slots = TPP_MCAST_SLOT_INC;
		mstrm->mcast_data->num_fds = 0;
	} else if (mstrm->mcast_data->num_fds >= mstrm->mcast_data->num_slots) {
		p = realloc(mstrm->mcast_data->strms, (mstrm->mcast_data->num_slots + TPP_MCAST_SLOT_INC) * sizeof(int));
		if (!p) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
				"Out of memory resizing strm array to %lu bytes",
				(mstrm->mcast_data->num_slots + TPP_MCAST_SLOT_INC) * sizeof(int));
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}
		mstrm->mcast_data->strms = p;
		mstrm->mcast_data->num_slots += TPP_MCAST_SLOT_INC;
	}
	mstrm->mcast_data->strms[mstrm->mcast_data->num_fds++] = tfd;

	return 0;
}

/**
 * @brief
 *	Return the current array of members of the mcast stream
 *
 * @param[in] mtfd - The multicast channel
 * @param[out] count - Return the number of members
 *
 * @return	member stream fd array
 * @retval   NULL  - Failure
 * @retval   !NULL - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int *
tpp_mcast_members(int mtfd, int *count)
{
	stream_t *strm;

	*count = 0;

	strm = get_strm_atomic(mtfd);
	if (!strm || !strm->mcast_data) {
		errno = ENOTCONN;
		return NULL;
	}

	*count = strm->mcast_data->num_fds;
	return strm->mcast_data->strms;
}

/**
 * @brief
 *	Duplicate a mcast_data structure
 *
 * @param[in]  m - The mcast data structure to clone
 *
 * @return	Pointer of the duplicate mcast_data structure
 * @retval 	NULL  - Failure (Out of memory)
 * @retval 	!NULL - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
mcast_data_t *
dup_mcast_data(mcast_data_t *m)
{
	mcast_data_t *d = malloc(sizeof(mcast_data_t));
	if (!d)
		return NULL;

	d->strms = malloc(sizeof(unsigned int) * m->num_fds);
	if (!d->strms) {
		free(d);
		return NULL;
	}
	memcpy(d->strms, m->strms, m->num_fds * sizeof(unsigned int));

	d->seqs = calloc(sizeof(unsigned int), m->num_fds);
	if (!d->seqs) {
		free(d->strms);
		free(d);
		return NULL;
	}

	d->num_fds = m->num_fds;
	d->num_slots = m->num_fds;
	return d;
}

/**
 * @brief
 *	Send a command notification to all member streams
 *
 * @param[in]  mtfd - The mcast stream
 * @param[in]  cmd  - The command to send
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
tpp_mcast_notify_members(int mtfd, int cmd)
{
	stream_t *mstrm;
	int i;

	mstrm = get_strm_atomic(mtfd);
	if (!mstrm || !mstrm->mcast_data) {
		errno = ENOTCONN;
		return;
	}

	for (i = 0; i < mstrm->mcast_data->num_fds; i++) {
		int tfd;
		stream_t *strm;

		tfd = mstrm->mcast_data->strms[i];
		strm = get_strm_atomic(tfd);
		if (!strm)
			continue;
		send_app_strm_close(strm, cmd, 0);
	}
}

/**
 * @brief
 *	Create a multicast packet and send the data to all member streams
 *
 * @param[in] mtfd - The multicast channel to which to send data
 * @param[in] data - The pointer to the block of data to send
 * @param[in] len  - Length of the data to send
 * @param[in] full_len - In case of large packets data is sent in chunks,
 *			 full_len is the total length of the data
 * @param[in] comprsd_len - Length of compressed data (if compressed)
 *
 * @return	Error code
 * @retval   -1 - Failure
 * @retval    0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mcast_send(int mtfd, void *data, unsigned int len, unsigned int full_len, unsigned int cmprsd_len)
{
	stream_t *mstrm;
	stream_t *strm;
	mcast_data_t *d = NULL;
	int i, totlen = 0;
	tpp_chunk_t chunks[3];
	tpp_mcast_pkt_hdr_t mhdr;
	tpp_mcast_pkt_info_t *minfo;
	tpp_mcast_pkt_info_t tmp_minfo;
	unsigned int cmpr_len = 0;
	void *minfo_buf = NULL;
	int minfo_len;
	int ret;
	int finish;
	void *def_ctx = NULL;

	mstrm = get_strm_atomic(mtfd);
	if (!mstrm || !mstrm->mcast_data) {
		errno = ENOTCONN;
		return -1;
	}

	d = dup_mcast_data(mstrm->mcast_data);
	if (!d) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory duplicating mcast data");
		goto err;
	}

	minfo_len = sizeof(tpp_mcast_pkt_info_t) * d->num_fds;

#ifdef DEBUG
	/* in debug mode satisfy valgrind by initializing header memory */
	memset(&mhdr, 0, sizeof(mhdr));
#endif

	/* header data */
	memset(&mhdr, 0, sizeof(tpp_mcast_pkt_hdr_t)); /* only to satisfy valgrind */
	mhdr.type = TPP_MCAST_DATA;
	mhdr.hop = 0;
	mhdr.data_cmprsd_len = htonl(cmprsd_len);
	mhdr.totlen = htonl(full_len);
	memcpy(&mhdr.src_addr, &mstrm->src_addr, sizeof(tpp_addr_t));
	mhdr.num_streams = htonl(d->num_fds);
	mhdr.info_len = htonl(minfo_len);

	chunks[0].data = &mhdr;
	chunks[0].len = sizeof(tpp_mcast_pkt_hdr_t);
	totlen = chunks[0].len;

	if (tpp_conf->compress == 1 && minfo_len > TPP_SEND_SIZE) {
		def_ctx = tpp_multi_deflate_init(minfo_len);
		if (def_ctx == NULL)
			goto err;
	} else {
		minfo_buf = malloc(minfo_len);
		if (!minfo_buf) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
				"Out of memory allocating mcast buffer of %d bytes", minfo_len);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			goto err;
		}
	}

	for (i = 0; i < d->num_fds; i++) {
		strm = get_strm_atomic(d->strms[i]);
		if (!strm) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Stream %d is not open", d->strms[i]);
			tpp_log_func(LOG_ERR, NULL, tpp_get_logbuf());
			goto err;
		}

		/* per stream data */
		tmp_minfo.src_sd = htonl(strm->sd);
		tmp_minfo.src_magic = htonl(strm->src_magic);
		tmp_minfo.dest_sd = htonl(strm->dest_sd);
		tmp_minfo.seq_no = htonl(strm->send_seq_no);
		d->seqs[i] = strm->send_seq_no; /* store seq in packet for retry case */

		TPP_DBPRT(("*** src_sd=%u, dest_sd=%u, seq_no_sent=%u", strm->sd, strm->dest_sd, strm->send_seq_no));

		strm->send_seq_no = get_next_seq(strm->send_seq_no);
		memcpy(&tmp_minfo.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

		if (def_ctx == NULL) { /* no compression */
			minfo = (tpp_mcast_pkt_info_t *)((char *) minfo_buf + (i * sizeof(tpp_mcast_pkt_info_t)));
			memcpy(minfo, &tmp_minfo, sizeof(tpp_mcast_pkt_info_t));
		} else {
			finish = (i == (d->num_fds - 1)) ? 1 : 0;

			ret = tpp_multi_deflate_do(def_ctx, finish, &tmp_minfo, sizeof(tpp_mcast_pkt_info_t));
			if (ret != 0)
				goto err;
		}
	}

	if (def_ctx != NULL) {
		minfo_buf = tpp_multi_deflate_done(def_ctx, &cmpr_len);
		if (minfo_buf == NULL)
			goto err;

		TPP_DBPRT(("*** mcast_send hdr orig=%d, cmprsd=%u", minfo_len, cmpr_len));

		chunks[1].data = minfo_buf;
		chunks[1].len = cmpr_len;
		totlen += chunks[1].len;
		mhdr.info_cmprsd_len = htonl(cmpr_len);
	} else {
		TPP_DBPRT(("*** mcast_send uncompressed hdr orig=%d", minfo_len));
		chunks[1].data = minfo_buf;
		chunks[1].len = minfo_len;
		totlen += chunks[1].len;
		mhdr.info_cmprsd_len = 0;
	}
	def_ctx = NULL; /* done with compression */

	chunks[2].data = data;
	chunks[2].len = len;
	totlen += chunks[2].len;

	app_thread_active_router = get_active_router(app_thread_active_router);
	if (app_thread_active_router == -1) {
		tpp_log_func(LOG_ERR, __func__, "No active router");
		goto err;
	}

	TPP_DBPRT(("*** sending %d totlen", totlen));
	if (tpp_transport_vsend_extra(routers[app_thread_active_router]->conn_fd, chunks, 3, d) == 0) {
		free(minfo_buf);
		return len;
	}
	tpp_log_func(LOG_ERR, __func__, "tpp_transport_vsend failed in tpp_mcast_send"); /* fall through */

err:
	tpp_mcast_notify_members(mtfd, TPP_CMD_NET_CLOSE);
	if (def_ctx)
		tpp_multi_deflate_done(def_ctx, &cmpr_len);

	if (minfo_buf)
		free(minfo_buf);

	if (d) {
		if (d->strms)
			free(d->strms);
		if (d->seqs)
			free(d->seqs);
		free(d);
	}
	return -1;
}

/**
 * @brief
 *	Close a multicast channel
 *
 * @param[in] mtfd - The multicast channel to close
 *
 * @return	Error code
 * @retval   -1 - Failure
 * @retval    0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mcast_close(int mtfd)
{
	stream_t *strm;

	strm = get_strm_atomic(mtfd);
	if (!strm) {
		return -1;
	}
	DIS_tpp_funcs();
	dis_destroy_chan(strm->sd);

	free_stream_resources(strm);
	free_stream(mtfd);
	return 0;
}

/*
 * ============================================================================
 *
 * Functions below this are mostly driven by the IO thread. Some of them could
 * be accessed by both the IO and the App threads (and such functions need
 * synchronization)
 *
 * ============================================================================
 */

/**
 * @brief
 *	Add the stream to a queue of streams to be closed by the transport thread.
 *
 * @par Functionality
 *	Even of the app thread wants to free a stream, it adds the stream to this
 *	queue, so that the transport thread frees it, eliminating any thread
 *	races.
 *
 * @param[in] strm - The stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
queue_strm_close(stream_t *strm)
{
	strm_action_info_t *c;

	tpp_lock(&strmarray_lock); /* already under lock, dont need get_strm_atomic */

	if (strmarray[strm->sd].slot_state != TPP_SLOT_BUSY) {
		tpp_unlock(&strmarray_lock);
		return;
	}

	strmarray[strm->sd].slot_state = TPP_SLOT_DELETED;
	TPP_DBPRT(("Marked sd=%u DELETED", strm->sd));

	if ((c = malloc(sizeof(strm_action_info_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream free info");
		tpp_unlock(&strmarray_lock);
		return;
	}
	c->strm_action_time = time(0); /* asap */
	c->strm_action_func = queue_strm_free;
	c->sd = strm->sd;

	if (tpp_enque(&strm_action_queue, c) == NULL)
		tpp_log_func(LOG_CRIT, __func__, "Failed to Queue close");

	TPP_DBPRT(("Enqueued strm close for sd=%u", strm->sd));

	tpp_unlock(&strmarray_lock);

	if ((app_thread_active_router = get_active_router(app_thread_active_router)) != -1) {
		tpp_transport_wakeup_thrd(routers[app_thread_active_router]->conn_fd);
	}
	return;
}

/**
 * @brief
 *	Free stream and add stream slot to a queue of slots to be marked free
 *	after TPP_CLOSE_WAIT time.
 *
 * @par Functionality
 *	The slot is not marked free immediately, rather after a period. This is to
 *	ensure that wandering/delayed messages do not cause havoc.
 *	Additionally deletes the stream's entry in the Stream AVL tree. This
 *	function is called from both the APP thread and the IO thread, so it
 *	synchronizes using the strmarray_lock mutex.
 *
 * @param[in] sd - The stream descriptor
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
queue_strm_free(unsigned int sd)
{
	strm_action_info_t *c;
	stream_t *strm;

	tpp_lock(&strmarray_lock);

	strm = strmarray[sd].strm;

	flush_acks(strm);
	free_stream_resources(strm);
	TPP_DBPRT(("Freed sd=%u resources", sd));

	if ((c = malloc(sizeof(strm_action_info_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream action info");
		tpp_unlock(&strmarray_lock);
		return;
	}
	c->strm_action_time = time(0) + TPP_CLOSE_WAIT; /* time to close */
	c->strm_action_func = free_stream;
	c->sd = sd;

	if (tpp_enque(&strm_action_queue, c) == NULL)
		tpp_log_func(LOG_CRIT, __func__, "Failed to Queue Free");

	tpp_unlock(&strmarray_lock);

	return;
}

/**
 * @brief
 *	Send close to the app for a stream with out of order packets
 *	that passed its timeout value
 *
 * @par Functionality
 *	Send a stream close to the app, so that the app will close it
 *	eventually. This stream has not received a data packet in sequence
 *	for the timeout period and is therefore assumed to be abandoned.
 *
 * @param[in] sd - The stream descriptor
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
strm_timeout_action(unsigned int sd)
{
	stream_t *strm;

	tpp_lock(&strmarray_lock);
	strm = strmarray[sd].strm;

	TPP_DBPRT(("*** sd=%u timed out, closing", sd));

	send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
	tpp_unlock(&strmarray_lock);
}

/**
 * @brief
 *	Add the stream to a queue of streams that has out of order packets
 *
 * @par Functionality
 *	If a stream receives a packet out of order, we add to a queue of
 *	such streams with a timeout, so that if the stream does not get
 *	out of the out-of-order mode, then we close it automatically. This
 *	is to close all such abandoned streams, though the cases of such
 *	occurrences are very minimal
 *
 * @param[in] strm - The stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static void
enque_timeout_strm(stream_t *strm)
{
	strm_action_info_t *c;

	tpp_lock(&strmarray_lock);

	if (strmarray[strm->sd].slot_state != TPP_SLOT_BUSY) {
		tpp_unlock(&strmarray_lock);
		return;
	}

	TPP_DBPRT(("Add sd=%u to timeout streams queue", strm->sd));

	if ((c = malloc(sizeof(strm_action_info_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream free info");
		tpp_unlock(&strmarray_lock);
		return;
	}
	c->strm_action_time = time(0) + TPP_STRM_TIMEOUT;
	c->strm_action_func = strm_timeout_action;
	c->sd = strm->sd;

	if ((strm->timeout_node = tpp_enque(&strm_action_queue, c)) == NULL)
		tpp_log_func(LOG_CRIT, __func__, "Failed to Queue OO strm");

	tpp_unlock(&strmarray_lock);

	if ((app_thread_active_router = get_active_router(app_thread_active_router)) != -1) {
		tpp_transport_wakeup_thrd(routers[app_thread_active_router]->conn_fd);
	}
	return;
}

/**
 * @brief
 *	Pass on a close message from peer to the APP
 *
 * @par Functionality
 *	If this side had already called close, then instead of sending a
 *	notification to the app, it queues a close operation.
 *	If a NET_CLOSE happened (network between leaf and router broke), then
 *	delete all retry and ack packets and then send notification to APP.
 *	For PEER_CLOSE, don't delete retries and acks, just send notification to
 *	APP.
 *
 * @param[in] strm - Pointer to the stream
 * @param[in] cmd - TPP_CMD_NET_CLOSE - network closed between leaf & router
 *		            TPP_CMD_PEER_CLOSE - Peer sent a close message
 * @param[in] error - Error code in case of network closure, set for future use
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
send_app_strm_close(stream_t *strm, int cmd, int error)
{
	errno = 0;

	strm->lasterr = error;
	strm->t_state = TPP_TRNS_STATE_NET_CLOSED;

	if (tpp_mbox_post(&app_mbox, strm->sd, cmd, NULL) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Error writing to app mbox");
		return -1;
	}

	return 0;
}

/**
 * @brief
 *	Helper function to find a stream based on destination address,
 *	destination stream descriptor.
 *
 * @par Functionality
 *	Searches the AVL tree of streams based on the destination address.
 *	There could be several entries, since several streams could be open
 *	to the same destination. The AVL search quickly find the first entry
 *	that matches the address. Then on, we serially match the fd of the
 *	destination stream.
 *
 * @param[in] dest_addr  - address of the destination
 * @param[in] dest_sd    - The descriptor of the destination stream
 * @param[in] dest_magic - The magic id of the destination stream
 *
 * @return stream ptr of the stream if found
 * @retval NULL - If a matching stream was not found
 * @retval !NULL - The ptr to the matching stream
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static stream_t *
find_stream_with_dest(tpp_addr_t *dest_addr, unsigned int dest_sd, unsigned int dest_magic)
{
	AVL_IX_REC *pkey;
	stream_t *strm;

	pkey = avlkey_create(AVL_streams, dest_addr);
	if (pkey == NULL)
		return NULL;

	if (avl_find_key(pkey, AVL_streams) != AVL_IX_OK) {
		free(pkey);
		return NULL;
	}

	while (1) {
		strm = pkey->recptr;

		TPP_DBPRT(("sd=%u, dest_sd=%u, u_state=%d, t-state=%d, dest_magic=%u", strm->sd, strm->dest_sd, strm->u_state, strm->t_state, strm->dest_magic));
		if (strm->dest_sd == dest_sd && strm->dest_magic == dest_magic) {
			free(pkey);
			return strm;
		}

		if (avl_next_key(pkey, AVL_streams) != AVL_IX_OK) {
			free(pkey);
			return NULL;
		}

		if (memcmp(&pkey->key, dest_addr, sizeof(tpp_addr_t)) != 0) {
			free(pkey);
			return NULL;
		}
	}
	return NULL;
}

/**
 * @brief
 *	Queue a retry packet into the retry queue in a
 *	sorted manner.
 *
 * @param[in] q - Address of the queue to which to insert
 * @param[in] pkt- The retry packet that has to be inserted
 *
 * @return Ptr to the location where it was inserted
 * @retval NULL - If the insertion failed
 * @retval !NULL - The location where the packet was inserted
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static tpp_que_elem_t *
enque_retry_sorted(tpp_que_t *q, tpp_packet_t *pkt)
{
	tpp_que_elem_t *n = NULL;
	tpp_packet_t *pkt_queued = NULL;
	retry_info_t *rt = NULL;
	time_t time;

	if (!pkt->extra_data)
		return NULL;

	time = ((retry_info_t *) pkt->extra_data)->retry_time;

	n = TPP_QUE_TAIL(q);
	while (n) {
		pkt_queued = TPP_QUE_DATA(n);
		rt = (retry_info_t *) pkt_queued->extra_data;
		if (rt->retry_time <= time)
			break;
		n = n->prev;
	}
	if (n)
		return (tpp_que_ins_elem(q, n, pkt, 0));
	else
		return (tpp_enque(q, pkt));
}

/**
 * @brief
 *	Shelve a data packet so that it can be retried later again.
 *
 * @par Functionality
 *	If fault tolerant mode is enabled (multiple proxies), then after each
 *	data packet is sent out, the packet is shelved. This function is called
 *	by leaf_pkt_postsend_handler. A retry structure is created and populated
 *	with the retry_time, and added to the extra_data ptr of the data pkt.
 *
 * @param[in] pkt - The hdr packet (+data for regular pkts) to be shelved
 * @param[in] data_pkt - The data pkt, separate from hdr, in mcast cases
 * @param[in] retry_time - The time by which the retry packet must be resent
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
shelve_pkt(tpp_packet_t *pkt, tpp_packet_t *data_pkt, time_t retry_time)
{
	tpp_data_pkt_hdr_t *data = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
	retry_info_t *rt;
	int sd = ntohl(data->src_sd);

	stream_t *strm = get_strm_atomic(sd);
	if (!strm) {
		tpp_log_func(LOG_ERR, __func__, "Could not find stream");
		return -1;
	}

	rt = (retry_info_t *) pkt->extra_data;
	if (rt) {
		if (rt->acked == 1) {
			/* this packet was already acked from a previous (re)try */
			/* so release this packet */
			tpp_clr_retry(pkt, strm);

			tpp_free_pkt(rt->data_pkt);
			tpp_free_pkt(pkt);

			return 0;
		}
		rt->retry_time = retry_time;
		rt->sent_to_transport = 0;
		TPP_DBPRT(("Packet already shelved for stream %d, retry_info=%p", sd, rt));
		return 0;
	}

	if ((rt = malloc(sizeof(retry_info_t))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating retry info");
		free(rt);
		return -1;
	}

	rt->data_pkt = data_pkt;
	rt->acked = 0;
	rt->retry_time = retry_time;
	rt->retry_count = 0;
	rt->sent_to_transport = 0;
	pkt->extra_data = rt;

	/* enqueue in a time sorted manner */
	if ((rt->global_retry_node = enque_retry_sorted(&global_retry_queue, pkt)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to shelve data packet");
		free(rt);
		pkt->extra_data = NULL;
		return -1;
	}
	if ((rt->strm_retry_node = enque_retry_sorted(&strm->retry_queue, pkt)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to shelve data packet");
		tpp_que_del_elem(&global_retry_queue, rt->global_retry_node);
		free(rt);
		pkt->extra_data = NULL;
		return -1;
	}
	TPP_DBPRT(("Shelved packet for stream %d, retry_info=%p, pkt=%p, data=%p, pos=%p, data_pkt=%p", sd, rt, pkt, pkt->data, pkt->pos, data_pkt));

	return 0;
}

/**
 * @brief
 *	Shelve a mcast data packet so that it can be retried later again.
 *
 * @par Functionality
 *	If fault tolerant mode is enabled (multiple proxies), then after each
 *	data packet is sent out, the packet is shelved. This function is called
 *	by leaf_pkt_postsend_handler. A retry structure is created and populated
 *	with the retry_time, and added to the extra_data ptr of the data pkt.
 *
 * @param[in] pkt - The data packet that has to be shelved
 * @param[in] retry_time - The time by which the retry packet must be resent
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
shelve_mcast_pkt(tpp_mcast_pkt_hdr_t *mcast_hdr, int sd, int seq, tpp_packet_t *pkt)
{
	tpp_data_pkt_hdr_t indiv_dhdr;
	tpp_packet_t *indiv_pkt;
	stream_t *strm;
	int ntotlen;
	time_t now = time(0);

	strm = get_strm_atomic(sd);
	if (!strm)
		return -1;

	memset(&indiv_dhdr, 0, sizeof(tpp_data_pkt_hdr_t)); /* only to satisfy valgrind */
	indiv_dhdr.type = TPP_DATA;
	indiv_dhdr.src_sd = htonl(strm->sd);
	indiv_dhdr.src_magic = htonl(strm->src_magic);
	indiv_dhdr.dest_sd = htonl(strm->dest_sd);
	indiv_dhdr.seq_no = htonl(seq);

	indiv_dhdr.ack_seq = htonl(UNINITIALIZED_INT);
	indiv_dhdr.dup = 1;

	indiv_dhdr.cmprsd_len = mcast_hdr->data_cmprsd_len;
	indiv_dhdr.totlen = mcast_hdr->totlen;
	memcpy(&indiv_dhdr.src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&indiv_dhdr.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	indiv_pkt = tpp_cr_pkt(NULL, sizeof(int) + sizeof(tpp_data_pkt_hdr_t), 1);
	if (!indiv_pkt)
		return -1;

	ntotlen = htonl(sizeof(tpp_data_pkt_hdr_t));
	memcpy(indiv_pkt->data, &ntotlen, sizeof(int));
	memcpy(indiv_pkt->data + sizeof(int), &indiv_dhdr, sizeof(tpp_data_pkt_hdr_t));

	pkt->ref_count++;

	shelve_pkt(indiv_pkt, pkt, now + TPP_MAX_RETRY_DELAY);

	return 0;
}

/**
 * @brief
 *	Queue a acknowledgment packet to be sent out later
 *
 * @param[in] strm - Ptr to the stream to which this ack belongs
 * @param[in] type - The type of the incoming packet thats to be acked (unused)
 * @param[in] seq_no_recvd - The sequence number of the packet recvd.
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
queue_ack(stream_t *strm, unsigned char type, unsigned int seq_no_recvd)
{
	ack_info_t *ack;

	ack = malloc(sizeof(ack_info_t));
	if (!ack) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating ack info");
		return -1;
	}

	ack->sd = strm->sd;
	ack->ack_time = time(0) + TPP_MAX_ACK_DELAY;
	TPP_DBPRT(("Queueing ack for received sd=%u seq_no=%u", ack->sd, seq_no_recvd));
	ack->seq_no = seq_no_recvd;

	if ((ack->strm_ack_node = tpp_enque(&strm->ack_queue, ack)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to queue received pkt");
		free(ack);
		return -1;
	}
	if ((ack->global_ack_node = tpp_enque(&global_ack_queue, ack)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Failed to queue received pkt");
		tpp_que_del_elem(&strm->ack_queue, ack->strm_ack_node);
		free(ack);
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Send an ack packet to the destination stream set in the ack packet
 *
 * @param[in] ack - Ack packet
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
send_ack_packet(ack_info_t *ack)
{
	tpp_data_pkt_hdr_t dhdr;
	stream_t *strm;

	tpp_lock(&strmarray_lock);
	strm = strmarray[ack->sd].strm;
	if (!strm || strmarray[ack->sd].slot_state == TPP_SLOT_FREE) {
		tpp_unlock(&strmarray_lock);
		return -1;
	}
	tpp_unlock(&strmarray_lock);

	memset(&dhdr, 0, sizeof(tpp_data_pkt_hdr_t)); /* only for valgrind */
	dhdr.type = TPP_DATA;
	dhdr.cmprsd_len = 0;
	dhdr.src_sd = htonl(ack->sd);
	dhdr.src_magic = htonl(strm->src_magic);
	dhdr.dest_sd = htonl(strm->dest_sd);
	dhdr.seq_no = htonl(ack->seq_no); /* seq no to ack */
	dhdr.ack_seq = dhdr.seq_no; /* same as seq_no */
	dhdr.dup = 0;
	memcpy(&dhdr.src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&dhdr.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	active_router = get_active_router(active_router);
	if (active_router == -1) {
		return -1;
	}

	if (tpp_transport_send(routers[active_router]->conn_fd, &dhdr, sizeof(tpp_data_pkt_hdr_t)) != 0) {
		tpp_log_func(LOG_ERR, __func__, "tpp_transport_send failed");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Send an retry packet to the destination stream set in the retry packet
 *
 * @param[in] pkt - The data packet. The packet should have retry information
 *		    in pkt->extra_data
 *
 * @return Error code
 * @retval -1 - Failure
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
send_retry_packet(tpp_packet_t *pkt)
{
	tpp_data_pkt_hdr_t *dhdr = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
	int sd = ntohl(dhdr->src_sd);
	retry_info_t *rt;
	stream_t *strm;
	void *p;
	int totlen;

	if (!pkt->extra_data)
		return -1;

	strm = get_strm_atomic(sd);
	if (!strm){
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Bad stream pointer for stream=%d", sd);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}

	rt = (retry_info_t *) pkt->extra_data;
	if (rt->retry_count > rpp_retry) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Too many retries for stream=%d", sd);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}

	/*
	 * Right before sending lets see if we can set the dest_sd to improve
	 * receiver performance
	 */
	if (ntohl(dhdr->dest_sd) == UNINITIALIZED_INT) {
		dhdr->dest_sd = htonl(strm->dest_sd);
	}

	active_router = get_active_router(active_router);
	if (active_router == -1) {
		tpp_log_func(LOG_CRIT, __func__, "No active router");
		return -1;
	}

	/* in case of mcast shelved packets, we need to handle the common data
	 * from the rt->data_pkt and make it part of the packet itself
	 */
	if (rt->data_pkt != NULL) {
		totlen = pkt->len + rt->data_pkt->len;
		p = realloc(pkt->data, totlen);
		if (!p)
			return -1;

		pkt->data = p;
		pkt->pos = pkt->data + pkt->len;
		pkt->len = totlen;
		totlen = htonl(pkt->len - sizeof(int)); /* the length of the whole packet without the leading int */
		memcpy(pkt->data, &totlen, sizeof(int)); /* update length in pkt */
		memcpy(pkt->pos, rt->data_pkt->data, rt->data_pkt->len);
		tpp_free_pkt(rt->data_pkt);
		rt->data_pkt = NULL;
	}

	/* reset the send pointer to the top of data for a resend */
	pkt->pos = pkt->data;

	/*
	 * Set rt properties before sending, cause send could delete the
	 * packet itself
	 */
	rt->retry_count++;
	rt->sent_to_transport = 1;

	if (tpp_transport_send_raw(routers[active_router]->conn_fd, pkt) != 0) {
		tpp_log_func(LOG_ERR, __func__, "tpp_transport_send_raw failed");
		return -1;
	}

	return 0;
}

/**
 * @brief
 *	Walk the sorted global ack queue to send ack packets that have a send
 *	time < now
 *
 * @param[in] now - The current time
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
check_pending_acks(time_t now)
{
	tpp_que_elem_t *n = NULL;
	stream_t *strm;
	int rc;

	while ((n = TPP_QUE_HEAD(&global_ack_queue))) {
		ack_info_t *ack;

		ack = TPP_QUE_DATA(n);
		if (ack && (ack->ack_time <= now)) {
			n = tpp_que_del_elem(&global_ack_queue, n);
			ack->global_ack_node = NULL;

			/* get the strm pointer irrespective of slot state,
			 * thus get it directly instead of calling get_strm_atomic
			 */
			tpp_lock(&strmarray_lock);
			strm = strmarray[ack->sd].strm;
			tpp_unlock(&strmarray_lock);

			if (!strm)
				continue;

			if (ack->strm_ack_node) {
				tpp_que_del_elem(&strm->ack_queue, ack->strm_ack_node);
				ack->strm_ack_node = NULL;
			}

			TPP_DBPRT(("Sending delayed ack packet sd=%u seq=%u", ack->sd, ack->seq_no));
			rc = send_ack_packet(ack);

			if (rc != 0)
				send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);

			free(ack);
		} else
			break; /* stop if we found an ack thats not yet ready */
	}
}

/**
 * @brief
 *	Walk the strms ack list and send the acks right away
 *
 * @param[in] strm - the stream whose acks we need to flush out
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: yes
 *
 */
static void
flush_acks(stream_t *strm)
{
	tpp_que_elem_t *n = NULL;
	ack_info_t *ack;
	int rc;

	while ((n = TPP_QUE_HEAD(&strm->ack_queue))) {
		ack = TPP_QUE_DATA(n);
		if (ack) {
			n = tpp_que_del_elem(&strm->ack_queue, n);
			ack->strm_ack_node = NULL;

			if (ack->global_ack_node) {
				tpp_que_del_elem(&global_ack_queue, ack->global_ack_node);
				ack->global_ack_node = NULL;
			}

			TPP_DBPRT(("Flushing ack packet sd=%u seq=%u", ack->sd, ack->seq_no));
			rc = send_ack_packet(ack);
			if (rc != 0)
				send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);

			free(ack);
		}
	}
}

/**
 * @brief
 *	Walk the sorted global stream free queue and free  stream slot
 *	after TPP_CLOSE_WAIT time
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
act_strm(time_t now, int force)
{
	tpp_que_elem_t *n = NULL;

	tpp_lock(&strmarray_lock);
	while ((n = TPP_QUE_NEXT(&strm_action_queue, n))) {
		strm_action_info_t *c;

		c = TPP_QUE_DATA(n);
		if (c && ((c->strm_action_time <= now) || (force == 1))) {
			n = tpp_que_del_elem(&strm_action_queue, n);
			TPP_DBPRT(("Calling action function for stream %u", c->sd));
			c->strm_action_func(c->sd);
			if (c->strm_action_func == free_stream) {
				/* free stream itself clears elements from the strm_action_queue
				 * so restart walking from the head of strm_action_queue
				 */
				n = NULL;
			}
			free(c);
		}
	}
	tpp_unlock(&strmarray_lock);
}

/**
 * @brief
 *	Walk the sorted global retry queue to send retry packets that have send
 *	time < now
 *
 * @param[in] now - The current time
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
check_retries(time_t now)
{
	tpp_que_elem_t *n = NULL;
	int sd;
	stream_t *strm;
	tpp_data_pkt_hdr_t *dhdr;
	int count_sent_to_transport = 0;

	while ((n = TPP_QUE_NEXT(&global_retry_queue, n))) {
		tpp_packet_t *pkt;
		retry_info_t *rt;

		pkt = TPP_QUE_DATA(n);
		rt = (retry_info_t *) pkt->extra_data;
		if (rt && (rt->retry_time <= now)) {
			if (rt->sent_to_transport == 1) {
				count_sent_to_transport++;
				if (count_sent_to_transport > 1000) {
					sprintf(tpp_get_logbuf(),
					        "Count of sent_to_transport retry packet reached 1000, doing IO now");
					tpp_log_func(LOG_INFO, __func__, tpp_get_logbuf());
					break;
				}
				continue;
			}

			dhdr = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
			sd = ntohl(dhdr->src_sd);

			/* get the strm in whatever state it is in */
			tpp_lock(&strmarray_lock);
			strm = strmarray[sd].strm;
			tpp_unlock(&strmarray_lock);

			if (strm && strm->t_state == TPP_TRNS_STATE_OPEN) {

				TPP_DBPRT(("Sending retry packet for sd=%d seq=%u retry_time=%ld, pkt=%p",
						sd, ntohl(dhdr->seq_no), rt->retry_time, pkt));

				if (send_retry_packet(pkt) != 0) {
					sprintf(tpp_get_logbuf(), "Could not send retry, sending net_close for sd=%u", strm->sd);
					tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
					send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
				} else {
					/*
					 * in case of non fault tolerant mode
					 * packet and retry will be deleted in
					 * postsend handler
					 */
					if (tpp_fault_tolerant_mode == 1)
						rt->retry_time = time(0) + TPP_MAX_RETRY_DELAY;
				}
				n = NULL; /* list could be modified by send_retry_packet */
			} else {
				/* delete this */
				n = tpp_que_del_elem(&global_retry_queue, n);
				rt->global_retry_node = NULL;

				if (strm && rt->strm_retry_node) {
					tpp_que_del_elem(&strm->retry_queue, rt->strm_retry_node);
					rt->strm_retry_node = NULL;
				}

				if (rt->sent_to_transport == 0) {
					tpp_free_pkt(rt->data_pkt); /* for mcast data */
					tpp_free_pkt(pkt);
				}
			}
		} else
			break;
	}
}

/**
 * @brief
 *	Delete all queued ack packets belonging to a particular stream
 *
 * @param[in] strm - The stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
del_acks(stream_t *strm)
{
	tpp_que_elem_t *n = NULL;
	ack_info_t *ack;

	while ((n = TPP_QUE_NEXT(&strm->ack_queue, n))) {
		ack = TPP_QUE_DATA(n);
		if (ack) {
			n = tpp_que_del_elem(&strm->ack_queue, n);
			ack->strm_ack_node = NULL;

			if (ack->global_ack_node) {
				tpp_que_del_elem(&global_ack_queue, ack->global_ack_node);
				ack->global_ack_node = NULL;
			}

			free(ack);
		}
	}
}

/**
 * @brief
 *	Delete all queued retry packets belonging to a particular stream
 *
 * @param[in] strm - The stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
del_retries(stream_t *strm)
{
	tpp_que_elem_t *n = NULL;
	retry_info_t *rt;
	tpp_packet_t *pkt;

	while ((n = TPP_QUE_NEXT(&strm->retry_queue, n))) {
		pkt = TPP_QUE_DATA(n);
		n = tpp_que_del_elem(&strm->retry_queue, n);

		if (pkt && pkt->extra_data) {
			rt = (retry_info_t *) pkt->extra_data;

			rt->strm_retry_node = NULL;

			if (rt->global_retry_node) {
				tpp_que_del_elem(&global_retry_queue, rt->global_retry_node);
				rt->global_retry_node = NULL;
			}
			rt->acked = 1;
			if (rt->sent_to_transport == 0) {
				tpp_free_pkt(rt->data_pkt); /* for mcast packets */
				tpp_free_pkt(pkt);
			}
		}
	}
}

/**
 * @brief
 *	The timer handler function registered with the IO thread.
 *
 * @par Functionality
 *	This function is called periodically (after the amount of time as
 *	specified by leaf_next_event_expiry() function) by the IO thread. This
 *	drives the delayed ack, retry, close packets to be acted upon in time.
 *
 * @retval  - Time of next event expriry
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
leaf_timer_handler(time_t now)
{
	check_pending_acks(now);
	check_retries(now);
	act_strm(now, 0);

	return leaf_next_event_expiry(now);
}

/**
 * @brief
 *	This function returns the amt of time after which the nearest event
 *	happens (event = ack, retry, close etc). The IO thread calls this
 *	function to determine how much time to sleep before calling the
 *	timer_handler function.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
time_t
leaf_next_event_expiry(time_t now)
{
	time_t rc1 = -1;
	time_t rc2 = -1;
	time_t rc3 = -1;
	time_t res = -1;
	tpp_que_elem_t *n;
	retry_info_t *rt;
	ack_info_t *ack;
	tpp_packet_t *pkt;
	strm_action_info_t *f;

	tpp_lock(&strmarray_lock);

	if ((n = TPP_QUE_HEAD(&global_ack_queue))) {
		if ((ack = TPP_QUE_DATA(n)))
			rc1 = ack->ack_time;
	}

	if ((n = TPP_QUE_HEAD(&global_retry_queue))) {
		if ((pkt = TPP_QUE_DATA(n))) {
			if (pkt->extra_data) {
				rt = (retry_info_t *) pkt->extra_data;
				rc2 = rt->retry_time;
			}
		}
	}

	if ((n = TPP_QUE_HEAD(&strm_action_queue))) {
		if ((f = TPP_QUE_DATA(n)))
			rc3 = f->strm_action_time;
	}
	tpp_unlock(&strmarray_lock);

	if (rc1 > 0)
		res = rc1;

	if (rc2 > 0 && (res == -1 || rc2 < res))
		res = rc2;

	if (rc3 > 0 && (res == -1 || rc3 < res))
		res = rc3;

	if (res != -1)
		res = res - now;

	return res;
}

/**
 * @brief
 *	When a prior sent data packet is acked, this function is called to
 *	release it from the list of shelved packets.
 *
 *	Remove from stream's retry queue as well as from the global queue of
 *	retry packets.
 *
 * @param[in] seq_no_acked - The sequence number that was acked
 * @param[in] strm - Pointer to the stream to which ack packet arrived
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
unshelve_pkt(stream_t *strm, int seq_no_acked)
{
	tpp_que_elem_t *n = NULL;
	retry_info_t *rt;
	tpp_packet_t *pkt;
	tpp_data_pkt_hdr_t *dhdr;
	/* let go of the hanging data since it is now acked */

	TPP_DBPRT(("release acked: num_unacked = %d", strm->num_unacked_pkts));

	if (tpp_fault_tolerant_mode == 0) {
		/*
		 * first account for the number of packets on wire
		 * for flow control
		 */
		strm->num_unacked_pkts--;
		if (strm->num_unacked_pkts < 0)
			strm->num_unacked_pkts = 0;
		return 0;
	}

	while ((n = TPP_QUE_NEXT(&strm->retry_queue, n))) {
		if ((pkt = TPP_QUE_DATA(n))) {
			rt = (retry_info_t *) pkt->extra_data;
			dhdr = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
			if (ntohl(dhdr->seq_no) == seq_no_acked) {
				rt->acked = 1;
				TPP_DBPRT(("Releasing shelved packet sd=%u seq_no=%d type=%d", strm->sd, seq_no_acked, dhdr->type));

				strm->num_unacked_pkts--;
				if (strm->num_unacked_pkts < 0)
					strm->num_unacked_pkts = 0;

				if (rt->sent_to_transport == 0) {
					/* need to free this, since ack is received */
					n = tpp_que_del_elem(&strm->retry_queue, n);
					rt->strm_retry_node = NULL;

					if (rt->global_retry_node) {
						tpp_que_del_elem(&global_retry_queue, rt->global_retry_node);
						rt->global_retry_node = NULL;
					}

					if (rt->data_pkt) {
						tpp_free_pkt(rt->data_pkt);
						rt->data_pkt = NULL;
					}
					tpp_free_pkt(pkt);
				} /* else delete will be done by post_send */
				return 0;
			}
		}
	}
	return 0;
}

/**
 * @brief
 *	Adds part of a received packet to the received buffer
 *
 * @par Functionality
 *	If the incoming packet was compressed then this also inflates the data
 *	before storing. Adds the inflated data to stream->part_recv_pkt
 *
 * @param[in] sd - The descriptor of the stream
 * @param[in] data - The data that has to be stored
 * @param[in] sz - The size of the data
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void *
add_part_packet(stream_t *strm, void *data, int sz)
{
	tpp_packet_t *pkt;
	char *q;
	tpp_data_pkt_hdr_t *dhdr;
	int totlen;
	unsigned int cmprsd_len;
	tpp_packet_t *obj;

	dhdr = data;
	totlen = ntohl(dhdr->totlen);
	cmprsd_len = ntohl(dhdr->cmprsd_len);

	q = (char *) data + sizeof(tpp_data_pkt_hdr_t);

	pkt = strm->part_recv_pkt;
	TPP_DBPRT(("*** pkt=%p, sd=%u, sz=%d, totlen=%d, cmprsd_len=%u", (void *) pkt, strm->sd, sz, totlen, cmprsd_len));
	if (!pkt) {
		pkt = tpp_cr_pkt(NULL, totlen, 1);
		if (!pkt)
			return NULL;
		TPP_DBPRT(("Total length = %d, sz=%d", totlen, sz));
		strm->part_recv_pkt = pkt;
	}
	memcpy(pkt->pos, q, sz);
	pkt->pos += sz;

	/* in case of uncompressed packets, totlen == compressed_len
	 * so amount of data on wire is compressed len, so allways check against
	 * compressed_len
	 */
	if (strm->part_recv_pkt->pos - strm->part_recv_pkt->data == cmprsd_len) {
		strm->part_recv_pkt->pos = strm->part_recv_pkt->data;
		obj = strm->part_recv_pkt;
		strm->part_recv_pkt = NULL; /* reset */
		if (cmprsd_len != totlen) {
			tpp_packet_t *tmp = obj;
			void *uncmpr_data;

			if ((uncmpr_data = tpp_inflate(tmp->data, cmprsd_len, totlen))) {
				obj = tpp_cr_pkt(uncmpr_data, totlen, 0);
				if (!obj)
					free(uncmpr_data);
			} else {
				tpp_log_func(LOG_CRIT, __func__, "Decompression failed");
				obj = NULL;
			}
			tpp_free_pkt(tmp);
		}
		return obj; /* packet complete */
	}
	return NULL;
}

/**
 * @brief
 *	Send a data packet to the APP layer
 *
 * @par Functionality
 *	Writes the packet to the pipe that the APP is monitoring, when APP reads
 *	from the read end of the pipe, it gets the pointer to the data
 *
 * @param[in] sd - The descriptor of the stream
 * @param[in] type - The type of the data packet (data, close etc)
 * @param[in] data - The data that has to be stored
 * @param[in] sz - The size of the data
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
send_pkt_to_app(stream_t *strm, unsigned char type, void *data, int sz)
{
	int cmd;
	tpp_packet_t *obj;

	if (type == TPP_DATA) {
		obj = add_part_packet(strm, data, sz);
		if (obj == NULL)
			return 0; /* more data required */
		cmd = TPP_CMD_NET_DATA;
	} else {
		cmd = TPP_CMD_PEER_CLOSE;
		strm->t_state = TPP_TRNS_STATE_PEER_CLOSED;
		obj = NULL;
	}

	TPP_DBPRT(("Sending cmd=%d to sd=%u", cmd, strm->sd));

	/* since we received one packet, send notification to app */
	if (tpp_mbox_post(&app_mbox, strm->sd, cmd, obj) != 0) {
		tpp_log_func(LOG_CRIT, __func__, "Error writing to app mbox");
		if (obj)
			tpp_free_pkt(obj);
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Sends a close packet to a peer. This is called when this end calls
 *	tpp_close()
 *
 * @param[in] strm - The stream to which close packet has to be sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
send_spl_packet(stream_t *strm, int type)
{
	tpp_data_pkt_hdr_t dhdr;
	tpp_chunk_t chunks[2];

	TPP_DBPRT(("Sending CLOSE packet sd=%u, seq_id=%u, dest_sd=%u",
			strm->sd, strm->send_seq_no, strm->dest_sd));

	/* this memset is not required, its only to satisfy valgrind */
	memset(&dhdr, 0, sizeof(tpp_data_pkt_hdr_t));
	dhdr.type = type;
	dhdr.cmprsd_len = 0;
	dhdr.src_sd = htonl(strm->sd);
	dhdr.src_magic = htonl(strm->src_magic);
	dhdr.dest_sd = htonl(strm->dest_sd);
	dhdr.seq_no = htonl(strm->send_seq_no);

	/* don't increment seq number if close packet is being sent out */
	if (type != TPP_CLOSE_STRM)
		strm->send_seq_no = get_next_seq(strm->send_seq_no);

	dhdr.ack_seq = htonl(UNINITIALIZED_INT);
	dhdr.dup = 0;
	memcpy(&dhdr.src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&dhdr.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	chunks[0].data = &dhdr;
	chunks[0].len = sizeof(tpp_data_pkt_hdr_t);

	app_thread_active_router = get_active_router(app_thread_active_router);
	if (app_thread_active_router == -1) {
		return -1;
	}

	if (tpp_transport_vsend(routers[app_thread_active_router]->conn_fd, chunks, 1) != 0) {
		tpp_log_func(LOG_ERR, __func__, "tpp_transport_vsend failed");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Helper function to find a key in a stream and match the stream pointers
 *
 * @param[in] strm - The stream to which close packet has to be sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static AVL_IX_REC *
find_stream_tree_key(stream_t *strm)
{
	AVL_IX_REC *pkey;

	pkey = avlkey_create(AVL_streams, &strm->dest_addr);
	if (pkey == NULL) {
		sprintf(tpp_get_logbuf(), "Out of memory allocating avlkey for sd=%u", strm->sd);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return NULL;
	}

	if (avl_find_key(pkey, AVL_streams) == AVL_IX_OK) {
		do {
			stream_t *t_strm;

			t_strm = pkey->recptr;
			if (strm == t_strm)
				return pkey;

			if (memcmp(&pkey->key, &strm->dest_addr, sizeof(tpp_addr_t)) != 0)
				break;
		} while (avl_next_key(pkey, AVL_streams) == AVL_IX_OK);
	}
	free(pkey);
	return NULL;
}

/**
 * @brief
 *	Clear all retries, acks and destroy the stream finally
 *
 * @param[in] strm - The stream that needs to be freed
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
free_stream_resources(stream_t *strm)
{
	tpp_packet_t *p;

	if (!strm)
		return;

	tpp_lock(&strmarray_lock);

	TPP_DBPRT(("Freeing stream resources for sd=%u", strm->sd));

	while ((p = tpp_deque(&strm->oo_queue)))
		tpp_free_pkt(p);

	if (strm->part_recv_pkt)
		tpp_free_pkt(strm->part_recv_pkt);
	strm->part_recv_pkt = NULL;

	/* delete all pending acks and retries */
	del_retries(strm);
	del_acks(strm);

	strmarray[strm->sd].slot_state = TPP_SLOT_DELETED;

	tpp_unlock(&strmarray_lock);

	if (strm->mcast_data) {
		if (strm->mcast_data->strms)
			free(strm->mcast_data->strms);
		if (strm->mcast_data->seqs)
			free(strm->mcast_data->seqs);
		free(strm->mcast_data);
	}
}

/**
 * @brief
 *	Marks the stream slot as free to be reused
 *
 * @param[in] sd - The stream descriptor that needs to be freed
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
free_stream(unsigned int sd)
{
	stream_t *strm;
	tpp_que_elem_t *n = NULL;
	strm_action_info_t *c;

	TPP_DBPRT(("Freeing stream %u", sd));

	tpp_lock(&strmarray_lock);

	strm = strmarray[sd].strm;
	if (strm->strm_type != TPP_STRM_MCAST) {
		AVL_IX_REC *pkey;

		pkey = find_stream_tree_key(strm);
		if (pkey == NULL) {
			/* this should not happen ever */
			sprintf(tpp_get_logbuf(), "Failed finding strm with dest=%s, strm=%p, sd=%u", tpp_netaddr(&strm->dest_addr), strm, strm->sd);
			tpp_log_func(LOG_ERR, __func__, tpp_get_logbuf());
			tpp_unlock(&strmarray_lock);
			return;
		}

		avl_delete_key(pkey, AVL_streams);
		free(pkey);
	}

	/* empty all strm actions from the strm action queue */
	while ((n = TPP_QUE_NEXT(&strm_action_queue, n))) {
		c = TPP_QUE_DATA(n);
		if (c && (c->sd == sd)) {
			n = tpp_que_del_elem(&strm_action_queue, n);
			free(c);
		}
	}

	strmarray[sd].slot_state = TPP_SLOT_FREE;
	strmarray[sd].strm = NULL;
	free(strm);

	if (freed_queue_count < 100) {
		tpp_enque(&freed_sd_queue, (void *)(intptr_t) sd);
		freed_queue_count++;
	}

	tpp_unlock(&strmarray_lock);
}

/**
 * @brief
 *	The pre-send handler registered with the IO thread.
 *
 * @par Functionality
 *	When the IO thread is ready to send out a packet over the wire, it calls
 *	a prior registered "pre-send" handler. This pre-send handler (for leaves)
 *	piggy-backs any pending acks to this data packet. This function is also
 *	used to do the flow control (throttling) - by checking number of unacked
 *	packets against the setting "rpp_highwater"
 *
 * @param[in] tfd - The actual IO connection on which data was about to be
 *			sent (unused)
 * @param[in] pkt - The data packet that is about to be sent out by the IO thrd
 * @param[in] extra - The extra data associated with IO connection
 *
 * @par Side Effects:
 *	None
 *
 * @retval 0 - Success (Transport layer will send out the packet)
 * @retval -1 - Failure (Transport layer will not send packet and will delete packet)
 *
 * @par MT-safe: No
 *
 */
int
leaf_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *extra)
{
	tpp_data_pkt_hdr_t *data = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
	unsigned char type = data->type;
	int len = *((int *)(pkt->data));
	stream_t *strm;
	time_t now = time(0);
	conn_auth_t *authdata = (conn_auth_t *)extra;

	/* never encrypt auth context data */
	if (type == TPP_AUTH_CTX)
		return 0;

	/* never encrypt auth context data */
	if (type == TPP_AUTH_CTX)
		return 0;

	len = ntohl(len) - sizeof(tpp_data_pkt_hdr_t);

	if (type == TPP_CLOSE_STRM || (type == TPP_DATA && len > 0)) {
		unsigned int sd;
		unsigned int ack_no;

		sd = ntohl(data->src_sd);
		ack_no = ntohl(data->ack_seq);
		strm = get_strm_atomic(sd);
		if (!strm) {
			TPP_DBPRT(("Sending data on free/deleted slot sd=%u, seq=%u", sd, ack_no));
			tpp_clr_retry(pkt, strm);
			tpp_free_pkt(pkt);
			return -1;
		}

		if (strm->t_state == TPP_TRNS_STATE_OPEN) {
			/*
			 * both in the case of net or peer closed, it means the receiver
			 * is not expecting (or cannot) receive a packet, so never send it
			 * a data packet (ack packets are fine).
			 */

			/* if packet cannot be sent now then shelve them */
			if (strm->num_unacked_pkts > rpp_highwater) {
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
					"Stream %u reached highwater, %d, throttling, seq=%d", sd,
					strm->num_unacked_pkts, ntohl(data->seq_no));
				tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());
				if (shelve_pkt(pkt, NULL, now + TPP_THROTTLE_RETRY) != 0) {
					tpp_free_pkt(pkt);
				}

				/*
				 * return -1, so transport does not send packet,
				 * but do not delete packet
				 */
				return -1;
			}

			/* add an ack packet to the data packet if available */
			if (ack_no == UNINITIALIZED_INT) {
				ack_info_t *ack = tpp_deque(&strm->ack_queue);
				if (ack) {
					ack->strm_ack_node = NULL; /* since we dequeued from strm */

					ack_no = ack->seq_no;
					TPP_DBPRT(("Setting piggyback ack sd=%u, seq=%u", sd, ack_no));
					data->ack_seq = htonl(ack_no);

					/* since we dequeued the ack, also remove from global list */
					if (ack->global_ack_node) {
						tpp_que_del_elem(&global_ack_queue, ack->global_ack_node);
						ack->global_ack_node = NULL;
					}

					free(ack);
				}
			}
			return 0;
		} else {
			/* remove pkt from retry list in case its linked there */
			if (pkt->extra_data) {
				retry_info_t *rt = pkt->extra_data;
				tpp_free_pkt(rt->data_pkt); /* mcast data */
			}
			tpp_clr_retry(pkt, strm);

			/* delete the packet and return -1 so no data is sent out */
			tpp_free_pkt(pkt);
			return -1;
		}
	}

	/*
	 * if presend handler is called from handle_disconnect()
	 * then extra will be NULL and this is just a sending simulation
	 * so no encryption needed
	 */
	if (authdata == NULL)
		return 0;

	if (authdata->encryptdef) {
		char *msgbuf = NULL;
		void *data_out = NULL;
		size_t len_out = 0;
		size_t newpktlen = 0;
		char *pktdata = NULL;
		size_t npktlen = 0;

		if (authdata->cleartext != NULL)
			free(authdata->cleartext);

		authdata->cleartext = malloc(pkt->len);
		if (authdata->cleartext == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "malloc failure");
			return -1;
		}
		memcpy(authdata->cleartext, pkt->data, pkt->len);
		authdata->cleartext_len = pkt->len;

		if (authdata->encryptdef->encrypt_data(authdata->encryptctx, (void *)pkt->data, (size_t)pkt->len, &data_out, &len_out) != 0) {
			return -1;
		}

		if (pkt->len > 0 && len_out <= 0) {
			pbs_asprintf(&msgbuf, "invalid encrypted data len: %d, pktlen: %d", len_out, pkt->len);
			tpp_log_func(LOG_CRIT, __func__, msgbuf);
			free(msgbuf);
			return -1;
		}

		/* + sizeof(int) for npktlen and + 1 for TPP_ENCRYPTED_DATA */
		newpktlen = len_out + sizeof(int) + 1;
		pktdata = malloc(newpktlen);
		if (pktdata != NULL) {
			free(pkt->data);
			pkt->data = pktdata;
		} else {
			free(data_out);
			tpp_log_func(LOG_CRIT, __func__, "malloc failure");
			return -1;
		}

		pkt->pos = pkt->data;

		npktlen = htonl(len_out + 1);
		memcpy(pkt->pos, &npktlen, sizeof(int));
		pkt->pos = pkt->pos + sizeof(int);

		*pkt->pos = (char)TPP_ENCRYPTED_DATA;
		pkt->pos++;
		memcpy(pkt->pos, data_out, len_out);

		pkt->pos = pkt->data;
		pkt->len = newpktlen;

		free(data_out);
	}
	return 0;
}

/**
 * @brief
 *	The post-send handler registered with the IO thread.
 *
 * @par Functionality
 *	After the IO thread has sent out a packet over the wire, it calls
 *	a prior registered "post-send" handler. This handler (for leaves)
 *	takes care of shelving the packets into a retry queue, so that in case
 *	no acks are received after a while, the packet can be resent again.
 *	Shelving the data packet happens only if fault_tolerant mode is enabled,
 *	ie, if more than one routers are available for this leaf.
 *
 * @param[in] tfd - The actual IO connection on which data was sent (unused)
 * @param[in] pkt - The data packet that is sent out by the IO thrd
 * @param[in] extra - The extra data associated with IO connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
leaf_pkt_postsend_handler(int tfd, tpp_packet_t *pkt, void *extra)
{
	tpp_data_pkt_hdr_t *data = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
	int len = *((int *)(pkt->data));
	unsigned char type = data->type;
	time_t now = time(0);
	tpp_packet_t *shlvd_pkt = NULL;
	stream_t *strm;

	if (type == TPP_AUTH_CTX) {
		tpp_free_pkt(pkt);
		return 0;
	}

	if (type == TPP_ENCRYPTED_DATA) {
		conn_auth_t *authdata = (conn_auth_t *)extra;

		if (authdata->cleartext == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "postsend called with encrypted data but no saved cleartext data in tls");
			return -1;
		}

		free(pkt->data);
		pkt->data = authdata->cleartext;
		pkt->len = authdata->cleartext_len;
		pkt->pos = pkt->data;

		authdata->cleartext = NULL;
		authdata->cleartext_len = 0;

		/* re-calculate data, len and type as pkt changed */
		data = (tpp_data_pkt_hdr_t *)(pkt->data + sizeof(int));
		type = data->type;
		len = *((int *)(pkt->data));
	}

	len = ntohl(len) - sizeof(tpp_data_pkt_hdr_t);

	/*
	 * Set routers state to connected, if a join packet was successfully
	 * sent
	 */
	if (type == TPP_CTL_JOIN) {
		int i;
		for (i = 0; i < max_routers; i++) {
			if (routers[i]->conn_fd == tfd) {
				routers[i]->state = TPP_ROUTER_STATE_CONNECTED;
				routers[i]->delay = 0; /* reset connection retry time to 0 */
				routers[i]->conn_time = time(0); /* record connect time */
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Connected to pbs_comm %s", routers[i]->router_name);
				tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
				break;
			}
		}

		/* since we have atleast one router who connected now, do app restore */
		if (no_active_router == 1) {
			TPP_DBPRT(("Sending cmd to call App net restore handler"));
			if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_RESTORE, NULL) != 0) {
				tpp_log_func(LOG_CRIT, __func__, "Error writing to app mbox");
				tpp_free_pkt(pkt);
				return -1;
			}
			no_active_router = 0;
		}
	} else if (type == TPP_CLOSE_STRM || (type == TPP_DATA && len > 0)) {
		unsigned int sd;

		sd = ntohl(data->src_sd);
		strm = get_strm_atomic(sd);
		if (!strm) {
			tpp_clr_retry(pkt, strm);
			tpp_free_pkt(pkt);
			return -1;
		}

		/* increment number of pkts on the wire, since its not a dup packet */
		if (data->dup == 0)
			strm->num_unacked_pkts++;

		/* also shelve the packet now for retrying */
		if (tpp_fault_tolerant_mode == 1) {
			data->dup = 1;
			if (shelve_pkt(pkt, NULL, now + TPP_MAX_RETRY_DELAY) != 0)
				return -1;

			return 0; /* don't free packet, it could be retried */
		} else {
			/* since no fault tolerance, it should be removed from
			 * global retry list in case it was there due to flow
			 * control
			 */
			tpp_clr_retry(pkt, strm);

			/* pkt itself is deleted at the end of the function
			 * so just fall through to the end
			 */
		}
	} else if (type == TPP_MCAST_DATA) {
		/* incr number of unacked packets for each member stream */
		int i;
		tpp_mcast_pkt_hdr_t *mcast_hdr = (tpp_mcast_pkt_hdr_t *)(pkt->data + sizeof(int));
		mcast_data_t *d = (mcast_data_t *) pkt->extra_data;
		int info_cmprsd_len = ntohl(mcast_hdr->info_cmprsd_len);
		int info_len = ntohl(mcast_hdr->info_len);
		/* int num_streams = ntohl(mcast_hdr->num_streams); */
		void *payload;
		int payload_len;

		len = *((int *)(pkt->data));
		len = ntohl(len); /* overall mcast packet length */

		if (info_cmprsd_len > 0) {
			payload_len = len - sizeof(tpp_mcast_pkt_hdr_t) - info_cmprsd_len;
			payload = ((char *) mcast_hdr) + sizeof(tpp_mcast_pkt_hdr_t) + info_cmprsd_len;
		} else {
			payload_len = len - sizeof(tpp_mcast_pkt_hdr_t) - info_len;
			payload = ((char *) mcast_hdr) + sizeof(tpp_mcast_pkt_hdr_t) + info_len;
		}

		if (tpp_fault_tolerant_mode == 1) {
			shlvd_pkt = tpp_cr_pkt(payload, payload_len, 1);
			if (!shlvd_pkt) {
				if (d->strms)
					free(d->strms);
				if (d->seqs)
					free(d->seqs);
				tpp_free_pkt(pkt);
				return -1;
			}
			shlvd_pkt->ref_count = 0;
		}

		for (i = 0; i < d->num_fds; i++) {
			strm = get_strm_atomic(d->strms[i]);
			if (!strm) {
				TPP_DBPRT(("post handler on deleted stream"));
				if (d->strms)
					free(d->strms);
				if (d->seqs)
					free(d->seqs);

				/* in fault_tolerant mode, free the shared packet only if not shelved even once yet */
				if (tpp_fault_tolerant_mode == 1 && i == 0)
					tpp_free_pkt(shlvd_pkt);

				tpp_free_pkt(pkt);
				return -1;
			}
			strm->num_unacked_pkts++;

			/* also shelve the packet now for retrying */
			if (tpp_fault_tolerant_mode == 1) {
				TPP_DBPRT(("Shelving MCAST packet for strm=%d, seq=%d, mcast_hdr=%p, shlvd_pkt=%p",
						d->strms[i], d->seqs[i], mcast_hdr, shlvd_pkt));
				if (shelve_mcast_pkt(mcast_hdr, d->strms[i], d->seqs[i], shlvd_pkt) != 0) {
					/* free the shared packet only if not shelved even once yet */
					if (i == 0)
						tpp_free_pkt(shlvd_pkt);

					tpp_free_pkt(pkt);
					return -1;
				}
			}
		}

		if (d->strms)
			free(d->strms);
		if (d->seqs)
			free(d->seqs);

		/* let it fall through and free the packet */
	}

	if (type != TPP_MCAST_DATA)
		tpp_clr_retry(pkt, NULL); /* for mcast packet, extra_data is mcast related data */

	tpp_free_pkt(pkt);
	return 0;
}

/**
 * @brief
 *	Check a stream based on sd, destination address,
 *	destination stream descriptor.
 *
 * @param[in] src_sd - The stream with which to match
 * @param[in] dest_addr - address of the destination
 * @param[in] dest_sd   - The descriptor of the destination stream
 *
 * @return stream ptr of the stream info matches passed params
 * @retval NULL - If a matching stream was not found, or passed params do not match
 * @retval !NULL - The ptr to the matching stream
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static stream_t *
check_strm_valid(unsigned int src_sd, tpp_addr_t *dest_addr, int dest_sd)
{
	stream_t *strm = NULL;

	if (strmarray == NULL || src_sd >= max_strms) {
		TPP_DBPRT(("Must be data for old instance, ignoring"));
		return NULL;
	}

	if (strmarray[src_sd].slot_state != TPP_SLOT_BUSY) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Data to sd=%u which is %s", src_sd,
		         (strmarray[src_sd].slot_state == TPP_SLOT_DELETED ? "deleted":"freed"));
		return NULL;
	}

	strm = strmarray[src_sd].strm;

	if (strm->t_state != TPP_TRNS_STATE_OPEN) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Data to sd=%u whose transport is not open (t_state=%d)",
				 src_sd, strm->t_state);
		send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
		return NULL;
	}

	if ((strm->dest_sd != UNINITIALIZED_INT && strm->dest_sd != dest_sd) ||
			memcmp(&strm->dest_addr, dest_addr, sizeof(tpp_addr_t)) != 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Data to sd=%u mismatch dest info in stream", src_sd);
		return NULL;
	}

	return strm;
}

/**
 * @brief
 *	The received packet handler registered with the IO thread.
 *
 * @par Functionality
 *	When the IO thread is received a packet over the wire, it calls
 *	a prior registered "pkt-send" handler. This handler is responsible to
 *	decode the data in the packet and do the needful. This handler for the
 *	leaf checks whether data came in order, or is a duplicate packet. If
 *	OOO data arrived, then it is queued in a OOO queue, else the data is
 *	sent to the application to be read. If an acknowledgment for a prior
 *	sent packet is received, this handler releases any prior shelved packet.
 *	If a close packet is received, then a close notification is sent to the
 *	APP. If a prior sent close packet is acknowledged, then the stream is
 *	queued to be closed.
 *
 * @param[in] tfd - The actual IO connection on which data was about to be
 *			sent (unused)
 * @param[in] data - The pointer to the data that arrived
 * @param[in] len  - Length of the arrived data
 * @param[in] ctx - The context (prior associated, if any) with the IO thread
 *		    (unused at the leaf)
 * @param[in] extra - The extra data associated with IO connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
leaf_pkt_handler(int tfd, void *data, int len, void *ctx, void *extra)
{
	stream_t *strm;
	unsigned int sd = UNINITIALIZED_INT;
	unsigned char type;
	void *data_out = NULL;
	size_t len_out = 0;

	type = *((char *) data);
	errno = 0;

	if (type == TPP_AUTH_CTX) {
		tpp_auth_pkt_hdr_t ahdr = {0};
		size_t len_in = 0;
		void *data_in = NULL;
		int is_handshake_done = 0;
		conn_auth_t *authdata = (conn_auth_t *)extra;
		auth_def_t *authdef = NULL;
		void *authctx = NULL;
		char *method = NULL;

		if (authdata == NULL) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tfd=%d, No auth data found", tfd);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}

		memcpy(&ahdr, data, sizeof(tpp_auth_pkt_hdr_t));
		if (ahdr.for_encrypt == FOR_AUTH) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tfd=%d, Authentication method mismatch in connection", tfd);
			method = tpp_conf->auth_config->auth_method;
		} else {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tfd=%d, Encryption method mismatch in connection", tfd);
			method = tpp_conf->auth_config->encrypt_method;
		}
		if (strcmp(ahdr.auth_type, method) != 0) {
			tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());
			return -1;
		}
		len_in = (size_t)len - sizeof(tpp_auth_pkt_hdr_t);
		data_in = calloc(1, len_in);
		if (data_in == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating authdata credential");
			return -1;
		}
		memcpy(data_in, (char *)data + sizeof(tpp_auth_pkt_hdr_t), len_in);

		if (ahdr.for_encrypt == FOR_AUTH) {
			authdef = authdata->authdef;
			authctx = authdata->authctx;
		} else {
			authdef = authdata->encryptdef;
			authctx = authdata->encryptctx;
		}

		if (authdef->process_handshake_data(authctx, data_in, len_in, &data_out, &len_out, &is_handshake_done) != 0) {
			if (len_out > 0) {
				tpp_log_func(LOG_CRIT, __func__, (char *)data_out);
				free(data_out);
			}
			free(data_in);
			return -1;
		}

		if (len_out > 0) {
			tpp_chunk_t chunks[2] = {{0}};

			chunks[0].data = &ahdr;
			chunks[0].len = sizeof(tpp_auth_pkt_hdr_t);

			chunks[1].data = data_out;
			chunks[1].len = (int)len_out;

			if (tpp_transport_vsend(tfd, chunks, 2) != 0) {
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_transport_vsend failed, err=%d", errno);
				tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
				free(data_out);
				free(data_in);
				return -1;
			}
			free(data_in);
			free(data_out);
		}

		/*
		 * We didn't send any auth handshake data
		 * and auth handshake is not completed
		 * so error out as we should send some auth handshake data
		 * or auth handshake should be completed
		 */
		if (is_handshake_done == 0 && len_out == 0) {
			tpp_log_func(LOG_CRIT, __func__, "Failed to establish auth context");
			return -1;
		}

		if (is_handshake_done != 1)
			return 0;

		if (tpp_conf->auth_config->encrypt_mode == ENCRYPT_ALL && ahdr.for_encrypt == FOR_AUTH) {
			if (strcmp(tpp_conf->auth_config->auth_method, tpp_conf->auth_config->encrypt_method) != 0) {
				authdata = NULL;
				authdef = get_auth(tpp_conf->auth_config->encrypt_method);
				if (authdef == NULL) {
					tpp_log_func(LOG_CRIT, __func__, "Failed to find authdef in post connect handler");
					return -1;
				}

				authdef->set_config((const pbs_auth_config_t *)&(tpp_conf->auth_config));

				if (authdef->create_ctx(&authctx, AUTH_CLIENT, tpp_transport_get_conn_hostname(tfd))) {
					tpp_log_func(LOG_CRIT, __func__, "Failed to create client auth context");
					return -1;
				}

				authdata->encryptctx = authctx;
				authdata->encryptdef = authdef;
				tpp_transport_set_conn_extra(tfd, authdata);

				if (authdef->process_handshake_data(authctx, NULL, 0, &data_out, &len_out, &is_handshake_done) != 0) {
					if (len_out > 0) {
						tpp_log_func(LOG_CRIT, __func__, (char *)data_out);
						free(data_out);
					}
					return -1;
				}

				if (len_out > 0) {
					tpp_chunk_t chunks[2] = {{0}};

					ahdr.type = TPP_AUTH_CTX;
					ahdr.for_encrypt = FOR_ENCRYPT;
					strcpy(ahdr.auth_type, authdef->name);

					chunks[0].data = &ahdr;
					chunks[0].len = sizeof(tpp_auth_pkt_hdr_t);

					chunks[1].data = data_out;
					chunks[1].len = len_out;

					if (tpp_transport_vsend(tfd, chunks, 2) != 0) {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_transport_vsend failed, err=%d", errno);
						tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
						free(data_out);
						return -1;
					}
					free(data_out);
				}

				/*
				* We didn't send any auth handshake data
				* and auth handshake is not completed
				* so error out as we should send some auth handshake data
				* or auth handshake should be completed
				*/
				if (is_handshake_done == 0 && len_out == 0) {
					tpp_log_func(LOG_CRIT, __func__, "Auth handshake failed");
					return -1;
				}

				if (is_handshake_done != 1)
					return 0;
			} else {
				authdata->encryptctx = authdata->authctx;
				authdata->encryptdef = authdata->authdef;
				tpp_transport_set_conn_extra(tfd, authdata);
			}
		}

		/* send TPP_CTL_JOIN msg to router */
		return leaf_send_ctl_join(tfd, data, ctx);

	} else if (type == TPP_ENCRYPTED_DATA) {
		conn_auth_t *authdata = (conn_auth_t *)extra;
		char *msgbuf = NULL;

		if (authdata->encryptdef == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Auth method associated with connetion doesn't support decryption of data");
			return -1;
		}

		if (authdata->encryptdef->decrypt_data(authdata->encryptctx, (void *)((char *)data + 1), (size_t)len - 1, &data_out, &len_out) != 0) {
			return -1;
		}

		if (len_out == 0) {
			pbs_asprintf(&msgbuf, "invalid decrypted data len: %d, pktlen: %d", len_out, len - 1);
			tpp_log_func(LOG_CRIT, __func__, msgbuf);
			free(msgbuf);
			return -1;
		}

		data = (char *)data_out + sizeof(int);
		len = len_out - sizeof(int);

		/* re-calculate type as data changed */
		type = *((char *) data);
	}

	/* analyze data and see what message it is
	 * it could be a ctl message (node join/leave)
	 * or it could be a data message (for a particular stream fd).
	 */
	switch (type) {
		case TPP_CTL_MSG: {
			tpp_ctl_pkt_hdr_t *hdr = (tpp_ctl_pkt_hdr_t *) data;
			int code = hdr->code;

			if (code == TPP_MSG_NOROUTE) {
				unsigned int src_sd = ntohl(hdr->src_sd);
				strm = get_strm_atomic(src_sd);
				if (strm) {
					char *msg = ((char *) data) + sizeof(tpp_ctl_pkt_hdr_t);
					snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "sd %u, Received noroute to dest %s, msg=\"%s\"", src_sd,
								tpp_netaddr(&hdr->src_addr), msg);
#ifdef NAS /* localmod 149 */
					tpp_log_func(LOG_DEBUG, NULL, tpp_get_logbuf());
#else
					tpp_log_func(LOG_INFO, NULL, tpp_get_logbuf());
#endif /* localmod 149 */

					TPP_DBPRT(("received noroute, sending TPP_CMD_NET_CLOSE to %u", strm->sd));
					send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
				}
				if (data_out)
					free(data_out);
				return 0;
			}

			if (code == TPP_MSG_UPDATE) {
				tpp_log_func(LOG_INFO, NULL, "Received UPDATE from pbs_comm");
				if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_RESTORE, NULL) != 0) {
					tpp_log_func(LOG_CRIT, __func__, "Error writing to app mbox");
				}
				if (data_out)
					free(data_out);
				return 0;
			}

			if (code == TPP_MSG_AUTHERR) {
				char *msg = ((char *) data) + sizeof(tpp_ctl_pkt_hdr_t);
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tfd %d, Received authentication error from router %s, err=%d, msg=\"%s\"", tfd,
							tpp_netaddr(&hdr->src_addr), hdr->error_num, msg);
				tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());
				if (data_out)
					free(data_out);
				return -1; /* close connection */
			}
		}
		break; /* TPP_CTL_MSG */

		case TPP_CTL_LEAVE: {
			tpp_leave_pkt_hdr_t *hdr = (tpp_leave_pkt_hdr_t *) data;
			AVL_IX_REC *pkey;
			tpp_que_t send_close_queue;
			tpp_addr_t *addrs;
			int i;

			PRTPKTHDR(__func__, hdr, 0);

			/* bother only about leave */
			tpp_lock(&strmarray_lock);
			TPP_QUE_CLEAR(&send_close_queue);

			/* go past the header and point to the list of addresses following it */
			addrs = (tpp_addr_t *) (((char *) data) + sizeof(tpp_leave_pkt_hdr_t));
			for(i = 0; i < hdr->num_addrs; i++) {
				if ((pkey = avlkey_create(AVL_streams, &addrs[i]))) {

					/*
					 * An avl tree, that allows duplicates, keeps nodes with same
					 * keys right next to each other, so one find is enough to
					 * get to the vicinity. Doing avl_next_key continuously as long
					 * as the keys match, is good enough to find all matching nodes
					 *
					 */
					if (avl_find_key(pkey, AVL_streams) == AVL_IX_OK) {
						while (1) {
							strm = pkey->recptr;
							strm->lasterr = 0;

							/* under lock already, can access directly */
							if (strmarray[strm->sd].slot_state == TPP_SLOT_BUSY) {
								if (tpp_enque(&send_close_queue, strm) == NULL) {
									tpp_log_func(LOG_CRIT, __func__, "Out of memory enqueing to send close queue");
									tpp_unlock(&strmarray_lock);
									if (data_out)
										free(data_out);
									return -1;
								}
							}

							/* if this is the end of the tree, break out */
							if (avl_next_key(pkey, AVL_streams) != AVL_IX_OK)
								break;

							/* if the next key in the tree is not the same key, break */
							if (memcmp(&pkey->key, &addrs[i], sizeof(tpp_addr_t)) != 0)
								break;
						}
					}
					free(pkey);
				}
			}
			tpp_unlock(&strmarray_lock);

			while ((strm = (stream_t *) tpp_deque(&send_close_queue))) {
				TPP_DBPRT(("received TPP_CTL_LEAVE, sending TPP_CMD_NET_CLOSE sd=%u", strm->sd));
				send_app_strm_close(strm, TPP_CMD_NET_CLOSE, hdr->ecode);
			}

			if (data_out)
				free(data_out);

			return 0;
		}
		break;
		/* TPP_CTL_LEAVE */

		case TPP_DATA:
		case TPP_CLOSE_STRM: {
			tpp_data_pkt_hdr_t *p = (tpp_data_pkt_hdr_t *) data;
			unsigned int seq_no_recvd;
			unsigned int seq_no_expected;
			unsigned int seq_no_acked;
			unsigned char dup;
			unsigned int src_sd;
			unsigned int dest_sd;
			unsigned int src_magic;
			unsigned int sz = len - sizeof(tpp_data_pkt_hdr_t);

			src_sd = ntohl(p->src_sd);
			dest_sd = ntohl(p->dest_sd);
			src_magic = ntohl(p->src_magic);
			seq_no_recvd = ntohl(p->seq_no);
			seq_no_acked = ntohl(p->ack_seq);
			dup = p->dup;

			PRTPKTHDR(__func__, p, sz);

			if (dest_sd == UNINITIALIZED_INT && type != TPP_CLOSE_STRM && sz == 0) {
				tpp_log_func(LOG_ERR, NULL, "ack packet without dest_sd set!!!");
				if (data_out)
					free(data_out);
				return -1;
			}

			if (dest_sd == UNINITIALIZED_INT) {
				tpp_lock(&strmarray_lock);
				strm = find_stream_with_dest(&p->src_addr, src_sd, src_magic);
				tpp_unlock(&strmarray_lock);
				if (strm == NULL) {
					TPP_DBPRT(("No stream associated, Opening new stream"));
					/*
					 * packet's destination address = stream's source address at our end
					 * packet's source address = stream's destination address at our end
					 */
					if ((strm = alloc_stream(&p->dest_addr, &p->src_addr)) == NULL) {
						tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating stream");
						if (data_out)
							free(data_out);
						return -1;
					}
				} else {
					TPP_DBPRT(("Stream sd=%u, u_state=%d, t_state=%d", strm->sd, strm->u_state, strm->t_state));
				}
				dest_sd = strm->sd;
			} else {
				TPP_DBPRT(("Stream found from index in packet = %u", dest_sd));
			}

			/* In any case, check for the stream's validity */
			tpp_lock(&strmarray_lock);
			strm = check_strm_valid(dest_sd, &p->src_addr, src_sd);
			tpp_unlock(&strmarray_lock);
			if (strm == NULL) {
				if (type != TPP_CLOSE_STRM && sz == 0) {
					if (data_out)
						free(data_out);
					return 0; /* it is an ack packet, don't send noroute */
				}
				tpp_log_func(LOG_WARNING, __func__, tpp_get_logbuf());
				tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, &p->src_addr, &p->dest_addr, src_sd, 0, tpp_get_logbuf());
				if (data_out)
					free(data_out);
				return 0;
			}

			/*
			 * this should be set even from ack and close packets since
			 * we could have opened a stream locally, sent a packet
			 * and the ack carries the other sides sd, which we must store
			 * and use in the next send out.
			 */
			strm->dest_sd = src_sd; /* next time outgoing will have dest_fd */
			strm->dest_magic = src_magic; /* used for matching next time onwards */

			seq_no_expected = strm->seq_no_expected;
			TPP_DBPRT(("sequence_no expected = %u", seq_no_expected));

			sd = strm->sd;

			if (seq_no_acked != UNINITIALIZED_INT) {
				unshelve_pkt(strm, seq_no_acked);
				/*
				 * if app u_state == TPP_STRM_STATE_CLOSE means an CLOSE packet was sent out
				 * and the strm's send_seq_no was the last sequence sent out, and it will not be
				 * incremented any more. If CLOSE is acked, then queue the stream for deletion
				 */
				if (strm->u_state == TPP_STRM_STATE_CLOSE && seq_no_acked == strm->send_seq_no) {
					TPP_DBPRT(("sd=%u PEER acked CLOSE, sending CLOSE to APP", strm->sd));
					send_pkt_to_app(strm, TPP_CLOSE_STRM, NULL, 0);
				}
			}

			if (type != TPP_CLOSE_STRM && sz == 0) {
				if (data_out)
					free(data_out);
				return 0; /* it is an ack packet, everything is done by now */
			}

			/* always ack data packets, even if duplicate */
			queue_ack(strm, type, seq_no_recvd);

			if (seq_no_recvd == seq_no_expected) {
				tpp_que_elem_t *n;
				int oo_cleared = 1;

				TPP_DBPRT(("Sending in sequence to app, sd=%u, seq=%u", sd, seq_no_expected));
				send_pkt_to_app(strm, type, data, sz);
				seq_no_expected = get_next_seq(seq_no_expected);

				/*
				 * also go through the hanged off list of out of order packets and
				 * send all those to app that now fall in sequence.
				 */
				n = NULL;
				while ((n = TPP_QUE_NEXT(&strm->oo_queue, n))) {
					tpp_packet_t *oo_pkt = (tpp_packet_t *) TPP_QUE_DATA(n);
					if (oo_pkt) {
						tpp_data_pkt_hdr_t *dhdr = (tpp_data_pkt_hdr_t *) oo_pkt->data;
						if (ntohl(dhdr->seq_no) == seq_no_expected) {

							n = tpp_que_del_elem(&strm->oo_queue, n);

							snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Sending OO packets to app, sd=%u, seq=%u", sd, seq_no_expected);
							tpp_log_func(LOG_INFO, NULL, tpp_get_logbuf());

							send_pkt_to_app(strm, dhdr->type, oo_pkt->data, oo_pkt->len - sizeof(tpp_data_pkt_hdr_t));
							seq_no_expected = get_next_seq(seq_no_expected);

							tpp_free_pkt(oo_pkt);
						} else {
							oo_cleared = 0;
							break;
						}
					}
				}

				/* if no out of order packets remained, clear this stream from the queue of OO strms */
				if (oo_cleared == 1) {
					if (strm->timeout_node) {
						tpp_lock(&strmarray_lock);
						tpp_que_del_elem(&strm_action_queue, strm->timeout_node);
						strm->timeout_node = NULL;
						tpp_unlock(&strmarray_lock);
					}
				}

				strm->seq_no_expected = seq_no_expected;
				if (data_out)
					free(data_out);
				return 0;
			} else {
				tpp_que_elem_t *n;
				tpp_packet_t *full_pkt;
				int seq_no_diff;

				/*
				* Check the sequence number in the packet, if duplicate drop it,
				* if out of order store it, if fine, let know app
				*/
				seq_no_diff = abs(seq_no_expected - seq_no_recvd);
				if ((seq_no_recvd < seq_no_expected && seq_no_diff < MAX_SEQ_NUMBER / 4)
					|| (seq_no_recvd > seq_no_expected && seq_no_diff > MAX_SEQ_NUMBER / 4)) {
					/* duplicate packet, drop it, ack was already sent */
					if (dup > 0) {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
							"Received duplicate packet with seq_no = %d", seq_no_recvd);
						tpp_log_func(LOG_DEBUG, NULL, tpp_get_logbuf());
					} else {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
							"Duplicate packet? with seq_no = %d without dup flag set", seq_no_recvd);
						tpp_log_func(LOG_DEBUG, NULL, tpp_get_logbuf());
					}
					duppkt_cnt++;
					if (data_out)
						free(data_out);
					return 0;
				}

				if (strm->timeout_node == NULL) {
					enque_timeout_strm(strm);
				}

				/*
				 * 1. Hang it off a out of order list on the stream
				 * 2. The sender would realize this and retransmit this.
				 */
				oopkt_cnt++;
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "OO pkt sd=%u seq=%u exp=%u u_state=%d t_state=%d dest=%s src_sd=%u, dest_sd=%u",
					strm->sd, seq_no_recvd, seq_no_expected, strm->u_state, strm->t_state, tpp_netaddr(&strm->dest_addr), src_sd,
					dest_sd);
				tpp_log_func(LOG_WARNING, NULL, tpp_get_logbuf());

				full_pkt = tpp_cr_pkt(data, len, 1);
				if (full_pkt == NULL) {
					if (data_out)
						free(data_out);
					return -1;
				}

				n = NULL;
				while ((n = TPP_QUE_NEXT(&strm->oo_queue, n))) {
					tpp_packet_t *oo_pkt = TPP_QUE_DATA(n);
					if (oo_pkt) {
						tpp_data_pkt_hdr_t *shdr = (tpp_data_pkt_hdr_t *) oo_pkt->data;
						unsigned int seq_no = (unsigned int) ntohl(shdr->seq_no);
						if (seq_no == seq_no_recvd) {
							/* duplicate packet */
							snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Recvd duplicate packet seq_no=%u, dup=%d", seq_no_recvd, shdr->dup);
							tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());

							tpp_free_pkt(full_pkt);
							if (data_out)
								free(data_out);
							return 0;
						} else if (seq_no > seq_no_recvd) {

							/* insert it here and return */
							n = tpp_que_ins_elem(&strm->oo_queue, n, full_pkt, 1);
							snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Inserted OO packet with seq_no = %u for sd=%u", seq_no_recvd,
								strm->sd);
							tpp_log_func(LOG_INFO, NULL, tpp_get_logbuf());
							if (data_out)
								free(data_out);
							return 0;
						}
					}
				}
				/* if it came here then packet was not inserted, so insert at end */
				if (tpp_enque(&strm->oo_queue, full_pkt) == NULL) {
					snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Failed to enque OO packet for sd = %u, Out of memory", strm->sd);
					tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());
					if (data_out)
						free(data_out);
					return -1;
				}
				if (data_out)
					free(data_out);
				return 0;
			}
			if (data_out)
				free(data_out);
			return 0;
		}
		break; /* TPP_DATA, TPP_CLOSE_STRM */

		default:
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Bad header for incoming packet on fd %d, header = %d", tfd, type);
			tpp_log_func(LOG_ERR, NULL, tpp_get_logbuf());

	} /* switch */

	if (data_out)
		free(data_out);
	return -1;
}

/**
 * @brief
 *	The connection drop (close) handler registered with the IO thread.
 *
 * @par Functionality
 *	When the connection between this leaf and a router is dropped, the IO
 *	thread first calls this (prior registered) function to notify the leaf
 *	layer of the fact that a connection was dropped. If not other routes
 *	are up (no other routers) or all other router connections down, then
 *	all streams that are currently open on this leaf are sent a close
 *	message. (The APP eventually reads the close message and calls tpp_close
 *	on those streams)
 *
 * @param[in] tfd - The actual IO connection on which data was about to be
 *			sent (unused)
 * @param[in] c - context associated with the IO thread (unused here)
 * @param[in] extra - The extra data associated with IO connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
leaf_close_handler(int tfd, int error, void *c, void *extra)
{
	int rc;
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_router_t *r;
	int last_state;

	if (extra) {
		conn_auth_t *authdata = (conn_auth_t *)extra;
		if (authdata->authctx && authdata->authdef)
			authdata->authdef->destroy_ctx(authdata->authctx);
		if (authdata->authdef != authdata->encryptctx && authdata->encryptctx && authdata->encryptdef)
			authdata->encryptdef->destroy_ctx(authdata->encryptctx);
		if (authdata->cleartext)
			free(authdata->cleartext);
		/* DO NOT free authdef here, it will be done in unload_auths() */
		free(authdata);
		tpp_transport_set_conn_extra(tfd, NULL);
	}

	if (tpp_going_down == 1)
		return -1; /* while we are doing shutdown don't try to reconnect etc */

	r = (tpp_router_t *) ctx->ptr;

	/* deallocate the connection structure associated with ctx */
	tpp_transport_close(r->conn_fd);

	/*
	 * Disassociate the older context, so we can attach
	 * to new connection old connection will be deleted
	 * shortly by caller
	 */
	free(ctx);
	tpp_transport_set_conn_ctx(tfd, NULL);
	last_state = r->state;
	r->state = TPP_ROUTER_STATE_DISCONNECTED;
	r->conn_fd = -1;

	if (last_state == TPP_ROUTER_STATE_CONNECTED) {
		/* log disconnection message */
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Connection to pbs_comm %s down", r->router_name);
		tpp_log_func(LOG_CRIT, NULL, tpp_get_logbuf());

		if (app_thread_active_router >= 0 && routers[app_thread_active_router] == r) {
			/* the current global index went down, set the index to -1 so its deduced again */
			app_thread_active_router = -1;
		}

		active_router = get_active_router(active_router);
		if (active_router == -1) {
			unsigned int i;

			/*
			 * No routers available, let app know of this
			 */
			if (!the_app_net_down_handler) {
				/* send individual net close messages to app */
				tpp_lock(&strmarray_lock);
				for (i = 0; i < max_strms; i++) {
					if (strmarray[i].slot_state == TPP_SLOT_BUSY) {
						strmarray[i].strm->t_state = TPP_TRNS_STATE_NET_CLOSED;
						TPP_DBPRT(("net down, sending TPP_CMD_NET_CLOSE sd=%u", strmarray[i].strm->sd));
						send_app_strm_close(strmarray[i].strm, TPP_CMD_NET_CLOSE, 0);
					}
				}
				tpp_unlock(&strmarray_lock);
			} else {
				tpp_lock(&strmarray_lock);
				for (i = 0; i < max_strms; i++) {
					if (strmarray[i].slot_state == TPP_SLOT_BUSY) {
						strmarray[i].strm->t_state = TPP_TRNS_STATE_NET_CLOSED;
						TPP_DBPRT(("net down, sending TPP_CMD_NET_CLOSE sd=%u", strmarray[i].strm->sd));
						send_app_strm_close(strmarray[i].strm, TPP_CMD_NET_CLOSE, 0);
					}
				}
				tpp_unlock(&strmarray_lock);
				if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_DOWN, NULL) != 0) {
					tpp_log_func(LOG_CRIT, __func__, "Error writing to app mbox");
					return -1;
				}
			}
		}
	}

	if (r->delay == 0)
		r->delay = TPP_CONNNECT_RETRY_MIN;
	else
		r->delay += TPP_CONNECT_RETRY_INC;

	if (r->delay > TPP_CONNECT_RETRY_MAX)
		r->delay = TPP_CONNECT_RETRY_MAX;

	/* since our connection with our router is down, we need to try again */
	/* connect to router and send initial join packet */
	if ((rc = connect_router(r)) != 0)
		return -1;

	if (active_router != -1) {
		check_retries(-1);
		check_pending_acks(-1);
	}
	return 0;
}

/**
 * @brief
 * 	Utility function to clear the retry related information from the packet
 *
 * @param[in] pkt  - pointer to the packet structure
 * @param[in] strm - if a stream is associated, then pointer to it, so that pkt
 *                   can be removed from the stream level retry queue
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
tpp_clr_retry(tpp_packet_t *pkt, stream_t *strm)
{
	if (pkt->extra_data) {
		retry_info_t *rt = pkt->extra_data;
		if (rt->global_retry_node) {
			tpp_que_del_elem(&global_retry_queue, rt->global_retry_node);
			rt->global_retry_node = NULL;
		}

		if (rt->strm_retry_node) {
			if (strm)
				tpp_que_del_elem(&strm->retry_queue, rt->strm_retry_node);

			rt->strm_retry_node = NULL;
		}
	}
}
