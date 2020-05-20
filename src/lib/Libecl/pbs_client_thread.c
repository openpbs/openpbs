/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
 * @file	pbs_client_thread.c
 *
 * @brief	Pbs threading related functions
 *
 * @par		Functionality:
 *	This module provides an higher level abstraction of the
 *	pthread calls by wrapping them with some additional logic to the
 *	rest of the PBS world.
 */

#include <pbs_config.h>   /* the master config generated by configure */
#include <unistd.h>
#include <sys/types.h>
#include <pwd.h>
#ifdef NAS /* localmod 005 */
#include <unistd.h>
#endif /* localmod 005 */
#include "libpbs.h"
#include "pbs_client_thread.h"

/**
 * @brief
 *	initializes the dis static tables for future use
 *
 * @par Functionality:
 *	Initializes the dis static tables for future use\n
 *	This is called only once from @see __init_thread_data via
 *	the pthread_once mechanism
 */
extern void dis_init_tables(void);
extern long dis_buffsize; /* defn of DIS_BUFSZ in dis headers */

/**
 * @brief
 *	Function to free the node pool structure
 *
 * @par Functionality:
 *	Frees the node pool structure. \n
 *	This is called only once when the thread is being destroyed
 */
extern void free_node_pool(void *);

/**
 * For capturing errors inside the once function. \n
 * Even though this is a global var, this won't cause threading issues, \n
 * since pthread calls the once function only once in a processes lifetime
 */
static int __pbs_client_thread_init_rc = 0;


/* the __ functions have the actual threaded functionality */
static int  __pbs_client_thread_lock_connection(int connect);
static int  __pbs_client_thread_unlock_connection(int connect);
static struct pbs_client_thread_context *
__pbs_client_thread_get_context_data(void);
static int  __pbs_client_thread_lock_conntable(void);
static int  __pbs_client_thread_unlock_conntable(void);
static int  __pbs_client_thread_lock_conf(void);
static int  __pbs_client_thread_unlock_conf(void);
static int  __pbs_client_thread_init_thread_context(void);
static int  __pbs_client_thread_init_connect_context(int connect);
static int  __pbs_client_thread_destroy_connect_context(int connect);
static void __pbs_client_thread_destroy_thread_data(void * p);


/*
 * The pfn_pbs_client_thread function pointers are assigned to the real
 * functions here. This is the default assignment. If an internal 'client'
 * (like the daemons) wish to bypass the verification and threading behavior
 * they can call pbs_client_thread_set_single_threaded_mode() to reset these
 * function pointers to point to single threaded mode funcs, most of which have
 * an empty implementation
 */

int (*pfn_pbs_client_thread_lock_connection)(int connect)
= &__pbs_client_thread_lock_connection;

int (*pfn_pbs_client_thread_unlock_connection)(int connect)
= &__pbs_client_thread_unlock_connection;

struct pbs_client_thread_context *
(*pfn_pbs_client_thread_get_context_data)(void)
= &__pbs_client_thread_get_context_data;

int (*pfn_pbs_client_thread_lock_conntable)(void)
= &__pbs_client_thread_lock_conntable;

int (*pfn_pbs_client_thread_unlock_conntable)(void)
= &__pbs_client_thread_unlock_conntable;

int (*pfn_pbs_client_thread_lock_conf)(void)
= &__pbs_client_thread_lock_conf;

int (*pfn_pbs_client_thread_unlock_conf)(void)
= &__pbs_client_thread_unlock_conf;

int (*pfn_pbs_client_thread_init_thread_context)(void)
= &__pbs_client_thread_init_thread_context;

int (*pfn_pbs_client_thread_init_connect_context)(int connect)
= &__pbs_client_thread_init_connect_context;

int (*pfn_pbs_client_thread_destroy_connect_context)(int connect)
= &__pbs_client_thread_destroy_connect_context;


/* following are some global thread related variables, like initializers etc */
static pthread_key_t key_tls; /* the key used to set/retrieve the TLS data */
static pthread_once_t pre_init_key_once = PTHREAD_ONCE_INIT; /* once keys */
static pthread_once_t post_init_key_once = PTHREAD_ONCE_INIT;

