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
 * @file	tpp_transport.c
 *
 * @brief	The IO layer of the tpp library (drives the IO thread)
 *
 * @par		Functionality:
 *
 *		TPP = TCP based Packet Protocol. This layer uses TCP in a multi-
 *		hop router based network topology to deliver packets to desired
 *		destinations. LEAF (end) nodes are connected to ROUTERS via
 *		persistent TCP connections. The ROUTER has intelligence to route
 *		packets to appropriate destination leaves or other routers.
 *
 *		This is the IO side in the tpp library.
 *		This IO layer is part of all the tpp participants,
 *		both leaves (end-points) and routers.
 *
 */
#include <pbs_config.h>

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
#include <sys/time.h>
#include <signal.h>
#include "pbs_idx.h"
#include "tpp_internal.h"
#include "auth.h"

#define TPP_CONN_DISCONNECTED   1 /* Channel is disconnected */
#define TPP_CONN_INITIATING     2 /* Channel is initiating */
#define TPP_CONN_CONNECTING     3 /* Channel is connecting */
#define TPP_CONN_CONNECTED      4 /* Channel is connected */

int tpp_going_down = 0;

/*
 * Delayed connection queue, to retry connection after
 * specific periods of time
 */
#define TPP_CONN_CONNECT_DELAY 1
typedef struct {
	int tfd;       /* on which physical connection */
	char cmdval; 	/* cmd type */
	time_t conn_time; /* time at which to connect */
} conn_event_t;

/*
 * The per thread data structure. This library creates a thread-pool of
 * a configuration supplied number of threads. Each thread maintains some
 * information about itself in this structure.
 *
 * The command pipe is a pipe which the thread monitors for incoming events, or
 * commands, so other threads can pass information to it via this pipe.
 *
 */
typedef struct {
	int thrd_index;			  /* thread index for debugging */
	pthread_t worker_thrd_id; /* Thread id of this thread */
	int listen_fd;		/* If this is the thread that is also doing
				 * the listening, then the listening socket
				 * descriptor
				 */
#ifdef NAS /* localmod 149 */
	int nas_tpp_log_enabled;	/* controls the printing of statistics
					 * to the log
					 */
	int NAS_TPP_LOG_PERIOD_A;	/* this should be the shortest of the
					 * logging periods, as it is also the
					 * frequency with which we check if
					 * statistics should be printed
					 */
	int NAS_TPP_LOG_PERIOD_B;
	int NAS_TPP_LOG_PERIOD_C;
	time_t nas_last_time_A;
	double nas_kb_sent_A;
	int nas_num_lrg_sends_A;
	int nas_num_qual_lrg_sends_A;
	int nas_max_bytes_lrg_send_A;
	int nas_min_bytes_lrg_send_A;
	double nas_lrg_send_sum_kb_A;
	time_t nas_last_time_B;
	double nas_kb_sent_B;
	int nas_num_lrg_sends_B;
	int nas_num_qual_lrg_sends_B;
	int nas_max_bytes_lrg_send_B;
	int nas_min_bytes_lrg_send_B;
	double nas_lrg_send_sum_kb_B;
	time_t nas_last_time_C;
	double nas_kb_sent_C;
	int nas_num_lrg_sends_C;
	int nas_num_qual_lrg_sends_C;
	int nas_max_bytes_lrg_send_C;
	int nas_min_bytes_lrg_send_C;
	double nas_lrg_send_sum_kb_C;
#endif /* localmod 149 */
	void *em_context;         /* the em context */
	tpp_que_t def_act_que;  /* The deferred action queue on this thread */
	tpp_mbox_t mbox;     /* message box for this thread */
	tpp_tls_t *tpp_tls;	/* tls data related to tpp work */
} thrd_data_t;

#ifdef NAS /* localmod 149 */
static  char tpp_instr_flag_file[_POSIX_PATH_MAX] = "/PBS/flags/tpp_instrumentation";
#endif /* localmod 149 */

static thrd_data_t **thrd_pool; /* array of threads - holds the thread pool */
static int num_threads;       /* number of threads in the thread pool */
static int last_thrd = -1;    /* global index to rotate work amongst threads */
static int max_con = MAX_CON; /* nfiles */

static struct tpp_config *tpp_conf;  /* store a pointer to the tpp_config supplied */

/*
 * Save the connection related parameters here, so we don't have to parse
 * each time.
 */
typedef struct {
	char *hostname; /* the host name to connect to */
	int port;       /* the port to connect to */
	int need_resvport;  /* bind to resv port? */
} conn_param_t;

/*
 * Structure that holds information about each TCP connection between leaves and
 * router or between routers and routers. A single IO thread can handle multiple
 * such physical connections. We refer to the indexes to the physical
 * connections as "transport fd" or tfd.
 */
typedef struct {
	int sock_fd;             /* socket fd (TCP) for this physical connection*/
	int lasterr;             /* last error that was captured on this socket */
	short net_state;         /* network status of this connection, up, down etc */
	int ev_mask;			 /* event mask in effect so far */

	conn_param_t *conn_params; /* the connection params */

	tpp_mbox_t send_mbox;     /* mbox of pkts to send */
	tpp_chunk_t scratch;      /* scratch to work on incoming data */
	tpp_packet_t *curr_send_pkt; /* current packet dequed from send_mbox to be sent out  */
	thrd_data_t *td;          /* connections controller thread */

	tpp_context_t *ctx;       /* upper layers context information */

	void *extra;              /* extra data structure */
} phy_conn_t;

/* structure for holding an array of physical connection structures */
typedef struct {
	int slot_state;        /* slot is busy or free */
	phy_conn_t *conn; /* the physical connection using this slot */
} conns_array_type_t;

conns_array_type_t *conns_array = NULL; /* array of physical connections */
int conns_array_size = 0;                    /* the size of physical connection array */
pthread_rwlock_t cons_array_lock;            /* rwlock used to synchronize array ops */
pthread_mutex_t thrd_array_lock;             /* mutex used to synchronize thrd assignment */

/* function forward declarations */
static void *work(void *v);
static int assign_to_worker(int tfd, int delay, thrd_data_t *td);
static int handle_disconnect(phy_conn_t *conn);
static void handle_incoming_data(phy_conn_t *conn);
static void send_data(phy_conn_t *conn);
static void free_phy_conn(phy_conn_t *conn);
static void handle_cmd(thrd_data_t *td, int tfd, int cmd, void *data);
static short add_pkt(phy_conn_t *conn);
static phy_conn_t *get_transport_atomic(int tfd, int *slot_state);

/**
 * @brief
 *	Enqueue an deferred action
 *
 * @par Functionality
 *	Used for initiating a connection after a delay, or deferred close / reads
 *
 * @param[in] td    - The thread data for the controlling thread
 * @param[in] tfd   - The descriptor of the physical connection
 * @param[in] delay - The amount of time after which event has to be triggered
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
enque_deferred_event(thrd_data_t *td, int tfd, int cmd, int delay)
{
	conn_event_t *conn_ev;
	tpp_que_elem_t *n;
	void *ret;

	conn_ev = malloc(sizeof(conn_event_t));
	if (!conn_ev) {
		tpp_log(LOG_CRIT, __func__, "Out of memory queueing a lazy connect");
		return;
	}
	conn_ev->tfd = tfd;
	conn_ev->cmdval = cmd;
	conn_ev->conn_time = time(0) + delay;

	n = NULL;
	while ((n = TPP_QUE_NEXT(&td->def_act_que, n))) {
		conn_event_t *p;

		p = TPP_QUE_DATA(n);

		/* sorted list, insert before node which has higher time */
		if (p && (p->conn_time >= conn_ev->conn_time))
			break;
	}
	/* insert before this position */
	if (n)
		ret = tpp_que_ins_elem(&td->def_act_que, n, conn_ev, 1);
	else
		ret = tpp_enque(&td->def_act_que, conn_ev);

	if (ret == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory queueing a lazy connect");
		free(conn_ev);
	}
}

