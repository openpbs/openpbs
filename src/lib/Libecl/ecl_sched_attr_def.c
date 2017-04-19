/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

     #include <pbs_config.h>   
     #include <sys/types.h>
     #include "pbs_ifl.h"
     #include "pbs_ecl.h"

     ecl_attribute_def ecl_sched_attr_def[] = {
/* SchedHost */	

	{
		ATTR_SchedHost,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},/* version */

	{
		ATTR_version,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},/* sched_cycle_len */

	{
		ATTR_sched_cycle_len,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_time,
		NULL_VERIFY_VALUE_FUNC	
	},/* do_not_span_psets */ 

	{
		ATTR_do_not_span_psets,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},/* sched_preempt_enforce_resumption */ 

	{
		ATTR_sched_preempt_enforce_resumption,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},/* preempt_targets_enable */ 

	{
		ATTR_preempt_targets_enable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},/* job_sort_formula_threshold */

	{
		ATTR_job_sort_formula_threshold,
		NO_USER_SET,
		ATR_TYPE_FLOAT,
		verify_datatype_float,
		NULL_VERIFY_VALUE_FUNC	
	},/* throughput_mode */ 

	{
		ATTR_throughput_mode,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},/* opt_backfill_fuzzy */

	{
		ATTR_opt_backfill_fuzzy,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},

	};
	int ecl_sched_attr_size=sizeof(ecl_sched_attr_def)/sizeof(ecl_attribute_def);
