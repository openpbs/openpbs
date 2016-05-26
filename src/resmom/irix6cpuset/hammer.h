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
#ifndef	_HAMMER_H
#define	_HAMMER_H
#ifdef	__cplusplus
extern "C" {
#endif

/* The name of this thread (psargs will be changed to reflect this value. */
#define	HAMMER_NAME		"hammer thread"

/* Number of sid's in the initial session id and exempt uid lists. */
#define HAMMER_SIDLIST_SZ	256
#define HAMMER_EXEMPT_SZ	256

/*
 * Path to the ps-info files in /proc.  Access to these files (as oppposed
 * to the full-blown /proc/<pid> files) is unrestricted and will not block.
 */
#define PROC_PINFO_PATH		"/proc/pinfo"

/* If defined, members of the PBS_EXEMPT_GROUP will be exempt from hammer. */
#define PBS_EXEMPT_GROUP	"loginok"

/* If defined, uids less than this value will be exempt from hammer. */
#define PBS_HAMMER_MINUID	1000	/* Uids of 1000+ will be hammered. */

/* If non-zero, ignore 'guest' and 'nobody' uids. */
#define IGNORE_GUESTS		1

/* Minimum interval (sec) between iterations of sample_loop() collector. */
#define HAMMER_LOOP_INTERVAL	30

/* Function declarations. */
int	hammer_loop(shared_block *, pid_t);
pid_t	start_hammer(int);

/* hammer's pid. */
extern pid_t	hammer_pid;
#ifdef	__cplusplus
}
#endif
#endif /* _HAMMER_H */
