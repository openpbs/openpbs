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
 * @file    db_postgres_attr.c
 *
 * @brief
 *	Implementation of the attribute related functions for postgres
 *
 */

#include <pbs_config.h>   /* the master config generated by configure */
#include "pbs_db.h"
#include "db_postgres.h"
#include "assert.h"

/*
 * initially allocate some space to buffer, anything more will be
 * allocated later as required. Just allocate 1000 chars, hoping that
 * most common sql's might fit within it without needing to resize
 */
#define INIT_BUF_SIZE 1000

#define   TEXTOID   25

struct str_data {
	int32_t len;
	char str[0];
};

/* Structure of array header to determine array type */
struct pg_array {
	int32_t ndim; /* Number of dimensions */
	int32_t off; /* offset for data, removed by libpq */
	Oid elemtype; /* type of element in the array */

	/* First dimension */
	int32_t size; /* Number of elements */
	int32_t index; /* Index of first element */
	/* data follows this portion */
};

/**
 * @brief
 *	Create a svrattrl structure from the attr_name, and values
 *
 * @param[in]	attr_name - name of the attributes
 * @param[in]	attr_resc - name of the resouce, if any
 * @param[in]	attr_value - value of the attribute
 * @param[in]	attr_flags - Flags associated with the attribute
 *
 * @retval - Pointer to the newly created attribute
 * @retval - NULL - Failure
 * @retval - Not NULL - Success
 *
 */
svrattrl *
make_attr(char *attr_name, char *attr_resc, char *attr_value, int attr_flags)
{
	int tsize;
	svrattrl *psvrat = NULL;
	int nlen = 0, rlen = 0, vlen = 0;
	char *p = NULL;

	tsize = sizeof(svrattrl);
	if (!attr_name)
		return NULL;

	nlen = strlen(attr_name);
	tsize += nlen + 1;

	if (attr_resc) {
		rlen = strlen(attr_resc);
		tsize += rlen + 1;
	}

	if (attr_value) {
		vlen = strlen(attr_value);
		tsize += vlen + 1;
	}

	if ((psvrat = (svrattrl *) malloc(tsize)) == 0)
		return NULL;

	CLEAR_LINK(psvrat->al_link);
	psvrat->al_sister = NULL;
	psvrat->al_atopl.next = 0;
	psvrat->al_tsize = tsize;
	psvrat->al_name = (char *) psvrat + sizeof(svrattrl);
	psvrat->al_resc = 0;
	psvrat->al_value = 0;
	psvrat->al_nameln = nlen;
	psvrat->al_rescln = 0;
	psvrat->al_valln = 0;
	psvrat->al_refct = 1;

	strcpy(psvrat->al_name, attr_name);
	p = psvrat->al_name + psvrat->al_nameln + 1;

	if (attr_resc && attr_resc[0] != '\0') {
		psvrat->al_resc = p;
		strcpy(psvrat->al_resc, attr_resc);
		psvrat->al_rescln = rlen;
		p = p + psvrat->al_rescln + 1;
	}
	
	psvrat->al_value = p;
	if (attr_value && attr_value[0] != '\0') {
		strcpy(psvrat->al_value, attr_value);
		psvrat->al_valln = vlen;
	}

	psvrat->al_flags = attr_flags;
	psvrat->al_op = SET;

	return (psvrat);
}
/**
 * @brief
 *	Converts a postgres hstore(which is in the form of array) to attribute linked list
 *
 * @param[in]	raw_array - Array string which is in the form of postgres hstore
 * @param[out]  attr_list - List of pbs_db_attr_list_t objects
 *
 * @return      Error code
 * @retval	-1 - On Error
 * @retval	 0 - On Success
 * @retval	>1 - Number of attributes
 *
 */
