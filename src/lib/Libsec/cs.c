/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */

/**
 * @file	cs.c
 * @brief
 * cs.c - Customer Authentication Module
 * 	  Kerberos initialization, authentication, encryption
 * 	  and cleanup
 * @author Jesse Pollard
 * @par	Modification/Additions:
 * 		Cas Lesiak
 */

#include <pbs_config.h>
#include <stddef.h>
#include <errno.h>
#include <sys/types.h>
#include "libsec.h"

/* Purpose of the following "#if" is to make this file gutless if
 * PBS build configuration did not specify one of the two possible
 * kerberization choices ( --enable-security=X,  X is either KAUTH or KCRYPT )
 *
 * If this file is gutless file cs_standard.c (want standard pbs_iff security)
 * will not be gutless and visa-versa.
 */

#if defined(PBS_SECURITY) && ((PBS_SECURITY == KAUTH ) || (PBS_SECURITY == KCRYPT ) )

/* system includes */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>
#include <krb5.h>
#include <com_err.h>

#if defined(HAVE_SYS_IOCTL_H)
#include <sys/ioctl.h>
#include <sys/uio.h>
#endif

#include <netdb.h>
#include <sys/socket.h>
#include <arpa/inet.h>

/*========================================================================
 * Kerberos related constants...
 *------------------------------------------------------------------------
 * KEYTAB - is the path to the batch systems keytab file, which doesn't
 * 	    have to be the same as the system keytab file, though I expect
 * 	    it to be the same for most installations
 * DEFAULT_LIFETIME - the time to request for a TGT on behalf of a server
 * 	    This time may also be set by policy in the KDC, which will
 * 	    override the request. It really should be longer than
 * 	    RENEWTIME but doesn't have to be. 10 hours allows the server
 * 	    to use a TGT to obtain service tickets without also having
 * 	    to always get a TGT first (the TGT is cached). Getting a
 * 	    TGT may take several seconds the first time.
 * RENEWTIME - the number of minutes before expiration of the servers
 * 	    TGT to obtain a new ticket. This isn't exact, but 10 minutes
 * 	    should be long enough to obtain and use a service ticket.
 * 	    Once the lifetime of a TGT is less than 10 minutes or expired,
 * 	    a new one will be obtained.
 * SERVICENAME - This is the key name for the batch system. It could be
 * 	    "host" in which case, the host/<hostname> keytab entry will
 * 	    be used for both batch and interactive use. Using a separate
 * 	    name allows batch to be controled at the KDC separately from
 * 	    interactive use. (Interactive use can be disabled by marking
 * 	    the host/hostname principal to "disabled", while still
 * 	    allowing batch jobs to continue.)
 * CACHENAME - Identifies the server Kerberos credential cache. In this
 * 	    case, it specifies a memory resident cache so that no
 * 	    server credentials derived from a keytab appear on disk.
 * KEY_USAGE - an application key used to permute the encryption
 * 	    algorithms. This number must be used by all applications
 * 	    that communicate with the corresponding server.
 * MAXSOCKADDR - the number of bytes needed for the largest socket
 * 	    address. This is taken from W. Richard Stevens, "UNIX Network
 * 	    Programming" vol 1, 1998. It should be large enough even
 * 	    for an IPv6 address returnde by the getpeername system call.
 *------------------------------------------------------------------------
 */

#define KEYTAB	"/etc/pbs.keytab"	/* keytab file to use		*/
#define DEFAULT_LIFETIME "10h 0m 0s"	/* default lifetime		*/

#define RENEWTIME	10*60	/* renew TGT 10 minutes before expires	*/

#define SERVICENAME	 "pbs"	/* service for tickets			*/
/* the SERVICE name part is "pbs", which*/
/* gets combined with the local host's  */
/* name to produce: "pbs/<hostname>"    */
/* This is the keytab entry needed 	*/

#define CACHENAME  "MEMORY: PBS server cache" /* Kerberos cache type	*/

#define KEY_USAGE	2001	/* Kerberos usage key shared between	*/
/* client and server			*/
#define MAXSOCKADDR	128	/* maximum socket address size		*/

/*------------------------------------------------------------------------
 * interfacing constants...
 *------------------------------------------------------------------------
 * see pbs/src/include/libsec.h
 */

/*------------------------------------------------------------------------
 * Internal constants: security blob flag usage
 *------------------------------------------------------------------------
 */

#define F_INIT		00001	/* structure is initialized		*/
#define F_SERVER	00002	/* initialized as a server		*/
#define F_CLIENT	00004	/* initialized as a client		*/


/*------------------------------------------------------------------------
 * External functions
 *------------------------------------------------------------------------
 * PBS library functions used in logging problems with security
 */

/*
 * void  cs_logerr ( errnum, id, txt )
 *
 * where:
 * 	errnum	- one of two choices:
 * 		  an error number suitable for str_error.
 * 		  -1 if don't care about the str_errording  message.
 * 	id	- identification string to identify from where the
 * 		  logging function is being called.
 * 	txt	- a textual string to appended to the new logfile line
 *
 * note: The maximum size of an output log line is 4096 bytes (defined by
 *	 LOG_BBUF_SIZE, in the PBS include file "log.h")
 *
 */

/**
 * @brief
 *------------------------------------------------------------------------
 * internal structures
 *------------------------------------------------------------------------
 * buffer allocation and header information
 * DBUF is a buffer header used for allocation, deallocation, and
 * 	data packing.
 * Allocation is performed by "buffer_needs" to ensure that a buffer
 * 	has sufficient space allocated to it.
 * Deallocation is performed by "buffer_free" when the buffer pointer is
 * 	not NULL, and sets the alloc and used counts to 0.
 * Data packing is possible by using the function "buffer_append" to
 *	append new data to the end of the current space. The "used" field
 *	is updated, as is the "alloc" if resizing is done.
 *
 * The buffer is not restricted to just these functions. The "used"
 * field can be manipulated directly, but don't count on "buffer_append"
 * to work coorectly in that case.
 *
 * It is not recommended to do anything with the "alloc" field. Use the
 * buffer_needs and buffer_free functions.
 *
 * The fucntion "buffer_needs" will only allocate memory in chunks of
 * "BUFFER_MIN" size.
 *------------------------------------------------------------------------
 */

typedef struct {
	int			alloc;		/* size of buf		*/
	int			used;		/* bytes used		*/
	unsigned char		*buffer;	/* the buffer		*/
} DBUF;

#define BUFFER_MIN	1024


/*------------------------------------------------------------------------
 * internal structure used by library's mechanism for keeping track
 * of a connection's context
 *------------------------------------------------------------------------
 */
typedef struct	soc_ctx {
	unsigned int sc_flg;	/*bit flags: 0x1 == "inuse"*/
	int	sc_sd;		/*socket descriptor*/
	void	*sc_ctx;	/*associated security context*/
} SOC_CTX;

/*
 * Internal constants related to the library's internal mechanism
 * for keeping track of connection contexts.
 */
#define TRK_SUCCESS		0
#define TRK_SUCCESS_INUSE	1
#define TRK_SUCCESS_FREE	2
#define TRK_TABLE_FULL		3
#define TRK_TBL_ERROR		4
#define TRK_EXPAND_FAIL		5
#define TRK_BAD_ARG		6

/*------------------------------------------------------------------------
 *prototypes of internal functions for (socket, context) tracking
 *------------------------------------------------------------------------
 */

static int	trak_tbl_expand(int sd);
static int	trak_set_ent(int sd, void *ctx);
static int	trak_rls_ent(int sd);
static SOC_CTX	*trak_find_ent(int sd, int *status);
static SOC_CTX	*trak_find_free(int sd, int *status);
static void	*trak_return_ctx(int sd, int *status);


/*------------------------------------------------------------------------
 * Security context structures
 *------------------------------------------------------------------------
 * part 1, the per-connection security data
 *------------------------------------------------------------------------
 */

typedef struct sec_ctx{
	unsigned int		flags;		/* blob control flags	*/
	struct sec_ctx		*chain;		/* links blobs		*/
	krb5_auth_context	auth_context;	/* authentication	*/
	krb5_ap_rep_enc_part	*reply;		/* encrypted reply	*/
	krb5_data		message;	/* reply from server	*/
	krb5_data		uticket;	/* client ticket	*/
	krb5_ticket		*ticket;	/* server ticket	*/
	krb5_flags		kflags;		/* request flags	*/
	char			*identity;	/* users identity string*/
	char			hostname[128];	/* remote host name	*/

	/* encryption data */

	size_t			blocksize;	/* encyrption blocksize	*/
	krb5_data		input_ivec;	/* chaining vector	*/
	krb5_data		output_ivec;	/* chaining vector	*/
	krb5_keyblock		*key;		/* encryption keys	*/

	/* configuration parameters */

	char			*host;		/* host to connect to	*/

	/* unrea decrypted data */

	DBUF			decbuf;		/* decrypted buffer	*/
	int			curr_read;	/* current read index	*/
} SEC_ctx;

/* part 2, the application global security data */

typedef struct {
	unsigned int		flags;		/* blob control flags	*/

	/* general variables */

	krb5_context		context;	/* kerberos context	*/
	krb5_error_code		retval;		/* kerberos status	*/
	krb5_ccache		cc;		/* credential cache	*/
	krb5_keytab		kt;		/* keytab reference	*/
	krb5_creds		creds;		/* keytab based creds	*/
	krb5_principal		server;		/* server principal	*/
	char			*cachefile;	/* user ticket cache	*/
	int			readerror;	/* input error code	*/

	/* data buffers */
	/* read/write buffer handling */

	DBUF			inbuf;		/* encrypted buffer	*/

	/* output buffers */

	int			writeerror;	/* output error code	*/
	DBUF			outbuf;		/* output buffer	*/

	DBUF			encoutbuf;	/* encrypted output	*/

	/* a single connection structure for client only use */

	SEC_ctx			single;		/* a single connection	*/
	SEC_ctx			*chain;		/* deallocation chain	*/
} KGlobal;

/* the global internal structure */

static KGlobal int_ctx;


/* the global internal tracking data*/

static	struct	soc_ctx	*ctx_trak = NULL;	/*tracking table*/
static	int	ctx_trak_max = 0;		/*num entries in ctx_trak*/

/* Global symbols and default "evaluations" */

void
sec_cslog(int ecode, const char *caller, const char *txtmsg)
{
	return;
}
void (*p_cslog)(int ecode, const char *caller, const char *txtmsg) = sec_cslog;


/*------------------------------------------------------------------------
 * unused utility functions (mostly for debugging aids)
 * 	To include these, just change the #if 0, to #if 1
 *------------------------------------------------------------------------
 */
 
/**
 * @brief
 * 	dump - utility function for debugging. This dumps the contents of a
 *	buffer
 *
 * @par	call:
 * 	dump(msg, length, data);
 *
 * @param[in] 	msg	- arbitrary text string to label the output
 * @param[in]	length	- the number of data bytes to dump
 * @param[in]	data	- pointer to the bytes to dump
 *
 */

