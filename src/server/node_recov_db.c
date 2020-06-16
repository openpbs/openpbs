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
 * @file    node_recov_db.c
 *
 * @brief
 *		node_recov_db.c - This file contains the functions to record a node
 *		data structure to database and to recover it from database.
 *
 */


#include <pbs_config.h>   /* the master config generated by configure */

#include <stdio.h>
#include <sys/types.h>

#include "pbs_ifl.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

#include <unistd.h>
#include "server_limits.h"
#include "list_link.h"
#include "attribute.h"

#include "log.h"
#include "attribute.h"
#include "list_link.h"
#include "server_limits.h"
#include "credential.h"
#include "libpbs.h"
#include "batch_request.h"
#include "pbs_nodes.h"
#include "job.h"
#include "resource.h"
#include "reservation.h"
#include "queue.h"
#include "svrfunc.h"
#include <memory.h>
#include "libutil.h"
#include "pbs_db.h"


/**
 * @brief
 *		convert from database to node structure
 *
 * @param[out]	pnode - Address of the node in the server
 * @param[in]	pdbnd - Address of the database node object
 *
 * @return	Error code
 * @retval   0 - Success
 * @retval  -1 - Failure
 *
 */
static int
db_2_node(struct pbsnode *pnode, pbs_db_node_info_t *pdbnd)
{
	if (pdbnd->nd_name && pdbnd->nd_name[0] != 0) {
		pnode->nd_name = strdup(pdbnd->nd_name);
		if (pnode->nd_name == NULL)
			return -1;
	}
	else
		pnode->nd_name = NULL;

	if (pdbnd->nd_hostname && (pdbnd->nd_hostname[0] != 0)) {
		pnode->nd_hostname = strdup(pdbnd->nd_hostname);
		if (pnode->nd_hostname == NULL)
			return -1;
	}
	else
		pnode->nd_hostname = NULL;

	pnode->nd_ntype = pdbnd->nd_ntype;
	pnode->nd_state = pdbnd->nd_state;
	if (pnode->nd_pque)
		strcpy(pnode->nd_pque->qu_qs.qu_name, pdbnd->nd_pque);

	if ((decode_attr_db(pnode, &pdbnd->cache_attr_list, &pdbnd->db_attr_list, node_attr_def, pnode->nd_attr, (int) ND_ATR_LAST, 0)) != 0)
		return -1;

	strcpy(pnode->nd_savetm, pdbnd->nd_savetm);

	return 0;
}


/**
 * @brief
 *		Recover a node from the database
 *
 * @param[in]	nd_name	- node name
 * @param[in]	pnode	- node pointer, if any, to be updated
 *
 * @return	The recovered node structure
 * @retval	NULL - Failure
 * @retval	!NULL - Success - address of recovered node returned
 */
struct pbsnode *
node_recov_db(char *nd_name, struct pbsnode *pnode)
{
	pbs_db_obj_info_t obj;
	pbs_db_conn_t *conn = (pbs_db_conn_t *) svr_db_conn;
	pbs_db_node_info_t dbnode = {{0}};
	int rc = 0;
	struct pbsnode *pnd = NULL;

	if (pnode)
		strcpy(dbnode.nd_savetm, pnode->nd_savetm);
	else {
		dbnode.nd_savetm[0] = '\0';
		if ((pnd = malloc(sizeof(struct pbsnode)))) {
			pnode = pnd;
			initialize_pbsnode(pnode, strdup(nd_name), NTYPE_PBS);
		} else {
			log_err(-1, __func__, "node_alloc failed");
			return NULL;
		}
	}

	strcpy(dbnode.nd_name, nd_name);
	obj.pbs_db_obj_type = PBS_DB_NODE;
	obj.pbs_db_un.pbs_db_node = &dbnode;

	rc = pbs_db_load_obj(conn, &obj);
	if (rc == -2)
		return pnode; /* no change in node, return the same pnode */

	if (rc == 0)
		rc = db_2_node(pnode, &dbnode);
	
	free_db_attr_list(&dbnode.db_attr_list);
	free_db_attr_list(&dbnode.cache_attr_list);

	if (rc != 0) {
		pnode = NULL; /* so we return NULL */
		if (pnd)
			free(pnd); /* free if we allocated here */
	}
	return pnode;
}

