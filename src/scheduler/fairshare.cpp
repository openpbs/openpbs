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
 * @file    fairshare.c
 *
 * @brief
 * 		fairshare.c - This file contains functions related to fareshare scheduling.
 *
 * Functions included are:
 * 	add_child()
 * 	add_unknown()
 * 	find_group_info()
 * 	find_alloc_ginfo()
 * 	new_group_info()
 * 	parse_group()
 * 	preload_tree()
 * 	count_shares()
 * 	calc_fair_share_perc()
 * 	test_perc()
 * 	update_usage_on_run()
 * 	decay_fairshare_tree()
 * 	compare_path()
 * 	print_fairshare()
 * 	write_usage()
 * 	rec_write_usage()
 * 	read_usage()
 * 	read_usage_v1()
 * 	read_usage_v2()
 * 	new_group_path()
 * 	free_group_path_list()
 * 	create_group_path()
 * 	over_fs_usage()
 * 	dup_fairshare_tree()
 * 	free_fairshare_tree()
 * 	free_fairshare_node()
 * 	new_fairshare_head()
 * 	dup_fairshare_head()
 * 	free_fairshare_head()
 * 	reset_temp_usage()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

#include <log.h>

#include "data_types.hpp"
#include "job_info.hpp"
#include "constant.hpp"
#include "fairshare.hpp"
#include "globals.hpp"
#include "misc.hpp"
#include "constant.hpp"
#include "config.hpp"
#include "log.h"
#include "fifo.hpp"
#include "resource_resv.hpp"
#include "resource.hpp"
#ifdef NAS /* localmod 041 */
#include "sort.hpp"
#endif


extern time_t last_decay;

/**
 * @brief
 *		add_child - add a group_info to the resource group tree
 *
 * @param[out]	ginfo	-	ginfo to add to the tree
 * @param[in,out]	parent	-	parent ginfo
 *
 * @return	nothing
 *
 */
void
add_child(group_info *ginfo, group_info *parent)
{
	if (parent != NULL) {
		ginfo->sibling = parent->child;
		parent->child = ginfo;
		ginfo->parent = parent;
		ginfo->resgroup = parent->cresgroup;
		ginfo->gpath = create_group_path(ginfo);
	}
}

/**
 * @brief
 * 		add a ginfo to the "unknown" group
 *
 * @param[in]	ginfo	-	ginfo to add
 * @param[in]	root	-	root of fairshare tree
 *
 * @return	nothing
 *
 */
void
add_unknown(group_info *ginfo, group_info *root)
{
	group_info *unknown;		/* ptr to the "unknown" group */

	unknown = find_group_info("unknown", root);
	add_child(ginfo, unknown);
	calc_fair_share_perc(unknown->child, UNSPECIFIED);
}

/**
 * @brief
 *		find_group_info - recursive function to find a group_info in the
 *			  resgroup tree
 *
 * @param[in]	name	-	name of the ginfo to find
 * @param[in]	root	-	the root of the current sub-tree
 *
 * @return	the found group_info or NULL
 *
 */
group_info *
find_group_info(const char *name, group_info *root)
{
	group_info *ginfo;		/* the found group */
	if (root == NULL || name == NULL || !strcmp(name, root->name))
		return root;

	ginfo = find_group_info(name, root->sibling);
	if (ginfo == NULL)
		ginfo = find_group_info(name, root->child);

	return ginfo;
}

/**
 * @brief
 *		find_alloc_ginfo - tries to find a ginfo in the fair share tree.  If it
 *			  can not find the ginfo, then allocate a new one and
 *			  add it to the "unknown" group
 *
 * @param[in]	name	-	name of the ginfo to find
 * @param[in]	root	-	root of the fairshare tree
 *
 * @return	the found ginfo or the newly allocated ginfo
 *
 */
group_info *
find_alloc_ginfo(char *name, group_info *root)
{
	group_info *ginfo;		/* the found group or allocated group */

	if (name == NULL || root == NULL)
		return NULL;

	ginfo = find_group_info(name, root);

	if (ginfo == NULL) {
		if ((ginfo = new_group_info()) == NULL)
			return NULL;

		ginfo->name = string_dup(name);
		ginfo->shares = 1;
		add_unknown(ginfo, root);
	}
	return ginfo;
}