static void
dump(char *msg, int  length, char *data)
{
	int i, j;
	int c;
	int dmp_cnt = 16;

	fprintf(stderr, "%s: length=%d\n ", msg, length);
	for (i = 0; i < length; i++) {
		if ((i+1) % dmp_cnt == 1 && i > 0) {
			fprintf(stderr, "  ");
			for (j = i - dmp_cnt; j < i; j++) {
				c = data[j];
				if (c < ' ' || c > 0x7f) c = '.';
				fprintf(stderr, "%c", c);
			}
			fprintf(stderr, "\n ");
		}
		fprintf(stderr, "%2.2hhx ", data[i]);
	}

	/* pad possible partial last line, and put the text */

	j = length % dmp_cnt;
	if (j == 0) j = dmp_cnt;
	for (i = 0; i < dmp_cnt - j; i++)
		fprintf(stderr, "   ");
	fprintf(stderr, "  ");
	for (i = length - j; i < length; i++) {
		c = data[i];
		if (c < ' ' || c > 0x7f) c = '.';
		fprintf(stderr, "%c", c);
	}

	fprintf(stderr, "\n");
}

/*========================================================================
 * Internal Supporting Functions
 *------------------------------------------------------------------------
 * Buffer management functions
 *     buffer_needs	- rellocate a buffer if insufficient space is
 *			  available
 *     buffer_free	- deallocate a buffer
 *     buffer_append	- append a data chunk to the end of a buffer
 *------------------------------------------------------------------------
 */
 
/**
 * @brief
 * 	buffer_needs - rellocate buffer if insufficient space is available
 *
 * @par	call:
 *	r = buffer_needs(buf,len);
 *
 * @param[in]	buf	- pointer to the buffer structure
 * @param[in]	len	- number of free bytes required
 *
 * @return	int
 * @retval	- allocation status:
 * @retval	0 => success
 * @retval	otherwise allocation failure
 *
 * @par	note:
 *	If the alloc - length fields in the buffer structure is less than
 *		the required number of bytes, then the buffer will be
 *		expanded. The contents of the buffer itself will remain
 *		but the alloc field will have been altered.
 *	The contents of the buffer will not be altered by reallocation.
 *		This is intentional to allow for packing multiple data
 *		chunks together.
 *	Buffers never decrease in size - only increase. A reused buffer
 *		is not deallocated to resize it downward. This is
 *		done to minimize fragmentation.
 * @par	ASSUMPTIONS:
 * 	The buffer structure is always initialized to 0, and with a
 * 		null pointer to the data string.
 *------------------------------------------------------------------------
 */

static int
buffer_needs(DBUF *buf, int len)
{
	int	size;
	unsigned char *p;

	/* compute a minimum buffer allocation */

	if (len % BUFFER_MIN) size = 1;
	else size = 0;
	size = ((len / BUFFER_MIN) + size) * BUFFER_MIN;

	/* now allocate a data buffer if necessary */

	if (size > buf->alloc) {
		if (buf->buffer) {
			p = realloc(buf->buffer, size);
			if (NULL == p) return (1);
			buf->buffer = p;
		} else {
			buf->buffer = calloc(1, size);
			buf->used = 0;
			if (NULL == buf->buffer)
				return (1);
		}
		buf->alloc = size;
	}
	return (0);
}

/**
 * @brief
 * 	buffer_free - deallocate a buffer
 *
 * @par	call:
 * 	r = buffer_free(buf);
 * 
 * @param[in]	buf	- pointer to the buffer structure
 *
 * @return	int
 * @retval	- always 0 (for now).
 *------------------------------------------------------------------------
 */

static int
buffer_free(
	DBUF	*buf)
{
	if (buf->buffer) free(buf->buffer);
	buf->buffer = NULL;
	buf->alloc = 0;
	buf->used = 0;

	return (0);
}

/**
 * @brief
 * 	buffer_append - append a data chunk to the end of a buffer
 *
 * @par	call
 * 	r = buffer_append(buf,len,data);
 * 
 * @param[in]	buf	- pointer to the buffer structure
 * @param[in]	len	- number of bytes to be appended
 * @param[in]	data	- pointer to the data to be appended
 *
 * @returns	int
 * @retval	- status result
 * @retval	0	=> data has been added
 * @retval	otherwise error, and no data is appended
 * 
 * @par	note:
 * 	This function assumes that the "used" field in the buffer
 * 		structure is valid.
 *------------------------------------------------------------------------
 */

static int
buffer_append(
	DBUF		*buf,
	int		len,
	unsigned char	*data)
{
	int		r, f;

	r = 0;
	f = buf->alloc - buf->used;
	if (len > f) {
		r = buffer_needs(buf, buf->used + len);
		if (! r) {
			memcpy(&buf->buffer[buf->used], data, len);
			buf->used += len;
		}
		/* note: nothing is done on allocation failure */
	} else {
		memcpy(&buf->buffer[buf->used], data, len);
		buf->used += len;
	}
	return (r);
}


/*------------------------------------------------------------------------
 * Internal functions supporting (descriptor, context) tracking mechanism
 *------------------------------------------------------------------------
 *
 * trak_tbl_expand - grow internal table to accomodate more descriptors
 * trak_set_ent - add data to a tracking table entry
 * trak_rls_ent - make tracking table entry available for reuse
 * trak_find_ent - find tracking table entry corresponding to descriptor
 * trak_find_free - find a free tracking table entry for the descriptor
 * trak_return_ctx - given a descriptor return the associated context
 *
 *------------------------------------------------------------------------
 */
 
/** 
 * @brief
 *	trak_tbl_expand - routine computes required size (number of entries)
 * 	of the tracking table based on the value of "sd".  If the current table
 * 	size is less than the computed value, the function will try to realloc
 * 	the table to the previously computed size.
 *
 * @param[in]	sd  socket descriptor value
 *
 * @return	int
 * @retval	0 	success
 * @retval	-1 	failure
 *------------------------------------------------------------------------
 */

static int
trak_tbl_expand(int sd)
{
	SOC_CTX	*tmpa;

	/* check for bad socket descriptor */

	if (sd < 0)
		return -1;

	if (sd >= ctx_trak_max) {

		int	hold = ctx_trak_max;

		ctx_trak_max = sd+10;

		if (ctx_trak == NULL) {
			ctx_trak = (struct soc_ctx *)calloc(ctx_trak_max,
				sizeof(SOC_CTX));
			if (ctx_trak == NULL) {
				ctx_trak_max = hold;
				return -1;
			}
		}
		else {
			tmpa = (struct soc_ctx *)realloc(ctx_trak,
				ctx_trak_max*sizeof(struct soc_ctx));
			if (tmpa != NULL) {

				ctx_trak = tmpa;
				memset(&ctx_trak[hold], '\0',
					(ctx_trak_max - hold) * sizeof(struct soc_ctx));

			} else {
				ctx_trak_max = hold;
				return -1;
			}
		}
	}

	/* successfully expanded table or expansion not necessary */
	return 0;
}


/**
 * @brief
 * 	trak_set_ent - One of a small group of internal functions whose job
 * 	it is to manipulate an entry in the library's (socket, context)
 * 	tracking mechanism.
 *
 * @par	Functionality:
 * 	Given a socket descriptor and a void pointer to a connection
 * 	specific security context add the supplied information to the
 * 	appropriate entry in the tracking table.
 *
 * @param[in]   sd   socket descriptor value to associate with context
 * @param[in]  ctx  connection specific context associated with socket
 *
 * @return	int
 * @retval	0  	success
 * @retval	-1   	failure
 *------------------------------------------------------------------------
 */

static int
trak_set_ent(int sd, void *ctx)
{
	int	err = 0;
	SOC_CTX	*psc;

	if (sd < 0 || ctx == NULL)
		return -1;

	/* arguments OK, locate appropriate table entry */

	if ((psc = trak_find_free(sd, &err)) == NULL) {

		if (err != TRK_TABLE_FULL) {
			return -1;
		}
	}

	psc->sc_flg |= 0x1;
	psc->sc_sd = sd;
	psc->sc_ctx = ctx;
	return 0;
}

/**
 * @brief
 * 	trak_rls_ent - One of a handful of internal functions whose job
 * 	it is to manipulate an entry in the library's (socket, context)
 * 	tracking mechanism.
 *
 * @par	Functionality:
 * 	Given a socket descriptor value this function will find the allocted
 * 	entry for this descriptor and manipulate its members so that it is
 * 	once again available for allocation.
 *
 * @param[in]	sd    socket descriptor value
 *
 * @return	int
 * @retval	0    	success
 * @retval	code    if not successful one of the status codes:
 *          		TRK_TABLE_FULL, TRK_TBL_ERROR, TRK_BAD_ARG
 *
 * @par	Note: 
 *	Calling this function will not cause the security context
 *	associated with the allocted tracking entry to also
 *    	be released (freed).  Function trak_return_ctx may be
 *   	useful in this regard.
 *
 *------------------------------------------------------------------------
 */

static int
trak_rls_ent(int sd)
{
	int	status;
	SOC_CTX	*psc;

	psc = trak_find_ent(sd, &status);

	/*test for anticipated case first*/

	if (psc != NULL) {
		if (status == TRK_SUCCESS_INUSE ||
			status == TRK_SUCCESS_FREE) {

			psc->sc_flg &= ~(0x1);
			psc->sc_sd = -1;
			psc->sc_ctx = NULL;
			return 0;
		}
	}

	/*unexpected case*/
	return (status);
}

/**
 * @brief
 * 	trak_find_ent - This one of a handful of internal functions
 *	whose job it is to manipulate an individual entry in the
 * 	library's (socket, context) tracking mechanism.
 *
 * @par	Functionality:
 * 	Given socket descriptor value find (try) in the tracking table
 * 	the entry allocted to this descriptor, i.e. the entry whose
 * 	"sc_sd" member has "sd" as its value.  Note the entry may or
 * 	may not be "inuse".
 *
 * @param[in]	sd - socket descriptor value (this end of connection)
 * @param[in]	status - place to write back an integer status code
 * @param[in]	*status == TRK_SUCCESS   if successful
 *
 * @return	pointer to SOC_CTX
 * @retval	pointer to SOC_CTX structure associated with input "sd"	if found
 * @retval	NULL    						if such an entry is not found.
 *
 * @par	Status:    
 *	set to one of the codes:\n
 *	TRK_SUCCESS_INUSE, TRK_SUCCESS_FREE
 * 	TRK_TABLE_FULL, TRK_TBL_ERROR, TRK_BAD_ARG
 *------------------------------------------------------------------------
 */

static SOC_CTX	*
trak_find_ent(int sd, int *status)
{
	if (sd < 0) {
		if (status != NULL)
			*status = TRK_BAD_ARG;
		return NULL;
	}

	if (sd >= ctx_trak_max) {
		*status = TRK_TABLE_FULL;
		return NULL;
	}

	/*test for the expected case first*/

	if ((ctx_trak[sd].sc_flg & 0x1) &&
		ctx_trak[sd].sc_ctx != NULL) {

		/* found inuse entry */

		*status = TRK_SUCCESS_INUSE;
		return (ctx_trak + sd);
	}

	/*test for entry availability (free)*/

	if (!(ctx_trak[sd].sc_flg & 0x1) &&
		ctx_trak[sd].sc_ctx == NULL) {

		*status = TRK_SUCCESS_FREE;
		return (ctx_trak + sd);
	}

	*status = TRK_TBL_ERROR;
	return NULL;
}

