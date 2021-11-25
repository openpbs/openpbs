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
 * @file	cs_standard.c
 * @brief
 * cs_standard.c - Standard PBS Authentication Module
 * 	  Authentication provided by this module is the standard (pbs_iff)
 * 	  authentication used in vanilla PBS.  Internal security interface
 * 	  (Hooks) are for the most part stubs which return CS_SUCCESS
 */

/* File is to be gutless if PBS not built vanilla w.r.t. security */

#include <pbs_config.h>
#include <stddef.h>
#include <sys/types.h>
#include "libsec.h"

#if (!defined(PBS_SECURITY) || (PBS_SECURITY == STD)) || (defined(PBS_SECURITY) && (PBS_SECURITY == KRB5))

/* system includes */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>

#if defined(HAVE_SYS_IOCTL_H)
#include <sys/ioctl.h>
#include <sys/uio.h>
#endif

#include <netdb.h>
#include <sys/socket.h>
#include <netdb.h>

/* PBS includes */

#include <pbs_error.h>

/*------------------------------------------------------------------------
 * interface return codes,...
 *------------------------------------------------------------------------
 * see pbs/src/include/libsec.h
 */

/*------------------------------------------------------------------------
 * External functions
 *------------------------------------------------------------------------
 */

/*------------------------------------------------------------------------
 * Global symbols and default "evaluations"
 *------------------------------------------------------------------------
 */
/**
 * @brief
 * 	Default logging function
 */
void
sec_cslog(int ecode, const char *caller, const char *txtmsg)
{
	return;
}

void (*p_cslog)(int ecode, const char *caller, const char *txtmsg) = sec_cslog;

/*========================================================================
 * PBS hook functions
 * CS_read	   - read encrypted data, decrypt and pass result to PBS
 * CS_write	   - encrypt PBS data, and write result
 * CS_client_auth  - authenticate to a server, authenticate server
 * CS_server_auth  - authenticate a client, authenticate to client
 * CS_close_socket - release per-connection security data
 * CS_close_app    - release application security data
 * CS_client_init  - initialize client global data
 * CS_server_init  - initialize server global data
 * CS_verify       - verify a user id (still to be developed)
 * CS_remap_ctx - remap connection security context to a new descriptor.
 *------------------------------------------------------------------------
 */
/**
 * @brief
 *	CS_read - read data
 *
 * @par	call:
 *	r = CS_read(fid,buf,len);
 *
 * @param[in]	fid	- file id to read from
 * @param[in]	buf	- address of the buffer to fill
 * @param[in]	len	- number of bytes to transfer
 *
 * @returns	int
 * @retval	- number of bytes read
 * @retval	CS_IO_FAIL (-1) on error
 *------------------------------------------------------------------------
 */

int
CS_read(int sd, char *buf, size_t len)
{

	return (read(sd, buf, len));
}

/**
 * @brief
 * 	CS_write - write data
 *
 * @par	call:
 *      r = CS_write ( fid, buf, len )
 *
 * @param[in]	fid     - file id to write to
 * @param[in]	buf     - address of the buffer to write
 * @param[in]	len     - number of bytes to transfer
 *
 * @returns	int
 * @retval	- number of bytes read
 * @retval	CS_IO_FAIL (-1) on error
 *------------------------------------------------------------------------
 */

int
CS_write(int sd, char *buf, size_t len)
{
	return (write(sd, buf, len));
}

/**
 * @brief
 * 	CS_client_auth - stub interface for STD authentication to a remote
 *
 * @par	server.:
 *	r = CS_client_auth ( fd );
 *
 * @param[in]	fd	- socket file id
 *
 * @returns	int
 * @retval	- CS_AUTH_USE_IFF
 *
 * @par	Note:  upon getting the above return value, the calling code should
 *	call PBSD_authenticate (which issues a read  popen of pbs_iff)
 *	and respond accordingly to its return value -  close down the
 *	connection's security, close the socket.  Otherwise,continue
 *	with the steps that follow a successful authentication..
 *------------------------------------------------------------------------
 */

