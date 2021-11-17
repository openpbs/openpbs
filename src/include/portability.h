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

#ifndef _PORTABILITY_H
#define _PORTABILITY_H

#define closesocket(X) close(X)
#define initsocketlib() 0
#define SOCK_ERRNO errno

#define NULL_DEVICE "/dev/null"

#undef DLLEXPORT
#define DLLEXPORT

#define dlerror_reset() dlerror()
#define SHAREDLIB_EXT "so"
#define fix_path(char, int)
#define get_uncpath(char)
#define critical_section()

#ifdef PBS_MOM
#define TRAILING_CHAR '/'
#define verify_dir(dir_val, isdir, sticky, disallow, fullpath) tmp_file_sec(dir_val, isdir, sticky, disallow, fullpath)
#define FULLPATH 1
#define process_string(str, tok, len) wtokcpy(str, tok, len)

/* Check and skip if there are any special trailing character */
#define skip_trailing_spcl_char(line, char_to_skip) \
	{                                           \
	}

/* Check whether character is special allowed character */
#define check_spl_ch(check_char) 1
#endif

#endif
