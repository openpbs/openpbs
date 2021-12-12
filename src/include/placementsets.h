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
 * @file	placementsets.h
 *
 * @brief
 *	Manage vnodes and their associated attributes
 */

#ifndef _PBS_PLACEMENTSETS_H
#define _PBS_PLACEMENTSETS_H

#include <sys/types.h>
#include <stdio.h>
#include "pbs_idx.h"

/*
 *	This structure is used to describe a dynamically-sized list, one which
 *	grows when needed.
 */
typedef struct dynlist {
	unsigned long dl_nelem; /* number of elements in dl_list[] */
	unsigned long dl_used;	/* of which this many are used */
	unsigned long dl_cur;	/* the one currently being filled in */
	void *dl_list;
} dl_t;

/**
 * @brief
 * @verbatim
 *	The list of vnodes and their associated attributes is tracked and
 *	maintained using a list that looks like this:
 *
 *	 +------------------------------+			vnl_t
 *	 |  	file mod time	        |
 *	 +------------------------------+
 *	 |	index tree		|
 *	 +------------------------------+
 *	 |	size of vnode list  	|
 *	 |	number of used entries	|
 *	 |	current entry index 	|
 *	 +------------------------------+
 *	 |	pointer to list head |	|
 *	 +---------------------------|--+
 *				     |
 *				    \ /
 *	   +---------------------------------------+ 	 	vnal_t
 *	   |	vnode ID		     | ... |
 *	   +---------------------------------------+
 *	   |	size of vnode attribute list | 	   |
 *	   |	number of used entries	     | ... |
 *	   |	current entry index	     | 	   |
 *	   +---------------------------------------+
 *	   |	pointer to list head | 	     | ... |
 *	   +-------------------------|-------------+
 *				     |
 *				    \ /
 *	      		     +-------------------------+	vna_t
 *			     | 	 attribute name  | ... |
 *			     |------------------ |-----+
 *			     | 	 attribute value | ... |
 *			     |------------------ |-----+
 *			     | 	 attribute type  | ... |    in V4 of message
 *			     |------------------ |-----+
 *			     | 0 (will be flags) | ... |    in V4 of message
 *			     +-------------------------+
 * @endverbatim
 */
typedef struct vnode_list {
	time_t vnl_modtime; /* last mod time for these data */
	void *vnl_ix;	    /* index with vnode name as key */
	dl_t vnl_dl;	    /* current state of vnal_t list */
#define vnl_nelem vnl_dl.dl_nelem
#define vnl_used vnl_dl.dl_used
#define vnl_cur vnl_dl.dl_cur
	/* vnl_list is a list of vnal_t structures */
#define vnl_list vnl_dl.dl_list
} vnl_t;
#define VNL_NODENUM(vnlp, n) (&((vnal_t *) ((vnlp)->vnl_list))[n])
#define CURVNLNODE(vnlp) VNL_NODENUM(vnlp, (vnlp)->vnl_cur)

typedef struct vnode_attrlist {
	char *vnal_id; /* unique ID for this vnode */
	dl_t vnal_dl;  /* current state of vna_t list */
#define vnal_nelem vnal_dl.dl_nelem
#define vnal_used vnal_dl.dl_used
#define vnal_cur vnal_dl.dl_cur
	/* vnal_list is a list of vna_t structures */
#define vnal_list vnal_dl.dl_list
} vnal_t;
#define VNAL_NODENUM(vnrlp, n) (&((vna_t *) ((vnrlp)->vnal_list))[n])
#define CURVNRLNODE(vnrlp) VNAL_NODENUM(vnrlp, (vnrlp)->vnal_cur)

typedef struct vnode_attr {
	char *vna_name; /* attribute[.resource] name */
	char *vna_val;	/* attribute/resource  value */
	int vna_type;	/* attribute/resource  data type */
	int vna_flag;	/* attribute/resource  flags */
} vna_t;

#define PS_DIS_V1 1
#define PS_DIS_V2 2
#define PS_DIS_V3 3
#define PS_DIS_V4 4
#define PS_DIS_CURVERSION PS_DIS_V4

/**
 * @brief
 *	An attribute named VNATTR_PNAMES attached to a ``special'' vnode
 *	will have as its value the list of placement set types.
 */
#define VNATTR_PNAMES "pnames"

