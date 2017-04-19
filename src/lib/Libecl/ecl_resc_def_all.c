/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "pbs_ecl.h"

      ecl_attribute_def ecl_svr_resc_def[] = {
      		
   /*cput*/
	
	{
		"cput",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mem*/
	
	{
		"mem",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN |ATR_DFLAG_CVTSLT,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*walltime*/
	
	{
		"walltime",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*min_walltime*/
	
	{
		"min_walltime",
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		verify_value_zero_or_positive	
	},		
   /*max_walltime*/
	
	{
		"max_walltime",
		READ_WRITE | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		verify_value_zero_or_positive	
	},		
   /*ncpus*/
	
	{
		"ncpus",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*select*/
	
	{
		"select",
		READ_WRITE,
		ATR_TYPE_STR,
		verify_datatype_select,
		verify_value_select	
	},		
   /*place*/
	
	{
		"place",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*nodes*/
	
	{
		"nodes",
		READ_WRITE,
		ATR_TYPE_STR,
		verify_datatype_nodes,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*nodect*/
	
	{
		"nodect",
		READ_ONLY | ATR_DFLAG_MGWR | ATR_DFLAG_RASSN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*arch*/
	
	{
		"arch",
		READ_WRITE | ATR_DFLAG_CVTSLT | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*netwins*/
	
	{
		"netwins",
		MGR_ONLY_SET | ATR_DFLAG_MOM | ATR_DFLAG_RASSN |ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*MPIPROCS*/
	
	{
		MPIPROCS,
		READ_WRITE | ATR_DFLAG_RASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*OMPTHREADS*/
	
	{
		OMPTHREADS,
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*cpupercent*/
	
	{
		"cpupercent",
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*file*/
	
	{
		"file",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*pmem*/
	
	{
		"pmem",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*vmem*/
	
	{
		"vmem",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN | ATR_DFLAG_ANASSN | ATR_DFLAG_CVTSLT,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*pvmem*/
	
	{
		"pvmem",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*nice*/
	
	{
		"nice",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*pcput*/
	
	{
		"pcput",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*nodemask*/
	
	{
		"nodemask",
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
  /*hpm*/
	
	{
		"hpm",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_RASSN,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*ssinodes*/
	
	{
		"ssinodes",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*host*/
	
	{
		"host",
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*vnode*/
	
	{
		"vnode",
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*resc*/
	
	{
		"resc",
		READ_WRITE,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*software*/
	
	{
		"software",
		READ_WRITE,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*site*/
	
	{
		"site",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mpphost*/
	
	{
		"mpphost",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mpparch*/
	
	{
		"mpparch",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mpplabels*/
	
	{
		"mpplabels",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mppwidth*/
	
	{
		"mppwidth",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*mppdepth*/
	
	{
		"mppdepth",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*mppnppn*/
	
	{
		"mppnppn",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},		
   /*mppnodes*/
	
	{
		"mppnodes",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mppmem*/
	
	{
		"mppmem",
		READ_WRITE | ATR_DFLAG_MOM,
		ATR_TYPE_SIZE,
		verify_datatype_size,
		NULL_VERIFY_VALUE_FUNC	
	},		
   /*mppt*/
	
	{
		"mppt",
		READ_WRITE | ATR_DFLAG_MOM | ATR_DFLAG_ALTRUN,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},
#if PE_MASK != 0
	/* PE mask on Cray T3e (similar to nodemask on SGI O2K */
	
	{
		"pe_mask",
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
#endif

	/*partition*/
	
	{
		"partition",
		NO_USER_SET | ATR_DFLAG_MOM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},	   
   /*aoe*/
	
	{
		"aoe",
		READ_WRITE | ATR_DFLAG_CVTSLT,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   	/*preempt_targets*/
	
	{
		"preempt_targets",
		READ_WRITE,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_preempt_targets	
	},

	};
	int ecl_svr_resc_size = sizeof(ecl_svr_resc_def)/sizeof(ecl_attribute_def);
      