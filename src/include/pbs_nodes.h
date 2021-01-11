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

#ifndef	_PBS_NODES_H
#define	_PBS_NODES_H
#ifdef	__cplusplus
extern "C" {
#endif



/*
 *	Header file used for the node tracking routines.
 */

#include "resv_node.h"
#include "resource.h"
#include "job.h"

#include "libutil.h"
#ifndef PBS_MOM
#include "pbs_db.h"
extern void *svr_db_conn;
#endif


#include "pbs_array_list.h"
#include "hook.h"
#include "hook_func.h"

/* Attributes in the Server's vnode (old node) object */
enum nodeattr {
#include "node_attr_enum.h"
	ND_ATR_LAST	/* WARNING: Must be the highest valued enum */
};


#ifndef PBS_MAXNODENAME
#define PBS_MAXNODENAME	79
#endif

/* Daemon info structure which are common for both mom and peer server */
struct daemon_info {
	unsigned long	dmn_state;   /* Daemon's state */
	int		dmn_stream;   /* TPP stream to service */
	unsigned long	*dmn_addrs;   /* IP addresses of host */
	pbs_list_head	dmn_deferred_cmds;	/* links to svr work_task list for TPP replies */
};
typedef struct daemon_info dmn_info_t;

/*
 * mominfo structure - used by both the Server and Mom
 *	to hold contact	information for an instance of a pbs_mom/pbs_server on a host
 * The server used it to represent moms and peer-servers and the mom uses it to represent peer-moms.
 * mi_data contains daemon-dependent sub-structure. 
 * So it is different to represent a mom (mom_svrinfo_t), a peer-svr (svrinfo_t) and a peer-mom (mom_vninfo_t, when used inside mom code).
 * mi_dmn_info represents the elements that are common for both mom and peer-svr. and only used within server code.
 */

struct machine_info {
	char		mi_host[PBS_MAXHOSTNAME+1]; /* hostname where service is */
	unsigned int	mi_port;	/* port to which service is listening */
	unsigned int	mi_rmport;	/* port for service RM */
	time_t		mi_modtime;	/* time configuration changed */
	dmn_info_t	*mi_dmn_info;	/* daemon specific data which are common for all */
	void		*mi_data;	/* daemon dependent substructure */
	pbs_list_link	mi_link; /* forward/backward links */	
};
typedef struct machine_info mominfo_t;
typedef struct machine_info server_t;

/*
 * The following structure is used by the Server for each Mom.
 * It is pointed to by the mi_data element in mominfo_t
 */

struct mom_svrinfo {
	long		msr_pcpus;   /* number of physical cpus reported by Mom */
	long		msr_acpus;   /* number of avail    cpus reported by Mom */
	u_Long		msr_pmem;	   /* amount of physical mem  reported by Mom */
	int		msr_numjobs; /* number of jobs on this node */
	char		*msr_arch;	    /* reported "arch" */
	char		*msr_pbs_ver;  /* mom's reported "pbs_version" */
	time_t		msr_timedown; /* time Mom marked down */
	struct work_task *msr_wktask;	/* work task for reque jobs */
	int		msr_numvnds;  /* number of vnodes */
	int		msr_numvslots; /* number of slots in msr_children */
	struct pbsnode	**msr_children;  /* array of vnodes supported by Mom */
	int		msr_jbinxsz;  /* size of job index array */
	struct job	**msr_jobindx;  /* index array of jobs on this Mom */
	long		msr_vnode_pool;/* the pool of vnodes that belong to this Mom */
	int		msr_has_inventory; /* Tells whether mom is an inventory reporting mom */
	mom_hook_action_t **msr_action;	/* pending hook copy/delete on mom */
	int		msr_num_action;	/* # of hook actions in msr_action */
};
typedef struct mom_svrinfo mom_svrinfo_t;

struct vnpool_mom {
	long			vnpm_vnode_pool;
	int			vnpm_nummoms;
	mominfo_t	       *vnpm_inventory_mom;
	mominfo_t	      **vnpm_moms;
	struct vnpool_mom      *vnpm_next;
};
typedef struct vnpool_mom vnpool_mom_t;

#ifdef	PBS_MOM

enum vnode_sharing_state	{ isshared = 0, isexcl = 1 };
enum rlplace_value		{ rlplace_unset = 0,
	rlplace_share = 1,
	rlplace_excl = 2 };

extern enum vnode_sharing_state vnss[][rlplace_excl - rlplace_unset + 1];

/*
 *	The following information is used by pbs_mom to track per-Mom
 *	information.  The mi_data member of a mominfo_t structure points to it.
 */
struct mom_vnodeinfo {
	char		*mvi_id;	/* vnode ID */
	enum vnode_sharing	mvi_sharing;	/* declared "sharing" value */
	unsigned int	mvi_memnum;	/* memory board node ID */
	unsigned int	mvi_ncpus;	/* number of CPUs in mvi_cpulist[] */
	unsigned int	mvi_acpus;	/* of those, number of CPUs available */
	struct mvi_cpus {
		unsigned int	mvic_cpunum;
#define	MVIC_FREE	0x1
#define	MVIC_ASSIGNED	0x2
#define	MVIC_CPUISFREE(m, j)	(((m)->mvi_cpulist[j].mvic_flags) & MVIC_FREE)
		unsigned int	mvic_flags;
		job		*mvic_job;	/* job this CPU is assigned */
	} *mvi_cpulist;				/* CPUs owned by this vnode */
};
typedef struct mvi_cpus		mom_mvic_t;
typedef struct mom_vnodeinfo	mom_vninfo_t;

extern enum rlplace_value getplacesharing(job *pjob);

#endif	/* PBS_MOM */


/* The following are used by Mom to map vnodes to the parent host */

struct  mom_vnode_map {
	char	   mvm_name[PBS_MAXNODENAME+1];
	char	  *mvm_hostn;	/* host name for MPI via PBS_NODEFILE */
	int	   mvm_notask;
	mominfo_t *mvm_mom;
};
typedef struct mom_vnode_map momvmap_t;

/* used for generation control on the Host to Vnode mapping */
struct	mominfo_time {
	time_t	   mit_time;
	int	   mit_gen;
};
typedef struct mominfo_time mominfo_time_t;

extern momvmap_t **mommap_array;
extern int	   mommap_array_size;
extern mominfo_time_t	   mominfo_time;
extern vnpool_mom_t *vnode_pool_mom_list;


struct	prop {
	char	*name;
	short	mark;
	struct	prop	*next;
};

struct	jobinfo {
	char		*jobid;
	int		has_cpu;
	size_t		mem;
	struct	jobinfo	*next;
};

struct	resvinfo {
	resc_resv	*resvp;
	struct resvinfo *next;
};

struct node_req {
	int	 nr_ppn;	/* processes (tasks) per node */
	int	 nr_cpp;	/* cpus per process           */
	int	 nr_np;		/* nr_np = nr_ppn * nr_cpp    */
};


/* virtual cpus - one for each resource_available.ncpus on a vnode */
struct	pbssubn {
	struct pbssubn	*next;
	struct jobinfo	*jobs;
	unsigned long	 inuse;
	long		 index;
};

union ndu_ninfo {
	struct {
		unsigned int __nd_lic_info:24;	/* OEM license information */
		unsigned int __nd_spare:8;	/* unused bits in this integer */
	} __ndu_bitfields;
	unsigned int	__nd_int;
};


/*
 * Vnode structure
 */
struct pbsnode {
	char *nd_name;		  /* vnode's name */
	mominfo_t **nd_moms; /* array of parent Moms */
	int nd_nummoms;		  /* number of Moms */
	int nd_nummslots;	  /* number of slots in nd_moms */
	int nd_index;		  /* global node index */
	int nd_arr_index;	  /* index of myself in the svr node array, only in mem, not db */
	char *nd_hostname;	  /* ptr to hostname */
	struct pbssubn *nd_psn;	  /* ptr to list of virt cpus */
	struct resvinfo *nd_resvp;
	long nd_nsn;		   /* number of VPs  */
	long nd_nsnfree;	   /* number of VPs free */
	long nd_ncpus;		   /* number of phy cpus on node */
	unsigned long nd_state;	   /* state of node */
	unsigned short nd_ntype;   /* node type */
	struct pbs_queue *nd_pque; /* queue to which it belongs */
	void *nd_lic_info;	/* information set and used for licensing */
	int nd_added_to_unlicensed_list;	/* To record if the node is added to the list of unlicensed node */
	pbs_list_link un_lic_link;		/*Link to unlicense list */
	int nd_svrflags;	/* server flags */
	pbs_list_link nd_link;	/* Link to holding svr list in case if this is an alien node */
	attribute nd_attr[ND_ATR_LAST];
};
typedef struct pbsnode pbs_node;

enum	warn_codes { WARN_none, WARN_ngrp_init, WARN_ngrp_ck, WARN_ngrp };
enum	nix_flags { NIX_none, NIX_qnodes, NIX_nonconsume };
enum	part_flags { PART_refig, PART_add, PART_rmv };

#define NDPTRBLK	50	/* extend a node ptr array by this amt */


/*
 * The following INUSE_* flags are used for several structures
 * (subnode.inuse, node.nd_state, and dmn_info.dmn_state).
 * The database schema stores node.nd_state as a 4 byte integer.
 * If more than 32 flags bits need to be added, the database schema will
 * need to be updated.  If not, the excess flags will be lost upon server restart
 */
#define	INUSE_FREE	 0x00	/* Node has one or more avail VPs	*/
#define	INUSE_OFFLINE	 0x01	/* Node was removed by administrator	*/
#define	INUSE_DOWN	 0x02	/* Node is down/unresponsive 		*/
#define	INUSE_DELETED	 0x04	/* Node is "deleted"			*/
#define INUSE_UNRESOLVABLE	 0x08	/* Node not reachable */
#define	INUSE_JOB	 0x10	/* VP   in used by a job (normal use)	*/
/* Node all VPs in use by jobs		*/
#define INUSE_STALE	 0x20	/* Vnode not reported by Mom            */
#define INUSE_JOBEXCL	 0x40	/* Node is used by one job (exclusive)	*/
#define	INUSE_BUSY	 0x80	/* Node is busy (high loadave)		*/
#define INUSE_UNKNOWN	 0x100	/* Node has not been heard from yet	*/
#define INUSE_NEEDS_HELLOSVR	0x200	/* Fresh hello sequence needs to be initiated */
#define INUSE_INIT	 0x400	/* Node getting vnode map info		*/
#define INUSE_PROV	 0x800	/* Node is being provisioned		*/
#define INUSE_WAIT_PROV	 0x1000	/* Node is being provisioned		*/
/* INUSE_WAIT_PROV is 0x1000 - this should not clash with MOM_STATE_BUSYKB
 * since INUSE_WAIT_PROV is used as part of the node_state and MOM_STATE_BUSYKB
 * is used inside mom for variable internal_state
 */
#define INUSE_RESVEXCL	0x2000	/* Node is exclusive to a reservation	*/
#define INUSE_OFFLINE_BY_MOM 0x4000 /* Node is offlined by mom */
#define INUSE_MARKEDDOWN 0x8000 /* TPP layer marked node down */
#define INUSE_NEED_ADDRS	0x10000	/* Needs to be sent IP addrs */
#define INUSE_MAINTENANCE	0x20000 /* Node has a job in the admin suspended state */
#define INUSE_SLEEP             0x40000 /* Node is sleeping */
#define INUSE_NEED_CREDENTIALS	0x80000 /* Needs to be sent credentials */

#define VNODE_UNAVAILABLE (INUSE_STALE | INUSE_OFFLINE | INUSE_DOWN | \
			   INUSE_DELETED | INUSE_UNKNOWN | INUSE_UNRESOLVABLE \
			   | INUSE_OFFLINE_BY_MOM | INUSE_MAINTENANCE | INUSE_SLEEP)

