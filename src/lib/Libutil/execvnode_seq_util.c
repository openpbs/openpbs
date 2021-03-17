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


/**
 * @file	execvnode_seq_util.c
 * @brief
 *  Utility functions to condense and unroll a sequence of execvnodes that are
 *  returned by the scheduler as confirmation of a standing reservation.
 *  The functionality is to condense into a human-readable string, the execvnodes
 *  of each occurrence of a standing reservation, and be able to retrieve each
 *  occurrence by occurrence index of an array.
 *
 *  Example usage (also refer to the debug function int test_execvnode_seq
 *  for a practical example):
 *
 *  Assume str points to some string.
 *  char *condensed_str;
 *  char **unrolled_str;
 *  char **tofree;
 *
 *  condensed_str = condense_execvnode_seq(str);
 *  unrolled_str = unroll_execvnode_seq(condensed_str, &tofree);
 *  ...access an arbitrary, say 2nd occurrence, index via unrolled_str[1]
 *  free_execvnode_seq(tofree);
 */
#include <pbs_config.h>   /* the master config generated by configure */

#include <libutil.h>
#include <log.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>


/* Initialize a dictionary structure */
static dictionary *new_dictionary();

/* Initialize a new word with the given string value */
static struct word *new_word(char *);

/* Initialize a new map for a given value */
static struct map *new_map(int);

/* Map a sequence of words to a list of indices by which
 * they are represented in the passed string str.
 */
static int direct_map(dictionary *, char *);

/* find a word in a dictionary */
static struct word *find_word(dictionary *, char *);

/* Append word to dictionary */
static int append_to_dict(dictionary *, char *, int);

/* Append the index of a word in a string to the mapping of the word */
static int append_to_word(dictionary *, struct word *, int);

/* Create a string out of all words in a dictionary and their corresponding mapped indices */
static char *dict_to_str(dictionary *);

/* Free memory allocated to dictionary */
static void free_dict(dictionary *);

/* Free memory allocated to a word and its mapping */
static void free_word(struct word *);


/**
 * @brief
 *	Initialize a dictionary structure.
 *
 * @return	structure handle
 * @retval	a new dictionary structure 	success
 * @retval	NULL 				if unable to allocate memory.
 *
 */
static dictionary *
new_dictionary()
{
	dictionary *dict;
	if ((dict = (dictionary *) malloc(sizeof(dictionary))) == NULL) {
		DBPRT(("new_dictionary: %s\n", MALLOC_ERR_MSG))
		return NULL;
	}
	dict->first = NULL;
	dict->last = NULL;
	dict->count = 0;
	dict->length = 0;
	dict->max_idx = 0;

	return dict;
}

/**
 * @brief
 * 	Initialize a new word with the given string value.
 *
 * @param[in] str - The string value associated to the new word
 *
 * @return 	structure handle
 * @retval	a new word structure 	succes
 * @retval	NULL 			if unable to allocate memory
 *
 */
static struct word *new_word(char *str)
{
	struct word *nw;

	if (str == NULL)
		return NULL;

	if ((nw = malloc(sizeof(struct word)))== NULL) {
		DBPRT(("new_word: %s\n", MALLOC_ERR_MSG))
		return NULL;
	}
	if ((nw->name = strdup(str)) == NULL) {
		free(nw);
		DBPRT(("new_word: %s\n", MALLOC_ERR_MSG));
		return NULL;
	}
	nw->next = NULL;
	nw->map = NULL;
	nw->count = 0;

	return nw;
}

/**
 * @brief
 * 	Initialize a new map for a given value. A map is the associated value of a
 * 	word, and in practice is the index where the word appears in the sequence.
 *
 * @param[in] val - The integer value corresponding to the index  of a word.
 *
 * @return 	structure handle
 * @retval	A new map structure 	success
 * @retval	NULL 			if unable to allocate memory.
 *
 */
static struct map *new_map(int val)
{
	struct map *m;

	if (val < 0)
		return NULL;

	if ((m = malloc(sizeof(struct map)))== NULL) {
		DBPRT(("new_map: %s\n", MALLOC_ERR_MSG))
		return NULL;
	}
	m->val = val;
	m->next = NULL;

	return m;
}

