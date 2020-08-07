/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
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
/**
 * @file    licensing_func.c
 *
 * @brief
 * 		licensing_func.c - miscellaneous server functions
 *
 * Functions included are:
 *
 */

#include <time.h>
#include "pbs_nodes.h"
#include "pbs_license.h"
#include "server.h"
#include "work_task.h"
#include "liblicense.h"
#include "svrfunc.h"

#define TEMP_BUF_LEN 20

pbs_licensing_control licensing_control;
pbs_license_counts license_counts;
struct work_task *init_licensing_task;
struct work_task *get_more_licenses_task;
struct work_task *licenses_linger_time_task;
extern time_t time_now;
/**
 * @brief
 * 	consume_licenses - use count licenses from the pool of
 * 			   already checked out licenses.
 *
 * @param[in]	- count	- number of licenses to consume
 *
 * @return int
 * @retval  0 - success - able to consume count licenses
 * @retval -1 - not enough licenses available.
 */
static int
consume_licenses(long count)
{
	if (count <= license_counts.licenses_local) {
		license_counts.licenses_local -= count;
		license_counts.licenses_used += count;
		return 0;
	} else
		return -1;
}

/**
 * @brief
 * 	return_licenses - return count licenses back to the
 * 			  pool of already checked out licenses.
 *
 * @param[in]	- count	- number of licenses to consume
 *
 * @return void
 */
static void
return_licenses(long count)
{
	license_counts.licenses_local += count;
	license_counts.licenses_used -= count;
}

/**
 * @brief
 * 	add_to_unlicensed_node_list - add a node to the list
 * 				      of unlicensed nodes
 *
 * @param[in]	- index - index of the node
 *
 * @return void
 */
static void
add_to_unlicensed_node_list(struct pbsnode *pnode)
{
	unlicensed_node *pun;

	if (pnode->nd_added_to_unlicensed_list)
		return;

	pun = malloc(sizeof(unlicensed_node));
	if (!pun)
		return;

	pun->pnode = pnode;
	CLEAR_LINK(pun->link);

	append_link(&unlicensed_nodes_list, &pun->link, pun);
	pnode->nd_added_to_unlicensed_list = 1;
}

/**
 * @brief
 * 	remove_from_unlicensed_node_list - remove a node from
 * 					   the list of
 * 					   unlicensed nodes.
 *
 * @param[in]	- index	- index of the node
 *
 * @return void
 */
void
remove_from_unlicensed_node_list(struct pbsnode *pnode)
{
	unlicensed_node *pun;
	if(!pnode->nd_added_to_unlicensed_list)
		return;

	pnode->nd_added_to_unlicensed_list = 0;
	pun = (unlicensed_node *) GET_NEXT(unlicensed_nodes_list);
	while (pun != NULL) {
		if (!strcmp(pun->pnode->nd_name, pnode->nd_name)) {
			licensing_control.licenses_total_needed -= pnode->nd_attr[ND_ATR_LicenseInfo].at_val.at_long;
			delete_link(&pun->link);
			free(pun);
			break;
		} else
			pun = (unlicensed_node *) GET_NEXT(pun->link);
	}
}

/**
 * @brief
 *	distribute_licenseinfo - for cray all the inventory is reported by the first vnode.
 *		so it has to be distributed to subsidiary vnodes.
 *		The distribution may not be even but we are trying our best.
 *
 * @param[in]	pointer to mom_svrinfo_t
 * @param[in]	total license count needed to be distributed.
 *
 * @return	void
 *
 * @par MT-Safe:	no
 */
