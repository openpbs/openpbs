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

#ifndef	_ATTRIBUTE_H
#define	_ATTRIBUTE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"
#include "pbs_internal.h"
#include "Long.h"
#include "grunt.h"
#include "list_link.h"
#include "pbs_db.h"

#ifndef _TIME_H
#include <sys/types.h>
#endif
/*
 * This header file contains the definitions for attributes
 *
 * Other required header files:
 *	"list_link.h"
 *	"portability.h"
 *
 * Attributes are represented in one or both of two forms, external and
 * internal.  When an attribute is moving external to the server, either
 * to the network or to disk (for saving), it is represented in the
 * external form, a "svrattropl" structure.  This structure holds the
 * attribute name as a string.  If the attribute is a resource type, the
 * resource name and resource value are encoded as strings, a total of three
 * strings.  If the attribute is not a resource, then the attribute value is
 * coded into a string for a total of two strings.
 *
 * Internally, attributes exist in two separate structures.  The
 * attribute type is defined by a "definition structure" which contains
 * the name of the attribute, flags, and pointers to the functions used
 * to access the value.  This info is "hard coded".  There is one
 * "attribute definition" per (attribute name, parent object type) pair.
 *
 * The attribute value is contained in another struture which contains
 * the value and flags.  Both the attribute value and definition are in
 * arrays and share the same index.  When an
 * object is created, the attributes associated with that object
 * are created with default values.
 */

/* define the size of fields in the structures */

#define ATRDFLAG 24
#define ATRVFLAG 16

#define ATRDTYPE  4
#define ATRVTYPE  8

#define ATRPART   4

#define BUF_SIZE 512
#define RESC_USED_BUF_SIZE 2048

#define MAX_STR_INT 40

/*
 * The following structure, svrattrl is used to hold the external form of
 * attributes.
 *
 */

struct svrattrl {
	pbs_list_link	al_link;
	struct svrattrl *al_sister;  /* co-resource svrattrl		     */
	struct attropl	al_atopl;    /* name,resource,value, see pbs_ifl.h   */
	int		al_tsize;    /* size of this structure (variable)    */
	int		al_nameln;   /* len of name string (including null)  */
	int		al_rescln;   /* len of resource name string (+ null) */
	int		al_valln;    /* len of value, may contain many nulls */
	unsigned int	al_flags:ATRVFLAG;  /* copy of attribute value flags */
	int		al_refct:16; /* reference count */
	/*
	 * data follows directly after
	 */
};
typedef struct svrattrl svrattrl;

#define al_name  al_atopl.name
#define al_resc  al_atopl.resource
#define al_value al_atopl.value
#define al_op	 al_atopl.op

/*
 * The value of an attribute is contained in the following structure.
 *
 * The length field specifies the amount of memory that has been
 * malloc-ed for the value (used for at_str, at_array, and at_resrc).
 * If zero, no space has been malloc-ed.
 *
 * The union member is selected based on the value type given in the
 * flag field of the definition.
 */

struct size_value {
	u_Long        atsv_num;	/* numeric part of a size value */
	unsigned int  atsv_shift:8;	/* binary shift count, K=10, g=20 */
	unsigned int  atsv_units:1;	/* units (size in words or bytes) */
};
#define ATR_SV_BYTESZ 0			/* size is in bytes */
#define ATR_SV_WORDSZ 1			/* size is in words */

/* used for Finer Granularity Control */
struct attr_entity {
	void	*ae_tree;	/* root of tree */
	time_t	 ae_newlimittm;	/* time last limit added */
};

union attrval {
	int type_int;
	long type_long;
	char *type_str;
};
typedef union attrval attrval_t;

enum attr_type {
	ATTR_TYPE_LONG, ATTR_TYPE_INT, ATTR_TYPE_STR,
};

union attr_val {	      /* the attribute value	*/
	long		      at_long;	/* long integer */
	long long		      at_ll;	/* largest long integer */
	char		      at_char;	/* single character */
	char 		     *at_str;	/* char string  */
	struct array_strings *at_arst;	/* array of strings */
	struct size_value     at_size;	/* size value */
	pbs_list_head	      at_list;	/* list of resources,  ... */
	struct  pbsnode	     *at_jinfo; /* ptr to node's job info  */
	short		      at_short;	/* short int; node's state */
	float		      at_float;	/* floating point value */
	struct attr_entity    at_enty;	/* FGC entity tree head */
};