/**
 * @brief
 *	Trigger deferred action for those whose time has been reached
 *
 * @param[in] td   - The thread data for the controlling thread
 * @param[in] now  - Current time to check events with
 *
 * @return Wait time for the next deferred event
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
trigger_deferred_events(thrd_data_t *td, time_t now)
{
	conn_event_t *q;
	tpp_que_elem_t *n = NULL;
	int slot_state;
	time_t wait_time = -1;

	while ((n = TPP_QUE_NEXT(&td->def_act_que, n))) {
		q = TPP_QUE_DATA(n);
		if (q == NULL)
			continue;
		if (now >= q->conn_time) {
			(void) get_transport_atomic(q->tfd, &slot_state);
			if (slot_state == TPP_SLOT_BUSY)
				handle_cmd(td, q->tfd, q->cmdval, NULL);

			n = tpp_que_del_elem(&td->def_act_que, n);
			free(q);
		} else {
			wait_time = q->conn_time - now;
			break;
			/*
			 * events are sorted on time,
			 * so if first not fitting, next events wont
			 */
		}
	}
	return wait_time;
}

/**
 * @brief
 * Function called by upper layers to get the "thrd" that
 * is associated with the connection
 *
 * @param[in] tfd - Descriptor to the physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void *
tpp_transport_get_thrd_context(int tfd)
{
	thrd_data_t *td = NULL;

	if (tpp_read_lock(&cons_array_lock))
		return NULL;

	if (tfd >= 0 && tfd < conns_array_size) {
		if (conns_array[tfd].conn && conns_array[tfd].slot_state == TPP_SLOT_BUSY)
			td = conns_array[tfd].conn->td;
	}
	tpp_unlock_rwlock(&cons_array_lock);

	return td;
}

/**
 * @brief
 *	Function called by upper layers to get the "user data/context" that
 *	is associated with the connection (this was set earlier)
 *
 * @param[in] tfd - Descriptor to the physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void *
tpp_transport_get_conn_ctx(int tfd)
{
	int slot_state;
	phy_conn_t *conn;
	conn = get_transport_atomic(tfd, &slot_state);
	if (conn)
		return conn->ctx;

	return NULL;
}

/**
 * @brief
 *	Function called by upper layers to associate a context (user data) to
 *	the physical connection
 *
 * @param[in] tfd - Descriptor to the physical connection
 * @param[in] ctx - Pointer to the user context
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_transport_set_conn_ctx(int tfd, void *ctx)
{
	int slot_state;
	phy_conn_t *conn;
	conn = get_transport_atomic(tfd, &slot_state);
	if (conn)
		conn->ctx = ctx;
}

/**
 * @brief
 *	Creates a listening socket using platform specific calls
 *
 * @param[in] port - port to bind socket to
 *
 * @return - socket descriptor of server socket
 * @retval   -1 - Failure
 * @retval !=-1 - Socket descriptor of newly created server socket
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tpp_cr_server_socket(int port)
{
	struct sockaddr_in serveraddr;
	int sd;
	int yes = 1;

	serveraddr.sin_family = AF_INET;
	serveraddr.sin_addr.s_addr = INADDR_ANY;
	serveraddr.sin_port = htons(port);
	memset(&(serveraddr.sin_zero), '\0', sizeof(serveraddr.sin_zero));

	if ((sd = tpp_sock_socket(AF_INET, SOCK_STREAM, 0)) == -1) {
		tpp_log(LOG_CRIT, __func__, "tpp_sock_socket() error, errno=%d", errno);
		return -1;
	}
	if (tpp_sock_setsockopt(sd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(int)) == -1) {
		tpp_log(LOG_CRIT, __func__, "tpp_sock_setsockopt() error, errno=%d", errno);
		return -1;
	}
	if (tpp_sock_bind(sd, (struct sockaddr *) &serveraddr, sizeof(serveraddr)) == -1) {
		char *msgbuf;
#ifdef HAVE_STRERROR_R
		char buf[TPP_GEN_BUF_SZ];

		if (strerror_r(errno, buf, sizeof(buf)) == 0)
			pbs_asprintf(&msgbuf, "%s while binding to port %d", buf, port);
		else
#endif
			pbs_asprintf(&msgbuf, "Error %d while binding to port %d", errno, port);
		tpp_log(LOG_CRIT, NULL, msgbuf);
		free(msgbuf);
		return -1;
	}
	if (tpp_sock_listen(sd, 1000) == -1) {
		tpp_log(LOG_CRIT, __func__, "tpp_sock_listen() error, errno=%d", errno);
		return -1;
	}
	return sd;
}

/**
 * @brief
 *	Initialize the transport layer.
 *
 * @par Functionality
 *	Does the following:
 *	1. Creates the TLS used for log buffer etc
 *	2. Creates the thread pool of threads, and initialize the threads
 *	3. If the caller is a router node, then assign one thread to also be
 *	   the listening thread. (binds and listens to a port)
 *	4. Create the command pipe of each thread.
 *
 * @param[in] conf - Ptr to the tpp_config passed from upper layers
 *
 * @return Error code
 * @retval -1 - Error
 * @retval  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_init(struct tpp_config *conf)
{
	int i;
	char mbox_name[TPP_MBOX_NAME_SZ];

	if (conf->node_type == TPP_LEAF_NODE || conf->node_type == TPP_LEAF_NODE_LISTEN) {
		if (conf->numthreads != 1) {
			tpp_log(LOG_CRIT, NULL, "Leaves should start exactly one thread");
			return -1;
		}
	} else {
		if (conf->numthreads < 2) {
			tpp_log(LOG_CRIT, NULL, "pbs_comms should have at least 2 threads");
			return -1;
		}
		if (conf->numthreads > 100) {
			tpp_log(LOG_CRIT, NULL, "pbs_comms should have <= 100 threads");
			return -1;
		}
	}

	tpp_log(LOG_INFO, NULL, "Initializing TPP transport Layer");
	if (tpp_init_lock(&thrd_array_lock))
		return -1;

	if (tpp_init_rwlock(&cons_array_lock))
		return -1;
	
#ifndef WIN32
	/* for unix, set a pthread_atfork handler */
	if (pthread_atfork(tpp_nslookup_atfork_prepare, tpp_nslookup_atfork_parent, tpp_nslookup_atfork_child) != 0) {
		tpp_log(LOG_CRIT, __func__, "tpp nslookup mutex atfork handler failed");
		return -1;
	}