static void
distribute_licenseinfo(mominfo_t *pmom, int lic_count)
{
	int i;
	char str_val[TEMP_BUF_LEN];
	pbsnode *pnode = NULL;
	int numvnds = ((mom_svrinfo_t *) pmom->mi_data)->msr_numvnds;
	int lic_rem = lic_count % (numvnds - 1);

	if (lic_count <= 0)
		return;

	for (i = 1; i < numvnds; i++) {
		pnode = ((mom_svrinfo_t *) pmom->mi_data)->msr_children[i];
		if (lic_rem) {
			snprintf(str_val, sizeof(str_val), "%d", ((lic_count / (numvnds - 1)) + 1));
			set_attr_svr(&(pnode->nd_attr[(int) ND_ATR_LicenseInfo]),
						 &node_attr_def[(int) ND_ATR_LicenseInfo],
						 str_val);
			lic_rem -= 1;
		} else {
			snprintf(str_val, sizeof(str_val), "%d", (lic_count / (numvnds - 1)));
			set_attr_svr(&(pnode->nd_attr[(int) ND_ATR_LicenseInfo]),
						 &node_attr_def[(int) ND_ATR_LicenseInfo],
						 str_val);
		}
	}
}

/**
 * @brief
 *		propagate the ND_ATR_License == ND_LIC_TYPE_locked value to
 *		subsidiary vnodes
 *
 * @param[in]	pointer to mom_svrinfo_t
 *
 * @return	void
 *
 * @par MT-Safe:	no
 * @par Side Effects:
 * 		socket license attribute modifications
 *
 * @par Note:
 *		Normally, a natural vnode's socket licensing state propagates
 *		to the subsidary vnodes.  However, this is not the case when
 *		the natural vnode is representing a Cray login node:  Cray login
 *		and compute nodes are licensed separately;  the socket licensing
 *		state propagates freely among a MoM's compute nodes but not from
 *		a login node to any compute node.
 */
void
propagate_licenses_to_vnodes(mominfo_t *pmom)
{
	struct pbsnode	*ptmp =	/* pointer to natural vnode */
		((mom_svrinfo_t *) pmom->mi_data)->msr_children[0];
	resource_def *prdefvntype;
	resource *prc;		/* vntype resource pointer */
	struct array_strings *as;
	pbsnode *pfrom_Lic; /* source License pointer */
	attribute *pfrom_RA;	/* source ResourceAvail pointer */
	int node_index_start;	/* where we begin looking for socket licenses */
	int i;
	int lic_count;

	/* Any other vnodes? If not, no work to do */
	if (((mom_svrinfo_t *) pmom->mi_data)->msr_numvnds < 2)
		return;

	prdefvntype = &svr_resc_def[RESC_VNTYPE];

	/*
 	 * Determine where to begin looking for socket licensed nodes:  if
 	 * the natural vnode is for a Cray login node, the important nodes 
 	 * are those for Cray compute nodes, which begin after the
 	 * login node (which is always the natural vnode and therefore
 	 * always first);  otherwise, we start looking at the beginning.
 	 */
	pfrom_RA = &ptmp->nd_attr[(int) ND_ATR_ResourceAvail];
	if (((pfrom_RA->at_flags & ATR_VFLAG_SET) != 0) &&
		((prc = find_resc_entry(pfrom_RA, prdefvntype)) != NULL) &&
		((prc->rs_value.at_flags & ATR_VFLAG_SET) != 0)) {
		/*
 		 * Node has a ResourceAvail vntype entry;  see whether it
 		 * contains CRAY_LOGIN.
 		 */
		as = prc->rs_value.at_val.at_arst;
		for (i = 0; i < as->as_usedptr; i++)
			if (strcmp(as->as_string[i], CRAY_LOGIN) == 0) {
				node_index_start = 1;
				break;
			} else
				node_index_start = 0;
	} else
		node_index_start = 0;

	/*
 	 * Make a pass over the subsidiary vnodes to see whether any have socket
 	 * licenses;  if not, no work to do.
 	 */
	for (i = node_index_start, pfrom_Lic = NULL, lic_count = 0;
		i < ((mom_svrinfo_t *) pmom->mi_data)->msr_numvnds; i++) {
		pbsnode *n = ((mom_svrinfo_t *) pmom->mi_data)->msr_children[i];

		if (n->nd_attr[(int) ND_ATR_LicenseInfo].at_flags & ATR_VFLAG_SET)
			lic_count = n->nd_attr[(int) ND_ATR_LicenseInfo].at_val.at_long;

		if ((n->nd_attr[(int) ND_ATR_License].at_flags & ATR_VFLAG_SET) &&
			(n->nd_attr[(int) ND_ATR_License].at_val.at_char == ND_LIC_TYPE_locked)) {
			pfrom_Lic = n;
			break;
		}
	}
	if (node_index_start)
		distribute_licenseinfo(pmom, lic_count);

	if (pfrom_Lic == NULL)
		return;

	/*
 	 * Now make another pass, this time updating the other vnodes'
 	 * ND_ATR_License attribute.
 	 */
	for (i = node_index_start;
		i < ((mom_svrinfo_t *) pmom->mi_data)->msr_numvnds; i++) {
		pbsnode *n = ((mom_svrinfo_t *) pmom->mi_data)->msr_children[i];

		set_attr_svr(&(n->nd_attr[(int) ND_ATR_License]),
					 &node_attr_def[(int)ND_ATR_License],
					 ND_LIC_locked_str);
		snprintf(log_buffer, sizeof(log_buffer),
			"nd_attr[ND_ATR_License] copied from %s to %s",
			pfrom_Lic->nd_name, n->nd_name);
		log_event(PBSEVENT_DEBUG4, PBS_EVENTCLASS_NODE,
			LOG_DEBUG, pmom->mi_host, log_buffer);
	}
}

