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
#ifndef	_COLLECTOR_H
#define	_COLLECTOR_H
#ifdef	__cplusplus
extern "C" {
#endif

/* Name of the collector thread (to set process args list) */
#define COLLECTOR_NAME			"collector thread"

/*
 * exit(2) code for the collector to indicate that a very fatal error has
 * occurred, and a restart is useless.
 */
#define COLLECTOR_BAIL_EXIT		5


/*
 * Sampling can be relatively expensive.  A simple rate-limiter is provided
 * that attempts to run the collector no more than once in any
 * COLLECTOR_LOOP_INTERVAL seconds.
 */
#define	COLLECTOR_LOOP_INTERVAL		90/*seconds*/

/*
 * At boot time, system libraries are pre-loaded into memory.  This prevents
 * some unlucky job being charged for the memory footprint of a library if it
 * is the first to touch it.
 *
 * These files are produced by the libldr code, and contain a list of the
 * device, inode and path of each of the preloaded libraries.  These are
 * parsed by mom, and processes are not charged for the memory used by the
 * segments listed in the indices.
 *
 * Unrecognized DSO's are logged in DSO_UNKNOWN_LOG the first time they are
 * encountered.
 */
#define	DSO32_INDEX_PATH		"/lib32/index"
#define	DSO64_INDEX_PATH		"/lib64/index"
#define DSO_UNKNOWN_LOG			"/PBS/mom_priv/unknown_dso"

/* Initial number of slots allocated to hold session arrays. */
#define	INITIAL_SID_SIZE		128

/*
 * Initial number of slots allocated to hold all segments of a process' memory
 * map as returned by the PIOCMAP_SGI ioctl on /proc/<pid>.
 */
#define	INITIAL_MAP_SIZE		1024

/*
 * Where to find the process pseudo-filesystem.  Operations on the pinfo
 * files are limited, but guaranteed to operate only on in-core data.  The
 * normal procfs code may block indefinitely (which is why this code exists
 * at all).
 */
#define	PROCFS_PATH			"/proc"
#define	PINFO_PATH			"/proc/pinfo"

/* Collector's pid */
extern	pid_t				collector_pid;

#ifdef	__cplusplus
}
#endif
#endif /* _COLLECTOR_H */