#endif

	tpp_sock_layer_init();

	max_con = tpp_get_nfiles();
	if (max_con < TPP_MAXOPENFD) {
		tpp_log(LOG_WARNING, NULL, "Max files too low - you may want to increase it.");
		if (max_con < 100) {
			tpp_log(LOG_CRIT, NULL, "Max files < 100, cannot continue");
			return -1;
		}
	}
	/* reduce max_con by 1, else on solaris devpoll could fail
	 * See https://community.oracle.com/thread/1915433?start=0&tstart=0.
	 * Snippet from that link..(lest that link goes way).
	 * "We can't monitor our /dev/poll file descriptor using /dev/poll,
	 * so the actual maximum number of file descriptors you can monitor
	 * is OPEN_MAX - 1. Solaris enforces that limit. This breaks other code
	 * out there too, e.g. the libevent library.
	 * Annoying even though it's arguably technically correct".
	 */
	max_con--;

	if (set_pipe_disposition() != 0) {
		tpp_log(LOG_CRIT, __func__, "Could not query SIGPIPEs disposition");
		return -1;
	}

	/* create num_threads worker threads */
	if ((thrd_pool = calloc(conf->numthreads, sizeof(thrd_data_t *))) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating threads");
		return -1;
	}

	for (i = 0; i < conf->numthreads; i++) {
		thrd_pool[i] = calloc(1, sizeof(thrd_data_t));
		if (thrd_pool[i] == NULL) {
			tpp_log(LOG_CRIT, __func__, "Out of memory creating threadpool");
			return -1;
		}
		tpp_invalidate_thrd_handle(&(thrd_pool[i]->worker_thrd_id));
#ifdef NAS /* localmod 149 */
		thrd_pool[i]->nas_tpp_log_enabled = 0;
		thrd_pool[i]->NAS_TPP_LOG_PERIOD_A = 60;
		thrd_pool[i]->NAS_TPP_LOG_PERIOD_B = 300;
		thrd_pool[i]->NAS_TPP_LOG_PERIOD_C = 600;
		thrd_pool[i]->nas_last_time_A = time(0);
		thrd_pool[i]->nas_kb_sent_A = 0.0;
		thrd_pool[i]->nas_num_lrg_sends_A = 0;
		thrd_pool[i]->nas_num_qual_lrg_sends_A = 0;
		thrd_pool[i]->nas_max_bytes_lrg_send_A = 0;
		thrd_pool[i]->nas_min_bytes_lrg_send_A = INT_MAX - 1;
		thrd_pool[i]->nas_lrg_send_sum_kb_A = 0.0;
		thrd_pool[i]->nas_last_time_B = time(0);
		thrd_pool[i]->nas_kb_sent_B = 0.0;
		thrd_pool[i]->nas_num_lrg_sends_B = 0;
		thrd_pool[i]->nas_num_qual_lrg_sends_B = 0;
		thrd_pool[i]->nas_max_bytes_lrg_send_B = 0;
		thrd_pool[i]->nas_min_bytes_lrg_send_B = INT_MAX - 1;
		thrd_pool[i]->nas_lrg_send_sum_kb_B = 0.0;
		thrd_pool[i]->nas_last_time_C = time(0);
		thrd_pool[i]->nas_kb_sent_C = 0.0;
		thrd_pool[i]->nas_num_lrg_sends_C = 0;
		thrd_pool[i]->nas_num_qual_lrg_sends_C = 0;
		thrd_pool[i]->nas_max_bytes_lrg_send_C = 0;
		thrd_pool[i]->nas_min_bytes_lrg_send_C = INT_MAX - 1;
		thrd_pool[i]->nas_lrg_send_sum_kb_C = 0.0;
#endif /* localmod 149 */

		thrd_pool[i]->listen_fd = -1;
		TPP_QUE_CLEAR(&thrd_pool[i]->def_act_que);

		if ((thrd_pool[i]->em_context = tpp_em_init(max_con)) == NULL) {
			tpp_log(LOG_CRIT, __func__, "em_init() error, errno=%d", errno);
			return -1;
		}

		snprintf(mbox_name, sizeof(mbox_name), "Th_%d", (char) i);
		if (tpp_mbox_init(&thrd_pool[i]->mbox, mbox_name, -1) != 0) {
			tpp_log(LOG_CRIT, __func__, "tpp_mbox_init() error, errno=%d", errno);
			return -1;
		}

		if (tpp_mbox_monitor(thrd_pool[i]->em_context, &thrd_pool[i]->mbox) != 0) {
			tpp_log(LOG_CRIT, __func__, "em_mbox_enable_monitoing() error, errno=%d", errno);
			return -1;
		}

		thrd_pool[i]->thrd_index = i;
	}

	if (conf->node_type == TPP_ROUTER_NODE) {
		char *host;
		int port;

		if ((host = tpp_parse_hostname(conf->node_name, &port)) == NULL) {
			tpp_log(LOG_CRIT, __func__, "Out of memory parsing pbs_comm name");
			return -1;
		}
		free(host);

		if ((thrd_pool[0]->listen_fd = tpp_cr_server_socket(port)) == -1) {
			tpp_log(LOG_CRIT, __func__, "pbs_comm socket creation failed");
			return -1;
		}

		if (tpp_em_add_fd(thrd_pool[0]->em_context, thrd_pool[0]->listen_fd, EM_IN) == -1) {
			tpp_log(LOG_CRIT, __func__, "Multiplexing failed");
			return -1;
		}
	}

	tpp_conf = conf;
	num_threads = conf->numthreads;

	for (i = 0; i < conf->numthreads; i++) {
		/* leave the write side of the command pipe to block */
		if (tpp_cr_thrd(work, &(thrd_pool[i]->worker_thrd_id), thrd_pool[i]) != 0) {
			tpp_log(LOG_CRIT, __func__, "Failed to create thread");
			return -1;
		}
	}
	tpp_log(LOG_INFO, NULL, "TPP initialization done");

	return 0;
}