struct attribute {
	unsigned int at_flags:ATRVFLAG;	/* attribute flags	*/
	unsigned int at_type:ATRVTYPE;	/* type of attribute    */
	svrattrl    *at_user_encoded;	/* encoded svrattrl form for users*/
	svrattrl    *at_priv_encoded;	/* encoded svrattrl form for mgr/op*/
	union  attr_val at_val;		/* the attribute value	*/
};
typedef struct attribute attribute;

/*
 * The following structure is used to define an attribute for any parent
 * object.  The structure declares the attribute's name, value type, and
 * access methods.  This information is "built into" the server in an array
 * of attribute_def structures.  The definition occurs once for a given name.
 */

struct attribute_def {
	char *at_name;
	int	(*at_decode)(attribute *patr, char *name, char *rn, char *val);
	int	(*at_encode)(const attribute *pattr, pbs_list_head *phead, char *aname, char *rsname, int mode, svrattrl **rtnl);
	int	(*at_set)(attribute *pattr, attribute *nattr, enum batch_op);
	int	(*at_comp)(attribute *pattr, attribute *with);
	void (*at_free)(attribute *pattr);
	int	(*at_action)(attribute *pattr, void *pobject, int actmode);
	unsigned int at_flags:ATRDFLAG;	/* flags: perms, ...		*/
	unsigned int at_type:ATRDTYPE;	/* type of attribute		*/
	unsigned int at_parent:ATRPART;	/* type of parent object	*/
};
typedef struct attribute_def attribute_def;

/**
 * This structure is used by IFL verification mechanism to associate
 * specific verification routines to specific attributes. New attributes added
 * to the above attribute_def array should also be added to this array to enable
 * attribute verification.
 */
struct ecl_attribute_def {
	char	*at_name;
	unsigned int at_flags;	/* flags: perms, ...		*/
	unsigned int at_type;	/* type of attribute		*/
	/** function pointer to the datatype verification routine */
	int	(*at_verify_datatype)(struct attropl *, char **);
	/** function pointer to the value verification routine */
	int	(*at_verify_value)(int, int, int, struct attropl *, char **);
};
typedef struct ecl_attribute_def ecl_attribute_def;


/* the following is a special flag used in granting permission to create      */
/* indirect references to resources in vnodes.  This bit does not actually    */
/* appear within the at_flags field of an attribute definition.               */
#define ATR_PERM_ALLOW_INDIRECT 0x1000000

/* combination defines for permission field */

#define READ_ONLY    (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD)
#define READ_WRITE   (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_USWR | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR)
#define NO_USER_SET  (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR)
#define MGR_ONLY_SET (ATR_DFLAG_USRD | ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_MGWR)
#define PRIV_READ (ATR_DFLAG_OPRD | ATR_DFLAG_MGRD)
#define ATR_DFLAG_SSET  (ATR_DFLAG_SvWR | ATR_DFLAG_SvRD)

/* What permission needed to be settable in a hook script */
#define ATR_DFLAG_HOOK_SET (ATR_DFLAG_USWR | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR)

/* Defines for Flag field in attribute (value) 		*/

#define ATR_VFLAG_SET		0x01	/* has specifed value (is set)	*/
#define ATR_VFLAG_MODIFY	0x02	/* value has been modified	*/
#define ATR_VFLAG_DEFLT		0x04	/* value is default value	*/
#define ATR_VFLAG_MODCACHE	0x08	/* value modified since cache 	*/
#define ATR_VFLAG_INDIRECT	0x10	/* indirect pointer to resource */
#define ATR_VFLAG_TARGET	0x20	/* target of indirect resource  */
#define ATR_VFLAG_HOOK		0x40	/* value set by a hook script   */
#define ATR_VFLAG_IN_EXECVNODE_FLAG	0x80	/* resource key value pair was found in execvnode */

#define ATR_MOD_MCACHE (ATR_VFLAG_MODIFY | ATR_VFLAG_MODCACHE)
#define ATR_SET_MOD_MCACHE (ATR_VFLAG_SET | ATR_MOD_MCACHE)
#define ATR_UNSET(X) (X)->at_flags = (((X)->at_flags & ~ATR_VFLAG_SET) | ATR_MOD_MCACHE)

/* Defines for Parent Object type field in the attribute definition	*/
/* really only used for telling queue types apart			*/