/* the following are used in Mom's internal state			*/
#define MOM_STATE_DOWN	 INUSE_DOWN
#define MOM_STATE_BUSY	 INUSE_BUSY
#define MOM_STATE_BUSYKB      0x1000	/* keyboard is busy 		   */
#define MOM_STATE_INBYKB      0x2000	/* initial period of keyboard busy */
#define MOM_STATE_CONF_HARVEST  0x4000	/* MOM configured to cycle-harvest */
#define MOM_STATE_MASK	      0x0fff	/* to mask what is sent to server  */

#define	FLAG_OKAY	 0x01	/* "ok" to consider this node in the search */
#define	FLAG_THINKING	 0x02	/* "thinking" to use node to satisfy specif */
#define	FLAG_CONFLICT	 0x04	/* "conflict" temporarily  ~"thinking"      */
#define	FLAG_IGNORE	 0x08	/* "no use"; reality, can't use node in spec*/

/* bits both in nd_state and inuse	*/
#define INUSE_SUBNODE_MASK (INUSE_OFFLINE|INUSE_OFFLINE_BY_MOM|INUSE_DOWN|INUSE_JOB|INUSE_STALE|\
INUSE_JOBEXCL|INUSE_BUSY|INUSE_UNKNOWN|INUSE_INIT|INUSE_PROV|INUSE_WAIT_PROV|\
INUSE_RESVEXCL|INUSE_UNRESOLVABLE|INUSE_MAINTENANCE|INUSE_SLEEP)

