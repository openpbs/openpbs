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


#ifndef	__RPP_H
#define __RPP_H
#ifdef	__cplusplus
extern "C" {
#endif

/*
 **	Default number of sendto attempts on a packet.
 */
#include "pbs_internal.h"

#define	RPP_RETRY	10
/*
 **	Default allowed number of outstanding pkts.
 */
#define	RPP_HIGHWATER	1024

/*
 * Default number of RPP packets to check every server iteration
 */
#define RPP_MAX_PKT_CHECK_DEFAULT	64

/* TPP specific definitions and structures */
#define TPP_DEF_ROUTER_PORT 17001

struct tpp_config {
	int    node_type; /* leaf, proxy */
	char   **routers; /* other proxy names (and backups) to connect to */
	int    numthreads;
	char   *node_name; /* list of comma separated node names */
	char   auth_type[MAXAUTHNAME + 1];
	int    is_auth_resvport;
	int    compress;
	int    tcp_keepalive; /* use keepalive? */
	int    tcp_keep_idle;
	int    tcp_keep_intvl;
	int    tcp_keep_probes;
	int    tcp_user_timeout;
	int    buf_limit_per_conn; /* buffer limit per physical connection */
	int    force_fault_tolerance; /* by default disabled */
};

/* rpp node types, leaf and router */
#define TPP_LEAF_NODE           1  /* leaf node that does not care about TPP_CTL_LEAVE messages from other leaves */
#define TPP_LEAF_NODE_LISTEN    2  /* leaf node that wants to be notified of TPP_CTL_LEAVE messages from other leaves */
#define TPP_ROUTER_NODE         3  /* router */
#define TPP_AUTH_NODE           4  /* authenticated, but yet unknown node type till a join happens */

/* TPP specific functions */
extern int	tpp_init(struct tpp_config *conf);
extern void tpp_set_app_net_handler(void (*app_net_down_handler)(void *data),
void (*app_net_restore_handler)(void *data));
extern void tpp_set_logmask(long logmask);
extern void set_tpp_funcs(void (*log_fn)(int, const char *, char *));
extern int set_tpp_config(struct pbs_config *, struct tpp_config *, char *, int, char *);
/*
 **	Common Function prototypes (rpp or tpp)
 */
extern int			(*pfn_rpp_open)(char *, unsigned int);
extern int			(*pfn_rpp_bind)(unsigned int);
extern int			(*pfn_rpp_poll)(void);
extern int			(*pfn_rpp_io)(void);
extern int			(*pfn_rpp_read)(int, void *, int);
extern int			(*pfn_rpp_write)(int, void *, int);
extern int			(*pfn_rpp_close)(int);
extern void			(*pfn_rpp_destroy)(int);
extern struct	sockaddr_in*	(*pfn_rpp_localaddr)(int);
extern struct	sockaddr_in*	(*pfn_rpp_getaddr)(int);
extern int			(*pfn_rpp_flush)(int);
extern void			(*pfn_rpp_shutdown)(void);
extern void			(*pfn_rpp_terminate)(void);
extern int			(*pfn_rpp_rcommit)(int, int);
extern int			(*pfn_rpp_wcommit)(int, int);
extern int			(*pfn_rpp_skip)(int, size_t);
extern int			(*pfn_rpp_eom)(int);
extern int			(*pfn_rpp_getc)(int);
extern int			(*pfn_rpp_putc)(int, int);
extern void			(*pfn_DIS_rpp_funcs)();
extern void			(*pfn_rpp_add_close_func)(int, void (*func)(int));

#define rpp_open(x, y)		(*pfn_rpp_open)(x, y)
#define rpp_bind(x)		(*pfn_rpp_bind)(x)
#define rpp_poll()		(*pfn_rpp_poll)()
#define rpp_io()		(*pfn_rpp_io)()
#define rpp_read(x, y, z)		(*pfn_rpp_read)(x, y, z)
#define rpp_write(x, y, z)	(*pfn_rpp_write)(x, y, z)
#define rpp_close(x)		(*pfn_rpp_close)(x)
#define rpp_destroy(x)		(*pfn_rpp_destroy)(x)
#define rpp_localaddr(x)	(*pfn_rpp_localaddr)(x)
#define rpp_getaddr(x)		(*pfn_rpp_getaddr)(x)
#define rpp_flush(x)		(*pfn_rpp_flush)(x)
#define rpp_shutdown()		(*pfn_rpp_shutdown)()
#define rpp_terminate()		(*pfn_rpp_terminate)()
#define rpp_rcommit(x, y)	(*pfn_rpp_rcommit)(x, y)
#define rpp_wcommit(x, y)	(*pfn_rpp_wcommit)(x, y)
#define rpp_skip(x, y)		(*pfn_rpp_skip)(x, y)
#define rpp_eom(x)		(*pfn_rpp_eom)(x)
#define rpp_getc(x)		(*pfn_rpp_getc)(x)
#define rpp_putc(x, y)		(*pfn_rpp_putc)(x, y)
#define DIS_rpp_funcs()		(*pfn_DIS_rpp_funcs)()
#define rpp_add_close_func(x, y) (*pfn_rpp_add_close_func)(x, y)

extern char	*netaddr(struct sockaddr_in *);
extern char *get_all_ips(char *, char *, size_t);
#define	RPP_ADVISE_TIMEOUT	1


typedef	void (rpp_logfunc_t)(char *);

extern	rpp_logfunc_t	*rpp_logfunc;

extern	int	rpp_fd;
extern	int	rpp_dbprt;
extern	int	rpp_retry;
extern	int	rpp_highwater;

/* rpp specific functions */
extern void set_rpp_funcs(void (*log_fn)(char *));
extern int tpp_get_thrd_index();

/**
 * @par	Experimental!
 *	Do not use.
 */
extern int	rpp_advise(int, void *);


/* special tpp only multicast function prototypes */
extern int tpp_mcast_open(void);
extern int tpp_mcast_add_strm(int mtfd, int tfd);
extern int *tpp_mcast_members(int mtfd, int *count);
extern int tpp_mcast_send(int mtfd, void *data, unsigned int len, unsigned int full_len, unsigned int compress);
extern int tpp_mcast_close(int mtfd);

/* utility for getting checksum of a file */
extern unsigned long crc_file(char *fname);
#endif
