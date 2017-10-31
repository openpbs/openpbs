#include<stdlib.h>
#include<stdio.h>
#include<string.h>

typedef enum {
	JSON_NULL,
	JSON_STRING,
	JSON_INT,
	JSON_FLOAT
}JsonValueType;

typedef enum {
	JSON_VALUE,
	JSON_OBJECT,
	JSON_OBJECT_END,
	JSON_ARRAY,
	JSON_ARRAY_END,
}JsonNodeType;

typedef struct JsonNode JsonNode;

struct JsonNode{
	JsonNodeType   node_type;
	JsonValueType  value_type;
	char *key;
	union{
		char  *string;
		long int inumber;
		double   fnumber;
	}value;
};
JsonNode* add_json_node(JsonNodeType ntype, JsonValueType vtype, char *key, void *value);
char *strdup_escape(const char *str);
int  generate_json(FILE *stream);
void free_json_node();
