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

#ifndef PBS_ARRAY_LIST_H__
#define PBS_ARRAY_LIST_H__

/*
 * The data structures, macros and functions in this header file are used for
 * compressing the list of IP addresses sent across from the
 * server to the MOM(s) as part of the IS_CLUSTER_ADDRS message.
 *
 * The high-level algorithm is to reduce a given set of IP addresses to range(s)
 * E.g.: Given: 1,2,3,4,5,8,9,10,11 => {1-5},{8,11}
 * The ranges are stores as an ordered pair: (a,b). The first element 'a' refers
 * to the first IP address in the range and the second element 'b' refers to
 * the number of continuous IP addresses.
 * e.g. (1,5) => {1,2,3,4,5,6}  from 1  to (1+5)
 *      (5,3) => {5,6,7,8}      from 5  to (5+3)
 *     (11,0) => {11}           from 11 to (11+0)
 *
 * Each ordered pair is represented by a 'PBS_IP_RANGE' data structure.
 * For a given ordered pair (a,b), the first element 'a' is referred
 * to as 'ra_low' and the second element 'b' is referred to as 'ra_high' in the
 * code/documentation.
 *
 */

/**
 * 'T' is used to store 'ra_low' and 'ra_high'.
 * This was 'typedef-ed to allow for inclusion of IP v6 addresses possibly
 * in the future
 */
typedef long unsigned int T;

/**
 * 'PBS_IP_RANGE' is used to store the ordered pair (ra_low,ra_high) where 'ra_low' is the
 * starting IP address in a range and 'ra_high' gives the number of IP address
 * in the range
 */
typedef struct pbs_ip_range {
	T ra_low;
	T ra_high;
} PBS_IP_RANGE; /* ra_high  is the number of addresses in the range 'in addition' to the starting address */

typedef PBS_IP_RANGE *pntPBS_IP_RANGE;

/**
 * The PBS_IP_LIST data structure contains an array of ordered pairs (PBS_IP_RANGE)
 * Carries meta-data about the range: the number of slots used and number of
 * slots available
 */
typedef struct pbs_ip_list {
	pntPBS_IP_RANGE li_range;
	int li_nrowsused;
	int li_totalsize;
} PBS_IP_LIST;

typedef PBS_IP_LIST *pntPBS_IP_LIST;
#define CHUNK 5 /* The number of slots by which PBS_IP_LIST is resized */
#define INIT_VALUE 0

/* Various macros to retrieve or set 'ra_low' or 'ra_high' for a given PBS_IP_RANGE */
#define IPLIST_GET_LOW(X, Y) (X)->li_range[(Y)].ra_low
#define IPLIST_GET_HIGH(X, Y) (X)->li_range[(Y)].ra_high
#define IPLIST_SET_LOW(X, Y, Z) (X)->li_range[(Y)].ra_low = (Z)
#define IPLIST_SET_HIGH(X, Y, Z) (X)->li_range[(Y)].ra_high = (Z)
#define IPLIST_IS_CONTINUOUS(X, Y) ((X) + 1 == (Y))

#define IPLIST_IS_CONTINUOUS_ROW(X, Y, Z) (IPLIST_IS_CONTINUOUS((IPLIST_GET_LOW(X, Y) + IPLIST_GET_HIGH(X, Y)), (Z)))
#define IPLIST_IS_ROW_SAME(X, Y, Z) ((IPLIST_GET_LOW(X, Y) + IPLIST_GET_HIGH(X, Y)) == (Z))
#define IPLIST_MOVE_DOWN(X, Y) (((X) - (Y)) * sizeof(PBS_IP_RANGE))
#define IPLIST_MOVE_UP(X, Y) (((X) - ((Y) + 1)) * sizeof(PBS_IP_RANGE))
#define IPLIST_SHIFT_ALL_DOWN_BY_ONE(X, Y, Z) memmove((X)->li_range + (Y) + 1, (X)->li_range + (Y), (Z) * sizeof(PBS_IP_RANGE))
#define IPLIST_SHIFT_ALL_UP_BY_ONE(X, Y, Z) memmove((X)->li_range + (Y), (X)->li_range + (Y) + 1, (Z) * sizeof(PBS_IP_RANGE))

#define IPLIST_INSERT_SUCCESS 0
#define IPLIST_INSERT_FAILURE -1
#define IPLIST_DELETE_SUCCESS 0
#define IPLIST_DELETE_FAILURE -1

