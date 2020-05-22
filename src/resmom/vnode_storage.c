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

#ifdef  PBS_MOM
#ifdef	WIN32
#include	"pbs_config.h"
#endif
#include	<stdlib.h>
#include	<string.h>
#include	<stdio.h>
#include	<errno.h>
#include	<assert.h>
#include	"libpbs.h"
#include	"log.h"
#include	"server_limits.h"
#include	"attribute.h"
#include	"placementsets.h"
#include	"resource.h"
#include	"pbs_nodes.h"

#ifdef	DEBUG
extern void	mom_CPUs_report();
#endif	/* DEBUG */

/**
 * @file
 */
/**
 * @brief
 *	creates vnode map
 *
 * @param[in] ctxp - pointer to pointer to vnodes
 *
 * @return 	int
 * @retval 	1	Success
 * @retval 	0 	Failure
 *
 */

int
create_vmap(void **ctxp)
{
	static AVL_IX_DESC	*pix;

	assert(ctxp != NULL);

	if (*ctxp == NULL) {
		if ((pix = malloc(sizeof(AVL_IX_DESC))) == NULL) {
			log_err(errno, __func__, "create_vmap malloc failed");
			*ctxp = NULL;
			return (0);
		} else
			*ctxp = pix;
		if (avl_create_index(pix, AVL_NO_DUP_KEYS, 0))
			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER, LOG_ERR, __func__, "Failed to create vnode map");
	}

	return (1);
}

/**
 * @brief
 *	destroys the vnode map
 *
 * @param[in] ctx - char pointer to node
 *
 * @return Void
 *
 */
void
destroy_vmap(void *ctx)
{
	assert(ctx != NULL);
	avl_destroy_index(ctx);
	free(ctx);
}

/**
 * @brief
 *	finds vnode map entry by vnode id
 *
 * @param[in] ctx - char pointer to vnode
 * @param[in] vnid - vnode id
 *
 * @return 	structure handle
 * @retval  	pointer to mominfo_t structure on success else NULL
 *
 */
mominfo_t *
find_vmapent_byID(void *ctx, const char *vnid)
{
	AVL_IX_REC      *pe;

	if ((pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1)) != NULL) {
		(void) strncpy(pe->key, vnid, PBS_MAXNODENAME);
		if (avl_find_key(pe, ctx) == AVL_IX_OK)
			return ((mominfo_t *) pe->recptr);
	} else {
		log_err(errno, __func__, "malloc pe failed");
#ifdef	DEBUG
		mom_CPUs_report();
#endif	/* DEBUG */
	}

	free (pe);
	return NULL;
}


/**
 * @brief
 *	adds vnode to vnode map by vnode id.
 *
 * @param[in] ctx - char pointer to vnode
 * @param[in] vnid - vnode id
 * @param[in] data - information about vnode
 *
 * @return 	int
 * @retval 	0	Success
 * @retval 	1	Failure
 *
 */
int
add_vmapent_byID(void *ctx, const char *vnid, void *data)
{
	AVL_IX_REC     	*pe = NULL;
	int rc = 0;

	if ((pe = malloc(sizeof(AVL_IX_REC) + PBS_MAXNODENAME + 1)) != NULL) {
		(void) strncpy(pe->key, vnid, PBS_MAXNODENAME);
		pe->recptr = data;
		if (avl_add_key(pe, ctx) != AVL_IX_OK) {
			rc = 1;
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__, "avl_add_key failed");
		}
	} else {
		rc = 1;
		log_err(errno, __func__, "malloc pe failed");
	}
	free(pe);
	return rc;
}
#endif	/* PBS_MOM */