/**
 * @brief
 *		new_group_info - allocate a new group_info struct and initalize it
 *
 * @return	a ptr to the new group_info
 *
 */
group_info *
new_group_info()
{
	group_info *new_;		/* the new group */

	if ((new_ = static_cast<group_info *>(malloc(sizeof(group_info)))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	new_->name = NULL;
	new_->resgroup = UNSPECIFIED;
	new_->cresgroup = UNSPECIFIED;
	new_->shares = UNSPECIFIED;
	new_->tree_percentage = 0.0;
	new_->group_percentage = 0.0;
	new_->usage = FAIRSHARE_MIN_USAGE;
	new_->temp_usage = FAIRSHARE_MIN_USAGE;
	new_->usage_factor = 0.0;
	new_->gpath = NULL;
	new_->parent = NULL;
	new_->sibling = NULL;
	new_->child = NULL;

	return new_;
}

/**
 * @brief
 * 		parse the resource group file
 *
 * @param[in]	fname	-	name of the file
 * @param[in]	root	-	root of fairshare tree
 *
 * @return	success/failure
 *
 *
 * @par FORMAT:   name	cresgrp		grpname		shares
 *	  name    - name of user/grp
 *	  cresgrp - resource group of the children of this group (if group)
 *	  grpname - resource group of this user/group
 *	  shares  - the amount of shares the user/group has in its resgroup
 *
 */
int
parse_group(const char *fname, group_info *root)
{
	group_info *ginfo;		/* ptr to parent group */
	group_info *new_ginfo;	/* used to add each new group */
	char buf[256];		/* used to read each line from the file */
	char *nametok;		/* strtok: name of new group */
	char *grouptok;		/* strtok: parent group name */
	char *cgrouptok;		/* strtok: resgrp of the children of newgrp */
	char *sharestok;		/* strtok: the amount of shares for newgrp */
	FILE *fp;			/* file pointer to the resource group file */
	char error = 0;		/* boolean: is there an error ? */
	int shares;			/* number of shares for the new group */
	int cgroup;			/* resource group of the children of the grp */
	char *endp;			/* used for strtol() */
	int linenum = 0;		/* current line number in the file */

	if ((fp = fopen(fname, "r")) == NULL) {
		snprintf(log_buffer, sizeof(log_buffer), "Error opening file %s", fname);
		log_err(errno, __func__, log_buffer);
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", "Warning: resource group file error, fair share will not work");
		return 0;
	}

	while (fgets(buf, 256, fp) != NULL) {
		if (buf[strlen(buf)-1] == '\n')
			buf[strlen(buf)-1] = '\0';
		linenum++;
		if (!skip_line(buf)) {
			nametok = strtok(buf, " \t");
			cgrouptok = strtok(NULL, " \t");
			grouptok = strtok(NULL, " \t");
			sharestok= strtok(NULL, " \t");

			if (nametok == NULL || cgrouptok == NULL ||
				grouptok == NULL || sharestok == NULL) {
				error = 1;
			}
			else if (find_group_info(nametok, root) != NULL) {
				error = 1;
				sprintf(log_buffer, "entity %s is not unique", nametok);
				fprintf(stderr, "%s\n", log_buffer);
				log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE,
					"fairshare", log_buffer);
			}
			else {
				if (!strcmp(grouptok, "root"))
					ginfo = find_group_info(FAIRSHARE_ROOT_NAME, root);
				else
					ginfo = find_group_info(grouptok, root);

				if (ginfo != NULL) {
					shares = strtol(sharestok, &endp, 10);
					if (*endp == '\0') {
						cgroup = strtol(cgrouptok, &endp, 10);
						if (*endp == '\0') {
							if ((new_ginfo = new_group_info()) == NULL)
								return 0;
							new_ginfo->name = string_dup(nametok);
							new_ginfo->resgroup = ginfo->cresgroup;
							new_ginfo->cresgroup = cgroup;
							new_ginfo->shares = shares;
							add_child(new_ginfo, ginfo);
						}
						else
							error = 1;
					}
					else
						error = 1;
				}
				else  {
					error = 1;
					sprintf(log_buffer, "Parent ginfo of %s doesnt exist.", nametok);
					fprintf(stderr, "%s\n", log_buffer);
					log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE,
						"fairshare", log_buffer);
				}
			}

			if (error) {
				sprintf(log_buffer, "resgroup: error on line %d.", linenum);
				fprintf(stderr, "%s\n", log_buffer);
				log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_NOTICE,
					"fairshare", log_buffer);
			}

			error = 0;
		}
	}
	fclose(fp);
	return 1;
}

