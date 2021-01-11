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

#ifndef	_LIST_LINK_H
#define	_LIST_LINK_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * list_link.h - header file for general linked list routines
 *		see list_link.c
 *
 *	A user defined linked list can be managed by these routines if
 *	the first element of the user structure is the pbs_list_link struct
 *	defined below.
 */

/* list entry list sub-structure */

typedef struct pbs_list_link {
	struct pbs_list_link *ll_prior;
	struct pbs_list_link *ll_next;
	void		 *ll_struct;
} pbs_list_link;
typedef pbs_list_link pbs_list_head;

/* macros to clear list head or link */

#define CLEAR_HEAD(e) e.ll_next = &e, e.ll_prior = &e, e.ll_struct = NULL
#define CLEAR_LINK(e) e.ll_next = &e, e.ll_prior = &e

#define LINK_INSET_BEFORE 0
#define LINK_INSET_AFTER  1

#if defined(DEBUG) && !defined(NDEBUG)
#define GET_NEXT(pe) get_next((pe), __FILE__, __LINE__)
#define GET_PRIOR(pe) get_prior((pe), __FILE__, __LINE__)
#else
#define GET_NEXT(pe)  (pe).ll_next->ll_struct
#define GET_PRIOR(pe) (pe).ll_prior->ll_struct
#endif

/* function prototypes */

extern void insert_link(pbs_list_link *oldp, pbs_list_link *newp, void *pobj, int pos);
extern void append_link(pbs_list_head *head, pbs_list_link *newp, void *pnewobj);
extern void delete_link(pbs_list_link *oldp);
extern void delete_clear_link(pbs_list_link *oldp);
extern void swap_link   (pbs_list_link *, pbs_list_link *);
extern int  is_linked(pbs_list_link *head, pbs_list_link *oldp);
extern void list_move(pbs_list_head *oldp, pbs_list_head *newp);

#ifndef NDEBUG
extern void *get_next(pbs_list_link, char *file, int line);
extern void *get_prior(pbs_list_link, char *file, int line);
#endif	/* NDEBUG */

#ifdef	__cplusplus
}
#endif
#endif /* _LIST_LINK_H */
