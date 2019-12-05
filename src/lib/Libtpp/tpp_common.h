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

#ifndef	__TPP_COMMON_H
#define __TPP_COMMON_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <pbs_config.h>

#include <sys/time.h>
#include <limits.h>
#include <time.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <errno.h>

#include "avltree.h"
#include "log.h"

#if defined (PBS_HAVE_DEVPOLL)
#define PBS_USE_DEVPOLL
#elif defined (PBS_HAVE_EPOLL)
#define PBS_USE_EPOLL
#elif defined (PBS_HAVE_POLLSET)
#define  PBS_USE_POLLSET
#elif defined (HAVE_POLL)
#define PBS_USE_POLL
#elif defined (HAVE_SELECT)
#define PBS_USE_SELECT
#endif

#if defined (PBS_USE_EPOLL)

#include <sys/epoll.h>

#elif defined (PBS_USE_POLL)

#include <poll.h>

#elif defined (PBS_USE_SELECT)

#if defined(FD_SET_IN_SYS_SELECT_H)
#include <sys/select.h>
#endif

#elif defined (PBS_USE_DEVPOLL)

#include <sys/devpoll.h>

#elif defined (PBS_USE_POLLSET)

#include <sys/poll.h>
#include <sys/pollset.h>
#include <fcntl.h>

#endif

#define MAX_SEQ_NUMBER          (UINT_MAX - 10)
#define UNINITIALIZED_INT       (MAX_SEQ_NUMBER + 1)
#define TPP_LOGBUF_SZ        	1024
#define TPP_MAXADDRLEN          (INET6_ADDRSTRLEN + 10)

/* some built in timing control defines to retry connections to routers */
#define TPP_CONNNECT_RETRY_MIN	2
#define TPP_CONNECT_RETRY_INC	2
#define TPP_CONNECT_RETRY_MAX	10
#define TPP_THROTTLE_RETRY      5 /* retry time after throttling a packet */


/* defines for the TPP address families
 * we don't use the AF_INET etc, since their values could (though mostly does not)
 * differ between OS flavors, so choosing something that fits in a char
 * and also is same for TPP libraries on all OS flavors
 */
#define TPP_ADDR_FAMILY_IPV4 	0
#define TPP_ADDR_FAMILY_IPV6 	1
#define TPP_ADDR_FAMILY_UNSPEC 	2


/*
 * Structure to hold an Address (ipv4 or ipv6)
 */
typedef struct {
	int ip[4]; /* can hold ipv6 as well */
	short port;  /* hold short port, keep as int for alignment */
	char family; /* Ipv4 or IPV6 etc */
} tpp_addr_t;

/*
 * Packet structure used at various places to hold a data and the
 * current position to which data has been consumed or processed
 */
typedef struct {
	char *data;	/* pointer to the data buffer */
	int len;	/* length of the data buffer */
	char *pos;	/* current position - till which data is consumed */
	void *extra_data;	/* any additional data */
	int ref_count;	/* number of accessors */
} tpp_packet_t;

/*
 * Structure used to describe chunks of data to be sent to a gather-and-send
 * api "tpp_transport_vsend". Each chunk has this structure.
 */
typedef struct {
	void *data;	/* pointer to data */
	int len;	/* length of data */
} tpp_chunk_t;

/*
 * The authenticate packet header structure
 */
typedef struct {
	unsigned char type;
	char auth_type[MAXAUTHNAME + 1];
} tpp_auth_pkt_hdr_t;
/* the authentication data follows this packet */

/*
 * The Join packet header structure
 */
typedef struct {
	unsigned char type;         /* type packet, JOIN, LEAVE etc */
	unsigned char node_type;    /* node type - leaf or router */
	unsigned char hop;          /* hop count */
	unsigned char index;        /* in case of leaves, primary connection or backup */
	unsigned char num_addrs;    /* number of addresses of source joining, max 128 */
} tpp_join_pkt_hdr_t;
/* a bunch of tpp_addr structs follow this packet */

