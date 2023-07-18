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

#include <stdlib.h>
#include "pbs_json.h"
#include "cJSON.h"

static cJSON *root = NULL; /* root of cJSON structure */
static cJSON *node = NULL; /* current node (object or array) */
static cJSON **np = NULL; /* node path to current node */
static int np_size;
static int np_pos;

/**
 * @brief
 * json_path_down
 * set a new child node to node path
 *
 * @param[in] n - new child node
 *
 * @return	structure node
 * @retval	structure of current node
 * @retval	NULL error
 *
 */
static cJSON *
json_path_down(cJSON *n)
{
	if (np == NULL) {
		np = (cJSON **) malloc(sizeof(cJSON *));

		if (np == NULL) {
			fprintf(stderr, "out of memory\n");
			return NULL;
		}

		np_size = 1;
		np_pos = -1;
	}

	if (np_pos + 1 < np_size) {
		np_size = np_size * 2;
		np = (cJSON **) realloc(np, sizeof(cJSON *) * np_size);

		if (np == NULL) {
			fprintf(stderr, "out of memory\n");
			return NULL;
		}
	}

	np[++np_pos] = n;
	return n;
}

/**
 * @brief
 * json_path_up
 * get the parrent of current node in node path
 *
 * @return	structure node
 * @retval	structure of current node
 * @retval	NULL error
 *
 */
static cJSON *
json_path_up()
{
	if (np_pos == 0 || np == NULL)
		return root;

	if (np_pos > 0)
		return np[--np_pos];

	return NULL;
}

/**
 * @brief
 * add_json_node
 * add object, array, or value into the current 'node'
 * which is either object or array
 * root object is created on first run
 *
 * @param[in] ntype - node type
 * @param[in] vtype - value type
 * @param[in] key - node key
 * @param[in] value - value for node
 *
 * @return	int
 * @retval	1	error
 * @retval	0	success
 *
 */
int
add_json_node(JsonNodeType ntype, JsonValueType vtype, char *key, void *value)
{
	if (root == NULL) {
		root = cJSON_CreateObject();
		if ((node = json_path_down(root)) == NULL)
			return 1;
	}

	if (root == NULL || node == NULL)
		return 1;

	if (ntype == JSON_VALUE && value != NULL) {
		cJSON *jvalue;

		if (vtype == JSON_STRING)
			jvalue = cJSON_CreateString((char *) value);

		if (vtype == JSON_INT)
			jvalue = cJSON_CreateNumber((double)(*(long int *)value));

		if (vtype == JSON_FLOAT)
			jvalue = cJSON_CreateNumber(*((double *) value));

		if (vtype == JSON_NULL) {
			/* try to parse value */
			jvalue = cJSON_ParseWithOpts((char *) value, NULL, 1);

			if (jvalue == NULL) {
				/* value parsing failed -> consider as a string */
				jvalue = cJSON_CreateString((char *) value);
			}
		}

		if (jvalue != NULL) {
			if (cJSON_IsObject(node))
				cJSON_AddItemToObject(node, key, jvalue);

			if (cJSON_IsArray(node))
				cJSON_AddItemToArray(node, jvalue);
		}
	}

	if (ntype == JSON_OBJECT || ntype == JSON_ARRAY) {
		cJSON *new_node;

		if (ntype == JSON_OBJECT)
			new_node = cJSON_CreateObject();

		if (ntype == JSON_ARRAY)
			new_node = cJSON_CreateArray();

		if (new_node == NULL) {
			fprintf(stderr, "cJSON error\n");
			return 1;
		}

		if (cJSON_IsObject(node))
			cJSON_AddItemToObject(node, key, new_node);

		if (cJSON_IsArray(node))
			cJSON_AddItemToArray(node, new_node);

		if ((node = json_path_down(new_node)) == NULL)
			return 1;
	}

	if (ntype == JSON_OBJECT_END || ntype == JSON_ARRAY_END) {
		if ((node = json_path_up()) == NULL)
			return 1;
	}

	return 0;
}

/**
 * @brief
 * print_json
 * print json structure using cJSON_Print()
 *
 * @param[in] stream - fd to which json o/p written
 *
 * @return	nothing
 *
 */
void
print_json(FILE *stream)
{
	char *json = NULL;
	json = cJSON_Print(root);
	if (json != NULL) {
		fprintf(stream, "%s", json);
		free(json);
	} else {
		fprintf(stderr, "cJSON error\n");
	}
}

/**
 * @brief
 * free_json
 * delete json structure using cJSON_Delete()
 *
 * @return	nothing
 *
 */
void
free_json()
{
	cJSON_Delete(root);
	if (np != NULL) {
		free(np);
		np = NULL;
	}
}
