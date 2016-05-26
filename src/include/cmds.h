/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */


/*
 * cmds.h
 *
 *	Header file for the PBS utilities.
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctype.h>
#include <string.h>
#include <time.h>

#include "pbs_error.h"
#include "libpbs.h"
#include "libsec.h"

#ifndef TRUE
#define TRUE	1
#define FALSE	0
#endif

#define notNULL(x)	(((x)!=NULL) && (strlen(x)>(size_t)0))
#define NULLstr(x)	(((x)==NULL) || (strlen(x)==0))

#ifdef NAS /* localmod 081 */
#define MAX_LINE_LEN 20480
#else
#define MAX_LINE_LEN 4095
#endif /* localmod 081 */
#define MAXSERVERNAME PBS_MAXSERVERNAME+PBS_MAXPORTNUM+2
#define PBS_DEPEND_LEN 2040

/* for calling pbs_parse_quote:  to accept whitespace as data or separators */
#define QMGR_ALLOW_WHITE_IN_VALUE 1
#define QMGR_NO_WHITE_IN_VALUE    0

extern int optind, opterr;
extern char *optarg;

extern int	parse_at_item(char *, char *, char *);
extern int	parse_jobid(char *, char **, char **, char **);
extern int	parse_stage_name(char *, char *, char *, char *);
extern void	prt_error(char *, char *, int);
extern int	cnt2mom(char *server);
extern void     set_attr_resc(struct attrl **, char *, char *, char *);

