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
 *
 * @brief
 *	This file contains the functions to perform a buffered
 *	save of an object (structure) and an attribute array to a file.
 *	It also has the function to recover (reload) an attribute array.
 *
 */

#include <pbs_config.h>   /* the master config generated by configure */

#include "pbs_ifl.h"
#include <assert.h>
#include <errno.h>
#include <memory.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include "list_link.h"
#include "attribute.h"
#include "log.h"
#include "pbs_nodes.h"
#include "svrfunc.h"


/* Global Variables */

extern int resc_access_perm;

char  pbs_recov_filename[MAXPATHLEN+1];

/* data items global to functions in this file */

#define PKBUFSIZE 4096
#define ENDATTRIBUTES -711

char   pk_buffer[PKBUFSIZE];	/* used to do buffered output */
static int     pkbfds = -2;	/* descriptor to use for saves */
static size_t  spaceavail;	/* space in pk_buffer available */
static size_t  spaceused;	/* amount of space used  in pkbuffer */


/**
 * @brief
 * 		save_setup - set up the save i/o buffer.
 *		The "buffer control information" is left updated to reflect
 *		the file descriptor, and the space in the buffer.
 * @param[in]	fds - file descriptor value
 */

void
save_setup(int fds)
{

	if (pkbfds != -2) {	/* somebody forgot to flush the buffer */
		log_err(-1, "save_setup", "someone forgot to flush");
	}

	/* initialize buffer control */

	pkbfds = fds;
	spaceavail = PKBUFSIZE;
	spaceused = 0;
}

/**
 * @brief
 * 		save_struct - Copy a structure (as a block)  into the save i/o buffer
 *		This is useful to save fixed sized structure without pointers
 *		that point outside of the structure itself.
 *
 *	Write out buffer as required. Leave spaceavail and spaceused updated
 *
 * @param[in]	pobj - pointer to the structure whose contents needs to be copied into a buffer.
 * @param[in]	objsize - required size of the object.
 *
 * @return      Error code
 * @retval	 0  - Success
 * @retval	-1  - Failure
 */

int
save_struct(char *pobj, unsigned int objsize)
{
	int	 amt;
	size_t	 copysize;
	int      i;
	char	*pbufin;
	char	*pbufout;


	assert(pkbfds >= 0);

	while (objsize > 0) {
		pbufin = pk_buffer + spaceused;
		if (objsize > spaceavail) {
			if ((copysize = spaceavail) != 0) {
				(void)memcpy(pbufin, pobj, copysize);
			}
			amt = PKBUFSIZE;
			pbufout = pk_buffer;
			while ((i=write(pkbfds, pbufout, amt)) != amt) {
				if (i == -1) {
					if (errno != EINTR) {
						return (-1);
					}
				} else {
					amt -= i;
					pbufout += i;
				}
			}
			pobj += copysize;
			spaceavail = PKBUFSIZE;
			spaceused  = 0;
		} else {
			copysize = (size_t)objsize;
			(void)memcpy(pbufin, pobj, copysize);
			spaceavail -= copysize;
			spaceused  += copysize;
		}
		objsize   -= copysize;
	}
	return (0);
}


/**
 * @buffer
 * 		save_flush - flush out the current save operation
 *		Flush buffer if needed, reset spaceavail, spaceused,
 *		clear out file descriptor
 *
 *	Returns: 0 on success
 *		-1 on failure (flush failed)
 */

int
save_flush(void)
{
	int i;
	char *pbuf;

	assert(pkbfds >= 0);

	pbuf = pk_buffer;
	if (spaceused > 0) {
		while ((i=write(pkbfds, pbuf, spaceused)) != spaceused) {
			if (i == -1) {
				if (errno != EINTR) {
					log_err(errno, "save_flush", "bad write");
					return (-1);
				}
			} else {
				pbuf += i;
				spaceused -= i;
			}
		}
	}
	pkbfds  = -2;	/* flushed flag */
	return (0);
}


