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

#ifndef	_SIMULATE_H
#define	_SIMULATE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.hpp"
#include "constant.hpp"

/*
 *	simulate_events - simulate the future of a PBS universe
 */
unsigned int
simulate_events(status *policy, server_info *sinfo,
	enum schd_simulate_cmd cmd, void *arg, time_t *sim_time);

/*
 *	is_timed - check if a resresv is a timed event
 * 			 (i.e. has a start and end time)
 */
int is_timed(event_ptr_t *resresv);

/*
 *      get_next_event - get the next_event from an event list
 *
 *        \param elist - the event list
 *
 *      \return the current event from the event list
 */
timed_event *get_next_event(event_list *elist);

/*
 * find the initial event based on a timed_event
 *
 *	event            - the current event
 *	ignore_disabled  - ignore disabled events
 *	search_type_mask - bitmask of types of events to search
 *
 *	returns the initial event of the correct type/disabled or not
 *
 *	NOTE: IGNORE_DISABLED_EVENTS exists to be passed in as the
 *		   ignore_disabled parameter.  It is non-zero.
 *
 *	NOTE: ALL_MASK can be passed in for search_type_mask to search
 *		   for all events types
 */
timed_event *find_init_timed_event(timed_event *event, int ignore_disabled, unsigned int search_type_mask);
/*
 *
 *	find_next_timed_event - find the next event based on a timed_event
 *
 *	event            - the current event
 *	ignore_disabled  - ignore disabled events
 *	search_type_mask - bitmask of types of events to search
 *
 *	return the next timed event of the correct type and disabled or not
 */
timed_event *find_next_timed_event(timed_event *event, int ignore_disabled, unsigned int search_type_mask);

/*
 *
 *	find the previous event based on a timed_event
 *
 *	  event            - the current event
 *	  ignore_disabled  - ignore disabled events
 *	  search_type_mask - bitmask of types of events to search
 *
 *	return the previous timed event of the correct type and disabled or not
 */
timed_event *find_prev_timed_event(timed_event *event, int ignore_disabled, unsigned int search_type_mask);

/*
 *      set_timed_event_disabled - set the timed_event disabled bit
 *
 *        te       - timed event to set
 *        disabled - used to set the disabled bit
 *
 *      return nothing
 */
void set_timed_event_disabled(timed_event *te, int disabled);

/*
 *
 *	find_timed_event - find a timed_event
 *			   we need to search by name and type because there
 *			   can be multiple events with the same name and
 *			   different types
 *
 *	  te_list - timed_event list to search in
 *	  ignore_disabled - ignore disabled events
 *	  name    - name of timed_event to search for
 *	  event_type - event_type or TIMED_LOW to ignore
 *	  event_time - time or 0 to ignore
 *
 *	return found timed_event or NULL
 *
 */
timed_event *
find_timed_event(timed_event *te_list, int ignore_disabled, const char *name,
	enum timed_event_types event_type, time_t event_time);




/*
 *      next_event - move an event_list to the next event and return it
 *
 *        \param elist - the event list
 *
 *      \return the next event or NULL if there are no more events
 */
timed_event *next_event(server_info *sinfo, int dont_move);

/*
 *      perform_event - takes a timed_event and performs any actions
 *                      required by the event to be completed.  Currently
 *                      only handles run and end events.
 *
 *        \param event - the event to peform
 *
 *      \return succss 1 /failure 0
 */
int perform_event(status *policy, timed_event *event);

/*
 *      create_event_list - create an event_list from running jobs and
 *                              confirmed reservations
 *
 *        \param sinfo - server universe to act upon
 *
 *      \return event_list
 */
event_list *create_event_list(server_info *sinfo);

/*
 *	exists_run_event - returns 1 if there exists a timed run event in
 *				the event list between the current event
 *				and the last event, or the end time if it is
 *				set
 *
 *	  calendar - event list
 *	  end_time - optional end time (0 means search all events)
 *
 *	returns 1: there exists a run event
 *		0: there doesn't exist a run event
 */
