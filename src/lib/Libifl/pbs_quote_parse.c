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

/**
 * @file	pbs_quote_parse.c
 */
#include <pbs_config.h>

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pbs_ifl.h"
#include "pbs_internal.h"

/**
 * @brief
 * 	-pbs_quote_parse - parse quoted value string acording to BZ 6088 rules
 *	1.  One of " or ' may be used as quoting character
 *	2.  characters must be printable as defined by "isprint()"
 *	3.  '&' not accepted (reserved for future expansion).
 *	4.  Comma is a token separator characters unless quoted
 *	5.  space is a token separator characters unless quoted or unless
 *		"allow_white" is true
 *
 * @param[in] in - he input string to parse
 * @param[out] out - ptr to where output value string is to be returned
 *		     On non-error return.  This is on the HEAP and freeing is
 *                   upto the caller; if function returns non-zero, "out" is
 *                   not valid and should not be freed
 * @param[in] endptr - ptr into orignal input where we left off processing
 * @param[in] allow_white - indication for whether to allow white space.
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	malloc failure
 * @retval	>0	parse error
 *			The >0 value can be passed to  "pbs_parse_err_msg()"
 *
 */

int
pbs_quote_parse(char *in, char **out, char **endptr, int allow_white)
{
	char *d; /* destination ptr (into "work") */
	size_t len;
	int nthchar;
	char quotechar = '\0'; /* character used for quoting */
	int quoting = 0;       /* true if performing quoting */
	char *s;	       /* working ptr into "in" */
	char *work;	       /* destination buffer for parsed out */

	*out = NULL;
	*endptr = NULL;

	if (in == NULL)
		return -1;
	len = strlen(in) + 1;
	work = calloc((size_t) 1, len); /* calloc used to zero area */
	if (work == NULL)
		return -1;

	d = work;

	s = in;
	while (isspace((int) *s)) /* skip leading white space */
		++s;

	nthchar = 0;
	while (*s != '\0') {

		++nthchar;

		if (!isprint((int) *s) && !isspace((int) *s)) {
			*endptr = s;
			free(work);
			return 2; /* illegal character */

		} else if (quoting) {

			if (*s == quotechar) {
				quoting = 0; /* end of quoting */
					     /* allow quotes inside the quoted string */
			} else if (*s == '&') {
				*endptr = s;
				free(work);
				return 2; /* illegal character */
			} else {
				*d++ = *s;
			}

		} else if (((*s == '"') || (*s == '\'')) &&
			   ((allow_white == 0) || (nthchar == 1))) {

			/* start quoting */
			if ((quotechar != '\0') && (quotechar != *s)) {
				/* cannot switch quoting char in mid stream */
				/* so this is a plain character */
				*d++ = *s;
			} else {
				quotechar = *s;
				quoting = 1;
			}

		} else if ((*s == ',') ||
			   (isspace((int) *s) && (allow_white == 0))) {

			/* hit a special (parsing) character */
			*endptr = s;
			*out = work;
			return 0;

		} else { /* normal un-quoted */

			/* check for special illegal character */
			if (*s == '&') {
				*endptr = s;
				free(work);
				return 2;
			}

			*d++ = *s;
		}

		s++;
	}
	*endptr = s;

	if (quoting) {
		free(work);
		return 4; /* invalid quoting, end of string */
	}

	*out = work;
	return 0;
}

/**
 * @brief
 *	-pbs_parse_err_msges - global list of pbs parse error messages
 *
 * @note
 *	make sure the string length of any message does not
 *	exceed PBS_PARSE_ERR_MSG_LEN_MAX
 */
const char pbs_parse_err_msges[][PBS_PARSE_ERR_MSG_LEN_MAX + 1] = {
	"illegal character",
	"improper quoting syntax",
	"no closing quote"};

/**
 * @brief
 *	-pbs_parse_err_msg() - for a positive, non-zero error returned by
 *	pbs_quote_parse(), return a pointer to an error message string
 *	Accepted error number are 2 and greater,  if not in this range,
 *	the string "error" is returned for the message
 *
 * @param[in] err -error number
 *
 * @return	string
 * @retval	error msg string	success
 * @retval	"error"			error
 *
 */
const char *
pbs_parse_err_msg(int err)
{
	int i;
	i = sizeof(pbs_parse_err_msges) / sizeof(pbs_parse_err_msges[0]);
	if ((err <= 1) || ((err - 1) > i))
		return ("error");
	else
		return (pbs_parse_err_msges[err - 2]);
}

/**
 * @brief
 * 	-pbs_prt_parse_err() -  print an error message associated with an
 *	parsing/syntax error detected by pbs_quote_parse()
 *
 * @par Note:
 *	Writes to stderr;  should not be used directly by a library function
 *	or a daemon, only by user commands.
 *
 * @param[in] txt - error message
 * @param[in] str - option with argument
 * @param[in] offset - diff between txt and str
 * @param[in] err - error number
 *
 * @return	Void
 *
 */
void
pbs_prt_parse_err(char *txt, char *str, int offset, int err)
{
	int i;
	const char *emsg;

	emsg = pbs_parse_err_msg(err);
	fprintf(stderr, "%s %s:\n%s\n", txt, emsg, str);
	for (i = 0; i < offset; ++i)
		putc((int) ' ', stderr);
	putc((int) '^', stderr);
	putc((int) '\n', stderr);
}