/**
 * @brief
 * 	clear_node_lic_attrs -	clear a node's ND_ATR_License and maybe
 * 				ND_ATR_LicenseInfo
 *
 * @param[in] - pnode - pointer to the node
 * @param[in] - clear_license_info - if ND_ATR_LicenseInfo should be cleared.
 *
 * @return void
 */
static void
clear_node_lic_attrs(pbsnode *pnode, int clear_license_info)
{
	if (clear_license_info && (pnode->nd_attr[(int) ND_ATR_LicenseInfo].at_flags & ATR_VFLAG_SET))
		clear_attr(&pnode->nd_attr[(int) ND_ATR_LicenseInfo], &node_attr_def[(int) ND_ATR_LicenseInfo]);

	if (pnode->nd_attr[(int) ND_ATR_License].at_flags & ATR_VFLAG_SET)
			clear_attr(&pnode->nd_attr[(int) ND_ATR_License], &node_attr_def[(int) ND_ATR_License]);
	pnode->nd_added_to_unlicensed_list = 0;
}

/**
 * @brief
 * 	set_node_lic_info_attr	- set node's license information
 * 				  namely ND_ATR_License and ND_ATR_LicenseInfo
 *
 * @param - pnode - pointer to the node
 *
 * @return - int
 * @retval - 0	-  Success
 * @retval - < 0 - Failure
 */
static int
set_node_lic_info_attr(pbsnode *pnode)
{
	long count;
	char path[MAXPATHLEN + 1];
	static char topology_dir[] = "topology";

	snprintf(path, sizeof(path), "%s/server_priv/%s/%s", pbs_conf.pbs_home_path,
		topology_dir, pnode->nd_name);

	count = lic_needed_for_node(path, &(pnode->nd_lic_info));
	if (count < 0) {
		switch (count) {
			case -1:
				sprintf(log_buffer,
					"topology file not found for node %s",
					pnode->nd_name);
				break;
			case -2:
				sprintf(log_buffer,
					"Unable to open topology file for node %s",
					pnode->nd_name);
				break;
			case -3:
				sprintf(log_buffer,
					"Error in parsing topology information for node %s",
					pnode->nd_name);
				break;
			case -4:
				sprintf(log_buffer,
					"Licensing library not initialized");
				break;
		}
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
		  	LOG_NOTICE, msg_daemonname, log_buffer);
		return -1;
	} else {
		char str_val[20];

		licensing_control.licenses_total_needed += count;		

		/* Save the number of licenses needed */
		snprintf(str_val, sizeof(str_val), "%ld", count);			
		set_attr_svr(&(pnode->nd_attr[(int) ND_ATR_LicenseInfo]),
			&node_attr_def[(int) ND_ATR_LicenseInfo], str_val);
	}
	return 0;
}