#define INUSE_COMMON_MASK  (INUSE_OFFLINE|INUSE_DOWN)
/* state bits that go from node to subn */
#define	CONFLICT	1	/*search process must consider conflicts*/
#define NOCONFLICT	0	/*be oblivious to conflicts in search*/

/*
 * server flags (in nd_svrflags)
 */
#define NODE_ALIEN      0x01	/* node does not belong to this server */
#define NODE_UNLICENSED 0x02 /* To record if the node is added to the list of unlicensed node */
#define NODE_NEWOBJ     0x04	/* new node ? */
#define NODE_ACCTED     0x08	/* resc recorded in job acct */

/* operators to set the state of a vnode. Nd_State_Set is "=",
 * Nd_State_Or is "|=" and Nd_State_And is "&=". This is used in set_vnode_state
 */
enum vnode_state_op {
	Nd_State_Set,
	Nd_State_Or,
	Nd_State_And
};

/* To indicate whether a degraded time should be set on a reservation */
enum vnode_degraded_op {
	Skip_Degraded_Time,
	Set_Degraded_Time,
};


/*
 * NTYPE_* values are used in "node.nd_type"
 */
#define NTYPE_PBS   	 0x00	/* Node is normal node	*/

#define PBSNODE_NTYPE_MASK	0xf		 /* relevant ntype bits */