/*
 * The Leave packet header structure
 */
typedef struct {
	unsigned char type;      /* type packet, JOIN, LEAVE etc */
	unsigned char hop;
	unsigned char ecode;
	unsigned char num_addrs; /* number of addresses of source leaving, max 128 */
} tpp_leave_pkt_hdr_t;
/* a bunch of tpp_addr structs follow this packet */

/*
 * The control packet header structure, MSG, NOROUTE etc
 */
typedef struct {
	unsigned char type;
	unsigned char code;        /* NOROUTE, UPDATE, ERROR */
	unsigned char error_num;   /* error_num in case of NOROUTE, ERRORs */
	unsigned int  src_sd;      /* source sd in case of NO ROUTE */
	tpp_addr_t src_addr;       /* src host address */
	tpp_addr_t dest_addr;      /* destination host dest host address */
} tpp_ctl_pkt_hdr_t;

/*
 * The data packet header structure
 */
typedef struct {
	unsigned char type;        /* type of the packet - TPP_DATA, JOIN etc */
	unsigned char dup;         /* Is this a duplicate packet? */

	unsigned int src_magic;    /* magic id of source stream */
	unsigned int cmprsd_len;   /* length of compressed data, 0 if not compressed */

	unsigned int src_sd;       /* source stream descriptor */
	unsigned int dest_sd;      /* destination stream descriptor */

	unsigned int seq_no;       /* packet sequence number */
	unsigned int ack_seq;      /* sequence number of packet being ackd */

	unsigned int totlen;       /* total pkt len (in case of fragmented pkts)*/

	tpp_addr_t src_addr;  /* src host address */
	tpp_addr_t dest_addr; /* dest host address */
} tpp_data_pkt_hdr_t;

/*
 * The multicast packet header structure
 */
typedef struct {
	unsigned char type;       /* type of packet - TPP_MCAST_DATA */
	unsigned char hop;        /* hop count */
	unsigned int num_streams; /* number of member streams */
	unsigned int info_len;    /* total length of info */
	unsigned int info_cmprsd_len; /* compressed length of info */
	unsigned int totlen;          /* total pkt len (in case of fragmented pkts) */
	unsigned int data_cmprsd_len; /* compressed len */
	tpp_addr_t src_addr;     /* source host address */
} tpp_mcast_pkt_hdr_t;

/*
 * Structure describing information about each member stream.
 * The overall packet includes a mcast header and multiple member stream
 * info (each of one member stream)
 */
typedef struct {
	unsigned int src_sd;	/* source descriptor of member stream */
	unsigned int src_magic; /* magic id of source stream */
	unsigned int dest_sd;	/* destination descriptor of member stream */
	unsigned int seq_no;	/* sequence number of member stream */
	tpp_addr_t dest_addr;	/* dest host address of member */
} tpp_mcast_pkt_info_t;

#define SLOT_INC                1000

#define TPP_SLOT_FREE           0
#define TPP_SLOT_BUSY           1
#define TPP_SLOT_DELETED        2

/* tpp internal message header types */
enum TPP_MSG_TYPES {
	TPP_CTL_JOIN = 1,
	TPP_CTL_LEAVE,
	TPP_DATA,
	TPP_CTL_MSG,
	TPP_CLOSE_STRM,
	TPP_MCAST_DATA,
	TPP_AUTH_CTX,
	TPP_ENCRYPTED_DATA,
	TPP_LAST_MSG
};

#define TPP_MSG_NOROUTE         1
#define TPP_MSG_UPDATE          2
#define TPP_MSG_AUTHERR         3


#define TPP_STRM_NORMAL         1
#define TPP_STRM_MCAST          2

#define TPP_MAX_ACK_DELAY       1
#define TPP_MAX_RETRY_DELAY     30
#define TPP_CLOSE_WAIT          60
#define TPP_STRM_TIMEOUT        600
#define TPP_MIN_WAIT            2
#define TPP_SEND_SIZE           8192