#define PARENT_TYPE_JOB		 1
#define PARENT_TYPE_QUE_ALL	 2
#define PARENT_TYPE_QUE_EXC	 3
#define PARENT_TYPE_QUE_RTE	 4
#define PARENT_TYPE_QUE_PULL	 5
#define PARENT_TYPE_SERVER	 6
#define PARENT_TYPE_NODE	 7
#define PARENT_TYPE_RESV	 8
#define PARENT_TYPE_SCHED	 9

/*
 * values for the "actmode" parameter to at_action()
 */
#define ATR_ACTION_NOOP	     0
#define ATR_ACTION_NEW       1
#define ATR_ACTION_ALTER     2
#define ATR_ACTION_RECOV     3
#define ATR_ACTION_FREE      4

/*
 * values for the mode parameter to at_encode(), determines:
 *	- list separater character for encode_arst()
 *	- which resources are encoded (see attr_fn_resc.c[encode_resc]
 */
#define ATR_ENCODE_CLIENT 0	/* encode for sending to client	+ sched	*/
#define ATR_ENCODE_SVR    1	/* encode for sending to another server */
#define ATR_ENCODE_MOM    2	/* encode for sending to MOM		*/
#define ATR_ENCODE_SAVE   3	/* encode for saving to disk	        */
#define ATR_ENCODE_HOOK   4	/* encode for sending to hook 		*/
#define ATR_ENCODE_DB     5	/* encode for saving to database        */

/*
 * structure to hold array of pointers to character strings
 */

struct array_strings {
	int	as_npointers;	/* number of pointer slots in this block */
	int	as_usedptr;	/* number of used pointer slots */
	int	as_bufsize;	/* size of buffer holding strings */
	char   *as_buf;		/* address of buffer */
	char   *as_next;	/* first available byte in buffer */
	char   *as_string[1];	/* first string pointer */
};

/*
 * specific attribute value function prototypes
 */
extern struct attrl *attropl2attrl(struct attropl *from);
struct attrl *new_attrl(void);
struct attrl *dup_attrl(struct attrl *oattr);
struct attrl *dup_attrl_list(struct attrl *oattr_list);
void free_attrl(struct attrl *at);
void free_attrl_list(struct attrl *at_list);
extern void clear_attr(attribute *pattr, attribute_def *pdef);
extern int  find_attr  (void *attrdef_idx, attribute_def *attr_def, char *name);
extern int  recov_attr_fs(int fd, void *parent, void *padef_idx, attribute_def *padef,
	attribute *pattr, int limit, int unknown);
extern void free_null  (attribute *attr);
extern void free_none  (attribute *attr);
extern svrattrl *attrlist_alloc(int szname, int szresc, int szval);
extern svrattrl *attrlist_create(char *aname, char *rname, int szval);
extern void free_svrattrl(svrattrl *pal);
extern void free_attrlist(pbs_list_head *attrhead);
extern void free_svrcache(attribute *attr);
extern int  attr_atomic_set(svrattrl *plist, attribute *old,
	attribute *nattr, void *adef_idx, attribute_def *pdef, int limit,
	int unkn, int privil, int *badattr);
extern int  attr_atomic_node_set(svrattrl *plist, attribute *old,
	attribute *nattr, attribute_def *pdef, int limit,
	int unkn, int privil, int *badattr);
extern void attr_atomic_kill(attribute *temp, attribute_def *pdef, int);
extern void attr_atomic_copy(attribute *old, attribute *nattr, attribute_def *pdef, int limit);

extern int copy_svrattrl_list(pbs_list_head *from_phead, pbs_list_head *to_head);
extern int convert_attrl_to_svrattrl(struct attrl *from_list, pbs_list_head *to_head);
extern int  compare_svrattrl_list(pbs_list_head *list1, pbs_list_head *list2);
extern svrattrl *find_svrattrl_list_entry(pbs_list_head *phead, char *name,
	char *resc);
extern int add_to_svrattrl_list(pbs_list_head *phead, char *name_str, char *resc_str,
	char *val_str, unsigned int flag, char *name_prefix);
extern int add_to_svrattrl_list_sorted(pbs_list_head *phead, char *name_str, char *resc_str,
	char *val_str, unsigned int flag, char *name_prefix);
extern unsigned int get_svrattrl_flag(char *name, char *resc, char *val,
	pbs_list_head *svrattrl_list, int hook_set_flag);