/**
 * @brief
 * 	Map a sequence of words to a list of indices by which
 * 	they are represented in the passed string str.
 *
 * @par	Given a sequence of words (the execvnodes), this function\n
 * 	1) Looks for the word in the dictionary\n
 * 	2) If the word is found, the index where it appears in the string is added
 *    	as a mapping of the word\n
 * 	3) If the word is not found in the dictionary, it is added.\n
 *
 * @param[out] dict - The dictionary considered.
 * @param[in] str - The string to check against in the dictionary.
 *
 * @par	Note:
 *	If the string exists in the dictionary, its index is appended
 * 	to the word entry. Otherwise it is added as a new word to the dictionary
 *
 * @return int
 * @retval 1 error
 * @retval 0 success
 */
static int
direct_map(dictionary *dict, char *str)
{
	struct word *w;
	char *str_tok;
	char *str_copy;
	int i = 0;

	if (dict == NULL || str == NULL)
		return 1;

	if ((str_copy = strdup(str)) == NULL) {
		DBPRT(("new_word: %s\n", MALLOC_ERR_MSG));
		return 1;
	}

	str_tok = strtok(str_copy, TOKEN_SEPARATOR);
	while (str_tok != NULL) {
		w = (struct word *)find_word(dict, str_tok);
		if (w == NULL) {
			if (append_to_dict(dict, str_tok, i)) {
				free(str_copy);
				return 1;
			}
		} else
			if (append_to_word(dict, w, i)) {
				free(str_copy);
				return 1;
			}
		i++;
		str_tok = strtok(NULL, TOKEN_SEPARATOR);
	}
	dict->max_idx = i;
	free(str_copy);
	return 0;
}

/**
 * @brief
 * 	Find a word in a dictionary.
 *
 * @param[in] dict - The dictionary in which to search
 * @param[in] str - The string to be found.
 *
 * @return	structure handle
 * @retval	a Word structure 	if the word is found,
 * @retval	NULL.			if not found
 *
 */
static struct word *find_word(dictionary *dict, char *str)
{
	struct word *cur;

	if (dict == NULL || str == NULL)
		return NULL;

	if (dict->count == 0)
		return NULL;

	for (cur = dict->first; cur!=NULL; cur = cur->next) {
		if (!strcmp(cur->name, str))
			return cur;
	}

	return NULL;
}

/**
 * @brief
 * 	Append word to dictionary.
 *
 * @param[in] dict - The dictionary considered.
 * @param[in] str - The string representation of the word to append
 * @param[in] val - The index at which the string resides in the original string.
 * 
 * @return int
 * @retval 1 error
 * @retval 0 success
 *
 */
static int
append_to_dict(dictionary *dict, char *str, int val)
{
	struct word *nw;
	struct word *tmp;

	if (dict == NULL || str == NULL || val < 0)
		return 1;

	nw = new_word(str);

	if (nw == NULL)
		return 1;

	if (dict->first == NULL) {
		dict->first = nw;
		dict->last = nw;
	}
	else {
		tmp = dict->first;
		dict->first = nw;
		nw->next = tmp;
	}
	nw->map = new_map(val);

	if (nw->map == NULL)
		return 1;

	nw->count++;
	dict->length += strlen(str);
	dict->length += MAX_INT_LENGTH;
	dict->count++;

	return 0;
}

/**
 * @brief
 * 	Append the index of a word in a string to the mapping of the word
 *
 * @param[in] dict - The dictionary considered
 * @param[in] w - The word to append to
 * @param[in] val - The index value to append to the word
 * 
 * @return int
 * @retval 1 error
 * @retval 0 success
 *
 */
static int
append_to_word(dictionary *dict, struct word *w, int val)
{

	struct map *m, *tmp;

	if (dict == NULL || w == NULL || val < 0)
		return 1;

	m = w->map;
	tmp = m;
	if (m == NULL) {
		m = new_map(val);

		if (m == NULL)
			return 1;

		w->map = m;
	}
	else {
		while (tmp->next!=NULL) {
			tmp = tmp->next;
		}
		tmp->next = new_map(val);

		if (tmp->next == NULL) 
			return 1;
	}
	w->count++;
	/* MAX_INT_LENGTH is the length of a string representation of an index */
	dict->length += MAX_INT_LENGTH;

	return 0;
}