/**
 * @brief
 * 		load the root node into the fair share tree
 *		the root node is the entire machine.  Also load
 *		the "unknown" group.  This group is for any user that
 *		is not specified in the resource group file.
 *
 * @return	new head and root of a fairshare tree
 *
 */
fairshare_head *
preload_tree()
{
	fairshare_head *head;
	group_info *root;
	group_info *unknown;		/* pointer to the "unknown" group */

	if ((head = new_fairshare_head()) == NULL)
		return 0;

	if ((root = new_group_info()) == NULL) {
		free_fairshare_head(head);
		return 0;
	}

	head->root = root;

	if ((root->name = string_dup(FAIRSHARE_ROOT_NAME)) == NULL) {
		free_fairshare_head(head);
		return NULL;
	}

	root->resgroup = -1;
	root->cresgroup = 0;
	root->tree_percentage = 1.0;

	if ((unknown = new_group_info()) == NULL) {
		free_fairshare_head(head);
		return NULL;
	}
	if ((unknown->name = string_dup(UNKNOWN_GROUP_NAME)) == NULL) {
		free_fairshare_node(unknown);
		free_fairshare_head(head);
		return NULL;
	}
	unknown->shares = conf.unknown_shares;
	unknown->resgroup = 0;
	unknown->cresgroup = 1;
	unknown->parent = root;
	add_child(unknown, root);
	return head;
}

/**
 * @brief
 *		count_shares - count the shares in a resource group
 *		       a resource group is a group_info and all of its
 *		       siblings
 *
 * @param[in]	grp	-	The start of a sibling chain
 *
 * @return	the number of shares
 *
 */
int
count_shares(group_info *grp)
{
	int shares = 0;		/* accumulator to count the shares */
	group_info *cur_grp;		/* the current group in a sibling chain */

	cur_grp = grp;

	while (cur_grp != NULL) {
		shares += cur_grp->shares;
		cur_grp = cur_grp->sibling;
	}

	return shares;
}

/**
 * @brief
 *		calc_fair_share_perc - walk the fair share group tree and calculate
 *			       the overall percentage of the machine a user/
 *			       group gets if all usage is equal
 *
 * @param[in,out]	root	-	the root of the current subtree
 * @param[in]	shares	-	the number of total shares in the group
 *
 * @return	success/failure
 *
 */
int
calc_fair_share_perc(group_info *root, int shares)
{
	int cur_shares;		/* total number of shares in the resgrp */

	if (root == NULL)
		return 0;

	if (shares == UNSPECIFIED)
		cur_shares = count_shares(root);
	else
		cur_shares = shares;

	if (cur_shares * root->parent->tree_percentage == 0) {
		root->group_percentage = 0;
		root->tree_percentage = 0;
	}
	else {
		root->group_percentage = (float) root->shares / cur_shares;
		root->tree_percentage = root->group_percentage  * root->parent->tree_percentage;
	}

	calc_fair_share_perc(root->sibling, cur_shares);
	calc_fair_share_perc(root->child, UNSPECIFIED);
	return 1;
}

/**
 * @brief
 * 		Update the usage of a fairshare entity for a job.  The process
 *         of updating an entity's usage causes the full usage of the job
 *	       to be accrued to the entity and all groups on the path from the
 *	       entity to the root of the fairshare tree.
 *
 * @param[in]	resresv	-	the job to accrue usage
 *
 * @return nothing
 *
 */
void
update_usage_on_run(resource_resv *resresv)
{
	usage_t u;
	struct group_path *gpath;

	if (resresv == NULL)
		return;

	if (!resresv->is_job || resresv->job == NULL)
		return;

	u = formula_evaluate(conf.fairshare_res, resresv, resresv->resreq);
	if (resresv->job->ginfo !=NULL) {
		gpath = resresv->job->ginfo->gpath;
		while (gpath != NULL) {
			gpath->ginfo->temp_usage += u;
			gpath = gpath->next;
		}
	}
	else
		log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_INFO, resresv->name,
			"Job doesn't have a group_info ptr set, usage not updated.");
}

