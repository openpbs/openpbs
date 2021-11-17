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

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>
#include <assert.h>
#include "dis.h"
#include "placementsets.h"

static vnl_t *vn_decode_DIS_V3(int, int *);
static vnl_t *vn_decode_DIS_V4(int, int *);
static int vn_encode_DIS_V4(int, vnl_t *);
static vnl_t *free_and_return(vnl_t *); /* expedient error function */
/**
 * @file	ps_dis.c
 */
/**
 * @brief
 *	vn_decode_DIS - read verison 3 or 4 vnode definition information from
 * Mom.
 * @par Functionality:
 *	The V4 over-the-wire representation of a placement set list (vnl_t) is
 *	a superset of V3.  V4 adds the ability to specify the type of an
 *	attribute/resource (and reserves a place in the protocol for flags).
 *	The V3 over-the-wire representation of a placement set list (vnl_t) is
 *
 *	version		unsigned integer	the version of the following
 *						information
 *
 *	Version PS_DIS_V3 consists of
 *
 *	vnl_modtime	signed long		this OTW format could be
 *						problematic:   the Open Group
 *						Base Specifications Issue 6
 *						says that time_t ``shall be
 *						integer or real-floating''
 *
 *	vnl_used	unsigned integer	number of entries in the vnal_t
 *						array to follow
 *
 *
 *	There follows, for each element of the vnal_t array,
 *
 *	vnal_id		string
 *
 *	vnal_used	unsigned integer	number of entries in the vna_t
 *						array to follow
 *
 *	vna_name	string			name of resource
 *	vna_val		string			value of resource
 *		Following added in V4
 *	vna_type	int			type of attribute/resource
 *	vna_flag	int			flag of attribute/resource (-h)
 *
 *
 * @param[in]	fd  - file (socket) descriptor from which to read
 * @param[out]	rcp - pointer to int into which to return the error value,
 *			either DIS_SUCCESS or some DIS_* error.
 *
 * @return	vnl_t *
 * @retval	pointer to decoded vnode information which has been malloc-ed.
 * @retval	NULL on error, see rcp value
 *
 * @par Side Effects: None
 *
 * @par MT-safe: yes
 *
 */
vnl_t *
vn_decode_DIS(int fd, int *rcp)
{
	unsigned int vers;

	vers = disrui(fd, rcp);
	if (*rcp != DIS_SUCCESS)
		return NULL;

	switch (vers) {
		case PS_DIS_V3:
			return (vn_decode_DIS_V3(fd, rcp));
		case PS_DIS_V4:
			return (vn_decode_DIS_V4(fd, rcp));

		default:
			*rcp = DIS_PROTO;
			return NULL;
	}
}

/**
 * @brief
 *	vn_decode_DIS_V4 - decode version 4 vnode information from Mom
 *
 * @par Functionality:
 *	See vn_decode_DIS() above, This is called from there to decode
 *	V4 information.
 *
 * @param[in]	fd  -     socket descriptor from which to read
 * @param[out]	rcp -     pointer to place to return error code if error.
 *
 * @return	vnl_t *
 * @retval	pointer to decoded vnode information which has been malloc-ed.
 * @retval	NULL on error, see rcp value
 *
 * @par Side Effects: None
 *
 * @par MT-safe: yes
 *
 */