extern int compare_svrattrl_list(pbs_list_head *l1, pbs_list_head *l2);

extern void free_str_array(char **);
extern char **svrattrl_to_str_array(pbs_list_head *);
extern int str_array_to_svrattrl(char **str_array, pbs_list_head *to_head, char *header_str);
extern char *str_array_to_str(char **str_array, char delimiter);
extern char *env_array_to_str(char **env_array, char delimiter);
extern char **str_to_str_array(char *str, char delimiter);
extern char *strtok_quoted(char *source, char delimiter);

extern int  decode_b  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_c  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_entlim  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_entlim_res  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_f  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_l  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_ll(attribute *patr, char *name, char *rn, char *val);
extern int  decode_size   (attribute *patr, char *name, char *rn, char *val);
extern int  decode_str   (attribute *patr, char *name, char *rn, char *val);
extern int  decode_jobname   (attribute *patr, char *name, char *rn, char *val);
extern int  decode_time  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_arst  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_arst_bs  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_resc  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_depend(attribute *patr, char *name, char *rn, char *val);
extern int  decode_hold(attribute *patr, char *name, char *rn, char *val);
extern int  decode_sandbox(attribute *patr, char *name, char *rn, char *val);
extern int  decode_project(attribute *patr, char *name, char *rn, char *val);
extern int  decode_uacl(attribute *patr, char *name, char *rn, char *val);
extern int  decode_unkn  (attribute *patr, char *name, char *rn, char *val);
extern int  decode_nodes(attribute *, char *, char *, char *);
extern int  decode_select(attribute *, char *, char *, char *);
extern int  decode_Mom_list(attribute *, char *, char *, char *);

extern int encode_b(const attribute *attr, pbs_list_head *phead, char *atname,
					char *rsname, int mode, svrattrl **rtnl);
extern int encode_c(const attribute *attr, pbs_list_head *phead, char *atname,
					char *rsname, int mode, svrattrl **rtnl);
extern int encode_entlim(const attribute *attr, pbs_list_head *phead, char *atname,
						 char *rsname, int mode, svrattrl **rtnl);
extern int encode_f(const attribute *attr, pbs_list_head *phead, char *atname,
					char *rsname, int mode, svrattrl **rtnl);
extern int encode_l(const attribute *attr, pbs_list_head *phead, char *atname,
					char *rsname, int mode, svrattrl **rtnl);
extern int encode_ll(const attribute *attr, pbs_list_head *phead, char *atname,
					 char *rsname, int mode, svrattrl **rtnl);
extern int encode_size(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);
extern int encode_str(const attribute *attr, pbs_list_head *phead, char *atname,
					  char *rsname, int mode, svrattrl **rtnl);
extern int encode_time(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);
extern int encode_arst(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);
extern int encode_arst_bs(const attribute *attr, pbs_list_head *phead, char *atname,
						  char *rsname, int mode, svrattrl **rtnl);
extern int encode_resc(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);
extern int encode_inter(const attribute *attr, pbs_list_head *phead, char *atname,
						char *rsname, int mode, svrattrl **rtnl);
extern int encode_unkn(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);
extern int encode_depend(const attribute *attr, pbs_list_head *phead, char *atname,
						 char *rsname, int mode, svrattrl **rtnl);
extern int encode_hold(const attribute *attr, pbs_list_head *phead, char *atname,
					   char *rsname, int mode, svrattrl **rtnl);

extern int set_b(attribute *attr, attribute *nattr, enum batch_op);
extern int set_c(attribute *attr, attribute *nattr, enum batch_op);
extern int set_entlim(attribute *attr, attribute *nattr, enum batch_op);
extern int set_entlim_res(attribute *attr, attribute *nattr, enum batch_op);
extern int set_f(attribute *attr, attribute *nattr, enum batch_op);
extern int set_l(attribute *attr, attribute *nattr, enum batch_op);
extern int set_ll(attribute *attr, attribute *nattr, enum batch_op);
extern int set_size  (attribute *attr, attribute *nattr, enum batch_op);
extern int set_str  (attribute *attr, attribute *nattr, enum batch_op);
extern int set_arst(attribute *attr, attribute *nattr, enum batch_op);
extern int set_arst_uniq(attribute *attr, attribute *nattr, enum batch_op);
extern int set_resc(attribute *attr, attribute *nattr, enum batch_op);
extern int set_hostacl  (attribute *attr, attribute *nattr, enum batch_op);
extern int set_uacl  (attribute *attr, attribute *nattr, enum batch_op);
extern int set_gacl  (attribute *attr, attribute *nattr, enum batch_op);
extern int set_unkn(attribute *attr, attribute *nattr, enum batch_op);
extern int set_depend(attribute *attr, attribute *nattr, enum batch_op);
extern u_Long get_kilobytes_from_attr(attribute *);
extern u_Long get_bytes_from_attr(attribute *);

