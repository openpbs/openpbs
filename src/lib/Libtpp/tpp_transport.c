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

#include "rpp.h"
#include "tpp_common.h"
#include "tpp_platform.h"
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
	tpp_que_t lazy_conn_que;  /* The delayed connection queue on this thread */
	tpp_que_t close_conn_que;  /* The closed connection queue on this thread */
	tpp_mbox_t mbox;     /* message box for this thread */
	tpp_tls_t *tpp_tls;	/* tls data related to tpp work */
} thrd_data_t;

#ifdef NAS /* localmod 149 */
static  char tpp_instr_flag_file[_POSIX_PATH_MAX] = "/PBS/flags/tpp_instrumentation";
#endif /* localmod 149 */

static thrd_data_t **thrd_pool; /* array of threads - holds the thread pool */
static int num_threads;       /* number of threads in the thread pool */

static int is_auth_resvport = -1;
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
	int is_auth_resvport;  /* bind to resv port? */
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
	int can_send;            /* can we send data in this fd now, or would it block? */

	conn_param_t *conn_params; /* the connection params */

	unsigned long send_queue_size;  /* total bytes waiting on send queue */
	tpp_que_t send_queue;      /* queue of pkts to send */
	tpp_packet_t scratch;      /* scratch to work on incoming data */
	thrd_data_t *td;                  /* connections controller thread */

	tpp_context_t *ctx;        /* upper layers context information */

	void *extra;               /* extra data structure */
} phy_conn_t;

/* structure for holding an array of physical connection structures */
typedef struct {
	int slot_state;        /* slot is busy or free */
	phy_conn_t *conn; /* the physical connection using this slot */
} conns_array_type_t;

conns_array_type_t *conns_array = NULL; /* array of physical connections */
int conns_array_size = 0;                    /* the size of physical connection array */
pthread_mutex_t cons_array_lock;             /* mutex used to synchronize array ops */
pthread_mutex_t thrd_array_lock;             /* mutex used to synchronize thrd assignment */

/* function forward declarations */
static void *work(void *v);
static int assign_to_worker(int tfd, int delay, thrd_data_t *td);
static int handle_disconnect(phy_conn_t *conn);
static void handle_incoming_data(phy_conn_t *conn);
static void send_data(phy_conn_t *conn);
static void free_phy_conn(phy_conn_t *conn);
static void handle_cmd(thrd_data_t *td, int tfd, int cmd, void *data);
static int add_pkts(phy_conn_t *conn);
static phy_conn_t *get_transport_atomic(int tfd, int *slot_state);

/**
 * @brief
 *	Enqueue an delayed connect
 *
 * @par Functionality
 *	Used for initiating a connection after a delay.
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
enque_lazy_connect(thrd_data_t *td, int tfd, int delay)
{
	conn_event_t *conn_ev;
	tpp_que_elem_t *n;
	void *ret;

	conn_ev = malloc(sizeof(conn_event_t));
	if (!conn_ev) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory queueing a lazy connect");
		return;
	}
	conn_ev->tfd = tfd;
	conn_ev->conn_time = time(0) + delay;

	n = NULL;
	while ((n = TPP_QUE_NEXT(&td->lazy_conn_que, n))) {
		conn_event_t *p;

		p = TPP_QUE_DATA(n);

		/* sorted list, insert before node which has higher time */
		if (p && (p->conn_time >= conn_ev->conn_time))
			break;
	}
	/* insert before this position */
	if (n)
		ret = tpp_que_ins_elem(&td->lazy_conn_que, n, conn_ev, 1);
	else
		ret = tpp_enque(&td->lazy_conn_que, conn_ev);

	if (ret == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory queueing a lazy connect");
		free(conn_ev);
	}
}