/**
 * @brief
 *	Convert a TOKEN_SEPARATOR delimited string into a condensed dictionary representation.
 *
 * @param[in] str - The string to condense into indexed arrays or repeating occurrences.
 *
 * @return 	string
 * @retval	a Condensed reprsentation of the string in which all recurring tokens are
 * 		represented by an indexed array. For example the string:
 *		(tic)~(tac)~(toe)~(tic)~(tic)~(tic) is condensed to (tic){0,3-5} (tac){1} (toe){2}
 *		( the condensed representation of the sequence of tokens)
 * @retval	NULL			error
 *
 */
char *
condense_execvnode_seq(const char *str)
{
	dictionary *dict;
	char *s_tmp;
	char *cp;

	if (str == NULL)
		return NULL;

	dict = new_dictionary();

	if (dict == NULL)
		return NULL;

	s_tmp = strdup(str);
	if (s_tmp == NULL) {
		DBPRT(("condense_execvnode_seq: %s\n", MALLOC_ERR_MSG));
		free(dict);
		return NULL;
	}
	if (direct_map(dict, s_tmp)) {
		free(s_tmp);
		free_dict(dict);
		return NULL;
	}
	cp = dict_to_str(dict);
	/* Free up all memory allocated */
	free_dict(dict);
	free(s_tmp);

	return cp;
}

/**
 * @brief
 * 	Unroll a condensed string into an indexed array of pointers to words (strings).
 * 	This function takes as input a string of the form:
 * 	<count>COUNT_TOK<vnode1><range1><vnode2><range2>...
 * The tokens that are being used are:
 * 1) COUNT_TOK to separate the number of occurrences from the sequence of execvnodes
 * 2) WORD_TOK WORD_MAP_TOK used to enclose the range of indices for each execvnode
 *
 * and returns an array of pointers of length count, for which each index of
 * the array points to either vnode1, vnode2,etc based on the values in
 * range1, range2, etc respectively.
 * The idea is that instead of recreating the original long sequence of vnodes, only
 * unique vnode strings are created and is referred to as an array of pointers.
 *
 * Because of this special handling, the pointers to the unique vnodes has to be
 * visible at return time so that it can be properly free'd. The pointers to these
 * unique vnodes are kept in the tofree parameter.
 *
 * @param[in] str - The string to unroll
 * @param[in] tofree - A pointer to a block of memory to deallocate
 *
 * @return A pointer to the unrolled string
 *
 */
char **
unroll_execvnode_seq(char *str, char ***tofree)
{
	char *word;
	char *map;
	char *range;
	char *nm1 = NULL;
	char *nm2 = NULL;
	char *nm3 = NULL;
	int max_idx;
	int first, last;
	char *tmp;
	int i;
	int j = 0;

	char **rev_dict;

	if (str == NULL) {
		*tofree = NULL;
		return NULL;
	}

	/* Tokenize the number of occurrences part */
	word = string_token(str, COUNT_TOK, &nm1);

	if (word == NULL)
		return NULL;
	/* The number of occurrences */
	max_idx = atoi(word);
	/* Allocate memory for the returning variable rev_dict which
	 * will be an array of pointers of length, the number of occurrences,
	 * for which each index corresponds to the execvnode associated to that occurrence */
	if ((rev_dict = (char **) malloc((max_idx + 1) * sizeof(char *))) == NULL) {
		DBPRT(("unroll_execvnode_seq: %s\n", MALLOC_ERR_MSG));
		return NULL;
	}
	/* Allocate memory to the block of memory that contains only Unique execvnodes
	 * that will need to be freed once the string is not anymore needed.
	 * This block of memory is made as large as rev_dict in the worst case where
	 * all execvnodes are distinct but is resized later for the average case
	 * where most execvnodes after a certain date will be identical */
	if ((*tofree = (char **) malloc((max_idx + 1) * sizeof(char *))) == NULL) {
		free(rev_dict);
		return NULL;
	}
	/* Tokenize the <vnode>{range} part */
	word = string_token(NULL, WORD_TOK, &nm1);
	while (word != NULL) {
		if ((tmp = strdup(word)) == NULL) {
			free(*tofree);
			free(rev_dict);
			DBPRT(("unroll_execvnode_seq: %s\n", MALLOC_ERR_MSG));
			return NULL;
		}
		/* Tokenize to isolate <vnode> in <vnode>{range} */
		word = string_token(NULL, WORD_MAP_TOK, &nm1);
		if (word == NULL) {
			free(tmp);
			break;
		}
		/* Tokenize to isolate {range} */
		map = string_token(word, MAP_TOK, &nm2);
		while (map != NULL) {
			/* Tokenize the range which can be of the form 0-10 or 0,3,5 */
			range = string_token(map, RANGE_TOK, &nm3);
			if (range != NULL) {
				first = atoi(range);
				last = first;
				/* Each index in range is parsed */
				range = string_token(NULL, RANGE_TOK, &nm3);
				if (range != NULL)
					last = atoi(range);
				/* Append the <vnode> token to the pointer array
				 * for each index indicated by range */
				for (i = first; i <= last; i++)
					rev_dict[i] = (char *) tmp;
			}
			else {
				rev_dict[atoi(map)] = (char *) tmp;
			}
			map = string_token(NULL, MAP_TOK, &nm2);
		}
		/* Append each unique <vnode> to the block of memory to free */
		if (j < max_idx) {
			(*tofree)[j] = tmp;
			j++;
		}
		else {
			j = max_idx;
			break;
		}
		word = string_token(NULL, WORD_TOK, &nm1);
	}

	rev_dict[max_idx] = NULL;

	(*tofree)[j] = NULL;

	return rev_dict;
}

