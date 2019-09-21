/* 
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
#ifndef	_PBS_CONFIG_H
#define	_PBS_CONFIG_H 1

/**
 * Scalability:
 * 	To address more than 10K connections, increase FD_SETSIZE
 * 	limit for select() to 16384, before including "winsock2.h".
 */
#ifdef FD_SETSIZE
#undef FD_SETSIZE
#endif
#define FD_SETSIZE 16384

#ifdef _WIN32_WINNT
#undef _WIN32_WINNT
#endif
/*
 * The header file Ws2tcpip.h contains various sections that are version
 * dependent. It uses the macro NTDDI_VERSION which is set based on the
 * value of _WIN32_WINNT. As older versions of Windows become obsolete,
 * this variable should be updated accordingly.
 *
 * 0x0400 = Windows NT 4.0
 * 0x0500 = Windows 2000
 * 0x0501 = Windows XP (EOL April 8, 2014)
 * 0x0502 = Windows Server 2003 (EOL July 14, 2015)
 * 0x0600 = Windows Vista and Windows Server 2008
 * 0x0601 = Windows 7
 * 0x0602 = Windows 8
 * 0x0603 = Windows 8.1
 * 0x0A00 = Windows 10
 */
#define _WIN32_WINNT 0x0600	/* so we get extensions like winsock2.h */

#include <winsock2.h>
#include <Ws2tcpip.h>  /* added for getaddrinfo and getnameinfo */
#include <windows.h>
#include <windowsx.h>
#include <winbase.h>
#include <io.h>
#include <sys/locking.h>
#include <direct.h>
#include <lmcons.h>
#include <process.h>
#include <time.h>
#include <sys/utime.h>
#include <win.h>		/* should be last in case we need to replace */
/* previous declarations */

typedef	unsigned long	u_long;
typedef	unsigned int	u_int;
typedef	unsigned short	u_short;
typedef	unsigned char	u_char;
typedef int		pbs_socklen_t;
typedef int		ssize_t;

#if 0
typedef	int		uid_t;
typedef	int		gid_t;
typedef	int		pid_t;
#endif


/*
 **	Config stuff.
 */
/* PBS specific: Define to the path of the global configuration file */
#define PBS_CONF_FILE "C:\\Program Files\\PBS Pro\\pbs.conf"
#define NGROUPS_MAX		10

/* PBS specific: Define if PBS should use RPP/UDP for resource queries */
#define RPP 1

/* The number of bytes in a double.  */
#define SIZEOF_DOUBLE 8

/* The number of bytes in a float.  */
#define SIZEOF_FLOAT 4

/* The number of bytes in a int.  */
#define SIZEOF_INT 4

/* The number of bytes in a long.  */
#define SIZEOF_LONG 4

/* The number of bytes in a long double.  */
#define SIZEOF_LONG_DOUBLE 12

/* The number of bytes in a short.  */
#define SIZEOF_SHORT 2

/* The number of bytes in a signed char.  */
#define SIZEOF_SIGNED_CHAR 1

/* The number of bytes in a unsigned.  */
#define SIZEOF_UNSIGNED 4

/* The number of bytes in a unsigned char.  */
#define SIZEOF_UNSIGNED_CHAR 1

/* The number of bytes in a unsigned int.  */
#define SIZEOF_UNSIGNED_INT 4

/* The number of bytes in a unsigned long.  */
#define SIZEOF_UNSIGNED_LONG 4

/* The number of bytes in a unsigned short.  */
#define SIZEOF_UNSIGNED_SHORT 2

/* PBS specific: The pathname of the temporary directory for mom */
#define TMP_DIR "C:\\WINNT\\TEMP"

/* Let's define PBS_PASS_CREDENTIALS but make sure openssl AES include and lib  */
/* files are available in \Program Files\Openssl\{include,lib }		*/
#define PBS_PASS_CREDENTIALS

#define HAVE_ATEXIT 1

#define H_ERRNO_DECLARED 1

/* PBS specific: Define to the path of the qstat init file */
#define QSTATRC_PATH "C:\\Program Files\\PBS Pro\\qstatrc"

/* Use Python */
#define	PYTHON	1
#define Py_NO_ENABLE_SHARED 1

/* Default PBS postgres port and user */
#define PBS_DATA_SERVICE_PORT 15007
#define PBS_DATA_SERVICE_USER "pbsdata"

/* on Windows use SELECT calls for tpp */
#define HAVE_SELECT

/* Define QMGR_HAVE_HIST for windows */
#define QMGR_HAVE_HIST 1

/* Define that we have read-write pthread locks */
#define RWLOCK_SUPPORT 1

#define PBS_COMPRESSION_ENABLED 1

#endif /* _PBS_CONFIG_H */