/* the function pointer to the upper layer received packet handler */
int (*the_pkt_handler)(int tfd, void *data, int len, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer connection close handler */
int (*the_close_handler)(int tfd, int error, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer connection restore handler */
int (*the_post_connect_handler)(int tfd, void *data, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer pre packet send handler */
int (*the_pkt_presend_handler)(int tfd, tpp_packet_t *pkt, void *ctx, void *extra) = NULL;

/* upper layer timer handler */
int (*the_timer_handler)(time_t now) = NULL;

/**
 * @brief
 *	Function to register the upper layer handler functions
 *
 * @param[in] pkt_presend_handler  - function ptr to presend handler
 * @param[in] pkt_handler          - function ptr to pkt recvd handler
 * @param[in] close_handler        - function ptr to net close handler
 * @param[in] post_connect_handler - function ptr to post_connect_handler
 * @param[in] timer_handler        - function ptr called periodically
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
void
tpp_transport_set_handlers(
	int (*pkt_presend_handler)(int tfd, tpp_packet_t *pkt, void *ctx, void *extra),
	int (*pkt_handler)(int tfd, void *data, int len, void *ctx, void *extra),
	int (*close_handler)(int tfd, int error, void *ctx, void *extra),
	int (*post_connect_handler)(int tfd, void *data, void *ctx, void *extra),
	int (*timer_handler)(time_t now))
{
	the_pkt_handler = pkt_handler;
	the_close_handler = close_handler;
	the_post_connect_handler = post_connect_handler;
	the_pkt_presend_handler = pkt_presend_handler;
	the_timer_handler = timer_handler;
}

/**
 * @brief
 *	Allocate a physical connection structure and initialize it
 *
 * @par Functionality
 *	Resize the physical connection array. Uses the mutex cons_array_lock
 *	before it manipulates the global conns_array.
 *
 * @param[in] tfd - The file descriptor to be assigned to the new connection
 *
 * @return  Pointer to the newly allocated physical connection structure
 * @retval NULL - Failure
 * @retval !NULL - Ptr to physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static phy_conn_t*
alloc_conn(int tfd)
{
	phy_conn_t *conn;
	char mbox_name[TPP_MBOX_NAME_SZ];

	conn = calloc(1, sizeof(phy_conn_t));
	if (!conn) {
		tpp_log(LOG_CRIT, __func__, "Out of memory allocating physical connection");
		return NULL;
	}
	conn->sock_fd = tfd;
	conn->extra = NULL;

	snprintf(mbox_name, sizeof(mbox_name), "Conn_%d", conn->sock_fd);
	if (tpp_mbox_init(&conn->send_mbox, mbox_name, TPP_MAX_MBOX_SIZE) != 0) {
		free(conn);
		tpp_log(LOG_CRIT, __func__, "tpp_mbox_init() error, errno=%d", errno);
		return NULL;
	}
	/* initialize the send queue to empty */

	/* set to stream array */
	if (tpp_write_lock(&cons_array_lock)) {
		free(conn);
		return NULL;
	}
	if (tfd >= conns_array_size - 1) {
		int newsize;
		void *p;

		/* resize conns */
		newsize = tfd + 100;
		p = realloc(conns_array, sizeof(conns_array_type_t) * newsize);
		if (!p) {
			free(conn);
			tpp_unlock_rwlock(&cons_array_lock);
			tpp_log(LOG_CRIT, __func__, "Out of memory expanding connection array");
			return NULL;
		}
		conns_array = (conns_array_type_t *) p;

		/* TPP_SLOT_FREE must remain defined as 0, for this memset to work
		 * and automatically set all new slots to FREE. We do not want to
		 * loop over 100 new slots just to set them free!
		 */
		memset(&conns_array[conns_array_size], 0, (newsize - conns_array_size) * sizeof(conns_array_type_t));
		conns_array_size = newsize;
	}
	if (conns_array[tfd].slot_state != TPP_SLOT_FREE) {
		tpp_log(LOG_ERR, __func__, "Internal error - slot not free");
		free(conn);
		tpp_unlock_rwlock(&cons_array_lock);
		return NULL;
	}

	tpp_set_non_blocking(conn->sock_fd);
	tpp_set_close_on_exec(conn->sock_fd);

	if (tpp_set_keep_alive(conn->sock_fd, tpp_conf) == -1) {
		free(conn);
		tpp_unlock_rwlock(&cons_array_lock);
		return NULL;
	}

	conns_array[tfd].slot_state = TPP_SLOT_BUSY;
	conns_array[tfd].conn = conn;

	tpp_unlock_rwlock(&cons_array_lock);

	return conn;
}

/**
 * @brief
 *	Creates a new physical connection between two routers or a router and
 *	a leaf.
 *
 * @param[in] hostname - hostname to connect to
 * @param[in] delay    - Connect after delay of this much seconds
 * @param[in] ctx      - Associate the passed ctx with the connection fd
 * @param[in] tctx     - Transport thrd context of the caller
 * @param[out] ret_tfd - The fd of the connection returned
 *
 * @return  Error code
 * @retval  -1   - Failure
 * @retval   0   - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_connect_spl(char *hostname, int delay, void *ctx, int *ret_tfd, void *tctx)
{
	phy_conn_t *conn;
	int fd;
	char *host;
	int port;

	if ((host = tpp_parse_hostname(hostname, &port)) == NULL) {
		tpp_log(LOG_CRIT, __func__, "Out of memory while parsing hostname");
		free(host);
		return -1;
	}

	fd = tpp_sock_socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0) {
		tpp_log(LOG_CRIT, __func__, "socket() error, errno=%d", errno);
		free(host);
		return -1;
	}

	if (tpp_set_keep_alive(fd, tpp_conf) == -1) {
		tpp_sock_close(fd);
		free(host);
		return -1;
	}

	*ret_tfd = fd;

	conn = alloc_conn(fd);
	if (!conn) {
		tpp_sock_close(fd);
		free(host);
		return -1;
	}

	conn->conn_params = calloc(1, sizeof(conn_param_t));
	if (!conn->conn_params) {
		free(conn);
		tpp_sock_close(fd);
		free(host);
		return -1;
	}
	conn->conn_params->need_resvport = strcmp(tpp_conf->auth_config->auth_method, AUTH_RESVPORT_NAME) == 0;
	conn->conn_params->hostname = host;
	conn->conn_params->port = port;

	conn->sock_fd = fd;
	conn->net_state = TPP_CONN_INITIATING;

	tpp_transport_set_conn_ctx(fd, ctx);

	assign_to_worker(fd, delay, tctx);

	return 0;
}

/**
 * @brief
 *	Wrapper to the call to tpp_transport_connect_spl, It calls
 *	tpp_transport_connect_spl with the tctx parameter as NULL.
 *
 * @param[in] hostname - hostname to connect to
 * @param[in] delay    - Connect after delay of this much seconds
 * @param[in] ctx     - Associate the passed ctx with the connection fd
 * @param[out] ret_tfd - The fd of the connection returned
 *
 * @return  Error code
 * @retval  -1   - Failure
 * @retval   0   - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_connect(char *hostname, int delay, void *ctx, int *ret_tfd)
{
	return tpp_transport_connect_spl(hostname, delay, ctx, ret_tfd, NULL);
}

/**
 * @brief
 *	Helper function to get a transport channel pointer and
 *	slot state in an atomic fashion
 *
 * @par Functionality:
 *	Acquire a lock on the connsarray lock and return the conn pointer and
 *	the slot state
 *
 * @param[in] tfd - The transport descriptor
 * @param[out] slot_state - The state of the slot occupied by this stream
 *
 * @return - Transport channel pointer
 * @retval NULL - Bad stream index/descriptor
 * @retval !NULL - Associated stream pointer
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static phy_conn_t *
get_transport_atomic(int tfd, int *slot_state)
{
	phy_conn_t *conn = NULL;
	*slot_state = TPP_SLOT_FREE;

	if (tpp_read_lock(&cons_array_lock))
		return NULL;

	if (tfd >= 0 && tfd < conns_array_size) {
		conn = conns_array[tfd].conn;
		*slot_state = conns_array[tfd].slot_state;
	}
	tpp_unlock_rwlock(&cons_array_lock);

	return conn;
}

/**
 * @brief
 *	Lock the strmarray lock and send post data on the
 *	threads mbox. The check for the tfd being up,
 *	and the posting of data into the manager thread's mbox
 *	are done as an atomic operation, i.e., under the cons_array_lock.
 *
 * @param[in] tfd - The file descriptor of the connection
 * @param[in] cmd - The cmd to post if conn is up
 * @param[in] pkt - Data associated with the command
 *
 * @return  Error code
 * @retval  -1 - Failure (slot free, or bad tfd)
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	errno is set
 *
 * @par MT-safe: No
 *
 */
static int
tpp_post_cmd(int tfd, char cmd, tpp_packet_t *pkt)
{
	int rc;
	phy_conn_t *conn = NULL;
	thrd_data_t *td = NULL;

	errno = 0;

	if (tpp_read_lock(&cons_array_lock))
		return -1;

	if (tfd >= 0 && tfd < conns_array_size) {
		if (conns_array[tfd].conn && conns_array[tfd].slot_state == TPP_SLOT_BUSY) {
			conn = conns_array[tfd].conn;
			td = conn->td;
		}
	}

	if (!td || !conn) {
		tpp_unlock_rwlock(&cons_array_lock);
		errno = EBADF;
		return -1;
	}

	if (cmd == TPP_CMD_SEND) {
		/* data associated that needs to be sent out, put directly into target mbox */
		/* write to worker threads send pipe */
		rc = tpp_mbox_post(&conn->send_mbox, tfd, cmd, (void*) pkt, pkt->totlen);
		if (rc == -2) {
			tpp_unlock_rwlock(&cons_array_lock);
			return rc;
		}
	}

	/* write to worker threads send pipe, to wakeup thread */
	rc = tpp_mbox_post(&td->mbox, tfd, cmd, NULL, 0);
	tpp_unlock_rwlock(&cons_array_lock);

	return rc;
}

/**
 * @brief
 *	Send a wakeup packet (a packet without any data) to the active
 *	transport thread, so that it wakes up and processes any pending
 *	notifications.
 *
 * @param[in] tfd   - The file descriptor of the connection
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_wakeup_thrd(int tfd)
{
	if (tfd < 0)
		return -1;

	if (tpp_post_cmd(tfd, TPP_CMD_WAKEUP, NULL) != 0) {
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Queue data to be sent out by the IO thread. This function can take a
 *	set of data buffers and sends them out after concatenating
 *
 * @param[in] tfd   - The file descriptor of the connection
 * @param[in] chunk - Array of chunks that describes each data buffer
 * @param[in] count - Number of chunks in the array of chunks
 * @param[in] totlen  - total length of data to be sent out
 * @param[in] extra - Extra data to be associated with the data packet
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval  -2 - transport buffers full
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_vsend(int tfd, tpp_packet_t *pkt)
{
	/* compute the length in network byte order for the whole packet */
	tpp_chunk_t *first_chunk = GET_NEXT(pkt->chunks);
	void *p_ntotlen = (void *) (first_chunk->data);
	int wire_len = htonl(pkt->totlen);
	int rc;

	if (tfd < 0) {
		tpp_free_pkt(pkt);
		return -1;
	}

	TPP_DBPRT("sending total length = %d", pkt->totlen);

	/* write the total packet length as the first byte of the packet header
	 * every packet header type has a ntotlen as the exact first element
	 * The total length of all the chunks of the packet is only know at this
	 * function, when all chunks are complete, so we compute the total length
	 * and set to the ntotlen element of the packet header
	 */
	memcpy(p_ntotlen, &wire_len, sizeof(int));

	/* write to worker threads send pipe */
	rc = tpp_post_cmd(tfd, TPP_CMD_SEND, (void *) pkt);
	if (rc != 0) {
		if (rc == -1)
			tpp_log(LOG_CRIT, __func__, "Error writing to thread cmd mbox");
		else if (rc == -2)
			tpp_log(LOG_CRIT, __func__, "thread cmd mbox is full");
		tpp_free_pkt(pkt);
	}
	return rc;
}

/**
 * @brief
 *	Whether the underlying connection is from a reserved port or not
 *
 * @param[in] tfd   - The file descriptor of the connection
 *
 * @return  Error code
 * @retval  -1 - Not associated with a reserved port
 * @retval   0 - Associated with a reserved port
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_isresvport(int tfd)
{
	int slot_state;
	phy_conn_t *conn;

	conn = get_transport_atomic(tfd, &slot_state);
	if (conn == NULL || slot_state != TPP_SLOT_BUSY)
		return -1;

	if (conn->conn_params->port >= 0 && conn->conn_params->port < IPPORT_RESERVED)
		return 0;

	return -1;
}

/**
 * @brief
 *	Assign a physical connection to a thread. A new connection (to be
 *	created) or a new incoming connection is assigned to one of the
 *	existing threads using this function. Assigns connections to a thread
 *	in a round-robin fashion (based on global thrd_index)
 *
 * @param[in] tfd   - The file descriptor of the connection
 * @param[in] delay - Connect/accept this new function only after this delay
 * @param[in] td    - The thread index to which to assign the conn to
 *
 * @return	Error code
 * @retval	1	Failure
 * @retval	0	Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
assign_to_worker(int tfd, int delay, thrd_data_t *td)
{
	int slot_state;
	phy_conn_t *conn;

	conn = get_transport_atomic(tfd, &slot_state);
	if (conn == NULL || slot_state != TPP_SLOT_BUSY)
		return 1;

	if (conn->td != NULL)
		tpp_log(LOG_CRIT, __func__, "ERROR! tfd=%d conn_td=%p, conn_td_index=%d, thrd_td=%p, thrd_td_index=%d", tfd, conn->td, conn->td->thrd_index, td, td ? td->thrd_index: -1);

	if (td == NULL) {
		int iters = 0;

		if (tpp_lock(&thrd_array_lock)) {
			return 1;
		}
		/* find a thread index to assign to, since none provided */
		do {
			last_thrd++;
			if (last_thrd >= num_threads) {
				last_thrd = 0;
				iters++;
			}
		} while (thrd_pool[last_thrd]->listen_fd != -1 && iters < 2);
		conn->td = thrd_pool[last_thrd];
		tpp_unlock(&thrd_array_lock);
	} else
		conn->td = td;

	if (tpp_mbox_post(&conn->td->mbox, tfd, TPP_CMD_ASSIGN, (void *)(long) delay, 0) != 0)
		tpp_log(LOG_CRIT, __func__, "tfd=%d, Error writing to mbox", tfd);

	return 0;
}