/**
 * @brief
 *	An attribute named VNATTR_HOOK_REQUESTOR attached to a ``special'' vnode
 *	will have as its value as the requestor (user@host) who is
 *	making a hook request to update vnodes information.
 */
#define VNATTR_HOOK_REQUESTOR "requestor"

/**
 * @brief
 *	An attribute named VNATTR_OFFLINE_VNODES attached to a `special' vnode
 *	will have a "1.<hook_name>" value to mean: a hook named <hook_name>
 *	instucted the server to 'offline_by_mom' all the vnodes managed by the mom owning
 *	this special vnode.
 *	A value of "0.<hook_name>" means a hook named <hook_name> instructed
 *	the server to 'clear offline_by_mom' states of all the vnodes managed by the mom
 *	owning the special vnode.
 */
#define VNATTR_HOOK_OFFLINE_VNODES "offline_vnodes"

/**
 * @brief
 *	An attribute named VNATTR_SCHEDULER_RESTART_CYCLE
 *	attached to a `special' vnode
 *	will have a "1,<hook_name>" value to mean a hook named
 *	<hook_name> has requested that a message be sent to the
 *	scheduler to restart its scheduling cycle.
 */
#define VNATTR_HOOK_SCHEDULER_RESTART_CYCLE "scheduler_restart_cycle"

typedef int(callfunc_t)(char *, char *, char *);

/**
 * @brief	add attribute to vnode
 *
 * @retval	0	success
 *
 * @retval	-1	failure
 */
extern int vn_addvnr(vnl_t *, char *, char *, char *, int, int, callfunc_t);

/**
 * @return
 *	an attribute in a vnal_t
 *
 * @retval	NULL	attribute does not exist
 */
extern char *attr_exist(vnal_t *, char *);

/**
 * @return	vnal_t	pointer to vnode
 * @retval	NULL	node does not exist
 */
extern vnal_t *vn_vnode(vnl_t *, char *);

/**
 * @return
 * the value of the attribute
 *
 * @retval	NULL	attribute does not exist
 */
extern char *vn_exist(vnl_t *, char *, char *);

/**
 * @brief	allocate new vnode list
 *
 * @return
 *	a pointer to an empty vnode list
 *
 * @retval	NULL	error
 *
 * @par Side-effects
 *	Space allocated for vnode list should be freed with vnl_free().
 */
extern vnl_t *vnl_alloc(vnl_t **);

/**
 * @brief	free vnode list
 */
extern void vnl_free(vnl_t *);

/**
 * @brief	merge new vnode list into existing list
 *
 * @return
 *	the existing vnode list
 *
 * @retval	NULL	error
 */
extern vnl_t *vn_merge(vnl_t *, vnl_t *, callfunc_t);

/**
 * @brief	merge new vnode list into existing list
 * 		for those vnodes with certain attribute names.
 *
 * @return
 *	the existing vnode list
 *
 * @retval	NULL	error
 */
extern vnl_t *vn_merge2(vnl_t *, vnl_t *, char **, callfunc_t);

/**
 * @brief	parse a file containing vnode information into a vnode list
 *
 * @return
 *	a pointer to the resulting vnode list
 *
 * @retval	NULL	error
 *
 * @par Side-effects
 *	Space allocated by the parse functions should be freed with vnl_free().
 */
extern vnl_t *vn_parse(const char *, callfunc_t);

/**
 * @brief	parse an already opened stream containing vnode information
 *
 * @return
 *	a pointer to the resulting vnode list
 *
 * @retval	NULL	error
 *
 * @par Side-effects
 *	Space allocated by the parse functions should be freed with vnl_free().
 */
extern vnl_t *vn_parse_stream(FILE *, callfunc_t);

/**
 * @brief	read a vnode list off the wire
 *
 * @return
 *	a pointer to the resulting vnode list
 *
 * @retval	NULL	error
 *
 * @par Side-effects
 *	Space allocated for vnode list should be freed with vnl_free().
 */
extern vnl_t *vn_decode_DIS(int, int *);

/**
 * @brief	send a vnode list over the network
 *
 * @return
 *	a DIS error code
 *
 * @retval	DIS_SUCCESS	success
 */
extern int vn_encode_DIS(int, vnl_t *);
#endif /* _PBS_PLACEMENTSETS_H */