/**
 * @brief
 *	Creates an array of size CHUNK of type PBS_IP_RANGE
 *
 * @par Functionality:
 *      This function is invoked by create_pbs_iplist
 *      It results in an array of PBS_IP_RANGE type of size CHUNK
 *      which is an array of ordered pairs (a,b)
 *
 * @param[in]	void
 *
 * @return	pntPBS_IP_RANGE a pointer to PBS_IP_RANGE
 */
pntPBS_IP_RANGE create_pbs_range(void);

/**
 * @brief
 *	Reallocates the array of PBS_IP_RANGE by CHUNK
 *
 * @par Functionality:
 *      Since the PBS_IP_LIST is build dynamically at run-time, therefore
 *      if required, more slots are created by invoking this function.
 *
 * @param[in]	void
 *
 * @return	pntPBS_IP_RANGE a pointer to the newly reallocated PBS_IP_RANGE
 */
pntPBS_IP_LIST resize_pbs_iplist(pntPBS_IP_LIST);

/**
 * @brief
 *	Creates an instance of PBS_IP_LIST
 *
 * @par Functionality:
 *      Invokes create_pbs_range() to
 *      create a PBS_IP_RANGE to store ordered pairs and sets 'totalsize' to CHUNK
 *
 * @param[in]	void
 *
 * @return	pntPBS_IP_RANGE a pointer to PBS_IP_RANGE or NULL if memory allocation fails
 */
pntPBS_IP_LIST create_pbs_iplist(void);

/**
 * @brief
 *	Frees memory associated with PBS_IP_LIST and PBS_IP_RANGE
 *
 * @param[in]	pntPBS_IP_LIST, pointer to PBS_IP_LIST to be freed
 *
 * @return	void
 */
void delete_pbs_iplist(pntPBS_IP_LIST);

/**
 * @brief
 *	Identifies location of slot in which to insert new incoming element.
 *
 * @par Functionality:
 *      This function is invoked by both insert_pbs_element( ) and delete_pbs_element( )
 *      The function takes pointer to PBS_IP_LIST in which to search for key 'T'
 *      The function performs a binary search over only the 'ra_low' elements of
 *      all the ordered pairs in the PBS_IP_LIST. If the element is found, the
 *      function returns the index at which the key is found. Else the function
 *      returns the index at which the element should be inserted. This is set
 *      in the third variable which is passed by reference to the function.
 *
 * @param[in]	pntPBS_IP_LIST pointer to the PBS_IP_LIST in which search is done
 * @param[in]  T the key for which to search in PBS_IP_LIST
 * @param[in]  int* The variable in which location of insertion/deletion is set
 *
 * @return	Non-negative if location found, -1 if location not found
 */
int search_iplist_location(pntPBS_IP_LIST, T, int *);

/**
 * @brief
 *	Inserts provided key into provided PBS_IP_LIST
 *
 * @par Functionality:
 *      The function first calls search_iplist_location to determine location at
 *      which to insert the new element.
 *      The function can determine when the insertion of new key may cause
 *      two distinct ranges to merge and does so.
 *      Function invokes resize_pbs_iplist to resize PBS_IP_LIST as required.
 *      Builds the PBS_IP_LIST dynamically at run-time.
 *
 * @param[in]	pntPBS_IP_LIST pointer to the PBS_IP_LIST in which to insert key.
 * @param[in]  T the key to insert in PBS_IP_LIST
 *
 * @return
 * 0 - SUCCESS
 * 1 - FAILURE
 */
int insert_iplist_element(pntPBS_IP_LIST, T);

/**
 * @brief
 *	Deletes provided key from given PBS_IP_LIST
 *
 * @par Functionality:
 *      The function takes the provided key and removes it from the given
 *      PBS_IP_LIST. If the key matches an element inside a range, then the
 *      range needs to be split into two ranges. The function takes care of
 *      the splitting of the ranges.
 *
 * @param[in]	pntPBS_IP_LIST pointer to the pntPBS_IP_LIST from which to delete key.
 * @param[in]  T the key to delete from PBS_IP_LIST
 *
 * @return
 * 0 - SUCCESS
 * 1 - FAILURE
 */
int delete_iplist_element(pntPBS_IP_LIST, T);

#endif