/* tpp cmds used internally by the layer to notify messages between threads */
#define TPP_CMD_SEND            1
#define TPP_CMD_CLOSE           2
#define TPP_CMD_ASSIGN          3
#define TPP_CMD_EXIT            4
#define TPP_CMD_NET_CLOSE       5
#define TPP_CMD_PEER_CLOSE      6
#define TPP_CMD_NET_DATA        7
#define TPP_CMD_DELAYED_CONNECT 8
#define TPP_CMD_NET_RESTORE     9
#define TPP_CMD_NET_DOWN        10
#define TPP_CMD_WAKEUP          11

#define TPP_DEF_ROUTER_PORT     17001
#define TPP_SCRATCHSIZE         8192

#define TPP_ROUTER_STATE_DISCONNECTED	0   /* Leaf not connected to router */
#define TPP_ROUTER_STATE_CONNECTING		1   /* Leaf is connecting to router */
#define TPP_ROUTER_STATE_CONNECTED		2   /* Leaf connected to router */

/*
 * This structure contains the information about what kind of end-point
 * is connected over each connection to this router. When some end-point
 * connects to this router (or this router connects to others), there is a
 * TCP connection created (we call it a physical connection). The end-point
 * then send a "join" packet identifying who it is, and what type it is.
 * The router keeps track of what "kind" of end-point is connected to each of
 * such physical connections.
 */
typedef struct {
	unsigned char type; /* leaf or router */
	void *ptr; /* pointer to router or leaf structure */
} tpp_context_t;

/*
 * Structure to hold information about a router
 */
typedef struct {
	char *router_name; /* router host id */
	tpp_addr_t router_addr; /* primary ip address of router */
	int conn_fd;     /* fd - in case there is direct connection to router */
	time_t conn_time; /* time at which connection completed */
	int initiator;   /* we initialized the connection to the router */
	int state;       /* 1 - connected or 0 - disconnected */
	int delay;       /* time delay in re-connecting to the router */
	int index;		 /* the preference of data going over this connection */
	AVL_IX_DESC *AVL_my_leaves; /* leaves connected to this router, used by comm only */
} tpp_router_t;

/*
 * Structure to hold information of a leaf node
 */
typedef struct {
	int conn_fd;                /* real connection id. -1 if not directly connected */
	unsigned char leaf_type;    /* need notifications or not */

	int   tot_routers;          /* total number of routers which has this this leaf */
	int   num_routers;
	tpp_router_t **r;      /* list of routers leaf is connected to */

	int   num_addrs;
	tpp_addr_t *leaf_addrs; /* list of leaf's addresses */
} tpp_leaf_t;

/* routines and headers to manage FIFO queues */
struct tpp_que_elem {
	void *queue_data;
	struct tpp_que_elem *prev;
	struct tpp_que_elem *next;
};
typedef struct tpp_que_elem tpp_que_elem_t;

/* queue consists of a pointer to the head and tail of the queue */
typedef struct {
	tpp_que_elem_t *head;
	tpp_que_elem_t *tail;
} tpp_que_t;

/*
 * The cmd structure is used to package the
 * command messages passed between threads
 */
typedef struct {
	unsigned int tfd;
	int cmdval;
	void *data;
} tpp_cmd_t;

/*
 * mbox is the "message box" for each thread
 * When a thread wants to send a msg/cmd to another
 * thread, it posts a message to that threads mbox.
 * That wakes up the thread from a poll/select
 * and allows to act on the message
 */
typedef struct {
	pthread_mutex_t mbox_mutex;
	tpp_que_t mbox_queue;
#ifdef HAVE_SYS_EVENTFD_H
	int mbox_eventfd;
#else
	int mbox_pipe[2]; /* may be unused */
#endif
} tpp_mbox_t;