/* tree for mapping contact info to node struture */
struct tree {
	unsigned long	   key1;
	unsigned long	   key2;
	mominfo_t         *momp;
	struct tree	  *left, *right;
};

extern void *node_attr_idx;
extern attribute_def node_attr_def[]; /* node attributes defs */
extern struct pbsnode **pbsndlist;           /* array of ptr to nodes  */
extern int svr_totnodes;                     /* number of nodes (hosts) */
extern struct tree *ipaddrs;
extern struct tree *streams;
extern mominfo_t **mominfo_array;
extern pntPBS_IP_LIST pbs_iplist;
extern int mominfo_array_size;
extern int mom_send_vnode_map;
extern int svr_num_moms;


/* Handlers for vnode state changing.for degraded reservations */
extern	void vnode_unavailable(struct pbsnode *, int);
extern	void vnode_available(struct pbsnode *);
extern	int find_degraded_occurrence(resc_resv *, struct pbsnode *, enum vnode_degraded_op);
extern	int find_vnode_in_execvnode(char *, char *);
extern	void set_vnode_state(struct pbsnode *, unsigned long , enum vnode_state_op);
extern	struct resvinfo *find_vnode_in_resvs(struct pbsnode *, enum vnode_degraded_op);
extern	void free_rinf_list(struct resvinfo *);
extern	void degrade_offlined_nodes_reservations(void);
extern	void degrade_downed_nodes_reservations(void);

extern	int mod_node_ncpus(struct pbsnode *pnode, long ncpus, int actmode);
extern	int	initialize_pbsnode(struct pbsnode*, char*, int);
extern	void	initialize_pbssubn(struct pbsnode *, struct pbssubn*, struct prop*);
extern  struct pbssubn *create_subnode(struct pbsnode *, struct pbssubn *lstsn);
extern	void	effective_node_delete(struct pbsnode*);
extern	void	setup_notification(void);
extern  struct	pbssubn  *find_subnodebyname(char *);
extern	struct	pbsnode  *find_nodebyname(char *);
extern	struct	pbsnode  *find_nodebyaddr(pbs_net_t);
extern	pbs_node *find_alien_node(char *nodename);
extern	void	free_prop_list(struct prop*);
extern	void	recompute_ntype_cnts(void);
extern	int	process_host_name_part(char*, svrattrl*, char**, int*);
extern  int     create_pbs_node(char *, svrattrl *, int, int *, struct pbsnode **, int);
extern  int     create_pbs_node2(char *, svrattrl *, int, int *, struct pbsnode **, int, int);
extern  int     mgr_set_node_attr(struct pbsnode *, attribute_def *, int, svrattrl *, int, int *, void *, int);
extern	int	node_queue_action(attribute *, void *, int);
extern	int	node_pcpu_action(attribute *, void *, int);
struct prop 	*init_prop(char *pname);
extern	void	set_node_license(void);
extern  int	set_node_topology(attribute*, void*, int);
extern	void	unset_node_license(struct pbsnode *);
extern  mominfo_t *tfind2(const unsigned long, const unsigned long, struct tree **);
extern	int	set_node_host_name(attribute *, void *, int);
extern	int	set_node_hook_action(attribute *, void *, int);
extern  int	set_node_mom_port  (attribute *, void *, int);
extern  mominfo_t *create_mom_entry(char *, unsigned int);
extern  mominfo_t *find_mom_entry(char *, unsigned int);
extern  void	momptr_down(mominfo_t *, char *);
extern  void	momptr_offline_by_mom(mominfo_t *, char *);
extern  void	momptr_clear_offline_by_mom(mominfo_t *, char *);
extern  void	   delete_mom_entry(mominfo_t *);
extern  mominfo_t *create_svrmom_entry(char *, unsigned int, unsigned long *);
extern  void       delete_svrmom_entry(mominfo_t *);
extern  int	legal_vnode_char(char, int);
extern 	char	*parse_node_token(char *, int, int *, char *);
extern  int	cross_link_mom_vnode(struct pbsnode *, mominfo_t *);
extern 	int	fix_indirectness(resource *, struct pbsnode *, int);
extern	int	chk_vnode_pool(attribute *, void *, int);
extern	void	free_pnode(struct pbsnode *);
extern	int	save_nodes_db(int, void *);
extern void	propagate_socket_licensing(mominfo_t *);
extern void	update_jobs_on_node(char *, char *, int, int);
extern int	mcast_add(mominfo_t *, int *, bool);
void		stream_eof(int, int, char *);

