/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
 *
 */
#ifndef	_RESOURCE_H
#define	_RESOURCE_H
#ifdef	__cplusplus
extern "C" {
#endif
#include "attribute.h"
#include "list_link.h"


/*
 * This header file contains the definitions for resources.
 *
 * Other required header files:
 *	"portability.h"
 *	"attribute.h"
 *	"list_link.h"
 *
 * Resources are "a special case" of attributes.  Resources use similiar
 * structures as attributes.  Certain types, type related functions,
 * and flags may differ between the two.
 *
 * Within the resource structure, the value is contained in an attribute
 * substructure, this is done so the various attribute decode and encode
 * routines can be "reused".
 *
 * For any server, queue or job attribute which is a set of resources,
 * the attribute points to an list  of "resource" structures.
 * The value of the resource is contained in these structures.
 *
 * Unlike "attributes" which are typically identical between servers
 * within an administrative domain,  resources vary between systems.
 * Hence, the resource instance has a pointer to the resource definition
 * rather than depending on a predefined index.
 */

#define RESOURCE_UNKNOWN "|unknown|"

typedef enum resdef_op {
	RESDEF_CREATE,
	RESDEF_UPDATE,
	RESDEF_DELETE
} resdef_op_t;

typedef struct resource {
	pbs_list_link 	     rs_link;	/* link to other resources in list */
	struct resource_def *rs_defin;	/* pointer to definition entry */
	attribute	     rs_value;	/* attribute struct holding value */
} resource;

typedef struct resource_def {
	char   *rs_name;
	int   (*rs_decode)(attribute *prsc, char *name, char *rn, char *val);
	int   (*rs_encode)(attribute *prsv, pbs_list_head *phead, char *atname,
		char *rsname, int mode, svrattrl **rtnl);
	int   (*rs_set)(attribute *old, attribute *new, enum batch_op op);
	int   (*rs_comp)(attribute *prsc, attribute *with);
	void  (*rs_free)(attribute *prsc);
	int   (*rs_action)(resource *presc, attribute *pat, void *pobj,
		int type, int actmode);
	unsigned int rs_flags:ATRDFLAG;	/* flags: R/O, ..., see attribute.h */
	unsigned int rs_type:ATRDTYPE;	/* type of resource,see attribute.h */
	unsigned int rs_entlimflg;	/* tracking entity limits for this  */
	struct resource_def *rs_next;
} resource_def;

struct resc_sum {
	struct resource_def *rs_def;	/* ptr to this resources's def   */
	struct resource     *rs_prs;	/* ptr resource in Resource_List */
	attribute            rs_attr;	/* used for summation of values  */
	int		     rs_set;	/* set if value is set here      */
};

/* following used for Entity Limits for Finer Granularity Control */
typedef struct  svr_entlim_leaf {
	resource_def	*slf_rescd;
	attribute	 slf_limit;
	attribute	 slf_sum;
} svr_entlim_leaf_t;

extern struct resc_sum *svr_resc_sum;
extern resource_def *svr_resc_def;	/* the resource definition array */
extern int	     svr_resc_size;	/* size (num elements) in above  */
extern int	     svr_resc_unk;	/* index to "unknown" resource   */

extern resource     *add_resource_entry(attribute *, resource_def *);
extern resource_def *find_resc_def(resource_def *, char *, int);
extern resource     *find_resc_entry(attribute *, resource_def *);
extern int          is_builtin(resource_def *rscdef);
extern int           update_resource_def_file(char *name, resdef_op_t op, int type, int perms);
extern int           add_resource_def(char *name, int type, int perms);
extern void          restart_python_interpreter(const char *);
extern long long     to_kbsize(char *val);
extern int   alloc_svrleaf(char *resc_name, svr_entlim_leaf_t **pplf);
extern int  parse_resc_type(char *val, int *resc_type_p);
extern int  parse_resc_flags(char *val, int *flag_ir_p, int *resc_flag_p);
extern int verify_resc_name(char *name);
extern int verify_resc_type_and_flags(int resc_type, int *pflag_ir, int *presc_flag, char *rescname, char *buf, int buflen, int autocorrect);
extern void update_resc_sum(void);

/* Defines for entity limit tracking */
#define PBS_ENTLIM_NOLIMIT  0	/* No entity limit has been set for this resc */
#define PBS_ENTLIM_LIMITSET 1	/* this set in rs_entlim if limit exists */

/*
 * struct for providing mapping between resource type name or a
 * resource type value and the corresponding functions.
 * See lib/Libattr/resc_map.c
 */
struct resc_type_map {
	char *rtm_rname;
	int   rtm_type;
	int   (*rtm_decode)(attribute *prsc, char *name, char *rn, char *val);
	int   (*rtm_encode)(attribute *prsv, pbs_list_head *phead, char *atname,
		char *rsname, int mode, svrattrl **rtnl);
	int   (*rtm_set)(attribute *old, attribute *new, enum batch_op op);
	int   (*rtm_comp)(attribute *prsc, attribute *with);
	void  (*rtm_free)(attribute *prsc);
};
extern struct resc_type_map *find_resc_type_map_by_typev(int);
extern struct resc_type_map *find_resc_type_map_by_typest(char *);
extern char *find_resc_flag_map(int);

#ifdef	__cplusplus
}
#endif
#endif	/* _RESOURCE_H */
