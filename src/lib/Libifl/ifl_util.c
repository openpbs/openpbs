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

#include "pbs_ifl.h"
#include "libpbs.h"

/**
 * @brief
 *	parse out the parts from 'server_name'
 *
 * @param[in] server_id_in - server id input, could be name:port pair
 * @param[out] server_name_out - server name out, does not include port
 * @param[out] port - port number out
 *
 * @return	string
 * @retval	servr name	success
 *
 */
char *
PBS_get_server(char *server_id_in, char *server_name_out, unsigned int *port)
{
	char *pc;
	unsigned int dflt_port = 0;
	char *p;

	server_name_out[0] = '\0';
	if (dflt_port == 0)
		dflt_port = pbs_conf.batch_service_port;

	/* first, get the "net.address[:port]" into 'server_name' */

	if ((server_id_in == NULL) || (*server_id_in == '\0')) {
		if ((p = pbs_default()) == NULL)
			return NULL;
		pbs_strncpy(server_name_out, p, PBS_MAXSERVERNAME);
	} else {
		pbs_strncpy(server_name_out, server_id_in, PBS_MAXSERVERNAME);
	}

	/* now parse out the parts from 'server_name_out' */

	if ((pc = strchr(server_name_out, (int) ':')) != NULL) {
		/* got a port number */
		*pc++ = '\0';
		*port = atoi(pc);
	} else {
		*port = dflt_port;
	}

	return server_name_out;
}

/**
 * @brief
 *	get one of the available connection from multisvr server list
 *
 * @param[in] svr_conns - pointer to array of server connections
 * 
 * @return int
 * @retval -1: error
 * @retval != -1 fd corresponding to the connection
 */
static int
get_available_conn(svr_conn_t **svr_conns)
{
	int i;

	for (i = 0; svr_conns[i]; i++)
		if (svr_conns[i]->state == SVR_CONN_STATE_UP)
			return svr_conns[i]->sd;

	return -1;
}

/**
 * @brief
 *	get random server sd - It will choose a random sd from available no of servers.
 *	If the randomly choosen connection is down, it will choose the first available conn.
 * @param[in] svr_conns - pointer to array of server connections
 * 
 * @return int
 * @retval -1: error
 * @retval != -1: fd corresponding to the connection
 */
int
random_srv_conn(svr_conn_t **svr_conns)
{
	int ind = 0;

	ind =  rand_num() % get_num_servers();

	if (svr_conns[ind] && svr_conns[ind]->state == SVR_CONN_STATE_UP)
		return svr_conns[ind]->sd;
		
	return get_available_conn(svr_conns);
}

/**
 * @brief
 *	Process object id and decide on the server index
 *	based on server part in the object id.

 * @param[in] id - object id
 * 
 * @return int
 * @retval >= 0: start_ind - index where the request should be fired first
 * @retval < 0: could not find appropriate index
 * 
 */
int
starting_index(char *id)
{
	char job_id_out[PBS_MAXCLTJOBID];
	char server_out[PBS_MAXSERVERNAME + 1];
	char server_name[PBS_MAXSERVERNAME + 1];
	uint server_port;
	int i;
	int nsvrs = get_num_servers();

	if ((get_server(id, job_id_out, server_out) == 0)) {
		if (PBS_get_server(server_out, server_name, &server_port)) {
			for (i = 0; i < nsvrs; i++) {
				if (!strcmp(server_name, pbs_conf.psi[i].name) &&
				    (server_port == pbs_conf.psi[i].port)) {
					return i;
				}
			}
		}
	}

	return -1;
}