/**
 * @brief
 * 	Get the total number of indices represented in the condensed string
 * 	which corresponds to the total number of occurrences in the execvnode string
 *
 * @param[in] str - Either a condensed execvnode_seq or a single execvnode
 * 		The format expected is in the form of:
 * 		execvnode_seq: N#(execvnode){0-N-1} e.g. 10:(mars:ncpus=1){0-9}
 * 		Single execvnode: (mars:ncpus=1)
 *
 * @return	int
 * @retval	The number of occurrences. If the first token is
 * @retval	0			   NULL,
 *
 */
int
get_execvnodes_count(char *str)
{
	int count;
	char *word;
	char *str_copy;

	if (str == NULL)
		return 0;

	if (str[0] == '(')
		return 1;

	if ((str_copy = strdup(str)) == NULL)
		return 0;
	word = strtok(str_copy, COUNT_TOK);

	if (word == NULL)
		return 0;

	count = atoi(word);
	free(str_copy);

	return count;
}

/**
 * @brief
 *	Translate a dictionary into a string
 *      Walks the entire dictionary, word by word, and for each word creates a
 *      string representation by concatenating words together.
 *      The result is a string of tokens separated by the WORD_TOK character.
 *      The format of the returned string is:
 *
 *      <num_occurrences>COUNT_TOK<vnode1>WORD_TOK<range>WORD_MAP_TOK<vnode2>
 *      WORD_TOK...COUNT_TOK, WORD_TOK and WORD_MAP_TOK are defined in the
 *      header file.
 *
 * @param[in]   dict - the dictionary considered
 *
 * @return char* The concatenation of all words in the dictionary.
 * @retval SUCCESS The concatenation of all words in the dictionary
 * @retval NULL	Memory allocation for returned string fails
 */