/* quickie macros to work with queues */
#define TPP_QUE_CLEAR(q)   (q)->head = NULL; (q)->tail = NULL
#define TPP_QUE_HEAD(q)    (q)->head
#define TPP_QUE_TAIL(q)    (q)->tail
#define TPP_QUE_NEXT(q, n) (((n) == NULL)?(q)->head:(n)->next)
#define TPP_QUE_DATA(n)    (((n) == NULL)?NULL:(n)->queue_data)

typedef struct {
	void *td;
	char tpplogbuf[TPP_LOGBUF_SZ];
	char tppstaticbuf[TPP_LOGBUF_SZ];
	void *log_data; /* data created by the logging layer for the TPP threads */
	void *avl_data; /* data created by the avl tree functions for the TPP threads */
} tpp_tls_t;

typedef struct {
	void *authctx;
	void *cleartext;
	int cleartext_len;
} conn_auth_t;

tpp_que_elem_t* tpp_enque(tpp_que_t *l, void *data);
void *tpp_deque(tpp_que_t *l);
tpp_que_elem_t* tpp_que_del_elem(tpp_que_t *l, tpp_que_elem_t *n);
tpp_que_elem_t* tpp_que_ins_elem(tpp_que_t *l, tpp_que_elem_t *n,
	void *data, int before);
/* End - routines and headers to manage FIFO queues */

void tpp_log_err(int errnum, char *routine, char *text);
void DIS_tpp_funcs();
int tpp_send(int sd, void *data, int len);
int tpp_recv(int sd, void *data, int len);
int tpp_ready_fds(int *sds, int len);
void *tpp_get_user_data(int sd);
int tpp_set_user_data(int sd, void *user_data);
char* convert_to_ip_port(char *host_port, int port);

int tpp_init_tls_key(void);
tpp_tls_t *tpp_get_tls(void);
char *tpp_get_logbuf(void);
char *mk_hostname(char *host, int port);
int tpp_eom(int fd);
int tpp_open(char *dest_host, unsigned int port);
int tpp_bind(unsigned int port);
int tpp_io(void);
int tpp_close(int sd);
struct sockaddr_in* tpp_localaddr(int fd);
struct sockaddr_in* tpp_getaddr(int tfd);
void tpp_shutdown(void);
void tpp_terminate(void);
int tpp_poll(void);
char *tpp_parse_hostname(char *full, int *port);
tpp_packet_t *tpp_cr_pkt(void *data, int len, int mk_data);

void tpp_router_shutdown(void);
void tpp_router_terminate(void);
void tpp_free_tls(void);

int tpp_transport_connect(char *hostname, int is_auth_resvport, int delay, void *ctx, int *ret_tfd);
int tpp_transport_vsend(int tfd, tpp_chunk_t *chunk, int count);
int tpp_transport_isresvport(int tfd);
int tpp_transport_vsend_extra(int tfd, tpp_chunk_t *chunk, int count, void *extra);
int tpp_transport_init(struct tpp_config *conf);
void tpp_transport_set_handlers(
	int (*pkt_presend_handler)(int phy_con, tpp_packet_t *pkt, void *extra),
	int (*pkt_postsend_handler)(int phy_con, tpp_packet_t *pkt, void *extra),
	int (*pkt_handler)(int, void *data, int len, void *, void *extra),
	int (*close_handler)(int, int, void *, void *extra),
	int (*post_connect_handler)(int sd, void *data, void *ctx, void *extra),
	int (*timer_handler)(time_t now)
	);
void tpp_set_logmask(long logmask);
int tpp_transport_shutdown(void);
int tpp_transport_terminate(void);
int tpp_transport_send(int tfd, void *data, int len);
int tpp_transport_send_raw(int tfd, tpp_packet_t *pkt);
int tpp_init_router(struct tpp_config *cnf);
void tpp_transport_set_conn_ctx(int tfd, void *ctx);
void *tpp_transport_get_conn_ctx(int tfd);
void *tpp_transport_get_thrd_context(int tfd);
int tpp_transport_wakeup_thrd(int tfd);
int tpp_transport_connect_spl(char *hostname, int is_auth_resvport, int delay, void *ctx, int *ret_tfd, void *tctx);
int tpp_transport_close(int tfd);