static pthread_mutex_t pbs_client_thread_conntable_mutex; /* for conn table */
static pthread_mutex_t pbs_client_thread_conf_mutex; /* for pbs_loadconf */
static pthread_mutexattr_t attr;


/**
 * This is a local thread_context variable which is used by the single threaded
 * model functions. This way the semantics is similar between single/multi
 * threaded code. The only difference in single threaded mode is that it uses a
 * global data structure to store the data instead of the TLS
 */
static struct pbs_client_thread_context
pbs_client_thread_single_threaded_context;

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_lock_connection_single_threaded(int connect)
{
	return 0;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_unlock_connection_single_threaded(int connect)
{
	return 0;
}

/** single threaded mode function definition
 * @brief
 *	Returns the thread context data
 *
 * @par Functionality:
 *	Returns the address of the global thread context variable called
 *	@see pbs_client_thread_single_threaded_context
 *
 * @retval - Address of the thread context data
 *
 */
struct pbs_client_thread_context *
__pbs_client_thread_get_context_data_single_threaded(void)
{
	return &pbs_client_thread_single_threaded_context;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_lock_conntable_single_threaded(void)
{
	return 0;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_unlock_conntable_single_threaded(void)
{
	return 0;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_lock_conf_single_threaded(void)
{
	return 0;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_unlock_conf_single_threaded(void)
{
	return 0;
}

/** single threaded mode dummy function definition */
static int
__pbs_client_thread_destroy_connect_context_single_threaded(int connect)
{
	return 0;
}

/**
 * this is a global variable but is used only when single threaded model is set,
 * so is not a issue with threading
 */
static int single_threaded_init_done = 0;

/**
 * @brief
 *	Initialize the thread context for single threaded applications.
 *
 * @par Functionality:
 *      1. Sets the context using global variable
 *	   pbs_client_thread_single_threaded_context \n
 *      2. Initializes the members of this structure \n
 *      3. Sets single_threaded_init_done to 1 \n
 *	This is the function that gets called when single threaded applications
 *	call pbs_client_thread_init_thread_context.
 *
 * @return	int
 *
 * @retval	0 - success
 * @retval	1 - failure (pbs_errno is set)
 *
 * @par Side-effects:
 *	Modifies global variable, single_threaded_init_done.
 *
 * @par Reentrancy:
 *	MT unsafe
 */
static int
__pbs_client_thread_init_thread_context_single_threaded(void)
{
	struct pbs_client_thread_context *ptr;
	struct passwd *pw;
	uid_t pbs_current_uid;

	if (single_threaded_init_done)
		return 0;

	ptr = &pbs_client_thread_single_threaded_context;

	/* initialize any elements of the single_threaded_context */
	memset(ptr, 0, sizeof(struct pbs_client_thread_context));

	ptr->th_dis_buffer = calloc(1, dis_buffsize); /* defined in tcp_dis.c */
	if (ptr->th_dis_buffer == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	/* set any default values for the TLS vars */
	ptr->th_pbs_tcp_timeout = PBS_DIS_TCP_TIMEOUT_SHORT;
	ptr->th_pbs_tcp_interrupt = 0;
	ptr->th_pbs_tcp_errno = 0;
	pbs_current_uid = getuid();
	if ((pw = getpwuid(pbs_current_uid)) == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}
	if (strlen(pw->pw_name) > (PBS_MAXUSER - 1)) {
		pbs_errno = PBSE_BADUSER;
		return -1;
	}
	strcpy(ptr->th_pbs_current_user, pw->pw_name);

	dis_init_tables();

	single_threaded_init_done = 1;
	ptr->th_pbs_mode = 1; /* single threaded */
	return 0;
}

/** single threaded mode dummy functions definition */
static int
__pbs_client_thread_init_connect_context_single_threaded(int connect)
{
	return 0;
}

/**
 * @brief
 *	Set single threaded mode for the caller
 *
 * @par Functionality:
 *	The functions pointers are reset to a different set of functions,
 *	most of which have an empty implementation.
 *	Called by the daemons to bypass multithreading functions.
 *	The functions pointers are reset to a different set of functions,
 *	most of which have an empty implementation.
 *
 * @return	void
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	MT unsafe - should be called only in a single threaded application
 */
void
pbs_client_thread_set_single_threaded_mode(void)
{
	/* point these to dummy functions */
	pfn_pbs_client_thread_lock_connection =
		__pbs_client_thread_lock_connection_single_threaded;
	pfn_pbs_client_thread_unlock_connection =
		__pbs_client_thread_unlock_connection_single_threaded;
	pfn_pbs_client_thread_get_context_data =
		__pbs_client_thread_get_context_data_single_threaded;
	pfn_pbs_client_thread_lock_conntable =
		__pbs_client_thread_lock_conntable_single_threaded;
	pfn_pbs_client_thread_unlock_conntable =
		__pbs_client_thread_unlock_conntable_single_threaded;
	pfn_pbs_client_thread_lock_conf =
		__pbs_client_thread_lock_conf_single_threaded;
	pfn_pbs_client_thread_unlock_conf =
		__pbs_client_thread_unlock_conf_single_threaded;
	pfn_pbs_client_thread_init_thread_context =
		__pbs_client_thread_init_thread_context_single_threaded;
	pfn_pbs_client_thread_init_connect_context =
		__pbs_client_thread_init_connect_context_single_threaded;
	pfn_pbs_client_thread_destroy_connect_context =
		__pbs_client_thread_destroy_connect_context_single_threaded;
}


/* following are the definitions of the actual threaded functions */

/**
 * @brief
 *	Pre/First initialization routine
 *
 * @par Functionality:
 *      1. Creates the key to be used to set/retrieve TLS data for a thread \n
 *      2. Creates the mutex attribute attr of type recursive mutex \n
 *      3. Creates the recursive mutex used to seralize access to global data \n
 *	This is the function called by pthread_once mechanism exactly once in
 *	the process lifetime from "__pbs_client_thread_init_thread_context".
 *
 * @see __pbs_client_thread_init_thread_context\n __post_init_thread_data
 *
 * @return	void
 *
 * @par Side-effects:
 *	Modifies global variable, __pbs_client_thread_init_rc. This variable is
 *	used to hold any error that might happen inside this function. (since
 *	pthread_once only takes a function with a void return type). This won't
 *	be a thread race/issue, since the variable is modified only by the init
 *	function which is called only once via pthread_once(). This global var
 *	is set by this function and used by the caller routine
 *	"__pbs_client_thread_init_thread_context" to know whether the code
 *	inside __init_thead_data executed successfully or not.
 *
 * @par Reentrancy:
 *	MT unsafe - must be called via pthread_once()
 */
static void
__init_thread_data(void)
{
	if ((__pbs_client_thread_init_rc =
		pthread_key_create(&key_tls,
		&__pbs_client_thread_destroy_thread_data)) != 0)
		return;

	/*
	 * since this function is called only once in the processes lifetime
	 * use this place to initialize mutex attribute and the mutexes
	 */
	if ((__pbs_client_thread_init_rc = pthread_mutexattr_init(&attr)) != 0)
		return;

	if ((__pbs_client_thread_init_rc = pthread_mutexattr_settype(&attr,
	/*
	 * linux does not have a PTHREAD_MUTEX_RECURSIVE attr_type, instead
	 * has a PTHREAD_MUTEX_RECURSIVE_NP (NP stands for non-portable). Thus
	 * need a conditional compile to ensure it builds properly in linux as
	 * well as the other unixes. The windows implementation of pthread, the
	 * Libpbspthread.dll library, however knows only about
	 * "PTHREAD_MUTEX_RECURSIVE", and will reject any other attr_type.
	 *
	 */
#if defined (linux)
		PTHREAD_MUTEX_RECURSIVE_NP
#else
		PTHREAD_MUTEX_RECURSIVE
#endif
		)) != 0)
		return;

	/*
	 * initialize the process-wide conntable mutex
	 * Recursive mutex
	 */
	if ((__pbs_client_thread_init_rc =
		pthread_mutex_init(&pbs_client_thread_conntable_mutex, &attr))
		!= 0)
		return;

	/*
	 * initialize the process-wide conf mutex
	 * Recursive mutex
	 */
	if ((__pbs_client_thread_init_rc =
		pthread_mutex_init(&pbs_client_thread_conf_mutex, &attr))
		!= 0)
		return;

	pthread_mutexattr_destroy(&attr);
	return;
}

/**
 * @brief
 *	Post initialization routine
 *
 * @par Functionality:
 *	1. Initializes the dis tables, by calling the function dis_init_tables.
 *	This is the function called by pthread_once mechanism exactly once in
 *	the process lifetime from "__pbs_client_thread_init_thread_context".
 *
 * @see __pbs_client_thread_init_thread_context\n __init_thread_data
 *
 * @note
 *	Called at the end of the __pbs_client_thread_init_thread_context.
 *      The reason is that the functionality depends on TLS data area set by
 *      __pbs_thead_init_context.
 *
 *
 * @return	void
 *
 * @par Reentrancy:
 *	MT unsafe - must be called via pthread_once()
 */
static void
__post_init_thread_data(void)
{
	dis_init_tables();
}

/**
 * @brief
 *	Initialize the thread context
 *
 * @par Functionality:
 *      1. Calls __init_thread_data via pthread_once to init mutexes/TLS key \n
 *      2. If TLS data is not already created, then create it \n
 *      3. Finally calls __post_init_thread_data function via pthread_once
 *         to ensure that the dis tables are initialized only once in the
 *         process lifetime. \n
 *	All external API calls should call this function first before calling
 *	any other pbs_client_thread_ functions.
 *
 * @see __init_thread_data\n __post_init_thread_data
 *
 * @return	int
 *
 * @retval	0 Success
 * @retval	>0 Failure (set to the pbs_errno)
 *
 * @par Side effects:
 *	If a failure occurs in this function, then it calls
 *	set_single_threaded_model to switch to a single threaded model to be
 *	able to return the error code reliably to the caller.
 *
 * @par Reentrancy:
 *	MT safe
 */
static int
__pbs_client_thread_init_thread_context(void)
{
	struct pbs_client_thread_context *ptr;
	int ret;
	struct passwd *pw;
	uid_t pbs_current_uid;
	int free_ptr = 0;

	/* initialize the TLS key for all threads */
	if (pthread_once(&pre_init_key_once, __init_thread_data) != 0) {
		ret = PBSE_SYSTEM;
		goto err;
	}

	if (__pbs_client_thread_init_rc != 0) {
		ret = PBSE_SYSTEM;
		goto err;
	}

	if (pthread_getspecific(key_tls) != NULL)
		return 0; /* thread data already initialized */

	ptr = calloc(1, sizeof(struct pbs_client_thread_context));
	if (!ptr) {
		ret = PBSE_SYSTEM;
		goto err;
	}

	/* set any default values for the TLS vars */
	ptr->th_pbs_tcp_timeout = PBS_DIS_TCP_TIMEOUT_SHORT;
	ptr->th_pbs_tcp_interrupt = 0;
	ptr->th_pbs_tcp_errno = 0;

	/* initialize any elements of the ptr */
	ptr->th_dis_buffer = calloc(1, dis_buffsize); /* defined in tcp_dis.c */
	if (ptr->th_dis_buffer == NULL) {
		free_ptr = 1;
		ret = PBSE_SYSTEM;
		goto err;
	}

	/*
	 * synchronize this part, since the getuid, getpwuid functions are not
	 * thread-safe
	 */
	if (pbs_client_thread_lock_conf() != 0) {
		free_ptr = 1;
		ret = PBSE_SYSTEM;
		goto err;
	}

	/* determine who we are */
	/*
	 * we need to do this here as well since not all threads would call
	 * connect, when other threads share the connection handle created by
	 * one thread
	 */
	pbs_current_uid = getuid();
	if ((pw = getpwuid(pbs_current_uid)) == NULL) {
		free_ptr = 1;
		ret = PBSE_SYSTEM;
		pbs_client_thread_unlock_conf();
		goto err;
	}
	if (strlen(pw->pw_name) > (PBS_MAXUSER - 1)) {
		free_ptr = 1;
		ret = PBSE_BADUSER;
		pbs_client_thread_unlock_conf();
		goto err;
	}
	strcpy(ptr->th_pbs_current_user, pw->pw_name);

	if (pthread_setspecific(key_tls, ptr) != 0) {
		ret = PBSE_SYSTEM;
		pbs_client_thread_unlock_conf();
		goto err;
	}
	if (pbs_client_thread_unlock_conf() != 0) {
		ret = PBSE_SYSTEM;
		goto err;
	}

	if (pthread_once(&post_init_key_once, __post_init_thread_data) != 0) {
		ret = PBSE_SYSTEM;
		goto err;
	}

	return 0;

err:
	/*
	 * this is a unlikely case and should not happen unless the system is
	 * low on memory before even before the program started, or if there
	 * are bugs in the pthread calls
	 */

	/*
	 * since thread init could not be set, set back single threaded mode,
	 * so that at least the pbs_errno etc would work for the client side
	 * to read the error code out of it.
	 */
	pbs_client_thread_set_single_threaded_mode();
	if (free_ptr) {
		free(ptr->th_dis_buffer);
		free(ptr);
	}
	pbs_errno = ret; /* set the errno so that client can access it */
	return ret;
}


/**
 * @brief
 *	Free the attribute error list from TLS
 *
 * @par Functionality:
 *      Helper function to free the list of attributes in error that is stored
 *	in the threads TLS
 *
 * @param[in]	errlist  - pointer to the array of attributes structures to free
 *
 * @return	void
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
void
free_errlist(struct ecl_attribute_errors *errlist)
{
	int i;
	struct attropl * attr;
	if (errlist) {
		/* iterate through the error list and free everything */
		for (i=0; i < errlist->ecl_numerrors; i++) {
			attr = errlist->ecl_attrerr[i].ecl_attribute;
			if (attr) {
				/* free the attropl structure pointer */
				if (attr->name != NULL) free(attr->name);
				if (attr->resource != NULL)
					free(attr->resource);
				if (attr->value != NULL) free(attr->value);
				free(attr);
			}
			/* free the errmsg pointer */
			if (errlist->ecl_attrerr[i].ecl_errmsg)
				free(errlist->ecl_attrerr[i].ecl_errmsg);
		}
		if (errlist->ecl_attrerr)
			free(errlist->ecl_attrerr);
		free(errlist);
	}
}

/**
 * @brief
 *	Destroy the thread context data
 *
 * @par Functionality:
 *      Called by pbs_client_thread_destroy_context to free the TLS data
 *	allocated for this thread
 *
 * @see __init_thread_data
 *
 * @param[in]	p - pointer to TLS data area
 *
 * @return	void
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
static void
__pbs_client_thread_destroy_thread_data(void *p)
{
	struct pbs_client_thread_connect_context *th_conn, *temp;
	struct pbs_client_thread_context *ptr =
		(struct pbs_client_thread_context *) p;

	if (ptr) {
		free_errlist(ptr->th_errlist);

		if (ptr->th_cred_info)
			free(ptr->th_cred_info);

		if (ptr->th_dis_buffer)
			free(ptr->th_dis_buffer);

		free_node_pool(ptr->th_node_pool);

		th_conn = ptr->th_conn_context;
		while (th_conn) {
			if (th_conn->th_ch_errtxt)
				free(th_conn->th_ch_errtxt);

			temp = th_conn;
			th_conn = th_conn->th_ch_next;
			free(temp);
		}
		free(ptr);
	}
}

/**
 * @brief
 *	Add a the connection related data to the TLS
 *
 * @par Functionality:
 *	Allocates memory for struct connect_context, initializes the members.
 *      Finally adds the structure to a linked list in the thread_context
 *      headed by the member th_conn_context. See struct thread_context for
 *      more information.
 *	Called by __pbs_cleint_thread_init_connect_context/
 *	__pbs_client_thread_lock_connection functions to add a connection
 *	context to the TLS data
 *
 * @see __pbs_client_thread_init_connect_context\n
 *	__pbs_client_thread_lock_connection\n
 *
 * @param[in]	connect - the connection identifier
 *
 * @retval	Address of the newly allocated node (success)
 * @retval	NULL (failure)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
struct pbs_client_thread_connect_context *
pbs_client_thread_add_connect_context(int connect)
{
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	struct pbs_client_thread_connect_context *new =
		malloc(sizeof(struct pbs_client_thread_connect_context));
	if (new == NULL)
		return NULL;

	new->th_ch = connect;
	new->th_ch_errno = 0;
	new->th_ch_errtxt = NULL;
	if (p->th_conn_context)
		new->th_ch_next = p->th_conn_context;
	else
		new->th_ch_next = NULL;

	p->th_conn_context = new; /* chain at the head */

	return new;
}

/**
 * @brief
 *	Remove the data associated with the connection from TLS
 *
 * @par Functionality:
 *	Deallocates memory for struct connect_context for the connection handle
 *	specified. The node is deallocated from the linked list headed by
 *	member th_conn_context in struct thread_context. For more information
 *	see definition of struct thread_context.
 *	Called by __pbs_client_thread_destroy_connect_context functions to
 *	remove a connection context from the TLS (struct thread_context)
 *
 * @see	__pbs_client_thread_destroy_connect_context
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @retval	0  -  (success)
 * @retval	-1 -  (failure)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
int
pbs_client_thread_remove_connect_context(int connect)
{
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	struct pbs_client_thread_connect_context *prev = NULL;
	struct pbs_client_thread_connect_context *ptr = p->th_conn_context;
	while (ptr) {
		if (ptr->th_ch == connect) {
			if (prev)
				prev->th_ch_next = ptr->th_ch_next;
			else
				p->th_conn_context = ptr->th_ch_next;

			if (ptr->th_ch_errtxt)
				free(ptr->th_ch_errtxt);

			free(ptr);
			return 0;
		}
		prev = ptr;
		ptr = ptr->th_ch_next;
	}
	return -1;
}

/**
 * @brief
 *	Find the address of connection context data
 *
 * @par Functionality:
 *	The node is searched from the linked list headed by the
 *	th_conn_context member of struct thread_context (TLS data)
 *	Called by functions __pbs_client_thread_lock_connection,
 *	__pbs_client_thread_unlock_connection,
 *	pbs_geterrmsg to locate the node associated to connection handle
 *	specified.
 *
 * @see	__pbs_client_thread_lock_connection\n
 *	__pbs_client_thread_unlock_connection
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @retval	Address of the node  -  (success)
 * @retval	NULL, node not found -  (failure)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
struct pbs_client_thread_connect_context *
pbs_client_thread_find_connect_context(int connect)
{
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	struct pbs_client_thread_connect_context *ptr = p->th_conn_context;
	while (ptr) {
		if (ptr->th_ch == connect)
			return ptr;
		ptr = ptr->th_ch_next;
	}
	return NULL;
}

/**
 * @brief
 *	Initializes the connection related data
 *
 * @par Functionality:
 *	1. Initialize the ch_mutex member of the struct connection to a
 *		recursively lockable mutex
 *	2. Calls pbs_client_thread_add_connect_context to add connect context
 *		to the linked list of connections headed by the member
 *		th_ch_conn_context of struct thread_context (TLS data).
 *
 * @see	pbs_client_thread_add_connect_context\n
 *	thread_context
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @retval	0  -  (success)
 * @retval	pbs_errno -  (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_init_connect_context(int connect)
{
	/* create an entry inside the thread context for this connect */
	if (pbs_client_thread_add_connect_context(connect) == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}

/**
 * @brief
 *	Destroys the connection related data
 *
 * @par Functionality:
 *	1. Destroy the ch_mutex member of the struct connection
 *	2. Calls pbs_client_thread_remove_connect_context to remove connection
 *		context from the linked list of connections headed by the member
 *		th_ch_conn_context of struct thread_context (TLS data).
 *
 * @see	pbs_client_thread_add_connect_context\n
 *	pbs_client_thread_remove_connect_context\n
 *	thread_context
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @retval	0  -  (success)
 * @retval	pbs_errno -  (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_destroy_connect_context(int connect)
{
	/* dont ever destroy a connect level mutex */
	/* remove entry frm thread context for this connect */
	if (pbs_client_thread_remove_connect_context(connect) != 0) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}

/**
 * @brief
 *	Fetches the thread context data pointer
 *
 * @par Functionality:
 *	Convenience function to get the thread context data of type
 *	struct thread_context from the TLS using pthread_getspecific call.
 *	In case pthread_getspecific returns NULL, it means that the thread_init
 *	function was not called before calling this method. This can happen
 *	when clients might access pbs_errno before calling any IFL API. In such
 *	case, pbs_client_thread_init_thread_context is called to initialize the
 *	the TLS data and then a call to pbs_client_thread_get_context_data gives
 *	us the address to the thread context data for this thread.
 *
 * @see	pbs_client_thread_init_thread_context\n
 *	pbs_client_thread_context
 *
 * @retval	Address of the thread context data
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static struct pbs_client_thread_context *
__pbs_client_thread_get_context_data(void)
{
	struct pbs_client_thread_context *p = NULL;
	p = pthread_getspecific(key_tls);
	if (p == NULL) {
		/* this thread has not entered pthread init, so call it */
		/* if this fails, it sets local context */
		(void) pbs_client_thread_init_thread_context();
		p = pbs_client_thread_get_context_data();
	}
	return p;
}