/**
 * @brief
 *	Add (a new) or accept (incoming) a transport connection.
 *
 *	In case of creating a new connection, it binds to a reserved port if
 *	the authentication is set to priv_fd.
 *
 * @param[in] conn - The physical connection structure, to initiate or to
 *                   accept.
 *
 * @return  Error code
 * @retval  -1 - Failure
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
add_transport_conn(phy_conn_t *conn)
{
	if (conn->net_state == TPP_CONN_INITIATING) {

		int fd = conn->sock_fd;

		/* authentication */
		if (conn->conn_params->need_resvport) {
			int tryport;
			int start;
			int rc = -1;

			srand(time(NULL));
			start = (rand() % (IPPORT_RESERVED - 1)) + 1;
			tryport = start;

			while (1) {
				struct sockaddr_in serveraddr;
				/* bind this socket to a reserved port */
				serveraddr.sin_family = AF_INET;
				serveraddr.sin_addr.s_addr = INADDR_ANY;
				serveraddr.sin_port = htons(tryport);
				memset(&(serveraddr.sin_zero), '\0', sizeof(serveraddr.sin_zero));
				if ((rc = tpp_sock_bind(fd, (struct sockaddr *) &serveraddr, sizeof(serveraddr))) != -1)
					break;
				if ((errno != EADDRINUSE) && (errno != EADDRNOTAVAIL))
					break;

				--tryport;
				if (tryport <= 0)
					tryport = IPPORT_RESERVED;
				if (tryport == start)
					break;
			}
			if (rc == -1) {
				tpp_log(LOG_WARNING, NULL, "No reserved ports available");
				return (-1);
			}
		}

		conn->net_state = TPP_CONN_CONNECTING;

		conn->ev_mask = EM_OUT | EM_ERR | EM_HUP;
		TPP_DBPRT("New socket, Added EM_OUT to ev_mask, now=%x", conn->ev_mask);
		if (tpp_em_add_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask) == -1) {
			tpp_log(LOG_ERR, __func__, "Multiplexing failed");
			return -1;
		}

		if (tpp_sock_attempt_connection(conn->sock_fd, conn->conn_params->hostname, conn->conn_params->port) == -1) {
			if (errno != EINPROGRESS && errno != EWOULDBLOCK && errno != EAGAIN) {
				char *msgbuf;
#ifdef HAVE_STRERROR_R
				char buf[TPP_GEN_BUF_SZ];

				if (strerror_r(errno, buf, sizeof(buf)) == 0)
					pbs_asprintf(&msgbuf, "%s while connecting to %s:%d", buf, conn->conn_params->hostname, conn->conn_params->port);
				else
#endif
					pbs_asprintf(&msgbuf, "Error %d while connecting to %s:%d", errno, conn->conn_params->hostname, conn->conn_params->port);
				tpp_log(LOG_ERR, NULL, msgbuf);
				free(msgbuf);
				return -1;
			}
		} else {
			TPP_DBPRT("phy_con %d connected", fd);
			conn->net_state = TPP_CONN_CONNECTED;

			/* since we connected, remove EM_OUT from the list and add EM_IN */
			conn->ev_mask = EM_IN | EM_ERR | EM_HUP;
			TPP_DBPRT("Connected, Removed EM_OUT and added EM_IN to ev_mask, now=%x", conn->ev_mask);
			if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask) == -1) {
				tpp_log(LOG_CRIT, __func__, "Multiplexing failed");
				return -1;
			}
			if (the_post_connect_handler)
				the_post_connect_handler(fd, NULL, conn->ctx, conn->extra);
		}
	} else if (conn->net_state == TPP_CONN_CONNECTED) {/* accepted socket */
		/* since we connected, remove EM_OUT from the list and add EM_IN */
		conn->ev_mask = EM_IN | EM_ERR | EM_HUP;
		TPP_DBPRT("Connected, Removed EM_OUT and added EM_IN to ev_mask, now=%x", conn->ev_mask);

		/* add it to my own monitored list */
		if (tpp_em_add_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask) == -1) {
			tpp_log(LOG_ERR, __func__, "Multiplexing failed");
			return -1;
		}

		TPP_DBPRT("Phy Con %d accepted", conn->sock_fd);
	} else {
		tpp_log(LOG_CRIT, __func__, "Bad net state - internal error");
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Handle a command sent to this thread by its monitored pipe fd
 *
 * @par Functionality
 *	Commands:
 *	TPP_CMD_EXIT: The thread is being asked to exit, close all connections
 *		      and then exit this thread
 *
 *	TPP_CMD_ASSIGN: Assign new connection (incoming) or add a
 *			to-be-created connection to this thread
 *
 *	TPP_CMD_SEND: Accept data from APP thread to be sent by this thread
 *
 * @param[in] td    - The threads data pointer
 * @param[in] tfd   - The tfd associated with this command
 * @param[in] cmd   - The command to execute (listed above)
 * @param[in] data  - The data (in case of send) to be sent
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
handle_cmd(thrd_data_t *td, int tfd, int cmd, void *data)
{
	int slot_state;
	phy_conn_t *conn;
	conn_event_t *conn_ev;
	int num_cons = 0;

	conn = get_transport_atomic(tfd, &slot_state);

	if(conn && (conn->td != td))
		tpp_log(LOG_CRIT, __func__, "ERROR! tfd=%d conn_td=%p, conn_td_index=%d, thrd_td=%p, thrd_td_index=%d, cmd=%d", tfd, conn->td, conn->td->thrd_index, td, td->thrd_index, cmd);

	if (cmd == TPP_CMD_CLOSE) {
		handle_disconnect(conn);

	} else if (cmd == TPP_CMD_EXIT) {
		int i;

		for (i = 0; i < conns_array_size; i++) {
			conn = get_transport_atomic(i, &slot_state);
			if (slot_state == TPP_SLOT_BUSY && conn->td == td) {
				/* stream belongs to this thread */
				num_cons++;
				handle_disconnect(conn);
			}
		}

		tpp_mbox_destroy(&td->mbox);
		if (td->listen_fd > -1)
			tpp_sock_close(td->listen_fd);

		/* clean up the lazy conn queue */
		while ((conn_ev = tpp_deque(&td->def_act_que)))
			free(conn_ev);

		tpp_log(LOG_INFO, NULL, "Thrd exiting, had %d connections", num_cons);

		/* destory the AVL tls */
		free_avl_tls();

		pthread_exit(NULL);
		/* no execution after this */

	} else if ((cmd == TPP_CMD_ASSIGN) || (cmd == TPP_CMD_CONNECT)) {
		int delay = (int)(long) data;

		if (conn == NULL || slot_state != TPP_SLOT_BUSY) {
			tpp_log(LOG_WARNING, __func__, "Phy Con %d (cmd = %d) already deleted/closing", tfd, cmd);
			return;
		}
		if ((delay == 0) || (cmd == TPP_CMD_CONNECT)) {
			if (add_transport_conn(conn) != 0) {
				handle_disconnect(conn);
			}
		} else {
			enque_deferred_event(td, tfd, TPP_CMD_CONNECT, delay);
		}

	} else if (cmd == TPP_CMD_SEND) {
		tpp_packet_t *pkt = (tpp_packet_t *) data;

		if (conn == NULL || slot_state != TPP_SLOT_BUSY) {
			tpp_log(LOG_WARNING, __func__, "Phy Con %d (cmd = %d) already deleted/closing", tfd, cmd);
			tpp_free_pkt(pkt);
			return;
		}

		/* handle socket add calls */
		send_data(conn);

	} else if (cmd == TPP_CMD_READ) {
		add_pkt(conn);
	}
}

/**
 * @brief
 *	Return the threads index from the tls located thread data
 *
 * @return - Thread index of the calling thread
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_get_thrd_index()
{
	tpp_tls_t *tls;
	thrd_data_t *td;
	if ((tls = tpp_get_tls()) == NULL)
		return -1;

	td = (thrd_data_t *)(tpp_get_tls()->td);
	if (td == NULL)
		return -1;

	return td->thrd_index;
}

/**
 * @brief
 *	This is the IO threads "thread-function". It includes a loop of
 *	waiting for monitored piped, sockets etc, and it drives the various
 *	functionality that the IO thread does.
 *
 * @par Functionality
 *	- Creates a event monitor context
 *	- Adds the cmd socket to the event monitor set
 *	- Adds the listening socket fd (if listening thread for router) to set
 *	- Checks if any event is outstanding in event queue for this thread
 *	  and if so, dispatches them
 *	- Calls the_event_expiry_handler to find how long the next event is
 *	  places at the upper layer
 *	- Waits on em wait for the duration determined from previous step
 *	- When em_wait is woken by a event, handles that event.
 *		- Handle command sent by another thread, like
 *			- Create a new connection
 *			- Send data over a connection etc
 *			- Close a thread
 *		- Accept incoming new connections (if a listening thread)
 *		- Accept data from peer and call upper layer handler
 *		- Detect closure of socket event and call upper layer handler
 *
 * @param[in] v - The thrd_data pointer passed by the init function that created
 *		  the threads. (Basically a pointer to its own thread_data).
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void*
work(void *v)
{
	thrd_data_t *td = (thrd_data_t *) v;
	int newfd;
	int i;
	int cmd;
	void *data;
	unsigned int tfd;
	em_event_t *events;
	phy_conn_t *conn;
	int slot_state;
	struct sockaddr clientaddr;
	int new_connection = 0;
	int timeout, timeout2;
	time_t now;
	tpp_tls_t *ptr;
#ifndef WIN32
	int rc;
	sigset_t	blksigs;
#endif

	/*
	 * Get the tls for this thread and store the passed thread data
	 * as a pointer in our own tls. This is for use in functions
	 * where we cannot pass the thread data as a parameter
	 */
	ptr = tpp_get_tls();
	if (!ptr) {
		fprintf(stderr, "Out of memory getting thread specific storage\n");
		return NULL;
	}
	ptr->td = (void *) td;
	td->tpp_tls = ptr; /* store allocated area for tls into td to free at shutdown/terminate */

#ifndef WIN32
	/* block a certain set of signals that we do not care about in this IO thread
	 * A signal directed to a multi-threaded program can be delivered to any thread
	 * which has a unblocked signal mask for that signal. This could cause havoc for
	 * for signal handler which are not supposed to be called from this IO thread.
	 * (example the SIGHUP handler for scheduler). Signals like SIGALRM and hardware
	 * generated signals (like SIGBUS and SIGSEGV) are always delivered to the
	 * thread that generated it (so they are thread specific anyway).
	 */
	sigemptyset(&blksigs);
	sigaddset(&blksigs, SIGHUP);
	sigaddset(&blksigs, SIGINT);
	sigaddset(&blksigs, SIGTERM);

	if ((rc = pthread_sigmask(SIG_BLOCK, &blksigs, NULL)) != 0) {
		tpp_log(LOG_CRIT, NULL, "Failed in pthread_sigmask, errno=%d", rc);
		return NULL;
	}
#endif
	tpp_log(LOG_CRIT, NULL, "Thread ready");

	/* start processing loop */
	for (;;) {
		int nfds;

		while (1) {
			now = time(0);

			/* trigger all delayed events, and return the wait time till the next one to trigger */
			timeout = trigger_deferred_events(td, now);
			if (the_timer_handler) {
				timeout2 = the_timer_handler(now);
			} else {
				timeout2 = -1;
			}

			if (timeout2 != -1) {
				if (timeout == -1 || timeout2 < timeout)
					timeout = timeout2;
			}

			if (timeout != -1) {
				timeout = timeout * 1000; /* milliseconds */
			}

			errno = 0;
			nfds = tpp_em_wait(td->em_context, &events, timeout);
			if (nfds <= 0) {
				if (!(errno == EINTR || errno == EINPROGRESS || errno == EAGAIN || errno == 0)) {
					tpp_log(LOG_ERR, __func__, "em_wait() error, errno=%d", errno);
				}
				continue;
			} else
				break;
		} /* loop around em_wait */

		new_connection = 0;

		/* check once more if cmd_pipe has any more data */
		while (tpp_mbox_read(&td->mbox, &tfd, &cmd, &data) == 0)
			handle_cmd(td, tfd, cmd, data);

		for (i = 0; i < nfds; i++) {

			int em_fd;
			int em_ev;

			em_fd = EM_GET_FD(events, i);
			em_ev = EM_GET_EVENT(events, i);

			/**
			 * at each iteration clear the command pipe, to
			 * avoid a deadlock between threads
			 **/
			while (tpp_mbox_read(&td->mbox, &tfd, &cmd, &data) == 0)
				handle_cmd(td, tfd, cmd, data);

			if (em_fd == td->listen_fd) {
				new_connection = 1;
			} else {
				conn = get_transport_atomic(em_fd, &slot_state);
				if (conn == NULL || slot_state != TPP_SLOT_BUSY)
					continue;

				if ((em_ev & EM_HUP) || (em_ev & EM_ERR)) {
					/*
					 * platforms differ in terms of when HUP or ERR is set
					 * best is to allow read to determine whether it was
					 * really a end of file
					 */
					handle_incoming_data(conn);
				} else {

					if (em_ev & EM_IN) {
						/* handle existing connections for data or closure */
						handle_incoming_data(conn);
					}

					if (em_ev & EM_OUT) {

						if (conn->net_state == TPP_CONN_CONNECTING) {
							/* check to see if the connection really completed */
							int result;
							pbs_socklen_t result_len = sizeof(result);

							if (tpp_sock_getsockopt(conn->sock_fd, SOL_SOCKET, SO_ERROR, &result, &result_len) != 0) {
								TPP_DBPRT("phy_con %d getsockopt failed", conn->sock_fd);
								handle_disconnect(conn);
								continue;
							}
							if (result == EAGAIN || result == EINPROGRESS) {
								/* not yet connected, ignore the EM_OUT */
								continue;
							} else if (result != 0) {
								/* non-recoverable error occurred, eg, ECONNRESET, so disconnect */
								TPP_DBPRT("phy_con %d disconnected", conn->sock_fd);
								handle_disconnect(conn);
								continue;
							}

							/* connected, finally!!! */
							conn->net_state = TPP_CONN_CONNECTED;

							if (the_post_connect_handler)
								the_post_connect_handler(conn->sock_fd, NULL, conn->ctx, conn->extra);
							TPP_DBPRT("phy_con %d connected", conn->sock_fd);
						}

						/* since we connected, remove EM_OUT from the list and add EM_IN */
						conn->ev_mask = EM_IN | EM_ERR | EM_HUP;
						TPP_DBPRT("Connected, Removed EM_OUT and added EM_IN to ev_mask, now=%x", conn->ev_mask);
						if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask) == -1) {
							tpp_log(LOG_ERR, __func__, "Multiplexing failed");
							return NULL;
						}
						send_data(conn);
					}
				}
			}
		}

		if (new_connection == 1) {
			pbs_socklen_t addrlen = sizeof(clientaddr);
			if ((newfd = tpp_sock_accept(td->listen_fd, (struct sockaddr *) &clientaddr, &addrlen)) == -1) {
				tpp_log(LOG_ERR, NULL, "tpp_sock_accept() error, errno=%d", errno);
				if (errno == EMFILE) {
					/* out of files, sleep couple of seconds to avoid error coming in loop */
					sleep(2);
				}
				continue;
			}

			conn = alloc_conn(newfd);
			if (!conn) {
				tpp_sock_close(newfd);
				return NULL;
			}

			conn->net_state = TPP_CONN_CONNECTED;

			conn->conn_params = calloc(1, sizeof(conn_param_t));
			if (!conn->conn_params) {
				tpp_log(LOG_CRIT, __func__, "Out of memory allocating connection params");
				free(conn);
				tpp_sock_close(newfd);
				return NULL;
			}
			conn->conn_params->need_resvport = strcmp(tpp_conf->auth_config->auth_method, AUTH_RESVPORT_NAME) == 0;
			conn->conn_params->hostname = strdup(tpp_netaddr_sa(&clientaddr));
			conn->conn_params->port = ntohs(((struct sockaddr_in *) &clientaddr)->sin_port);

			/**
			 *  accept socket, and add socket to stream, assign stream to
			 * thread, and write to that thread control pipe
			 **/
			assign_to_worker(newfd, 0, NULL); /* time 0 means no delay */
		}
	}
	return NULL;
}