int tpp_init_lock(pthread_mutex_t *lock);
int tpp_lock(pthread_mutex_t *lock);
int tpp_unlock(pthread_mutex_t *lock);
int tpp_destroy_lock(pthread_mutex_t *lock);

/* rwlock is not supported by posix, so dont
 * refer to this in the header file, instead
 * use voids. The respective C sources which
 * implement this will defined _XOPEN_SOURCE
 * if necessary
 */
int tpp_init_rwlock(void *lock);
int tpp_rdlock_rwlock(void *lock);
int tpp_wrlock_rwlock(void *lock);
int tpp_unlock_rwlock(void *lock);
int tpp_destroy_rwlock(void *lock);

int tpp_set_non_blocking(int fd);
int tpp_set_close_on_exec(int fd);
void tpp_free_pkt(tpp_packet_t *pkt);
int tpp_send_ctl_msg(int fd, int code, tpp_addr_t *src, tpp_addr_t *dest, unsigned int src_sd, char err_num, char *msg);
int tpp_cr_thrd(void *(*start_routine)(void*), pthread_t *id, void *data);
void tpp_add_close_func(int sd, void (*func)(int));
int tpp_set_keep_alive(int fd, struct tpp_config *cnf);

void *tpp_deflate(void *inbuf, unsigned int inlen, unsigned int *outlen);
void *tpp_inflate(void *inbuf, unsigned int inlen, unsigned int totlen);
void *tpp_multi_deflate_init(int len);
int tpp_multi_deflate_do(void *ctx, int fini, void *inbuf, unsigned int inlen);
void *tpp_multi_deflate_done(void *c, unsigned int *cmpr_len);

int tpp_add_fd(int ctl_fd, int fd, int event);
int tpp_del_fd(int ctl_fd, int fd);
int tpp_mod_fd(int ctl_fd, int fd, int event);

int tpp_validate_hdr(int tfd, char *pkt_start);
tpp_addr_t *tpp_get_addresses(char *node_names, int *leaf_addr_count);
tpp_addr_t *tpp_get_local_host(int sock);
tpp_addr_t *tpp_get_connected_host(int sock);
int tpp_sock_resolve_ip(tpp_addr_t *addr, char *host, int len);
tpp_addr_t *tpp_sock_resolve_host(char *host, int *count);

const char * tpp_transport_get_conn_hostname(int tfd);
void tpp_transport_set_conn_extra(int tfd, void *extra);

char *tpp_netaddr(tpp_addr_t *);
char *tpp_netaddr_sa(struct sockaddr *);

extern void (*tpp_log_func)(int level, const char *id, char *mess); /* log function */

extern int tpp_dbprt;

void free_router(tpp_router_t *r);
void free_leaf(tpp_leaf_t *l);

#ifdef WIN32
int tr_2_errno(int win_errno);
#endif

/**********************************************************************/
/* em related definitions */
/**********************************************************************/
#define TPP_MAXOPENFD 8192 /*limit for pbs_comm max open files*/
#define MAX_CON		TPP_MAXOPENFD /* default max connections */

#if defined (PBS_USE_POLL)

typedef struct {
	int fd;
	int events;
} em_event_t;

typedef struct {
	struct pollfd *fds;
	em_event_t *events;
	int curr_nfds;
	int max_nfds;
} poll_context_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#elif defined (PBS_USE_EPOLL)

typedef struct epoll_event em_event_t;

typedef struct {
	int epoll_fd;
	int max_nfds;
	pid_t init_pid;
	em_event_t *events;
} epoll_context_t;

#define EM_GET_FD(ev, i) ev[i].data.fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	EPOLLIN
#define EM_OUT	EPOLLOUT
#define EM_HUP	EPOLLHUP
#define EM_ERR	EPOLLERR

#elif defined (PBS_USE_POLLSET)