/**
 * @brief
 *		convert node structure to DB format
 *
 * @param[in]	pnode - Address of the node in the server
 * @param[out]	pdbnd - Address of the database node object
 *
 * @return 0    Success
 * @retval	>=0 What to save: 0=nothing, OBJ_SAVE_NEW or OBJ_SAVE_QS
 */
static int
node_2_db(struct pbsnode *pnode, pbs_db_node_info_t *pdbnd)
{
	int wrote_np = 0;
	svrattrl *psvrl, *tmp;
	int vnode_sharing = 0;
	int savetype = 0;

	strcpy(pdbnd->nd_name, pnode->nd_name);
	strcpy(pnode->nd_savetm, pdbnd->nd_savetm);

	savetype |= OBJ_SAVE_QS;
	/* nodes do not have a qs area, so we cannot check whether qs changed or not 
	 * hence for now, we always write the qs area, for now!
	 */
		
	/* node_index is used to sort vnodes upon recovery.
	* For Cray multi-MoM'd vnodes, we ensure that natural vnodes come
	* before the vnodes that it manages by introducing offsetting all
	* non-natural vnodes indices to come after natural vnodes.
	*/
	pdbnd->nd_index = (pnode->nd_nummoms * svr_totnodes) + pnode->nd_index;

	if (pnode->nd_hostname)
		strcpy(pdbnd->nd_hostname, pnode->nd_hostname);
	
	if (pnode->nd_moms && pnode->nd_moms[0])
		pdbnd->mom_modtime = pnode->nd_moms[0]->mi_modtime;
	
	pdbnd->nd_ntype = pnode->nd_ntype;
	pdbnd->nd_state = pnode->nd_state;
	if (pnode->nd_pque)
		strcpy(pdbnd->nd_pque, pnode->nd_pque->qu_qs.qu_name);
	else
		pdbnd->nd_pque[0] = 0;

	if ((encode_attr_db(node_attr_def, pnode->nd_attr, ND_ATR_LAST, &pdbnd->cache_attr_list, &pdbnd->db_attr_list, 0)) != 0)
		return -1;

	/* MSTODO: how can we optimize this loop - eliminate this? */
	psvrl = (svrattrl *) GET_NEXT(pdbnd->db_attr_list.attrs);
	while (psvrl != NULL) {
		if ((strcmp(psvrl->al_name, ATTR_rescavail) == 0) && (strcmp(psvrl->al_resc, "ncpus") == 0)) {
			wrote_np = 1;
			psvrl = (svrattrl *)GET_NEXT(psvrl->al_link);
			continue;
		}

		if (strcmp(psvrl->al_name, ATTR_NODE_pcpus) == 0) {
			/* don't write out pcpus at this point, see */
			/* check for pcpus if needed after loop end */
			tmp = (svrattrl *)GET_NEXT(psvrl->al_link); /* store next node pointer */
			delete_link(&psvrl->al_link);
			free(psvrl);
			pdbnd->db_attr_list.attr_count--;
			psvrl = tmp;
			continue;

		} else if (strcmp(psvrl->al_name, ATTR_NODE_resv_enable) == 0) {
			/*  write resv_enable only if not default value */
			if ((psvrl->al_flags & ATR_VFLAG_DEFLT) != 0) {
				tmp = (svrattrl *)GET_NEXT(psvrl->al_link); /* store next node pointer */
				delete_link(&psvrl->al_link);
				free(psvrl);
				pdbnd->db_attr_list.attr_count--;
				psvrl = tmp;
				continue;
			}
		}
		psvrl = (svrattrl *)GET_NEXT(psvrl->al_link);
	}

	/*
	 * Attributes with default values are not general saved to disk.
	 * However to deal with some special cases, things needed for
	 * attaching jobs to the vnodes on recover that we don't have
	 * except after we hear from Mom, i.e. we :
	 * 1. Need number of cpus, if it isn't writen as a non-default, as
	 *    "np", then write "pcpus" which will be treated as a default
	 * 2. Need the "sharing" attribute written even if default
	 *    and not the default value (i.e. it came from Mom).
	 *    so save it as the "special" [sharing] when it is a default
	 */
	if (wrote_np == 0) {
		char pcpu_str[10];
		svrattrl *pal;

		/* write the default value for the num of cpus */
		sprintf(pcpu_str, "%ld", pnode->nd_nsn);
		pal = make_attr(ATTR_NODE_pcpus, "", pcpu_str, 0);
		append_link(&pdbnd->db_attr_list.attrs, &pal->al_link, pal);

		pdbnd->db_attr_list.attr_count++;
	}

	if (vnode_sharing) {
		char *vn_str;
		svrattrl *pal;

		vn_str = vnode_sharing_to_str((enum vnode_sharing) pnode->nd_attr[ND_ATR_Sharing].at_val.at_long);
		pal = make_attr(ATTR_NODE_Sharing, "", vn_str, 0);
		append_link(&pdbnd->db_attr_list.attrs, &pal->al_link, pal);

		pdbnd->db_attr_list.attr_count++;
	}

	return savetype;
}

