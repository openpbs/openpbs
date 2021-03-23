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
 *		tpp_ interface functions that the daemons use to communicate
 *		with other daemons.
 *
 *		The code is driven by 2 threads. The Application thread (from
 *		the daemons) calls the main interfaces (tpp_ functions).
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
#include <stdint.h>


#include "pbs_idx.h"
#include "libpbs.h"
#include "tpp_internal.h"
#include "dis.h"
#include "auth.h"

/*
 *	Global Variables
 */

/**
 *	file descriptor returned by tpp_init()
 */
int		tpp_fd = -1;

 /* whether a forked child called tpp_terminate or not? initialized to false */
int tpp_terminated_in_child = 0;

/*
 * app_mbox is the "monitoring mechanism" for the application
 * send notifications to the application about incoming data
 * or events. THIS IS EDGE TRIGGERED. Once triggered, app must
 * read all the data available, or else, it could end up with
 * a situation where data exists to be read, but there is no
 * notification to wake up waiting app thread from select/poll.
 */
tpp_mbox_t app_mbox;

/* counters for various statistics */
int oopkt_cnt = 0;  /* number of out of order packets received */
int duppkt_cnt = 0; /* number of duplicate packets received */

static struct tpp_config *tpp_conf; /* the global TPP configuration file */

static tpp_addr_t *leaf_addrs = NULL;
static int leaf_addr_count = 0;

/*
 * The structure to hold information about the multicast channel
 */
typedef struct {
	int num_fds;   /* number of streams that are part of mcast channel */
	int num_slots; /* number of slots in the channel (for resizing) */
	int *strms;    /* array of member stream descriptors */
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

	unsigned short u_state;   /* stream state, APP thread updates, IO thread read-only */
	unsigned short t_state;
	short lasterr;            /* updated by IO thread only, for future use */

	tpp_addr_t src_addr;  /* address of the source host */
	tpp_addr_t dest_addr; /* address of destination host - set by APP thread, read-only by IO thread */

	void *user_data;            /* user data set by tpp_dis functions. Basically used for DIS encoding */

	tpp_que_t recv_queue; /* received packets - APP thread only, hence no lock */

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
pthread_rwlock_t strmarray_lock;      /* global lock for the streams array and streams_idx (not for an individual stream) */
unsigned int max_strms = 0;           /* total number of streams allocated */

/* the following two variables are used to quickly find out a unused slot */
unsigned int high_sd = UNINITIALIZED_INT; /* the highest stream sd used */
tpp_que_t freed_sd_queue;            /* last freed stream sd */
int freed_queue_count = 0;

/* index of streams - so that we can search faster inside it */
void *streams_idx = NULL;

/* following common structure is used to do a timed action on a stream */
typedef struct {
	unsigned int sd;
	time_t strm_action_time;
	void (*strm_action_func)(unsigned int);
} strm_action_info_t;

/* global queue of stream slots to be marked FREE after TPP_CLOSE_WAIT time */
tpp_que_t strm_action_queue;
pthread_mutex_t strm_action_queue_lock;

/* leaf specific stream states */
#define TPP_STRM_STATE_OPEN             1   /* stream is open */
#define TPP_STRM_STATE_CLOSE            2   /* stream is closed */

#define TPP_TRNS_STATE_OPEN             1   /* stream open */
#define TPP_TRNS_STATE_PEER_CLOSED      2   /* stream closed by peer */
#define TPP_TRNS_STATE_NET_CLOSED       3   /* network closed (noroute etc) */

#define TPP_MCAST_SLOT_INC              100 /* inc members in mcast group */

/* the physical connection to the router from this leaf */
static tpp_router_t **routers = NULL;
static int max_routers = 0;

/* forward declarations of functions used by this code file */

/* function pointers */
void (*the_app_net_down_handler)(void *data) = NULL;
void (*the_app_net_restore_handler)(void *data) = NULL;
time_t leaf_next_event_expiry(time_t now); /* IO thread only */

/* static functions */
static int connect_router(tpp_router_t *r);
static tpp_router_t *get_active_router();
static stream_t *get_strm_atomic(unsigned int sd);
static stream_t *get_strm(unsigned int sd);
static stream_t *alloc_stream(tpp_addr_t *src_addr, tpp_addr_t *dest_addr);
static void free_stream(unsigned int sd);
static void free_stream_resources(stream_t *strm);
static void queue_strm_close(stream_t *); /* call only by APP thread, however inserts into strm_action_queue */
static void queue_strm_free(unsigned int sd); /* invoked by IO thread only, via acting on the strm_action_queue */
static void act_strm(time_t now, int force);
static int send_app_strm_close(stream_t *strm, int cmd, int error);
static int send_pkt_to_app(stream_t *strm, unsigned char type, void *data, int sz, int totlen);
static stream_t *find_stream_with_dest(tpp_addr_t *dest_addr, unsigned int dest_sd, unsigned int dest_magic);
static int send_spl_packet(stream_t *strm, int type);
static int leaf_send_ctl_join(int tfd, void *c);
static int send_to_router(tpp_packet_t *pkt);

/* forward declarations */
static int leaf_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *ctx, void *extra);
static int leaf_pkt_handler(int tfd, void *data, int len, void *ctx, void *extra);
static int leaf_pkt_handler_inner(int tfd, void *buf, void **data_out, int len, void *c, void *extra);
static int leaf_close_handler(int tfd, int error, void *ctx, void *extra);
static int leaf_timer_handler(time_t now);
static int leaf_post_connect_handler(int tfd, void *data, void *ctx, void *extra);

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

	if (tpp_terminated_in_child == 1)
		return NULL;

	tpp_read_lock(&strmarray_lock); /* walking the array, so read lock */
	if (sd < max_strms) {
		if (strmarray[sd].slot_state == TPP_SLOT_BUSY)
			strm = strmarray[sd].strm;
	}
	tpp_unlock_rwlock(&strmarray_lock);

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
 *	For example, in the case of pbs_server, such a handler is "net_down_handler".
 *
 * @see
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
leaf_send_ctl_join(int tfd, void *c)
{
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_router_t *r;
	tpp_join_pkt_hdr_t *hdr = NULL;
	tpp_packet_t *pkt = NULL;
	int len;
	int i;

	if (!ctx)
		return 0;

	if (ctx->type == TPP_ROUTER_NODE) {
		r = (tpp_router_t *) ctx->ptr;
		r->state = TPP_ROUTER_STATE_CONNECTING;

		/* send a TPP_CTL_JOIN message */
		pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_join_pkt_hdr_t), 1, (void **) &hdr);
		if (!pkt) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			return -1;
		}

		hdr->type = TPP_CTL_JOIN;
		hdr->node_type = tpp_conf->node_type;
		hdr->hop = 1;
		hdr->index = r->index;
		hdr->num_addrs = leaf_addr_count;

		/* log my own leaf name to help in troubleshooting later */
		for (i = 0; i < leaf_addr_count; i++) {
			tpp_log(LOG_CRIT, NULL, "Registering address %s to pbs_comm %s", tpp_netaddr(&leaf_addrs[i]), r->router_name);
		}

		len = leaf_addr_count * sizeof(tpp_addr_t);
		if (!tpp_bld_pkt(pkt, leaf_addrs, len, 1, NULL)) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			return -1;
		}

		if (tpp_transport_vsend(r->conn_fd, pkt) != 0) { /* this has to go irrespective of router state being down */
			tpp_log(LOG_CRIT, __func__, "tpp_transport_vsend failed, err=%d", errno);
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
static int
leaf_post_connect_handler(int tfd, void *data, void *c, void *extra)
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
	return leaf_send_ctl_join(tfd, c);
}

