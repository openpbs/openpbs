/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include "pbs_ifl.h"
      #include "pbs_ecl.h"

      ecl_attribute_def ecl_node_attr_def[] = {

   /* ND_ATR_Mom  */

	{
		ATTR_NODE_Mom,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_Port */

	{
		ATTR_NODE_Port,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_version  */

	{
		ATTR_version,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_SvWR,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_ntype */

	{
		ATTR_NODE_ntype,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_SHORT,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_state */

	{
		ATTR_NODE_state,
		NO_USER_SET | ATR_DFLAG_NOSAVM,
		ATR_TYPE_SHORT,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_pcpus */

	{
		ATTR_NODE_pcpus,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_Priority */

	{
		ATTR_p,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		verify_value_priority	
	},
   /* ND_ATR_jobs */

	{
		ATTR_NODE_jobs,
		ATR_DFLAG_RDACC | ATR_DFLAG_NOSAVM,
		ATR_TYPE_JINFOP,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_MaxRun */

	{
		ATTR_maxrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_MaxGrpRun */

	{
		ATTR_maxgrprun,
		NO_USER_SET,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_No_Tasks */

	{
		ATTR_NODE_No_Tasks,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_PNames */

	{
		ATTR_PNames,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_resvs */

	{
		ATTR_NODE_resvs,
		ATR_DFLAG_RDACC | ATR_DFLAG_NOSAVM,
		ATR_TYPE_JINFOP,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_ResourceAvail */

	{
		ATTR_rescavail,
		NO_USER_SET,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		verify_value_resc	
	},
   /* ND_ATR_ResourceAssn */

	{
		ATTR_rescassn,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_RESC,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_Queue */

	{
		ATTR_queue,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_Comment */

	{
		ATTR_comment,
		NO_USER_SET | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
  /* ND_ATR_ResvEnable */

	{
		ATTR_NODE_resv_enable,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_NoMultiNode */

	{
		ATTR_NODE_NoMultiNode,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_Sharing */

	{
		ATTR_NODE_Sharing,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_ProvisionEnable */

	{
		ATTR_NODE_ProvisionEnable,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_BOOL,
		verify_datatype_bool,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_current_aoe */

	{
		ATTR_NODE_current_aoe,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_STR,
		NULL_VERIFY_DATATYPE_FUNC,
		NULL_VERIFY_VALUE_FUNC	
	},
   /* ND_ATR_in_multivnode_host */

	{
		ATTR_NODE_in_multivnode_host,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		verify_datatype_long,
		NULL_VERIFY_VALUE_FUNC	
	},

	};
	int   ecl_node_attr_size = sizeof(ecl_node_attr_def)/sizeof(ecl_attribute_def);