/**
 * @brief
 *	Function to close a transport layer connection.
 *
 * @param[in] tfd - The connection descriptor to be closed
 *
 * @retval 0  - Success
 * @retval -1 - Failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_close(int tfd)
{
	/* write to worker threads send pipe */
	if (tpp_post_cmd(tfd, TPP_CMD_CLOSE, NULL) != 0)
		return -1;

	return 0;
}

/**
 * @brief
 *	handle a disconnect notification by calling the upper layer
 *	close_handler. Called from the thread main loop inside work().
 *
 * @param[in] conn - The physical connection that was disconnected
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 * @return Error code
 * @retval	1	Failure
 * @retval	0	Succeess
 */
static int
handle_disconnect(phy_conn_t *conn)
{
	int error;
	short cmd;
	int tfd;
	tpp_packet_t *pkt;
	pbs_socklen_t len = sizeof(error);
	tpp_que_elem_t *n = NULL;

	if (conn == NULL || conn->net_state == TPP_CONN_DISCONNECTED)
		return 1;

	if (conn->net_state == TPP_CONN_CONNECTING || conn->net_state == TPP_CONN_CONNECTED) {
		if (tpp_em_del_fd(conn->td->em_context, conn->sock_fd) == -1) {
			tpp_log(LOG_ERR, __func__, "Multiplexing failed");
			return 1;
		}
	}
	tpp_sock_getsockopt(conn->sock_fd, SOL_SOCKET, SO_ERROR, &error, &len);

	conn->net_state = TPP_CONN_DISCONNECTED;
	conn->lasterr = error;

	if (the_close_handler)
		the_close_handler(conn->sock_fd, error, conn->ctx, conn->extra);

	conn->extra = NULL;

	if (tpp_write_lock(&cons_array_lock))
		return 1;

	/*
	 * Since we are freeing the socket connection we must
	 * empty any pending commands that were in this thread's
	 * mbox (since this thread is the connection's manager
	 *
	 */
	n = NULL;
	while (tpp_mbox_clear(&conn->td->mbox, &n, conn->sock_fd, &cmd, (void **) &pkt) == 0)
		tpp_free_pkt(pkt);

	conns_array[conn->sock_fd].slot_state = TPP_SLOT_FREE;
	conns_array[conn->sock_fd].conn = NULL;

	tpp_unlock_rwlock(&cons_array_lock);

	/* free old connection */
	tfd = conn->sock_fd;
	free_phy_conn(conn);
	tpp_sock_close(tfd);

	return 0;
}

