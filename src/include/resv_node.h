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

#ifndef _RESV_NODE_H
#define _RESV_NODE_H
#ifdef __cplusplus
extern "C" {
#endif

typedef struct subUniverse subUniverse;
typedef struct spec_and_context spec_and_context;
typedef struct spec_and_context spec_ctx;
typedef struct resc_resv resc_resv;
typedef struct pbsnode pbsnode;
typedef unsigned reservationTag;

/*"specification and solving context"*/

/*pointer to an instantiation of "spec_and_context" is passed to the node
 *solving routine, "node_spec".  It finds, if possible, a set of nodes in the
 *specified subUniverse that satisfies the node specification stored in field
 *"nspec"
 */

struct subUniverse {

	struct pbsnode **univ; /*solve relative to this "universe",
						 which is just an array of pbsnode
						 pointers
						 */
	int usize;	       /*number of entries in "universe" array*/
	int inheap;	       /*set non-zero if univ is in heap and
					 should be freed */
};

struct spec_and_context {
	char *nspec; /*specification of a node set*/

	subUniverse subUniv;

	unsigned int when : 4; /*NEEDNOW or NEEDFUTURE*/
	unsigned int type : 4; /*SPECTYPE_JOB; SPECTYPE_RESV*/

	resc_resv *belong_to;	/*0==no parent else, ptr to parent*/
	reservationTag resvTag; /*if trying to find nodes for a */
	/*reservation or reservation job*/
	/*this is the resv's "handle"   */
	/*currently not being used      */

	long stime; /*job or reservation "start" time*/
	long etime; /*best estimate of "end" time*/
};

extern spec_and_context *create_context(void *, int, char *);
extern void free_context(spec_and_context *);

#ifdef __cplusplus
}
#endif
#endif /*_RESV_NODE_H*/