extern char *msg_daemonname;

#define	NODE_TOPOLOGY_TYPE_HWLOC	"hwloc"
#define	NODE_TOPOLOGY_TYPE_CRAY		"Cray-v1:"
#define	NODE_TOPOLOGY_TYPE_WIN		"Windows:"

#define	CRAY_COMPUTE	"cray_compute"	/* vntype for a Cray compute node */
#define	CRAY_LOGIN	"cray_login"	/* vntype for a Cray login node */

/* Mom Job defines */
#define JOB_ACT_REQ_REQUEUE 0
#define JOB_ACT_REQ_DELETE  1
#define JOB_ACT_REQ_DEALLOCATE	2


extern void remove_mom_from_pool(mominfo_t *);
extern void mcast_moms();

#ifndef PBS_MOM
extern int node_save_db(struct pbsnode *pnode);
struct pbsnode *node_recov_db(char *nd_name, struct pbsnode *pnode);
extern int add_mom_to_pool(mominfo_t *);
extern void reset_pool_inventory_mom(mominfo_t *);
extern vnpool_mom_t *find_vnode_pool(mominfo_t *pmom);
extern void mcast_msg();
int get_job_share_type(struct job *pjob);
#endif

extern  int	   recover_vmap(void);
extern  void       delete_momvmap_entry(momvmap_t *);
extern  momvmap_t *create_mommap_entry(char *, char *hostn, mominfo_t *, int);
extern mominfo_t	*find_mom_by_vnodename(const char *);
extern momvmap_t	*find_vmap_entry(const char *);
extern mominfo_t	*add_mom_data(const char *, void *);
extern mominfo_t	*find_mominfo(const char *);
extern int		create_vmap(void **);
extern void		destroy_vmap(void *);
extern mominfo_t	*find_vmapent_byID(void *, const char *);
extern int		add_vmapent_byID(void *, const char *, void *);
extern  int		open_conn_stream(mominfo_t *);
extern void		close_streams(int stm, int ret);
extern void		delete_daemon_info(struct machine_info *pmi);
extern dmn_info_t *	init_daemon_info(unsigned long *pul, unsigned int port, struct machine_info *pmi);


attribute *get_nattr(const struct pbsnode *pnode, int attr_idx);
char *get_nattr_str(const struct pbsnode *pnode, int attr_idx);
struct array_strings *get_nattr_arst(const struct pbsnode *pnode, int attr_idx);
pbs_list_head get_nattr_list(const struct pbsnode *pnode, int attr_idx);
long get_nattr_long(const struct pbsnode *pnode, int attr_idx);
char get_nattr_c(const struct pbsnode *pnode, int attr_idx);
int set_nattr_generic(struct pbsnode *pnode, int attr_idx, char *val, char *rscn, enum batch_op op);
int set_nattr_str_slim(struct pbsnode *pnode, int attr_idx, char *val, char *rscn);
int set_nattr_l_slim(struct pbsnode *pnode, int attr_idx, long val, enum batch_op op);
int set_nattr_b_slim(struct pbsnode *pnode, int attr_idx, long val, enum batch_op op);
int set_nattr_c_slim(struct pbsnode *pnode, int attr_idx, char val, enum batch_op op);
int set_nattr_short_slim(struct pbsnode *pnode, int attr_idx, short val, enum batch_op op);
int is_nattr_set(const struct pbsnode *pnode, int attr_idx);
void free_nattr(struct pbsnode *pnode, int attr_idx);
void clear_nattr(struct pbsnode *pnode, int attr_idx);
void set_nattr_jinfo(struct pbsnode *pnode, int attr_idx, struct pbsnode *val);

#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_NODES_H */