/**
 * @brief
 *	 	Write set of attributes to disk file
 *
 * @par	Functionality:
 *		Each of the attributes is encoded  into the attrlist form.
 *		They are packed and written using save_struct().
 *
 *		The final real attribute is followed by a dummy attribute with a
 *		al_size of ENDATTRIB.  This cannot be mistaken for the size of a
 *		real attribute.
 *
 *		Note: attributes of type ATR_TYPE_ACL are not saved with the other
 *		attribute of the parent (queue or server).  They are kept in their
 *		own file.
 *
 * @param[in]	padef - Address of parent's attribute definition array
 * @param[in]	pattr - Address of the parent objects attribute array
 * @param[in]	numattr - Number of attributes in the list
 *
 * @return      Error code
 * @retval	 0  - Success
 * @retval	-1  - Failure
 */
int
save_attr_fs(attribute_def *padef, attribute *pattr, int numattr)
{
	svrattrl	 dummy;
	int		 errct = 0;
	pbs_list_head 	 lhead;
	int		 i;
	svrattrl	*pal;
	int		 rc;

	/* encode each attribute which has a value (not non-set) */

	CLEAR_HEAD(lhead);

	for (i = 0; i < numattr; i++) {

		if ((padef+i)->at_type != ATR_TYPE_ACL) {

			/* note access lists are not saved this way */

			rc = (padef+i)->at_encode(pattr+i, &lhead,
				(padef+i)->at_name,
				NULL, ATR_ENCODE_SAVE, NULL);

			if (rc < 0)
				errct++;

			(pattr+i)->at_flags &= ~ATR_VFLAG_MODIFY;

			/* now that it has been encoded, block and save it */

			while ((pal = (svrattrl *)GET_NEXT(lhead)) !=
				NULL) {

				if (save_struct((char *)pal, pal->al_tsize) < 0)
					errct++;
				delete_link(&pal->al_link);
				(void)free(pal);
			}
		}
	}

	/* indicate last of attributes by writting dummy entry */

#ifdef DEBUG
	(void)memset(&dummy, 0, sizeof(dummy));
#endif
	dummy.al_tsize = ENDATTRIBUTES;
	if (save_struct((char *)&dummy, sizeof(dummy)) < 0)
		errct++;


	if (errct)
		return (-1);
	else
		return (0);
}


/**
 * @brief
 *		read attributes from disk file
 *
 *		Recover (reload) attribute from file written by save_attr().
 *		Since this is not often done (only on server initialization),
 *		Buffering the reads isn't done.
 *
 * @param[in]	fd - The file descriptor of the file to write to
 * @param[in] 	parent - void pointer to one of the PBS objects
 *					  to whom these attributes belong
 * @param[in]   padef_idx - Search index of this attribute definition array
 * @param[in]	padef - Address of parent's attribute definition array
 * @param[in]	pattr - Address of the parent objects attribute array
 * @param[in]	limit - Index of the last attribute
 * @param[in]	unknown - Index of the start of the unknown attribute list
 *
 * @return      Error code
 * @retval	 0  - Success
 * @retval	-1  - Failure
 */

