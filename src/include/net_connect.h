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

#ifndef _NET_CONNECT_H
#define _NET_CONNECT_H

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
typedef unsigned long pbs_net_t; /* for holding host addresses */
#define PBS_NET_TYPE
#endif

#ifndef INADDR_NONE
#define INADDR_NONE (unsigned int) 0xFFFFFFFF
#endif

#define PBS_NET_MAXCONNECTIDLE 900

/* flag bits for cn_authen field */
#define PBS_NET_CONN_AUTHENTICATED 0x01
#define PBS_NET_CONN_FROM_PRIVIL 0x02
#define PBS_NET_CONN_NOTIMEOUT 0x04
#define PBS_NET_CONN_FROM_QSUB_DAEMON 0x08
#define PBS_NET_CONN_FORCE_QSUB_UPDATE 0x10
#define PBS_NET_CONN_PREVENT_IP_SPOOFING 0x20

#define QSUB_DAEMON "qsub-daemon"

/*
 **	Protocol numbers and versions for PBS communications.
 */

#define RM_PROTOCOL 1 /* resource monitor protocol number */
#define TM_PROTOCOL 2 /* task manager protocol number */
#define IM_PROTOCOL 3 /* inter-mom protocol number */
#define IS_PROTOCOL 4 /* inter-server protocol number */

/* When protocol changes, increment the version
* not to be changed lightly as it makes everything incompatable.
*/
#define RM_PROTOCOL_VER 1     /* resmon protocol version number */
#define TM_PROTOCOL_VER 2     /* task manager protocol version number */
#define TM_PROTOCOL_OLD 1     /* old task manager protocol version number */
#define IM_PROTOCOL_VER 6     /* inter-mom protocol version number */
#define IM_OLD_PROTOCOL_VER 5 /* inter-mom old protocol version number */
#define IS_PROTOCOL_VER 4     /* inter-server protocol version number */

/*	Types of Inter Server messages (between Server and Mom). */
#define IS_NULL 0
#define IS_CMD 1
#define IS_CMD_REPLY 2
#define IS_CLUSTER_ADDRS 3
#define IS_UPDATE 4
#define IS_RESCUSED 5
#define IS_JOBOBIT 6
#define IS_OBITREPLY 7
#define IS_REPLYHELLO 8
#define IS_SHUTDOWN 9
#define IS_IDLE 10
#define IS_REGISTERMOM 11
#define IS_UPDATE2 12
#define IS_DISCARD_JOB 13
#define IS_DISCARD_DONE 14
#define IS_UPDATE_FROM_HOOK 15		   /* request to update vnodes from a hook running on parent mom host */
#define IS_RESCUSED_FROM_HOOK 16	   /* request from child mom for a hook */
#define IS_HOOK_JOB_ACTION 17		   /* request from hook to delete/requeue job */
#define IS_HOOK_ACTION_ACK 18		   /* acknowledge a request of the above 2    */
#define IS_HOOK_SCHEDULER_RESTART_CYCLE 19 /* hook wish scheduler to recycle */
#define IS_HOOK_CHECKSUMS 20		   /* mom reports about hooks seen */
#define IS_UPDATE_FROM_HOOK2 21		   /* request to update vnodes from a hook running on a parent mom host or an allowed non-parent mom host */
#define IS_HELLOSVR 22			   /* hello send to server from mom to initiate a hello sequence */

/* return codes for client_to_svr() */

#define PBS_NET_RC_FATAL -1
#define PBS_NET_RC_RETRY -2

/* bit flags: authentication method (resv ports/external) and authentication mode(svr/client) */

#define B_RESERVED 0x1 /* need reserved port */
#define B_SVR 0x2      /* generate server type auth message */

