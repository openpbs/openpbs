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

#include <ctype.h>
#include <string.h>
#include "pbs_entlim.h"

#include <stdio.h>

/**
 * @brief
 * 	strip_trailing_white - strip whitespace from the end of a character string
 *
 * @param[in] pw - input string
 *	The input string is null terminated at the start of any trailing
 *	white space.
 *
 * @return	Void
 */
static void
strip_trailing_white(char *pw)
{
	while (isspace((int) *pw))
		--pw;
	*(pw + 1) = '\0';
	return;
}

/**
 * @brief
 * 	-Parse a string of the form: 	value1 [, value2 ...]
 * 	returning a pointer to each "value" in turn striping out the white space
 *
 * @param[in,out] - start - address of pointer to start of string, it is
 *		updated to the start of the next substring on return;
 *
 * @return char *
 * @retval pointer to first (next) substring
 * @retval NULL if reached the end the string
 */

char *
parse_comma_string_r(char **start)
{
	char *pc;
	char *rv;

	char *back;

	if ((start == NULL) || (*start == NULL))
		return NULL;

	pc = *start;

	if (*pc == '\0')
		return NULL; /* already at end, no strings */

	/* skip over leading white space */

	while ((*pc != '\n') && isspace((int) *pc) && *pc)
		pc++;

	rv = pc; /* the start point which will be returned */

	/* go find comma or end of line */

	while (*pc) {
		if ((*pc == ',') || (*pc == '\n'))
			break;
		++pc;
	}
	back = pc;
	while (isspace((int) *--back)) /* strip trailing spaces */
		*back = '\0';

	if (*pc)
		*pc++ = '\0'; /* if not end, terminate this and adv past */
	*start = pc;

	return (rv);
}

static char pbs_all[] = PBS_ALL_ENTITY;

/**
 * @brief
 * 	-etlim_validate_name - check the entity name for:
 *	1. if type is 'o', then name must be "PBS_ALL",
 *	2. else name must not contain invalid characters
 *
 * @param[in] etype - limits on entity type
 * @param[in] ename - entity name
 *
 * @return	int
 * @retval	0	if name is ok
 * @retval	-1 	if name is invalid
 */
static int
etlim_validate_name(enum lim_keytypes etype, char *ename)
{
	if (etype == LIM_OVERALL) {
		/* do special check on entity for etype 'o' */
		if (strcmp(ename, pbs_all) != 0)
			return (-1);
	} else {
		/* other etypes cannot use "PBS_ALL" */
		if (strcmp(ename, pbs_all) == 0)
			return (-1);

		/* check for invalid characters in entity's name */
		if (strpbrk(ename, ETLIM_INVALIDCHAR) != NULL)
			return (-1);
	}
	return 0;
}

/**
 * @brief
 * 	-etlim_parse_one - parse a single "entity limit" string, for example
 *	"[ u:name=value ]" into its component parts:
 *
 * @param[in] 	etype  - entity type enum
 * @param[in]	etenty - entity type letter : name  - u:job
 * @param[in]	entity - entity name
 * @param[in]	val    - value
 *
 * @return	int
 * @retval	0 	no error; values into etype, entity, val
 * @retval	<0 	the negative of the offset (index) into the string
 *		     	at which point the sytax error occurred.
 *
 *  Warning	the input string will be munged with null characters,
 *		If you need the string intact,  pass in a copy
 */
int
entlim_parse_one(char *str, enum lim_keytypes *etype, char **etenty, char **entity, char **val)
{
	char *pc;
	char *pendname = NULL;

	pc = str;

	/* search for open bracket */
	while (isspace((int) *pc))
		++pc;
	if (*pc != '[')
		return (str - pc - 1); /* negative of offset into string */

	++pc;
	/* skip whitespace till entity type letter */
	while (isspace((int) *pc))
		++pc;
	if (*pc == 'u')
		*etype = LIM_USER;
	else if (*pc == 'g')
		*etype = LIM_GROUP;
	else if (*pc == 'p')
		*etype = LIM_PROJECT;
	else if (*pc == 'o')
		*etype = LIM_OVERALL;
	else
		return (str - pc - 1);
	*etenty = pc;

	/* next must be the colon */
	if (*++pc != ':')
		return (str - pc - 1);
	++pc;

	/* next must be start of entity's name */
	if ((*pc == '\0') || isspace((int) *pc))
		return (str - pc - 1);
	*entity = pc;

	/* Look for the end of the entity name, either the close quote or */
	/* the first white space.   If there is non-white space between   */
	/* the end (shown by "pendname") and the bracket/equal sign; then */
	/* that is an error.						  */
	if ((*pc == '"') || (*pc == '\'')) {
		/* entity name is quoted,  look for matchng quote */
		char match = *pc;
		*entity = ++pc; /* incr past the quote character */

		while (*pc && *pc != match)
			++pc;
		if (*pc == '\0')
			return (str - pc - 1); /* no closing quote */
		/* set to null, ending the name */
		*pc = '\0';
		pendname = pc; /* mark reached end of name (close quote) */
	}

	/* skip to equal sign  or closing bracket */
	++pc;
	while (*pc && (*pc != '=') && (*pc != ']')) {
		if (isspace((int) *pc)) {
			*pc = '\0';
			pendname = pc; /* mark end of name (whitespace) */
		} else if (pendname != NULL) {
			/* non-white space and already saw end of name, error */
			return (str - pc - 1);
		}
		++pc;
	}

	if (*pc == ']') {
		/* case of "[u:name]" without value */
		*pc = '\0';
		/* check name for validity */
		if (etlim_validate_name(*etype, *entity) == -1)
			return (str - ((*entity) + 2) - 1);
		*val = NULL; /* no value */
		return 0;
	} else if (*pc == '\0') {
		/* error; no ']' nor '=' */
		return (str - pc - 1);
	}

	/* hit the '=', value must follow */

	*pc = '\0';
	strip_trailing_white(pc - 1);

	/* check name for validity */
	if (etlim_validate_name(*etype, *entity) == -1)
		return (str - ((*entity) + 2) - 1);

	++pc;
	/* skip white till start of value */
	while (isspace(*pc))
		++pc;
	if (*pc == '\0')
		return (str - pc - 1); /* error, no value after = */
	else if (*pc == '-')
		return (str - pc - 1); /* error, negative value */
	*val = pc;

	/* skip to closing bracket */
	++pc;
	while (*pc && (*pc != ']') && (!isspace(*pc)))
		++pc;
	while (isspace(*pc)) /* skip trailing white */
		++pc;

	if (*pc != ']')
		return (str - pc - 1);
	strip_trailing_white(pc - 1);
	return 0;
}