/**
 * @brief
 *	Locks the connection level mutex
 *
 * @par Functionality:
 *	1. Locks ch_mutex member (recursive mutex) of the connection structure
 *		thus providing the semantics of locking a connection
 *	2. If the connection context was not previously added to TLS area for
 *		this thread (if this is the first call to lock_connection) then
 *		add it to the TLS by calling
 *		pbs_client_thread_add_connect_context())
 *
 * @see	pbs_client_thread_find_connect_context\n
 *	pbs_client_thread_add_connect_context
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_lock_connection(int connect)
{
	struct pbs_client_thread_connect_context *con;
	pthread_mutex_t *mutex = NULL;

	if ((mutex = get_conn_mutex(connect)) == NULL) {
		return (pbs_errno = PBSE_SYSTEM);
	}

	if (pthread_mutex_lock(mutex) != 0) {
		return (pbs_errno = PBSE_SYSTEM);
	}

	con = pbs_client_thread_find_connect_context(connect);
	if (con == NULL) {
		/*
		 * add the connect context to thread, since this thread is
		 * sharing a connection handle amongst threads
		 */
		if ((con = pbs_client_thread_add_connect_context(connect))
			== NULL) {
			(void)pthread_mutex_unlock(mutex);
			return (pbs_errno = PBSE_SYSTEM);
		}
	}

	/* copy stuff from con to connection handle slot */
	set_conn_errno(connect, con->th_ch_errno);
	if (set_conn_errtxt(connect, con->th_ch_errtxt) != 0) {
		(void)pthread_mutex_unlock(mutex);
		return (pbs_errno = PBSE_SYSTEM);;
	}
	return 0;
}