/**
 * @brief
 *		decay_fairshare_tree - decay the usage information kept in the fair
 *			       share tree
 *
 * @param[in,out]	root	-	the root of the fairshare tree
 *
 * @return nothing
 *
 */
void
decay_fairshare_tree(group_info *root)
{
	if (root == NULL)
		return;

	decay_fairshare_tree(root->sibling);
	decay_fairshare_tree(root->child);

	root->usage *= conf.fairshare_decay_factor;
	if (root->usage < FAIRSHARE_MIN_USAGE)
		root->usage = FAIRSHARE_MIN_USAGE;
}

/**
 * @brief
 *		compare_path - compare two group_path's and see which is more
 *		       deserving to run
 * @par
 *		comparison: usage / priority
 *
 * @param[in]	gp1	-	group path 1
 * @param[in]	gp2	-	group path 2
 *
 * @return	int
 * @retval	-1	: gp1 is more deserving
 * @retval	0	: both are equal
 * @retval	1	: gp2 is more deserving
 *
 */
int
compare_path(struct group_path *gp1, struct group_path *gp2)
{
	struct group_path *cur1, *cur2;
	double curval1, curval2;
	int rc = 0;

	if (gp1 == NULL && gp2 == NULL)
		return 0;

	if (gp1 != NULL && gp2 == NULL)
		return -1;

	if (gp1 == NULL && gp2 != NULL)
		return 1;


	cur1 = gp1;
	cur2 = gp2;

	while (cur1 != NULL && cur2 != NULL && rc == 0  ) {
		if (cur1 != cur2) {
			if (cur1->ginfo->tree_percentage <= 0 && cur2->ginfo->tree_percentage> 0)
				return 1;
			if (cur1->ginfo->tree_percentage > 0 && cur2->ginfo->tree_percentage<= 0)
				return -1;
			if (cur1->ginfo->tree_percentage <= 0 && cur2->ginfo->tree_percentage<= 0)
				return 0;

			curval1 = cur1->ginfo->temp_usage / cur1->ginfo->tree_percentage;
			curval2 = cur2->ginfo->temp_usage / cur2->ginfo->tree_percentage;

			if (curval1 < curval2)
				rc = -1;
			else if (curval2 < curval1)
				rc = 1;
		}

		cur1 = cur1->next;
		cur2 = cur2->next;
	}

	return rc;
}

/**
 * @brief
 *		write_usage - write the usage information to the usage file
 *		      This function uses a recursive helper function
 *
 * @param[in]	filename	-	usage file
 * @param[in]	fhead	-	Pointer to fairshare_head structure.
 *
 * @return	success/failure
 *
 */
int
write_usage(const char *filename, fairshare_head *fhead)
{
	FILE *fp;		/* file pointer to usage file */
	struct group_node_header head;

	if (fhead == NULL)
		return 0;

	if (filename == NULL)
		filename = USAGE_FILE;

	if ((fp = fopen(filename, "wb")) == NULL) {
		sprintf(log_buffer, "Error opening file %s", filename);
		log_err(errno, "write_usage", log_buffer);
		return 0;
	}

	/* version 2:
	 * header
	 * last_decay
	 * group_node_usage_v2
	 * group_node_usage_v2
	 * ...
	 */

	pbs_strncpy(head.tag, USAGE_MAGIC, sizeof(head.tag));
	head.version = USAGE_VERSION;
	fwrite(&head, sizeof(struct group_node_header), 1, fp);
	fwrite(&fhead->last_decay, sizeof(time_t), 1, fp);

	rec_write_usage(fhead->root, fp);
	fclose(fp);
	return 1;
}

/**
 * @brief
 *		rec_write_usage - recursive helper function which will write out all
 *			  the group_info structs of the resgroup tree
 *
 * @param[in]	root	-	the root of the current subtree
 * @param[in]	fp	-	the file to write the ginfo out to
 *
 * @return nothing
 *
 */
