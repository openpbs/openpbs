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
 * @file rstester.c
 *
 * @brief
 *		rstester.c - This file contains the functions related to resource testing.
 *
 * Functions included are:
 * 	main()
 * 	read_attrs()
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pbs_ifl.h>
#include "attribute.h"

/* prototypes */
static struct attrl *read_attrs(FILE *fp);
/**
 * @brief
 *      This is main function of rstester.
 *
 * @return	int
 * @retval	0	: success
 * @retval	1	: failure
 *
 */
int
main(int argc, char *argv[])
{
	int c;
	int print_parse = 0;
	int print_resc = 0;
	int print_assn = 0;
	int read_values = 0;
	FILE *fp = NULL;
	rescspec *parse_tree;
	struct batch_status *bs;
	struct attrl *al = NULL;
	int eval_value;
	char logbuf[256];

	while ((c = getopt(argc, argv, "parv:")) != -1)
		switch (c) {
			case 'p':
				print_parse = 1;
				break;
			case 'a':
				print_assn = 1;
				break;
			case 'r':
				print_resc = 1;
				break;
			case 'v':
				read_values = 1;
				fp = fopen(optarg, "r");
				break;

			default:
				fprintf(stderr, "Invalid Option: -%c\n",  c);
		}

	if (argc < optind) {
		fprintf(stderr, "no rescspec!\n");
		return 1;
	}

	if (read_values && (fp == NULL || (al = read_attrs(fp)) == NULL)) {
		fprintf(stderr, "No file to read attribs from!\n");
		return 1;
	}

	/* turn on error output to stdout */
	rescspec_print_errors(1);

	parse_tree = rescspec_parse(argv[optind]);


	if (parse_tree != NULL) {
		if (read_values) {
			logbuf[0] = '\0';
			eval_value = rescspec_evaluate(parse_tree, al, logbuf);
			if (eval_value > 0)
				printf("Evaluate: yes\n");
			else if (eval_value == 0)
				printf("Evaluate: no: %s\n", logbuf);
			else
				printf("Evaluate: Error\n");
		}

		if (print_parse) {
			printf("The Parse Tree:\n");
			print_rescspec_tree(parse_tree, NULL);
		}

		if (print_resc) {
			printf("The Resources: \n");
			bs = rescspec_get_resources(parse_tree);
			if (bs != NULL) {
				print_attrl(bs->attribs);
				/*      pbs_statfree(bs); */
			}
		}

		if (print_assn) {
			printf("The Assignments: \n");
			bs = rescspec_get_assignments(parse_tree);
			if (bs != NULL) {
				print_attrl(bs->attribs);
				/*      pbs_statfree(bs); */
			}
		}
	}
	if (fp != NULL)
		fclose(fp);
	return 0;
}

/**
 * @brief
 *		read_attrs - read attribvalue pairs from file
 *
 * @param[in]	fp	-	the file to read from
 *
 * @return	attrl
 * @retval	list of attrib value pairs	: success
 * @retval	NULL	: failed
 *
 */
static struct attrl *read_attrs(FILE *fp)
{
	char buf[1024];		/* buf to read into */
	struct attrl *head = NULL;	/* head of list */
	struct attrl *cur = NULL;	/* current entry in list */
	struct attrl *prev = NULL;	/* prev entry to add current one to */

	if (fp == NULL)
		return NULL;

	while (fgets(buf, 1024, fp) != NULL) {
		if ((cur = new_attrl()) == NULL)
			return NULL;

		/* chop the \n */
		buf[strlen(buf)-1] = '\0';

		cur->name = ATTR_l;
		cur->resource = strdup(strtok(buf, "= 	"));
		cur->value = strdup(strtok(NULL, "= 	"));

		if (prev != NULL) {
			prev->next = cur;
			prev = cur;
		}
		else {
			prev = cur;
			head = cur;
		}
	}

	return head;
}
