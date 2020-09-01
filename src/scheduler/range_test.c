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

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "data_types.hpp"
#include "range.h"

/* to make references happy */
char *msg_daemonname = "range_test";

#define HELPSTR "Commands:\n" \
"print          - print current range\n" \
"z              - enter new range\n" \
"dup            - dup the current range and print the copy\n" \
"next           - print next value in range\n" \
"add N          - add N to current range\n" \
"remove N       - remove N from current range\n" \
"contain N      - does the current range contain N\n" \
"intersection r - find intersection between current range and r\n" \
"quit           - leave program\n" \
"help           - print this help\n"


/* Prototypes */
void print_range_list(range *r);
range *get_range();
int get_num();
int handle_command(range *r, char *cmd, char *arg);


/*
 * commands: (only need to type non-ambigous portion)
 *
 * print      - print current range
 * znew       - enter new range
 * dup        - dup the current range and print the copy
 * next       - print next value in range
 * add N      - add N to current range
 * remove N   - remove N from current range
 * contain N  - does the current range contain N
 * quit       - leave program
 * help       - print list of commands
 */
/**
 * @brief
 * 		entry point to range_test.c
 *
 * @return	int
 * @retval	1	: success, do nothing
 * @retval	0	: success, get new range
 * @retval	-1	: error
 */
int
main(int argc, char *argv[])
{
	range *r = NULL;
	char buf[1024];
	char cmd[512];
	char arg[512];
	int len;
	int ret;

	if (argc >= 3) {
		r = range_parse(argv[1]);

		if (r != NULL) {
			if (argc == 3)
				handle_command(r, argv[2], NULL);
			else
				handle_command(r, argv[2], argv[3]);

			print_range_list(r);

			return 0;
		}
		else {
			fprintf(stderr, "Bad range\n");
			return 1;
		}
	}

	do {
		if (r == NULL)
			r = get_range();

		if (r == NULL)
			return 1;

		printf("> ");

		if (fgets(buf, 1024, stdin) != NULL) {
			len = strlen(buf);
			buf[len-1] = '\0';
			len--;
			if (strncmp("quit", buf, len) == 0)
				return 0;

			if (sscanf(buf, "%s %s", cmd, arg) == 2)
				ret = handle_command(r, cmd, arg);
			else
				ret = handle_command(r, cmd, NULL);

			if (ret == 0) {
				free_range_list(r);
				r = NULL;
			}
		}
	} while (1);

	return ret;
}

/**
 * @brief
 * 		get_range - read a string from the command line and parse it into
 *		    a range and return that.  If a string doesn't correctly
 *		    parse, keep asking until one correctly parses
 *
 * @return	range
 *
 */
range *
get_range()
{
	range *r = NULL;
	char buf[1024];

	do {
		printf("Range: ");
		if (fgets(buf, 1024, stdin) != NULL) {
			buf[strlen(buf)-1] = '\0';
			r = range_parse(buf);
		}
	} while (r == NULL);

	return r;
}

/**
 * @brief
 *		get_num - get a number and return it as an integer
 *
 * @return	number
 *
 */
int
get_num()
{
	char buf[1024];
	int num;
	char *endp;
	int cont = 1;

	do {
		printf("Enter Number: ");
		if (fgets(buf, 1024, stdin) != NULL) {
			num = strtol(buf, &endp, 10);
			if (*endp == '\n')
				cont = 0;
			else
				printf("%s is not a number\n", buf);
		}
	} while (cont);

	return num;
}

/**
 * @brief
 *		print_range_list - print range list
 *
 * @param[in]	r	-	the range to print
 *
 * @return	nothing
 *
 */
void
print_range_list(range *r)
{
	if (r == NULL) {
		printf("NULL range\n");
		return;
	}

	while (r != NULL) {
		printf("s: %-5d e: %-5d st: %-5d ct: %-5d\n", r->start,
			r->end,
			r->step,
			r->count);
		r = r->next;
	}
}

/**
 * @brief
 *		handle_command - handle a range test command
 *
 * @param[in]	r	-	range to test
 * @param[in]	cmd -	the command to handle
 * @param[in]	arg -	an argument to the command
 *
 * @return	int
 * @retval	1	: success, do nothing
 * @retval	0	: success, get new range
 * @retval	-1 	: error
 *
 */
int
handle_command(range *r, char *cmd, char *arg)
{
	int num_arg = 0;
	int num;
	char *endp;
	int ret = 1;
	range *r2, *r3;
	int len;

	if (cmd == NULL)
		return -1;

	if (arg != NULL) {
		num_arg = strtol(arg, &endp, 10);
		if (*endp != '\0')
			return -1;
	}

	len = strlen(cmd);

	if (strncmp("print", cmd, len) == 0)
		print_range_list(r);
	else if (strncmp("znew", cmd, len) == 0) {
		ret = 0;
	}
	else if (strncmp("dup", cmd, len) == 0) {
		r2 = dup_range_list(r);
		print_range_list(r2);
		free_range_list(r2);
	}
	else if (strncmp("next", cmd, len) == 0) {
		if (arg == NULL)
			num_arg = -1;
		num = range_next_value(r, num_arg);
		printf("next: %d\n", num);
	}
	else if (strncmp("add", cmd, len) == 0) {
		if (range_add_value(r, num_arg, ENABLE_SUBRANGE_STEPPING) == 0)
			printf("Could not add value\n");
	}
	else if (strncmp("remove", cmd, len) == 0) {
		if (range_remove_value(&r, num_arg) == 0)
			printf("Could not remove value\n");
	}
	else if (strncmp("contains", cmd, len) == 0) {
		if (range_contains(r, num_arg))
			printf("Range contains %d\n", num_arg);
		else
			printf("Range does not contain %d\n", num_arg);
	}
	else if (strncmp("help", cmd, len) == 0)
		printf("%s", HELPSTR);
	else if (strncmp("intersection", cmd, len) == 0) {
		r2 = get_range();
		printf("Intersection Between r1:\n");
		print_range_list(r);
		printf("and r2:\n");
		print_range_list(r2);
		r3 = range_intersection(r2, r);
		printf("Intersection:\n");
		print_range_list(r3);

		free_range_list(r2);
		free_range_list(r3);
	}
	else {
		printf("Unknown command\n");
		ret = -1;
	}

	return ret;
}