/**
 * @brief
 *	Unlocks the connection level mutex
 *
 * @par Functionality:
 *	1. Removes the connection context from the TLS for this thread by
 *		calling pbs_client_thread_remove_connect_context()
 *	2. Unlocks the ch_mutex member (recursive mutex) of connection structure
 *		thus providing the semantics of unlocking a connection
 *
 * @param[in]	connect - the connection identifier from pbs_connect call
 *
 * @see	pbs_client_thread_find_connect_context
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_unlock_connection(int connect)
{
	pthread_mutex_t *mutex = NULL;
	struct pbs_client_thread_connect_context *con = NULL;
	char *errtxt = NULL;

	if ((mutex = get_conn_mutex(connect)) == NULL) {
		return (pbs_errno = PBSE_SYSTEM);
	}

	con = pbs_client_thread_find_connect_context(connect);
	if (con == NULL) {
		return (pbs_errno = PBSE_SYSTEM);
	}

	/* copy stuff from con to connection handle slot */
	con->th_ch_errno = get_conn_errno(connect);
	errtxt = get_conn_errtxt(connect);
	if (errtxt) {
		if (con->th_ch_errtxt)
			free(con->th_ch_errtxt);
		con->th_ch_errtxt = strdup(errtxt);
		if (con->th_ch_errtxt == NULL)
			return (pbs_errno = PBSE_SYSTEM);
	}

	if (pthread_mutex_unlock(mutex) != 0) {
		return (pbs_errno = PBSE_SYSTEM);
	}

	return 0;
}

