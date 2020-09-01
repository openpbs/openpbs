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
 * @file    pbsfs.cpp
 *
 * @brief
 * 		pbsfs.cpp - contains functions which are related to PBS file share.
 *
 * Functions included are:
 * 	main()
 * 	print_fairshare_entity()
 *
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <libpbs.h>
#include <pbs_ifl.h>
#include "data_types.hpp"
#include "constant.hpp"
#include "config.hpp"
#include "fairshare.hpp"
#include "parse.hpp"
#include "pbs_version.h"
#include "sched_cmds.h"
#include "log.h"
#include "fifo.hpp"

/* prototypes */
static void print_fairshare_entity(group_info *ginfo);
static void print_fairshare(group_info *root, int level);

/* flags */
#define FS_GET 1
#define FS_SET 2
#define FS_PRINT 4
#define FS_PRINT_TREE 8
#define FS_DECAY 16
#define FS_COMP 32
#define FS_TRIM_TREE 64
#define FS_WRITE_FILE 128

/**
 * @brief
 * 		The entry point of pbsfs
 *
 * @return	int
 * @retval	0	: success
 * @retval	1	: something is wrong!
 */
int
main(int argc, char *argv[])
{
	char path_buf[256] = {0};
	char sched_name[PBS_MAXSCHEDNAME + 1] = "default";
	group_info *ginfo;
	group_info *ginfo2;
	int c;
	int flags = FS_PRINT;
	int flag1 = 0;
	double val;
	char *endp;
	char *testp;

	/* the real deal or output version and exit? */
	PRINT_VERSION_AND_EXIT(argc, argv);
	set_msgdaemonname(const_cast<char *>("pbsfs"));

	if (pbs_loadconf(0) <= 0)
		exit(1);

	while ((c = getopt(argc, argv, "sgptdceI:-:")) != -1)
		switch (c) {
			case 'g':
				flags = FS_GET;
				break;
			case 's':
				flags = FS_SET | FS_WRITE_FILE;
				break;
			case 'p':
				flags = FS_PRINT;
				break;
			case 't':
				flags = FS_PRINT_TREE;
				break;
			case 'd':
				flags = FS_DECAY | FS_WRITE_FILE;
				break;
			case 'c':
				flags = FS_COMP;
				break;
			case 'e':
				flags = FS_TRIM_TREE | FS_WRITE_FILE;
				break;
			case 'I':
				snprintf(sched_name, sizeof(sched_name), "%s", optarg);
				break;
			case '-':
				flag1 = 1;
				break;
		}

	if (flag1 == 1) {
		fprintf(stderr, "Usage: pbsfs --version\n");
		exit(1);
	}

	if (validate_running_user(argv[0]) == 0) {
		exit(1);
	}

	if ((flags & (FS_PRINT | FS_PRINT_TREE)) && (argc - optind) != 0) {
		fprintf(stderr, "Usage: pbsfs -[ptdgcs] [-I sched_name]\n");
		exit(1);
	}
	else if ((flags & FS_GET)  && (argc - optind) != 1) {
		fprintf(stderr, "Usage: pbsfs [-I sched_name] -g <fairshare_entity>\n");
		exit(1);
	}
	else if ((flags & FS_SET) && (argc - optind) != 2) {
		fprintf(stderr, "Usage: pbsfs [-I sched_name] -s <fairshare_entity> <usage>\n");
		exit(1);
	}
	else if ((flags & FS_COMP) && (argc - optind) != 2) {
		fprintf(stderr, "Usage: pbsfs [-I sched_name] -c <entity1> <entity2>\n");
		exit(1);
	}

	if (strcmp(sched_name, "default") != 0) {
		int pbs_sd;
		struct batch_status *bs;
		struct batch_status *cur_bs;
		pbs_sd = pbs_connect(NULL);
		if (pbs_sd < 0) {
			fprintf(stderr, "Can't connect to the server\n");
			exit(1);
		}
		bs = pbs_statsched(pbs_sd, NULL, NULL);

		for (cur_bs = bs; cur_bs != NULL; cur_bs = cur_bs->next) {
			if (strcmp(cur_bs->name, sched_name) == 0) {
				struct attrl *cur_attrl;
				for (cur_attrl = cur_bs->attribs; cur_attrl != NULL; cur_attrl = cur_attrl->next) {
					if (strcmp(cur_attrl->name, ATTR_sched_priv) == 0) {
						pbs_strncpy(path_buf, cur_attrl->value, sizeof(path_buf));
						break;
					}
				}
				if (cur_attrl == NULL) {
					fprintf(stderr, "Scheduler %s does not have its sched_priv set\n", sched_name);
					exit(1);
				}
				break;
			}
		}
		if (cur_bs == NULL) {
			fprintf(stderr, "Scheduler %s does not exist\n", sched_name);
			exit(1);
		}
		pbs_disconnect(pbs_sd);

	} else
		snprintf(path_buf, sizeof(path_buf), "%s/sched_priv/", pbs_conf.pbs_home_path);

	if (chdir(path_buf) == -1) {
		perror("Unable to access fairshare data");
		exit(1);
	}
	init_config();
	parse_config(CONFIG_FILE);
	if ((conf.fairshare = preload_tree()) == NULL) {
		fprintf(stderr, "Error in preloading fairshare information\n");
		return 1;
	}
	if (parse_group(RESGROUP_FILE, conf.fairshare->root) == 0)
		return 1;

	if (flags & FS_TRIM_TREE)
		read_usage(USAGE_FILE, FS_TRIM, conf.fairshare);
	else
		read_usage(USAGE_FILE, 0, conf.fairshare);

	calc_fair_share_perc(conf.fairshare->root->child, UNSPECIFIED);
	calc_usage_factor(conf.fairshare);

	if (flags & FS_PRINT_TREE)
		print_fairshare(conf.fairshare->root, 0);
	else if (flags & FS_PRINT  ) {
		printf("Fairshare usage units are in: %s\n", conf.fairshare_res);
		print_fairshare(conf.fairshare->root, -1);
	}
	else if (flags & FS_DECAY)
		decay_fairshare_tree(conf.fairshare->root);
	else if (flags & (FS_GET | FS_SET | FS_COMP)) {
		ginfo = find_group_info(argv[optind], conf.fairshare->root);

		if (ginfo == NULL) {
			fprintf(stderr, "Fairshare Entity %s does not exist.\n", argv[optind]);
			return 1;
		}
		if (flags & FS_COMP) {
			ginfo2 = find_group_info(argv[optind + 1], conf.fairshare->root);

			if (ginfo2 == NULL) {
				fprintf(stderr, "Fairshare Entity %s does not exist.\n", argv[optind + 1]);
				return 1;
			}
			switch (compare_path(ginfo->gpath, ginfo2->gpath)) {
				case -1:
					printf("%s\n", ginfo->name);
					break;

				case 0:
					printf("%s == %s\n", ginfo->name, ginfo2->name);
					break;

				case 1:
					printf("%s\n", ginfo2->name);
			}
		}
		else if (flags & FS_GET)
			print_fairshare_entity(ginfo);
		else {
			testp = argv[optind + 1];
			val = strtod(testp, &endp);

			if (*endp == '\0')
				ginfo->usage = val;
		}
	}

	if (flags & FS_WRITE_FILE) {
		FILE *fp;
		/* make backup of database file */
		remove(USAGE_FILE ".bak");
		if (rename(USAGE_FILE, USAGE_FILE ".bak") < 0)
			perror("Could not backup usage database.");
		write_usage(USAGE_FILE, conf.fairshare);
		if ((fp = fopen(USAGE_TOUCH, "w")) != NULL)
			fclose(fp);
	}

	return 0;
}
/**
 * @brief
 * 		print the group info structure.
 *
 * @param[in]	ginfo	-	group info structure.
 */
