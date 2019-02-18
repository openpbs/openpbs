/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
#ifndef	_RESV_INFO_H
#define	_RESV_INFO_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <pbs_config.h>
#include "data_types.h"

/*
 *	stat_resvs - status the reservations in batch_status form from the
 *	server
 */
struct batch_status *stat_resvs(int pbs_sd);

/*
 *	query_reservations - query the reservations from the server
 */
resource_resv **query_reservations(server_info *sinfo, struct batch_status *resvs);

/*
 *	query_resv_info - convert the servers batch_statys structure into a
 */
resource_resv *query_resv(struct batch_status *resv, server_info *sinfo);

/*
 *	new_resv_info - allocate and initialize new resv_info structure
 */
#ifdef NAS /* localmod 005 */
resv_info *new_resv_info(void);
#else
resv_info *new_resv_info();
#endif /* localmod 005 */

/*
 *	free_resv_info - free all the memory used by a rev_info structure
 */
void free_resv_info(resv_info *rinfo);

/*
 *	dup_resv_info - duplicate a reservation
 */
resv_info *dup_resv_info(resv_info *rinfo, server_info *sinfo);

/*
 *      check_new_reservations - check for new reservations and handle them
 *                               if we can serve the reservation, we reserve it
 *                               and if we can't, we delete the reservation
 */
int check_new_reservations(status *policy, int pbs_sd, resource_resv **resvs, server_info *sinfo);

/**
 *      confirm_reservation - attempts to confirm a resource reservation
 */
int confirm_reservation(status *policy, int pbs_sd, resource_resv *nresv, server_info *sinfo);

/**
 *      counts the number of vnodes associated to a reservation that are not
 *                               available
 */
int check_vnodes_down(node_info **ninfo_arr, int * total_vnodes, char *vnodes_down_name);

/**
 * Release reousrces allocated to a reservation
 */
void release_nodes(resource_resv *resc_resv);

/*
 *	create_resv_nodes - create a node universe for a reservation
 */
node_info **create_resv_nodes(nspec **nspec_arr, server_info *sinfo);

/*
 *	adjust_alter_resv_nodes - adjust nodes resources for reservations that
 *				  that are being altered.
 */
void adjust_alter_resv_nodes(resource_resv **all_resvs, node_info **all_nodes);

/* Will we try and confirm this reservation in this cycle */
int will_confirm(resource_resv *resv, time_t server_time);

#ifdef	__cplusplus
}
#endif
#endif /* _RESV_INFO_H */
