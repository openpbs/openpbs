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

#ifndef	_FAIRSHARE_H
#define	_FAIRSHARE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.hpp"
/*
 *      add_child - add a ginfo to the resource group tree
 */
void add_child(group_info *ginfo, group_info *parent);

/*
 *      find_group_info - recursive function to find a ginfo in the
 resgroup tree
 */
group_info *find_group_info(const char *name, group_info *root);

/*
 *      find_alloc_ginfo - trys to find a ginfo in the fair share tree.  If it
 *                        can not find the ginfo, then allocate a new one and
 *                        add it to the "unknown" group
 */
group_info *find_alloc_ginfo(char *name, group_info *root);


/*
 *      new_group_info - allocate a new group_info struct and initalize it
 */
#ifdef NAS /* localmod 005 */
group_info * new_group_info(void);
#else
group_info * new_group_info();
#endif /* localmod 005 */

/*
 *
 *	parse_group - parse the resource group file
 *
 *	  fname - name of the file
 *	  root  - root of fairshare tree
 *
 *	return success/failure
 *
 *
 *	FORMAT:   name	cresgrp		grpname		shares
 *
 *	  name    - name of user/grp
 *	  cresgrp - resource group of the children of this group (if group)
 *	  grpname - resource group of this user/group
 *	  shares  - the amount of shares the user/group has in its resgroup
 *
 */
int parse_group(const char *fname, group_info *root);

/*
 *
 *	preload_tree -  load the root node into the fair share tree
 *			the root node is the entire machine.  Also load
 *			the "unknown" group.  This group is for any user that
 *			is not specified in the resource group file.
 *
 *	return new head and root of a fairshare tree
 *
 */
#ifdef NAS /* localmod 005 */
fairshare_head *preload_tree(void);
#else
fairshare_head *preload_tree();
#endif /* localmod 005 */


/*
 *      count_shares - count the shares in the current resource group
 */
int count_shares(group_info *grp);

/*
 *      calc_fair_share_perc - walk the fair share group tree and calculate
 *                             the overall percentage of the machine a user/
 *                             group gets if all usage is equal
 */
int calc_fair_share_perc(group_info *root, int shares);

/*
 *      update_usage_on_run - update a users usage information when a
 *                            job is run
 */
void update_usage_on_run(resource_resv *resresv);

/*
 *      decay_fairshare_tree - decay the usage information kept in the fair
 *                             share tree
 */
void decay_fairshare_tree(group_info *root);

/*
 *      write_usage - write the usage information to the usage file
 *                    This fuction uses a recursive helper function
 */
int write_usage(const char *filename, fairshare_head *fhead);

/*
 *      rec_write_usage - recursive helper function which will write out all
 *                        the group_info structs of the resgroup tree
 */
void rec_write_usage(group_info *root, FILE *fp);

/*
 *      read_usage - read the usage information and load it into the
 *                   resgroup tree.
 */
void read_usage(const char *filename, int flags, fairshare_head *fhead);

/*
 *      read_usage_v1 - read version 1 usage file
 */
int read_usage_v1(FILE *fp, group_info *root);

/*
 *      read_usage_v2 - read version 2 usage file
 */
int read_usage_v2(FILE *fp, int flags, group_info *root);

/*
 *      new_group_path - create a new group_path structure and init it
 */
#ifdef NAS /* localmod 005 */
struct group_path *new_group_path(void);
#else
struct group_path *new_group_path();
#endif /* localmod 005 */

/*
 *      free_group_path_list - free a entire group path list
 */
void free_group_path_list(struct group_path *gp);

/*
 *      create_group_path - create a path from the root to the leaf of the tree
 */
struct group_path *create_group_path(group_info *ginfo);

/*
 *      compare_path - compare two group_path's and see which is more
 *                     deserving to run
 */
int compare_path(struct group_path *gp1, struct group_path *gp2);

/*
 *      over_fs_usage - return true of a entity has used more then their
 *                      fairshare of the machine.  Overusage is defined as
 *                      a user using more then their strict percentage of the
 *                      total usage used (the usage of the root node)
 */
int over_fs_usage(group_info *ginfo);

/*
 *	dup_fairshare_tree
 *
 *	  root - root of the tree
 *	  nparent - the parent of the root in the "new" duplicated tree
 *
 *	return duplicated fairshare tree
 */
group_info *dup_fairshare_tree(group_info *root, group_info *nparent);

/*
 *	free_fairshare_tree - free the entire fairshare tree
 */
void free_fairshare_tree(group_info *root);

/*
 *	free_fairshare_node - free the data associated with
 *			      a single fairshare tree node
 */
void free_fairshare_node(group_info *node);

/*
 *	new_fairshare_head - constructor
 */
#ifdef NAS /* localmod 005 */
fairshare_head *new_fairshare_head(void);
#else
fairshare_head *new_fairshare_head();
#endif /* localmod 005 */

/*
 *	dup_fairshare_head - copy constructor for fairshare_head
 *
 *	  ofhead - fairshare_head to dup
 *
 *	return duplicated fairshare_head
 */
fairshare_head *dup_fairshare_head(fairshare_head *ofead);

/*
 *	free_fairshare_head - destructor for fairshare_head
 */
void free_fairshare_head(fairshare_head *fhead);

/*
 *
 *	add_unknown - add a ginfo to the "unknown" group
 *
 *	  ginfo - ginfo to add
 *	  root  - root of fairshare tre
 *
 *	return nothing
 *
 */
void add_unknown(group_info *ginfo, group_info *root);

/*
 * 	reset_temp_usage - walk the fairshare tree resetting temp_usage = usage
 *
 * 	  head - fairshare node to reset
 *
 * 	return nothing
 */
void reset_temp_usage(group_info *head);

/* reset the tree to 1 usage */
void reset_usage(group_info *node);

/* Calculate the arbitrary usage of the tree */
void calc_usage_factor(fairshare_head *tree);



#ifdef	__cplusplus
}
#endif
#endif	/* _FAIRSHARE_H */
