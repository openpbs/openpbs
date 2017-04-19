/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>    
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "list_link.h"
      #include "attribute.h"
      #include "pbs_nodes.h"
      #include "svrfunc.h"

      attribute_def que_attr_def[] = {


	/* QA_ATR_QType */

	{
		ATTR_qtype,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		set_queue_type,
		NO_USER_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_Priority */

	{
		ATTR_p,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_MaxJobs */

	{
		ATTR_maxque,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_TotalJobs */

	{
		ATTR_total,
		decode_null,
		encode_l,
		set_null,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_JobsByState */

	{
		ATTR_count,
		decode_null,
		encode_str,
		set_null,
		comp_str,
		free_null,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_STR,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_MaxRun */

	{
		ATTR_maxrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_max_queued */

	{
		ATTR_max_queued,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_ct,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_max_queued_res */

	{
		ATTR_max_queued_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_AclHostEnabled */

	{
		ATTR_aclhten,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_AclHost */

	{
		ATTR_aclhost,
		decode_arst,
		encode_arst,
		set_hostacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_AclUserEnabled */

	{
		ATTR_acluren,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_AclUsers */

	{
		ATTR_acluser,
		decode_arst,
		encode_arst,
		set_uacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_FromRouteOnly */

	{
		ATTR_fromroute,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_ResourceMax */

	{
		ATTR_rescmax,
		decode_resc,
		encode_resc,
		set_resources_min_max,
		comp_resc,
		free_resc,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_ResourceMin */

	{
		ATTR_rescmin,
		decode_resc,
		encode_resc,
		set_resources_min_max,
		comp_resc,
		free_resc,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_ResourceDefault */

	{
		ATTR_rescdflt,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		action_resc_dflt_queue,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_ReqCredEnable */

	{
		ATTR_ReqCredEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_ReqCred */

	{
		ATTR_ReqCred,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		cred_name_okay,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_maxarraysize */

	{
		ATTR_maxarraysize,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_ALL
	},

	/* QE_ATR_AclGroupEnabled */

	{
		ATTR_aclgren,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QE_ATR_AclGroup */

	{
		ATTR_aclgroup,
		decode_arst,
		encode_arst,
		set_gacl,
		comp_arst,
		free_arst,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_ACL,
		PARENT_TYPE_QUE_ALL
	},

	/* QE_ATR_ChkptMin */

	{
		ATTR_chkptmin,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_RendezvousRetry */

	{
		"rendezvous_retry",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_ReservedExpedite */

	{
		"reserved_expedite",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_ReservedSync */

	{
		"reserved_sync",
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_DefaultChunk */

	{
		ATTR_DefaultChunk,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		deflt_chunk_action,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_ResourceAvail */

	{
		"resources_available",
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_ResourceAssn */

	{
		ATTR_rescassn,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		READ_ONLY,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_KillDelay */

	{
		ATTR_killdelay,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxGrpRun */

	{
		ATTR_maxgrprun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_max_run */

	{
		ATTR_max_run,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_max_run_res */

	{
		ATTR_max_run_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_max_run_soft */

	{
		ATTR_max_run_soft,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_max_run_res_soft */

	{
		ATTR_max_run_res_soft,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_chk,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_HasNodes */

	{
		ATTR_HasNodes,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxUserRes */

	{
		ATTR_maxuserres,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxGroupRes */

	{
		ATTR_maxgroupres,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxUserRunSoft */

	{
		ATTR_maxuserrunsoft,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxGrpRunSoft */

	{
		ATTR_maxgrprunsoft,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxUserResSoft */

	{
		ATTR_maxuserressoft,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_MaxGroupResSoft */

	{
		ATTR_maxgroupressoft,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		check_no_entlim,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_QUE_EXC
	},

	/* QE_ATR_NodeGroupKey */

	{
		ATTR_NodeGroupKey,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		is_valid_resource,
		NO_USER_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_QUE_EXC
	},

   /* QE_ATR_BackfillDepth */

	{
		ATTR_backfill_depth,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		action_backfill_depth,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_EXC
	},

	/* QR_ATR_RouteDestin */

	{
		ATTR_routedest,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_QUE_RTE
	},

	/* QR_ATR_AltRouter */

	{
		ATTR_altrouter,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_RTE
	},

	/* QR_ATR_RouteHeld */

	{
		ATTR_routeheld,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_RTE
	},

	/* QR_ATR_RouteWaiting */

	{
		ATTR_routewait,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_RTE
	},

	/* QR_ATR_RouteRetryTime */

	{
		ATTR_routeretry,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_RTE
	},

	/* QR_ATR_RouteLifeTime	 */

	{
		ATTR_routelife,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_QUE_RTE
	},
#include "site_que_attr_def.h"
	/* QA_ATR_Enabled */

	{
		ATTR_enable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		check_que_enable,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_Started */

	{
		ATTR_start,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		queuestart_action,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_QUE_ALL
	},

 	/* QA_ATR_queued_jobs_threshold */

	{
		ATTR_queued_jobs_threshold,
		decode_entlim,
		encode_entlim,
		set_entlim,
		comp_str,
		free_entlim,
		action_entlim_ct,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_ALL
	},

	/* QA_ATR_queued_jobs_threshold_res */

	{
		ATTR_queued_jobs_threshold_res,
		decode_entlim_res,
		encode_entlim,
		set_entlim_res,
		comp_str,
		free_entlim,
		action_entlim_res,
		NO_USER_SET,
		ATR_TYPE_ENTITY,
		PARENT_TYPE_QUE_ALL
	},

	};