/**
 * @brief
 * 	trak_find_free - One of a small group of internal functions
 * 	whose job it is to manipulate an entry in the library's
 * 	(socket, context) tracking mechanism.
 *
 * @par	Functionality:
 * 	Given socket descriptor value find (try) an unallocated entry
 * 	to associated with the descriptor.
 *
 * @param[in]	sd - socket descriptor value
 * @param[in]	status - place to write back an integer status code
 * @param[in] 	*status == TRK_SUCCESS if free entry found
 *
 * @return      pointer to SOC_CTX
 * @retval      pointer to SOC_CTX structure associated with input "sd" if found
 * @retval      NULL                                                    if such an entry is not found.
 *
 */

static SOC_CTX	*
trak_find_free(int sd, int *status)
{
	SOC_CTX	*psc;

	psc = trak_find_ent(sd, status);

	/*test for the expected case first*/

	if (psc != NULL  && (*status == TRK_SUCCESS_FREE)) {
		*status = TRK_SUCCESS;
		return psc;
	}

	/*test for the less expected case*/

	if (psc == NULL && (*status == TRK_TABLE_FULL)) {
		if (trak_tbl_expand(sd) != 0) {
			*status = TRK_EXPAND_FAIL;
			return NULL;
		}

		psc = trak_find_ent(sd, status);
		if (psc != NULL  && (*status == TRK_SUCCESS_FREE)) {
			*status = TRK_SUCCESS;
			return psc;
		}

	}

	/*problem in tracking table if get to here*/

	*status = TRK_TBL_ERROR;
	return NULL;
}

/**
 * @brief
 * 	trak_return_ctx - One of a group of internal functions
 * 	whose job it is to manipulate an entry in the library's
 * 	(socket, context) tracking mechanism.
 *
 * @par	Functionality:
 * 	Given socket descriptor value find (try) an allocated tracking
 * 	table entry whose "sc_sd" member * has descriptor value equal
 * 	to member value sc_sd.  If successful, return a pointer to the
 * 	socket's associated context.
 *
 * @param[in]   sd - socket descriptor value
 * @param[in]   status - place to write back an integer status code
 * @param[in]   *status == TRK_SUCCESS if free entry found
 *
 * @return      pointer to SOC_CTX
 * @retval      pointer to associated, connection specific context
 * @retval      NULL	if such an entry is not found.
 *
 */

static void	*
trak_return_ctx(int sd, int *status)
{
	if (sd < 0) {
		if (status != NULL)
			*status = TRK_BAD_ARG;
		return NULL;
	}

	if (sd >= ctx_trak_max) {
		*status = TRK_TABLE_FULL;
		return NULL;
	}

	if (!(ctx_trak[sd].sc_flg & 0x1) ||
		ctx_trak[sd].sc_ctx == NULL) {

		*status = TRK_TBL_ERROR;
		return NULL;
	}

	/*Expected case*/
	*status = TRK_SUCCESS;
	return ctx_trak[sd].sc_ctx;
}


/*------------------------------------------------------------------------
 * Reliable TCP read/write functions
 *     cs_tcp_read	 - read buffers reliably in the presence of signals
 *     tcp_write - write buffers reliably in the presence of signals
 *     tcp_writev - write vector buffers in the presence of signals
 *
 * note:
 * 	These currently assume blocking I/O is in effect. Some tweaks
 * 	are still needed to support non-blocking I/O. (in other words,
 * 	to simulate blocking io....)
 *
 * 	In the PBS environment this may/will be necessary since
 * 	encrypted I/O will require more data to be written (blocksize
 * 	based on encryption type - typically 8/16 byte units), which
 * 	can cause synchronization loss if a write needs to block.
 *
 * 	One way to avoid this is to determine the I/O mode early in
 * 	the CS functions, then set blocking mode (if non-blocking) and
 * 	restore non-blocking before returning. The end result is that
 * 	blocking I/O is always in effect on TCP sockets.
 *
 * 	This may introduce a little jerkyness in the I/O but I don't
 * 	think it will be significant as the IO will be done in units
 * 	of desired read/write size.
 *
 * 	This may be in error if PBS uses FIONREAD to determine how much
 * 	to read... The FIONREAD count would reflect the encrypted size,
 * 	not the plaintext size, which could cause a read request for
 * 	too much data. This again may not be an error IF short reads
 * 	at an end of file are not counted as a failure. It could cause
 * 	a return of 0 bytes read for an end-of-file indicator when the
 * 	socket gets closed.
 *------------------------------------------------------------------------
 */
 
/**
 * @brief
 * 	cs_tcp_read - reliably read the required number of bytes from a socket
 * 
 * @par	call:
 * 	r = cs_tcp_read(fid,buf,len);
 * 
 * @param[in]	fid	- file descriptor to read from
 * @param[in]	buf	- pointer to the data buffer to store data
 * @param[in]	len	- number of bytes to transfer into the buffer
 * 
 * @return	int
 * @retval	number of bytes read (should always be equal to len)
 * @retval	-1 on error
 * 
 * @par	note:
 * 	Taken from "UNIX Network Programming Volume 1, second edition"
 * 	by W. Richard Stevens, page 78.
 *
 * 	This still leaves one possible error scenario: Some data was
 * 	successfully read... then an error occurs. All return values
 * 	assume that everything is either completed, or no input was done.
 * 	One such error is EAGAIN, caused by nonblocking I/O.
 *
 */


static int
cs_tcp_read(
	int		fid,
	unsigned char	*buf,
	int		len)
{
	int			nleft;
	int			nread;
	unsigned char	*ptr;

	ptr = buf;
	nleft = len;
	errno = 0;

	while (nleft > 0) {
		if ((nread = read(fid, ptr, nleft)) < 0) {
			if (EINTR == errno) {
				nread = 0;		/* and call read again */
			} else {
				return (-1);		/* error */
			}
		} else if (0 == nread) {

			break;			/* got EOF */
		}
		nleft -= nread;
		ptr += nread;
	}
	return (len - nleft);
}

#if 0

/**
 * @brief
 * 	tcp_write - reliably write the required number of bytes to a socket
 * 
 * @par	call:
 * 	r = tcp_write(fid,buf,len);
 * 
 * @param[in]	fid	- file descriptor to read from
 * @param[in]	buf	- pointer to the data buffer to output
 * @param[in]	len	- number of bytes to transfer to the socket
 * 
 * @return	int
 * @retval	number of bytes written (should always be equal to len)
 * @retval	-1 on error
 * 
 * @par	note:
 * 	Taken from "UNIX Network Programming Volume 1, second edition"
 * 	by W. Richard Stevens, page 78.
 *
 * 	This still leaves one possible error scenario: Some data was
 * 	successfully written... then an error occurs. All return values
 * 	assume that everything is either completed, or no output was done.
 * 	One such error is EAGAIN, caused by nonblocking I/O.
 *
 */

static int
tcp_write(
	int		fid,
	unsigned char	*buf,
	int		len)
{
	int			nleft;
	int			nwritten;
	unsigned char	*ptr;

	ptr = buf;
	nleft = len;
	errno = 0;
	while (nleft > 0) {
		if ((nwritten = write(fid, ptr, nleft)) <= 0) {
			if (EINTR == errno) {
				nwritten = 0;		/* and call write again */
			} else {
				return (-1);		/* error */
			}
		}
		nleft -= nwritten;
		ptr += nwritten;
	}
	return (len);
}
#endif

/**
 * @brief
 * 	tcp_writev - reliably write the required data to a socket
 * 
 * @par	call:
 * 	r = tcp_write(fid,vec,len);
 * 
 * @param[in]	fid	- file descriptor to read from
 * @param[in]	vec	- pointer to the vector descriptor of data buffers to output
 * @param[in]	len	- number of vectors in the vec array
 * 
 * @return 	int
 * @retval	number of bytes written (should always be equal to the
 * 		sum of the lengths in each vector descriptor)
 * @retval	-1 on error
 * 
 * @par	note:
 * 	Adapted from "UNIX Network Programming Volume 1, second edition"
 * 	by W. Richard Stevens, page 78 - for use with writev.
 *
 * 	This still leaves one possible error scenario: Some data was
 * 	successfully written... then an error occurs. All return values
 * 	assume that everything is either completed, or no output was done.
 * 	One such error is EAGAIN, caused by nonblocking I/O.
 *
 * 	The vector array (vec parameter) may be modified. So do NOT use
 * 	a constant vector array, or assume that it is not modified.
 *
 */

static int
tcp_writev(
	int		fid,
	struct iovec	*vec,
	int		veclen)
{
	int			res;
	int			nwritten;

	res = 0;
	errno = 0;
	while (veclen > 0) {
		if ((nwritten = writev(fid, vec, veclen)) <= 0) {
			if (EINTR == errno) {
				nwritten = 0;		/* and call write again */
			} else {
				return (-1);		/* error */
			}
		}
		res += nwritten;		/* tally the actual output */

		/* now we must adjust the vector list to compensate for a	*/
		/* short write							*/

		while (nwritten >= vec[0].iov_len && 0 < veclen) {
			nwritten -= vec[0].iov_len;	/* an iovec was completed */
			veclen--;			/* and show it was completed */
			vec++;			/* point to next iovec */
		}

		/* the first remaining vector may be adjusted */

		if (0 < nwritten) {
			vec[0].iov_len -= nwritten;
			vec[0].iov_base += nwritten;
		}
	}
	return (res);	 /* the tally of written bytes */
}

/*========================================================================
 * Authentication support functions
 *------------------------------------------------------------------------
 * send_krb5_data - send a Kerberos packet to a server
 * receive_krb5_data - receive a Kerberos packet from a client
 *
 * A "client" may be another server when it is acting in a client manner
 *------------------------------------------------------------------------
 */

/**
 * @brief 
 *	send_krb5_data - send a Kerberos packet to a server
 * 
 * @par	call:
 * 	r = send_krb5_data(fd, msg);
 * 
 * @param[in]	fd	- file descriptor of a socket to write to
 * @param[in]	msg	- pointer to a krb5_data structure with the data to send
 * 
 * @return	int
 * @retval	write success/failure
 * @retval	-1	=>	failure
 * 		 		a.Invalid parameters were passed
 * 		  		to the write system call
 * 		  		b.More than 64K bytes were attempted
 * 		  		c.message data is null
 * 		 	retval	!= msg->length => failure
 * 			otherwise the return value is msg->length.
 * 
 * @par	note:
 * 	The use of "tcp_write" eliminates short writes.
 *
 * @par	assumption:
 * 	The message to send will NOT exceed 64K bytes.
 *
 */

static int
send_krb5_data(int fd, krb5_data *msg)
{
	unsigned short int	len;
	int			r;
	struct iovec	vec[2];

	/* verify input parameters (the message pointer must not be null	*/
	/* and the data length must be less than 64K)			*/

	if (NULL == msg ||
		NULL == msg->data ||
		65536 < msg->length) return (-1);

	/* now send the information */

	len = htons(msg->length);	/* put length in network order */
	vec[0].iov_base = &len;		/* setup packet header */
	vec[0].iov_len  = sizeof(len);

	vec[1].iov_base = msg->data;	/* setup packet body */
	vec[1].iov_len  = msg->length;

	r = tcp_writev(fd, vec, 2);	/* send packet... */

	if ((r - sizeof(len)) == msg->length)
		return (r - sizeof(len));		/* compensate for header size */

	return (-1);
}