int
recov_attr_fs(int fd, void *parent, void *padef_idx, attribute_def *padef, attribute *pattr, int limit, int unknown)
{
	int	  amt;
	int	  len;
	int	  index;
	svrattrl *pal = NULL;
	int	  palsize = 0;
	svrattrl *tmpal = NULL;

	pal = (svrattrl *)malloc(sizeof(svrattrl));
	if (!pal)
		return (-1);
	palsize = sizeof(svrattrl);

	/* set all privileges (read and write) for decoding resources	*/
	/* This is a special (kludge) flag for the recovery case, see	*/
	/* decode_resc() in lib/Libattr/attr_fn_resc.c			*/

	resc_access_perm = ATR_DFLAG_ACCESS;

	/* For each attribute, read in the attr_extern header */

	while (1) {
		errno = -1;
		memset(pal, 0, palsize);
		len = read(fd, (char *)pal, sizeof(svrattrl));
		if (len != sizeof(svrattrl)) {
			sprintf(log_buffer, "read1 error of %s",
				pbs_recov_filename);
			log_err(errno, __func__, log_buffer);
			free(pal);
			return (errno);
		}
		if (pal->al_tsize == ENDATTRIBUTES)
			break;		/* hit dummy attribute that is eof */
		amt = pal->al_tsize - sizeof(svrattrl);
		if (amt < 1) {
			sprintf(log_buffer, "Invalid attr list size in %s",
				pbs_recov_filename);
			log_err(errno, __func__, log_buffer);
			free(pal);
			return (errno);
		}

		/* read in the attribute chunk (name and encoded value) */

		if (palsize < pal->al_tsize) {
			tmpal = (svrattrl *)realloc(pal, pal->al_tsize);
			if (tmpal == NULL) {
				sprintf(log_buffer,
					"Unable to alloc attr list size in %s",
					pbs_recov_filename);
				log_err(errno, __func__, log_buffer);
				free(pal);
				return (errno);
			}
			pal = tmpal;
			palsize = pal->al_tsize;
		}
		if (!pal)
			return (errno);
		CLEAR_LINK(pal->al_link);

		/* read in the actual attribute data */

		len = read(fd, (char *)pal + sizeof(svrattrl), amt);
		if (len != amt) {
			sprintf(log_buffer, "read2 error of %s",
				pbs_recov_filename);
			log_err(errno, __func__, log_buffer);
			free(pal);
			return (errno);
		}

		/* the pointer into the data are of course bad, so reset them */

		pal->al_name = (char *)pal + sizeof(svrattrl);
		if (pal->al_rescln)
			pal->al_resc = pal->al_name + pal->al_nameln;
		else
			pal->al_resc = NULL;
		if (pal->al_valln)
			pal->al_value = pal->al_name + pal->al_nameln +
				pal->al_rescln;
		else
			pal->al_value = NULL;

		pal->al_refct = 1;	/* ref count reset to 1 */

		/* find the attribute definition based on the name */

		index = find_attr(padef_idx, padef, pal->al_name);
		if (index < 0) {
			/*
			 * There are two ways this could happen:
			 * 1. if the (job) attribute is in the "unknown" list -
			 *    keep it there;
			 * 2. if the server was rebuilt and an attribute was
			 *    deleted, -  the fact is logged and the attribute
			 *    is discarded (system,queue) or kept (job)
			 */
			if (unknown > 0) {
				index = unknown;
			} else {
				log_errf(-1, __func__, "unknown attribute \"%s\" discarded", pal->al_name);
				continue;
			}
		}

		/*
		 * In the normal case we just decode the attribute directly
		 * into the real attribute since there will be one entry only
		 * for that attribute.
		 *
		 * However, "entity limits" are special and may have multiple,
		 * the first of which is "SET" and the following are "INCR".
		 * For the SET case, we do it directly as for the normal attrs.
		 * For the INCR,  we have to decode into a temp attr and then
		 * call set_entity to do the INCR.
		 */

		if (((padef+index)->at_type != ATR_TYPE_ENTITY) ||
			(pal->al_atopl.op != INCR)) {
			if ((padef+index)->at_decode) {
				(void)(padef+index)->at_decode(pattr+index,
					pal->al_name, pal->al_resc, pal->al_value);
				if ((padef+index)->at_action)
					(void)(padef+index)->at_action(pattr+index,
						parent, ATR_ACTION_RECOV);
			}
		} else {
			attribute tmpa;
			memset(&tmpa, 0, sizeof(attribute));
			/* for INCR case of entity limit, decode locally */
			if ((padef+index)->at_decode) {
				(void)(padef+index)->at_decode(&tmpa,
					pal->al_name, pal->al_resc, pal->al_value);
				(void)(padef+index)->at_set(pattr+index, &tmpa, INCR);
				(void)(padef+index)->at_free(&tmpa);
			}
		}
		(pattr+index)->at_flags = pal->al_flags & ~ATR_VFLAG_MODIFY;
	}

	(void)free(pal);
	return (0);
}