/**
 * @brief
 *	Trigger connects for those whose connect time has been reached
 *
 * @param[in] td   - The thread data for the controlling thread
 * @param[in] now  - Current time to check events with
 *
 * @return Wait time for the next connection event
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
trigger_lazy_connects(thrd_data_t *td, time_t now)
{
	conn_event_t *q;
	tpp_que_elem_t *n = NULL;
	int slot_state;
	time_t wait_time = -1;

	while ((n = TPP_QUE_NEXT(&td->lazy_conn_que, n))) {
		q = TPP_QUE_DATA(n);
		if (q == NULL)
			continue;
		if (now >= q->conn_time) {
			(void) get_transport_atomic(q->tfd, &slot_state);
			if (slot_state == TPP_SLOT_BUSY)
				handle_cmd(td, q->tfd, TPP_CMD_ASSIGN, NULL);

			n = tpp_que_del_elem(&td->lazy_conn_que, n);
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

	if (tpp_lock(&cons_array_lock)) {
		return NULL;
	}
	if (tfd >= 0 && tfd < conns_array_size) {
		if (conns_array[tfd].conn && conns_array[tfd].slot_state == TPP_SLOT_BUSY)
			td = conns_array[tfd].conn->td;
	}
	tpp_unlock(&cons_array_lock);

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
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_sock_socket() error, errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
	if (tpp_sock_setsockopt(sd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(int)) == -1) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_sock_setsockopt() error, errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
		return -1;
	}
	if (tpp_sock_bind(sd, (struct sockaddr *) &serveraddr, sizeof(serveraddr)) == -1) {
		char *msgbuf;
#ifdef HAVE_STRERROR_R
		char buf[TPP_LOGBUF_SZ + 1];

		if (strerror_r(errno, buf, sizeof(buf)) == 0)
			pbs_asprintf(&msgbuf, "%s while binding to port %d", buf, port);
		else
#endif
			pbs_asprintf(&msgbuf, "Error %d while binding to port %d", errno, port);
		tpp_log_func(LOG_CRIT, NULL, msgbuf);
		fprintf(stderr, "%s", msgbuf);
		free(msgbuf);
		return -1;
	}
	if (tpp_sock_listen(sd, 1000) == -1) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_sock_listen() error, errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
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

	if (conf->node_type == TPP_LEAF_NODE || conf->node_type == TPP_LEAF_NODE_LISTEN) {
		if (conf->numthreads != 1) {
			tpp_log_func(LOG_CRIT, NULL, "Leaves should start exactly one thread");
			return -1;
		}
	} else {
		if (conf->numthreads < 2) {
			tpp_log_func(LOG_CRIT, NULL, "pbs_comms should have at least 2 threads");
			return -1;
		}
		if (conf->numthreads > 100) {
			tpp_log_func(LOG_CRIT, NULL, "pbs_comms should have <= 100 threads");
			return -1;
		}
	}

	tpp_log_func(LOG_INFO, NULL, "Initializing TPP transport Layer");
	if (tpp_init_lock(&thrd_array_lock)) {
		return -1;
	}
	if (tpp_init_lock(&cons_array_lock)) {
		return -1;
	}
	tpp_sock_layer_init();

	max_con = tpp_get_nfiles();
	if (max_con < TPP_MAXOPENFD) {
		tpp_log_func(LOG_WARNING, NULL, "Max files too low - you may want to increase it.");
		if (max_con < 100) {
			tpp_log_func(LOG_CRIT, NULL, "Max files < 100, cannot continue");
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
		tpp_log_func(LOG_CRIT, __func__, "Could not query SIGPIPEs disposition");
		return -1;
	}

	/* create num_threads worker threads */
	if ((thrd_pool = calloc(conf->numthreads, sizeof(thrd_data_t *))) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating threads");
		return -1;
	}

	for (i = 0; i < conf->numthreads; i++) {
		thrd_pool[i] = calloc(1, sizeof(thrd_data_t));
		if (thrd_pool[i] == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory creating threadpool");
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
		TPP_QUE_CLEAR(&thrd_pool[i]->lazy_conn_que);
		TPP_QUE_CLEAR(&thrd_pool[i]->close_conn_que);

		if ((thrd_pool[i]->em_context = tpp_em_init(max_con)) == NULL) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "em_init() error, errno=%d", errno);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}

		if (tpp_mbox_init(&thrd_pool[i]->mbox) != 0) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_mbox_init() error, errno=%d", errno);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}

		if (tpp_mbox_monitor(thrd_pool[i]->em_context, &thrd_pool[i]->mbox) != 0) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "em_mbox_enable_monitoing() error, errno=%d", errno);
			tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
			return -1;
		}

		thrd_pool[i]->thrd_index = i;
	}

	if (conf->node_type == TPP_ROUTER_NODE) {
		char *host;
		int port;

		if ((host = tpp_parse_hostname(conf->node_name, &port)) == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory parsing pbs_comm name");
			return -1;
		}
		free(host);

		if ((thrd_pool[0]->listen_fd = tpp_cr_server_socket(port)) == -1) {
			tpp_log_func(LOG_CRIT, __func__, "pbs_comm socket creation failed");
			return -1;
		}

		if (tpp_em_add_fd(thrd_pool[0]->em_context, thrd_pool[0]->listen_fd, EM_IN) == -1) {
			tpp_log_func(LOG_CRIT, __func__, "Multiplexing failed");
			return -1;
		}
	}

	tpp_conf = conf;
	is_auth_resvport = conf->is_auth_resvport;
	num_threads = conf->numthreads;

	for (i = 0; i < conf->numthreads; i++) {
		/* leave the write side of the command pipe to block */
		if (tpp_cr_thrd(work, &(thrd_pool[i]->worker_thrd_id), thrd_pool[i]) != 0) {
			tpp_log_func(LOG_CRIT, __func__, "Failed to create thread");
			return -1;
		}
	}
	tpp_log_func(LOG_INFO, NULL, "TPP initialization done");

	return 0;
}