static char *
dict_to_str(dictionary *dict)
{
	char *condensed;
	char *tmp;
	char buf[1024];
	struct word *w;
	struct map *m;
	int prev = 0, first = 0, cur;
	int begin_range=1;

	if (dict == NULL)
		return NULL;

	w = dict->first;

	if (w == NULL)
		return NULL;

	/* Allocate  sufficient memory for the string to be returned
	 * this string will be resized at the end of the function.*/
	if ((condensed=malloc((dict->length+1)* sizeof(char)))==NULL) {
		DBPRT(("dict_to_str: %s\n", MALLOC_ERR_MSG));
		return NULL;
	}

	/* Write the number of occurrences followed by COUNT_TOK */
	sprintf(condensed, "%d%s", dict->max_idx, COUNT_TOK);

	m = w->map;

	while (w != NULL) {
		tmp = strdup(w->name);
		if (tmp == NULL) {
			break;
		}
		/* Concatenate the vnode followed by the separator
		 * to start the range */
		(void) strcat(condensed, tmp);
		(void) strcat(condensed, WORD_TOK);

		while (m != NULL) {
			cur = m->val;
			/* If current value (and not first scan) is increment
			 *  of previous then keep reading */
			if (!begin_range && cur == prev+1) {
				m = m->next;
				prev = cur;
				continue;
			}

			if (begin_range) {
				first = cur;
				begin_range=0;
				m = m->next;
			}
			else {
				/* Concatentate the range */
				if (first==prev)
					sprintf(buf, "%d%s", first, MAP_TOK);
				else
					sprintf(buf, "%d%s%d, ", first, RANGE_TOK, prev);
				(void) strcat(condensed, buf);
				begin_range=1;
			}

			prev = cur;
		}
		if (first==prev)
			sprintf(buf, "%d", first);
		else
			sprintf(buf, "%d%s%d", first, RANGE_TOK, prev);
		(void) strcat(condensed, buf);

		begin_range=1;

		w = w->next;
		if (w != NULL)
			m = w->map;
		/* Concatenate the closing separator of the range */
		strcat(condensed, WORD_MAP_TOK);

		free(tmp);
	}
	/* condensed was malloc'd dict->length which was an "overestimate" of the actual needed memory
	 * resize to what's actually been used */
	tmp = realloc(condensed, (strlen(condensed)+1)*sizeof(char));
	if (tmp == NULL) {
		free(condensed);
		DBPRT(("dict_to_str: %s\n", MALLOC_ERR_MSG));
		return NULL;
	}
	else
		condensed = tmp;

	condensed[strlen(condensed)]='\0';

	return condensed;
}

/**
 * @brief
 * 	Free up all memory allocated to dictionary
 *
 * @param[in] dict - The dictionary considered
 *
 */
static void
free_dict(dictionary *dict)
{
	struct word *w;
	struct word *w_tmp;

	if (dict == NULL)
		return;

	w = dict->first;

	if (w == NULL) {
		free(dict);
		return;
	}

	while (w->next!=NULL) {
		w_tmp = w->next;
		free_word(w);
		w = w_tmp;
	}
	free_word(w);
	free(dict);
}

/**
 * @brief
 * 	Free memory allocated to a word and its mapping
 *
 * @param[in] w - The word to deallocate memory for
 *
 */
static void
free_word(struct word *w)
{
	struct map *m;
	struct map *m_tmp;

	if (w == NULL)
		return;

	m = w->map;

	if (m == NULL)
		return;

	while (m->next != NULL) {
		m_tmp = m->next;
		free(m);
		m = m_tmp;
	}
	free(m);
	free(w->name);
	free(w);
}

/**
 * @brief
 * 	Free the memory allocated to an unrolled execvnode sequence.
 *  	The execvnode sequence is an array of pointers to the unique
 *  	execvnode strings.
 *
 * @par	Note that this function is passed the block of memory allocated
 *  	from unroll_execvnode_seq's argument and NOT its return value.
 *  	The block of memory that is freed here is only the unique execvnodes
 *  	that had been allocated and not the array of pointers to these execvnodes.
 *
 * @param[in] ptr - Pointer to a block of memory to free
 *
 */
void
free_execvnode_seq(char **ptr)
{
	int i;

	if (ptr == NULL)
		return;

	for (i=0; ptr[i]!=NULL; i++)
		free(ptr[i]);
	free(ptr);
}


#ifdef DEBUG
/**
 * @brief
 * 	function for Unit test
 *
 */
void
test_execvnode_seq()
{
	int i;
	int num;
	char *str;
	char *condensed_execvnodes;
	char **tofree;
	char **unroll_execvnodes;

	/* using all possible legal vnode characters separated by TOKEN_SEPARATOR */
	str = "(a-_^.#[0]:n=1)~(b@m.[1],c:m=2)~(a-_^.#[0]:n=1)~(b@m.[1],c:m=2)";
	printf("Original string: %s\n", str);
	condensed_execvnodes = condense_execvnode_seq(str);
	num = get_execvnodes_count(condensed_execvnodes);
	printf("condensed string: %s\n", condensed_execvnodes);
	unroll_execvnodes = unroll_execvnode_seq(condensed_execvnodes, &tofree);
	printf("Decompressed string:\n");
	for (i = 0; i < num; i++)
		printf("%s ", unroll_execvnodes[i]);
	printf("\n");
	free(unroll_execvnodes);
	free_execvnode_seq(tofree);
	free(condensed_execvnodes);
}
#endif
