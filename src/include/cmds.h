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



/*
 * cmds.h
 *
 *	Header file for the PBS utilities.
 */

#ifndef	_CMDS_H
#define	_CMDS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <string.h>
#include <time.h>

#include "pbs_error.h"
#include "libpbs.h"
#include "libsec.h"

/* Needed for qdel and pbs_deljoblist */
#define DELJOB_DFLT_NUMIDS 1000

typedef struct svr_jobid_list svr_jobid_list_t;
struct svr_jobid_list {
	int max_sz;
	int total_jobs;
	int svr_fd;
	char svrname[PBS_MAXSERVERNAME + 1];
	char **jobids;
	svr_jobid_list_t *next;
};

#ifndef TRUE
#define TRUE	1
#define FALSE	0
#endif

#define notNULL(x)	(((x)!=NULL) && (strlen(x)>(size_t)0))
#define NULLstr(x)	(((x)==NULL) || (strlen(x)==0))

#define MAX_LINE_LEN 4095
#define LARGE_BUF_LEN 4096
#define MAXSERVERNAME PBS_MAXSERVERNAME+PBS_MAXPORTNUM+2
#define PBS_DEPEND_LEN 2040

/* for calling pbs_parse_quote:  to accept whitespace as data or separators */
#define QMGR_ALLOW_WHITE_IN_VALUE 1
#define QMGR_NO_WHITE_IN_VALUE    0

#define QDEL_MAIL_SUPPRESS 1000

extern int optind, opterr;
extern char *optarg;

extern int	parse_at_item(char *, char *, char *);
extern int	parse_jobid(char *, char **, char **, char **);
extern int	parse_stage_name(char *, char *, char *, char *);
extern void	prt_error(char *, char *, int);
extern int	check_max_job_sequence_id(struct batch_status *);
extern void	set_attr_error_exit(struct attrl **, char *, char *);
extern void	set_attr_resc_error_exit(struct attrl **, char *, char *, char *);

#ifdef	__cplusplus
}
#endif
#endif	/* _CMDS_H */