/* the function pointer to the upper layer received packet handler */
int (*the_pkt_handler)(int tfd, void *data, int len, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer connection close handler */
int (*the_close_handler)(int tfd, int error, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer connection restore handler */
int (*the_post_connect_handler)(int tfd, void *data, void *ctx, void *extra) = NULL;

/* the function pointer to the upper layer pre packet send handler */
int (*the_pkt_presend_handler)(int tfd, tpp_packet_t *pkt, void *extra) = NULL;

/* the function pointer to the upper layer post packet send handler */
int (*the_pkt_postsend_handler)(int tfd, tpp_packet_t *pkt, void *extra) = NULL;

/* upper layer timer handler */
int (*the_timer_handler)(time_t now) = NULL;

/**
 * @brief
 *	Function to register the upper layer handler functions
 *
 * @param[in] pkt_presend_handler  - function ptr to presend handler
 * @param[in] pkt_postsend_handler - function ptr to postsend handler
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
tpp_transport_set_handlers(int (*pkt_presend_handler)(int phy_con, tpp_packet_t *pkt, void *extra),
	int (*pkt_postsend_handler)(int phy_con, tpp_packet_t *pkt, void *extra),
	int (*pkt_handler)(int, void *data, int len, void *, void *extra),
	int (*close_handler)(int, int, void *, void *extra),
	int (*post_connect_handler)(int sd, void *data, void *ctx, void *extra),
	int (*timer_handler)(time_t now))
{
	the_pkt_handler = pkt_handler;
	the_close_handler = close_handler;
	the_post_connect_handler = post_connect_handler;
	the_pkt_postsend_handler = pkt_postsend_handler;
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

	conn = calloc(1, sizeof(phy_conn_t));
	if (!conn) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating physical connection");
		return NULL;
	}
	conn->sock_fd = tfd;
	conn->send_queue_size = 0;
	conn->extra = NULL;
	TPP_QUE_CLEAR(&conn->send_queue);
	/* initialize the send queue to empty */

	/* set to stream array */
	if (tpp_lock(&cons_array_lock)) {
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
			tpp_unlock(&cons_array_lock);
			tpp_log_func(LOG_CRIT, __func__, "Out of memory expanding connection array");
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
		tpp_log_func(LOG_ERR, __func__, "Internal error - slot not free");
		free(conn);
		tpp_unlock(&cons_array_lock);
		return NULL;
	}

	tpp_set_non_blocking(conn->sock_fd);
	tpp_set_close_on_exec(conn->sock_fd);

	if (tpp_set_keep_alive(conn->sock_fd, tpp_conf) == -1) {
		free(conn);
		tpp_unlock(&cons_array_lock);
		return NULL;
	}

	conns_array[tfd].slot_state = TPP_SLOT_BUSY;
	conns_array[tfd].conn = conn;

	tpp_unlock(&cons_array_lock);

	return conn;
}

/**
 * @brief
 *	Creates a new physical connection between two routers or a router and
 *	a leaf.
 *
 * @param[in] hostname - hostname to connect to
 * @param[in] is_auth_resvport - bind to resv port?
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
tpp_transport_connect_spl(char *hostname, int is_auth_resvport, int delay, void *ctx, int *ret_tfd, void *tctx)
{
	phy_conn_t *conn;
	int fd;
	char *host;
	int port;

	if ((host = tpp_parse_hostname(hostname, &port)) == NULL) {
		tpp_log_func(LOG_CRIT, __func__, "Out of memory while parsing hostname");
		free(host);
		return -1;
	}

	fd = tpp_sock_socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "socket() error, errno=%d", errno);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
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
	conn->conn_params->is_auth_resvport = is_auth_resvport;
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
 *	Wrapper to the call to tpp_transport_connect_specific, It calls
 *	tpp_transport_connect_spl with the tctx parameter as NULL.
 *
 * @param[in] hostname - hostname to connect to
 * @param[in] is_auth_resvport - bind to resv port?
 * @param[in] delay    - Connect after delay of this much seconds
 * @param[in] ctx	   - Associate the passed ctx with the connection fd
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
tpp_transport_connect(char *hostname, int is_auth_resvport, int delay, void *ctx, int *ret_tfd)
{
	return tpp_transport_connect_spl(hostname, is_auth_resvport, delay, ctx, ret_tfd, NULL);
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

	if (tpp_lock(&cons_array_lock)) {
		return NULL;
	}
	if (tfd >= 0 && tfd < conns_array_size) {
		conn = conns_array[tfd].conn;
		*slot_state = conns_array[tfd].slot_state;
	}
	tpp_unlock(&cons_array_lock);

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
tpp_post_cmd(int tfd, int cmd, tpp_packet_t *pkt)
{
	thrd_data_t *td = NULL;

	errno = 0;

	if (tpp_lock(&cons_array_lock)) {
		return -1;
	}

	if (tfd >= 0 && tfd < conns_array_size) {
		if (conns_array[tfd].conn && conns_array[tfd].slot_state == TPP_SLOT_BUSY)
			td = conns_array[tfd].conn->td;
	}

	if (!td) {
		tpp_unlock(&cons_array_lock);
		errno = EBADF;
		return -1;
	}

	/* write to worker threads send pipe */
	if (tpp_mbox_post(&td->mbox, tfd, cmd, (void*) pkt) != 0) {
		tpp_unlock(&cons_array_lock);
		return -1;
	}

	tpp_unlock(&cons_array_lock);
	return 0;
}

