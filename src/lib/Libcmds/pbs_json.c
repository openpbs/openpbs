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
*/

#include <ctype.h>
#include "pbs_json.h"
#include "libutil.h"
#define ARRAY_NESTING_LEVEL 500 /* describes the nesting level of a JSON array*/

typedef struct JsonLink JsonLink;
struct JsonLink{
	JsonNode *node;
	JsonLink *next;
};

static JsonLink *head = NULL, *prev_link = NULL;

/**
 * @brief
 *	create_json_node
 * 	malloc and initialize a new json node
 *
 * @return	pointer to newly created json node.
 */
static JsonNode*
create_json_node() {
	JsonNode *new_node = malloc(sizeof(JsonNode));
	if (new_node == NULL) {
		return NULL;
	}
	new_node->node_type  = JSON_VALUE;
	new_node->value_type = JSON_NULL;
	new_node->key = NULL;
	return new_node;
}

/**
 * @brief
 *	link a json node
 *
 * @param[in] node - pointer to JsonNode
 *
 * @return	int
 * @retval	0	if linked
 * @retval	1	if node null
 *
 */
static int
link_node(JsonNode *node) {
	JsonLink *new_link = malloc(sizeof(JsonLink));
	if (new_link == NULL)
		return 1;
	new_link->node = node;
	new_link->next = NULL;
	if (head == NULL) {
		head = new_link;
		prev_link = head;
	} else {
		prev_link->next = new_link;
		prev_link = new_link;
	}
	return 0;
}

/**
 * @brief
 * Duplicates a string where the new string conforms to JSON
 *
 * @param[in] str - string to be duplicated
 *
 * @return string
 * @retval JSON conforming string   success
 * @retval NULL                     error
 *
 */
char*
strdup_escape(JsonEscapeType esc_type, const char *str)
{
	int       i = 0;
	int       len = 0;
	char      *temp = NULL;
	char      *buf = NULL;
	if (str != NULL) {
		i = 0;
		len = MAXBUFLEN;
		buf = (char *) malloc(len);
		if (buf == NULL)
			return NULL;
		while (*str) {
			switch (*str) {
			case '\b':
				buf[i++] = '\\';
				buf[i++] = 'b';
				str++;
				break;
			case '\f':
				buf[i++] = '\\';
				buf[i++] = 'f';
				str++;
				break;
			case '\n':
				buf[i++] = '\\';
				buf[i++] = 'n';
				str++;
				break;
			case '\r':
				buf[i++] = '\\';
				buf[i++] = 'r';
				str++;
				break;
			case '\t':
				buf[i++] = '\\';
				buf[i++] = 't';
				str++;
				break;
			case '"':
				if (esc_type == JSON_ESCAPE) {
					buf[i++] = *str++;
					break;
				} /* else JSON_FULLESCAPE */
				buf[i++] = '\\';
				buf[i++] = '"';
				str++;
				break;
			case '\\':
				if (esc_type == JSON_ESCAPE) {
					buf[i++] = *str++;
					break;
				} /* else JSON_FULLESCAPE */
				buf[i++] = '\\';
				buf[i++] = '\\';
				str++;
				break;
			default:
				buf[i++] = *str++;
			}
			if (i >= len - 2) {
				len *= BUFFER_GROWTH_RATE;
				temp = (char *) realloc(buf, len);
				if (temp == NULL) {
					free(buf);
					return NULL;
				}
				buf = temp;
			}
		}
		buf[i] = '\0';
	}
	return buf;
}

/**
 * @brief
 *	add node to json list
 *
 * @param[in] ntype - node type
 * @param[in] vtype - value type
 * @param[in] key - node key
 * @param[in] value - value for node
 *
 * @return 	structure handle
 * @retval	structure handle to JsonNode list	success
 * @retval	NULL					error
 *
 */
JsonNode*
add_json_node(JsonNodeType ntype, JsonValueType vtype, JsonEscapeType esc_type, char *key, void *value) {
	int 	  rc = 0;
	char	  *ptr = NULL;
	char 	  *pc  = NULL;
	double    val  = 0;
	long int  ivalue = 0;
	JsonNode  *node = NULL;

	node = create_json_node();
	if (node == NULL) {
		fprintf(stderr, "Json Node: out of memory\n");
		return NULL;
	}
	node->node_type = ntype;
	if (key != NULL) {
		ptr = strdup((char *)key);
		if (ptr == NULL) {
			fprintf(stderr, "Json Node: out of memory\n");
			return NULL;
		}
		node->key = ptr;
	}
	if (vtype == JSON_NULL && value != NULL) {
		val = strtod(value, &pc);
		while (pc) {
			if (isspace(*pc))
				pc++;
			else
				break;
		}
		if (strcmp(pc, "") == 0) {
			ivalue = (long int) val;
			if (val == ivalue) {/* This checks if value have any non zero fractional part after decimal. If not then value has to be represented as integer otherwise as float. */
				node->value_type = JSON_INT;
				node->value.inumber = ivalue;
			} else {
				node->value_type = JSON_FLOAT;
				node->value.fnumber = val;
			}
		} else
			node->value_type = JSON_STRING;
	}
	else {
		node->value_type = vtype;
		if (node->value_type == JSON_INT)
			node->value.inumber = *((long int *)value);
		else if (node->value_type == JSON_FLOAT)
			node->value.fnumber = *((double *)value);
	}


	if (node->value_type == JSON_STRING) {
		if (value != NULL) {
			ptr = strdup_escape(esc_type, value);
			if (ptr == NULL)
				return NULL;
		}
		node->value.string = ptr;
	}
	rc = link_node(node);
	if (rc) {
		free(node);
		fprintf(stderr, "Json link: out of memory\n");
		return NULL;
	}
	return node;
}