/**
 * @brief
 *	Save a node to the database. When we save a node to the database, delete
 *	the old node information and write the node afresh. This ensures that
 *	any deleted attributes of the node are removed, and only the new ones are
 *	updated to the database.
 *
 * @param[in]	pnode - Pointer to the node to save
 *
 * @return      Error code
 * @retval	0 - Success
 * @retval	-1 - Failure
 *
 */
int
node_save_db(struct pbsnode *pnode)
{
	pbs_db_node_info_t dbnode = {{0}};
	pbs_db_obj_info_t obj;
	pbs_db_conn_t *conn = (pbs_db_conn_t *) svr_db_conn;
	int savetype;
	int rc = -1;

	if ((savetype = node_2_db(pnode, &dbnode))  == -1)
		goto done;

	obj.pbs_db_obj_type = PBS_DB_NODE;
	obj.pbs_db_un.pbs_db_node = &dbnode;

	if ((rc = pbs_db_save_obj(conn, &obj, savetype)) != 0) {
		savetype |= (OBJ_SAVE_NEW | OBJ_SAVE_QS);
		rc = pbs_db_save_obj(conn, &obj, savetype);
	}

	if (rc == 0)
		strcpy(pnode->nd_savetm, dbnode.nd_savetm);
done:
	free_db_attr_list(&dbnode.db_attr_list);
	free_db_attr_list(&dbnode.cache_attr_list);
	
	if (rc != 0) {
		strcpy(log_buffer, "node_save failed ");
		if (conn->conn_db_err != NULL)
			strncat(log_buffer, conn->conn_db_err, LOG_BUF_SIZE - strlen(log_buffer) - 1);
		log_err(-1, __func__, log_buffer);
		panic_stop_db(log_buffer);
	}
	return rc;
}



/**
 * @brief
 *	Delete a node from the database
 *
 * @param[in]	pnode - Pointer to the node to delete
 *
 * @return      Error code
 * @retval	0 - Success
 * @retval	-1 - Failure
 *
 */
int
node_delete_db(struct pbsnode *pnode)
{
	pbs_db_node_info_t dbnode;
	pbs_db_obj_info_t obj;
	pbs_db_conn_t *conn = (pbs_db_conn_t *) svr_db_conn;

	strcpy(dbnode.nd_name, pnode->nd_name);
	obj.pbs_db_obj_type = PBS_DB_NODE;
	obj.pbs_db_un.pbs_db_node = &dbnode;

	if (pbs_db_delete_obj(conn, &obj) == -1)
		return (-1);
	else
		return (0);	/* "success" or "success but rows deleted" */
}
