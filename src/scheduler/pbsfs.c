/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */

/**
 * @file    pbsfs.c
 *
 * @brief
 * 		pbsfs.c - contains functions which are related to PBS file share.
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
#include "data_types.h"
#include "constant.h"
#include "fairshare.h"
#include "parse.h"
#include "pbs_version.h"
#include "sched_cmds.h"
#include "log.h"

/* prototypes */
void print_fairshare_entity(group_info *ginfo);

/* flags */
#define FS_GET 1
#define FS_SET 2
#define FS_PRINT 4
#define FS_PRINT_TREE 8
#define FS_DECAY 16
#define FS_ADD 32
#define FS_COMP 64
#define FS_TRIM_TREE 128
#define FS_WRITE_FILE 256

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
	char path_buf[256];
	group_info *ginfo;
	group_info *ginfo2;
	int c;
	int flags = FS_PRINT;
	int flag1 = 0;
	double val;
	char *endp;
	char *testp;

	/*the real deal or output version and exit?*/
	execution_mode(argc, argv);
	set_msgdaemonname("pbsfs");

	if (pbs_loadconf(0) <= 0)
		exit(1);

	while ((c = getopt(argc, argv, "sgptdcae-:")) != -1)
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
			case 'a':
				flags = FS_ADD;
				break;
			case 'c':
				flags = FS_COMP;
				break;
			case 'e':
				flags = FS_TRIM_TREE | FS_WRITE_FILE;
				break;
			case '-':
				flag1 = 1;
				break;
		}

	if (flag1 == 1) {
		fprintf(stderr, "Usage: pbsfs --version\n");
		exit(1);
	}
	if (flags & (FS_PRINT | FS_PRINT_TREE) && (argc - optind) != 0) {
		fprintf(stderr, "Usage: pbsfs -[ptdgcs]\n");
		exit(1);
	}
	else if (flags & FS_GET  && (argc - optind) != 1) {
		fprintf(stderr, "Usage: pbsfs -g <fairshare_entity>\n");
		exit(1);
	}
	else if (flags & FS_SET && (argc - optind) != 2) {
		fprintf(stderr, "Usage: pbsfs -s <fairshare_entity> <usage>\n");
		exit(1);
	}
	else if (flags & FS_COMP && (argc - optind) != 2) {
		fprintf(stderr, "Usage: pbsfs -c <entity1> <entity2>\n");
		exit(1);
	}

	sprintf(path_buf, "%s/sched_priv/", pbs_conf.pbs_home_path);
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

	if (flags & FS_TRIM_TREE) {
		if (!read_usage(USAGE_FILE, FS_TRIM, conf.fairshare))
			return 1;
	}
	else
		if (!read_usage(USAGE_FILE, 0, conf.fairshare))
			return 1;

	calc_fair_share_perc(conf.fairshare->root->child, UNSPECIFIED);

	if (flags & FS_PRINT_TREE)
		print_fairshare(conf.fairshare->root, 0);
	else if (flags & FS_PRINT  ) {
		printf("Fairshare usage units are in: %s\n", conf.fairshare_res);
		print_fairshare(conf.fairshare->root, -1);
	}
	else if (flags & FS_DECAY)
		decay_fairshare_tree(conf.fairshare->root);
	else if (flags & (FS_GET | FS_SET | FS_ADD | FS_COMP)) {
		ginfo = find_group_info(argv[2], conf.fairshare->root);

		if (ginfo == NULL) {
			fprintf(stderr, "Fairshare Entity %s does not exist.\n", argv[2]);
			return 1;
		}
		if (flags & FS_COMP) {
			ginfo2 = find_group_info(argv[3], conf.fairshare->root);

			if (ginfo2 == NULL) {
				fprintf(stderr, "Fairshare Entity %s does not exist.\n", argv[3]);
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
			testp = argv[3];
			val = strtod(testp, &endp);

			if (*endp == '\0') {
				if (flags & FS_SET)
					ginfo->usage = val;
				else
					ginfo->usage += val;
			}
		}
	}

	if (flags & FS_WRITE_FILE) {
		/* make backup of database file */
		remove(USAGE_FILE ".bak");
		if (rename(USAGE_FILE, USAGE_FILE ".bak") < 0)
			perror("Could not backup usage database.");
		write_usage(USAGE_FILE, conf.fairshare);
	}

	return 0;
}
/**
 * @brief
 * 		print the group info structure.
 *
 * @param[in]	ginfo	-	group info structure.
 */
void
print_fairshare_entity(group_info *ginfo)
{
	struct group_path *gp;
	printf(
		"fairshare entity: %s\n"
		"Resgroup        : %d\n"
		"cresgroup       : %d\n"
		"Shares          : %d\n"
		"Percentage      : %f%%\n"
		"usage           : %.0lf (%s)\n"
		"usage/perc      : %.0lf\n",
		ginfo->name,
		ginfo->resgroup,
		ginfo->cresgroup,
		ginfo->shares,
		ginfo->percentage * 100,
		ginfo->usage, conf.fairshare_res,
		ginfo->percentage == 0 ? -1 : ginfo->usage / ginfo->percentage);

	printf("Path from root: \n");
	gp = ginfo->gpath;
	while (gp != NULL) {
		printf("%-10s: %5d %10.0f / %5.3f = %.0f\n",
			gp->ginfo->name, gp->ginfo->cresgroup,
			gp->ginfo->usage, gp->ginfo->percentage,
			gp->ginfo->percentage == 0 ? -1 :
			gp->ginfo->usage / gp->ginfo->percentage);
		gp = gp->next;
	}
}