/**
 * @brief
 * 	check_license_expiry - 	checks if licenses are about to expire,
 * 				and if so logs the warning message and
 * 				sends an email to the account defined
 * 				by the 'mail_from' server attribute
 * 				about an expiring license.
 * @return - void
 */
void
check_license_expiry(struct work_task *wt)
{
	char *warn_str = NULL;

	warn_str = lic_check_expiry();
	if (warn_str && (strlen(warn_str) > 0)) {
		struct tm *plt;

		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
			msg_daemonname, warn_str);

		plt = localtime(&time_now);
		if (plt && (plt->tm_yday != licensing_control.expiry_warning_email_yday)) {
			/* Send email at most once a day to prevent
			 * bombarding a recipient's inbox.
			 * NOTE: Sending of email can also be turned off
			 * by unsetting the 'mail_from' server attribute.
			 */
			sprintf(log_buffer, "License server %s: %s",
				pbs_licensing_location, warn_str);
			svr_mailowner(0, 0, 0, log_buffer);
			licensing_control.expiry_warning_email_yday = plt->tm_yday;
		}
	}
	set_task(WORK_Timed, time_now + 86400, check_license_expiry, NULL);
}

/**
 * @brief
 * 	get_licenses	- get count licenses from pbs_license_info
 *
 * @param[in]	- count	- number of licenses
 *
 * @return - int
 * @retval - 0 -   Succces
 * @retval - < 0 - Failure
 */
int
get_licenses(int lic_count)
{
	int status;
	int diff = lic_count - licensing_control.licenses_checked_out;
	/* Try getting the licenses */
	status = lic_get(lic_count);
	if (status < 0) {
		sprintf(log_buffer,
			"%d licenses could not be checked out from pbs_license_info=%s",
			lic_count, pbs_licensing_location);
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
			LOG_NOTICE, msg_daemonname, log_buffer);
		license_counts.licenses_local = 0;
		license_counts.licenses_used = 0;
		licensing_control.licenses_checked_out = 0;
	} else {
		sprintf(log_buffer,
			"%d licenses checked out from pbs_license_info=%s",
			lic_count, pbs_licensing_location);
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
			LOG_NOTICE, msg_daemonname, log_buffer);

		licensing_control.licenses_checked_out = lic_count;
		licensing_control.licenses_checkout_time = time_now;
		license_counts.licenses_local = lic_count - license_counts.licenses_used;
		license_counts.licenses_global -= diff;
	}
	check_license_expiry(NULL);
	return status;
}

/**
 * @brief
 * 	calc_licences_allowed - calculate the number of licenses that can be
 * 				checked out based on pbs_license_min and
 * 				pbs_license_max
 *
 * @return	int
 * @retval	n	: number of licenses we can check out
 *
 * @Note - should be called only after lic_obtainable() has been called.
 */

static long
calc_licenses_allowed()
{
	long count = licensing_control.licenses_total_needed;

	if (licensing_control.licenses_min > count)
		count = licensing_control.licenses_min;

	if (licensing_control.licenses_max < count)
		count = licensing_control.licenses_max;

	if ((license_counts.licenses_global + licensing_control.licenses_checked_out) < count)
		count = license_counts.licenses_global + licensing_control.licenses_checked_out;

	return count;
}

/**
 * @brief
 * 	get_more_licenses - task to get more licenses when we have unlicensed nodes
 *
 * @param[in] - ptask
 *
 * @return void
 */