extern int   comp_b(attribute *attr, attribute *with);
extern int   comp_c(attribute *attr, attribute *with);
extern int   comp_f(attribute *attr, attribute *with);
extern int   comp_l(attribute *attr, attribute *with);
extern int   comp_ll(attribute *attr, attribute *with);
extern int   comp_size  (attribute *attr, attribute *with);
extern void  from_size  (const struct size_value *, char *);
extern int   comp_str  (attribute *attr, attribute *with);
extern int   comp_arst(attribute *attr, attribute *with);
extern int   comp_resc(attribute *attr, attribute *with);
extern int   comp_unkn(attribute *attr, attribute *with);
extern int   comp_depend(attribute *attr, attribute *with);
extern int   comp_hold(attribute *attr, attribute *with);

extern int action_depend(attribute *attr, void *pobj, int mode);
extern int check_no_entlim(attribute *attr, void *pobj, int mode);
extern int action_entlim_chk(attribute *attr, void *pobj, int mode);
extern int action_entlim_ct  (attribute *attr, void *pobj, int mode);
extern int action_entlim_res(attribute *attr, void *pobj, int mode);
extern int at_non_zero_time(attribute *attr, void *pobj, int mode);
extern int set_log_events(attribute *pattr, void *pobject, int actmode);

extern void free_str  (attribute *attr);
extern void free_arst(attribute *attr);
extern void free_entlim(attribute *attr);
extern void free_resc(attribute *attr);
extern void free_depend(attribute *attr);
extern void free_unkn(attribute *attr);
extern int   parse_equal_string(char  *start, char **name, char **value);
extern char *parse_comma_string(char *start);
extern char *return_external_value(char *name, char *val);
extern char *return_internal_value(char *name, char *val);

#define NULL_FUNC_CMP (int (*)(attribute *, attribute *))0
#define NULL_FUNC_RESC (int (*)(resource *, attribute *, void *, int, int))0
#define NULL_FUNC (int (*)(attribute *, void *, int))0
#define NULL_VERIFY_DATATYPE_FUNC (int (*)(struct attropl *, char **))0
#define NULL_VERIFY_VALUE_FUNC (int (*)(int, int, int, struct attropl *, char **))0

/* other associated funtions */

extern int   acl_check(attribute *, char *canidate, int type);
extern int   check_duplicates(struct array_strings *strarr);

extern char *arst_string(char *str, attribute *pattr);
extern void  attrl_fixlink(pbs_list_head *svrattrl);
extern int   save_attr_fs(attribute_def *, attribute *, int);

extern int      encode_state(const attribute *, pbs_list_head *, char *,
	char *, int, svrattrl **rtnl);
extern int      encode_props(const attribute*, pbs_list_head*, char*,
	char*, int, svrattrl **rtnl);
extern int      encode_jobs  (const attribute*, pbs_list_head*, char*,
	char*, int, svrattrl **rtnl);
extern int      encode_resvs(const attribute*, pbs_list_head*, char*,
	char*, int, svrattrl **rtnl);
extern int      encode_ntype(const attribute*, pbs_list_head*, char*,
	char*, int, svrattrl **rtnl);
extern int      encode_sharing(const attribute*, pbs_list_head*, char*,
	char*, int, svrattrl **rtnl);
extern int      decode_state(attribute*, char*, char*, char*);
extern int      decode_props(attribute*, char*, char*, char*);
extern int      decode_ntype(attribute*, char*, char*, char*);
extern int	decode_sharing(attribute*, char*, char*, char*);
extern int      decode_null  (attribute*, char*, char*, char*);
extern int      comp_null(attribute*, attribute*);
extern int      count_substrings(char*, int*);
extern int      set_resources_min_max(attribute *, attribute*, enum batch_op);
extern int      set_node_state  (attribute*, attribute*, enum batch_op);
extern int      set_node_ntype  (attribute*, attribute*, enum batch_op);
extern int      set_node_props  (attribute*, attribute*, enum batch_op);
extern int      set_null	(attribute*, attribute*, enum batch_op);
extern int      node_state      (attribute*, void*, int);
extern int      node_np_action  (attribute*, void*, int);
extern int      node_ntype(attribute*, void*, int);
extern int      node_prop_list(attribute*, void*, int);
extern int      node_comment(attribute *, void *, int);
extern int	is_true_or_false(char *val);
extern void unset_entlim_resc(attribute *, char *);
extern int      action_node_partition(attribute *, void *, int);

