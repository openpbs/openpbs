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

#include "pbs_ifl.h"
#include "libpbs.h"
#include "pbs_error.h"
#include "dis.h"
#include "pbs_share.h"

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
 *      In case svr_conns is NULL it just returns fd
 * @param[in] fd - virtual fd or the actual fd
 * @param[in] svr_conns - pointer to array of server connections
 *
 * @return int
 * @retval -1: error
 * @retval != -1: fd corresponding to the connection
 */
int
random_srv_conn(int fd, svr_conn_t **svr_conns)
{
	int ind = 0;

	/* It is actual fd and hence return fd itself */
	if (svr_conns == NULL)
		return fd;

	ind =  rand_num() % get_num_servers();

	if (svr_conns[ind] && svr_conns[ind]->state == SVR_CONN_STATE_UP)
		return svr_conns[ind]->sd;

	return get_available_conn(svr_conns);
}

/**
 * @brief	Get the server instance index from the job/resv id, which will act as a hint
 * 		as to which server the job/reservation might possibly be located.
 * 		This function also works even if PBS_SERVER name is not part of obj_id.
 * 		For example, obj_id can be "123.stblr3" or "123", "R123.stblr4" or "R123" where
 * 		stblr3/stblr4 are PBS_SERVER names.

 * @param[in] obj_id - job or resv object id
 * @param[in] obj_type - job or resv object
 *
 * @return int
 * @retval >= 0: start_ind - index where the request should be fired first
 * @retval < 0: could not find appropriate index
 */
int
get_obj_location_hint(char *obj_id, int obj_type)
{
	char *ptr = NULL;
	char *ptr_idx = NULL;
	int svridx = -1;
	char *endptr = NULL;
	int id_len = 0;

	if (IS_EMPTY(obj_id) || !msvr_mode() || (obj_type != MGR_OBJ_JOB && obj_type != MGR_OBJ_RESV))
		return -1;

	ptr = strchr(obj_id, '.');

	if (ptr) /* obj_id contains PBS_SERVER name */
		*ptr = '\0';

	id_len = strlen(obj_id);

	if ((obj_type == MGR_OBJ_RESV && (id_len - 1) <= MSVR_JID_NCHARS_SVR) || id_len <= MSVR_JID_NCHARS_SVR)
		return -1;

	ptr_idx = &obj_id[id_len - MSVR_JID_NCHARS_SVR];

	svridx = strtol(ptr_idx, &endptr, 10);

	if (*endptr != '\0' || svridx >= get_num_servers())
		svridx = -1;

	if (ptr)
		*ptr = '.';

	return svridx;
}

/**
 * @brief
 *	Finds server instance id associated with the given job and returns its fd
 *
 * @param[in]   c - socket on which connected
 * @param[in]   job_id - job identifier
 *
 * @return int
 * @retval SUCCESS returns fd of the server instance associated with the job_id
 * @retval ERROR -1
 */
int
get_job_svr_inst_id(int c, char *job_id)
{
	struct attrl *attr;
	struct batch_status *ss = NULL;
	char *svr_inst_id = NULL;
	static struct attrl attribs[] = {
		{	NULL,
			ATTR_server_inst_id,
			NULL,
			"",
			SET
		}	
	};

	if (job_id == NULL)
		return -1;

	/* Do a job stat to find out the server_instance_fd of
	 * the server instance where the job resides
	 */
	ss = pbs_statjob(c, job_id, attribs, NULL);
	if (ss == NULL)
		return -1;

	if (ss != NULL) {
		for (attr = ss->attribs; attr != NULL; attr = attr->next) {
			if (strcmp(attr->name, ATTR_server_inst_id) == 0) { 
				svr_inst_id = strdup(attr->value);
				if (svr_inst_id == NULL) {
					pbs_statfree(ss);
					return -1;
				}
				break;
			}
		}
	}   

	c = get_svr_inst_fd(c, svr_inst_id);
	free(svr_inst_id);
	pbs_statfree(ss);

	return c;
	
}