/**
 * @brief
 *	Queue a raw (without adding header) packet to the IO thread
 *
 * @param[in] tfd - The file descriptor of the connection
 * @param[in] pkt - The raw packet (possibly one that already has a header)
 *		    (mostly used for retransmitting already formatted packets)
 *
 * @return  Error code
 * @retval  -1  - Failure
 * @retval   0  - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_send_raw(int tfd, tpp_packet_t *pkt)
{
	/* write to worker threads send pipe */
	if (tpp_post_cmd(tfd, TPP_CMD_SEND, (void*) pkt) != 0) {
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Queue data to be sent out by the IO thread
 *
 * @param[in] tfd  - The file descriptor of the connection
 * @param[in] data - The ptr to the data buffer to be sent
 * @param[in] len  - The length of the data buffer
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
tpp_transport_send(int tfd, void *data, int len)
{
	tpp_packet_t *pkt;
	int nlen;

	pkt = tpp_cr_pkt(NULL, len + sizeof(int), 1);
	if (!pkt)
		return -1;

	nlen = htonl(len);
	memcpy(pkt->data, &nlen, sizeof(int));
	memcpy(pkt->data + sizeof(int), data, len);

	/* write to worker threads send pipe */
	if (tpp_post_cmd(tfd, TPP_CMD_SEND, (void*) pkt) != 0) {
		tpp_free_pkt(pkt);
		return -1;
	}
	return 0;
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
	if (tpp_post_cmd(tfd, TPP_CMD_WAKEUP, NULL) != 0) {
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Check the amount of data queued on a outgoing connection. If the buffered
 *	(and unsent) data is greater than some limit specified per connection,
 *	then that connection is closed.
 *
 * @param[in] conn   - The connection that has to be checked
 *
 * @return  Error code
 * @retval  -1 - buffered data exceeds specified limits
 * @retval   0 - buffered data within limits
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
check_buffer_limits(phy_conn_t *conn)
{
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
 * @retval   0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
int
tpp_transport_vsend_extra(int tfd, tpp_chunk_t *chunk, int count, void *extra)
{
	tpp_packet_t *pkt;
	int i;
	int ntotlen;
	int totlen = 0;

	errno = 0;

	for (i = 0; i < count; i++)
		totlen += chunk[i].len;

	pkt = tpp_cr_pkt(NULL, totlen + sizeof(int), 1);
	if (!pkt)
		return -1;

	ntotlen = htonl(totlen);
	memcpy(pkt->pos, &ntotlen, sizeof(int));
	pkt->pos = pkt->pos + sizeof(int);

	for (i = 0; i < count; i++) {
		memcpy(pkt->pos, chunk[i].data, chunk[i].len);
		pkt->pos = pkt->pos + chunk[i].len;
	}
	pkt->len = totlen + sizeof(int);
	pkt->pos = pkt->data;
	pkt->extra_data = extra;

	/* write to worker threads send pipe */
	if (tpp_post_cmd(tfd, TPP_CMD_SEND, (void *) pkt) != 0) {
		tpp_free_pkt(pkt);
		return -1;
	}
	return 0;
}

/**
 * @brief
 *	Wrapper over tpp_transport_vsend_extra, calls tpp_transport_vsend_extra
 *	with a NULL set for the parameter extra.
 *
 * @param[in] tfd   - The file descriptor of the connection
 * @param[in] chunk - Array of chunks that describes each data buffer
 * @param[in] count - Number of chunks in the array of chunks
 * @param[in] totlen  - total length of data to be sent out
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
tpp_transport_vsend(int tfd, tpp_chunk_t *chunk, int count)
{
	return (tpp_transport_vsend_extra(tfd, chunk, count, NULL));
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

	if (conn->td != NULL) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "ERROR! tfd=%d conn_td=%p, conn_td_index=%d, thrd_td=%p, thrd_td_index=%d", tfd, conn->td, conn->td->thrd_index, td, td ? td->thrd_index: -1);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
	}

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

	if (tpp_mbox_post(&conn->td->mbox, tfd, TPP_CMD_ASSIGN, (void *)(long) delay) != 0) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tfd=%d, Error writing to mbox", tfd);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
	}
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
		if (conn->conn_params->is_auth_resvport) {
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
				tpp_log_func(LOG_WARNING, NULL, "No reserved ports available");
				return (-1);
			}
		}

		conn->net_state = TPP_CONN_CONNECTING;
		if (tpp_em_add_fd(conn->td->em_context, conn->sock_fd,
			EM_OUT | EM_ERR | EM_HUP) == -1) {
			tpp_log_func(LOG_ERR, __func__, "Multiplexing failed");
			return -1;
		}

		conn->can_send = 0;

		if (tpp_sock_attempt_connection(conn->sock_fd, conn->conn_params->hostname, conn->conn_params->port) == -1) {
			if (errno != EINPROGRESS && errno != EWOULDBLOCK && errno != EAGAIN) {
				char *msgbuf;
#ifdef HAVE_STRERROR_R
				char buf[TPP_LOGBUF_SZ + 1];

				if (strerror_r(errno, buf, sizeof(buf)) == 0)
					pbs_asprintf(&msgbuf,
						"%s while connecting to %s:%d", buf,
						conn->conn_params->hostname,
						conn->conn_params->port);
				else
#endif
					pbs_asprintf(&msgbuf,
						"Error %d while connecting to %s:%d", errno,
						conn->conn_params->hostname,
						conn->conn_params->port);
				tpp_log_func(LOG_ERR, NULL, msgbuf);
				free(msgbuf);
				return -1;
			}
		} else {
			TPP_DBPRT(("phy_con %d connected", fd));
			conn->net_state = TPP_CONN_CONNECTED;

			/* since we connected, remove EMOUT from the list */
			if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, EM_IN | EM_ERR | EM_HUP) == -1) {
				tpp_log_func(LOG_CRIT, __func__, "Multiplexing failed");
				return -1;
			}
			conn->can_send = 1;
			if (the_post_connect_handler)
				the_post_connect_handler(fd, NULL, conn->ctx, conn->extra);
		}
	} else if (conn->net_state == TPP_CONN_CONNECTED) {/* accepted socket */

		/* add it to my own monitored list */
		if (tpp_em_add_fd(conn->td->em_context, conn->sock_fd, EM_IN | EM_ERR | EM_HUP) == -1) {
			tpp_log_func(LOG_ERR, __func__, "Multiplexing failed");
			return -1;
		}
		conn->can_send = 1;

		TPP_DBPRT(("Phy Con %d accepted", conn->sock_fd));
	} else {
		tpp_log_func(LOG_CRIT, __func__, "Bad net state - internal error");
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

	if(conn && (conn->td != td)) {
		sprintf(tpp_get_logbuf(), "ERROR! tfd=%d conn_td=%p, conn_td_index=%d, thrd_td=%p, thrd_td_index=%d, cmd=%d", tfd, conn->td, conn->td->thrd_index, td, td->thrd_index, cmd);
		tpp_log_func(LOG_CRIT, __func__, tpp_get_logbuf());
	}

	if (cmd == TPP_CMD_CLOSE) {
		handle_disconnect(conn);
	} else if (cmd == TPP_CMD_EXIT) {
		int i;
		tpp_tls_t *p;

		for (i = 0; i < conns_array_size; i++) {
			conn = get_transport_atomic(i, &slot_state);
			if (slot_state == TPP_SLOT_BUSY && conn->td == td) {
				/* stream belongs to this thread */
				num_cons++;
				handle_disconnect(conn);
			}
		}

		tpp_mbox_destroy(&td->mbox, 1);
		tpp_em_destroy(td->em_context);
		if (td->listen_fd > -1)
			tpp_sock_close(td->listen_fd);

		/* clean up the lazy conn queue */
		while ((conn_ev = tpp_deque(&td->lazy_conn_que))) {
			free(conn_ev);
		}

		/* clean up the close queue and piled up send data */
		while ((conn = tpp_deque(&td->close_conn_que))) {
			tpp_sock_close(conn->sock_fd);
			free_phy_conn(conn);
		}

		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Thrd exiting, had %d connections", num_cons);
		tpp_log_func(LOG_INFO, NULL, tpp_get_logbuf());

		/* clean up any tls memory, just for valgrind's sake */
		if ((p = tpp_get_tls())) {
			free(p->log_data);
			free(p->avl_data);
			free(p);
			td->tpp_tls = NULL;
		}

		pthread_exit(NULL);
		/* no execution after this */

	} else if (cmd == TPP_CMD_ASSIGN) {
		int delay = (int)(long) data;

		if (conn == NULL || slot_state != TPP_SLOT_BUSY) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Phy Con %d (cmd = %d) already deleted/closing", tfd, cmd);
			tpp_log_func(LOG_WARNING, __func__, tpp_get_logbuf());
			return;
		}
		if (delay == 0) {
			if (add_transport_conn(conn) != 0) {
				handle_disconnect(conn);
			}
		} else {
			enque_lazy_connect(td, tfd, delay);
		}
	} else if (cmd == TPP_CMD_SEND) {
		tpp_packet_t *pkt = (tpp_packet_t *) data;

		if (conn == NULL || slot_state != TPP_SLOT_BUSY) {
			snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Phy Con %d (cmd = %d) already deleted/closing", tfd, cmd);
			tpp_log_func(LOG_WARNING, __func__, tpp_get_logbuf());
			tpp_free_pkt(pkt);
			return;
		}
		if (tpp_enque(&conn->send_queue, pkt) == NULL) {
			tpp_log_func(LOG_CRIT, __func__, "Out of memory enqueing to send queue");
			return;
		}
		conn->send_queue_size += pkt->len;

		/* handle socket add calls */
		send_data(conn);
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
		sprintf(tpp_get_logbuf(), "Failed in pthread_sigmask, errno=%d", rc);
		tpp_log_func(LOG_CRIT, NULL, "Failed in pthread_sigmask");
		return NULL;
	}