static void
print_fairshare_entity(group_info *ginfo)
{
	struct group_path *gp;
	printf(
		"fairshare entity: %s\n"
		"Resgroup		: %d\n"
		"cresgroup		: %d\n"
		"Shares			: %d\n"
		"Percentage		: %f%%\n"
		"fairshare_tree_usage	: %f\n"
		"usage			: %.0lf (%s)\n"
		"usage/perc		: %.0lf\n",
		ginfo->name,
		ginfo->resgroup,
		ginfo->cresgroup,
		ginfo->shares,
		ginfo->tree_percentage * 100,
		ginfo->usage_factor,
		ginfo->usage, conf.fairshare_res,
		ginfo->tree_percentage == 0 ? -1 : ginfo->usage / ginfo->tree_percentage);

	printf("Path from root: \n");
	for (gp = ginfo->gpath; gp != NULL; gp = gp->next) {
		printf("%-10s: %5d %10.0f / %5.3f = %.0f\n",
			gp->ginfo->name, gp->ginfo->cresgroup,
			gp->ginfo->usage, gp->ginfo->tree_percentage,
			gp->ginfo->tree_percentage == 0 ? -1 :
			gp->ginfo->usage / gp->ginfo->tree_percentage);
	}
}

/**
 * @brief
 *		print_fairshare - print out the fair share tree
 *
 * @param[in]	root	-	root of subtree
 * @param[in]	level	-	-1	: print long version
 *				 0	: print brief but hierarchical tree
 *
 * @return nothing
 *
 */
static void
print_fairshare(group_info *root, int level)
{
	if (root == NULL)
		return;

	if (level < 0) {
		printf(
			"%-10s: Grp: %-5d  cgrp: %-5d"
			"Shares: %-6d Usage: %-6.0lf Perc: %6.3f%%\n",
			root->name, root->resgroup, root->cresgroup, root->shares,
			root->usage, (root->tree_percentage * 100));
	}
	else
		printf("%*s%s(%d)\n", level, " ", root->name, root->cresgroup);

	print_fairshare(root->child, level >= 0 ? level + 5 : -1);
	print_fairshare(root->sibling, level);
}