/**
 * @brief
 * 	receive_krb5_data - receive a Kerberos data packet from the network
 * 
 * @par	call:
 *	r = receive_krb5_data(fd, msg, buf);
 * 
 * @param[in]	fd	- file descripor of a socket to read from
 * @param[in]	msg	- pointer to a krb5_data structure to receive the data
 * @param[in] 	buf	- pointer to a resizable workspace buffer structure
 * 
 * @return	int
 * @retval	-1	=> failure (read failure, memory allocation
 * 		  	   failure...)
 * @retval	retval	== length of the message	success
 * @retval	retval	!= length of the message  	otherwise it is another failure
 *
 * @par	note:
 * 	The returned krb5_data structure contains a pointer into the
 * 	resized buffer. The caller must maintain the association of
 * 	krb5_data structure with the resizable buffer structure, or
 * 	to copy the data to another buffer.
 *
 * 	The buffer will contain the number of bytes used for the
 * 	input data. This may be useful where data may be appended
 * 	to the buffer and then passed on to somewhere else.
 *
 */

static int
receive_krb5_data(int fd, krb5_data *msg, DBUF *buf)
{
	unsigned short int	len;
	int			r;

	r = cs_tcp_read(fd, (char *)&len, sizeof(len));  /* required space */

	if (r != sizeof(len)) {

		/* Did we get an EOF -  other end calling close will cause this */
		if (r == 0)
			return (0);

		cs_logerr(-1, "receive_krb5_data", "failed to read message length");
		return (-1);
	}

	len = ntohs(len);
	r = buffer_needs(buf, len);		/* make sure of space */

	if (r) {
		cs_logerr(-1, "receive_krb5_data", "buffer allocation failed");
		return (-1);
	}

	r = cs_tcp_read(fd, buf->buffer, len);
	if (r == len) {
		msg->data = buf->buffer;
		msg->length = len;
		buf->used = r;				/* may be useful later */
	} else
		r = -1;

	return (r);		/* note: r doesn't include the 2 byte header */
}

/**
 * @brief
 * 	get_keytab_tgt - obtain a server TGT based on a keytab entry
 * 
 * @par	call:
 * 	r = get_keytab_tgt()
 *
 * @return	int(return status)
 * @retval	0		=> success
 * @retval	anything else => failure
 * 
 * @par	note:
 * 	The global structure (int_ctx) is updated with the new TGT
 * 	information. This is done here to bypass the expiration of
 * 	the keytab derived TGT.
 *
 */

static int
get_keytab_tgt(void)
{
	krb5_error_code		code;
	krb5_get_init_creds_opt	opts;
	krb5_deltat			lifetime;
	krb5_timestamp		now;
	krb5_timestamp		endtime;

	/* check for expiration/expired ticket */

	endtime = int_ctx.creds.times.endtime;
	if ((code = krb5_timeofday(int_ctx.context, &now))) {
		/* this particular error should NOT happen */
		/* as it implies that the OS has failed    */
		cs_logerr(-1, "cs:get_keytab_tgt",
			"krb5_timeofday failed");
		cs_logerr(-1, "cs:get_keytab_tgt",
			(char *)error_message(code));
		return (1);
	}

	/* This should even work if no credentials have been initialized
	 * as the endtime will be 0. If the TGT lifetime is still good
	 * return success
	 */

	if (now + RENEWTIME < endtime)
		return (0);

	/* convert the default lifetime to a delta time */

	if ((code = krb5_string_to_deltat(DEFAULT_LIFETIME, &lifetime))) {
		cs_logerr(-1, "cs:get_keytab_tgt",
			"Error while converting default lifetime");
		cs_logerr(-1, "cs:get_keytab_tgt",
			(char *)error_message(code));
		return (1);
	}

	krb5_get_init_creds_opt_init(&opts);

	krb5_get_init_creds_opt_set_tkt_life(&opts, lifetime);

	/*
	 * A subtle point: get_init_creds* can take a long time (a few
	 * seconds), so instead of destroying the credential cache and
	 * then have get_in_tkt fill it in, we get the credentials, _then_
	 * initialize and store the credential cache.
	 */

	if ((code = krb5_get_init_creds_keytab(
		int_ctx.context,
		&int_ctx.creds,
		int_ctx.server,
		int_ctx.kt,
		0,
		NULL,
		&opts))) {
		return code;
	}

	if ((code = krb5_cc_initialize(int_ctx.context,
		int_ctx.cc,
		int_ctx.server))) {
		return code;
	}

	if ((code = krb5_cc_store_cred(int_ctx.context,
		int_ctx.cc,
		&int_ctx.creds))) {
		return code;
	}

	return 0;

}

/**
 * @brief
 * 	get_service_ticket - obtain the necessary credentials for a client
 * 
 * @par	call:
 * 	r = get_service_ticket(fd,ctx);
 * 
 * @param[in]	fd	- file descriptor of the connection
 * @param[in]	ctx	- the per-connection security data
 * 
 * @return	int(status)
 * @retval	CS_SUCCESS	  => no error
 * @retval	CS_FATAL_NOAUTH => authentication or communication failure
 * 
 * @par	note:
 * 	If this function is invoked by a server, then the service ticket
 * 	will be obtained using keytab based keys. The keytab credentials
 * 	will be stored in the global structure where the user credentials
 * 	should already be. Credentials for the server must be obtained
 * 	here since they may have expired during normal operation.
 *
 * 	A client will already have credentials available in the global
 * 	structure. User credentials are not renewed here since the
 * 	user will have to obtain/maintain them outside of the client
 * 	application.
 *
 * 	This function bridges between the CS_ specific hooks, and the
 * 	internal only functions that do NOT return CS_ success/fail
 * 	status value.
 *
 */

static int
get_service_ticket(
	int		fd,
	SEC_ctx		*ctx)
{
	union {
		char		caddr[MAXSOCKADDR];
		struct sockaddr	haddr;		/* remote peer name */
	}addr;
	int			len;
	struct hostent	*host;		/* pointer to a host name struct*/
	char		*name;		/* pointer to the hostname */
	krb5_creds		creds;
	krb5_creds		*outcreds;
	krb5_error_code	retval;
	int			res;
	char               *remote_ip;

	/* check for the need of a keytab based TGT */

	if (int_ctx.flags & F_SERVER) {
		if (get_keytab_tgt()) {
			cs_logerr(-1, "cs:get_service_ticket",
				"Cannot access keytab");
			return (CS_FATAL_NOAUTH);
		}
	}

	/* first get the IP number of the remote host */

	len = sizeof(addr);
	res = getpeername(fd, &addr.haddr, &len);
	if (res) {
		cs_logerr(-1, "cs:get_service_ticket",
			"Cannot get peername");
		return (CS_FATAL_NOAUTH);
	}

	/* convert the IP to ascii for comparison */

	remote_ip = inet_ntoa(((struct sockaddr_in *) &addr.haddr)->sin_addr);

	/* check if connection from 127.x.x.x */

	if (strncmp(remote_ip, "127.", 4) == 0) {

		/* set name to NULL for kerberos */

		name = NULL;
		ctx->hostname[0]=0;

	} else {
		/* now get the FQDN of the remote host (ie. the hostname) */

		res = getnameinfo(&addr.haddr,
			sizeof(addr),
			ctx->hostname,
			128,
			NULL,
			0,
			NI_NAMEREQD);
		if (res) {
			cs_logerr(-1, "cs:get_service_ticket",
				"Cannot get remote host name");
			return (CS_FATAL_NOAUTH);
		}
		name = ctx->hostname;
	}


	/*
	 * Before we use it, we zero out all of the fields in the
	 * credential cache structure (since we're going to want
	 * to call krb5_free_cred_contents later, we don't want any
	 * junk pointers in there).
	 */

	memset((void *) &creds, 0, sizeof(creds));

	/*
	 * We need to fill in our client principal name.  We get this
	 * out of the credential cache (it's called the "primary principal").
	 * Use this to fill in creds.client.
	 */

	retval = krb5_cc_get_principal(int_ctx.context,
		int_ctx.cc,
		&creds.client);
	if (retval) {
		cs_logerr(-1, "cs:get_service_ticket",
			(char *)error_message(retval));
		krb5_cc_close(int_ctx.context, int_ctx.cc);
		return (CS_FATAL_NOAUTH);
	}

	/* get the service ticket
	 * Now we need to fill in the service principal name. This
	 * can be done in a few different ways:
	 *
	 * - If you are constructing a "standard" (host-based) principal
	 *   name, you can use krb5_sname_to_principal. For the "host"
	 *   principal, that function call would look like:
	 *
	 *	    krb5_sname_to_principal(context, hostname, "host",
	 *	    				KRB5_NT_SRV_HST, &principal);
	 *
	 * - You can construct it by hand with the principal building
	 *   macros (krb5_princ_realm, krb5_princ_name, etc etc).
	 *
	 * - You can parse an ASCII principal string (which is shown below)
	 *   Note that we are getting the principal name from the command
	 *   line argument (argv[1]). Note that we place the server
	 *   principal name into the "server" member of the krb5_creds
	 *   structure.
	 *      krb5_parse_name(context, argv[1], &creds.server);
	 */

	retval = krb5_sname_to_principal(
		int_ctx.context,
		name,
		SERVICENAME,
		KRB5_NT_SRV_HST,
		&creds.server);
	if (retval) {
		cs_logerr(-1, "cs:get_service_ticket",
			(char *)error_message(retval));
		return (CS_FATAL_NOAUTH);
	}

	/*
	 * Now we actually contact the KDC and get the credentials. This
	 * is the encrypted Kerberos ticket, the session key, and all of
	 * the other information necessary to authenticate to a server.
	 * This function takes our ticket out of the credential cache,
	 * contacts the KDC, and fills in our output creds structure.
	 *
	 * In order, the arguments to this funciton are:
	 *
	 * #1 - krb5_context.
	 * #2 - various flags. None of the flags are needed for our usage
	 * 	    so we set this to be zero.
	 * #3 - The credential cache. This is so we can access our client
	 * 	    credentials to get our service ticket (either from the KDC
	 * 	    or the credential cache).
	 * #4 - Our input credentials We get our service principal out of
	 * 	    this structure.
	 * #5 - Our output credentials. This is what we use to construct
	 *      the AP_REQ message down below.
	 */

	retval = krb5_get_credentials(int_ctx.context,
		0,
		int_ctx.cc,
		&creds,
		&outcreds);
	if (retval) {
		/* unable to get credentials (outcreds) */

		cs_logerr(-1, "cs:get_service_ticket",
			(char *)error_message(retval));
		krb5_free_cred_contents(int_ctx.context, &creds);
		return (CS_FATAL_NOAUTH);
	}

	/*
	 * Now we've actually gotten to the point where we're going to
	 * create a Kerberos ticket! This is called an AP_REQ (APplication
	 * REQuest) message in kerberos terminology. This function is
	 * a little bit odd in that it will allocate a auth_context for
	 * us (but we need to pass in a zero'd out pointer).
	 *
	 * Here are the arguments in detail:
	 * #1 - the kerberos 5 context.
	 * #2 - the kerbero 5 authorization context. This contains
	 *	    crypto information like the session key. This gets filled
	 *	    in for us by krb5_mk_req()
	 * #3 - Flags to indicate optional processing to the Kerberos protocol.
	 *      The important one here is  AP_OPTS_UTUAL_REQUIRED. This
	 *      means that mutual authentication (client to server AND
	 *      server to client) must be performed, and that is important
	 *      in nearly all cases; it's recommended to do this unless there
	 *      is a strong technical reason why you cannot. The other
	 *      option given to this function is AP_OPTS_USE_SUBKEY which
	 *      will cause this function to generate a sub-session key which
	 *      can later be used for encryption/checksum (you can use the
	 *      session key for this, but a subsession key means you use a
	 *      new key for each session, rather than the same key for
	 *      multiple sessions that use the same ticket).
	 * #4 - This is a passed in krb5_data structure (which itself is
	 *      just a container object containing a pointer and a length)
	 *      which is used to indicate "checkum" data that will be
	 *      checksummed and signed; the signed checksum of this data
	 *      is sent in the AP_REQ. This is used to tie the Kerberos
	 *      authentication to the lower-level protocol (for example,
	 *      you could put an IP address/port number of some other
	 *      application-specific information). In our case, we simply
	 *      pass in NULL.
	 * #5 - This is the previously-metntioned krb5_creds structure.
	 *      The only thing that we use out of here is the server
	 *      things, but in this case we just take the defaults).
	 * #6 - This is the actual output of the function. A krb5_data
	 *      structure is filled in with a pointer and a length containing
	 *      the actual bytes of the AP_REQ. This is what we need to
	 *      transmit to the application server.
	 */

	retval = krb5_mk_req_extended(int_ctx.context,
		&ctx->auth_context,
		AP_OPTS_MUTUAL_REQUIRED |
		AP_OPTS_USE_SUBKEY,
		NULL,
		outcreds,
		&ctx->uticket);
	if (retval) {
		/* unable to get kerberos ticket */

		cs_logerr(-1, "cs:get_service_ticket",
			(char *)error_message(retval));

		if (ctx->auth_context)
			krb5_auth_con_free(int_ctx.context, ctx->auth_context);

		krb5_free_cred_contents(int_ctx.context, &creds);
		krb5_free_creds(int_ctx.context, outcreds);

		return (CS_FATAL_NOAUTH);
	}

	/*
	 * we don't need these things anymore
	 */

	krb5_free_cred_contents(int_ctx.context, &creds);
	krb5_free_creds(int_ctx.context, outcreds);

	return (CS_SUCCESS);
}