void
rec_write_usage(group_info *root, FILE *fp)
{
	struct group_node_usage_v2 grp;	/* used to write out usage info */

	if (root == NULL)
		return;

	/* only write out leaves of the tree (fairshare entities)
	 * usage defaults to 1 so don't bother writing those out either
	 * It is possible that the unknown group is empty.  Don't want to write it out
	 */
#ifdef NAS /* localmod 043 */
	if (root->child == NULL) {
#else
	if (root->usage != 1 && root->child == NULL && strcmp(root->name, UNKNOWN_GROUP_NAME) != 0) {
#endif /* localmod 043 */
		snprintf(grp.name, sizeof(grp.name), "%s", root->name);
		grp.usage = root->usage;

		fwrite(&grp, sizeof(struct group_node_usage_v2), 1, fp);
	}

	rec_write_usage(root->sibling, fp);
	rec_write_usage(root->child, fp);
}

/**
 * @brief
 *		read_usage - read the usage information and load it into the
 *		     resgroup tree.
 *
 * @param[in]	filename	-	The file which stores the usage information.
 * @param[in]	flags	-	flags to check whether to trim or not.
 * @param[in]	fhead	-	pointer to fairshare_head struct.
 *
 * @return void
 *
 */
void
read_usage(const char *filename, int flags, fairshare_head *fhead)
{
	FILE *fp;				/* file pointer to usage file */
	struct group_node_header head;		/* usage file header */
	time_t last;				/* read the last sync from the file */
	int error = 0;				/* error reading in usage header */

	if (fhead == NULL || fhead->root == NULL)
		return;

	if (filename == NULL)
		filename = USAGE_FILE;

	if ((fp = fopen(filename, "r")) == NULL) {
		log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_WARNING, "fairshare usage",
			  "Creating usage database for fairshare");
		fprintf(stderr, "Creating usage database for fairshare.\n");
		return;
	}

	/* read header */
	if (fread(&head, sizeof(struct group_node_header), 1, fp) != 0) {
		if (!strcmp(head.tag, USAGE_MAGIC)) { /* this is a header */
			if (head.version == 2) {
				if (fread(&last, sizeof(time_t), 1, fp) != 0) {
					/* 946713600 = 1/1/2000 00:00 - before usage version 2 existed */
					if (last == 0 || last > 946713600)
						fhead->last_decay = last;
					else
						error = 1;
				}
				if (!error)
					read_usage_v2(fp, flags, fhead->root);
			}
			else
				error = 1;

			if (error)
				log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_WARNING,
					  "fairshare usage", "Invalid usage file header");

		}
		else	 { /* original headerless usage file */
			rewind(fp);
			read_usage_v1(fp, fhead->root);
		}
	}

	fclose(fp);
}

/**
 * @brief
 * 		read version 1 usage file
 *
 * @param[in]	fp	-	the file pointer to the open file
 * @param[in]	root	-	root of the fairshare tree
 *
 * @return	int
 *	@retval	1	: success
 *	@retval	0	: failure
 *
 */
int
read_usage_v1(FILE *fp, group_info *root)
{
	struct group_node_usage_v1 grp;
	group_info *ginfo;
	struct group_path *gpath;

	if (fp == NULL)
		return 0;

	while (fread(&grp, sizeof(struct group_node_usage_v1), 1, fp)) {
		if (grp.usage >= 0 && is_valid_pbs_name(grp.name, USAGE_NAME_MAX)) {
			ginfo = find_alloc_ginfo(grp.name, root);
			if (ginfo != NULL) {
				ginfo->usage = grp.usage;
				ginfo->temp_usage = grp.usage;
				if (ginfo->child == NULL) {
					gpath = ginfo->gpath;
					/* add usage down the path from the root to our parent */
					while (gpath->next != NULL) {
						gpath->ginfo->usage += grp.usage;
						gpath->ginfo->temp_usage += grp.usage;
						gpath = gpath->next;
					}
				}
			}
		}
		else
			log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_WARNING,
				  "fairshare usage", "Invalid entity");
	}

	return 1;
}

/**
 * @brief
 * 		read version 2 usage file
 *
 * @param[in]	fp	- the file pointer to the open file
 * @param[in]	flags	- flags to check whether to trim or not.
 * @param[in]	root	- root of the fairshare tree
 *
 *	@retval 1 success
 *	@retval 0 failure
 *
 */