void
get_more_licenses(struct work_task *ptask)
{
	int status;
	long lic_count;

	get_more_licenses_task = NULL;

	license_counts.licenses_global = lic_obtainable();

	if (license_counts.licenses_global < (licensing_control.licenses_total_needed - licensing_control.licenses_checked_out))
		get_more_licenses_task = set_task(WORK_Timed, time_now + 300, get_more_licenses, NULL);

	if (license_counts.licenses_global > 0) {
		lic_count = calc_licenses_allowed();
		if (lic_count != licensing_control.licenses_checked_out) {
			if ((lic_count < licensing_control.licenses_checked_out) && (lic_count < licensing_control.licenses_total_needed)) {
				int i;
				for (i = 0; i < svr_totnodes; i++)
					clear_node_lic_attrs(pbsndlist[i], 0);
				license_counts.licenses_used = 0;
			}
			status = get_licenses(lic_count);
			if (status == 0)
				license_nodes();
		}
	} else
		license_counts.licenses_global = 0;
}

/**
 * @brief
 * 	license_one_node - try licensing a single node
 *
 * @param[in] pnode - pointer to the node
 *
 * @return void
 */
void
license_one_node(pbsnode *pnode)
{
	if (license_counts.licenses_global > 0 || license_counts.licenses_used > 0) {
		int status = 0;

		if (pnode->nd_lic_info == NULL)
			status = set_node_lic_info_attr(pnode);

		if (status == 0) {
			if (consume_licenses(pnode->nd_attr[(int)ND_ATR_LicenseInfo].at_val.at_long) == 0) {
				set_attr_svr(&(pnode->nd_attr[(int)ND_ATR_License]),
				 	&node_attr_def[(int)ND_ATR_License],
				 	ND_LIC_locked_str);
			} else {
				add_to_unlicensed_node_list(pnode);
				if (get_more_licenses_task)
					delete_task(get_more_licenses_task);
				get_more_licenses_task = set_task(WORK_Timed, time_now + 2, get_more_licenses, NULL);
			}
		}
	} else
		add_to_unlicensed_node_list(pnode);
}

/**
 * @brief	On Cray, we need to release all licenses distributed across
 * 		the vnodes before consuming the bulk count of licenses
 * 		for the first vnode. Distribution will be done at a later stage.
 *
 * @param[in,out]	pnode	- pointer to node structure
 * @param[in]		type	- type of topology info
 *
 * @return	void
 */
void
release_lic_for_cray(struct pbsnode *pnode)
{
	int i;
	attribute *ppnli;
	attribute *ppnl;

	for (i = 0; i < pnode->nd_nummoms; i++) {
		if (((mom_svrinfo_t *) pnode->nd_moms[i]->mi_data)->msr_numvnds > 1) {
			mom_svrinfo_t *mi_data = (mom_svrinfo_t *) pnode->nd_moms[i]->mi_data;
			for (i = 1; i < mi_data->msr_numvnds; i++) {
				pnode = mi_data->msr_children[i];
				ppnli = &pnode->nd_attr[(int) ND_ATR_LicenseInfo];
				ppnl = &pnode->nd_attr[(int) ND_ATR_License];

				if ((ppnl->at_flags & ATR_VFLAG_SET) &&
						(ppnl->at_val.at_char == ND_LIC_TYPE_locked)) {
					clear_attr(&(pnode->nd_attr[(int) ND_ATR_License]),
							&node_attr_def[(int) ND_ATR_License]);
					return_licenses(ppnli->at_val.at_long);
				}
			}
			break;
		}
	}
}

/**
 * @brief - update_license_highuse - record max number of lic used over time
 * 				     This information is logged into the
 * 				     accounting license file.
 */