/*========================================================================
 * Internal realizations of PBS hook function's
 * cs_READ	   - read encrypted data, decrypt and pass result to PBS
 * cs_WRITE	   - encrypt PBS data, and write result
 * cs_CLIENT_AUTH  - authenticate to a server, authenticate server
 * cs_SERVER_AUTH  - authenticate a client, authenticate to client
 * cs_CLOSE_SOCKET - release per-connection security data
 *------------------------------------------------------------------------
 */
 
/**
 * @brief
 *	cs_READ - read data
 * 
 * @par	call:
 *	r = cs_READ ( fid, buf,len, ctx );
 * 
 * @param[in]	fid	- file id to read from
 * @param[in]	buf	- address of the buffer to fill
 * @param[in]	len	- number of bytes to transfer
 * @param[in]	ctx	- security blob pointer
 * 
 * @return	int
 * @retval	number of bytes read, or error
 *
 */

static int
cs_READ(int fid, char *buf, size_t len, SEC_ctx *ctx)
{
	krb5_error_code	retval;
	int			res;
	int			count;
	krb5_enc_data	encdata;
	krb5_data		message;
	char		*ip;
	char		*curbuf;
	char		ebuf[ 80 ];

	if (NULL == buf) {
		/* really now.... */

		return (-1);
	}

	if (NULL == ctx)
		ctx = &int_ctx.single;

	if (!(ctx->flags & F_INIT)) {

		sprintf(ebuf, "uninitialized context for descriptor %d", fid);
		cs_logerr(-1, "cs_READ", ebuf);
		return (-1);
	}

	/* basic checks are done */

	count = len;
	curbuf = buf;
	do {
		/*----------------------------------------------------------------
		 * part 1 - some data is, or may be, in the current decoded buffer
		 *----------------------------------------------------------------
		 */
		if (ctx->curr_read  <  ctx->decbuf.used) {
			/* must always skip the first two bytes as these are the
			 * net ordered plaintext length
			 * (note to self - this can be optimized by using a memcpy)
			 */

			ip = &ctx->decbuf.buffer[ 2 + ctx->curr_read ];
			while ((ctx->curr_read < ctx->decbuf.used) && count) {
				*curbuf++ = *ip++;
				count--;
				ctx->curr_read++;
			}

			if (count == 0) {

				/* completely filled caller's provided buffer */
				return ((int)len);

			} else if (ctx->curr_read == ctx->decbuf.used) {

				/* amount copied from "decryption buffer" */
				return (len - count);
			}
		}

		/*----------------------------------------------------------------
		 * part 2 - encrypted data must be read
		 * 	    note: data buffer used by the encrypted "encdata" is
		 * 	    automatically managed with int_ctx.inbuf
		 *----------------------------------------------------------------
		 */

		int_ctx.readerror = 0;
		res = receive_krb5_data(fid, &encdata.ciphertext, &int_ctx.inbuf);

		if (res <= 0  ) {

			/* error or no data from socket (i.e. EOF) */
			if (res != 0) {
				sprintf(ebuf, "input failure for descriptor %d", fid);
				cs_logerr(-1, "cs_READ", ebuf);
			}

			return (res);
		}
		int_ctx.inbuf.used = res;
#if 0
		dump("CS_read ciphertext buffer", int_ctx.inbuf.used, int_ctx.inbuf.buffer);
#endif

		/*----------------------------------------------------------------
		 * part 3 - data must be decrypted
		 *----------------------------------------------------------------
		 */

		/* setup structure for the encrypted data */
		/* the data portion has already be setup by receive_krb5_data */

		encdata.enctype = ctx->key->enctype;

		/* reallocate decryption buffer if necessary */
		/* note: this is the per-connection decrypted buffer */

		if (buffer_needs(&ctx->decbuf, res)) {
			cs_logerr(-1, "cs_READ", "buffer failure");
			errno = 0;
			return (-1);
		}

		message.data = ctx->decbuf.buffer;
		message.length = res;

		/*
		 * Actually decrypt the message. Function arguments are as
		 * follows:
		 * #1 - Kerberos  5 context, as discussed previously
		 * #2 - the encryption key (negotiated securely by Kerberos)
		 * #3 - The key usage number. This is an integer that is
		 * 	used to further permute the encryption key. We match
		 * 	it up with the client's key usage number (KEY_USAGE).
		 * #4 - The initial vector to the CBC algorithm (initialized in
		 * 	CS_xx_auth)
		 * #5 - the ciphertext to be decrypted.
		 * #6 - the output (plaintext)
		 */

		retval = krb5_c_decrypt(int_ctx.context,
			ctx->key,
			KEY_USAGE,
			&ctx->input_ivec,
			&encdata,
			&message);
		if (retval) {
			int_ctx.readerror = 5;
			cs_logerr(-1, "cs_READ", (char *)error_message(retval));
			errno = 0;
			return (-1);
		}

		/* remember: the first two bytes are the cleartext data length */

		ctx->decbuf.used = ntohs(*(unsigned short*)ctx->decbuf.buffer);
		ctx->curr_read = 0;

		/* we no longer care what is done with the encrypted data.
		 * the buffer will be reused by future input activity
		 */
		int_ctx.inbuf.used = 0;

#if 0
		dump("CS_read plaintext buffer", message.length, message.data);
#endif

	} while (1);
}

/**
 * @brief
 * 	cs_WRITE - write data
 * 
 * @par	call:
 *      r = cs_WRITE ( fid, buf, len, ctx )
 * 
 * @param[in]     fid     - file id to write to
 * @param[in]     buf     - address of the buffer to write
 * @param[in]     len     - number of bytes to transfer
 * @param[in]     ctx     - security blob pointer
 * 
 * @return	int
 * @retval	number of bytes read, or error
 * 
 * @par	note:
 *      This function assumes a write will be less than 64k bytes long
 *      since encryption MAY expand the buffer...(modulus encryption
 *      blocksize at most). It is recommended to keep the write size
 *      below 64k - 128 bytes (128 is my opinion, it actually depends
 *      on the largest encryption blocksize -1), though this is not
 *      enforced here (the 64k limit is).
 *
 *      Longer buffers can be supported, but the plaintext length
 *      would then need to be 4 bytes long, AND the send/receive_krb5_data
 *      functions would have to be modified for 4 byte lengths.
 *
 */

static int
cs_WRITE(int fid, char *buf, int len, SEC_ctx	*ctx)
{
	krb5_error_code	retval;
	krb5_data		message;	/* to be sent			*/
	krb5_enc_data	encmessage;	/* encrypted message		*/
	int			size;

	if (65536 < len)
		return (-1);

	if (NULL == buf) {
		/* really now.... */
		return (-1);
	}

	if (NULL == ctx)
		ctx = &int_ctx.single;

	if (!(ctx->flags & F_INIT))
		return (-1);

	/*----------------------------------------------------------------
	 * part 1 - setup the plaintext buffer (including the plaintext
	 * 		length
	 *----------------------------------------------------------------
	 */

	int_ctx.outbuf.used = 0;
	if (buffer_needs(&int_ctx.outbuf, len + 2)) {
		cs_logerr(-1, "cs_WRITE", "buffer allocation failure");
		return (-1);
	}

	/* put the plaintext length at the beginning of the buffer */

	*(unsigned short int *)int_ctx.outbuf.buffer = htons(len);
	int_ctx.outbuf.used += 2;	/* skip the plaintext length */

	/* now append the plaintext data */

	buffer_append(&int_ctx.outbuf, len, buf);

	/* now set the kerberos data structure for a message */

	message.length = int_ctx.outbuf.used;
	message.data = int_ctx.outbuf.buffer;
#if 0
	dump("CS_write plaintext buffer", message.length, message.data);
#endif

	/*----------------------------------------------------------------
	 * part 2 - setup the output buffer structure
	 *----------------------------------------------------------------
	 */

	/*
	 * Set up the output buffer. We can determine the size of the
	 * encryted data for a given plaintext length by the use
	 * of krb5_c_encrypt_length
	 */

	retval = krb5_c_encrypt_length(
		int_ctx.context,
		ctx->key->enctype,
		message.length,
		&size);
	if (retval) {
		cs_logerr(-1, "cs_WRITE", (char *)error_message(retval));
		return (-1);
	}

	if (buffer_needs(&int_ctx.encoutbuf, size)) {
		cs_logerr(-1, "cs_WRITE", "buffer allocation failure");
		return (-1);
	}

	/* so now set the kerberos encrypted data structure */

	encmessage.ciphertext.data = int_ctx.encoutbuf.buffer;
	encmessage.ciphertext.length = size;
	int_ctx.encoutbuf.used = size;	/* may be usefull later */

	/*----------------------------------------------------------------
	 * part 3 - encrypt the data
	 *----------------------------------------------------------------
	 */

	/*
	 * Now we actually encrypt something! The arguments to this function
	 * are as follows:
	 *
	 * #1 - Kerberos context; discussed previously
	 * #2 - The encryption key that we are using to encrypt this
	 *	    data (it was negotiated securely for us by Kerberos).
	 * #3 - the key usage number. Thi is an integer that is
	 *      used to further permute the encryption key. Applications
	 *      are free to pick key usage numbers from 1024 and above;
	 *      we pic KEY_USAGE here.
	 * #4 - The initial vector to the CBC algorithm
	 * #5 - the plaintext to be encrypted
	 * #6 - the output (ciphertext)
	 */

	retval = krb5_c_encrypt(int_ctx.context,
		ctx->key,
		KEY_USAGE,
		&ctx->output_ivec,
		&message,
		&encmessage);
	if (retval) {
		int_ctx.writeerror = 3;
		cs_logerr(-1, "cs_WRITE", (char *)error_message(retval));
		return (-1);
	}

	/*----------------------------------------------------------------
	 * part 4 - send the data (done by send_krb5_data)
	 * 		This works because the krb5_enc_data data structue
	 * 		field ciphertext is a krb5_data structure.
	 *----------------------------------------------------------------
	 */

#if 0
	dump("CS_write ciphertext buffer",
		encmessage.ciphertext.length, encmessage.ciphertext.data);
#endif

	if (send_krb5_data(fid, &encmessage.ciphertext) == size)
		return (len);
	else
		return (-1);

	/* NOTE: this is using the global data buffers because it is
	 * 	     NOT in a re-entrant situation. All access to outbuf, and
	 * 	     encoutbuf are synchronous with respect to CS_write.
	 * 	     Asynchronous buffers can be done, but they would have to
	 * 	     be stored in the per-context buffer.
	 */

}