#endif
	tpp_log_func(LOG_CRIT, NULL, "Thread ready");

	/* store the log and avl tls data so we can free later */
	td->tpp_tls->log_data = log_get_tls_data();
	td->tpp_tls->avl_data = get_avl_tls();

	/* start processing loop */
	for (;;) {
		int nfds;

		while (1) {
			now = time(0);

			/* trigger all delayed connects, and return the wait time till the next one to trigger */
			timeout = trigger_lazy_connects(td, now);
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
					snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "em_wait() error, errno=%d", errno);
					tpp_log_func(LOG_ERR, __func__, tpp_get_logbuf());
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
						/* set can_send_now flag on stream */

						if (conn->net_state == TPP_CONN_CONNECTING) {
							/* check to see if the connection really completed */
							int result;
							pbs_socklen_t result_len = sizeof(result);

							if (tpp_sock_getsockopt(conn->sock_fd, SOL_SOCKET, SO_ERROR, &result, &result_len) != 0) {
								TPP_DBPRT(("phy_con %d getsockopt failed", conn->sock_fd));
								handle_disconnect(conn);
								continue;
							}
							if (result == EAGAIN || result == EINPROGRESS) {
								/* not yet connected, ignore the EM_OUT */
								continue;
							} else if (result != 0) {
								/* non-recoverable error occurred, eg, ECONNRESET, so disconnect */
								TPP_DBPRT(("phy_con %d disconnected", conn->sock_fd));
								handle_disconnect(conn);
								continue;
							}

							/* connected, finally!!! */
							conn->net_state = TPP_CONN_CONNECTED;

							if (the_post_connect_handler)
								the_post_connect_handler(conn->sock_fd, NULL, conn->ctx, conn->extra);
							TPP_DBPRT(("phy_con %d connected", conn->sock_fd));
						}

						/**
						 * since we can write data now remove
						 * POLLOUT from list of events, else we will
						 * have a infinite loop from em_wait
						 **/
						if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd, EM_IN | EM_HUP | EM_ERR) == -1) {
							tpp_log_func(LOG_ERR, __func__, "Multiplexing failed");
							return NULL;
						}
						conn->can_send = 1;
						send_data(conn);
					}
				}
			}
		}

		if (new_connection == 1) {
			pbs_socklen_t addrlen = sizeof(clientaddr);
			if ((newfd = tpp_sock_accept(td->listen_fd, (struct sockaddr *) &clientaddr, &addrlen)) == -1) {
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "tpp_sock_accept() error, errno=%d", errno);
				tpp_log_func(LOG_ERR, NULL, tpp_get_logbuf());
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
				tpp_log_func(LOG_CRIT, __func__, "Out of memory allocating connection params");
				free(conn);
				tpp_sock_close(newfd);
				return NULL;
			}
			conn->conn_params->is_auth_resvport = is_auth_resvport;
			conn->conn_params->hostname = strdup(tpp_netaddr_sa(&clientaddr));
			conn->conn_params->port = ntohs(((struct sockaddr_in *) &clientaddr)->sin_port);

			/**
			 *  accept socket, and add socket to stream, assign stream to
			 * thread, and write to that thread control pipe
			 **/
			assign_to_worker(newfd, 0, NULL); /* time 0 means no delay */
		}

		/* now actually delete and close fd's that got the close
		 * we do this at the end of the event loop so that we
		 * do not advertently free things but a later event in the
		 * array triggers another close, possibly closing another
		 * fd
		 */
		while ((conn = tpp_deque(&td->close_conn_que))) {
			tpp_sock_close(conn->sock_fd);
			free_phy_conn(conn);
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
	int cmd;
	void *data;
	pbs_socklen_t len = sizeof(error);
	tpp_que_elem_t *n;

	if (conn == NULL || conn->net_state == TPP_CONN_DISCONNECTED)
		return 1;

	if (conn->net_state == TPP_CONN_CONNECTING || conn->net_state == TPP_CONN_CONNECTED) {
		if (tpp_em_del_fd(conn->td->em_context, conn->sock_fd) == -1) {
			tpp_log_func(LOG_ERR, __func__, "Multiplexing failed");
			return 1;
		}
	}
	tpp_sock_getsockopt(conn->sock_fd, SOL_SOCKET, SO_ERROR, &error, &len);

	conn->net_state = TPP_CONN_DISCONNECTED;
	conn->lasterr = error;
	conn->can_send = 0;

	if (the_close_handler)
		the_close_handler(conn->sock_fd, error, conn->ctx, conn->extra);

	conn->extra = NULL;

	if (tpp_lock(&cons_array_lock)) {
		return 1;
	}

	/*
	 * Since we are freeing the socket connection we must
	 * empty any pending commands that were in this thread's
	 * mbox (since this thread is the connection's manager.
	 * Some of these pending commands are "send" data, and
	 * this is the only copy we have since packet gets shelved
	 * only in the_pkt_postsend_handler.
	 * Simulate a successful data-send by allowing the packets to
	 * flow through the_call back functions the_pkt_presend_handler
	 * and the_pkt_postsend_handler. This is similar to us having
	 * just sent out the packets but they failed in transit.
	 */
	n = NULL;
	while (tpp_mbox_clear(&conn->td->mbox, &n, conn->sock_fd, &cmd, &data) == 0) {
		if (cmd == TPP_CMD_SEND) {
			int freed = 0;
			if (the_pkt_presend_handler) {
				if (the_pkt_presend_handler(conn->sock_fd, data, conn->extra) == 0) {
					if (the_pkt_postsend_handler) {
						the_pkt_postsend_handler(conn->sock_fd, data, conn->extra);
						freed = 1;
					}
				} else
					freed = 1;
			}
			if (!freed)
				tpp_free_pkt(data);
		}
	}

	conns_array[conn->sock_fd].slot_state = TPP_SLOT_FREE;
	conns_array[conn->sock_fd].conn = NULL;

	tpp_unlock(&cons_array_lock);

	/* now enque the connection structure to a queue to be
	 * actually deleted at the end of the event loop for
	 * this thread (fd will also be closed there)
	 */
	if (tpp_enque(&conn->td->close_conn_que, conn) == NULL)
		tpp_log_func(LOG_CRIT, __func__, "Out of memory queueing close connection");

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
	int rc;
	int torecv = 0;

	while (1) {
		int space_left;
		int offset;
		int closed;
		int amt;

		offset = conn->scratch.pos - conn->scratch.data;
		space_left = conn->scratch.len - offset; /* remaining space */
		if (space_left == 0) {
			/* resize buffer */
			if (conn->scratch.len == 0)
				conn->scratch.len = TPP_SCRATCHSIZE;
			else {
				conn->scratch.len += TPP_SCRATCHSIZE;
				snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
						"Increased scratch size for tfd=%d to %d", conn->sock_fd, conn->scratch.len);
				tpp_log_func(LOG_INFO, __func__, tpp_get_logbuf());
			}
			conn->scratch.data = realloc(conn->scratch.data, conn->scratch.len);
			if (conn->scratch.data == NULL) {
				tpp_log_func(LOG_CRIT, __func__, "Out of memory resizing scratch data");
				return;
			}
			conn->scratch.pos = conn->scratch.data + offset;
			torecv = conn->scratch.len - (conn->scratch.pos - conn->scratch.data);
		} else
			torecv = space_left;

		/*
		 * do not receive any more than TPP_SCRATCHSIZE data
		 * because that can cause add_pkts to do a lot of
		 * memmove() unnecessarily. If there is more data
		 * we will circle right back from epoll() anyway
		 */
		if (torecv > TPP_SCRATCHSIZE)
			torecv = TPP_SCRATCHSIZE;

		/* receive as much as we can */
		closed = 0;
		amt = 0;
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
			amt += rc;
			conn->scratch.pos += rc;
		}
		rc = add_pkts(conn);
		if (rc == -1) {
			/* a disconnect had happened in the flow, quit this routine */
			return;
		}

		if (closed == 1) {
			handle_disconnect(conn);
			return;
		}
		if (torecv > 0) /* did not receive full data, do not try any more */
			break;
	}
}