static void
update_license_highuse(void)
{
	int u;

	u = license_counts.licenses_used;
	if (u > license_counts.licenses_high_use.lu_max_hr)
		license_counts.licenses_high_use.lu_max_hr = u;
	if (u > license_counts.licenses_high_use.lu_max_day)
		license_counts.licenses_high_use.lu_max_day = u;
	if (u > license_counts.licenses_high_use.lu_max_month)
		license_counts.licenses_high_use.lu_max_month = u;
	if (u > license_counts.licenses_high_use.lu_max_forever)
		license_counts.licenses_high_use.lu_max_forever = u;
}

/**
 * @brief
 * 	license_nodes - License the nodes
 *
 * @return void
 */
void
license_nodes()
{
	int i;
	pbsnode *np;
	unlicensed_node *punodes;
	unlicensed_node *pnext;

	punodes = (unlicensed_node *) GET_NEXT(unlicensed_nodes_list);
	while (punodes != NULL) {
		np = punodes->pnode;
		pnext = (unlicensed_node *) GET_NEXT(punodes->link);
		if ((np->nd_attr[(int)ND_ATR_License].at_val.at_char != ND_LIC_TYPE_locked)) {
			if (np->nd_attr[(int)ND_ATR_LicenseInfo].at_flags & ATR_VFLAG_SET) {
				if (consume_licenses(np->nd_attr[(int)ND_ATR_LicenseInfo].at_val.at_long) == 0) {
					set_attr_svr(&(np->nd_attr[(int)ND_ATR_License]),
						 &node_attr_def[(int)ND_ATR_License],
						 ND_LIC_locked_str);
					delete_link(&punodes->link);
					free(punodes);
				}
			} else {
				for (i = 0; i < np->nd_nummoms; i++)
					propagate_licenses_to_vnodes(np->nd_moms[i]);
			}
		}
		punodes = pnext;
	}
	update_license_highuse();
	return;
}

/**
 * @brief
 * 	init_licensing - initialize licensing
 *
 * @param[in] ptask - associcated work task
 *
 * @return: void
 */

void
init_licensing(struct work_task *ptask)
{
	int i;
	int count;
	long lic_count;

	if (init_licensing_task && (init_licensing_task != ptask)) {
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
			LOG_INFO, msg_daemonname,
			"skipping a init licensing task");
		return;
	}

	/*
 	 * We have to calculate the number of licenses again
 	 * as the license location has changed.
 	 */
	memset(&license_counts, 0, sizeof(license_counts));
	licensing_control.licenses_total_needed = 
		licensing_control.licenses_checkout_time = 
			licensing_control.licenses_checked_out = 0;
	licensing_control.expiry_warning_email_yday = -1;

	count = lic_init(pbs_licensing_location);
	if (count < 0) {
		for (i = 0; i < svr_totnodes; i++) {
			clear_node_lic_attrs(pbsndlist[i], 1);
			free(pbsndlist[i]->nd_lic_info);
			pbsndlist[i]->nd_lic_info = NULL;
			add_to_unlicensed_node_list(pbsndlist[i]);
		}

		switch (count) {
			case -1:
				sprintf(log_buffer,
					"pbs_license_info=%s does not point to a license server",
					pbs_licensing_location);
				break;
			case -2:
				sprintf(log_buffer,
					"connection could not be established with pbs_license_info=%s",
					pbs_licensing_location);
				break;
			case -3:
				sprintf(log_buffer,
					"supported licenses type not available at pbs_license_info=%s",
					pbs_licensing_location);
				break;
		}
		log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_SERVER,
			  LOG_NOTICE, msg_daemonname, log_buffer);
		return;
	}

	for (i = 0; i < svr_totnodes; i++) {
		clear_node_lic_attrs(pbsndlist[i], 1);
		free(pbsndlist[i]->nd_lic_info);
		pbsndlist[i]->nd_lic_info = NULL;

		set_node_lic_info_attr(pbsndlist[i]);

		add_to_unlicensed_node_list(pbsndlist[i]);
	}

	/* Determine how many licenses we can check out */
	license_counts.licenses_global = count;
	lic_count = calc_licenses_allowed();

	if (lic_count > 0) {
		int status;
		status = get_licenses(lic_count);

		if (status == 0)
			/* Now let us license the nodes */
			license_nodes();
	}

	return;
}