/**
 * @brief
 * 	cs_CLIENT_AUTH - authenticate to a remote server
 * 
 * @par	call:
 *	r = cs_CLIENT_AUTH ( fd, ctx );
 * 
 * @param[in]	fd	- socket file id
 * @param[in]	ctx	- pointer to a per conntection security context pointer
 *		  	(not used in the default)
 * 
 * @return	int
 * @retval 	status result, 0 => success
 * @retval	nonzero signals that a fatal error was detected
 *
 */

static int
cs_CLIENT_AUTH(int fd, void **pctx)
{
	SEC_ctx		*ctx;		/* pointer to the context */
	int			res;
	krb5_error_code	retval;

	/* if there is no per-connect, use the internal version */

	if (NULL == pctx) ctx = &int_ctx.single;
	else {
		if (NULL == *pctx) {	/* then the connect context isn't setup	*/
			*pctx = ctx = calloc(1, sizeof(SEC_ctx));
			if (NULL == ctx) {
				cs_logerr(-1, "CS_client_auth",
					"cannot calloc per-connection data");
				return (CS_FATAL_NOMEM);
			}
			/* Note: calloc zeros the allocated memory */
		} else {
			ctx = *pctx;
			ctx->flags = 0;
		}
	}

	if (ctx->flags & F_INIT) return (CS_SUCCESS);

	/* initialize the per-connect security */

	ctx->flags = F_INIT;

	if (res = get_service_ticket(fd, ctx)) return (res);
	ctx->flags |= F_CLIENT;

	/* send the ticket to the server */

	res = send_krb5_data(fd, &ctx->uticket);
	if (res <= 0) return (CS_FATAL_NOAUTH);

	/* get the reply - note: data is stored in decbuf which will be
	 * 			     reused in CS_read  so don't free it */

	res = receive_krb5_data(fd, &ctx->message, &ctx->decbuf);

	if (res <= 0)
		return (CS_FATAL_NOAUTH);

	/* verify the server identity */

	if (retval = krb5_rd_rep(int_ctx.context,
		ctx->auth_context,
		&ctx->message,
		&ctx->reply)) {

		/* server verification failed */

		cs_logerr(-1, "CS_client_auth", (char *)error_message(retval));
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOAUTH);
	}

	krb5_free_ap_rep_enc_part(int_ctx.context, ctx->reply);

	/*--------------------------------------------------------------------
	 * Encryption Initialization
	 *
	 * The first thing we need to do is to get the encryption key that
	 * has been set up as part of the Kerboers exchange. All of the
	 * crypto stuff has been stored in the authorization context, so
	 * all we need to do is extract it from there. Note that this shows
	 * one of the (many) API pecularities; on the client, it's called
	 * the local subkey, and on the server, it's called the remote
	 * subkey.
	 */

	retval = krb5_auth_con_getlocalsubkey(int_ctx.context,
		ctx->auth_context,
		&ctx->key);
	if (retval) {
		/* unable to retrieve local subkey */
		cs_logerr(-1, "CS_client_auth", (char *)error_message(retval));
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOAUTH);
	}

	if (! ctx->key) {
		/* no subkey found in auth_context */

		cs_logerr(-1, "CS_client_auth", "No subkey found in auth_context");
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOAUTH);
	}

	/*
	 * Get the blocksize, and set up our input and output ivecs
	 */

	retval = krb5_c_block_size(int_ctx.context,
		ctx->key->enctype,
		&ctx->blocksize);
	if (retval) {
		/* unable to determine crypto blocksize */
		cs_logerr(-1, "CS_client_auth", (char *)error_message(retval));
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOMEM);
	}

	/* now generate the ivec/ovec encryption vectors (for chaining) */

	ctx->input_ivec.data = calloc(1, ctx->blocksize);
	if (! ctx->input_ivec.data) {
		/* Unable to calloc input ivec */

		cs_logerr(-1, "CS_client_auth",
			"Unable to calloc for input ivec");
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOMEM);
	}

	ctx->output_ivec.data = calloc(1, ctx->blocksize);
	if (! ctx->output_ivec.data) {
		/* unable to calloc for output ivec */

		cs_logerr(-1, "CS_client_auth",
			"Unable to calloc for output ivec");

		free(ctx->input_ivec.data);
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		return (CS_FATAL_NOMEM);
	}

	ctx->input_ivec.length = ctx->output_ivec.length = ctx->blocksize;

	/* Note that when we transmit, we use an ivec of all zeros; when
	 * the server transmits, it uses all ones.
	 * NOTE: for base UDP these vectors must be reset after every packet.
	 */

	memset(ctx->input_ivec.data, 0xff, ctx->input_ivec.length);
	memset(ctx->output_ivec.data, 0, ctx->output_ivec.length);

	/* now mark the decbuf as not used. It is allocated, but any
	 * data contained within is now trash. This allows the buffer
	 * to be reused for the plaintext buffer during CS_read operation.
	 */

	ctx->decbuf.used = 0;	/* no usable data exists in the buffer */

	/* this is where a forwarded key would be generated and sent
	 * to the server.
	 */

	return (CS_SUCCESS);
}

/**
 * @brief
 * 	cs_SERVER_AUTH - authenticate to a client
 *
 * @par	call:
 *	r = cs_SERVER_AUTH ( fd, ctx );
 * 
 * @param[in]	fd	- socket file id
 * @param[in]	ctx	- per conntection security context
 * 
 * @return	int
 * @retval	status result, 0 => success
 * @retval	nonzero signals that a fatal error was detected
 *
 */

static int
cs_SERVER_AUTH(int fd, void **pctx)
{
	SEC_ctx		*ctx;		/* pointer to the context */
	int			res;
	krb5_error_code	retval;

	/* part 1 - matches client_auth */
	/* if there is no per-connect, use the internal version */

	if (NULL == pctx) ctx = &int_ctx.single;
	else {
		if (NULL == *pctx) {	/* then the connect context isn't setup	*/
			*pctx = ctx = calloc(1, sizeof(SEC_ctx));
			if (NULL == ctx) {
				cs_logerr(-1, "CS_server_auth",
					"cannot calloc per-connection data");
				return (CS_FATAL_NOMEM);
			}
			/* Note: calloc zeros the allocated memory */
		} else {
			ctx = *pctx;
			ctx->flags = 0;
		}
	}

	if (ctx->flags & F_INIT) return (CS_SUCCESS);

	/* initialize the per-connect security blob */

	ctx->flags = F_INIT;

	/* receive the user message for verification
	 * note: the data is stored in decbuf which will be
	 *       reused in CS_read so don't free it
	 */

	if (receive_krb5_data(fd, &ctx->message, &ctx->decbuf) <= 0)
		return (CS_FATAL_NOAUTH);

	/* verify the client identity */

	retval = krb5_rd_req(int_ctx.context,
		&ctx->auth_context,
		&ctx->message,
		int_ctx.server,
		int_ctx.kt,
		&ctx->kflags,
		&ctx->ticket);
	if (retval) {
		/* user invalid  - krb5_rd_req failed */
		cs_logerr(-1, "CS_server_auth",
			"user invalid - krb5_rd_req failed");
		cs_logerr(-1, "CS_server_auth",
			(char *)error_message(retval));

		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}

	/* the client's identity (since authentication was successful)
	 * is in ticket->enc_part2->client.
	 */

	retval = krb5_unparse_name(int_ctx.context,
		ctx->ticket->enc_part2->client,
		&ctx->identity);

	/* wer're done with the ticket so get rid of it */

	krb5_free_ticket(int_ctx.context, ctx->ticket);
	if (retval) {
		/* krb5_unparse_name failed */

		cs_logerr(-1, "CS_server_auth", (char *)error_message(retval));
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}
	ctx->ticket = NULL;

	/*
	 * Now we need to send back an AP_REP to verify our identity to the
	 * user. We create this message by calling krb5_mk_rep(). All of the
	 * necessary crypto bits for this call are stored in the auth_context,
	 * so this call is relatively simple.
	 * note: the ctx->message data buffer is handled by ctx->decbuf so
	 * it isn't necessary to free it before this call.
	 */

	retval = krb5_mk_rep(int_ctx.context,
		ctx->auth_context,
		&ctx->message);
	if (retval) {
		/* krb5_mk_rep failed */
		cs_logerr(-1, "CS_server_auth", (char *)error_message(retval));
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}

	/* send this response to the client */

	if (0 >= send_krb5_data(fd, &ctx->message)) return (CS_FATAL_NOAUTH);

	/* communications has been initialized and authenticated */

	ctx->flags |= F_SERVER;

	/*--------------------------------------------------------------------
	 * Encryption Initialization
	 *
	 * Next we're expecting an encrypted message from the client.
	 * We need to set up stuff for that. To do that, we need to:
	 *
	 *  - Get our subsession key out of the authorization context
	 *  - Set up or initial vectors
	 */

	/*
	 * Retrieve the subsession key from the authorization context.
	 * Note that on the server, we get the "remote" subsession key.
	 */

	retval = krb5_auth_con_getremotesubkey(int_ctx.context,
		ctx->auth_context,
		&ctx->key);
	if (retval) {
		/* unable to retrieve the remote subkey */
		cs_logerr(-1, "CS_server_auth",
			(char *)error_message(retval));
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}
	if (! ctx->key) {
		/* no subkey found in auth context */
		cs_logerr(-1, "CS_server_auth",
			"No subkey found in auth_context");
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}

	/*
	 * find out the blocksize of our cryptosystem
	 */

	retval = krb5_c_block_size(int_ctx.context,
		ctx->key->enctype,
		&ctx->blocksize);

	if (retval) {
		/* unable to determine crypto blocksize */
		cs_logerr(-1, "CS_server_auth",
			(char *)error_message(retval));
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOAUTH);
	}

	ctx->input_ivec.data = calloc(1, ctx->blocksize);
	if (! ctx->input_ivec.data) {

		/* unable to calloc for input ivec */

		cs_logerr(-1, "CS_server_auth", "Unable to calloc input ivec");
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOMEM);
	}

	ctx->output_ivec.data = calloc(1, ctx->blocksize);
	if (! ctx->output_ivec.data) {

		/* unable to calloc for output ivec */

		cs_logerr(-1, "CS_server_auth", "Unable to calloc output ivec");
		free(ctx->input_ivec.data);
		krb5_free_keyblock(int_ctx.context, ctx->key);
		ctx->key = NULL;
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
		ctx->flags &= ~F_INIT;
		return (CS_FATAL_NOMEM);
	}

	ctx->input_ivec.length = ctx->output_ivec.length = ctx->blocksize;

	/*
	 * When we transmit, we use an ivec of all ones; the client uses
	 * an ivec of all zeros
	 * NOTE: for UDP these vectors must be reset after every packet
	 */

	memset(ctx->input_ivec.data, 0, ctx->input_ivec.length);
	memset(ctx->output_ivec.data, 0xff, ctx->output_ivec.length);

	/* now mark the decbuf as not used. It is allocated, but any
	 * data contained within is now trash. This allows the buffer
	 * to be reused for the plaintext buffer during CS_read operation.
	 */

	ctx->decbuf.used = 0;	/* no usable data exists in the buffer */

	/*--------------------------------------------------------------------
	 * this is where a forwarded key would be received from the
	 * client and saved in something for the user.
	 */

	return (CS_SUCCESS);
}