int exists_run_event(event_list *calendar, time_t end_time);

/* Checks to see if there is a run event on a node before the end time */
int exists_run_event_on_node(node_info *ninf, time_t end);

/* Checks if a reservation run event exists between now and 'end' */
int exists_resv_event(event_list *calendar, time_t end);


/*
 *      create_events - creates an timed_event list from running jobs
 *                          and confirmed reservations
 *
 *        \param sinfo - server universe to act upon
 *        \param flags -
 *
 *        \return timed_event list
 */
timed_event *create_events(server_info *sinfo);

/*
 * new_event_list() - event_list constructor
 */
#ifdef NAS /* localmod 005 */
event_list *new_event_list(void);
#else
event_list *new_event_list();
#endif /* localmod 005 */

/*
 *      dup_event_list() - evevnt_list copy constructor
 *
 *        \param oel - event list to copy
 *        \param nsinfo - new universe
 *
 *      \return duplicated event_list
 */
event_list *dup_event_list(event_list *oel, server_info *nsinfo);

/*
 * free_event_list - event_list destructor
 */
void free_event_list(event_list *elist);

/*
 * new_timed_event() - timed_event constructor
 */
#ifdef NAS /* localmod 005 */
timed_event *new_timed_event(void);
#else
timed_event *new_timed_event();
#endif /* localmod 005 */

/*
 * dup_timed_event() - timed_event copy constructor
 *
 *   \param ote - timed_event to copy
 *   \param nsinfo - "new" universe where to find the event_ptr
 */
timed_event *dup_timed_event(timed_event *ote, server_info *nsinfo);

/*
 *      dup_timed_event_list() - timed_event copy constructor for a list
 *
 *        \param ote_list - list of timed_events to copy
 *        \param nsinfo - "new" universe where to find the event_ptr
 */
timed_event *dup_timed_event_list(timed_event *ote_list, server_info *nsinfo);

/*
 * free_timed_event - timed_event destructor
 */
void free_timed_event(timed_event *te);

/*
 * free_timed_event_list - destructor for a list of timed_event structures
 */
void free_timed_event_list(timed_event *te_list);

#ifndef NAS /* localmod 005 */
/*
 * new_event_list - event_list constructor
 */
event_list *new_event_list();

/*
 *      dup_event_list - event_list copy constructor
 *
 *        \param oel    - event list to copy
 *        \param nsinfo - "new" universe to find event pointers from
 */
event_list *dup_event_list(event_list *oel, server_info *nsinfo);

/*
 *      free_event_list - event_list destructor
 *
 *        \param el - event_list to free
 */
void free_event_list(event_list *el);
#endif /* localmod 005 */

/*
 *      find_event_by_name - find an event by event name
 *
 *        \param events - list of timed_event structures to search
 *        \param name   - name of event to search for
 *
 *      \return found timed_event or NULL
 */
timed_event *find_event_by_name(timed_event *events, char *name);


/*
 *      add_timed_event - add an event to a sorted list of events
 *
 *      ASSUMPTION: if multiple events are at the same time, all
 *                  end events will come first
 *
 *        \param events - event list to add event to
 *        \param te     - timed_event to add to list
 *
 *      \return head of timed_event list
 */
timed_event *add_timed_event(timed_event *events, timed_event *te);
/*
 *
 *	add_event - add a timed_event to an event list
 *
 *	  calendar - event list
 *	  te       - timed event
 *
 *	return 1 success / 0 failure
 *
 */
int add_event(event_list *calendar, timed_event *te);

/*
 *	delete_event - delete a timed event from an event list
 */
void delete_event(server_info *sinfo, timed_event *e);

/*
 *      create_event - create a timed_event with the passed in arguemtns
 *
 *        \param event_type - event_type member
 *        \param event_time - event_time member
 *        \param event_ptr  - event_ptr member
 *
 *      \return newly created timed_event or NULL on error
 */
