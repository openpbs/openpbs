/*Disclaimer: This is a machine generated file.*/
/*For modifying any attribute change corresponding XML file */

      #include <pbs_config.h>   
      #include <sys/types.h>
      #include <stdlib.h>
      #include <ctype.h>
      #include "server_limits.h"
      #include "pbs_ifl.h"
      #include <string.h>
      #include "list_link.h"
      #include "attribute.h"
      #include "resource.h"
      #include "pbs_error.h"
      #include "pbs_nodes.h"

      attribute_def node_attr_def[] = {


   /* ND_ATR_Mom  */

	{
		ATTR_NODE_Mom,
		decode_Mom_list,
		encode_arst,
		set_arst_uniq,
		comp_arst,
		free_arst,
		set_node_host_name,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_Port */

	{
		ATTR_NODE_Port,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		set_node_mom_port,
		ATR_DFLAG_OPRD | ATR_DFLAG_MGRD | ATR_DFLAG_OPWR | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_version  */

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
		PARENT_TYPE_NODE
	},

   /* ND_ATR_ntype */

	{
		ATTR_NODE_ntype,
		decode_ntype,
		encode_ntype,
		set_node_ntype,
		comp_null,
		free_null,
		node_ntype,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_SHORT,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_state */

	{
		ATTR_NODE_state,
		decode_state,
		encode_state,
		set_node_state,
		comp_null,
		free_null,
		node_state,
		NO_USER_SET | ATR_DFLAG_NOSAVM,
		ATR_TYPE_SHORT,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_pcpus */

	{
		ATTR_NODE_pcpus,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		node_pcpu_action,
		READ_ONLY | ATR_DFLAG_SvWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_Priority */

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
		PARENT_TYPE_NODE
	},

   /* ND_ATR_jobs */

	{
		ATTR_NODE_jobs,
		decode_null,
		encode_jobs,
		set_null,
		comp_null,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_RDACC | ATR_DFLAG_NOSAVM,
		ATR_TYPE_JINFOP,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_MaxRun */

	{
		ATTR_maxrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_MaxUserRun */

	{
		ATTR_maxuserrun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_MaxGrpRun */

	{
		ATTR_maxgrprun,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_No_Tasks */

	{
		ATTR_NODE_No_Tasks,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		NO_USER_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_PNames */

	{
		ATTR_PNames,
		decode_arst,
		encode_arst,
		set_arst,
		comp_arst,
		free_arst,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_ARST,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_resvs */

	{
		ATTR_NODE_resvs,
		decode_null,
		encode_resvs,
		set_null,
		comp_null,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_RDACC | ATR_DFLAG_NOSAVM,
		ATR_TYPE_JINFOP,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_ResourceAvail */

	{
		ATTR_rescavail,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		node_np_action,
		NO_USER_SET,
		ATR_TYPE_RESC,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_ResourceAssn */

	{
		ATTR_rescassn,
		decode_resc,
		encode_resc,
		set_resc,
		comp_resc,
		free_resc,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_NOSAVM,
		ATR_TYPE_RESC,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_Queue */

	{
		ATTR_queue,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		node_queue_action,
		MGR_ONLY_SET,
		ATR_TYPE_STR,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_Comment */

	{
		ATTR_comment,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		node_comment,
		NO_USER_SET | ATR_DFLAG_NOSAVM,
		ATR_TYPE_STR,
		PARENT_TYPE_NODE
	},

  /* ND_ATR_ResvEnable */

	{
		ATTR_NODE_resv_enable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_NoMultiNode */

	{
		ATTR_NODE_NoMultiNode,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		NULL_FUNC,
		MGR_ONLY_SET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_Sharing */

	{
		ATTR_NODE_Sharing,
		decode_sharing,
		encode_sharing,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_ProvisionEnable */

	{
		ATTR_NODE_ProvisionEnable,
		decode_b,
		encode_b,
		set_b,
		comp_b,
		free_null,
		node_prov_enable_action,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_BOOL,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_current_aoe */

	{
		ATTR_NODE_current_aoe,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		node_current_aoe_action,
		MGR_ONLY_SET | ATR_DFLAG_SSET,
		ATR_TYPE_STR,
		PARENT_TYPE_NODE
	},

   /* ND_ATR_in_multivnode_host */

	{
		ATTR_NODE_in_multivnode_host,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_MGRD | ATR_DFLAG_MGWR,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},


	{
		ATTR_NODE_License,
		decode_c,
		encode_c,
		set_c,
		comp_c,
		free_null,
		NULL_FUNC,
		READ_ONLY | ATR_DFLAG_SSET,
		ATR_TYPE_CHAR,
		PARENT_TYPE_NODE
	},


	{
		ATTR_NODE_LicenseInfo,
		decode_l,
		encode_l,
		set_l,
		comp_l,
		free_null,
		NULL_FUNC,
		ATR_DFLAG_SSET,
		ATR_TYPE_LONG,
		PARENT_TYPE_NODE
	},


	{
		ATTR_NODE_TopologyInfo,
		decode_str,
		encode_str,
		set_str,
		comp_str,
		free_str,
		set_node_topology,
		ATR_DFLAG_SSET,
		ATR_TYPE_STR,
		PARENT_TYPE_NODE
	},

	};
