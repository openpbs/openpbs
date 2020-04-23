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



#define	LICSTATE_SERVER_UNCONF	0x1	/* no license server configured */
#define	LICSTATE_HAS_SERVER	0x2	/* license server reachable */
#define	LICSTATE_SOCKETS_UNCONF	0x4	/* no socket license file configured */
#define	LICSTATE_HAS_SOCKETS	0x8	/* nonzero number of socket licenses */

enum licensing_backend  prev_lb     = LIC_UNKNOWN;	/* Value of previous licensing backend. */
enum licensing_backend last_valid_attempt = LIC_UNKNOWN;

int         pbs_licensing_checkin(void);
int         pbs_checkout_licensing(int);
char        *pbs_license_location(void);
void        inspect_license_path(void);
int         licstate_is_configured(enum licensing_backend);
int         licstate_is_up(enum licensing_backend);

/**
 * @brief
 *		pbs_licensing_status	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	LICSTATE_HAS_SOCKETS
 */
int
pbs_licensing_status(void)
{
	return (LICSTATE_HAS_SOCKETS);
}

/**
 * @brief
 *		pbs_licensing_count	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	10000000
 */
int
pbs_licensing_count(void)
{
	return (licenses.lb_aval_floating);
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
 *		pbs_checkout_licensing	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	need
 */
int
pbs_checkout_licensing(int need)
{
	return (need);
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
 *		inspect_license_path	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
inspect_license_path(void)
{
}

/**
 * @brief
 *		init_socket_licenses	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
init_socket_licenses(char *license_file)
{
}

/**
 * @brief
 *		sockets_release	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
sockets_release(int nsockets)
{
	return;
}

/**
 * @brief
 *		sockets_consume	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	zero
 */
int
sockets_consume(int nsockets)
{
	return (0);
}

/**
 * @brief
 *		licstate_unconfigured	- It's a placeholder function
 * 		which has intentionally kept empty.
 */
void
licstate_unconfigured(enum licensing_backend lb)
{
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

/**
 * @brief
 *		licstate_is_up	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	LICSTATE_HAS_SOCKETS
 */
int
licstate_is_configured(enum licensing_backend lb)
{
	return (LICSTATE_HAS_SOCKETS);
}

/**
 * @brief
 *		licstate_is_up	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	one
 */
int
licstate_is_up(enum licensing_backend lb)
{
	return (1);
}

/**
 * @brief
 *		license_sanity_check	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	zero
 */
int
license_sanity_check(void)
{
	return (0);
}

/**
 * @brief
 *		license_more_nodes	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
license_more_nodes(void) {
	return;
}

/**
 * @brief
 *		propagate_socket_licensing	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
propagate_socket_licensing(mominfo_t *pmom, int distribute) {
	return;
}

/**
 * @brief
 *		nsockets_from_topology	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	zero
 */
int
nsockets_from_topology(char *topology_str, ntt_t type)
{
	return 0;
}

/**
 * @brief
 *		unlicense_socket_licensed_nodes	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
unlicense_socket_licensed_nodes(void)
{
	return;
}

/**
 * @brief
 *		clear_license_info	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void
clear_license_info(void)
{
	return;
}

/**
 * @brief
 *		release_node_lic	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return zero
 */
int
release_node_lic(void *pobj)
{
	return 0;
}

/**
 * @brief
 *		validate_sign	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return True
 */
int
validate_sign(char *sign, void *pobj)
{
   return 1;
}

/**
 * @brief
 *		check_sign	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return zero
 */
int check_sign(void *pobj, void *new)
{
	return 0;
}

/**
 * @brief
 *		process_topology_info	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void process_topology_info(void *pobj, char *topology_str, ntt_t type)
{
	return;
}

/**
 * @brief
 *		unset_signature	- It's a placeholder function
 * 		which has intentionally kept empty.
 * @return	void
 */
void unset_signature(void *pobj, char * rs_name)
{
	return;
}