/**
 * @brief
 *	handle incoming data using the scratch space which is part of each
 *	connection structure. Resize the scratch space if required.
 *
 *	Receive data as much as available, check if a packet can be formed, if
 *	so, then call app_pkts to form packets and send to the upper layer to
 *	be processed.
 *
 * @param[in] conn - The physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
handle_incoming_data(phy_conn_t *conn)
{
	int torecv = 0;
	int space_left;
	int offset;
	int closed;
	int pkt_len;
	char *p;
	short rc;

	while (1) {
		offset = conn->scratch.pos - conn->scratch.data;
		space_left = conn->scratch.len - offset; /* remaining space */
		if (space_left == 0) {
			/* resize buffer */
			if (conn->scratch.len == 0)
				conn->scratch.len = TPP_SCRATCHSIZE;
			else {
				conn->scratch.len += TPP_SCRATCHSIZE;
				tpp_log(LOG_INFO, __func__, "Increased scratch size for tfd=%d to %d", conn->sock_fd, conn->scratch.len);
			}
			p = realloc(conn->scratch.data, conn->scratch.len);
			if (!p) {
				tpp_log(LOG_CRIT, __func__, "Out of memory resizing scratch data");
				return;
			}
			conn->scratch.data = p;
			conn->scratch.pos = conn->scratch.data + offset;
			space_left = conn->scratch.len - offset;
		}

		if (offset > sizeof(int)) {
			pkt_len = ntohl(*((int *) conn->scratch.data));
			torecv = pkt_len - offset; /* offset amount of data already received */
			if (torecv > space_left)
				torecv = space_left;
		} else {
			/*
			 * we are starting to read a new packet now
			 * so we try to read the length part only first
			 * so we know how much more to read this is to
			 * avoid reading more than one packet, to eliminate memmoves
			 */
			torecv = sizeof(int) + sizeof(char) - offset; /* also read the type character */
			pkt_len = 0;
		}

		/* receive as much as we can */
		closed = 0;
		while (torecv > 0) {
			rc = tpp_sock_recv(conn->sock_fd, conn->scratch.pos, torecv, 0);
			if (rc == 0) {
				closed = 1; /* received close */
				break;
			}
			if (rc < 0) {
				if (errno != EWOULDBLOCK && errno != EAGAIN) {
					handle_disconnect(conn);
					return; /* error case - don't even process data */
				}
				break;
			}
			torecv -= rc;
			conn->scratch.pos += rc;
		}

		if (closed == 1) {
			handle_disconnect(conn);
			return;
		}
		if (torecv > 0) /* did not receive full data, do not try any more */
			break;

		if (add_pkt(conn) != 0)
			return;
	}
}