/**
 * @brief
 * 	cs_CLOSE_SOCKET - cleanup security blob when closing a socket.
 * 
 * @par	call:
 * 	r = cs_CLOSE_SOCKET ( pctx );
 * 
 * @param[in]	pctx	- pointer to a per conntection security context pointer
 *		  (not used in the default)
 * 
 * @returns	int
 * @retval	status result, 0 => success
 * 
 * @par	note:
 * 	The socket should still be open when this function is called.
 * 	The pointer to the security blob may be modified, hence pctx
 * 	points to the pointer to the blob.
 *
 */

static int
cs_CLOSE_SOCKET(void **pctx)
{
	SEC_ctx	*ctx;

	/* if there is no per-connect, use the internal version */

	if (NULL == pctx) ctx = &int_ctx.single;
	else {
		if (NULL == *pctx) {	/* then the connect context isn't setup	*/
			return (CS_SUCCESS); /* so ignore the request */
		}
		ctx = *pctx;
	}

	if (ctx->input_ivec.data) {
		free(ctx->input_ivec.data);
	}
	if (ctx->output_ivec.data) {
		free(ctx->output_ivec.data);
	}

	if (ctx->key) {
		krb5_free_keyblock(int_ctx.context, ctx->key);
	}

	if (ctx->identity) {
		krb5_free_unparsed_name(int_ctx.context, ctx->identity);
	}

	if (ctx->auth_context) {
		krb5_auth_con_free(int_ctx.context, ctx->auth_context);
	}

	if (ctx->decbuf.buffer) {
		free(ctx->decbuf.buffer);
	}

	/* needs checking - there may be a memory leak ????????? */
	/* also - if the chain entry gets used, it must be restored */

	memset(ctx, 0, sizeof(SEC_ctx));

	return (CS_SUCCESS);		/* always return success if no error */
}



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
 * @return	int
 * @retval	number of bytes read, or error
 *
 */

int
CS_read(int sd, char *buf, size_t len)
{
	int	status;
	void	*ctx;

#if	(PBS_SECURITY == KCRYPT )

	if ((ctx = trak_return_ctx(sd, &status)) == NULL) {
		return (CS_IO_FAIL);
	}

	return (cs_READ(sd, buf, len, ctx));
#endif

	/*PBS built for kerberos authentication only*/
	return (read(sd, buf, len));
}

/**
 * @brief
 * 	CS_write - write data
 *
 * @par	call:
 *      r = CS_write ( fid, buf, len )
 * 
 * @param[in]     fid     - file id to write to
 * @param[in]     buf     - address of the buffer to write
 * @param[in]     len     - number of bytes to transfer
 * 
 * @return	int
 * @retval	number of bytes read, or error
 * 
 * @par	note:
 *      This function assumes a write will be less than 64k bytes long
 *      since encryption MAY expand the buffer...(modulus encryption
 *      blocksize at most). It is recommended to keep the write size
 *      below 64k - 128 bytes (128 is my opinion, it actually depends
 *      on the largest encryption blocksize -1), though this is not
 *      enforced here (the 64k limit is).
 *
 *      Longer buffers can be supported, but the plaintext length
 *      would then need to be 4 bytes long, AND the send/receive_krb5_data
 *      functions would have to be modified for 4 byte lengths.
 *
 */

int
CS_write(int sd, char *buf, size_t len)
{
	int	status;
	void	*ctx;

#if	(PBS_SECURITY == KCRYPT )

	if ((ctx = trak_return_ctx(sd, &status)) == NULL) {
		return (CS_IO_FAIL);
	}

	return (cs_WRITE(sd, buf, (int)len, ctx));
#endif

	/*PBS built for kerberos authentication only*/
	return (write(sd, buf, len));

}

/**
 * @brief
 * 	CS_client_auth - authenticate to a remote server
 * 
 * @par	call:
 *	r = CS_client_auth(fd);
 * 
 * @param[in]	fd	- socket file id
 * 
 * @return	int
 * @retval	status result, 0 => success
 * @retval	nonzero signals that a fatal error was detected
 *
 */

int
CS_client_auth(int sd)
{
	int	status;
	void	*lctx = NULL;

	if ((trak_find_free(sd, &status)) == NULL) {
		return (CS_FATAL);
	}
	if (cs_CLIENT_AUTH(sd, &lctx) == CS_SUCCESS) {
		if (trak_set_ent(sd, lctx) == 0)
			return (CS_SUCCESS);
		else {
			/*don't expect this path to ever occur*/

			cs_CLOSE_SOCKET(&lctx);
			if (lctx)
				free(lctx);

			trak_rls_ent(sd);
		}
	}
	return (CS_FATAL);
}

/**
 * @brief
 * 	CS_server_auth - authenticate to a client
 * 
 * @par	call:
 *	r = CS_server_auth(fd);
 *
 * @param[in]	fd	- socket file id

 * @return	int
 * @retval	status result, 0 => success
 * @retval	nonzero signals that a fatal error was detected
 *
 */

