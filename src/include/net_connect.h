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
#ifndef	_NET_CONNECT_H
#define	_NET_CONNECT_H


/*
 * Other Include Files Required
 *	<sys/types.h>
 *       "pbs_ifl.h"
 */
#include <sys/types.h>
#include <unistd.h>
#include "list_link.h"
#include "auth.h"
#define PBS_NET_H
#ifndef PBS_NET_TYPE
typedef unsigned long pbs_net_t;        /* for holding host addresses */
#define PBS_NET_TYPE
#endif

#ifndef INADDR_NONE
#define INADDR_NONE	(unsigned int)0xFFFFFFFF
#endif

#define PBS_NET_MAXCONNECTIDLE  900

/* flag bits for cn_authen field */
#define PBS_NET_CONN_AUTHENTICATED 0x01
#define PBS_NET_CONN_FROM_PRIVIL   0x02
#define PBS_NET_CONN_NOTIMEOUT	   0x04
#define PBS_NET_CONN_FROM_QSUB_DAEMON	0x08
#define PBS_NET_CONN_FORCE_QSUB_UPDATE	0x10
#define PBS_NET_CONN_TO_SCHED	0x20

#define	QSUB_DAEMON	"qsub-daemon"

/*
 **	Protocol numbers and versions for PBS communications.
 */

#define RM_PROTOCOL	1	/* resource monitor protocol number */
#define RM_PROTOCOL_VER	1	/* resmon protocol version number */

#define	TM_PROTOCOL	2	/* task manager protocol number */
#define	TM_PROTOCOL_VER	2	/* task manager protocol version number */
#define	TM_PROTOCOL_OLD	1	/* old task manager protocol version number */

#define	IM_PROTOCOL	3	/* inter-mom protocol number */
#define	IM_PROTOCOL_VER	6	/* inter-mom protocol version number */
#define	IM_OLD_PROTOCOL_VER 5	/* inter-mom old protocol version number */

#define	IS_PROTOCOL	4	/* inter-server protocol number */
#define	IS_PROTOCOL_VER	3	/* inter-server protocol version number */


/*
 **	Types of Inter Server messages (between Server and Mom).
 */
#define	IS_NULL			0
#define	IS_HELLO		1
#define	IS_CLUSTER_ADDRS	2
#define IS_UPDATE		3
#define IS_RESCUSED		4
#define IS_JOBOBIT		5
#define IS_BADOBIT		6
#define IS_RESTART		7
#define IS_SHUTDOWN		8
#define IS_IDLE			9
#define IS_ACKOBIT		10
#define IS_GSS_HANDSHAKE	11	/* Deprecated */
#define IS_CLUSTER_KEY		12	/* Deprecated */
#define IS_REGISTERMOM		13
#define IS_UPDATE2		14
#define IS_HELLO2		15
#define IS_HOST_TO_VNODE	16
#define IS_RECVD_VMAP		17
#define IS_MOM_READY		17	/* alias for IS_RECD_VMAP */
#define IS_HELLO3		18
#define IS_DISCARD_JOB		19
#define IS_HELLO4		20
#define IS_DISCARD_DONE		21
#define IS_HPCBP_ATTRIBUTES	22 	/* Deprecated */
#define	IS_CLUSTER_ADDRS2	23
#define IS_UPDATE_FROM_HOOK	24 /* request to update vnodes from a hook running on parent mom host */
#define IS_RESCUSED_FROM_HOOK	25 /* request from child mom for a hook */
#define IS_HOOK_JOB_ACTION      26 /* request from hook to delete/requeue job */
#define IS_HOOK_ACTION_ACK      27 /* acknowledge a request of the above 2    */
#define IS_HOOK_SCHEDULER_RESTART_CYCLE  29 /* hook wish scheduler to recycle */
#define IS_HOOK_CHECKSUMS		 30 /* mom reports about hooks seen */
#define IS_HELLO_NO_INVENTORY	31 /* send info about the mom node only */
#define IS_UPDATE_FROM_HOOK2	32 /* request to update vnodes from a hook running on a parent mom host or an allowed non-parent mom host */

#define IS_CMD          40
#define IS_CMD_REPLY    41

/* Bits for IS_HELLO4 contents */
#define HELLO4_vmap_version	 1
#define HELLO4_running_jobs	 2

/* return codes for client_to_svr() */

