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


/**
 * @file	cmds_common.c
 * @brief
 *	Functions shared by all pbs commands C files
 */

#include <stdlib.h>
#include <pbs_config.h>   /* the master config generated by configure */
#include "attribute.h"

/**
 * @brief
 *	Add an entry to an attribute list. First, create the entry and set
 * 	the fields. If the attribute list is empty, then just point it at the
 * 	new entry. Otherwise, append the new entry to the list.
 *
 *  This function is a wrapper of set_attr function in libpbs. It exits when
 *  a non-zero error code is returned by set_attr.
 *
 * @param[in/out] attrib - pointer to attribute list
 * @param[in]     attrib_name - attribute name
 * @param[in]     attrib_value - attribute value
 *
 * @return	Void
 */
void
set_attr_error_exit(struct attrl **attrib, char *attrib_name, char *attrib_value) {
    if (set_attr(attrib, attrib_name, attrib_value))
        exit(2);
}

/**
 * @brief
 *	wrapper function for set_attr_resc in libpbs. Exits if a non-zero error
 *  code is returned by set_attr_resc.
 *
 * @param[in/out] attrib - pointer to attribute list
 * @param[in]     attrib_name - attribute name
 * @param[in]     attrib_value - attribute value
 *
 * @return      Void
 */
void
set_attr_resc_error_exit(struct attrl **attrib, char *attrib_name, char *attrib_resc, char *attrib_value)
{
    if (set_attr_resc(attrib, attrib_name, attrib_resc, attrib_value))
        exit(2);
}

/*
 * Stub function of actual DIS_tpp_funcs for PBS clients commands
 * which doesn't use TPP
 */
void
DIS_tpp_funcs() { }