/**
 * @brief
 * enum conn_type is used to (1) indicate that a connection table entry is in
 * use or is free (Idle).  Additional meaning for the entries are:
 *
 * @verbatim
 * 	Primary
 * 		the primary entry (port) on which the daemon is listening for
 *		connections from a client
 * 	Secondary
 * 		another connection on which the daemon is listening, a different
 *		service such as "resource monitor" part of Mom.
 *		If init_network() is called twice, the second port/entry is
 *		marked as the Secondary
 *	FromClientDIS
 *		a client initiated connection
 *	TppComm
 *		TPP based connection
 *	ChildPipe
 *		Used by Mom for a "unix" pipe between herself and a child;
 *		this is not a IP connection.
 *
 * @endverbatim
 *
 * @note
 *	The entries marked as Primary, Secondary, and TppComm do not require
 *	additional authenication of the user making the request.
 */
typedef struct connection conn_t;
enum conn_type {
	Primary = 0,
	Secondary,
	FromClientDIS,
	ToServerDIS,
	TppComm,
	ChildPipe,
	Idle
};

/*
 * This is used to know where the connection is originated from.
 * This can be extended to have MOM and other clients of Server in future.
 */
typedef enum conn_origin {
	CONN_UNKNOWN = 0,
	CONN_SCHED_PRIMARY,
	CONN_SCHED_SECONDARY,
	CONN_SCHED_ANY
} conn_origin_t;

/* functions available in libnet.a */

conn_t *add_conn(int sock, enum conn_type, pbs_net_t, unsigned int port, int (*ready_func)(conn_t *), void (*func)(int));
int set_conn_as_priority(conn_t *);
int add_conn_data(int sock, void *data); /* Adds the data to the connection */
void *get_conn_data(int sock);		 /* Gets the pointer to the data present with the connection */
int client_to_svr(pbs_net_t, unsigned int port, int);
int client_to_svr_extend(pbs_net_t, unsigned int port, int, char *);
void close_conn(int socket);
pbs_net_t get_connectaddr(int sock);
int get_connecthost(int sock, char *namebuf, int size);
pbs_net_t get_hostaddr(char *hostname);
int comp_svraddr(pbs_net_t, char *, pbs_net_t *);
int compare_short_hostname(char *shost, char *lhost);
unsigned int get_svrport(char *servicename, char *proto, unsigned int df);
int init_network(unsigned int port);
int init_network_add(int sock, int (*readyreadfunc)(conn_t *), void (*readfunc)(int));
void net_close(int);
int wait_request(float waittime, void *priority_context);
extern void *priority_context;
void net_add_close_func(int, void (*)(int));
extern pbs_net_t get_addr_of_nodebyname(char *name, unsigned int *port);
extern int make_host_addresses_list(char *phost, u_long **pul);

conn_t *get_conn(int sock); /* gets the connection, for a given socket id */
void connection_idlecheck(void);
void connection_init(void);
char *build_addr_string(pbs_net_t);
int set_nodelay(int fd);
extern void process_IS_CMD(int);

struct connection {
	int cn_sock;			/* socket descriptor */
	pbs_net_t cn_addr;		/* internet address of client */
	int cn_sockflgs;		/* file status flags - fcntl(F_SETFL) */
	unsigned int cn_port;		/* internet port number of client */
	unsigned short cn_authen;	/* authentication flags */
	enum conn_type cn_active;	/* idle or type if active */
	time_t cn_lasttime;		/* time last active */
	int (*cn_ready_func)(conn_t *); /* true if data rdy for cn_func */
	void (*cn_func)(int);		/* read function when data rdy */
	void (*cn_oncl)(int);		/* func to call on close */
	unsigned short cn_prio_flag;	/* flag for a priority socket */
	pbs_list_link cn_link;		/* link to the next connection in the linked list */
	/* following attributes are for */
	/* credential checking */
	time_t cn_timestamp;
	void *cn_data; /* pointer to some data for cn_func */
	char cn_username[PBS_MAXUSER + 1];
	char cn_hostname[PBS_MAXHOSTNAME + 1];
	char *cn_credid;
	char cn_physhost[PBS_MAXHOSTNAME + 1];
	pbs_auth_config_t *cn_auth_config;
	conn_origin_t cn_origin; /* used to know the origin of the connection i.e. Scheduler, MOM etc. */
};
#endif /* _NET_CONNECT_H */
