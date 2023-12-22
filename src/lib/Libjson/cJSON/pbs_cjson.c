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
#include <stdio.h>
#include <cjson/cJSON.h>
#include "pbs_json.h"

/**
 * @brief
 *	Insert cJSON structure into cJSON object or array
 *
 * @param[in] parent - parent cJSON structure
 * @param[in] key - key for object structure, ignored for arrays
 * @param[in] value - cJSON structure
 *
 */
static void
cjson_insert_item(cJSON *parent, char *key, cJSON *value)
{
    if (cJSON_IsObject(parent))
        cJSON_AddItemToObject(parent, key, value);

    if (cJSON_IsArray(parent))
        cJSON_AddItemToArray(parent, value);
}

/**
 * @brief
 *	create json object
 *
 * @return - json_data
 * @retval   NULL - Failure
 * @retval   json_data - Success
 *
 */
json_data *
pbs_json_create_object()
{
    return (json_data *) cJSON_CreateObject();
}

/**
 * @brief
 *	create json array
 *
 * @return - json_data
 * @retval   NULL - Failure
 * @retval   json_data - Success
 *
 */
json_data *
pbs_json_create_array()
{
    return (json_data *) cJSON_CreateArray();
}

/**
 * @brief
 *	insert json data into json structure (like object or array)
 *
 * @param[in] parent - json object or array
 * @param[in] key - key for object structure, ignored for arrays
 * @param[in] value - json structure
 *
 */
void
pbs_json_insert_item(json_data *parent, char *key, json_data *value)
{
    cJSON *par = (cJSON *) parent;
    cJSON *val = (cJSON *) value;
    cjson_insert_item(par, key, val);
}

/**
 * @brief
 *  insert string into json structure (like object or array)
 *
 * @param[in] parent - json object or array
 * @param[in] key - key for object structure, ignored for arrays
 * @param[in] value - string
 *
 * @return - Error code
 * @retval   1 - Failure
 * @retval   0 - Success
 *
 */
int
pbs_json_insert_string(json_data *parent, char *key, char *value)
{
    cJSON *par = (cJSON *) parent;
    cJSON *val;
    if ((val = cJSON_CreateString(value)) == NULL)
        return 1;
    cjson_insert_item(par, key, val);
    return 0;
}

/**
 * @brief
 *  insert number into json structure (like object or array)
 *
 * @param[in] parent - json object or array
 * @param[in] key - key for object structure, ignored for arrays
 * @param[in] value - number
 *
 * @return - Error code
 * @retval   1 - Failure
 * @retval   0 - Success
 *
 */
int
pbs_json_insert_number(json_data *parent, char *key, double value)
{
    cJSON *par = (cJSON *) parent;
    cJSON *val;
    if ((val = cJSON_CreateNumber(value)) == NULL)
        return 1;
    cjson_insert_item(par, key, val);
    return 0;
}

/**
 * @brief
 *  parse and insert value into json structure (like object or array)
 *
 * @param[in] parent - json object or array
 * @param[in] key - key for object structure, ignored for arrays
 * @param[in] value - string for parsing
 * @param[in] ignore_empty - do not insert empty values (like 0 or "")
 *
 * @return - Error code
 * @retval   1 - Failure
 * @retval   0 - Success
 *
 */
int
pbs_json_insert_parsed(json_data *parent, char *key, char *value, int ignore_empty)
{
    cJSON *par = (cJSON *) parent;
    cJSON *val;
    if ((val = cJSON_ParseWithOpts(value, NULL, 1)) == NULL)
        val = cJSON_CreateString(value);
    if (ignore_empty && val != NULL) {
        if (cJSON_IsString(val) && cJSON_GetStringValue(val)[0] == '0') {
            cJSON_Delete(val);
            val = NULL;
        }
#if CJSON_VERSION_MAJOR <= 17 && CJSON_VERSION_MINOR <= 7 && CJSON_VERSION_PATCH < 13
        if (cJSON_IsNumber(val) && val->valuedouble == 0)
#else
        if (cJSON_IsNumber(val) && cJSON_GetNumberValue(val) == 0)
#endif
        {
            cJSON_Delete(val);
            val = NULL;
        }
    }
    if (!ignore_empty && val == NULL)
        return 1;
    if (val)
        cjson_insert_item(par, key, val);
    return 0;
}

/**
 * @brief
 *  print json data to output
 *
 * @param[in] data - json data
 * @param[in] stream - output
 *
 * @return - Error code
 * @retval   1 - Failure
 * @retval   0 - Success
 *
 */
int
pbs_json_print(json_data *data, FILE *stream)
{
	char *json_out = cJSON_Print((cJSON *) data);
    if (json_out != NULL) {
        fprintf(stream, "%s\n", json_out);
		free(json_out);
	} else {
		return 1;
	}
    return 0;
}

/**
 * @brief
 *  free json structure
 *
 * @param[in] data - json data
 *
 */
void
pbs_json_delete(json_data *data)
{
    cJSON_Delete((cJSON *) data);
}