/* Action routines for OS provisioning */
extern int	node_prov_enable_action(attribute *, void *, int);
extern int	node_current_aoe_action(attribute *, void *, int);
extern int	svr_max_conc_prov_action(attribute *, void *, int);

/* Manager functions */
extern void	mgr_log_attr(char *, struct svrattrl *, int, char *, char *);
extern int	mgr_set_attr(attribute *, void *, attribute_def *, int, svrattrl *, int, int *, void *, int);
/* Extern functions (at_action) called  from job_attr_def*/

extern int job_set_wait(attribute *, void *, int);
extern int setup_arrayjob_attrs(attribute *pattr, void *pobject, int actmode);
extern int fixup_arrayindicies  (attribute *pattr, void *pobject, int actmode);
extern int action_resc_job(attribute *pattr, void *pobject, int actmode);
extern int ck_chkpnt(attribute *pattr, void *pobject, int actmode);
extern int keepfiles_action(attribute *pattr, void *pobject, int actmode);
extern int removefiles_action(attribute *pattr, void *pobject, int actmode);
/*extern int depend_on_que(attribute *, void *, int);*/
extern int comp_chkpnt(attribute *, attribute *);
extern int alter_eligibletime(attribute *, void *, int);
extern int action_max_run_subjobs(attribute *, void *, int);
/* Extern functions from svr_attr_def */
extern int manager_oper_chk(attribute *pattr, void *pobject, int actmode);
extern int poke_scheduler(attribute *pattr, void *pobject, int actmode);
extern int cred_name_okay(attribute *pattr, void *pobject, int actmode);
extern int action_reserve_retry_time(attribute *pattr, void *pobject, int actmode);
extern int action_reserve_retry_init(attribute *pattr, void *pobject, int actmode);
extern int set_rpp_retry(attribute *pattr, void *pobject, int actmode);
extern int set_node_fail_requeue(attribute *pattr, void *pobject, int actmode);
extern int set_rpp_highwater(attribute *pattr, void *pobject, int actmode);
extern int set_license_location(attribute *pattr, void *pobject, int actmode);
extern int set_license_min(attribute *pattr,  void *pobject,  int actmode);
extern int set_license_max(attribute *pattr,  void *pobject,  int actmode);
extern int set_license_linger(attribute *pattr,  void *pobject,  int actmode);
extern int set_job_history_enable(attribute *pattr,  void *pobject,  int actmode);
extern int set_job_history_duration(attribute *pattr,  void *pobject,  int actmode);
extern int default_queue_chk(attribute *pattr,  void *pobject,  int actmode);
extern int force_qsub_daemons_update_action(attribute *pattr,  void *pobject,  int actmode);
extern int action_resc_dflt_svr(attribute *pattr, void *pobj, int actmode);
extern int action_jobscript_max_size(attribute *pattr, void *pobj, int actmode);
extern int action_check_res_to_release(attribute *pattr, void *pobj, int actmode);
extern int set_max_job_sequence_id(attribute *pattr, void *pobj, int actmode);
extern int set_cred_renew_enable(attribute *pattr, void *pobject, int actmode);
extern int set_cred_renew_period(attribute *pattr, void *pobject, int actmode);
extern int set_cred_renew_cache_period(attribute *pattr, void *pobject, int actmode);


/* Extern functions from sched_attr_def*/
extern int action_opt_bf_fuzzy(attribute *pattr, void *pobj, int actmode);

extern int encode_svrstate(const attribute *pattr,  pbs_list_head *phead,  char *aname,
	char *rsname,  int mode,  svrattrl **rtnl);

extern int decode_rcost(attribute *patr,  char *name,  char *rn,  char *val);
extern int encode_rcost(const attribute *attr,  pbs_list_head *phead,  char *atname,
	char *rsname,  int mode,  svrattrl **rtnl);
