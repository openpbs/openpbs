/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include <stdlib.h>
      #include <stdio.h>
      #include <ctype.h>
      #include "pbs_ifl.h"
      #include "server_limits.h"
      #include <string.h>
      #include "list_link.h"
      #include "attribute.h"
      #include "resource.h"
      #include "pbs_error.h"
      #include "pbs_nodes.h"
      #include "svrfunc.h"
      #include "grunt.h"

      extern int set_node_ct(resource *, attribute *, void *, int, int actmode);
      extern int decode_place(struct attribute *, char *, char *, char *);
      extern int preempt_targets_action(resource *presc, attribute *pattr, void *pobject, int type, int actmode);
      extern int zero_or_positive_action  (resource *, attribute *, void *, int, int actmode);
      #ifndef PBS_MOM
      extern int host_action(resource *, attribute *, void *, int, int actmode);
      extern int resc_select_action(resource *, attribute *, void *, int, int);
      #endif /* PBS_MOM */
      /* ordered by guess to put ones most often used at front */

      static resource_def svr_resc_defm[] = {
      		
   /*cput*/
	
	{
		"cput",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mem*/
	
	{
		"mem",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN |ATR_DFLAG_CVTSLT,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*walltime*/
	
	{
		"walltime",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*min_walltime*/
	
	{
		"min_walltime",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*max_walltime*/
	
	{
		"max_walltime",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*ncpus*/
	
	{
		"ncpus",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*naccelerators*/
	
	{
		"naccelerators",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*select*/
	
	{
		"select",
		decode_select,
		encode_str,
		set_str,
		comp_str,
		free_str,
		#ifdef PBS_MOM
			NULL_FUNC,
		#else
			resc_select_action,
		#endif
		READ_WRITE,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*place*/
	
	{
		"place",
		decode_place,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*nodes*/
	
	{
		"nodes",
		decode_nodes,
		encode_str,
		set_str,
		comp_str,
		free_str,
		set_node_ct,
		READ_WRITE,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*nodect*/
	
	{
		"nodect",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_MGWR | ATR_DFLAG_RASSN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*arch*/
	
	{
		"arch",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_CVTSLT | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*netwins*/
	
	{
		"netwins",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET | ATR_DFLAG_MOM | ATR_DFLAG_RASSN |ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*nchunk*/
	
	{
		"nchunk",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*vntype*/
	
	{
		"vntype",
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_ARST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*MPIPROCS*/
	
	{
		MPIPROCS,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_RASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*OMPTHREADS*/
	
	{
		OMPTHREADS,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*cpupercent*/
	
	{
		"cpupercent",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*file*/
	
	{
		"file",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*pmem*/
	
	{
		"pmem",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*vmem*/
	
	{
		"vmem",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*pvmem*/
	
	{
		"pvmem",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*nice*/
	
	{
		"nice",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*pcput*/
	
	{
		"pcput",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*nodemask*/
	
	{
		"nodemask",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_null,
		NULL_FUNC,
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
  /*hpm*/
	
	{
		"hpm",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*ssinodes*/
	
	{
		"ssinodes",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*host*/
	
	{
		"host",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		#ifdef PBS_MOM
			NULL_FUNC,
		#else
			host_action,
		#endif
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*vnode*/
	
	{
		"vnode",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*resc*/
	
	{
		"resc",
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_ARST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*software*/
	
	{
		"software",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*site*/
	
	{
		"site",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*exec_vnode*/
	
	{
		"exec_vnode",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*start_time*/
	
	{
		"start_time",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mpphost*/
	
	{
		"mpphost",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mpparch*/
	
	{
		"mpparch",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mpplabels*/
	
	{
		"mpplabels",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppwidth*/
	
	{
		"mppwidth",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppdepth*/
	
	{
		"mppdepth",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppnppn*/
	
	{
		"mppnppn",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		zero_or_positive_action,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppnodes*/
	
	{
		"mppnodes",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppmem*/
	
	{
		"mppmem",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*mppt*/
	
	{
		"mppt",
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},
#if PE_MASK != 0
	/* PE mask on Cray T3e (similar to nodemask on SGI O2K */
	
	{
		"pe_mask",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},
#endif

	/*partition*/
	
	{
		"partition",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},
#ifndef PBS_MOM	   
   /*aoe*/
	
	{
		"aoe",
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_ARST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},
#endif

   	/*preempt_targets*/
	
	{
		"preempt_targets",
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		preempt_targets_action,
		READ_WRITE,
		ATR_TYPE_ARST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},
   	/*accelerator*/
	
	{
		"accelerator",
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_CVTSLT,
		ATR_TYPE_BOOL,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*accelerator_model*/
	
	{
		"accelerator_model",
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_CVTSLT,
		ATR_TYPE_STR,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*accelerator_memory*/
	
	{
		"accelerator_memory",
		decode_size,
		encode_size,
		set_size,
		comp_size,
		free_null,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN |ATR_DFLAG_CVTSLT,
		ATR_TYPE_SIZE,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
   /*accelerator_group*/
	
	{
		"accelerator_group",
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_ARST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},		
    /* the definition for the "unknown" resource MUST be last */
	
	{
		"|unknown|",
		decode_unkn,
		encode_unkn,
		set_unkn,
		comp_unkn,
		free_unkn,
		NULL_FUNC,
		READ_WRITE,
		ATR_TYPE_LIST,
		PBS_ENTLIM_NOLIMIT,
		(struct resource_def *)0
	},

	};
	int           svr_resc_size = sizeof(svr_resc_defm) / sizeof(resource_def);
	resource_def *svr_resc_def  = svr_resc_defm;
	int	      svr_resc_unk  = sizeof(svr_resc_defm) / sizeof(resource_def)-1;
      