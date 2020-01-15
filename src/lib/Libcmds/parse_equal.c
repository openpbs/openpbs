/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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

#include <pbs_config.h>   /* the master config generated by configure */
#include "cmds.h"

/**
 * @file	parse_equal.c
 */
/**
 * @brief
 * 	parse_equal_string - parse a string of the form:
 *		name1 = value1[, value2 ...][, name2 = value3 [, value4 ...]]
 *	into <name1> <value1[, value2 ...>
 *	     <name2> <value3 [, value4 ...>
 *
 *	On the first call,
 *		*name will point to "name1"
 *		*value will point to "value1 ..." upto but not
 *			including the comma before "name2".
 *	On a second call, with start = NULL,
 *		*name will point to "name2"
 *		*value will point t0 "value3 ..."
 *
 * @param[in]	start	the start of the string to parse
 * @param[in]	name    set to point to the name string
 * @param[in]  	value	set to point to the value string
 *
 *      start is the start of the string to parse.  If called again with
 *      start  being a null pointer, it will resume parsing where it stoped
 *      on the prior call.

 * @return	int
 * @retval	1 	if  name and value are found
 * @retval	0 	if nothing (more) is parsed (null input)
 * @retval	-1 	if a syntax error was detected.
 *
 */

int
parse_equal_string(start, name, value)
char  *start;
char **name;
char **value;
{
	static char *pc;	/* where prior call left off */
	char        *backup;
	int	     quoting = 0;

	if (start != NULL)
		pc = start;

	if (*pc == '\0') {
		*name = NULL;
		return (0);	/* already at end, return no strings */
	}

	/* strip leading spaces */

	while (isspace((int)*pc) && *pc)
		pc++;

	if (*pc == '\0') {
		*name = NULL;	/* null name */
		return (0);
	} else if ((*pc == '=') || (*pc == ','))
		return (-1);	/* no name, return error */

	*name = pc;

	/* have found start of name, look for end of it */

	while (!isspace((int)*pc) && (*pc != '=') && *pc)
		pc++;

	/* now look for =, while stripping blanks between end of name and = */

	while (isspace((int)*pc) && *pc)
		*pc++ = '\0';
	if (*pc != '=')
		return (-1);	/* should have found a = as first non blank */
	*pc++ = '\0';

	/* that follows is the value string, skip leading white space */

	while (isspace((int)*pc) && *pc)
		pc++;

	/* is the value string to be quoted ? */

	if ((*pc == '"') || (*pc == '\''))
		quoting = (int)*pc++;
	*value = pc;

	/*
	 * now go to first equal sign, or if quoted, the first equal sign
	 * after the close quote
	 */

	if (quoting) {
		while ((*pc != (char)quoting) && *pc)	/* look for matching */
			pc++;
		if (*pc)
			*pc = ' ';	/* change close quote to space */
		else
			return (-1);
	}
	while ((*pc != '=') && *pc)
		pc++;

	if (*pc == '\0') {
		while (isspace((int)*--pc));
		if (*pc == ',')	/* trailing comma is a no no */
			return (-1);
		pc++;
		return (1);	/* no equal, just end of line, stop here */
	}

	/* back up to the first comma found prior to the equal sign */

	while (*--pc != ',')
		if (pc <= *value)	/* gone back too far, no comma, error */
			return (-1);
	backup = pc++;
	*backup = '\0';			/* null the comma */

	/* strip off any trailing white space */

	while (isspace((int)*--backup))
		*backup = '\0';
	return (1);
}