/**
 * @brief
 *	Add a packet to the receivers buffer or if buffer is full
 *  add a deffered action, so that it can be checked later
 *
 * @param[in] conn - The physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static short
add_pkt(phy_conn_t *conn)
{
	short rc = 0;
	short mod_rc = 0;
	int avl_len;
	int pkt_len;

	avl_len = conn->scratch.pos - conn->scratch.data;
	if (avl_len >= sizeof(int)) {
		pkt_len = ntohl(*((int *) conn->scratch.data));
		if (pkt_len < avl_len) {
			/* some data corruption has happened, or sombody trying DOS */
			tpp_log(LOG_CRIT, __func__, "tfd=%d, Critical error in protocol header, pkt_len=%d, avl_len=%d, dropping connection",conn->sock_fd, pkt_len, avl_len);
			handle_disconnect(conn);
			return -1; /* treat as bad data rejected by upper layer */
		}
		if (avl_len == pkt_len) {
			/* we got a full packet */
			if (the_pkt_handler) {
				rc = the_pkt_handler(conn->sock_fd, conn->scratch.data, pkt_len, conn->ctx, conn->extra);
				if (rc != 0) {
					if (rc == -1) {
						/* upper layer rejected data, disconnect */
						handle_disconnect(conn);
						return rc;
					} else if (rc == -2) {
						conn->ev_mask &= ~EM_IN; /* reciever buffer full, must wait, remove EM_IN */
						tpp_log(LOG_INFO, __func__, "tfd=%d, Receive buffer full, will wait", conn->sock_fd);
						enque_deferred_event(conn->td, -1, TPP_CMD_READ, 0);
						mod_rc = tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask);
					}
				} else {
					if ((conn->ev_mask & EM_IN) == 0) {
						/* packet added successfully, add EM_IN back */
						conn->ev_mask |= EM_IN;
						tpp_log(LOG_INFO, __func__, "tfd=%d, Receive buffer ok, continuing", conn->sock_fd);
						mod_rc = tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask);
					}
				}
				if (mod_rc != 0) {
					tpp_log(LOG_ERR, __func__, "Multiplexing failed");
					rc = mod_rc;
				}
			}

			if (rc == 0) {
			   /*
				* no need to memmove or coalesce the data, since we would have read
				* just enough for a packet, so, just reset pointers
				*/
				conn->scratch.pos = conn->scratch.data;
			}
		}
	}
	return rc;
}

/**
 * @brief
 *	Loop over the list of queued data and send out packet by packet
 *	Stop if sending would block.
 *
 * @param[in] conn - The physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
send_data(phy_conn_t *conn)
{
	tpp_chunk_t *p = NULL;
	tpp_packet_t *pkt = NULL;
	int rc;
	int curr_pkt_done = 0;
	int tosend;

	/*
	 * if a socket is still connecting, we will wait to send out data,
	 * even if app called close - so check this first
	 */
	if ((conn->net_state == TPP_CONN_CONNECTING) || (conn->net_state == TPP_CONN_INITIATING))
		return;

	TPP_DBPRT("send_data, EM_OUT=%d, ev_mask now=%x", (conn->ev_mask & EM_OUT), conn->ev_mask);
	while ((conn->ev_mask & EM_OUT) == 0) {
		rc = 0;
		curr_pkt_done = 0;

		pkt = conn->curr_send_pkt;
		if (!pkt) {
			/* get the next packet from send_mbox */
			if (tpp_mbox_read(&conn->send_mbox, NULL, NULL, (void **) &conn->curr_send_pkt) != 0) {
				if (!(errno == EAGAIN || errno == EWOULDBLOCK))
					tpp_log(LOG_ERR, __func__, "tpp_mbox_read failed");
				return;
			}
			pkt = conn->curr_send_pkt;
		}
		p = pkt->curr_chunk;

		/* data available, first byte, presend handler present, call handler */
		if ((p == GET_NEXT(pkt->chunks)) && (p->pos == p->data) && the_pkt_presend_handler) {
			if ((rc = the_pkt_presend_handler(conn->sock_fd, pkt, conn->ctx, conn->extra)) == 0) {
				p = pkt->curr_chunk; /* presend handler could change pkt contents */
			}
		}

		if (p && (rc == 0)) {
			tosend = p->len - (p->pos - p->data);
			while (tosend > 0) {
				rc = tpp_sock_send(conn->sock_fd, p->pos, tosend, 0);
				if (rc < 0) {
					if (errno == EWOULDBLOCK || errno == EAGAIN) {
						/* set this socket in POLLOUT */
						conn->ev_mask |= EM_OUT;
						TPP_DBPRT("EWOULDBLOCK, added EM_OUT to ev_mask, now=%x", conn->ev_mask);
						if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, conn->ev_mask)	== -1) {
							tpp_log(LOG_ERR, __func__, "Multiplexing failed");
							return;
						}
					} else {
						handle_disconnect(conn);
						return;
					}
					break;
				}
				TPP_DBPRT("tfd=%d, sending out %d bytes", conn->sock_fd, rc);
				p->pos += rc;
				tosend -= rc;
			}

			if (tosend == 0) {
				p = GET_NEXT(p->chunk_link);
				if (p)
					pkt->curr_chunk = p;
				else
					curr_pkt_done = 1;
			}
		} else
			curr_pkt_done = 1;

		if (pkt && curr_pkt_done) {
			/*
			* all data in this packet has been sent or done with.
			* delete this node and get next node in queue
			*/
			tpp_free_pkt(pkt);
			conn->curr_send_pkt = NULL;
		}
	}
}

/**
 * @brief
 *	Free a physical connection
 *
 * @param[in] conn - The physical connection
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static void
free_phy_conn(phy_conn_t *conn)
{
	tpp_que_elem_t *n = NULL;
	tpp_packet_t *pkt;
	short cmd;

	if (!conn)
		return;

	if (conn->conn_params) {
		if (conn->conn_params->hostname)
			free(conn->conn_params->hostname);
		free(conn->conn_params);
	}

	while (tpp_mbox_clear(&conn->send_mbox, &n, conn->sock_fd, &cmd, (void **) &pkt) == 0) {
		if (cmd == TPP_CMD_SEND)
			tpp_free_pkt(pkt);
	}

	tpp_mbox_destroy(&conn->send_mbox);

	free(conn->ctx);
	free(conn->scratch.data);
	free(conn);
}

/**
 * @brief
 *	Shut down this layer, send "exit" commands to all threads, and then
 *	free the thread pool.
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 * @return error code
 * @retval	1	failure
 * @retval	0	success
 */
int
tpp_transport_shutdown()
{
	int i;
	void *ret;

	tpp_log(LOG_INFO, NULL, "Shutting down TPP transport Layer");

	for (i = 0; i < num_threads; i++) {
		tpp_mbox_post(&thrd_pool[i]->mbox, 0, TPP_CMD_EXIT, NULL, 0);
	}

	for (i = 0; i < num_threads; i++) {
		if (tpp_is_valid_thrd(thrd_pool[i]->worker_thrd_id))
			pthread_join(thrd_pool[i]->worker_thrd_id, &ret);
		
		tpp_em_destroy(thrd_pool[i]->em_context);
		free(thrd_pool[i]->tpp_tls);
		free(thrd_pool[i]);
	}
	free(thrd_pool);

	for (i = 0; i < conns_array_size; i++) {
		if (conns_array[i].conn) {
			tpp_sock_close(conns_array[i].conn->sock_fd);
			free_phy_conn(conns_array[i].conn);
		}
	}

	/* free the array */
	free(conns_array);
	if (tpp_destroy_rwlock(&cons_array_lock))
		return 1;

	return 0;
}

/**
 * @brief
 *	"Terminate" this layer, no threads to be stopped, just free all memory
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_terminate()
{
	int i;

	/* Warning: Do not attempt to destroy any lock
	 * This is not required since our library is effectively
	 * not used after a fork.
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

	for (i = 0; i < num_threads; i++) {
		if (thrd_pool[i]->listen_fd > -1)
			tpp_sock_close(thrd_pool[i]->listen_fd);
	}

	/* close all open physical connections, else child carries open socket
	 * and a later close at parent is not all sides closed
	 */
	for (i = 0; i < conns_array_size; i++) {
		if (conns_array[i].conn)
			tpp_sock_close(conns_array[i].conn->sock_fd);
	}

	return 0;
}

/**
 * @brief
 *	Retrive hostname associated with given file descriptor of physical connection
 *
 * @param[in] tfd - Descriptor to the physical connection
 *
 */
const char *
tpp_transport_get_conn_hostname(int tfd)
{
	int slot_state;
	phy_conn_t *conn;
	conn = get_transport_atomic(tfd, &slot_state);
	if (conn) {
		return ((const char *)(conn->conn_params->hostname));
	}
	return NULL;
}

/**
 * @brief
 *	Function associates some extra structure with physical connection
 *
 * @param[in] tfd - Descriptor to the physical connection
 * @param[in] extra - Pointer to extra structure
 *
 */
void
tpp_transport_set_conn_extra(int tfd, void *extra)
{
	int slot_state;
	phy_conn_t *conn;
	conn = get_transport_atomic(tfd, &slot_state);
	if (conn) {
		conn->extra = extra;
	}
}