/**
 * @brief
 *	Locks the connection table level mutex
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_lock_conntable(void)
{
	if (pthread_mutex_lock(&pbs_client_thread_conntable_mutex) != 0) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}


/**
 * @brief
 *	Unlocks the connection table level mutex
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_unlock_conntable(void)
{
	if (pthread_mutex_unlock(&pbs_client_thread_conntable_mutex) != 0) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}


/**
 * @brief
 *	Locks the configuration level mutex (conf_mutex)
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_lock_conf(void)
{
	if (pthread_mutex_lock(&pbs_client_thread_conf_mutex) != 0) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}


/**
 * @brief
 *	Unlocks the configuration level mutex (conf_mutex)
 *
 * @retval	0 (success)
 * @retval	pbs_errno (failure)
 *
 * @par Side-effects:
 *	Sets pbs_errno
 *
 * @par Reentrancy:
 *	Reentrant
 */
static int
__pbs_client_thread_unlock_conf(void)
{
	if (pthread_mutex_unlock(&pbs_client_thread_conf_mutex) != 0) {
		pbs_errno = PBSE_SYSTEM;
		return pbs_errno;
	}
	return 0;
}

/**
 * @brief
 *	Returns the address of dis_buffer used in dis communication.
 *
 * @par Functionality:
 *	This function returns the address of the per thread dis_buffer location
 *	from the TLS by calling @see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the dis_buffer from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
char *
__dis_buffer_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (p->th_dis_buffer);
}


/**
 * @brief
 *	Returns the address of pbs_errno.
 *
 * @par Functionality:
 *	This function returns the address of the per thread location of
 *	pbs_errno variable from the TLS by calling
 *	@see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_errno from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
int *
__pbs_errno_location(void)
{
	/*
	 * returns real thread context or data from a global structure called
	 * local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (&p->th_pbs_errno);
}


/**
 * @brief
 *	Returns the address of pbs_server.
 *
 * @par Functionality:
 *	This function returns the address of the per thread location of
 *	pbs_server from the TLS by calling
 *	@see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_server from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
char *
__pbs_server_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (p->th_pbs_server);
}

/**
 * @brief
 *	Returns the address of pbs_current_user.
 *
 * @par Functionality:
 *	This function returns address of the per thread location of
 *	pbs_current_user from the TLS by calling
 *	@see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_current_user from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
char *
__pbs_current_user_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (p->th_pbs_current_user);
}

/**
 * @brief
 *	Returns the address of pbs_tcp_timeout.
 *
 * @par Functionality:
 *	This function returns address of the per thread location of
 *	pbs_tcp_timeout from the TLS by calling
 *	@see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_tcp_timeout from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
time_t *
__pbs_tcptimeout_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (&p->th_pbs_tcp_timeout);
}


/**
 * @brief
 *	Returns the address of pbs_tcp_interrupt.
 *
 * @par Functionality:
 *	This function returns address of the per thread location of
 *	pbs_tcp_interrupt from the TLS by calling
 *	@see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_tcp_interrupt from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
int *
__pbs_tcpinterrupt_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (&p->th_pbs_tcp_interrupt);
}


/**
 * @brief
 *	Returns the location of pbs_tcp_errno.
 *
 * @par Functionality:
 *	This function returns address of the per thread location of
 *	pbs_tcp_errno from the TLS
 *	by calling @see __pbs_client_thread_get_context_data
 *
 * @retval	Address of the pbs_tcp_errno from TLS (success)
 *
 * @par Side-effects:
 *	None
 *
 * @par Reentrancy:
 *	Reentrant
 */
int *
__pbs_tcperrno_location(void)
{
	/*
	 * returns real thread context or data from a global structure
	 * called local_thread_context
	 */
	struct pbs_client_thread_context *p =
		pbs_client_thread_get_context_data();
	return (&p->th_pbs_tcp_errno);
}