int
read_usage_v2(FILE *fp, int flags, group_info *root)
{
	struct group_node_usage_v2 grp;
	group_info *ginfo;
	struct group_path *gpath;

	if (fp == NULL)
		return 0;

	while (fread(&grp, sizeof(struct group_node_usage_v2), 1, fp)) {
		if (grp.usage >= 0 && is_valid_pbs_name(grp.name, USAGE_NAME_MAX)) {
			/* if we're trimming the tree, don't add any new nodes which are not
			 * already in the resource_group file
			 */
			if (flags & FS_TRIM)
				ginfo = find_group_info(grp.name, root);
			else
				ginfo = find_alloc_ginfo(grp.name, root);

			if (ginfo != NULL) {
				ginfo->usage = grp.usage;
				ginfo->temp_usage = grp.usage;
				if (ginfo->child == NULL) {
					gpath = ginfo->gpath;
					/* add usage down the path from the root to our parent */
					while (gpath->next != NULL) {
						gpath->ginfo->usage += grp.usage;
						gpath->ginfo->temp_usage += grp.usage;
						gpath = gpath->next;
					}
				}
			}
		}
		else
			log_event(PBSEVENT_SCHED, PBS_EVENTCLASS_FILE, LOG_WARNING,
				  "fairshare usage", "Invalid entity");
	}

	return 1;
}

/**
 * @brief
 *		new_group_path - create a new group_path structure and init it
 *
 * @return	the new group_pathj
 */
struct group_path *new_group_path()
{
	struct group_path *new_;

