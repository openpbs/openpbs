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

#include <pbs_config.h>   /* the master config generated by configure */

#include <sys/types.h>
#include <ctype.h>
#include <memory.h>
#ifndef NDEBUG
#include <stdio.h>
#endif
#include <stdlib.h>
#include <string.h>
#include "pbs_ifl.h"
#include "list_link.h"
#include "attribute.h"
#include "server_limits.h"
#include "job.h"
#include "pbs_error.h"

#define HOLD_ENCODE_SIZE 4

/**
 * @file	attr_fn_hold.c
 * @brief
 * 	This file contains special decode and encode functions for the hold-types
 * 	attribute.  All other functions for this attribute are the standard
 * 	_b (boolean) routines.
 *
 */

/**
 * @brief
 *	decode_hold - decode string into hold attribute
 *
 * @param[in] patr - ptr to attribute to decode
 * @param[in] name - attribute name
 * @param[in] rescn - resource name or null
 * @param[out] val - string holding values for attribute structure
 *
 * @retval      int
 * @retval      0       if ok
 * @retval      >0      error number1 if error,
 * @retval      *patr   members set
 *
 */

int
decode_hold(attribute *patr, char *name, char *rescn, char *val)
{
	char  *pc;

	patr->at_val.at_long = 0;
	if ((val != NULL) && (strlen(val) > (size_t)0)) {
		for (pc = val; *pc != '\0'; pc++) {
			switch (*pc) {
				case 'n':
					patr->at_val.at_long = HOLD_n;
					break;
				case 'u':
					patr->at_val.at_long |= HOLD_u;
					break;
				case 'o':
					patr->at_val.at_long |= HOLD_o;
					break;
				case 's':
					patr->at_val.at_long |= HOLD_s;
					break;
				case 'p':
					patr->at_val.at_long |= HOLD_bad_password;
					break;
				default:
					return (PBSE_BADATVAL);
			}
		}
		patr->at_flags |= ATR_SET_MOD_MCACHE;
	} else
		ATR_UNSET(patr);

	return (0);
}

/**
 * @brief
 * 	encode_str - encode attribute of type ATR_TYPE_STR into attr_extern
 *
 * @param[in] attr - ptr to attribute to encode
 * @param[in] phead - ptr to head of attrlist list
 * @param[in] atname - attribute name
 * @param[in] rsname - resource name or null
 * @param[in] mode - encode mode
 * @param[out] rtnl - ptr to svrattrl
 *
 * @retval      int
 * @retval      >0      if ok, entry created and linked into list
 * @retval      =0      no value to encode, entry not created
 * @retval      -1      if error
 *
 */
/*ARGSUSED*/

int
encode_hold(const attribute *attr, pbs_list_head *phead, char *atname, char *rsname, int mode, svrattrl **rtnl)

{
	int       i;
	svrattrl *pal;

	if (!attr)
		return (-1);
	if (!(attr->at_flags & ATR_VFLAG_SET))
		return (0);

	pal = attrlist_create(atname, rsname, HOLD_ENCODE_SIZE + 1);
	if (pal == NULL)
		return (-1);

	i = 0;
	if (attr->at_val.at_long == 0)
		*(pal->al_value + i++) = 'n';
	else {
		if (attr->at_val.at_long & HOLD_s)
			*(pal->al_value + i++) = 's';
		if (attr->at_val.at_long & HOLD_o)
			*(pal->al_value + i++) = 'o';
		if (attr->at_val.at_long & HOLD_u)
			*(pal->al_value + i++) = 'u';
		if (attr->at_val.at_long & HOLD_bad_password)
			*(pal->al_value + i++) = 'p';
	}
	while (i < HOLD_ENCODE_SIZE+1)
		*(pal->al_value + i++) = '\0';

	pal->al_flags = attr->at_flags;
	if (phead)
		append_link(phead, &pal->al_link, pal);
	if (rtnl)
		*rtnl = pal;

	return (1);
}

/**
 * @brief
 * 	comp_hold - compare two attributes of type hold
 *
 * @param[in] attr - pointer to attribute structure
 * @param[in] with - pointer to attribute structure
 *
 * @return      int
 * @retval      0       if the set of strings in "with" is a subset of "attr"
 * @retval      1       otherwise
 *
 */

int
comp_hold(attribute *attr, attribute *with)
{
	if (!attr || !with)
		return -1;
	if (attr->at_val.at_long == with->at_val.at_long)
		return 0;
	else
		return 1;
}
