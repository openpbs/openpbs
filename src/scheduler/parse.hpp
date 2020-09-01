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

#ifndef	_PARSE_H
#define	_PARSE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.hpp"
#include "globals.hpp"

/*
 *	parse_config - parse the config file and set a struct config
 *
 *	FILE FORMAT:
 *	config_name [white space ] : [ white space ] config_value
 */
int parse_config(const char *fname);

/*
 *      init_config - initalize the config struture
 */
#ifdef NAS /* localmod 005 */
int init_config(void);
#else
int init_config();
#endif /* localmod 005 */

/*
 *      scan - Scan through the string looking for a white space delemeted word
 *             or quoted string.
 */
char *scan(char *str, char target);

/*
 * sort compare function for preempt status's
 * sort by decending number of bits in the bitfields (most number of preempt
 * statuses at the top) and then priorities
 */
int preempt_cmp(const void *p1, const void *p2);

/*
 *      preempt_bit_field - take list of preempt names seperated by +'s and
 *                          create a bitfield representing it.  The bitfield
 *                          is created by taking the name in the prempt enum
 *                          and shifting a bit into that position.
 */
int preempt_bit_field(char * plist);

/*
 *      valid_config - perform validity checks on scheduler configuration
 *                     In a warning situation, we will fix it the best we can
 *                     and continue
 *
 *      returns 1: valid config (perfectly valid or with warnings)
 *              0: invalid config
 */
int valid_config(void);

/* Check if string is a valid special case sorting string */
int is_speccase_sort(char *sort_res, int sort_type);

void free_sort_info(enum sort_info_type si_type);

#ifdef	__cplusplus
}
#endif
#endif	/* _PARSE_H */