static vnl_t *
vn_decode_DIS_V4(int fd, int *rcp)
{
	unsigned int i, j;
	unsigned int size;
	time_t t;
	vnl_t *vnlp;

	if ((vnlp = calloc(1, sizeof(vnl_t))) == NULL) {
		*rcp = DIS_NOMALLOC;
		return NULL;
	}

	t = (time_t) disrsl(fd, rcp);
	if (*rcp != DIS_SUCCESS) {
		free(vnlp);
		return NULL;
	} else {
		vnlp->vnl_modtime = t;
	}
	size = disrui(fd, rcp);
	if (*rcp != DIS_SUCCESS) {
		free(vnlp);
		return NULL;
	} else {
		vnlp->vnl_nelem = vnlp->vnl_used = size;
	}

	if ((vnlp->vnl_list = calloc(vnlp->vnl_nelem,
				     sizeof(vnal_t))) == NULL) {
		free(vnlp);
		*rcp = DIS_NOMALLOC;
		return NULL;
	}

	for (i = 0; i < vnlp->vnl_used; i++) {
		vnal_t *curreslist = VNL_NODENUM(vnlp, i);

		/*
		 *	In case an error occurs and we need to free
		 *	whatever's been allocated so far, we use the
		 *	vnl_cur entry to record the number of vnal_t
		 *	entries to free.
		 */
		vnlp->vnl_cur = i;

		curreslist->vnal_id = disrst(fd, rcp);
		if (*rcp != DIS_SUCCESS)
			return (free_and_return(vnlp));

		size = disrui(fd, rcp);
		if (*rcp != DIS_SUCCESS)
			return (free_and_return(vnlp));
		else
			curreslist->vnal_nelem = curreslist->vnal_used = size;
		if ((curreslist->vnal_list = calloc(curreslist->vnal_nelem,
						    sizeof(vna_t))) == NULL)
			return (free_and_return(vnlp));

		for (j = 0; j < size; j++) {
			vna_t *curres = VNAL_NODENUM(curreslist, j);

			/*
			 *	In case an error occurs and we need to free
			 *	whatever's been allocated so far, we use the
			 *	vnal_cur entry to record the number of vna_t
			 *	entries to free.
			 */
			curreslist->vnal_cur = j;

			curres->vna_name = disrst(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
			curres->vna_val = disrst(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
			curres->vna_type = disrsi(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
			curres->vna_flag = disrsi(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
		}
	}

	*rcp = DIS_SUCCESS;
	return (vnlp);
}

/**
 * @brief
 *	vn_decode_DIS_V3 - decode version 3 vnode information from Mom
 *
 * @par Functionality:
 *	See vn_decode_DIS() above, This is called from there to decode
 *	V3 information.
 *
 * @param[in]	fd  -     socket descriptor from which to read
 * @param[out]	rcp -     pointer to place to return error code if error.
 *
 * @return	vnl_t *
 * @retval	pointer to decoded vnode information which has been malloc-ed.
 * @retval	NULL on error, see rcp value
 *
 * @par Side Effects: None
 *
 * @par MT-safe: yes
 *
 */
static vnl_t *
vn_decode_DIS_V3(int fd, int *rcp)
{
	unsigned int i, j;
	unsigned int size;
	time_t t;
	vnl_t *vnlp;

	if ((vnlp = calloc(1, sizeof(vnl_t))) == NULL) {
		*rcp = DIS_NOMALLOC;
		return NULL;
	}

	t = (time_t) disrsl(fd, rcp);
	if (*rcp != DIS_SUCCESS) {
		free(vnlp);
		return NULL;
	} else
		vnlp->vnl_modtime = t;
	size = disrui(fd, rcp);
	if (*rcp != DIS_SUCCESS) {
		free(vnlp);
		return NULL;
	} else
		vnlp->vnl_nelem = vnlp->vnl_used = size;

	if ((vnlp->vnl_list = calloc(vnlp->vnl_nelem,
				     sizeof(vnal_t))) == NULL) {
		free(vnlp);
		*rcp = DIS_NOMALLOC;
		return NULL;
	}

	for (i = 0; i < vnlp->vnl_used; i++) {
		vnal_t *curreslist = VNL_NODENUM(vnlp, i);

		/*
		 *	In case an error occurs and we need to free
		 *	whatever's been allocated so far, we use the
		 *	vnal_cur entry to record the number of vnal_t
		 *	entries to free.
		 */
		vnlp->vnl_cur = i;

		curreslist->vnal_id = disrst(fd, rcp);
		if (*rcp != DIS_SUCCESS)
			return (free_and_return(vnlp));

		size = disrui(fd, rcp);
		if (*rcp != DIS_SUCCESS)
			return (free_and_return(vnlp));
		else
			curreslist->vnal_nelem = curreslist->vnal_used = size;
		if ((curreslist->vnal_list = calloc(curreslist->vnal_nelem,
						    sizeof(vna_t))) == NULL)
			return (free_and_return(vnlp));

		for (j = 0; j < size; j++) {
			vna_t *curres = VNAL_NODENUM(curreslist, j);

			/*
			 *	In case an error occurs and we need to free
			 *	whatever's been allocated so far, we use the
			 *	vnal_cur entry to record the number of vna_t
			 *	entries to free.
			 */
			curreslist->vnal_cur = j;

			curres->vna_name = disrst(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
			curres->vna_val = disrst(fd, rcp);
			if (*rcp != DIS_SUCCESS)
				return (free_and_return(vnlp));
		}
	}

	*rcp = DIS_SUCCESS;
	return (vnlp);
}

/**
 * @brief
 *	vn_encode_DIS - encode vnode information, used by Mom.
 *
 * @par Functionality:
 *	Used to encode vnode information.  See vn_decode_DIS() above for a
 *	description of the information encoded/decoded.  Only the latest
 *	version of information is currently supported for encode.
 *
 * @param[in]	fd   - socket descriptor to which to write the encode info.
 * @param[in]	vnlp - structure to encode and send.
 *
 * @return	int
 * @retval	DIS_SUCCESS (0) on success
 * @retval	DIS_* on error.
 *
 * @par Side Effects: None
 *
 * @par MT-safe: No, the structure pointed to by vnlp needs to be locked
 *
 */
int
vn_encode_DIS(int fd, vnl_t *vnlp)
{
	switch (PS_DIS_CURVERSION) {
		case PS_DIS_V4:
			return (vn_encode_DIS_V4(fd, vnlp));

		default:
			return (DIS_PROTO);
	}
}

/**
 * @brief
 *	vn_encode_DIS_V4 - encode version 4 vnode information, used by Mom.
 *
 * @par Functionality:
 *	Used to encode vnode information.  See vn_encode_DIS() above for a
 *	description of the information.  Supports version 4 only.
 *
 * @param[in]	fd   - socket descriptor to which to write the encode info.
 * @param[in]	vnlp - structure to encode and send.
 *
 * @return	int
 * @retval	DIS_SUCCESS (0) on success
 * @retval	DIS_* on error.
 *
 * @par Side Effects: None
 *
 * @par MT-safe: No, the structure pointed to by vnlp needs to be locked
 *
 */
static int
vn_encode_DIS_V4(int fd, vnl_t *vnlp)
{
	int rc;
	unsigned int i, j;

	if (((rc = diswui(fd, PS_DIS_V4)) != 0) ||
	    ((rc = diswsl(fd, (long) vnlp->vnl_modtime)) != 0) ||
	    ((rc = diswui(fd, vnlp->vnl_used)) != 0))
		return (rc);

	for (i = 0; i < vnlp->vnl_used; i++) {
		vnal_t *curreslist = VNL_NODENUM(vnlp, i);

		if ((rc = diswst(fd, curreslist->vnal_id)) != 0)
			return (rc);
		if ((rc = diswui(fd, curreslist->vnal_used)) != 0)
			return (rc);

		for (j = 0; j < curreslist->vnal_used; j++) {
			vna_t *curres = VNAL_NODENUM(curreslist, j);

			if ((rc = diswst(fd, curres->vna_name)) != 0)
				return (rc);
			if ((rc = diswst(fd, curres->vna_val)) != 0)
				return (rc);
			if ((rc = diswsi(fd, curres->vna_type)) != 0)
				return (rc);
			if ((rc = diswsi(fd, curres->vna_flag)) != 0)
				return (rc);
		}
	}

	return (DIS_SUCCESS);
}

/**
 * @brief
 *	free_and_return - free a vnl_t data structure.
 *
 * @par Functionality:
 *	Note that this function is nearly identical to vnl_free() (q.v.),
 *	with the exception of using the *_cur values to free partially-
 *
 * @param[in]	vnlp - pointer to structure to free
 *
 * @return	vnl_t *
 * @retval	NULL
 *
 * @par Side Effects: None
 *
 * @par MT-safe: No, vnlp needs to be locked.
 *
 */
static vnl_t *
free_and_return(vnl_t *vnlp)
{
	unsigned int i, j;

	/* N.B. <=, not < because we may have a partially-allocated ith one */
	for (i = 0; i <= vnlp->vnl_cur; i++) {
		vnal_t *vnrlp = VNL_NODENUM(vnlp, i);

		/* N.B. <=, not < (as above) for partially-allocated jth one */
		for (j = 0; j <= vnrlp->vnal_cur; j++) {
			vna_t *vnrp = VNAL_NODENUM(vnrlp, j);
			free(vnrp->vna_name);
			free(vnrp->vna_val);
		}
		free(vnrlp->vnal_list);
		free(vnrlp->vnal_id);
	}
	free(vnlp->vnl_list);
	free(vnlp);

	return NULL;
}