#define PBS_NET_RC_FATAL -1
#define PBS_NET_RC_RETRY -2

/* bit flags: authentication method (resv ports/external) and authentication mode(svr/client) */

#define B_RESERVED	0x1	/* need reserved port */
#define B_SVR		0x2	/* generate server type auth message */

/**
 * @brief
 * enum conn_type is used to (1) indicate that a connection table entry is in
 * use or is free (Idle).  Additional meaning for the entries are:
 * @verbatim
 * Primary - the primary entry (port) on which the daemon is listening for
 *           connections from a client
 * Secondary - another connection on which the daemon is listening, a different
 *           service such as "resource monitor" part of Mom.
 *           If init_network() is called twice, the second port/entry is
 *           marked as the Secondary
 * FromClientDIS - a client initiated connection
 * RppComm - Used by the daemons who do RPP
 * ChildPipe - Used by Mom for a "unix" pipe between herself and a child;
 *           this is not a IP connection.
 * @endverbatim
 * The entries marked as Primary, Secondary, and RppComm do not require
 * additional authenication of the user making the request.
 */

typedef struct connection conn_t;
enum conn_type {
	Primary = 0,
	Secondary,
	FromClientDIS,
	ToServerDIS,
	RppComm,
	ChildPipe,
	Idle
};

/* functions available in libnet.a */

conn_t *add_conn(int sock, enum conn_type, pbs_net_t, unsigned int port, int (*ready_func)(conn_t *), void (*func)(int));
conn_t *add_conn_priority(int sock, enum conn_type, pbs_net_t, unsigned int port, int (*ready_func)(conn_t *), void (*func)(int), int priority_flag);
int add_conn_data(int sock, void *data); /* Adds the data to the connection */
void *get_conn_data(int sock); /* Gets the pointer to the data present with the connection */
void close_socket(int sock);
int  client_to_svr(pbs_net_t, unsigned int port, int);
int  client_to_svr_extend(pbs_net_t, unsigned int port, int, char*);
void set_client_to_svr_timeout(unsigned int);
void close_conn(int socket);
pbs_net_t get_connectaddr(int sock);
int  get_connecthost(int sock, char *namebuf, int size);
pbs_net_t get_hostaddr(char *hostname);
int  compare_short_hostname(char *shost, char *lhost);
unsigned int  get_svrport(char *servicename, char *proto, unsigned int df);
int  init_network(unsigned int port);
int  init_network_add(int sock, int (*readyreadfunc)(conn_t *), void (*readfunc)(int));
void net_close(int);
int  wait_request(time_t waittime, void *priority_context);
extern void *priority_context;
void net_add_close_func(int, void(*)(int));
extern  pbs_net_t  get_addr_of_nodebyname(char *name, unsigned int *port);

conn_t *get_conn(int sock); /* gets the connection, for a given socket id */
void connection_idlecheck(void);
void connection_init(void);
char *build_addr_string(pbs_net_t);
int set_nodelay(int fd);

struct connection {
	int		cn_sock;	/* socket descriptor */
	pbs_net_t	cn_addr;	/* internet address of client */
	int		cn_sockflgs;	/* file status flags - fcntl(F_SETFL) */
	unsigned int	cn_port;	/* internet port number of client */
	unsigned short  cn_authen;	/* authentication flags */
	enum conn_type	cn_active;	/* idle or type if active */
	time_t		cn_lasttime;	/* time last active */
	int		(*cn_ready_func)(conn_t *); /* true if data rdy for cn_func */
	void		(*cn_func)(int); /* read function when data rdy */
	void		(*cn_oncl)(int); /* func to call on close */
	unsigned short	cn_prio_flag;	/* flag for a priority socket */
	pbs_list_link   cn_link;  /* link to the next connection in the linked list */
	/* following attributes are for */
	/* credential checking */
	time_t          cn_timestamp;
	void            *cn_data;         /* pointer to some data for cn_func */
	char            cn_username[PBS_MAXUSER + 1];
	char            cn_hostname[PBS_MAXHOSTNAME + 1];
	char            *cn_credid;
	char            cn_physhost[PBS_MAXHOSTNAME + 1];
	int             cn_is_auth_resvport;
	char            cn_auth_method[MAXAUTHNAME + 1];
	int             cn_encrypt_mode;
};
#endif	/* _NET_CONNECT_H */