	if ((new_ = static_cast<group_path *>(malloc(sizeof(struct group_path)))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	new_->ginfo = NULL;
	new_->next = NULL;

	return new_;
}

/**
 * @brief
 *		free_group_path_list - free a entire group path list
 *
 * @param[in]	gp	-	the head of the group path list
 *
 * @return nothing
 */
void
free_group_path_list(struct group_path *gp)
{
	struct group_path *next;
	struct group_path *cur;

	if (gp == NULL)
		return;

	cur = gp;

	while (cur != NULL) {
		next = cur->next;
		free(cur);
		cur = next;
	}
}

/**
 * @brief
 *		create_group_path - create a path from the root to the leaf of the tree
 *
 * @param[in]	ginfo - the group_root to create the path from
 *
 * @return path
 *
 */
struct group_path *create_group_path(group_info *ginfo)
{
	struct group_path *ret;	/* what is returned from recursive call */
	struct group_path *cur;	/* used to find the end of the path */

	if (ginfo == NULL)
		return NULL;

	ret = create_group_path(ginfo->parent);

	if (ret != NULL) {
		cur = ret;

		while (cur->next != NULL)
			cur = cur->next;

		cur->next = new_group_path();
		cur->next->ginfo = ginfo;
	}
	else {
		ret = new_group_path();
		ret->ginfo = ginfo;
	}

	return ret;
}

/**
 * @brief
 *		over_fs_usage - return true of a entity has used more then their
 *			fairshare of the machine.  Overusage is defined as
 *			a user using more then their strict percentage of the
 *			total usage used (the usage of the root node)
 *
 * @param[in]	ginfo	-	the entity to check
 *
 * @return	true/false
 * @retval	-	true	: if the user is over their usage
 * @retval	-	false	: if under
 *
 */
int
over_fs_usage(group_info *ginfo)
{
	return ginfo->gpath->ginfo->usage * ginfo->tree_percentage < ginfo->usage;
}

/**
 * @brief
 * 		copy constructor for the fairshare tree
 *
 * @param[in]	root	-	root of the tree
 * @param[in] nparent	-	the parent of the root in the new dup'd tree
 *
 * @return	duplicated fairshare tree
 */
group_info *
dup_fairshare_tree(group_info *root, group_info *nparent)
{
	group_info *nroot;
	if (root == NULL)
		return NULL;

	nroot = new_group_info();

	if (nroot == NULL)
		return NULL;


	nroot->resgroup = root->resgroup;
	nroot->cresgroup = root->cresgroup;
	nroot->shares = root->shares;
	nroot->tree_percentage = root->tree_percentage;
	nroot->group_percentage = root->group_percentage;
	nroot->usage = root->usage;
	nroot->usage_factor = root->usage_factor;
	nroot->temp_usage = root->temp_usage;
	nroot->name = string_dup(root->name);

	if (nroot->name == NULL) {
		free_fairshare_node(nroot);
		return NULL;
	}

	add_child(nroot, nparent);


	nroot->sibling = dup_fairshare_tree(root->sibling, nparent);
	nroot->child = dup_fairshare_tree(root->child, nroot);

	return nroot;
}

/**
 *	@brief
 *		free the entire fairshare tree
 *
 * @param[in]	root	-	root of the tree
 */
void
free_fairshare_tree(group_info *root)
{
	if (root == NULL)
		return;

	free_fairshare_tree(root->sibling);
	free_fairshare_tree(root->child);
	free_fairshare_node(root);
}

/**
 * @brief
 *		free the data associated with a single fairshare tree node
 *
 * @param[in,out]	root	-	single fairshare tree node
 */
void
free_fairshare_node(group_info *node)
{
	if (node == NULL)
		return;

	free(node->name);
	free_group_path_list(node->gpath);
	free(node);
}

/**
 * @brief
 * 		constructor for fairshare head
 */
fairshare_head *
new_fairshare_head()
{
	fairshare_head *fhead;

	if ((fhead = static_cast<fairshare_head *>(malloc(sizeof(fairshare_head)))) == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	fhead->root = NULL;
	fhead->last_decay = 0;

	return fhead;
}

/**
 * @brief
 *		copy constructor for fairshare_head
 *
 * @param[in]	ofhead	-	fairshare_head to dup
 *
 * @return	duplicated fairshare_head
 * @retval	NULL	: fail
 */
fairshare_head *
dup_fairshare_head(fairshare_head *ofhead)
{
	fairshare_head *nfhead;

	if (ofhead == NULL)
		return NULL;

	nfhead = new_fairshare_head();

	if (nfhead == NULL)
		return NULL;

	nfhead->last_decay = ofhead->last_decay;
	nfhead->root = dup_fairshare_tree(ofhead->root, NULL);
	if (nfhead->root == NULL) {
		free_fairshare_head(nfhead);
		return NULL;
	}

	return nfhead;
}

/**
 * @brief
 * 		destructor for fairshare_head
 *
 * @param[in]	fhead	-	fairshare_head to be freed.
 */
void
free_fairshare_head(fairshare_head *fhead)
{
	if (fhead == NULL)
		return;

	free_fairshare_tree(fhead->root);

	free(fhead);
}

/**
 * @brief
 * 		recursively walk the fairshare tree resetting temp_usage = usage
 *
 * @param[in]	head	-	fairshare node to reset
 *
 * @return	void
 */
void
reset_temp_usage(group_info *head)
{
	if (head == NULL)
		return;

	head->temp_usage = head->usage;
	reset_temp_usage(head->sibling);
	reset_temp_usage(head->child);
}

/**
 * @brief
 *		recursive helper function to calc_usage_factor()
 * @param root	- parent fairshare tree node
 * @param ginfo	- child fairshare tree node
 *
 * @return void
 */
static void
calc_usage_factor_rec(group_info *root, group_info *ginfo)
{
	float usage;

	if (root == NULL || ginfo == NULL)
		return;

	usage = ginfo->usage / root->usage;
	ginfo->usage_factor = usage + ((ginfo->parent->usage_factor - usage) * ginfo->group_percentage);

	calc_usage_factor_rec(root, ginfo->sibling);
	calc_usage_factor_rec(root, ginfo->child);
}

/**
 * @brief
 *		calculate usage_factor numbers for entire tree.
 *		The usage_factor is a number that takes the node's usage
 *		plus part of its parent's usage_factor into account.  This
 *		will give a number that is comparable across the tree.
 *
 * @param[in] tree - fairshare tree
 *
 * @return void
 */
void
calc_usage_factor(fairshare_head *tree)
{
	group_info *ginfo;
	group_info *root;

	if (tree == NULL)
		return;

	root = tree->root;
	/* Root's children use their real usage as their arbitrary usage */
	for (ginfo = root->child; ginfo != NULL; ginfo = ginfo->sibling) {
		ginfo->usage_factor = ginfo->usage / root->usage;
		calc_usage_factor_rec(root, ginfo->child);
	}

}

/**
 * @brief reset the usage of the fairshare tree so the usage can be reread.
 *	If the usage is not reset first, any entity that is no longer in the
 *	fairshare usage file will retain their original usage.
 * @param node - the fairshare node
 */
void reset_usage(group_info *node) {
	if(node == NULL)
		return;
	reset_usage(node->sibling);
	reset_usage(node->child);
	node->usage = 1;
	node->temp_usage = 1;
}