int
CS_client_auth(int sd)
{
	return (CS_AUTH_USE_IFF);
}

/**
 * @brief
 * 	CS_server_auth - authenticate to a client
 *
 * @par	call:
 *	r = CS_server_auth(fd);
 *
 * @param[in]	fd	- socket file id
 *
 * @returns	int
 * @retval	- CS_AUTH_CHECK_PORT
 *
 * @par	Note:  upon getting the above return value, the calling code should
 *	check if the remote port is in the privileged range and
 *	proceed accordingly.
 *------------------------------------------------------------------------
 */

int
CS_server_auth(int sd)
{

	return (CS_AUTH_CHECK_PORT);
}

/**
 * @brief
 * 	CS_close_socket - cleanup security blob when closing a socket.
 *
 * @par	call:
 * 	r = CS_close_socket ( fd );
 *
 * @param[in]	fd	- socket file id
 *
 * @return	int
 * @retval	status result, 0 => success
 *
 * @par	note:
 * 	The socket should still be open when this function is called.
 * 	The pointer to the security blob may be modified, hence pctx
 * 	points to the pointer to the blob.
 *------------------------------------------------------------------------
 */

int
CS_close_socket(int sd)
{
	/*
	 * For standard PBS security we don't have a need for a
	 * "per connection" security context
	 */

	return (CS_SUCCESS);
}

/**
 * @brief
 * 	CS_close_app - the global cleanup function
 *
 * @par	call:
 *	r = CS_close_app();
 *
 * @returns	int
 * @retval	- CS_SUCCESS
 *
 */

int
CS_close_app(void)
{
	return (CS_SUCCESS);
}

/**
 * @brief
 *	CS_client_init - the client initialization function for global security
 * 		    data
 * @par	usage:
 * 	r = CS_client_init();
 *
 * @returns 	int
 * @retval	initialization status
 *
 */

int
CS_client_init(void)
{

	return (CS_SUCCESS); /* always return success if no error */
}

/**
 * @brief
 *	CS_server_init - the server initialization function for global security
 * 		    data
 * @par	usage:
 * 	r = CS_server_init();
 *
 * @returns	int
 * @retval	initialization status
 *
 */

int
CS_server_init(void)
{
	return (CS_SUCCESS);
}

/**
 * @brief
 * 	CS_verify - verify user is authorized on host
 * @par	call:
 * 	r = CS_verify ( ??? );
 *
 * @returns	int
 * @retval	verification status
 * @retval	CS_SUCCESS	    => start the user process
 * @retval	CS_FATAL_NOAUTH   => user is not authorized
 * @retval	CS_NOTIMPLEMENTED => do the old thing (rhosts)
 *
 */

int
CS_verify()
{
	return (CS_SUCCESS);
}

/**
 * @brief
 * 	CS_remap_ctx - interface is available to remap connection's context
 * 	to a new descriptor.   Old association is removed from the tracking
 * 	mechanism's data.
 *
 * Should the socket descriptor associated with the connection get
 * replaced by a different descriptor (e.g. mom's call of the FDMOVE
 * macro for interactive qsub job) this is the interface to use to
 * make the needed adjustment to the tracking table.
 *
 * @param[in] sd     connection's original socket descriptor
 * @param[in] newsd  connection's new socket descriptor
 *
 * @return	int
 * @retval	CS_SUCCESS
 * @retval	CS_FATAL
 *
 * @par	Remark:
 *	If the return value is CS_FATAL the connection should be
 *	CS_close_socket should be called on the original descriptor
 *	to deallocate the tracking table entry, and the connection
 *	should then be closed.
 *------------------------------------------------------------------------
 */

int
CS_remap_ctx(int sd, int newsd)
{
	/*
	 * For standard PBS security we don't have a need for a
	 * "per connection" security context remapping
	 */

	return (CS_SUCCESS);
}

#endif /* undefined( PBS_SECURITY ) || ( PBS_SECURITY == STD ) */