typedef struct pollfd em_event_t;

typedef struct {
	pollset_t ps;
	int max_nfds;
	em_event_t *events;
} pollset_context_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].revents

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#elif defined (PBS_USE_SELECT)

typedef struct {
	int fd;
	int events;
} em_event_t;

typedef struct {
	fd_set master_read_fds;
	fd_set master_write_fds;
	fd_set master_err_fds;
	fd_set read_fds;
	fd_set write_fds;
	fd_set err_fds;
	int maxfd;
	int max_nfds;
	em_event_t *events;
} sel_context_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].events

#define EM_IN	0x001
#define EM_OUT	0x002
#define EM_HUP	0x004
#define EM_ERR	0x008

#elif defined (PBS_USE_DEVPOLL)

typedef struct pollfd em_event_t;

typedef struct {
	int devpoll_fd;
	em_event_t *events;
	int max_nfds;
} devpoll_context_t;

#define EM_GET_FD(ev, i) ev[i].fd
#define EM_GET_EVENT(ev, i) ev[i].revents

#define EM_IN	POLLIN
#define EM_OUT	POLLOUT
#define EM_HUP	POLLHUP
#define EM_ERR	POLLERR

#endif

/* platform independent functions that handle the underlying platform specific event
 * handling mechanism. Internally it could use epoll, poll, select etc, depending on the
 * platform.
 */
void *tpp_em_init(int max_events);
void tpp_em_destroy(void *em_ctx);
int tpp_em_add_fd(void *em_ctx, int fd, int event_mask);
int tpp_em_mod_fd(void *em_ctx, int fd, int event_mask);
int tpp_em_del_fd(void *em_ctx, int fd);
int tpp_em_wait(void *em_ctx, em_event_t **ev_array, int timeout);
#ifndef WIN32
int tpp_em_pwait(void *em_ctx, em_event_t **ev_array, int timeout, const sigset_t *sigmask);
#else
int tpp_em_wait_win(void *em_ctx, em_event_t **ev_array, int timeout);
#endif
/* platform independent functions that manipulate a mbox of a thread
 * Internally these functions may use a eventfd, signalfd, signals,
 * plain pipes etc.
 */
int tpp_mbox_init(tpp_mbox_t *mbox);
void tpp_mbox_destroy(tpp_mbox_t *mbox, int destroy_lock);
int tpp_mbox_monitor(void *em_ctx, tpp_mbox_t *mbox);
int tpp_mbox_read(tpp_mbox_t *mbox, unsigned int *tfd, int *cmdval, void **data);
int tpp_mbox_clear(tpp_mbox_t *mbox, tpp_que_elem_t **n, unsigned int tfd, int *cmdval, void **data);
int tpp_mbox_post(tpp_mbox_t *mbox, unsigned int tfd, int cmdval, void *data);
int tpp_mbox_getfd(tpp_mbox_t *mbox);

extern int tpp_going_down;
/**********************************************************************/

/*
 *	Different print macros for use in debugging.
 */
#ifdef  DEBUG

#define		TPP_DBPRT(x) \
	if (tpp_dbprt) { \
		int	err = errno; \
		time_t now; \
		struct tm ptm; \
		now = time(NULL); \
		localtime_r(&now, &ptm); \
		printf("%02d/%02d/%04d %02d:%02d:%02d;Thread:%d:%s: ",  \
			ptm.tm_mon+1, ptm.tm_mday, ptm.tm_year+1900, \
			ptm.tm_hour, ptm.tm_min, ptm.tm_sec, \
			tpp_get_thrd_index(), \
			__func__); \
			printf x; \
		printf("\n"); \
		fflush(stdout); \
		errno = err; \
	}
void print_packet_hdr(const char *fnc, void *data, int len);
#define PRTPKTHDR(id, data, len)  \
		print_packet_hdr(id, data, len);

#else

#define		TPP_DBPRT(x)
#define		PRTPKTHDR(id, data, len)

#endif

#endif
