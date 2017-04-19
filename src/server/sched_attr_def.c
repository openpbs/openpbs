/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

     #include <pbs_config.h>   
     #include <sys/types.h>
     #include "pbs_ifl.h"
     #include "list_link.h"
     #include "attribute.h"
     #include "pbs_nodes.h"
     #include "svrfunc.h"
     #include "pbs_error.h"
     #include "pbs_python.h"

     attribute_def sched_attr_def[] = {

/* SchedHost */	

	{
		ATTR_SchedHost,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		PARENT_TYPE_SCHED
	},
/* version */

	{
		ATTR_version,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		NULL_FUNC,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		PARENT_TYPE_SCHED
	},
/* sched_cycle_len */

	{
		ATTR_sched_cycle_len,
		decode_time,
		encode_time,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SCHED
	},
/* do_not_span_psets */ 

	{
		ATTR_do_not_span_psets,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SCHED
	},
/* sched_preempt_enforce_resumption */ 

	{
		ATTR_sched_preempt_enforce_resumption,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SCHED
	},
/* preempt_targets_enable */ 

	{
		ATTR_preempt_targets_enable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_SCHED
	},
/* job_sort_formula_threshold */

	{
		ATTR_job_sort_formula_threshold,
		decode_f,
		encode_f,
		set_f,
		comp_f,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_FLOAT,
		PARENT_TYPE_SCHED
	},
/* throughput_mode */ 

	{
		ATTR_throughput_mode,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		set_sched_throughput_mode,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_SCHED
	},
/* opt_backfill_fuzzy */

	{
		ATTR_opt_backfill_fuzzy,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		action_opt_bf_fuzzy,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_SCHED
	},

         #include "site_sched_attr_def.h"
	};
