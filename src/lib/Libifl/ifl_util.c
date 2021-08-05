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

#include <pbs_config.h>

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
PBS_get_server(const char *server_id_in, char *server_name_out, unsigned int *port)
{
	char *pc;
	unsigned int dflt_port = pbs_conf.batch_service_port;
	char *p;

	server_name_out[0] = '\0';

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