timed_event *
create_event(enum timed_event_types event_type,
	time_t event_time, event_ptr_t *event_ptr,
	event_func_t event_func, void *event_func_arg);


/*
 *	calc_run_time - calculate the run time of a job
 *
 *	returns time_t of when the job will run
 *		or -1 on error
 */
time_t calc_run_time(char *job_name, server_info *sinfo, int flags);

/*
 *
 *	find_event_ptr - find the correct event pointer for the duplicated
 *			 event based on event type
 *
 *	  \param ote    - old event
 *	  \param nsinfo - "new" universe
 *
 * 	\return event_ptr in new universe or NULL on error
 */
event_ptr_t *find_event_ptr(timed_event *ote, server_info *nsinfo);
/*
 *	determine_event_name - determine a timed events name based off of
 *				event type and sets it
 *
 *	  \param te - the event
 *
 *	\par Side Effects
 *	te -> name is set to static data or data owned by other entities.
 *	It should not be freed.
 *
 *	\returns 1 if the name was successfully set 0 if not
 */
int determine_event_name(timed_event *te);

/*
 *	dedtime_change - update dedicated time policy
 *
 *	  \param policy - status structure to update dedicated time policy
 *	  \param arg    - "START" or "END"
 *
 *	\return success 1 or failure/error 0
 */
int dedtime_change(status *policy, void  *arg);

/*
 *	add_dedtime_events - add the dedicated time events from conf
 *
 *	  \param elist - the event list to add the dedicated time events to
 *
 *	\return success 1 / failure 0
 */
int add_dedtime_events(event_list *elist, struct status *policy);

/*
 *
 *	simulate_resmin - simulate the minimum amount of a resource list
 *			  for an event list until a point in time
 *
 *	  reslist  - resource list to simulate
 *	  end	  - end time
 *	  calendar - calendar to simulate
 *	  incl_arr - only use events for resresvs in this array (can be NULL)
 *	  exclude	  - job/resv to ignore (possibly NULL)
 *
 *	return static pointer to amount of resources available during
 *	return the entire length from now to end
 */
schd_resource *
simulate_resmin(schd_resource *reslist, time_t end, event_list *calendar,
	resource_resv **incl_arr, resource_resv *exclude);

/*
 *
 *	policy_change_to_str - return a printable name for a policy change event
 *
 *	  te - policy change timed event
 *
 *	return printable string name of policy change event
 */
const char *policy_change_to_str(timed_event *te);


/*
 * policy_change_info - should we do anything on policy change events
 */
int policy_change_info(server_info *sinfo, resource_resv *resresv);
/*
 *        takes a bitfield returned by simulate_events and will determine if
 *        the amount resources have gone up down, or are unchanged.  If events
 *	  caused resources to be both freed and used, we err on the side of
 *	  caution and say there are more resources.
 */
int describe_simret(unsigned int simret);

/*
 *       adds event(s) for bringing the node back up after we provision a node
 */
int add_prov_event(event_list *calendar, time_t event_time, node_info *node);

/*
 * generic simulation function which will call a function pointer over
 * a calendar from now to an end time.  The simulation will continue
 * until the end of the calendar or until the function returns <=0.
 */
int
generic_sim(event_list *calendar, unsigned int event_mask, time_t end, int default_ret,
	int (*func)(timed_event*, void*, void*), void *arg1, void *arg2);


te_list *new_te_list();

te_list *dup_te_list(te_list *ote, timed_event *new_timed_event_list);
te_list *dup_te_lists(te_list *ote, timed_event *new_timed_event_list);

void free_te_list(te_list *tel);

int add_te_list(te_list **tel, timed_event *te);
int remove_te_list(te_list **tel, timed_event *e);


#ifdef	__cplusplus
}
#endif
#endif /* _SIMULATE_H */