int
CS_server_auth(int	sd)
{
	int	status;
	void    *lctx = NULL;

	if ((trak_find_free(sd, &status)) == NULL) {
		return (CS_FATAL);
	}

	if (cs_SERVER_AUTH(sd, &lctx) == CS_SUCCESS) {

		if (trak_set_ent(sd, lctx) == 0)
			return (CS_SUCCESS);
		else {
			/*don't expect this path to ever be taken*/

			cs_CLOSE_SOCKET(&lctx);
			if (lctx)
				free(lctx);

			trak_rls_ent(sd);
		}
	}
	return (CS_FATAL);
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
 * @par	Note:
 * 	The socket should still be open when this function is called.
 * 	The pointer to the security blob may be modified, hence pctx
 * 	points to the pointer to the blob.
 *
 */

int
CS_close_socket(int sd)
{
	int	status;
	void    *lctx = NULL;

	if ((trak_find_ent(sd, &status)) != NULL) {
		if (status == TRK_SUCCESS_FREE)
			return (CS_SUCCESS);
		else if (status == TRK_SUCCESS_INUSE) {

			if ((lctx = trak_return_ctx(sd, &status)) != NULL) {

				/*free any structures hanging on context
				 *then free the SOC_ctx structure itself
				 *and release the entry in the context
				 *tracking table
				 */

				cs_CLOSE_SOCKET(&lctx);
				free(lctx);
				(void)trak_rls_ent(sd);
				return (CS_SUCCESS);
			} else {
				/*don't ever expect this path*/
				return (CS_FATAL);
			}
		}
	}

	/*other status:TRK_TABLE_FULL, TRK_TBL_ERROR, TRK_BAD_ARG*/

	if (status == TRK_TABLE_FULL &&
		ctx_trak == NULL && ctx_trak_max == 0)

		/* called find_trak_ent () during initialization */
		return (CS_SUCCESS);
	else
		return (CS_FATAL);
}

/**
 * @brief
 * 	CS_close_app - the global cleanup function
 *
 * @par	call:
 *	r = CS_close_app();
 *
 * @returns	int
 * @retval	status result, 0 => success
 * @retval	nonzero signals that a fatal error was detected and
 *		activity will NOT be continued, or restarted
 *
 */

int
CS_close_app(void)
{
	/* needs checking - there may be a memory leak			*/
	/* also - if the chain entry gets used, it must be processed	*/
	/*        before the following					*/

	if (int_ctx.inbuf.buffer) free(int_ctx.inbuf.buffer);
	if (int_ctx.outbuf.buffer) free(int_ctx.outbuf.buffer);
	if (int_ctx.encoutbuf.buffer) free(int_ctx.encoutbuf.buffer);
	if (int_ctx.server)
		krb5_free_principal(int_ctx.context, int_ctx.server);
	if (int_ctx.kt) krb5_kt_close(int_ctx.context, int_ctx.kt);
	if (int_ctx.cc) krb5_cc_close(int_ctx.context, int_ctx.cc);
	krb5_free_context(int_ctx.context);

	memset(&int_ctx, 0, sizeof(KGlobal));

	return (CS_SUCCESS);		/* always return success if no error */
}


/**
 * @brief
 * 	CS_client_init - the client initialization function for global security
 * 		    data
 * @par	usage:
 * 	r = CS_client_init();
 *
 * @returns	int
 * @retval	initialization status
 *
 */

int
CS_client_init(void)
{
	krb5_error_code	retval;
	krb5_ccache		cc;
	krb5_creds		creds;
	krb5_creds		*outcreds;
	int			i;

	/* double initializations (without calling close_app) are sensless	*/
	/* so this will ignore such situations				*/

	if (int_ctx.flags & F_INIT) return (CS_SUCCESS);

	/* force everything to zero */

	memset(&int_ctx, 0, sizeof(KGlobal));

	/* Kerberos setup
	 * --------------
	 *  Before any other Kerberos functions are called, you must initialize
	 *  the Kerberos context with this function. If you are completely
	 *  done with Kerberos, you can free the context with
	 *  krb5_free_context()
	 */

	retval = krb5_init_context(&int_ctx.context);
	if (retval) {
		cs_logerr(-1, "CS_client_init", (char *)error_message(retval));
		return (CS_FATAL);
	}

	/*
	 * Before we can atually get a service ticket, we ned to
	 * initialize the credential cache. If we had a non-standard
	 * credential cache (like a memory one), we'd use another
	 * function as shown in CS_server_init, but if we're taking the
	 * default, we just use krb5_cc_default().
	 */

	retval = krb5_cc_default(int_ctx.context, &int_ctx.cc);
	if (retval) {
		cs_logerr(-1, "CS_client_init", (char *)error_message(retval));
		return (CS_FATAL);
	}

	/*
	 * We need to fill in our client principal name. We get this
	 * out of the credential cache (it's called the "primary principal").
	 * Use this to fill in creds.client
	 */

	retval = krb5_cc_get_principal(int_ctx.context,
		int_ctx.cc,
		&creds.client);
	if (retval) {
		cs_logerr(-1, "CS_client_init", (char *)error_message(retval));
		krb5_cc_close(int_ctx.context, int_ctx.cc);
		return (CS_FATAL);
	}

	int_ctx.flags = F_INIT | F_CLIENT;

	return (CS_SUCCESS);		/* always return success if no error */
}

/**
 * @brief
 * 	CS_server_init - the server initialization function for global security
 * 		    data
 * @par	usage:
 * 	r = CS_server_init();
 *
 * @return	int
 * @retval	initialization status
 *
 */

int
CS_server_init(void)
{
	SEC_ctx		*ctx = NULL;
	krb5_error_code	retval;
	krb5_ccache		cc;
	krb5_creds		creds;
	krb5_creds		*outcreds;
	char		*keytab;
	int			i;
	char		hostname[PBS_MAXHOSTNAME+1];

	/* double initializations (without calling close_app) are sensless	*/
	/* so this will ignore such situations				*/


	if (int_ctx.flags & F_INIT) return (CS_SUCCESS);

	/* force everything to zero */

	memset(&int_ctx, 0, sizeof(KGlobal));

	/* intialize Kerberos context */

	retval = krb5_init_context(&int_ctx.context);
	if (retval) {
		/* kerberos initialization failure */
		cs_logerr(-1, "CS_server_init",
			(char *)error_message(retval));
		return (CS_FATAL);
	}

	/* setup memory cache structure for servers */
	/* This specifies a memory cache which prevents ANY of the
	 * credentials derived from the keytab from appearing on disk.
	 * The parameters are:
	 * #1 - Kerberos 5 context
	 * #2 - name of the cache. This MUST be of the form "<type>:<spec>"
	 *      where the <type> must be one of the known cache types,
	 *      <spec> is interpreted by the cache type support. The known
	 *      <types> are:
	 *      FILE   - the usual, a disk file, and <spec> is the file name
	 *      MEMORY - memory resident, <spec> is ignored
	 *      PIPE   - (new in NRL version) and uses a socket to communicate
	 *      	     with a daemon to manage the cache.
	 *      API    - platform dependant and not always defined
	 *      MSLSA  - used only on MS Windows platforms
	 * #3 - pointer to the krb5_ccache variable to be intialized
	 */

	retval = krb5_cc_resolve(int_ctx.context,
		CACHENAME,
		&int_ctx.cc);
	if (retval) {
		cs_logerr(-1, "CS_server_init", (char *)error_message(retval));
		return (CS_FATAL);
	}

	/* evaluate location of the keytab file */

	int_ctx.kt = NULL;		/* the default must be NULL */
	retval = krb5_kt_resolve(int_ctx.context, KEYTAB, &int_ctx.kt);
	if (retval) {
		/* unable to resolve keytab */
		cs_logerr(-1, "CS_server_init", (char *)error_message(retval));
		krb5_free_context(int_ctx.context);
		return (CS_FATAL);
	}

	/* we must get a name for the PBS principal. This is the
	 * type/hostname format, where the hostname must be able
	 * to get the FQDN name.
	 */

	if (gethostname(hostname, (sizeof(hostname) - 1))) {
		if (int_ctx.kt) krb5_kt_close(int_ctx.context, int_ctx.kt);
		krb5_free_context(int_ctx.context);
		return (CS_FATAL);
	}

	/*
	 * We need to parse the service principal so we can use the "right"
	 * principal in the keytab. If we were to pass in a NULL to
	 * the principal argument of rd_req(), that would mean the code
	 * could accept any principal (which might be desirable in some
	 * multi-homed situations). This should be adjusted depending
	 * on the application need.
	 */

	retval = krb5_sname_to_principal(int_ctx.context,
		hostname,
		SERVICENAME,
		KRB5_NT_SRV_HST,
		&int_ctx.server);
	if (retval) {

		/* error parsing principal name */

		cs_logerr(-1, "CS_server_init", (char *)error_message(retval));
		if (int_ctx.kt) krb5_kt_close(int_ctx.context, int_ctx.kt);
		krb5_free_context(int_ctx.context);
		return (CS_FATAL);
	}

	int_ctx.flags = F_INIT | F_SERVER;

	return (CS_SUCCESS);		/* always return success if no error */
}

/**
 * @brief
 * 	CS_verify       - verify a user id (still to be developed)
 * 
 * @par	call:
 * 	r = CS_verify(???);
 *
 * @return	int
 * @retval	- verification status
 * @retval	CS_SUCCESS	    => start the user process
 * @retval	CS_FATAL_NOAUTH   => user is not authorized
 * @retval	CS_NOTIMPLEMENTED => do the old thing (rhosts)
 *
 * @par	note:
 * 	This should be invoked by an execution host to verify the user
 * 	Kerberos identity and the login that is going to be used. To
 * 	do this means the user principal will be:
 * 	    1.  verified with the KDC (as in retrieve a batch service
 * 	        ticket)
 * 	    2.  the KDC is verified by validating the batch service
 * 	        ticket
 * 	The result is that the user credentials are verified (ie, not
 * 	disabled, deleted, or otherwise non-functional), and the validated
 * 	principal + login can be verified together as authorized by one
 * 	of the following options:
 * 	    1. searching a local table for a (principal,login) record
 * 	       match
 * 	    2. having the user id  portion of the principal, match the
 * 	       login AND having the realm portion of the principal match
 * 	       the local realm
 * 	Final authorization is still left to PBS (as in, the login must
 * 	have a valid uid, gid, home directory, shell,... the usual UNIX
 * 	passwd authorizations)
 *------------------------------------------------------------------------
 */

int
CS_verify(void)
{
	return (CS_NOTIMPLEMENTED);
}

#if 0
/* May want to use Jesse' suggested interface at a future */

/**
 * @brief
 * 	CS_reset_vector - reset the chaining vectors associated the caller's
 * 	end of the connection.
 *
 * @par	call:
 *	r = CS_reset_vector ( sd );
 * 
 * @param[in]	fd	- socket descriptor
 * 
 * @return	int
 * @retval	- CS_SUCCESS 	if no problems
 * @retval	- CS_FATAL 	if problem occured
 * 
 * @par	note:
 * 	whenever this interface is used it has to be used on both
 * 	the client process and the server process, and for the same
 * 	communication, for the connection in question.
 *
 *	This interface was suggested by Jesse Pollard as a possible
 *	way to cope with keeping the encryption initialization vectors
 *	in sync between client and daemon.  Not being used but remains
 *	in the code as it may be of use with UDP messages, when those too
 *	become encrypted/decrypted.  This interface is not being exposed
 *	in the requirement/design document and libsec.h header files
 *	at this time.  These should be revised at the appropriate time.
 *
 */

int
CS_reset_vector(int sd)
{
	int	status;
	void	*ctx;

#if	(PBS_SECURITY == KCRYPT )

	if ((ctx = trak_return_ctx(sd, &status)) == NULL) {
		return (CS_FATAL);
	}

	return (cs_RESET_VECTOR((SEC_ctx *)ctx));
#endif

	/*PBS built for kerberos authentication only*/
	return (CS_SUCCESS);
}

/**
 * @brief
 * 	cs_RESET_VECTOR - reset security context's block chaining vector
 * 	initializations (vectors "input_ivec" and "output_ivec") for caller's
 * 	end of the connection.
 *
 * @par	call:
 * 	r = cs_RESET_VECTOR ( SEC_ctx *ctx )
 *
 * @param[in]      ctx - pointer to the connection's security context
 * 
 * @return	int
 * @retval	CS_SUCCESS	=> 	block chaining initialization vectors reset
 * @retval	CS_FATAL	=> 	chaining vector reset failed
 *
 */

static int
cs_RESET_VECTOR(SEC_ctx *pctx)
{
	SEC_ctx	*ctx;
	int		err;

	if (NULL == pctx)
		ctx = &int_ctx.single;
	else
		ctx = pctx;

	err = CS_FATAL;
	if (F_INIT & ctx->flags) {

		if (F_CLIENT & ctx->flags) {

			/* Note that when we transmit, we use an ivec of all zeros;
			 * when the server transmits, it uses all ones.
			 * NOTE: for base UDP these vectors must be reset after every
			 * packet.
			 */

			memset(ctx->input_ivec.data, 0xff, ctx->input_ivec.length);
			memset(ctx->output_ivec.data, 0, ctx->output_ivec.length);

			err = CS_SUCCESS;
		} else if (F_SERVER & ctx->flags) {

			/* Note that when we transmit, we use an ivec of all ones;
			 * when the client transmits, it uses all zeros.
			 * NOTE: for base UDP these vectors must be reset after every
			 * packet.
			 */

			memset(ctx->input_ivec.data, 0, ctx->input_ivec.length);
			memset(ctx->output_ivec.data, 0xff, ctx->output_ivec.length);
			err = CS_SUCCESS;
		}
	}
	return (err);
}
#endif

/**
 * @brief
 * 	CS_remap_ctx - interface is available to remap connection's context
 * 	to a new descriptor.   Old association is removed from the tracking
 * 	mechanism's data.
 *
 * @par	Functionality:
 * 	Should the socket descriptor associated with the connection get
 * 	replaced by a different descriptor (e.g. mom's call of the FDMOVE
 * 	macro for interactive qsub job) this is the interface to use to
 * 	make the needed adjustment to the tracking table.
 *
 * @param[in]  sd     connection's original socket descriptor
 * @param[in]  newsd  connection's new socket descriptor
 *
 * @return	int
 * @retval	CS_SUCCESS	success
 * @retval	CS_FATAL	error
 *
 * @par	Remark:  If the return value is CS_FATAL the connection should get
 *          CS_close_socket called on the original descriptor to cause
 *          a deallocation of the tracking table entry.  Subsequent to this
 *          the connection should then be closed.
 *
 */

int
CS_remap_ctx(int sd, int newsd)
{

	int	status;
	void	*ctx;

	if ((ctx = trak_return_ctx(sd, &status)) == NULL) {
		return (CS_FATAL);
	}

	if (trak_set_ent(newsd, ctx) == -1) {
		return (CS_FATAL);
	}

	if (trak_rls_ent(sd) != 0) {
		(void)trak_rls_ent(newsd);
		return (CS_FATAL);
	}
	return (CS_SUCCESS);
}

#endif /* defined(PBS_SECURITY) && ( ( PBS_SECURITY == KAUTH ) || ( PBS_SECURITY == KCRYPT ) ) */

/*endif   PBS_KRBZ */
