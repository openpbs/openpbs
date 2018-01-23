/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */
#ifndef	_LINKED_LIST_H
#define	_LINKED_LIST_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * linked_list.h - header file for general linked list routines
 *		see linked_list.c
 *
 *	A user defined linked list can be managed by these routines if
 *	the first element of the user structure is the pbs_list_node struct
 *	defined below.
 */

/* list entry list sub-structure */

typedef struct pbs_list_node {
	struct pbs_list_node *prev;
	struct pbs_list_node *next;
	void		 *data;
} pbs_list_node;
typedef pbs_list_node pbs_list_node;

/* macros to clear list head or node */

#define CLEAR_HEAD(e) e.next = &e, e.prev = &e, e.data = (void *)0
#define CLEAR_NODE(e) e.next = &e, e.prev = &e

#define NODE_INSET_BEFORE 0
#define NODE_INSET_AFTER  1

#if defined(DEBUG) && !defined(NDEBUG)
#define GET_NEXT(pe) get_next((pe), __FILE__, __LINE__)
#define GET_PREV(pe) get_prev((pe), __FILE__, __LINE__)
#else
#define GET_NEXT(pe)  (pe).next->data
#define GET_PREV(pe) (pe).prev->data
#endif

/* function prototypes */

extern void insert_node(pbs_list_node *old, pbs_list_node *new, void *pobj, int pos);
extern void append_node(pbs_list_node *head, pbs_list_node *new, void *pnewobj);
extern void delete_node(pbs_list_node *old);
extern void swap_node   (pbs_list_node *, pbs_list_node *);
extern int  is_in_list(pbs_list_node *head, pbs_list_node *old);
extern void list_move(pbs_list_node *old, pbs_list_node *new);

#ifndef NDEBUG
extern void *get_next(pbs_list_node, char *file, int line);
extern void *get_prev(pbs_list_node, char *file, int line);
#endif	/* NDEBUG */

#ifdef	__cplusplus
}
#endif
#endif /* _LINKED_LIST_H */
