/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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

#ifndef	_PBS_HPCP_CLIENT_H
#define	_PBS_HPCP_CLIENT_H 1

#include "libpbs.h"
#include "linked_list.h"
#include "server_limits.h"
#include "attribute.h"
#include "job.h"
#include "pbs_error.h"
#include "batch_request.h"


#ifdef	__cplusplus
extern 	"C" {
#endif

/*
 * Possible states of job once it is moved to HPCBP Server.
 * These states are different from PBS Server states and once
 * job moves to 'FINISHED' or 'TERMINATE' or 'FAILED' then
 * the HPCBP MOM sends obit to the PBS Server.
 */

#define HPCBP_JOB_STATE_PENDING 	0
#define HPCBP_JOB_STATE_RUNNING 	1
#define HPCBP_JOB_STATE_FINISHED 	2
#define HPCBP_JOB_STATE_TERMINATED 	3
#define HPCBP_JOB_STATE_FAILED 		4
#define HPCBP_JOB_STATE_UNKNOWN 	5

#define HPCBP_NODE_STATUS 		1

/* Possible return values from 'hpcbp_pbs_qdel' */

#define HPCBP_JOB_TERMINATE_SUCCESS 	1
#define HPCBP_JOB_TERMINATE_FAILED  	2
#define HPCBP_JOB_TEMINATE_UNDEFINED 	3
#define HPCBP_JOB_TERMINATE_ERROR  	4

#define MOM_PRIV			"mom_priv"

extern int hpcbp_pbs_qsub(job*, char **, char *, size_t);
extern int hpcbp_pbs_qstat(char *);
extern void hpcbp_remove_temp(char *);
extern int hpcbp_pbs_pbsnodes(int, char *, char *);
extern int hpcbp_fetch_server_certificate(void);
extern void hpcbp_qstat_logmessage(int, int, char *, char *);
extern int hpcbp_pbs_qdel(job *, char *, size_t);
extern int hpcbp_create_endpoint_reference(void);

#ifdef	__cplusplus
}
#endif

#endif	/* _PBS_HPCP_CLIENT_H */