/**
 * @brief
 *	Carve packets out of the data received and send any complete packet to
 *	the application by calling the upper layers "the_pkt_handler".
 *
 * @param[in] conn - The physical connection
 *
 * @retval Error code
 * @return -1 - Error
 * @return  0 - Success
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: No
 *
 */
static int
add_pkts(phy_conn_t *conn)
{
	char *pkt_start;
	int avl_len;
	int rc = 0;
	int tfd = conn->sock_fd;
	int slot_state;
	int count = 0;

	int recv_len = conn->scratch.pos - conn->scratch.data;
	pkt_start = conn->scratch.data;
	avl_len = recv_len;

	while (avl_len >= (sizeof(int) + sizeof(char))) {
		int pkt_len;
		int data_len;
		char *data;

		/*  We have enough data now to validate the header */
		if (tpp_validate_hdr(tfd, pkt_start) != 0) {
			handle_disconnect(conn);
			return -1;
		}

		data_len = ntohl(*((int *) pkt_start));
		pkt_len = data_len + sizeof(int);
		if (avl_len < pkt_len)
			break;

		data = pkt_start + sizeof(int);
		if (the_pkt_handler) {
			if ((rc = the_pkt_handler(conn->sock_fd, data, data_len, conn->ctx, conn->extra)) != 0) {
				/* upper layer rejected data, disconnect */
				handle_disconnect(conn);
				return -1;
			}

			conn = get_transport_atomic(tfd, &slot_state);
			if (slot_state != TPP_SLOT_BUSY)
				return -1;
		}

		count++;
		/* coalesce before next packet to maintain alignment */
		avl_len = avl_len - pkt_len;
		memmove(conn->scratch.data, conn->scratch.data + pkt_len, (size_t)avl_len); /* area OVERLAP - use memmove */
		conn->scratch.pos = conn->scratch.data + avl_len;
	}

	if (count > 50) {
		snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ, "Received many small packets(%d)", count);
		tpp_log_func(LOG_INFO, __func__, tpp_get_logbuf());
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
	tpp_packet_t *p = NULL;
	int rc;
	int can_send_more;
	tpp_que_elem_t *n;
#ifdef NAS /* localmod 149 */
	time_t curr;
	int rc_iflag;
#endif /* localmod 149 */


	/*
	 * if a socket is still connecting, we will wait to send out data,
	 * even if app called close - so check this first
	 */
	if (conn->net_state == TPP_CONN_CONNECTING || conn->net_state == TPP_CONN_INITIATING)
		return;

	n = TPP_QUE_HEAD(&conn->send_queue);
	p = TPP_QUE_DATA(n);

	if (conn->can_send == 0)
		return;

	can_send_more = 1;

	while (p && can_send_more) {
		int tosend;

		tosend = p->len - (p->pos - p->data);
		if (p->pos == p->data) {
			if (the_pkt_presend_handler) {
				if (the_pkt_presend_handler(conn->sock_fd, p, conn->extra) != 0) {
					/* handler asked not to send data, skip packet */
					conn->send_queue_size -= tosend;
					(void) tpp_que_del_elem(&conn->send_queue, n);
					n = TPP_QUE_HEAD(&conn->send_queue);
					p = TPP_QUE_DATA(n);
					continue;
				}
				/* the_pkt_presend_handler could change the pkt size*/
				tosend = p->len;
			}
		}

		while (tosend > 0) {
			rc = tpp_sock_send(conn->sock_fd, p->pos, tosend, 0);
#ifdef NAS /* localmod 149 */
			if (rc > 0) {
				curr = time(0);

				conn->td->nas_kb_sent_A += ((double) rc) / 1024.0;
				conn->td->nas_kb_sent_B += ((double) rc) / 1024.0;
				conn->td->nas_kb_sent_C += ((double) rc) / 1024.0;

				if (tosend > TPP_SCRATCHSIZE) {
					conn->td->nas_num_lrg_sends_A++;
					conn->td->nas_lrg_send_sum_kb_A += ((double) tosend) / 1024.0;

					if (rc != tosend) {
						conn->td->nas_num_qual_lrg_sends_A++;
					}

					if (tosend > conn->td->nas_max_bytes_lrg_send_A) {
						conn->td->nas_max_bytes_lrg_send_A = tosend;
					}

					if (tosend < conn->td->nas_min_bytes_lrg_send_A) {
						conn->td->nas_min_bytes_lrg_send_A = tosend;
					}



					conn->td->nas_num_lrg_sends_B++;
					conn->td->nas_lrg_send_sum_kb_B += ((double) tosend) / 1024.0;

					if (rc != tosend) {
						conn->td->nas_num_qual_lrg_sends_B++;
					}

					if (tosend > conn->td->nas_max_bytes_lrg_send_B) {
						conn->td->nas_max_bytes_lrg_send_B = tosend;
					}

					if (tosend < conn->td->nas_min_bytes_lrg_send_B) {
						conn->td->nas_min_bytes_lrg_send_B = tosend;
					}



					conn->td->nas_num_lrg_sends_C++;
					conn->td->nas_lrg_send_sum_kb_C += ((double) tosend) / 1024.0;

					if (rc != tosend) {
						conn->td->nas_num_qual_lrg_sends_C++;
					}

					if (tosend > conn->td->nas_max_bytes_lrg_send_C) {
						conn->td->nas_max_bytes_lrg_send_C = tosend;
					}

					if (tosend < conn->td->nas_min_bytes_lrg_send_C) {
						conn->td->nas_min_bytes_lrg_send_C = tosend;
					}
				}

				if (curr > (conn->td->nas_last_time_A + conn->td->NAS_TPP_LOG_PERIOD_A)) {
					rc_iflag = access(tpp_instr_flag_file, F_OK);
					if (rc_iflag != 0) {
						conn->td->nas_tpp_log_enabled = 0;
					} else {
						conn->td->nas_tpp_log_enabled = 1;
					}

					if (conn->td->nas_tpp_log_enabled) {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
							 "tpp_instr period_A %d last %d secs (mb=%.3f, mb/min=%.3f) lrg send over %d (sends=%d, qualified=%d, minbytes=%d, maxbytes=%d, avgkb=%.1f)",
							 conn->td->NAS_TPP_LOG_PERIOD_A,
							 (int) (curr - conn->td->nas_last_time_A),
							 conn->td->nas_kb_sent_A / 1024.0,
							 (conn->td->nas_kb_sent_A / 1024.0) / (((double) (curr - conn->td->nas_last_time_A)) / 60.0),
							 TPP_SCRATCHSIZE,
							 conn->td->nas_num_lrg_sends_A,
							 conn->td->nas_num_qual_lrg_sends_A,
							 conn->td->nas_num_lrg_sends_A > 0 ? conn->td->nas_min_bytes_lrg_send_A : 0,
							 conn->td->nas_max_bytes_lrg_send_A,
							 conn->td->nas_num_lrg_sends_A > 0 ? conn->td->nas_lrg_send_sum_kb_A / ((double) conn->td->nas_num_lrg_sends_A) : 0.0);
						tpp_log_func(LOG_ERR, __func__, tpp_get_logbuf());
					}

					conn->td->nas_last_time_A = curr;
					conn->td->nas_kb_sent_A = 0.0;
					conn->td->nas_num_lrg_sends_A = 0;
					conn->td->nas_num_qual_lrg_sends_A = 0;
					conn->td->nas_max_bytes_lrg_send_A = 0;
					conn->td->nas_min_bytes_lrg_send_A = INT_MAX - 1;
					conn->td->nas_lrg_send_sum_kb_A = 0.0;
				}

				if (curr > (conn->td->nas_last_time_B + conn->td->NAS_TPP_LOG_PERIOD_B)) {
					if (conn->td->nas_tpp_log_enabled) {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
							 "tpp_instr period_B %d last %d secs (mb=%.3f, mb/min=%.3f) lrg send over %d (sends=%d, qualified=%d, minbytes=%d, maxbytes=%d, avgkb=%.1f)",
							 conn->td->NAS_TPP_LOG_PERIOD_B,
							 (int) (curr - conn->td->nas_last_time_B),
							 conn->td->nas_kb_sent_B / 1024.0,
							 (conn->td->nas_kb_sent_B / 1024.0) / (((double) (curr - conn->td->nas_last_time_B)) / 60.0),
							 TPP_SCRATCHSIZE,
							 conn->td->nas_num_lrg_sends_B,
							 conn->td->nas_num_qual_lrg_sends_B,
							 conn->td->nas_num_lrg_sends_B > 0 ? conn->td->nas_min_bytes_lrg_send_B : 0,
							 conn->td->nas_max_bytes_lrg_send_B,
							 conn->td->nas_num_lrg_sends_B > 0 ? conn->td->nas_lrg_send_sum_kb_B / ((double) conn->td->nas_num_lrg_sends_B) : 0.0);
						tpp_log_func(LOG_ERR, __func__, tpp_get_logbuf());
					}

					conn->td->nas_last_time_B = curr;
					conn->td->nas_kb_sent_B = 0.0;
					conn->td->nas_num_lrg_sends_B = 0;
					conn->td->nas_num_qual_lrg_sends_B = 0;
					conn->td->nas_max_bytes_lrg_send_B = 0;
					conn->td->nas_min_bytes_lrg_send_B = INT_MAX - 1;
					conn->td->nas_lrg_send_sum_kb_B = 0.0;
				}

				if (curr > (conn->td->nas_last_time_C + conn->td->NAS_TPP_LOG_PERIOD_C)) {
					if (conn->td->nas_tpp_log_enabled) {
						snprintf(tpp_get_logbuf(), TPP_LOGBUF_SZ,
							 "tpp_instr period_C %d last %d secs (mb=%.3f, mb/min=%.3f) lrg send over %d (sends=%d, qualified=%d, minbytes=%d, maxbytes=%d, avgkb=%.1f)",
							conn->td->NAS_TPP_LOG_PERIOD_C,
							(int) (curr - conn->td->nas_last_time_C),
							conn->td->nas_kb_sent_C / 1024.0,
							(conn->td->nas_kb_sent_C / 1024.0) / (((double) (
							curr - conn->td->nas_last_time_C)) / 60.0),
							TPP_SCRATCHSIZE,
							conn->td->nas_num_lrg_sends_C,
							conn->td->nas_num_qual_lrg_sends_C,
							conn->td->nas_num_lrg_sends_C > 0 ? conn->td->nas_min_bytes_lrg_send_C : 0,
							conn->td->nas_max_bytes_lrg_send_C,
							conn->td->nas_num_lrg_sends_C > 0 ? conn->td->nas_lrg_send_sum_kb_C / ((double) conn->td->nas_num_lrg_sends_C) : 0.0);
						tpp_log_func(LOG_ERR, __func__, tpp_get_logbuf());
					}

					conn->td->nas_last_time_C = curr;
					conn->td->nas_kb_sent_C = 0.0;
					conn->td->nas_num_lrg_sends_C = 0;
					conn->td->nas_num_qual_lrg_sends_C = 0;
					conn->td->nas_max_bytes_lrg_send_C = 0;
					conn->td->nas_min_bytes_lrg_send_C = INT_MAX - 1;
					conn->td->nas_lrg_send_sum_kb_C = 0.0;
				}
			}
#endif /* localmod 149 */

			if (rc < 0) {
				if (errno == EWOULDBLOCK || errno == EAGAIN) {
					/* set this socket in POLLOUT */
					if (tpp_em_mod_fd(conn->td->em_context, conn->sock_fd,
						EM_IN | EM_OUT | EM_HUP | EM_ERR)	== -1) {
						tpp_log_func(LOG_ERR, __func__, "Multiplexing failed");
						return;
					}

					/* set to cannot send data any more */
					conn->can_send = 0;
				} else {
					handle_disconnect(conn);
					return;
				}
				can_send_more = 0;
				break;
			}
			TPP_DBPRT(("tfd=%d, sending out %d bytes", conn->sock_fd, rc));
			p->pos += rc;
			tosend -= rc;
		}

		if (tosend == 0) {
			conn->send_queue_size -= p->len;

			if (the_pkt_postsend_handler)
				the_pkt_postsend_handler(conn->sock_fd, p, conn->extra);
			else {
				tpp_free_pkt(p);
			}

			/*
			 * all data in this packet has been sent or done with.
			 * delete this node and get next node in queue
			 */
			(void)tpp_que_del_elem(&conn->send_queue, n);
			n = TPP_QUE_HEAD(&conn->send_queue);
			p = TPP_QUE_DATA(n);
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
	tpp_packet_t *p = NULL;

	if (!conn)
		return;

	if (conn->conn_params) {
		if (conn->conn_params->hostname)
			free(conn->conn_params->hostname);
		free(conn->conn_params);
	}

	while ((p = tpp_deque(&conn->send_queue))) {
		tpp_free_pkt(p);
	}

	free(conn->ctx);
	free(conn->scratch.data);
	free(conn->scratch.extra_data);
	free(conn);
}

/*
 * Dummy log function used when terminate is called
 * We cannot log anything after fork even if tpp_dummy_logfunc
 * is called accidentally, so set tpp_log_func to this
 * dummy function
 */
void
tpp_dummy_logfunc(int level, const char *id, char *mess)
{
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

	tpp_log_func(LOG_INFO, NULL, "Shutting down TPP transport Layer");

	for (i = 0; i < num_threads; i++) {
		tpp_mbox_post(&thrd_pool[i]->mbox, 0, TPP_CMD_EXIT, NULL);
	}

	for (i = 0; i < num_threads; i++) {
		if (tpp_is_valid_thrd(thrd_pool[i]->worker_thrd_id))
			pthread_join(thrd_pool[i]->worker_thrd_id, &ret);
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
	if (tpp_destroy_lock(&cons_array_lock)) {
		return 1;
	}
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
	 * not used after a fork. The function tpp_mbox_destroy
	 * calls pthread_mutex_destroy, so don't call them.
	 * Also never log anything from a terminate handler
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
	tpp_log_func = tpp_dummy_logfunc;

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