/**
 * @brief
 *	frees a json node
 *
 * @return	Void
 *
 */
void
free_json_node() {

	JsonLink *link = head;
	while (link != NULL) {
		if (link->node->value_type == JSON_STRING) {
			if (link->node->value.string != NULL)
				free(link->node->value.string);
		}
		if (link->node->key != NULL)
			free(link->node->key);
		free(link->node);
		head = link->next;
		free(link);
		link = head;
	}
	head = NULL;
	prev_link = NULL;
}

/**
 * @brief
 *	generate_json_node
 *	Takes a JsonNode type link list and file stream as an input.
 * 	Reads the link-list node by node and write the json output
 * 	on the passed file stream.
 *
 * @param[in] stream - fd to which json o/p written
 *
 * @return	int
 * @retval	0	success
 * @retval	1	error
 *
 */
int
generate_json(FILE * stream) {
	int	  indent = 0;
	int	  prnt_comma = 0;
	int	  last_object_value = 0;
	int	  last_array_value = 0;
	int	 *arr_lvl = NULL;
	int	  curnt_arr_lvl= 0;
	JsonNode *node = NULL;
	JsonLink *link = head;

	fprintf(stream, "{");
	indent += 4;
	arr_lvl = malloc(ARRAY_NESTING_LEVEL * sizeof(int*));
	memset(arr_lvl, 0, (ARRAY_NESTING_LEVEL * sizeof(int)));

	while (link) {
		node = link->node;
		switch (node->node_type) {
			case JSON_OBJECT:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");
				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s{", indent, indent, " ");
				else
					fprintf(stream, "%*.*s\"%s\":{", indent, indent, " ", node->key);
				indent += 4;
				prnt_comma = 0;
				/*moving to next node since there's no value associated within an OBJECT type node*/
				link = link->next;
				continue;

			case JSON_OBJECT_END:
				last_object_value = 1;
				break;

			case JSON_ARRAY:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");
				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s[",indent,indent," ");
				else
					fprintf(stream, "%*.*s\"%s\":[", indent, indent, " ", node->key);
				indent += 4;
				prnt_comma = 0;
				arr_lvl[curnt_arr_lvl+1] = indent;
				curnt_arr_lvl++;
				break;

			case JSON_ARRAY_END:
				last_array_value = 1;
				break;

			case JSON_VALUE:
				break;

			default:
				free(arr_lvl);
				return 1;
		}
		switch (node->value_type) {
			case JSON_STRING:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");
				if (arr_lvl[curnt_arr_lvl]==indent)
					fprintf(stream, "%*.*s\"%s\"", indent, indent, " ", node->value.string);
				else
					fprintf(stream, "%*.*s\"%s\":\"%s\"", indent, indent, " ", node->key, node->value.string);
				prnt_comma = 1;
				break;

			case JSON_INT:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");

				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s%ld",indent,indent," ", node->value.inumber);
				else
					fprintf(stream, "%*.*s\"%s\":%ld", indent, indent, " ", node->key, node->value.inumber);
				prnt_comma = 1;
				break;
			case JSON_FLOAT:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");


				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s%lf",indent,indent," ", node->value.fnumber);
				else
					fprintf(stream, "%*.*s\"%s\":%lf", indent, indent, " ", node->key, node->value.fnumber);
				prnt_comma = 1;
				break;

			case JSON_NULL:
				break;

			default:
				free(arr_lvl);
				return 1;
		}

		if (last_array_value) {
			indent -= 4;
			fprintf(stream, "\n%*.*s]", indent, indent, " ");
			last_array_value = 0;
			curnt_arr_lvl--;
			prnt_comma = 1;
		} else if (last_object_value) {
			indent -= 4;
			fprintf(stream, "\n%*.*s}", indent, indent, " ");
			last_object_value = 0;
			prnt_comma = 1;
		}
		link = link->next;
	}
	free(arr_lvl);
	indent -= 4;
	if (indent != 0)
		return 1;
	fprintf(stream, "\n}\n");
	return 0;
}
