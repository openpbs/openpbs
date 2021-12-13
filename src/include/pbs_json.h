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

#ifndef _PBS_JSON_H
#define _PBS_JSON_H
#ifdef __cplusplus
extern "C" {
#endif

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

typedef enum {
	JSON_NULL,
	JSON_STRING,
	JSON_INT,
	JSON_FLOAT,
	JSON_NUMERIC
} JsonValueType;

typedef enum {
	JSON_NOVALUE,
	JSON_ESCAPE,	 /* the value may be partially escaped */
	JSON_FULLESCAPE, /* escape all the necessary chars */
} JsonEscapeType;

typedef enum {
	JSON_VALUE,
	JSON_OBJECT,
	JSON_OBJECT_END,
	JSON_ARRAY,
	JSON_ARRAY_END,
} JsonNodeType;

typedef struct JsonNode JsonNode;

struct JsonNode {
	JsonNodeType node_type;
	JsonValueType value_type;
	char *key;
	union {
		char *string;
		long int inumber;
		double fnumber;
	} value;
};

JsonNode *add_json_node(JsonNodeType ntype, JsonValueType vtype, JsonEscapeType esc_type, char *key, void *value);
char *strdup_escape(JsonEscapeType esc_type, const char *str);
int generate_json(FILE *stream);
void free_json_node_list();

#ifdef __cplusplus
}
#endif
#endif /* _PBS_JSON_H */
