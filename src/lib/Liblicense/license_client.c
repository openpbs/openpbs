/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

/**
 * @file	license_client.c
 * @brief
 *  This file contains stub functions 
 * which are not used in the open source.
 */

#include <pbs_config.h>   /* the master config generated by configure */
#include "pbs_license.h"
#include "pbs_internal.h"
#include <sys/types.h>
#include "pbs_nodes.h"

static unsigned int avail_licenses   = 10000000;

char        *pbs_license_location(void);

/**
 * @brief
 *		pbs_licensing_count	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	10000000
 */
int
pbs_licensing_count(void)
{
	return (avail_licenses);
}

/**
 * @brief
 *		pbs_open_con_licensing	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	zero
 */
int
pbs_open_con_licensing(void)
{
	return (0);
}

/**
 * @brief
 *		pbs_close_con_licensing	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
pbs_close_con_licensing(void)
{
}

/**
 * @brief
 *		pbs_licensing_checkin	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	zero
 */
int
pbs_licensing_checkin(void)
{
	return (0);
}

/**
 * @brief
 *		pbs_license_location	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	NULL
 */
char *
pbs_license_location(void)
{
	return (pbs_licensing_license_location);
}

/**
 * @brief
 *		licstate_down	- It's a placeholder function
 * 		which has intentionally kept empty.
 */
void
licstate_down(void)
{
}

void
init_licensing(char *lic_location)
{
}

int
get_licenses(void *lic_info)
{
	return 0;
}

void
set_node_lic_info(void *lic_info, void *nd_lic_info, int node_count, int nsockets)
{
	return;
}

int
get_lic_needed_for_node(void *ptr)
{
	return 0;
}

char *
get_lic_error()
{
	return "";
}

int
devices_to_node(int num)
{
	return num;
}

void
unset_node_lic_info(void *lic_info, void *nd_lic_info)
{
}

int
license_sanity_check()
{
	return 0;
}

int
checkkey(char **cred_list, char *nd_name, time_t expiry)
{
	return 0;
}