int
dbarray_2_attrlist(char *raw_array, pbs_db_attr_list_t *attr_list)
{
	int i;
	int j;
	int rows;
	int flags;
	char *endp;
	char *attr_name;
	char *attr_value;
	char *attr_flags;
	char *attr_resc;
	svrattrl *pal;
	struct pg_array *array = (struct pg_array *) raw_array;
	struct str_data *val = (struct str_data *)(raw_array + sizeof(struct pg_array));

	CLEAR_HEAD(attr_list->attrs);
	attr_list->attr_count = 0;

	if (ntohl(array->ndim) == 0)
		return 0;

	if (ntohl(array->ndim) > 1 || ntohl(array->elemtype) != TEXTOID)
		return -1;

	rows = ntohl(array->size);

	for (i=0, j = 0; j < rows; i++, j+=2) {

		attr_resc = NULL;
		attr_value = NULL;
		
		attr_name = val->str;
		val = (struct str_data *)((char *) val->str + ntohl(val->len));

		attr_flags = val->str;
		val = (struct str_data *)((char *) val->str + ntohl(val->len));

		if ((attr_resc = strchr(attr_name, '.'))) {
			*attr_resc = '\0';
			attr_resc++;
		}

		if ((attr_value = strchr(attr_flags, '.'))) {
			*attr_value = '\0';
			attr_value++;
		}

		flags = strtol(attr_flags, &endp, 10);
		if (*endp != '\0')
			return -1;

		if (!(pal = make_attr(attr_name, attr_resc, attr_value, flags)))
			return -1;
		
		append_link(&(attr_list->attrs), &pal->al_link, pal);
	}
	attr_list->attr_count = i;
	return 0;
}

/**
 * @brief
 *	Converts an PBS link list of attributes to DB hstore(array) format
 *
 * @param[out]  raw_array - Array string which is in the form of postgres hstore
 * @param[in]	attr_list - List of pbs_db_attr_list_t objects
 * @param[in]	keys_only - if true, convert only the keys, not values also
 *
 * @return      Error code
 * @retval	-1 - On Error
 * @retval	 0 - On Success
 *
 */
int
attrlist_2_dbarray_ex(char **raw_array, pbs_db_attr_list_t *attr_list, int keys_only)
{
	struct pg_array *array;
	int len = 0;
	struct str_data *val = NULL;
	int attr_val_len = 0;
	svrattrl *pal;
	int count = 0;

	len = sizeof(struct pg_array);
	for (pal = (svrattrl *)GET_NEXT(attr_list->attrs); pal != NULL; pal = (svrattrl *)GET_NEXT(pal->al_link)) {
		len += sizeof(int32_t) + PBS_MAXATTRNAME + PBS_MAXATTRRESC + 1; /* include space for dot */
		if (keys_only)
			attr_val_len = 0;
		else
			attr_val_len = (pal->al_atopl.value == NULL? 0:strlen(pal->al_atopl.value));
		len += sizeof(int32_t) + 3 + attr_val_len + 1; /* include space for dot */
		count++;
	}

	assert(count == attr_list->attr_count);

	array = malloc(len);
	if (!array)
		return -1;
	array->ndim = htonl(1);
	array->off = 0;
	array->elemtype = htonl(TEXTOID);
	if (keys_only)
		array->size = htonl(attr_list->attr_count);
	else
		array->size = htonl(attr_list->attr_count * 2);
	array->index = htonl(1);

	/* point to data area */
	val = (struct str_data *)((char *) array + sizeof(struct pg_array));

	for (pal = (svrattrl *)GET_NEXT(attr_list->attrs); pal != NULL; pal = (svrattrl *)GET_NEXT(pal->al_link)) {
		sprintf(val->str, "%s.%s", pal->al_atopl.name, ((pal->al_atopl.resource == NULL)?"":pal->al_atopl.resource));
		val->len = htonl(strlen(val->str));

		val = (struct str_data *)(val->str + ntohl(val->len)); /* point to end */

		if (keys_only == 0) {
			sprintf(val->str, "%d.%s", pal->al_flags, ((pal->al_atopl.value == NULL)?"":pal->al_atopl.value));
			val->len = htonl(strlen(val->str));

			val = (struct str_data *)(val->str + ntohl(val->len)); /* point to end */
		}
	}
	*raw_array = (char *) array;

	return ((char *) val - (char *) array);
}

/**
 * @brief
 *	Converts an PBS link list of attributes to DB hstore(array) format
 *
 * @param[out]  raw_array - Array string which is in the form of postgres hstore
 * @param[in]	attr_list - List of pbs_db_attr_list_t objects
 *
 * @return      Error code
 * @retval	-1 - On Error
 * @retval	 0 - On Success
 *
 */
int
attrlist_2_dbarray(char **raw_array, pbs_db_attr_list_t *attr_list)
{
	return attrlist_2_dbarray_ex(raw_array, attr_list, 0);
}

/**
 * @brief
 *	Frees attribute list memory
 *
 * @param[in]	attr_list - List of pbs_db_attr_list_t objects
 *
 * @return      None
 *
 */
void
free_db_attr_list(pbs_db_attr_list_t *attr_list)
{
	if (attr_list->attr_count > 0) {
		free_attrlist(&attr_list->attrs);
		attr_list->attr_count = 0;
	}
}