/**
 * @brief
 * 	-etlim_parse - parse a comma separated set of  "entity limit" strings,
 *	for example:  "[ u:name=value ],[g:name], ..." and for each separate
 *	entity limit substring, call the specified "addfunc" function with
 *		entity name  ("u:name"),
 *		passed-in resource name ("mem" or "ncpus"), and
 *		entity limit value ("10mb" or "4")
 *
 *	The "addfunc" will add the entity entry to the collection controlled
 *	by the contex identified by 'cts".  The "addfunc" function will return
 *	0 for no error or non-zero for an error.
 *
 * @return	int
 * @retval	0	no error
 * @retval	<0 	the negative of the offset (index) into the string
 *		     	at which point the sytax error occurred.
 * @retval	>0	A general PBS error that is not specific to a location
 *		     	in the input string.
 *
 *  Warning	the input string will be munged with null characters,
 *		If you need the string intact,  pass in a copy
 */
int
entlim_parse(char *str, char *resc, void *ctx,
	     int (*addfunc)(void *ctx, enum lim_keytypes kt, char *fulent,
			    char *entity, char *resc, char *value))
{
	enum lim_keytypes etype;
	char *ett;
	char *entity;
	char *ntoken;
	char *val;
	char *pcs;
	int rc;

	ntoken = str;
	while ((pcs = parse_comma_string_r(&ntoken)) != NULL) {
		rc = entlim_parse_one(pcs, &etype, &ett, &entity, &val);
		if (rc < 0)			 /* syntax error, rc is offset in ntoken */
			return (str - pcs) + rc; /* adjust for str */
		if (addfunc) {
			if ((rc = addfunc(ctx, etype, ett, entity, resc, val)) != 0)
				if (rc != 0)
					return rc;
		}
	}
	return 0;
}

#ifdef ENTLIM_STANDALONE_TEST

static int badonly = 0;

/**
 * @brief
 * 	-this is just a dummy "addfunc" that prints what was passed in
 *
 * @return	int
 *
 */
int
dummyadd(void *ctx, enum lim_keytypes kt, char *fent, char *entity, char *resc, char *value)
{
	if (strpbrk(entity, " 	") != NULL)
		fprintf(stderr, "  Note: entity name <%s> contains space\n", entity);
	if (badonly == 1)
		return 0;
	if (value)
		printf("\t--%c--%s--%s--%s\n", *fent, entity, resc, value);
	else
		printf("\t--%c--%s--%s--<null>\n", *fent, entity, resc);
	return 0;
}

main(int argc, char *argv[])
{
	char *cstr;
	char input[256];
	char etl;
	char *etname, *val;
	char *pcs;
	int rc;
	int i;
	int goodonly = 0;

	while ((i = getopt(argc, argv, "bg")) != EOF) {
		switch (i) {
			case 'b':
				badonly = 1;
				break;

			case 'g':
				goodonly = 1;
				break;

			default:
				fprintf(stderr, "Usage: %s [-b]\n", argv[0]);
				fprintf(stderr, "\t b = print only rejected (bad) entries\n");
				fprintf(stderr, "\t g = print only valid entries\n");
				return (1);
		}
	}

	if (isatty(fileno(stdin)) == 1) {
		printf("enter string: ");
		fflush(stdout);
	}
	while (fgets(input, 255, stdin) != NULL) {
		if ((cstr = strdup(input)) == NULL) {
			fprintf(stderr, "Out of Memory!\n");
			return 1;
		}
		printf("  %s\n", cstr);
		rc = entlim_parse(cstr, "mem", NULL, dummyadd);
		if ((rc != 0) && (goodonly == 0)) {
			printf("error: %s\n", input);
			i = 7 - rc;
			while (--i)
				putchar(' ');
			printf("^\n");
		}
		free(cstr);
		bzero(input, 256);
		if (isatty(fileno(stdin)) == 1) {
			printf("enter string: ");
			fflush(stdout);
		}
	}
	return 0;
}
#endif /* ENTITY_STANDALONE_TEST */