/**
 * @brief
 *	The function initiates a connection from the leaf to a router
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
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating tpp context");
		return -1;
	}
	ctx->ptr = r;
	ctx->type = TPP_ROUTER_NODE;

	/* initiate connections to the tpp router (single for now) */
	if (tpp_transport_connect(r->router_name, r->delay, ctx, &(r->conn_fd)) == -1) {
		tpp_log(LOG_ERR, NULL, "Connection to pbs_comm %s failed", r->router_name);
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
 *	using the IO thread into the leaf logic code
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
	int rc, i;
	int app_fd;

	tpp_conf = cnf;
	if (tpp_conf->node_name == NULL) {
		tpp_log(LOG_CRIT, NULL,  "TPP leaf node name is NULL");
		return -1;
	}

	/* before doing anything else, initialize the key to the tls */
	if (tpp_init_tls_key() != 0) {
		/* can only use prints since tpp key init failed */
		fprintf(stderr, "Failed to initialize tls key\n");
		return -1;
	}

	tpp_log(LOG_CRIT, NULL, "TPP leaf node names = %s", tpp_conf->node_name);

	tpp_init_rwlock(&strmarray_lock);
	tpp_init_lock(&strm_action_queue_lock);

	if (tpp_mbox_init(&app_mbox, "app_mbox", TPP_MAX_MBOX_SIZE) != 0) {
		tpp_log(LOG_CRIT, __func__, "Failed to create application mbox");
		return -1;
	}

	/* initialize the app_mbox */
	app_fd = tpp_mbox_getfd(&app_mbox);

	TPP_QUE_CLEAR(&strm_action_queue);
	TPP_QUE_CLEAR(&freed_sd_queue);

	streams_idx = pbs_idx_create(PBS_IDX_DUPS_OK, sizeof(tpp_addr_t));
	if (streams_idx == NULL) {
		tpp_log(LOG_CRIT, __func__, "Failed to create index for leaves");
		return -1;
	}

	/* get the addresses associated with this leaf */
	leaf_addrs = tpp_get_addresses(tpp_conf->node_name, &leaf_addr_count);
	if (!leaf_addrs) {
		tpp_log(LOG_CRIT, __func__, "Failed to resolve address, err=%d", errno);
		return -1;
	}

	/*
	 * first register handlers with the transport, so these functions are called
	 * from the IO thread from the transport layer
	 */
	tpp_transport_set_handlers(
		leaf_pkt_presend_handler, /* called before sending packet */
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

	if (max_routers == 0) {
		tpp_log(LOG_CRIT, NULL, "No pbs_comms configured, cannot start");
		return -1;
	}

	if ((routers = calloc(max_routers, sizeof(tpp_router_t *))) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating pbs_comms array");
		return -1;
	}
	routers[max_routers - 1] = NULL;

	/* initialize the router structures and initiate connections to them */
	for (i = 0; tpp_conf->routers[i]; i++) {
		if ((routers[i] = malloc(sizeof(tpp_router_t))) == NULL)  {
			tpp_log(LOG_CRIT, __func__, "Out of memory allocating pbs_comm structure");
			return -1;
		}

		routers[i]->router_name = tpp_conf->routers[i];
		routers[i]->conn_fd = -1;
		routers[i]->initiator = 1;
		routers[i]->state = TPP_ROUTER_STATE_DISCONNECTED;
		routers[i]->index = i;
		routers[i]->delay = 0;

		tpp_log(LOG_INFO, NULL, "Connecting to pbs_comm %s", routers[i]->router_name);

		/* connect to router and send initial join packet */
		if ((rc = connect_router(routers[i])) != 0)
			return -1;
	}

#ifndef WIN32

	/*
	 * As such atfork handlers are required since after a fork, fork() replicates
	 * only calling thread that called fork() and TPP layer never calls fork. So, this
	 * means that the TPP thread is always dead/unavailable in a child process.
	 *
	 * We register only a post_fork child handler to set "tpp_terminated_in_child" flag
	 * which renders TPP functions to return right away without doing anything,
	 * rendering TPP functionality "bypassed" in the child process.
	 *
	 */

	/* for unix, set a pthread_atfork handler */
	if (pthread_atfork(NULL, NULL, tpp_terminate)) {
		tpp_log(LOG_CRIT, __func__, "TPP client atfork handler registration failed");
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

	TPP_DBPRT("sd=%d", fd);
	strm = get_strm(fd);
	if (!strm) {
		TPP_DBPRT("Bad sd %d", fd);
		return -1;
	}
	p = tpp_deque(&strm->recv_queue); /* only APP thread accesses this queue, hence no lock */
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
	void *pdest_addr = &dest_addr;
	void *idx_ctx = NULL;

	if ((dest = mk_hostname(dest_host, port)) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory opening stream");
		return -1;
	}

	addrs = tpp_get_addresses(dest, &count);
	if (!addrs) {
		tpp_log(LOG_CRIT, __func__, "Failed to resolve address, err=%d", errno);
		free(dest);
		return -1;
	}
	memcpy(&dest_addr, addrs, sizeof(tpp_addr_t));
	free(addrs);

	tpp_read_lock(&strmarray_lock); /* walking the idx, so read lock */

	/*
	 * Just try to find a fully open stream to use, else fall through
	 * to create a new stream. Any half closed streams will be closed
	 * elsewhere, either when network first dropped or if any message
	 * comes to such a half open stream
	 */
	while (pbs_idx_find(streams_idx, &pdest_addr, (void **)&strm, &idx_ctx) == PBS_IDX_RET_OK) {
		if (memcmp(pdest_addr, &dest_addr, sizeof(tpp_addr_t)) != 0)
			break;
		if (strm->u_state == TPP_STRM_STATE_OPEN && strm->t_state == TPP_TRNS_STATE_OPEN && strm->used_locally == 1) {
			tpp_unlock_rwlock(&strmarray_lock);
			pbs_idx_free_ctx(idx_ctx);

			TPP_DBPRT("Stream for dest[%s] returned = %u", dest, strm->sd);
			free(dest);
			return strm->sd;
		}
	}
	pbs_idx_free_ctx(idx_ctx);

	tpp_unlock_rwlock(&strmarray_lock);

	/* by default use the first address of the host as the source address */
	if ((strm = alloc_stream(&leaf_addrs[0], &dest_addr)) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating stream");
		free(dest);
		return -1;
	}

	/* set the used_locally flag, since the APP is aware of this fd */
	strm->used_locally = 1;

	TPP_DBPRT("Stream for dest[%s] returned = %d", dest, strm->sd);
	free(dest);

	return strm->sd;
}


/**
 * @brief
 *	Returns the active router which has an established TCP connection
 *
 * @par Functionality:
 *	Loops through the list of routers and returns the first one having
 *	an active TCP connection. Favors the currently active router
 *
 * @return - The active router
 * @retval NULL   - Function failed
 * @retval !NULL - Success, the active router is returned
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static tpp_router_t *
get_active_router()
{
	int i;
	static int index = 0;

	if (routers == NULL)
		return NULL;

	/*
	 * If we had already been using an alternate router it should be good to use
	 * without checking connection age, since we were already using it
	 */
	if (index >= 0 && index < max_routers && routers[index] && routers[index]->state == TPP_ROUTER_STATE_CONNECTED)
		return routers[index];

	for (i = 0; i < max_routers; i++) {
		if (routers[i]->state == TPP_ROUTER_STATE_CONNECTED) {
			index = i;
			return routers[index];
		}
	}

	return NULL;
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
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   >=0 - Success - amount of data sent
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
	stream_t *strm;
	int rc = -1;
	unsigned int to_send;
	void *data_dup;
	tpp_data_pkt_hdr_t *dhdr = NULL;
	tpp_packet_t *pkt;

	strm = get_strm(sd);
	if (!strm) {
		TPP_DBPRT("Bad sd %d", sd);
		return -1;
	}

	if ((tpp_conf->compress == 1) && (len > TPP_COMPR_SIZE)) {
		data_dup = tpp_deflate(data, len, &to_send); /* creates a copy */
		if (data_dup == NULL) {
			tpp_log(LOG_CRIT, __func__, "tpp deflate failed");
			return -1;
		}
	} else {
		data_dup = malloc(len);
		if (!data_dup) {
			tpp_log(errno, __func__, "Failed to duplicate data");
			return -1;
		}
		memcpy(data_dup, data, len);
		to_send = len;
	}
	/* we have created a copy of the data either way, compressed, or not */

	tpp_log(LOG_DEBUG, __func__, "**** sd=%d, compr_len=%d, len=%d, dest_sd=%u", sd, to_send, len, strm->dest_sd);

	if (strm->strm_type == TPP_STRM_MCAST) {
		/* do other stuff */
		return tpp_mcast_send(sd, data_dup, to_send, len);
	}

	/* create a new pkt and add the dhdr chunk first */
	pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_data_pkt_hdr_t), 1, (void **) &dhdr);
	if (!pkt) {
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		free(data_dup);
		return -1;
	}
	dhdr->type = TPP_DATA;
	dhdr->src_sd = htonl(sd);
	dhdr->src_magic = htonl(strm->src_magic);
	dhdr->dest_sd = htonl(strm->dest_sd);
	dhdr->totlen = htonl(len);
	memcpy(&dhdr->src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&dhdr->dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	/* add the data chunk to the already created pkt */
	if (!tpp_bld_pkt(pkt, data_dup, to_send, 0, NULL)) { /* data is already a duplicate buffer */
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		return -1;
	}

	rc = send_to_router(pkt);
	if (rc == 0)
		return len;  /* all given data sent, so return len */

	if (rc == -2)
		tpp_log(LOG_CRIT, __func__, "mbox full, returning error to App!");
	else if (rc == -1)
		tpp_log(LOG_ERR, __func__, "Failed to send to router");

	send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
	return rc;
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
 *	packet. To move to the next packet, the APP must call "tpp_eom".
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
	tpp_chunk_t *chunk = NULL;
	stream_t *strm;
	int offset, avail_bytes, trnsfr_bytes;

	errno = 0;
	if (len == 0)
		return 0;

	strm = get_strm(sd);
	if (!strm) {
		TPP_DBPRT("Bad sd %d", sd);
		return -1;
	}

	strm->used_locally = 1;

	if ((n = TPP_QUE_HEAD(&strm->recv_queue))) /* only APP thread accesses this queue, hence no lock */
		cur_pkt = TPP_QUE_DATA(n);

	/* read from head */
	if (cur_pkt == NULL) {
		errno = EWOULDBLOCK;
		return -1; /* no data currently - would block */
	}

	chunk = GET_NEXT(cur_pkt->chunks);
	if (chunk == NULL) {
		errno = EWOULDBLOCK;
		return -1; /* no data currently - would block */
	}

	offset = chunk->pos - chunk->data;
	avail_bytes = chunk->len - offset;
	trnsfr_bytes = (len < avail_bytes) ? len : avail_bytes;

	if (trnsfr_bytes == 0) {
		errno = EWOULDBLOCK;
		return -1; /* no data currently - would block */
	}

	memcpy(data, chunk->pos, trnsfr_bytes);
	chunk->pos = chunk->pos + trnsfr_bytes;

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

	tpp_write_lock(&strmarray_lock); /* updating the array + adding to idx, so WRITE lock */

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

		TPP_DBPRT("***Searching for a free slot");
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
		tpp_unlock_rwlock(&strmarray_lock);
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating stream");
		return NULL;
	}
	strm->strm_type = TPP_STRM_NORMAL;
	strm->sd = sd;
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

	TPP_QUE_CLEAR(&strm->recv_queue); /* only APP thread accesses this queue, once created here, hence no lock */

	/* set to stream array */
	if (max_strms == 0 || sd > max_strms - 1) {
		unsigned int newsize;
		void *p;

		/* resize strmarray */
		newsize = sd + 100;
		p = realloc(strmarray, sizeof(stream_slot_t) * newsize);
		if (!p) {
			free(strm);
			tpp_unlock_rwlock(&strmarray_lock);
			tpp_log(LOG_CRIT, __func__, "Out of memory resizing stream array");
			return NULL;
		}
		strmarray = (stream_slot_t *) p;
		memset(&strmarray[max_strms], 0, (newsize - max_strms) * sizeof(stream_slot_t));
		max_strms = newsize;
	}

	strmarray[sd].slot_state = TPP_SLOT_BUSY;
	strmarray[sd].strm = strm;

	if (dest_addr) {
		/* also add stream to the streams_idx with the dest as key */
		if (pbs_idx_insert(streams_idx, &strm->dest_addr, strm) != PBS_IDX_RET_OK) {
			tpp_log(LOG_CRIT, __func__, "Failed to add strm with sd=%u to streams", strm->sd);
			free(strm);
			tpp_unlock_rwlock(&strmarray_lock);
			return NULL;
		}
	}

	TPP_DBPRT("*** Allocated new stream, sd=%u, src_magic=%u", strm->sd, strm->src_magic);

	tpp_unlock_rwlock(&strmarray_lock);

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

	TPP_DBPRT("from pid = %d", getpid());

	tpp_mbox_destroy(&app_mbox);

	tpp_going_down = 1;

	tpp_transport_shutdown();
	/* all threads are dead by now, so no locks required */

	DIS_tpp_funcs();

	for (i = 0; i < max_strms; i++) {
		if (strmarray[i].slot_state == TPP_SLOT_BUSY) {
			sd = strmarray[i].strm->sd;
			dis_destroy_chan(sd);
			free_stream_resources(strmarray[i].strm);
			free_stream(sd);
		}
	}

	if (strmarray)
		free(strmarray);
	tpp_destroy_rwlock(&strmarray_lock);

	free_tpp_config(tpp_conf);
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
	 * not used after a fork.
	 * Also never log anything from (or after) a terminate handler.
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
	if (tpp_terminated_in_child == 1)
		return;

	/* set flag so this function is never entered within
	 * this process again, so no fear of double frees
	 */
	tpp_terminated_in_child = 1;

	tpp_transport_terminate();

	tpp_mbox_destroy(&app_mbox);
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
				TPP_DBPRT("sd=%u, cmd=%d, u_state=%d, t_state=%d, len=%d, dest_sd=%u", sd, cmd, strm->u_state, strm->t_state, pkt->totlen, strm->dest_sd);

				if (strm->u_state == TPP_STRM_STATE_OPEN) {
					/* add packet to recv queue */
					if (tpp_enque(&strm->recv_queue, pkt) == NULL) { /* only APP thread accesses this queue, hence not lock */
						tpp_log(LOG_CRIT, __func__, "Failed to queue received pkt");
						tpp_free_pkt(pkt);
						return -1;
					}
					sds[strms_found++] = sd;
				} else {
					TPP_DBPRT("Data recvd on closed stream %u discarded", sd);
					tpp_free_pkt(pkt);
					/* respond back by sending the close packet once more */
					send_spl_packet(strm, TPP_CLOSE_STRM);
				}
			} else {
				TPP_DBPRT("Data recvd on deleted stream %u discarded", sd);
				tpp_free_pkt(pkt);
			}
		} else if (cmd == TPP_CMD_PEER_CLOSE || cmd == TPP_CMD_NET_CLOSE) {

			if ((strm = get_strm_atomic(sd))) {
				TPP_DBPRT("sd=%u, cmd=%d, u_state=%d, t_state=%d, data=%p", sd, cmd, strm->u_state, strm->t_state, data);

				if (strm->u_state == TPP_STRM_STATE_OPEN) {
					if (cmd == TPP_CMD_PEER_CLOSE) {
						/* ask app to close stream */
						TPP_DBPRT("Sent peer close to stream sd=%u", sd);
						sds[strms_found++] = sd;

					} else if (cmd == TPP_CMD_NET_CLOSE) {
						/* network closed, so clear all pending data to be
						 * received, and signal that sd
						 */
						TPP_DBPRT("Sent net close stream sd=%u", sd);
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
		tpp_log(LOG_WARNING, __func__, "Slot %d freed!", sd);
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

	strm->close_func = func;
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

	TPP_DBPRT("Closing sd=%d", sd);
	/* free the recv_queue also */
	while ((p = tpp_deque(&strm->recv_queue))) /* only APP thread accesses this queue, hence no lock */
		tpp_free_pkt(p);

	/* send a close packet */
	strm->u_state = TPP_STRM_STATE_CLOSE;

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

	TPP_DBPRT("tpp_mcast_open called with fd=%u", strm->sd);

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
 * @param[in] unique - add only unique streams. Use only if caller might call
 * 			this function with duplicate tfd.
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
tpp_mcast_add_strm(int mtfd, int tfd, bool unique)
{
	void *p;
	stream_t *mstrm;
	stream_t *strm;
	int i = 0;

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
			tpp_log(LOG_CRIT, __func__, "Out of memory allocating mcast data");
			return -1;
		}

		mstrm->mcast_data->strms = malloc(TPP_MCAST_SLOT_INC * sizeof(int));
		if (!mstrm->mcast_data->strms) {
			free(mstrm->mcast_data);
			tpp_log(LOG_CRIT, __func__, "Out of memory allocating strm array of %lu bytes",
				(unsigned long)(TPP_MCAST_SLOT_INC * sizeof(int)));
			return -1;
		}
		mstrm->mcast_data->num_slots = TPP_MCAST_SLOT_INC;
		mstrm->mcast_data->num_fds = 0;
	} else if (mstrm->mcast_data->num_fds >= mstrm->mcast_data->num_slots) {
		p = realloc(mstrm->mcast_data->strms, (mstrm->mcast_data->num_slots + TPP_MCAST_SLOT_INC) * sizeof(int));
		if (!p) {
			tpp_log(LOG_CRIT, __func__, "Out of memory resizing strm array to %lu bytes", (mstrm->mcast_data->num_slots + TPP_MCAST_SLOT_INC) * sizeof(int));
			return -1;
		}
		mstrm->mcast_data->strms = p;
		mstrm->mcast_data->num_slots += TPP_MCAST_SLOT_INC;
	}

	if (unique) {
		for (i = 0; i < mstrm->mcast_data->num_fds; i++) {
			if (mstrm->mcast_data->strms[i] == tfd)
				return 0;
		}
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
 * @param[in] to_send  - Length of the data to send
 * @param[in] len - In case of large packets data is sent in chunks,
 *                       len is the total length of the data
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval  -2 - transport buffers full
 * @retval   >=0 - Success - amount of data sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_mcast_send(int mtfd, void *data, unsigned int to_send, unsigned int len)
{
	stream_t *mstrm = NULL;
	stream_t *strm = NULL;
	int i;
	int rc = -1;
	tpp_mcast_pkt_hdr_t *mhdr = NULL;
	tpp_mcast_pkt_info_t *minfo = NULL;
	tpp_mcast_pkt_info_t tmp_minfo;
	tpp_packet_t *pkt = NULL;
	unsigned int cmpr_len = 0;
	void *minfo_buf = NULL;
	int minfo_len;
	int ret;
	int finish;
	int num_fds;
	void *def_ctx = NULL;

	mstrm = get_strm_atomic(mtfd);
	if (!mstrm || !mstrm->mcast_data) {
		errno = ENOTCONN;
		return -1;
	}

	num_fds = mstrm->mcast_data->num_fds;

	minfo_len = sizeof(tpp_mcast_pkt_info_t) * num_fds;

	/* header data */
	pkt = tpp_bld_pkt(NULL, NULL, sizeof(tpp_mcast_pkt_hdr_t), 1, (void **) &mhdr);
	if (!pkt) {
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		return -1;
	}
	mhdr->type = TPP_MCAST_DATA;
	mhdr->hop = 0;
	mhdr->totlen = htonl(len);
	memcpy(&mhdr->src_addr, &mstrm->src_addr, sizeof(tpp_addr_t));
	mhdr->num_streams = htonl(num_fds);
	mhdr->info_len = htonl(minfo_len);

	if (tpp_conf->compress == 1 && minfo_len > TPP_COMPR_SIZE) {
		def_ctx = tpp_multi_deflate_init(minfo_len);
		if (def_ctx == NULL)
			goto err;
	} else {
		minfo_buf = malloc(minfo_len);
		if (!minfo_buf) {
			tpp_log(LOG_CRIT, __func__, "Out of memory allocating mcast buffer of %d bytes", minfo_len);
			goto err;
		}
	}

	for (i = 0; i < num_fds; i++) {
		strm = get_strm_atomic(mstrm->mcast_data->strms[i]);
		if (!strm) {
			tpp_log(LOG_ERR, NULL, "Stream %d is not open", mstrm->mcast_data->strms[i]);
			goto err;
		}

		/* per stream data */
		tmp_minfo.src_sd = htonl(strm->sd);
		tmp_minfo.src_magic = htonl(strm->src_magic);
		tmp_minfo.dest_sd = htonl(strm->dest_sd);

		TPP_DBPRT("MCAST src_sd=%u, dest_sd=%u", strm->sd, strm->dest_sd);

		memcpy(&tmp_minfo.dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

		if (def_ctx == NULL) { /* no compression */
			minfo = (tpp_mcast_pkt_info_t *)((char *) minfo_buf + (i * sizeof(tpp_mcast_pkt_info_t)));
			memcpy(minfo, &tmp_minfo, sizeof(tpp_mcast_pkt_info_t));
		} else {
			finish = (i == (num_fds - 1)) ? 1 : 0;

			ret = tpp_multi_deflate_do(def_ctx, finish, &tmp_minfo, sizeof(tpp_mcast_pkt_info_t));
			if (ret != 0)
				goto err;
		}
	}

	if (def_ctx != NULL) {
		minfo_buf = tpp_multi_deflate_done(def_ctx, &cmpr_len);
		if (minfo_buf == NULL)
			goto err;

		TPP_DBPRT("*** mcast_send hdr orig=%d, cmprsd=%u", minfo_len, cmpr_len);
		mhdr->info_cmprsd_len = htonl(cmpr_len);
	} else {
		TPP_DBPRT("*** mcast_send uncompressed hdr orig=%d", minfo_len);
		mhdr->info_cmprsd_len = 0;
		cmpr_len = minfo_len;
	}
	def_ctx = NULL; /* done with compression */

	if (!tpp_bld_pkt(pkt, minfo_buf, cmpr_len, 0, NULL)) { /* add minfo chunk */
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		return -1;
	}

	if (!tpp_bld_pkt(pkt, data, to_send, 0, NULL)) { /* add data chunk */
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		return -1;
	}

	TPP_DBPRT("*** sending %d totlen", pkt->totlen);

	rc = send_to_router(pkt);
	if (rc == 0)
		return len; /* all given data sent, so return len */

	tpp_log(LOG_ERR, __func__, "Failed to send to router"); /* fall through */

err:
	tpp_mcast_notify_members(mtfd, TPP_CMD_NET_CLOSE);
	if (def_ctx)
		tpp_multi_deflate_done(def_ctx, &cmpr_len);

	if (minfo_buf)
		free(minfo_buf);
	return rc;
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

	if (mtfd < 0)
		return 0;

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

/**
 * @brief
 *	Add the stream to a queue of streams to be closed by the transport thread.
 *
 * @par Functionality
 *	Even if the app thread wants to free a stream, it adds the stream to this
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
	tpp_router_t *r = get_active_router();

	if (!r)
		return;

	tpp_write_lock(&strmarray_lock); /* already under lock, dont need get_strm_atomic */

	if (strmarray[strm->sd].slot_state != TPP_SLOT_BUSY) {
		tpp_unlock_rwlock(&strmarray_lock);
		return;
	}
	strmarray[strm->sd].slot_state = TPP_SLOT_DELETED;
	tpp_unlock_rwlock(&strmarray_lock);

	TPP_DBPRT("Marked sd=%u DELETED", strm->sd);

	if ((c = malloc(sizeof(strm_action_info_t))) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating stream free info");
		return;
	}
	c->strm_action_time = time(0); /* asap */
	c->strm_action_func = queue_strm_free;
	c->sd = strm->sd;

	tpp_lock(&strm_action_queue_lock);
	if (tpp_enque(&strm_action_queue, c) == NULL)
		tpp_log(LOG_CRIT, __func__, "Failed to Queue close");

	tpp_unlock(&strm_action_queue_lock);

	TPP_DBPRT("Enqueued strm close for sd=%u", strm->sd);

	tpp_transport_wakeup_thrd(r->conn_fd);
	return;
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
 *	Free stream and add stream slot to a queue of slots to be marked free
 *	after TPP_CLOSE_WAIT time.
 *
 * @par Functionality
 *	The slot is not marked free immediately, rather after a period. This is to
 *	ensure that wandering/delayed messages do not cause havoc.
 *	Additionally deletes the stream's entry in the Stream index.
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

	strm = get_strm_atomic(sd);
	if (!strm)
		return;

	free_stream_resources(strm);
	TPP_DBPRT("Freed sd=%u resources", sd);

	if ((c = malloc(sizeof(strm_action_info_t))) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating stream action info");
		return;
	}
	c->strm_action_time = time(0) + TPP_CLOSE_WAIT; /* time to close */
	c->strm_action_func = free_stream;
	c->sd = sd;

	tpp_lock(&strm_action_queue_lock);
	if (tpp_enque(&strm_action_queue, c) == NULL)
		tpp_log(LOG_CRIT, __func__, "Failed to Queue Free");
	tpp_unlock(&strm_action_queue_lock);

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
 *	send notification to APP.
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

	if (tpp_mbox_post(&app_mbox, strm->sd, cmd, NULL, 0) != 0) {
		tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
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
 *	Searches the index of streams based on the destination address.
 *	There could be several entries, since several streams could be open
 *	to the same destination. The index search quickly find the first entry
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
	void *idx_ctx = NULL;
	void *idx_nkey = dest_addr;
	stream_t *strm;

	while (pbs_idx_find(streams_idx, &idx_nkey, (void **)&strm, &idx_ctx) == PBS_IDX_RET_OK) {
		if (memcmp(idx_nkey, dest_addr, sizeof(tpp_addr_t)) != 0)
			break;
		TPP_DBPRT("sd=%u, dest_sd=%u, u_state=%d, t-state=%d, dest_magic=%u", strm->sd, strm->dest_sd, strm->u_state, strm->t_state, strm->dest_magic);
		if (strm->dest_sd == dest_sd && strm->dest_magic == dest_magic) {
			pbs_idx_free_ctx(idx_ctx);
			return strm;
		}
	}
	pbs_idx_free_ctx(idx_ctx);
	return NULL;
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

	tpp_lock(&strm_action_queue_lock);
	while ((n = TPP_QUE_NEXT(&strm_action_queue, n))) {
		strm_action_info_t *c;

		c = TPP_QUE_DATA(n);
		if (c && ((c->strm_action_time <= now) || (force == 1))) {
			n = tpp_que_del_elem(&strm_action_queue, n);
			TPP_DBPRT("Calling action function for stream %u", c->sd);
			tpp_unlock(&strm_action_queue_lock);

			/* unlock and call action function, then reacquire lock */
			c->strm_action_func(c->sd);

			tpp_lock(&strm_action_queue_lock);
			if (c->strm_action_func == free_stream) {
				/* free stream itself clears elements from the strm_action_queue
				 * so restart walking from the head of strm_action_queue
				 */
				n = NULL;
			}
			free(c);
		}
	}
	tpp_unlock(&strm_action_queue_lock);
}

/**
 * @brief
 *	The timer handler function registered with the IO thread.
 *
 * @par Functionality
 *	This function is called periodically (after the amount of time as
 *	specified by leaf_next_event_expiry() function) by the IO thread. This
 *	drives the close packets to be acted upon in time.
 *
 * @retval  - Time of next event expriry
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
leaf_timer_handler(time_t now)
{
	act_strm(now, 0);

	return leaf_next_event_expiry(now);
}

/**
 * @brief
 *	This function returns the amt of time after which the nearest event
 *	happens (close etc). The IO thread calls this function to determine
 *	how much time to sleep before calling the timer_handler function
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
	strm_action_info_t *f;

	tpp_lock(&strm_action_queue_lock);

	if ((n = TPP_QUE_HEAD(&strm_action_queue))) {
		if ((f = TPP_QUE_DATA(n)))
			rc3 = f->strm_action_time;
	}
	tpp_unlock(&strm_action_queue_lock);

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
 *	Send a data packet to the APP layer
 *
 * @par Functionality
 *	Writes the packet to the pipe that the APP is monitoring, when APP reads
 *	from the read end of the pipe, it gets the pointer to the data
 *
 * @param[in] sd - The descriptor of the stream
 * @param[in] type - The type of the data packet (data, close etc)
 * @param[in] buf - The data that has to be stored
 * @param[in] sz - The size of the data
 * @param[in] totlen - Total data size
 *
 * @return Error code
 * @retval 0 - Success
 * @retval -1 - Failure
 * @retval -2 - App mbox full
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
send_pkt_to_app(stream_t *strm, unsigned char type, void *data, int sz, int totlen)
{
	int rc;
	int cmd;
	void *tmp;
	tpp_packet_t *obj;

	if (type == TPP_DATA) {
		/* in case of uncompressed packets, totlen == compressed_len
		 * so amount of data on wire is compressed len, so allways check against
		 * compressed_len
		 */
		if (sz != totlen) {
			if (!(tmp = tpp_inflate(data, sz, totlen))) {
				tpp_log(LOG_CRIT, __func__, "Decompression failed");
				return -1;
			}
			data = tmp;
		} else {
			/* this is still the pointer to the data part of original buffer, must make copy */
			tmp = malloc(totlen);
			memcpy(tmp, data, totlen);
			data = tmp;
		}
		obj = tpp_bld_pkt(NULL, data, totlen, 0, NULL);
		if (!obj) {
			tpp_log(LOG_CRIT, __func__, "Failed to build packet");
			return -1;
		}
		cmd = TPP_CMD_NET_DATA;
	} else {
		cmd = TPP_CMD_PEER_CLOSE;
		strm->t_state = TPP_TRNS_STATE_PEER_CLOSED;
		obj = NULL;
	}

	TPP_DBPRT("Sending cmd=%d to sd=%u", cmd, strm->sd);

	/* since we received one packet, send notification to app */
	rc = tpp_mbox_post(&app_mbox, strm->sd, cmd, obj, sz);
	if (rc != 0) {
		if (obj)
			tpp_free_pkt(obj);
		if (rc == -1)
			tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
		else if (rc == -2)
			tpp_log(LOG_CRIT, __func__, "App mbox is full");
	}
	return rc;
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
	tpp_data_pkt_hdr_t *dhdr = NULL;
	tpp_packet_t *pkt = NULL;

	TPP_DBPRT("Sending CLOSE packet sd=%u, dest_sd=%u", strm->sd, strm->dest_sd);

	pkt = tpp_bld_pkt(NULL, dhdr, sizeof(tpp_data_pkt_hdr_t), 1, (void **) &dhdr);
	if (!pkt) {
		tpp_log(LOG_CRIT, __func__, "Failed to build packet");
		return -1;
	}

	dhdr->type = type;
	dhdr->src_sd = htonl(strm->sd);
	dhdr->src_magic = htonl(strm->src_magic);
	dhdr->dest_sd = htonl(strm->dest_sd);

	memcpy(&dhdr->src_addr, &strm->src_addr, sizeof(tpp_addr_t));
	memcpy(&dhdr->dest_addr, &strm->dest_addr, sizeof(tpp_addr_t));

	if (send_to_router(pkt) != 0) {
		tpp_log(LOG_ERR, __func__, "Failed to send to router");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	destroy the stream finally
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
	if (!strm)
		return;

	tpp_write_lock(&strmarray_lock);

	TPP_DBPRT("Freeing stream resources for sd=%u", strm->sd);

	strmarray[strm->sd].slot_state = TPP_SLOT_DELETED;

	tpp_unlock_rwlock(&strmarray_lock);

	if (strm->mcast_data) {
		if (strm->mcast_data->strms)
			free(strm->mcast_data->strms);
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

	TPP_DBPRT("Freeing stream %u", sd);

	tpp_write_lock(&strmarray_lock); /* updating stream, idx, so WRITE lock */

	strm = strmarray[sd].strm;
	if (strm->strm_type != TPP_STRM_MCAST) {
		void *idx_ctx = NULL;
		int found = 0;
		stream_t *t_strm = NULL;
		void *pdest_addr = &strm->dest_addr;

		while (pbs_idx_find(streams_idx, &pdest_addr, (void **)&t_strm, &idx_ctx) == PBS_IDX_RET_OK) {
			if (memcmp(pdest_addr, &strm->dest_addr, sizeof(tpp_addr_t)) != 0)
				break;
			if (strm == t_strm) {
				found = 1;
				break;
			}
		}

		if (!found) {
			/* this should not happen ever */
			tpp_log(LOG_ERR, __func__, "Failed finding strm with dest=%s, strm=%p, sd=%u", tpp_netaddr(&strm->dest_addr), strm, strm->sd);
			tpp_unlock_rwlock(&strmarray_lock);
			pbs_idx_free_ctx(idx_ctx);
			return;
		}

		pbs_idx_delete_byctx(idx_ctx);
		pbs_idx_free_ctx(idx_ctx);
	}

	strmarray[sd].slot_state = TPP_SLOT_FREE;
	strmarray[sd].strm = NULL;
	free(strm);

	if (freed_queue_count < 100) {
		tpp_enque(&freed_sd_queue, (void *)(intptr_t) sd);
		freed_queue_count++;
	}

	tpp_unlock_rwlock(&strmarray_lock);

	tpp_lock(&strm_action_queue_lock);
	/* empty all strm actions from the strm action queue */
	while ((n = TPP_QUE_NEXT(&strm_action_queue, n))) {
		c = TPP_QUE_DATA(n);
		if (c && (c->sd == sd)) {
			n = tpp_que_del_elem(&strm_action_queue, n);
			free(c);
		}
	}
	tpp_unlock(&strm_action_queue_lock);
}

/**
 * @brief
 *	The pre-send handler registered with the IO thread.
 *
 * @par Functionality
 *	When the IO thread is ready to send out a packet over the wire, it calls
 *	a prior registered "pre-send" handler
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
static int
leaf_pkt_presend_handler(int tfd, tpp_packet_t *pkt, void *c, void *extra)
{
	conn_auth_t *authdata = (conn_auth_t *)extra;
	tpp_context_t *ctx = (tpp_context_t *) c;
	tpp_router_t *r;
	tpp_data_pkt_hdr_t *data;
	tpp_chunk_t *first_chunk;
	unsigned char type;

	if (!pkt)
		return 0;
		
	first_chunk = GET_NEXT(pkt->chunks);
	if (!first_chunk)
		return 0;

	data = (tpp_data_pkt_hdr_t *) first_chunk->data;
	type = data->type;

	/* Connection accepcted by comm, set router's state to connected */
	if (type == TPP_CTL_JOIN) {
		r = (tpp_router_t *) ctx->ptr;
		r->state = TPP_ROUTER_STATE_CONNECTED;
		r->delay = 0; /* reset connection retry time to 0 */
		r->conn_time = time(0); /* record connect time */

		tpp_log(LOG_CRIT, NULL, "Connected to pbs_comm %s", r->router_name);

		TPP_DBPRT("Sending cmd to call App net restore handler");
		if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_RESTORE, NULL, 0) != 0) {
			tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
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

	if (authdata->encryptdef == NULL)
		return 0; /* no encryption set, so no need to encrypt packets */

	return (tpp_encrypt_pkt(authdata, pkt));
}

/**
 * @brief
 *	Check a stream based on sd, destination address,
 *	destination stream descriptor.
 *
 * @param[in] src_sd - The stream with which to match
 * @param[in] dest_addr - address of the destination
 * @param[in] dest_sd   - The descriptor of the destination stream
 * @paarm[in] msg - point to buf to return message
 * @param[in] sz - length of message buffer
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
check_strm_valid(unsigned int src_sd, tpp_addr_t *dest_addr, int dest_sd, char *msg, int sz)
{
	stream_t *strm = NULL;

	if (strmarray == NULL || src_sd >= max_strms) {
		TPP_DBPRT("Must be data for old instance, ignoring");
		return NULL;
	}

	if (strmarray[src_sd].slot_state != TPP_SLOT_BUSY) {
		snprintf(msg, sz, "Data to sd=%u which is %s", src_sd, (strmarray[src_sd].slot_state == TPP_SLOT_DELETED ? "deleted" : "freed"));
		return NULL;
	}

	strm = strmarray[src_sd].strm;

	if (strm->t_state != TPP_TRNS_STATE_OPEN) {
		snprintf(msg, sz, "Data to sd=%u whose transport is not open (t_state=%d)", src_sd, strm->t_state);
		send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
		return NULL;
	}

	if ((strm->dest_sd != UNINITIALIZED_INT && strm->dest_sd != dest_sd) || memcmp(&strm->dest_addr, dest_addr, sizeof(tpp_addr_t)) != 0) {
		snprintf(msg, sz, "Data to sd=%u mismatch dest info in stream", src_sd);
		return NULL;
	}

	return strm;
}

/**
 * @brief
 *	Wrapper function for the leaf to handle incoming data. This
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
leaf_pkt_handler(int tfd, void *buf, int len, void *c, void *extra)
{
	void *data_out = NULL;
	int rc = leaf_pkt_handler_inner(tfd, buf, &data_out, len, c, extra);
	free(data_out);
	return rc;
}

/**
 * @brief
 *	Inner handler function for the received packet handler registered with the IO thread.
 *
 * @par Functionality
 *	When the IO thread is received a packet over the wire, it calls
 *	a prior registered "chunk-send" handler. This handler is responsible to
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
 * @param[in] buf - The pointer to the data that arrived
 * @param[out] data_out - The pointer to the newly allocated data buffer, if any
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
static int
leaf_pkt_handler_inner(int tfd, void *buf, void **data_out, int len, void *ctx, void *extra)
{
	stream_t *strm;
	enum TPP_MSG_TYPES type;
	tpp_data_pkt_hdr_t *dhdr = buf;
	conn_auth_t *authdata = (conn_auth_t *)extra;
	int totlen;
	int rc;

again:
	totlen = ntohl(dhdr->totlen);
	type = dhdr->type;
	errno = 0;

	if(type >= TPP_LAST_MSG)
		return -1;

	switch (type) {
		case TPP_ENCRYPTED_DATA: {
			int sz = sizeof(tpp_encrypt_hdr_t);
			int len_out;

			if (authdata == NULL) {
				tpp_log(LOG_CRIT, __func__, "tfd=%d, No auth data found", tfd);
				return -1;
			}

			if (authdata->encryptdef == NULL) {
				tpp_log(LOG_CRIT, __func__, "connetion doesn't support decryption of data");
				return -1;
			}

			if (authdata->encryptdef->decrypt_data(authdata->encryptctx, (void *)((char *)buf + sz), (size_t)len - sz, data_out, (size_t *)&len_out) != 0) {
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
			int rc = 0;

			memcpy(&ahdr, dhdr, sizeof(tpp_auth_pkt_hdr_t));
			len_in = (size_t)len - sizeof(tpp_auth_pkt_hdr_t);
			data_in = calloc(1, len_in);
			if (data_in == NULL) {
				tpp_log(LOG_CRIT, __func__, "Out of memory");
				return -1;
			}
			memcpy(data_in, (char *)dhdr + sizeof(tpp_auth_pkt_hdr_t), len_in);

			rc = tpp_handle_auth_handshake(tfd, tfd, authdata, ahdr.for_encrypt, data_in, len_in);
			if (rc != 1) {
				free(data_in);
				return rc;
			}

			free(data_in);

			if (ahdr.for_encrypt == FOR_ENCRYPT && strcmp(authdata->config->auth_method, AUTH_RESVPORT_NAME) != 0) {
				if (strcmp(authdata->config->auth_method, authdata->config->encrypt_method) != 0) {
					rc = tpp_handle_auth_handshake(tfd, tfd, authdata, FOR_AUTH, NULL, 0);
					if (rc != 1) {
						return rc;
					}
				} else {
					authdata->authctx = authdata->encryptctx;
					authdata->authdef = authdata->encryptdef;
					tpp_transport_set_conn_extra(tfd, authdata);
				}
			}

			/* send TPP_CTL_JOIN msg to router */
			return leaf_send_ctl_join(tfd, ctx);
		}
		break; /* TPP_AUTH_CTX */

		case TPP_CTL_MSG: {
			tpp_ctl_pkt_hdr_t *hdr = (tpp_ctl_pkt_hdr_t *) dhdr;
			int code = hdr->code;

			if (code == TPP_MSG_NOROUTE) {
				unsigned int src_sd = ntohl(hdr->src_sd);
				strm = get_strm_atomic(src_sd);
				if (strm) {
					char *msg = ((char *) dhdr) + sizeof(tpp_ctl_pkt_hdr_t);
					tpp_log(LOG_DEBUG, NULL, "sd %u, Received noroute to dest %s, msg=\"%s\"", src_sd, tpp_netaddr(&hdr->src_addr), msg);
					send_app_strm_close(strm, TPP_CMD_NET_CLOSE, 0);
				}
				return 0;
			}

			if (code == TPP_MSG_UPDATE) {
				tpp_log(LOG_INFO, NULL, "Received UPDATE from pbs_comm");
				if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_RESTORE, NULL, 0) != 0) {
					tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
				}
				return 0;
			}

			if (code == TPP_MSG_AUTHERR) {
				char *msg = ((char *) dhdr) + sizeof(tpp_ctl_pkt_hdr_t);
				tpp_log(LOG_CRIT, NULL, "tfd %d, Received authentication error from router %s, err=%d, msg=\"%s\"", tfd, tpp_netaddr(&hdr->src_addr), hdr->error_num, msg);
				return -1; /* close connection */
			}
		}
		break; /* TPP_CTL_MSG */

		case TPP_CTL_LEAVE: {
			tpp_leave_pkt_hdr_t *hdr = (tpp_leave_pkt_hdr_t *) dhdr;
			tpp_que_t send_close_queue;
			tpp_addr_t *addrs;
			int i;

			PRTPKTHDR(__func__, hdr, 0);

			/* bother only about leave */
			tpp_read_lock(&strmarray_lock); /* walking stream idx, so read lock */
			TPP_QUE_CLEAR(&send_close_queue);

			/* go past the header and point to the list of addresses following it */
			addrs = (tpp_addr_t *) (((char *) dhdr) + sizeof(tpp_leave_pkt_hdr_t));
			for (i = 0; i < hdr->num_addrs; i++) {
				void *idx_ctx = NULL;
				void *paddr = &addrs[i];

				while (pbs_idx_find(streams_idx, &paddr, (void **)&strm, &idx_ctx) == PBS_IDX_RET_OK) {
					if (memcmp(paddr, &addrs[i], sizeof(tpp_addr_t)) != 0)
						break;
					strm->lasterr = 0;
					/* under lock already, can access directly */
					if (strmarray[strm->sd].slot_state == TPP_SLOT_BUSY) {
						if (tpp_enque(&send_close_queue, strm) == NULL) {
							tpp_log(LOG_CRIT, __func__, "Out of memory enqueing to send close queue");
							tpp_unlock_rwlock(&strmarray_lock);
							pbs_idx_free_ctx(idx_ctx);
							return -1;
						}
					}
				}
				pbs_idx_free_ctx(idx_ctx);
			}
			tpp_unlock_rwlock(&strmarray_lock);

			while ((strm = (stream_t *) tpp_deque(&send_close_queue))) {
				TPP_DBPRT("received TPP_CTL_LEAVE, sending TPP_CMD_NET_CLOSE sd=%u", strm->sd);
				send_app_strm_close(strm, TPP_CMD_NET_CLOSE, hdr->ecode);
			}

			return 0;
		}
		break;
		/* TPP_CTL_LEAVE */

		case TPP_DATA:
		case TPP_CLOSE_STRM: {
			char msg[TPP_GEN_BUF_SZ] = "";
			unsigned int src_sd;
			unsigned int dest_sd;
			unsigned int src_magic;
			unsigned int sz = len - sizeof(tpp_data_pkt_hdr_t);
			void *data = (char *) dhdr + sizeof(tpp_data_pkt_hdr_t);

			src_sd = ntohl(dhdr->src_sd);
			dest_sd = ntohl(dhdr->dest_sd);
			src_magic = ntohl(dhdr->src_magic);

			PRTPKTHDR(__func__, dhdr, sz);

			if (dest_sd == UNINITIALIZED_INT && type != TPP_CLOSE_STRM && sz == 0) {
				tpp_log(LOG_ERR, NULL, "ack packet without dest_sd set!!!");
				return -1;
			}

			if (dest_sd == UNINITIALIZED_INT) {
				tpp_read_lock(&strmarray_lock); /* walking stream idx, so read lock */
				strm = find_stream_with_dest(&dhdr->src_addr, src_sd, src_magic);
				tpp_unlock_rwlock(&strmarray_lock);
				if (strm == NULL) {
					TPP_DBPRT("No stream associated, Opening new stream");
					/*
					 * packet's destination address = stream's source address at our end
					 * packet's source address = stream's destination address at our end
					 */
					if ((strm = alloc_stream(&dhdr->dest_addr, &dhdr->src_addr)) == NULL) {
						tpp_log(LOG_CRIT, __func__, "Out of memory allocating stream");
						return -1;
					}
				} else {
					TPP_DBPRT("Stream sd=%u, u_state=%d, t_state=%d", strm->sd, strm->u_state, strm->t_state);
				}
				dest_sd = strm->sd;
			} else {
				TPP_DBPRT("Stream found from index in packet = %u", dest_sd);
			}

			/* In any case, check for the stream's validity */
			tpp_read_lock(&strmarray_lock); /* walking stream idx, so read lock */
			strm = check_strm_valid(dest_sd, &dhdr->src_addr, src_sd, msg, sizeof(msg));
			tpp_unlock_rwlock(&strmarray_lock);
			if (strm == NULL) {
				if (type != TPP_CLOSE_STRM && sz == 0)
					return 0; /* it is an ack packet, don't send noroute */

				tpp_log(LOG_WARNING, __func__, msg);
				tpp_send_ctl_msg(tfd, TPP_MSG_NOROUTE, &dhdr->src_addr, &dhdr->dest_addr, src_sd, 0, msg);
				return 0;
			}

			/*
			 * this should be set even close packets since
			 * we could have opened a stream locally, sent a packet
			 * and the ack carries the other sides sd, which we must store
			 * and use in the next send out.
			 */
			strm->dest_sd = src_sd; /* next time outgoing will have dest_fd */
			strm->dest_magic = src_magic; /* used for matching next time onwards */

			rc = send_pkt_to_app(strm, type, data, sz, totlen);

			return rc; /* 0 - success, -1 failed, -2 app mbox full */
		}
		break; /* TPP_DATA, TPP_CLOSE_STRM */

		default:
			tpp_log(LOG_ERR, NULL,  "Bad header for incoming packet on fd %d, header = %d, len = %d", tfd, type, len);

	} /* switch */

	return -1;
}