/**
 * @brief	check the sign is valid for given node
 *
 * @param[in]	sign	hash input
 * @param[out]	pnode	pointer to node structure
 *
 * @return	int
 * @retval	PBSE_NONE	: Hash is valid
 * @retval	PBSE_BADNDATVAL	: Bad attribute value
 * @retval	PBSE_LICENSEINV	: License is invalid
 */
static int
validate_sign(char *sign, struct pbsnode *pnode)
{
	int ret;
	time_t expiry = 0;
	char **cred_list = break_delimited_str(sign, '_');
	attribute *ppnl = &pnode->nd_attr[(int) ND_ATR_License];
	attribute *ppnli = &pnode->nd_attr[(int) ND_ATR_LicenseInfo];
	attribute_def *pnadl = &node_attr_def[(int) ND_ATR_License];
	attribute_def *pnadli = &node_attr_def[(int) ND_ATR_LicenseInfo];

	ret = checkkey(cred_list, pnode->nd_name, &expiry);
	free_string_array(cred_list);
	switch (ret) {
		case -3:
			log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_NODE,
				LOG_NOTICE, pnode->nd_name, "Invalid signature");
			return PBSE_LICENSEINV;
		case -2:
			return PBSE_BADTSPEC;
		case -1:
			return PBSE_BADNDATVAL;
		case 0:
			snprintf(log_buffer, sizeof(log_buffer),
					"Signature is valid till:%ld", expiry);
			log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_NODE,
						LOG_DEBUG, pnode->nd_name, log_buffer);
			if ((ppnl->at_flags & ATR_VFLAG_SET) &&
				(ppnl->at_val.at_char == ND_LIC_TYPE_locked)) {
				return_licenses(ppnli->at_val.at_long);
				clear_attr(ppnl, pnadl);
				clear_attr(ppnli, pnadli);
			}
			set_attr_svr(ppnl, pnadl, ND_LIC_cloud_str);
			break;
		case 1:
			snprintf(log_buffer, sizeof(log_buffer),
			"Signature is valid, but it has expired at:%ld", expiry);
			log_event(PBSEVENT_ADMIN, PBS_EVENTCLASS_NODE,
						LOG_DEBUG, pnode->nd_name, log_buffer);
			return PBSE_NONE;
	}
	return PBSE_NONE;
}

/**
 * @brief	If changing lic_signature, check sign
 *
 * @param[out]	pnode	pointer to node structure
 * @param[in]	new	- new attribute
 *
 * @return	int
 * @retval	PBSE_NONE	: Hash is valid
 * @retval	PBSE_BADNDATVAL	: Bad attribute value
 * @retval	PBSE_LICENSEINV	: License is invalid
 */
