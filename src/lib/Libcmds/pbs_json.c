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
#include <ctype.h>
#include "pbs_json.h"
#include "libutil.h"
#define ARRAY_NESTING_LEVEL 500 /* describes the nesting level of a JSON array*/

typedef struct JsonLink JsonLink;
struct JsonLink {
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
static JsonNode *
create_json_node()
{
	JsonNode *new_node = malloc(sizeof(JsonNode));
	if (new_node == NULL) {
		return NULL;
	}
	new_node->node_type = JSON_VALUE;
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
link_node(JsonNode *node)
{
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
 * @note
 * - If a string value contains one of the following:
 * 	\'
 *	\,
 * and the \ is not escaped with another backslash, then drop that \.
 * Otherwise, both forms produce JSON error.
 * For instance:
 *	\'     -> '
 *	\\'    -> \\'
 *	\\\'   -> \\'
 *	\\\\'  -> \\\\'
 *	\\\\\' -> \\\\'
 * - If a string value contains " (embedded double quote) and it's not escaped
 *   (not preceded by a backslash), then escape it, resulting in \".
 */
char *
strdup_escape(JsonEscapeType esc_type, const char *str)
{
	int i = 0;
	int len = 0;
	char *temp = NULL;
	char *buf = NULL;
	const char *bufstr = NULL;
	const char *orig_str = NULL;
	if (str != NULL) {
		orig_str = str;
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
						bufstr = str;
						bufstr--;
						if ((bufstr >= orig_str) && (*bufstr != '\\')) {
							buf[i++] = '\\';
						}
						buf[i++] = *str++;
						break;
					} /* else JSON_FULLESCAPE */
					buf[i++] = '\\';
					buf[i++] = '"';
					str++;
					break;
				case '\\':
					if (esc_type == JSON_ESCAPE) {
						bufstr = str + 1;
						if (*bufstr && ((*bufstr == '\'') || (*bufstr == ','))) {
							str++;
							buf[i++] = *str++;
						} else {
							buf[i++] = *str++;
							if (*bufstr)
								buf[i++] = *str++;
						}
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
 * @brief free an individual json node
 * @param[in] node - node to free
 *
 * @return void
 */
void
free_json_node(JsonNode *node)
{
	if ((node->value_type == JSON_STRING) || (node->value_type == JSON_NUMERIC)) {
		if (node->value.string != NULL)
			free(node->value.string);
	}
	if (node->key != NULL)
		free(node->key);
	free(node);
}

/**
 * @brief
 *	frees the json node list
 *
 * @return	Void
 *
 */
void
free_json_node_list()
{
	JsonLink *link = head;
	while (link != NULL) {
		free_json_node(link->node);
		head = link->next;
		free(link);
		link = head;
	}
	head = NULL;
	prev_link = NULL;
}

/**
 * @brief
 *	Determines if 'str' contains only white-space characters.
 *
 * @param[in] str - string to check
 *
 * @return	int
 * @retval	1	if 'str' contains only white-space characters.
 * @retval	0	error or otherwise.
 *
 */
static int
whitespace_only(const char *str)
{

	if (str == NULL)
		return (0);

	while ((*str != '\0') && isspace(*str))
		str++;
	if (*str == '\0')
		return (1);
	return (0);
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
JsonNode *
add_json_node(JsonNodeType ntype, JsonValueType vtype, JsonEscapeType esc_type, char *key, void *value)
{
	int rc = 0;
	char *ptr = NULL;
	char *pc = NULL;
	JsonNode *node = NULL;
	int value_is_whitespace = 0;

	node = create_json_node();
	if (node == NULL) {
		fprintf(stderr, "Json Node: out of memory\n");
		return NULL;
	}
	node->node_type = ntype;
	if (key != NULL) {
		ptr = strdup((char *) key);
		if (ptr == NULL) {
			free_json_node(node);
			fprintf(stderr, "Json Node: out of memory\n");
			return NULL;
		}
		node->key = ptr;
	}
	value_is_whitespace = whitespace_only(value);
	if (vtype == JSON_NULL && value != NULL && !value_is_whitespace) {
		double val;
		val = strtod(value, &pc);
		while (pc) {
			if (isspace(*pc))
				pc++;
			else
				break;
		}
		/* In Python3, value with leading zeroes is
		 * represented as a string, unless all zeroes (00000...)
		 * or is part of a decimal number < 1 (0.0001 ... 0.99999).
		 */
		if ((strcmp(pc, "") == 0) &&
		    ((*(char *) value != '0') || (val < 1))) {
			node->value_type = JSON_NUMERIC;
			ptr = strdup(value);
			if (ptr == NULL) {
				free_json_node(node);
				return NULL;
			}
			node->value.string = ptr;
		} else {
			node->value_type = JSON_STRING;
		}
	} else if (value_is_whitespace) {
		node->value_type = JSON_STRING;
	} else {
		node->value_type = vtype;
		if (node->value_type == JSON_INT)
			node->value.inumber = *((long int *) value);
		else if (node->value_type == JSON_FLOAT)
			node->value.fnumber = *((double *) value);
	}

	if (node->value_type == JSON_STRING) {
		if (value != NULL) {
			ptr = strdup_escape(esc_type, value);
			if (ptr == NULL) {
				free_json_node(node);
				return NULL;
			}
		}
		node->value.string = ptr;
	}
	rc = link_node(node);
	if (rc) {
		free_json_node(node);
		fprintf(stderr, "Json link: out of memory\n");
		return NULL;
	}
	return node;
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
generate_json(FILE *stream)
{
	int indent = 0;
	int prnt_comma = 0;
	int last_object_value = 0;
	int last_array_value = 0;
	int *arr_lvl = NULL;
	int curnt_arr_lvl = 0;
	JsonNode *node = NULL;
	JsonLink *link = head;

	fprintf(stream, "{");
	indent += 4;
	arr_lvl = malloc(ARRAY_NESTING_LEVEL * sizeof(int *));
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
					fprintf(stream, "%*.*s[", indent, indent, " ");
				else
					fprintf(stream, "%*.*s\"%s\":[", indent, indent, " ", node->key);
				indent += 4;
				prnt_comma = 0;
				arr_lvl[curnt_arr_lvl + 1] = indent;
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
				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s\"%s\"", indent, indent, " ", show_nonprint_chars(node->value.string));
				else
					fprintf(stream, "%*.*s\"%s\":\"%s\"", indent, indent, " ", node->key, show_nonprint_chars(node->value.string));
				prnt_comma = 1;
				break;

			case JSON_INT:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");

				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s%ld", indent, indent, " ", node->value.inumber);
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
					fprintf(stream, "%*.*s%lf", indent, indent, " ", node->value.fnumber);
				else
					fprintf(stream, "%*.*s\"%s\":%lf", indent, indent, " ", node->key, node->value.fnumber);
				prnt_comma = 1;
				break;
			case JSON_NUMERIC:
				if (prnt_comma)
					fprintf(stream, ",\n");
				else
					fprintf(stream, "\n");

				if (arr_lvl[curnt_arr_lvl] == indent)
					fprintf(stream, "%*.*s%s", indent, indent, " ", node->value.string); /*print the string but type remain same*/
				else
					fprintf(stream, "%*.*s\"%s\":%s", indent, indent, " ", node->key, node->value.string); /* print the string but type remain same*/
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