/**
 * @brief
 *	The connection drop (close) handler registered with the IO thread.
 *
 * @par Functionality
 *	When the connection between this leaf and a router is dropped, the IO
 *	thread first calls this (prior registered) function to notify the leaf
 *	layer of the fact that a connection was dropped.
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
static int
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
		if (authdata->authdef != authdata->encryptdef && authdata->encryptctx && authdata->encryptdef)
			authdata->encryptdef->destroy_ctx(authdata->encryptctx);
		if (authdata->config)
			free_auth_config(authdata->config);
		/* DO NOT free authdef here, it will be done in unload_auths() */
		free(authdata);
		tpp_transport_set_conn_extra(tfd, NULL);
	}

	r = (tpp_router_t *) ctx->ptr;

	/* deallocate the connection structure associated with ctx */
	tpp_transport_close(r->conn_fd);

	if (tpp_going_down == 1)
		return -1; /* while we are doing shutdown don't try to reconnect etc */

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
		unsigned int i;
		/* log disconnection message */
		tpp_log(LOG_CRIT, NULL, "Connection to pbs_comm %s down", r->router_name);

		/* send individual net close messages to app */
		tpp_read_lock(&strmarray_lock); /* walking stream idx, so read lock */
		for (i = 0; i < max_strms; i++) {
			if (strmarray[i].slot_state == TPP_SLOT_BUSY) {
				strmarray[i].strm->t_state = TPP_TRNS_STATE_NET_CLOSED;
				TPP_DBPRT("net down, sending TPP_CMD_NET_CLOSE sd=%u", strmarray[i].strm->sd);
				send_app_strm_close(strmarray[i].strm, TPP_CMD_NET_CLOSE, 0);
			}
		}
		tpp_unlock_rwlock(&strmarray_lock);

		if (the_app_net_down_handler) {
			if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_DOWN, NULL, 0) != 0) {
				tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
				return -1;
			}
		}

		/* if we are connected to another router, make app layer realize they need to restart streams */
		/* send a connection restore message, so app restarts streams on the alternate route */
		if (get_active_router()) {
			if (tpp_mbox_post(&app_mbox, UNINITIALIZED_INT, TPP_CMD_NET_RESTORE, NULL, 0) != 0) {
				tpp_log(LOG_CRIT, __func__, "Error writing to app mbox");
				return -1;
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

	return 0;
}

/* @brief
 * wrapper routine that checks the router connection status before calling
 * tpp_transport_send(). This function can check not just the router fd
 * but that the connection  is actually in fully connected state
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval  -2 - transport buffers full
 * @retval   0 - Success
 *
 */
static int
send_to_router(tpp_packet_t *pkt)
{
	tpp_router_t *router = get_active_router();
	if ((router == NULL) || (router->conn_fd == -1) || (router->state != TPP_ROUTER_STATE_CONNECTED)) {
		tpp_log(LOG_ERR, __func__, "No active router");
		return -1;
	}

	return (tpp_transport_vsend(router->conn_fd, pkt));
}