int
check_sign(pbsnode *pnode, attribute *new)
{
	resource *presc;
	resource_def *prdef;
	int err = PBSE_NONE;

	prdef = find_resc_def(svr_resc_def, ND_RESC_LicSignature);
	presc = find_resc_entry((attribute *)new, prdef);
	if (presc && (presc->rs_value.at_flags & ATR_VFLAG_MODIFY)) {
		if ((err = validate_sign(presc->rs_value.at_val.at_str, pnode)) != PBSE_NONE)
			return (err);
		presc->rs_value.at_flags &= ~ATR_VFLAG_DEFLT;
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 	initialize license counters
 *
 * @param[in]	counts - pointer to the pbs_license_counts structure
 */
void
reset_license_counters(pbs_license_counts *counts)
{
	long global = lic_obtainable();

	if (global > 0) {
		counts->licenses_global = global;
		counts->licenses_local = global;
	} else {
		counts->licenses_global = 0;
		counts->licenses_local = 0;
	}
	counts->licenses_used = 0;
	counts->licenses_high_use.lu_max_forever = 0;
}

/*
 * @brief - release_node_lic -  return back the licenses to the pool
 * 				when a node is deleted.
 * @param - pobj - pointer to the node
 *
 * @return - int
 * @retval - 1 - if the licenses were returned
 * @retval - 0 - the node was not licensed in the first place.
 */
int
release_node_lic(void *pobj)
{
	if (pobj) {
		struct pbsnode *pnode = pobj;
		attribute *ppnl = &pnode->nd_attr[(int) ND_ATR_License];
		attribute *ppnli = &pnode->nd_attr[(int) ND_ATR_LicenseInfo];

		if (pnode->nd_lic_info)
			free(pnode->nd_lic_info);

		/* release license if node is locked */
		if ((ppnl->at_val.at_char == ND_LIC_TYPE_locked) &&
						(ppnli->at_flags & ATR_VFLAG_SET)) {
			return_licenses(pnode->nd_attr[(int)ND_ATR_LicenseInfo].at_val.at_long);
			licensing_control.licenses_total_needed -= pnode->nd_attr[ND_ATR_LicenseInfo].at_val.at_long;
			clear_attr(ppnl, &node_attr_def[(int) ND_ATR_License]);
			clear_attr(ppnli, &node_attr_def[(int) ND_ATR_LicenseInfo]);
			return 1;
		}
	}
	return 0;
}

/**
 * @brief	clear license on unset action of lic_signature
 *
 * @param[in,out]	pnode	-	pointer to node structure
 * @param[in]		rs_name	-	resource name
 *
 * @return	void
 */
void unset_signature(void *pobj, char *rs_name)
{
	attribute *ppnl;
	struct pbsnode *pnode = pobj;

	if (!pnode || !rs_name)
		return;

	if (!strcmp(rs_name, ND_RESC_LicSignature)) {
		ppnl = &pnode->nd_attr[(int) ND_ATR_License];
		if ((ppnl->at_flags & ATR_VFLAG_SET) && (ppnl->at_val.at_char == ND_LIC_TYPE_cloud))
			clear_attr(ppnl, &node_attr_def[(int) ND_ATR_License]);
	}
}

/**
 * @brief
 *		unlicense_nodes	-	reset the ND_ATR_License value 
 *		of a socket-licensed node. if we don't have enough licenses.
 *
 * @return	void
 *
 * @par MT-Safe:	no
 * @par Side Effects:
 *		None
 */
void
unlicense_nodes(void)
{
	int i;
	pbsnode	*np;
	int first = 1;
	static char msg_node_unlicensed[] = "%s attribute reset on one or more nodes";

	for (i = 0; i < svr_totnodes; i++) {
		np = pbsndlist[i];
		if (np->nd_attr[(int) ND_ATR_License].at_val.at_char == ND_LIC_TYPE_locked) {
			clear_attr(&np->nd_attr[(int) ND_ATR_License],
				&node_attr_def[(int) ND_ATR_License]);
			if (first) {
				first = 0;
				sprintf(log_buffer, msg_node_unlicensed,
					ATTR_NODE_License);
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SERVER,
					LOG_ERR, msg_daemonname, log_buffer);
			}
		}
	}
}

/**
 * @brief - return_lingering_licenses - task to return unused licenses
 * 					back to pbs_license_info
 *
 * @return - void
 */
void
return_lingering_licenses(struct work_task *ptask)
{
	if ((licensing_control.licenses_checked_out > licensing_control.licenses_min) &&
		(license_counts.licenses_local > 0))
		get_licenses(licensing_control.licenses_min);

	licenses_linger_time_task = set_task(WORK_Timed,
		time_now + licensing_control.licenses_linger_time,
		return_lingering_licenses, NULL);
}
