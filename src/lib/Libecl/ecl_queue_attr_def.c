/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>    
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "pbs_ecl.h"

      ecl_attribute_def ecl_que_attr_def[] = {

	/* QA_ATR_QType */

	{
		ATTR_qtype,
		NO_USER_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_queue_type	
	},
	/* QA_ATR_Priority */

	{
		ATTR_p,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_priority	
	},
	/* QA_ATR_MaxJobs */

	{
		ATTR_maxque,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_TotalJobs */

	{
		ATTR_total,
		READ_ONLY,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_JobsByState */

	{
		ATTR_count,
		READ_ONLY,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_MaxRun */

	{
		ATTR_maxrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_max_queued */

	{
		ATTR_max_queued,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_max_queued_res */

	{
		ATTR_max_queued_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_AclHostEnabled */

	{
		ATTR_aclhten,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_AclHost */

	{
		ATTR_aclhost,
		NO_USER_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_AclUserEnabled */

	{
		ATTR_acluren,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_AclUsers */

	{
		ATTR_acluser,
		NO_USER_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_FromRouteOnly */

	{
		ATTR_fromroute,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_ResourceMax */

	{
		ATTR_rescmax,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QA_ATR_ResourceMin */

	{
		ATTR_rescmin,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QA_ATR_ResourceDefault */

	{
		ATTR_rescdflt,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QA_ATR_ReqCredEnable */

	{
		ATTR_ReqCredEnable,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_ReqCred */

	{
		ATTR_ReqCred,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_credname	
	},
	/* QA_ATR_maxarraysize */

	{
		ATTR_maxarraysize,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_AclGroupEnabled */

	{
		ATTR_aclgren,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_AclGroup */

	{
		ATTR_aclgroup,
		NO_USER_SET,
		ATR_TYPE_ACL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_ChkptMin */

	{
		ATTR_chkptmin,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_RendezvousRetry */

	{
		"rendezvous_retry",
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_ReservedExpedite */

	{
		"reserved_expedite",
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_ReservedSync */

	{
		"reserved_sync",
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_DefaultChunk */

	{
		ATTR_DefaultChunk,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_ResourceAvail */

	{
		"resources_available",
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_ResourceAssn */

	{
		ATTR_rescassn,
		READ_ONLY,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_KillDelay */

	{
		ATTR_killdelay,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_MaxGrpRun */

	{
		ATTR_maxgrprun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_max_run */

	{
		ATTR_max_run,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_max_run_res */

	{
		ATTR_max_run_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_max_run_soft */

	{
		ATTR_max_run_soft,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_max_run_res_soft */

	{
		ATTR_max_run_res_soft,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_HasNodes */

	{
		ATTR_HasNodes,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_BOOL,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_MaxUserRes */

	{
		ATTR_maxuserres,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_MaxGroupRes */

	{
		ATTR_maxgroupres,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_MaxUserRunSoft */

	{
		ATTR_maxuserrunsoft,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_MaxGrpRunSoft */

	{
		ATTR_maxgrprunsoft,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QE_ATR_MaxUserResSoft */

	{
		ATTR_maxuserressoft,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_MaxGroupResSoft */

	{
		ATTR_maxgroupressoft,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
	/* QE_ATR_NodeGroupKey */

	{
		ATTR_NodeGroupKey,
		NO_USER_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* QE_ATR_BackfillDepth */

	{
		ATTR_backfill_depth,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_zero_or_positive	
	},
	/* QR_ATR_RouteDestin */

	{
		ATTR_routedest,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QR_ATR_AltRouter */

	{
		ATTR_altrouter,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QR_ATR_RouteHeld */

	{
		ATTR_routeheld,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QR_ATR_RouteWaiting */

	{
		ATTR_routewait,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QR_ATR_RouteRetryTime */

	{
		ATTR_routeretry,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QR_ATR_RouteLifeTime	 */

	{
		ATTR_routelife,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_Enabled */

	{
		ATTR_enable,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_Started */

	{
		ATTR_start,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
 	/* QA_ATR_queued_jobs_threshold */

	{
		ATTR_queued_jobs_threshold,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
	/* QA_ATR_queued_jobs_threshold_res */

	{
		ATTR_queued_jobs_threshold_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},

	};
	int   ecl_que_attr_size = sizeof(ecl_que_attr_def)/sizeof(ecl_attribute_def);