extern int set_rcost(attribute *attr,  attribute *nattr,  enum batch_op);
extern void free_rcost(attribute *attr);
extern int decode_null(attribute *patr,  char *name,  char *rn,  char *val);
extern int set_null(attribute *patr,  attribute *nattr,  enum batch_op op);
extern int eligibletime_action(attribute *pattr,  void *pobject,  int actmode);
extern int decode_formula(attribute *patr,  char *name,  char *rn,  char *val);
extern int action_backfill_depth(attribute *pattr,  void *pobj,  int actmode);
extern int action_est_start_time_freq(attribute *pattr,  void *pobj,  int actmode);
extern int action_sched_iteration(attribute *pattr, void *pobj, int actmode);
extern int action_sched_priv(attribute *pattr, void *pobj, int actmode);
extern int action_sched_log(attribute *pattr, void *pobj, int actmode);
extern int action_sched_user(attribute *pattr, void *pobj, int actmode);
extern int action_sched_host(attribute *pattr, void *pobj, int actmode);
extern int action_sched_partition(attribute *pattr, void *pobj, int actmode);
extern int action_sched_preempt_order(attribute *pattr, void *pobj, int actmode);
extern int action_sched_preempt_common(attribute *pattr, void *pobj, int actmode);
extern int action_job_run_wait(attribute *pattr, void *pobj, int actmode);
extern int action_throughput_mode(attribute *pattr, void *pobj, int actmode);

/* Extern functions from queue_attr_def */
extern int decode_null(attribute *patr, char *name, char *rn, char *val);
extern int set_null(attribute *patr, attribute *nattr, enum batch_op op);
extern int cred_name_okay(attribute *pattr, void *pobject, int actmode);
extern int action_resc_dflt_queue(attribute *pattr, void *pobj, int actmode);
extern int action_queue_partition(attribute *pattr, void *pobj, int actmode);
/* Extern functions (at_action) called  from resv_attr_def */
extern int action_resc_resv(attribute *pattr, void *pobject, int actmode);


/* Functions used to save and recover the attributes from the database */
extern int encode_single_attr_db(attribute_def *padef, attribute *pattr, pbs_db_attr_list_t *db_attr_list);
extern int encode_attr_db(attribute_def *padef, attribute *pattr, int numattr,  pbs_db_attr_list_t *db_attr_list, int all);
extern int decode_attr_db(void *parent, pbs_list_head *attr_list,
	void *padef_idx, attribute_def *padef, attribute *pattr, int limit, int unknown);

extern int is_attr(int, char *, int);

extern int set_attr(struct attrl **attrib, const char *attrib_name, const char *attrib_value);
extern int set_attr_resc(struct attrl **attrib, const char *attrib_name, const char *attrib_resc, const char *attrib_value);

extern svrattrl *make_attr(char *attr_name, char *attr_resc, char *attr_value, int attr_flags);
extern void *cr_attrdef_idx(attribute_def *adef, int limit);

/* Attr setters */
int set_attr_generic(attribute *pattr, attribute_def *pdef, char *value, char *rescn, enum batch_op op);
int set_attr_with_attr(attribute_def *pdef, attribute *oattr, attribute *nattr, enum batch_op op);
void set_attr_l(attribute *pattr, long value, enum batch_op op);
void set_attr_ll(attribute *pattr, long long value, enum batch_op op);
void set_attr_c(attribute *pattr, char value, enum batch_op op);
void set_attr_b(attribute *pattr, long val, enum batch_op op);
void set_attr_short(attribute *pattr, short value, enum batch_op op);
void mark_attr_not_set(attribute *attr);
void mark_attr_set(attribute *attr);
void post_attr_set(attribute *attr);

/* Attr getters */
char get_attr_c(const attribute *pattr);
long get_attr_l(const attribute *pattr);
long long get_attr_ll(const attribute *pattr);
char *get_attr_str(const attribute *pattr);
struct array_strings *get_attr_arst(const attribute *pattr);
int is_attr_set(const attribute *pattr);
attribute *_get_attr_by_idx(attribute *list, int attr_idx);
pbs_list_head get_attr_list(const attribute *pattr);
void free_attr(attribute_def *attr_def, attribute *pattr, int attr_idx);

/* "type" to pass to acl_check() */
#define ACL_Host  1
#define ACL_User  2
#define ACL_Group 3

#ifdef	__cplusplus
}
#endif
#endif 	/* _ATTRIBUTE_H */
