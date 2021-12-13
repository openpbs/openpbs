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
 * @file    pbs_client_thread.h
 *
 * @brief
 *	Pbs threading related functions declarations and structures
 */

#ifndef _PBS_CLIENT_THREAD_H
#define _PBS_CLIENT_THREAD_H

#ifdef __cplusplus
extern "C" {
#endif

#include <pthread.h>

/**
 * @brief
 *  Structure used for storing the connection related context data
 *
 *  Since each thread can open multiple connections, these connection specific
 *  data that might be accessed by the thread after an API call needs to be
 *  saved. An example of this is a thread calling pbs_submit(c1) and
 *  pbs_submit(c2) and then calling pbs_geterrmsg(c1) and pbs_geterrmsg(c2).
 *  The connection level errtxt and errno cannot be left at a global connection
 *  table level, since multiple threads will overwrite it when they share a
 *  connection (since the locking is done at an API level, and the errmsg might
 *  be requested past lock boundaries).
 *
 *  The structure connect_context captures ch_errno, and ch_errtxt from the
 *  connection handle. For each connection associated with a thread, a node of
 *  type struct connect_context is stored into the linked list headed by member
 *  th_ch_conn_context in structure thread_context
 */
struct pbs_client_thread_connect_context {
	/** connection handle */
	int th_ch;
	/** last error number that occured on this connection handle */
	int th_ch_errno;
	/** last server error text on this connection handle */
	char *th_ch_errtxt;
	/** link to the next node in the linked list */
	struct pbs_client_thread_connect_context
		*th_ch_next;
};

/**
 * @brief
 *  Structure used to store thread level context data (TLS)
 *
 *  struct thread_context is the consolidated data that is required by each
 *  thread during its flow throught IFL API and communication to server.
 *  The structure is allocated and stored into TLS area during thread_init
 */
struct pbs_client_thread_context {
	/** stores the global pbs errno */
	int th_pbs_errno;
	/** head pointer to the linked list of connection contexts */
	struct pbs_client_thread_connect_context
		*th_conn_context;
	/** pointer to the array of attribute error structures */
	struct ecl_attribute_errors
		*th_errlist;
	/** pointer to the location for the dis_buffer for each thread */
	char *th_dis_buffer;
	/** pointer to the cred_info structure used by pbs_submit_with_cred */
	void *th_cred_info;
	/** used by totpool and usepool functions */
	void *th_node_pool;
	char th_pbs_server[PBS_MAXSERVERNAME + 1];
	char th_pbs_defserver[PBS_MAXSERVERNAME + 1];
	char th_pbs_current_user[PBS_MAXUSER + 1];
	time_t th_pbs_tcp_timeout;
	int th_pbs_tcp_interrupt;
	int th_pbs_tcp_errno;
	int th_pbs_mode;
};

/* corresponding function pointers for the externally used functions */
extern int (*pfn_pbs_client_thread_lock_connection)(int connect);
extern int (*pfn_pbs_client_thread_unlock_connection)(int connect);
extern struct pbs_client_thread_context *(*pfn_pbs_client_thread_get_context_data)(void);
extern int (*pfn_pbs_client_thread_lock_conntable)(void);
extern int (*pfn_pbs_client_thread_unlock_conntable)(void);
extern int (*pfn_pbs_client_thread_lock_conf)(void);
extern int (*pfn_pbs_client_thread_unlock_conf)(void);
extern int (*pfn_pbs_client_thread_init_thread_context)(void);
extern int (*pfn_pbs_client_thread_init_connect_context)(int connect);
extern int (*pfn_pbs_client_thread_destroy_connect_context)(int connect);

/* #defines for functions called by other code */
#define pbs_client_thread_lock_connection(connect) \
	(*pfn_pbs_client_thread_lock_connection)(connect)
#define pbs_client_thread_unlock_connection(connect) \
	(*pfn_pbs_client_thread_unlock_connection)(connect)
#define pbs_client_thread_get_context_data() \
	(*pfn_pbs_client_thread_get_context_data)()
#define pbs_client_thread_lock_conntable() \
	(*pfn_pbs_client_thread_lock_conntable)()
#define pbs_client_thread_unlock_conntable() \
	(*pfn_pbs_client_thread_unlock_conntable)()
#define pbs_client_thread_lock_conf() \
	(*pfn_pbs_client_thread_lock_conf)()
#define pbs_client_thread_unlock_conf() \
	(*pfn_pbs_client_thread_unlock_conf)()
#define pbs_client_thread_init_thread_context() \
	(*pfn_pbs_client_thread_init_thread_context)()
#define pbs_client_thread_init_connect_context(connect) \
	(*pfn_pbs_client_thread_init_connect_context)(connect)
#define pbs_client_thread_destroy_connect_context(connect) \
	(*pfn_pbs_client_thread_destroy_connect_context)(connect)

/* functions to add/remove/find connection context to the thread context */
struct pbs_client_thread_connect_context *
pbs_client_thread_add_connect_context(int connect);
int pbs_client_thread_remove_connect_context(int connect);
struct pbs_client_thread_connect_context *
pbs_client_thread_find_connect_context(int connect);
void free_errlist(struct ecl_attribute_errors *errlist);

/* function called by daemons to set them to use the unthreaded functions */
void pbs_client_thread_set_single_threaded_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* _PBS__CLIENT_THREAD_H */
