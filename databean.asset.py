##==============================================================================
#*   Launch Point NAME: DATABEAN.ASSET
#* 
#*   PURPOSE: To build WhereClause for Assettype/Spec/Factors
#*
#*   REVISIONS:
#*   Ver        Date              Author                             Description
#*   ---------  ---------- ---  ---------- ---------------  -----------------------------------
#*   1          29/12/2025      Pavan Uppalanchu          MAS-6743 :Advance Filter for Asset Application
#*   2          09/04/2026      Pavan Uppalanchu          Advance Filter for Asset Application - Additional Features
#*   3          05/07/2026      Pavan Uppalanchu          Rev 2 : To modify Factor Driver Columns
#*
#***************************** End Standard Header ****************************
#================================================================================

from psdi.server import MXServer
from psdi.util.logging import MXLoggerFactory
from psdi.mbo import MboConstants

# Initialize Logger
logger = MXLoggerFactory.getLogger("maximo.script")

def initialize (ctx):
    
    wcs = ctx.webclientsession()
    app = wcs.getCurrentApp()
    appBean = app.getAppBean()
    
    # Initiliaze Default Operators in between sections.
    
    appBean.setQbe("EG_ANDOR1", 'AND')
    appBean.setQbe("EG_ANDOR2", 'AND')
    appBean.setQbe("EG_ANDOR3", 'OR')
    appBean.setQbe("EG_ANDOR4", 'OR')
    appBean.setQbe("EG_ANDOR5", 'OR')
    
    # Default row for KPI Values
    
    kpibean = app.getDataBean("eg_kpi")
    kpibeanSet = kpibean.getMboSet()
    if kpibeanSet.isEmpty():
        kpibeanSet.add()


# Below Action gets executed when user clicks FIND Button 
#ctx is context to pass for a method in Bean classes

def eg_Filtergaps_bean(ctx):
    # 1. Initialize UI and App Beans
    wcs = ctx.webclientsession()
    app = wcs.getCurrentApp()
    resultsBean = app.getResultsBean()
    appBean = app.getAppBean()
    
    # 2. Collect Inputs for AND OR Values between the sections

    and_or_healthkpi = appBean.getQbe("EG_ANDOR1")
    andOr1 = and_or_healthkpi.upper() if (and_or_healthkpi and and_or_healthkpi.strip()) else "AND"
    
    and_or_location = appBean.getQbe("EG_ANDOR2")
    andOr2 = and_or_location.upper() if (and_or_location and and_or_location.strip()) else "AND"
    
    and_or_assetflds = appBean.getQbe("EG_ANDOR3")
    andOr3 = and_or_assetflds.upper() if (and_or_assetflds and and_or_assetflds.strip()) else "OR"
    
    and_or_attributeflds = appBean.getQbe("EG_ANDOR4")
    andOr4 = and_or_attributeflds.upper() if (and_or_attributeflds and and_or_attributeflds.strip()) else "OR"
    
    and_or_factorsAndDriverflds = appBean.getQbe("EG_ANDOR5")
    andOr5 = and_or_factorsAndDriverflds.upper() if (and_or_factorsAndDriverflds and and_or_factorsAndDriverflds.strip()) else "OR"
    
    where_parts = [] # We will store all valid SQL fragments here
    global_operators = [] # will store in between Operators
    
    #Grouping for Asset, Specification, Factors and Drivers, Paiting Works
    group_parts = [] 
    group_operators = []
    
    # Health KPIs
    
    Health_search_bean = app.getDataBean("eg_kpi")
    Health_Set = Health_search_bean.getMboSet()
    health_mbo = Health_Set.moveFirst()
    if health_mbo:
        kpi_values = {
        "risk_category": health_mbo.getString("EG_RISKCATEGORY"),
        "health_indicator": health_mbo.getString("EG_ASSETHEALTH"),
        "pof_category": health_mbo.getString("EG_FAILURE"),
        "impact_cos": health_mbo.getString("EG_CRITICALITY")
    }

    # 2. Build the inner WHERE conditions only for non-empty values
    inner_where_parts = []
    for column, value in kpi_values.items():
        if value: # Check if the user actually selected something
            inner_where_parts.append("v.{} = '{}'".format(column, value))

    # 3. If at least one KPI was selected, build the final subquery
    if inner_where_parts:
        inner_where_clause = " AND ".join(inner_where_parts)
        inner_where_clause = inner_where_clause + " and v.report_year = YEAR(CURRENT DATE) " 
        
        
        exists_clause = "exists (select 1 from maximo.eg_risk_report v  where v.assetid = asset.assetid and v.siteid = asset.siteid  and {0})".format(inner_where_clause)
                    
        where_parts.append("(" + exists_clause + ")")
        global_operators.append(andOr1)
        
    # Location  Search 
    location_search_bean = app.getDataBean("eg_advsearchlocations")
    locationClause = buildClauseFromLocationSearch (location_search_bean, ctx)
    if locationClause:
         where_parts.append("(" + locationClause + ")")
         global_operators.append(andOr2)   
         
    # Asset Fields Search - 
    assetField_search_bean = app.getDataBean("eg_assetfields_table")
    assetFieldClause = buildClauseFromFieldSearch (assetField_search_bean, ctx)
    if assetFieldClause:
         group_parts.append("(" + assetFieldClause + ")")
         group_operators.append(andOr3)


    # 4. Process Table 1: Standard Specifications  Search
    attribute_search_bean = app.getDataBean("eg_SEARCHATTR_table")
    generated_where = buildClauseFromAttrSearch(attribute_search_bean,ctx)        
    if generated_where:
        group_parts.append("({})".format(generated_where))
        group_operators.append(andOr4)
    

    # 5. Process Table 2: Drivers and Factors
    factors_bean = app.getDataBean("eg_Factors_Drivers_table")
    Factors_whereClause = buildClauseFromFactorsAndDriverSearch(factors_bean,ctx) 
    if Factors_whereClause:
        group_parts.append("({})".format(Factors_whereClause))
        group_operators.append(andOr5)
            
    # 6. Process Table : PaintWorks Search
    paintWorks_search_bean = app.getDataBean("eg_PaintingWorks_table")
    generated_where = buildClauseFromPaintWorks(paintWorks_search_bean,ctx)        
    
    
    if generated_where:
        group_parts.append("({})".format(generated_where))
        
    if group_parts:
        grouped_sql = ""
        for i in range(len(group_parts)):
            if i == 0:
                grouped_sql = group_parts[i]
            else:
                op = group_operators[i-1]
                grouped_sql = "%s %s %s" % (grouped_sql, op, group_parts[i])
            
        
        # Wrap the entire result in an extra set of outer brackets
        final_grouped_clause = "( %s )" % grouped_sql
        where_parts.append(final_grouped_clause)
    

    # 6. Assemble Final SQL and Update UI
    final_sql = ""
    appBean.resetQbe()
    if where_parts:
    
        for i in range(len(where_parts)):
            if i == 0:
                final_sql = where_parts[i]
            else:
                # Take the operator from the PREVIOUS section to join this one
                op = global_operators[i-1] 
                final_sql = "%s %s %s" % (final_sql, op, where_parts[i])
        
        
        resultsBean.setUserWhere(final_sql)
        resultsBean.reset()
        
        # Refresh the table state and close
        resultsBean.getTableStateFlags().setFlag(256, True)
        ctx.closeDialog()
        ctx.setEventHandled()
    else:
        # If no search criteria were entered, just close the dialog
        ctx.closeDialog()
        ctx.error("eg_advsearch","eg_assetadvsearch", None)
        
def buildClauseFromLocationSearch(locationSearch,ctx):

    if not locationSearch:
        return ""
    
    dialogset = locationSearch.getMboSet()
    # Check if set is null or empty
    if not dialogset or dialogset.isEmpty():
        return ""
    
    clause = ""
    allRowsEmpty = True
    firstValidRow = True
    pendingOp = "OR" # Default operator
    
    # Iterate through the MboSet
    locationMbo = dialogset.moveFirst()
    i = 0
    while locationMbo:
        # Skip if marked for deletion
        if locationMbo.toBeDeleted():
            locationMbo = dialogset.moveNext()
            i += 1
            continue
            
        location = locationMbo.getString("EG_LOCATION")
        rowAndOr = locationMbo.getString("EG_ANDOR")
        
        # Skip if location is empty (None or whitespace)
        if not location or not location.strip():
            locationMbo = dialogset.moveNext()
            i += 1
            continue
            
        allRowsEmpty = False
        queryType = locationMbo.getString("EG_LOCTYPE")
        
        # Build the condition fragment
        if queryType == "ONLYONE":
            condition = "location = '{0}'".format(location.replace("'", "''"))
        else:
            # Hierarchical search using LOCANCESTOR
            condition = ("location IN (SELECT locancestor.location FROM locancestor "
                         "WHERE locancestor.ancestor = '{0}')").format(location.replace("'", "''"))
        
        # Determine current row operator
        thisRowOp = "OR"
        if rowAndOr and rowAndOr.strip():
            thisRowOp = rowAndOr.strip().upper()
            
        # Handle Clause Assembly
        if firstValidRow:
            clause = condition
            firstValidRow = False
            pendingOp = thisRowOp
        else:
            # Connect using the operator from the PREVIOUS row (as per your Java logic)
            connectOp = " AND " if pendingOp == "AND" else " OR "
            clause =  clause  + connectOp  + condition 
            pendingOp = thisRowOp
            
        locationMbo = dialogset.moveNext()
        i += 1
        
    if allRowsEmpty:
        return ""
        
    return clause
    
def Empty(value, ctx):
    # If it's None, it's empty
    if value is None:
        return True
    # If it's a string, check for whitespace
    if isinstance(value, str) or isinstance(value, unicode):
        return not value.strip()
    # If it's a number (int, float, long), it's not empty
    if isinstance(value, (int, float, long)):
        return False
    return not value
    
def buildSingleFieldRowClausePart(assetType, assetField, specValue, operator, ctx):
    """
    Builds the SQL fragment for a single row.
    """
    clausePart = '' 
    if assetType or assetField:
    # If the field name is empty, build a clause only for ASSETTYPE
        if Empty(assetField, ctx):
            clausePart = "assettype = '%s' " % ((assetType))
            logger.debug("Asset Search Row with AssetType-only condition: " + clausePart)
            return clausePart
    
        op = operator
        
        logger.debug("ASSET search: assetType={0}, field={1}, value='{2}', operator={3}".format(assetType, assetField, specValue, op))
    
        if not Empty(specValue, ctx):
            # Case when a value is provided
            safeValue = specValue.replace("'", "''")
            
            if op == "Contains (for text)":
                condition = "UPPER({0}) LIKE UPPER('%{1}%')".format(assetField, safeValue)
            elif op == "Equal to":
                condition = "{0} = '{1}'".format(assetField, safeValue)
            elif op == "Greater than equal to":
                condition = "{0} >= '{1}'".format(assetField, safeValue)
            elif op == "Greater than":
                condition = "{0} > '{1}'".format(assetField, safeValue)
            elif op == "Less than equal to":
                condition = "{0} <= '{1}'".format(assetField, safeValue)
            elif op == "Less than":
                condition = "{0} < '{1}'".format(assetField, safeValue)
            elif op == "Not equal to":
                condition = "{0} != '{1}'".format(assetField, safeValue)
            else: # default OPERATOR to equals to
                condition = "{0} = '{1}'".format(assetField, safeValue)
                
            if assetType:
                clausePart = "(ASSETTYPE = '{0}' AND {1})".format(assetType.replace("'", "''"), condition)
            else:
                clausePart = "({0})".format(condition)
        else:
            # Case when value is empty
            condition = "{0} IS NULL".format(assetField)
            if assetType:
                clausePart = "(ASSETTYPE = '{0}' AND {1})".format(assetType.replace("'", "''"), condition)
            else:
                clausePart = "({0})".format(condition)

    return clausePart
    
def buildClauseFromFieldSearch(fieldSearch, ctx):
    """
    Main logic to iterate through the Asset Fields DataBean and build the full clause.
    """
    if fieldSearch is None:
        return ""
        
    dialogset = fieldSearch.getMboSet()
    if not dialogset or dialogset.isEmpty():
        return ""
        
    clause = ""
    allRowsEmpty = True
    firstValidRow = True
    pendingOp = "OR" # Initial default
    
    # Iterate through each row in the table
    for i in range(dialogset.count()):
        searchmbo = dialogset.getMbo(i)
        
        if not searchmbo or searchmbo.toBeDeleted():
            continue
            
        logger.debug("Processing Asset Search  Mbo {0}".format(i))
        
        # Extract values
        assetType = searchmbo.getString("EG_ASSETTYPE")
        assetField = searchmbo.getString("EG_ASSETFIELDS")
        specValue = searchmbo.getString("EG_ASSETFIELDVALUES")
        operator = searchmbo.getString("EG_OPERATOR")
        rowAndOr = searchmbo.getString("EG_ANDOR")
        
        allRowsEmpty = False
        thisRowOp = rowAndOr.upper() if not Empty(rowAndOr, ctx) else "OR"
        
        # Build fragment for this row
        clausePart = buildSingleFieldRowClausePart(assetType, assetField, specValue, operator, ctx)
        
        if Empty(clausePart,ctx):
            continue
            
        logger.debug("Asset Search Row {0} thisOp: '{1}', pendingOp: '{2}', clausePart: {3}".format(i, thisRowOp, pendingOp, clausePart))
        
        if firstValidRow:
            clause = clausePart
            firstValidRow = False
            pendingOp = thisRowOp
        else:
            # Combine with previous conditions using the operator from the PREVIOUS row
            connectOp = " AND " if pendingOp == "AND" else " OR "
            clause = " {0} {1} {2}".format(clause, connectOp, clausePart)
            pendingOp = thisRowOp
            
    if allRowsEmpty:
        return ""
        
    logger.debug("Final Asset Search  clause: " + clause)
    return clause
    

def buildClauseFromAttrSearch(AttrSearch, ctx):
    """
    Main logic to iterate through the Specifications Search DataBean and build the full clause.
    """
    
    if AttrSearch is None:
        return ""
        
    dialogset = AttrSearch.getMboSet()
    if not dialogset or dialogset.isEmpty():
        return ""
        
    clause = ""
    allRowsEmpty = True
    firstValidRow = True
    pendingOp = "OR" # Initial default
    
    # Iterate through each row in the table
    for i in range(dialogset.count()):
        searchmbo = dialogset.getMbo(i)
        
        if not searchmbo or searchmbo.toBeDeleted():
            continue
            
        logger.debug("Processing Specification Search Mbo {0}".format(i))
        
        # Extract values
        attrassettype = searchmbo.getString("EG_ASSETTYPE")
        rowAndOr = searchmbo.getString("EG_ANDOR")
        ac_service = MXServer.getMXServer().lookup("ASSETCATALOG")
        #generated_where = ac_service.attributesSearch(wcs.getUserInfo(), appBean.getMboName(), attribute_set)
        attributesAndValues = [[None for j in range(5)] for i in range(1)]

        if searchmbo and not searchmbo.toBeDeleted():
            wcs = ctx.webclientsession()
            app = wcs.getCurrentApp()
            appBean = app.getAppBean()
            attributesAndValues[0][0] = searchmbo.getString("assetattrid")
            attributesAndValues[0][1] = searchmbo.getString("specValue")
            attributesAndValues[0][4] = searchmbo.getString("section")
    
    # Call existing Java methods
        attrsAndValues = ac_service.convertList(wcs.getUserInfo(), attributesAndValues)
        clausePart_attr = ac_service.getClassAndAttributesSearchWhere(wcs.getUserInfo(),appBean.getMboName(),None,attrsAndValues,None,None)
        
        if attrassettype and clausePart_attr:
        
            clausePart = "(ASSETTYPE = '" + attrassettype + "' AND " + clausePart_attr + ")"
            
        else: 
            clausePart = clausePart_attr
            
        allRowsEmpty = False
        thisRowOp = rowAndOr.upper() if not Empty(rowAndOr, ctx) else "OR"
        
        # Build fragment for this row
        
        if Empty(clausePart,ctx):
            continue
            
        logger.debug("Specification Search Row {0} thisOp: '{1}', pendingOp: '{2}', clausePart: {3}".format(i, thisRowOp, pendingOp, clausePart))
        
        if firstValidRow:
            clause = clausePart
            firstValidRow = False
            pendingOp = thisRowOp
        else:
            # Combine with previous conditions using the operator from the PREVIOUS row
            connectOp = " AND " if pendingOp == "AND" else " OR "
            clause = "{0}{1}{2}".format(clause, connectOp, clausePart)
            pendingOp = thisRowOp
            
    if allRowsEmpty:
        return ""
        
    logger.debug("Final Specifications Search clause: " + clause)
    return clause
    
def buildSinglePaintWorksRowClausePart(assetType, assetField, specValue, operator, ctx):
    """
    Builds the SQL fragment for a single row.
    """
    clausePart = '' 
    if assetType or assetField:
    # If the field name is empty, build a clause only for ASSETTYPE
        if Empty(assetField, ctx):
            return clausePart
    
        op = operator
        
        logger.debug("Processing Paint Works Row ASSET search: assetType={0}, field={1}, value='{2}', operator={3}".format(assetType, assetField, specValue, op))
    
        if not Empty(specValue, ctx):
            # Case when a value is provided
            safeValue = specValue.replace("'", "''")
            user_filters = ""
            
            if op == "Contains (for text)":
                condition = " UPPER({0}) LIKE UPPER('%{1}%')".format(assetField, safeValue)
            elif op == "Equal to":
                condition = " b.{0} = '{1}'".format(assetField, safeValue)
            elif op == "Greater than equal to":
                condition = " b.{0} >= '{1}'".format(assetField, safeValue)
            elif op == "Greater than":
                condition = " b.{0} > '{1}'".format(assetField, safeValue)
            elif op == "Less than equal to":
                condition = " b.{0} <= '{1}'".format(assetField, safeValue)
            elif op == "Less than":
                condition = " b.{0} < '{1}'".format(assetField, safeValue)
            elif op == "Not equal to":
                condition = "  b.{0} != '{1}'".format(assetField, safeValue)
            else: # default OPERATOR to equals to
                condition = " b.{0} = '{1}'".format(assetField, safeValue)
                
            if assetType:
                user_filters = " and asset.ASSETTYPE = '{0}' AND {1}".format(assetType.replace("'", "''"), condition)
            else:
                user_filters = " and {0}".format(condition)
                
        else:
            # Case when value is empty
            condition = " b.{0} IS NULL".format(assetField)
            if assetType:
                user_filters = " and asset.ASSETTYPE = '{0}' AND {1}".format(assetType.replace("'", "''"), condition)
                
            else:
                user_filters = " and {0}".format(condition)
            
        sql_template = """
        exists (
            select 1 from EG_TOWER_PAINTING_COMP b 
            where b.eg_assetnum = asset.assetnum 
            and b.siteid = asset.siteid
            {user_filters}
            and b.EG_MAINT_START_YEAR = (
                select max(c.EG_MAINT_START_YEAR) 
                from EG_TOWER_PAINTING_COMP c 
                where c.eg_assetnum = b.eg_assetnum 
                and c.siteid = b.siteid
            )
        )
        """
        if user_filters:
            clausePart = sql_template.format(user_filters=user_filters)

    return clausePart
    
def buildClauseFromPaintWorks(PaintingWorksSearch, ctx):
    """
    Main logic to iterate through the DataBean and build the full clause.
    """
    if PaintingWorksSearch is None:
        return ""
        
    dialogset = PaintingWorksSearch.getMboSet()
    if not dialogset or dialogset.isEmpty():
        return ""
        
    clause = ""
    allRowsEmpty = True
    firstValidRow = True
    pendingOp = "OR" # Initial default
    
    # Iterate through each row in the table
    for i in range(dialogset.count()):
        searchmbo = dialogset.getMbo(i)
        
        if not searchmbo or searchmbo.toBeDeleted():
            continue
            
        logger.debug("Processing Paint Works Mbo {0}".format(i))
        
        # Extract values
        assetType = searchmbo.getString("EG_ASSETTYPE")
        paintworksField = searchmbo.getString("EG_TOWERPAINTFIELD")
        paintworksFieldValue = searchmbo.getString("EG_TOWERPAINTFIELDVALUE")
        operator = searchmbo.getString("EG_OPERATOR")
        rowAndOr = searchmbo.getString("EG_ANDOR")
        
        allRowsEmpty = False
        thisRowOp = rowAndOr.upper() if not Empty(rowAndOr, ctx) else "OR"
        
        # Build fragment for this row
        clausePart = buildSinglePaintWorksRowClausePart(assetType, paintworksField, paintworksFieldValue, operator, ctx)
        
        if Empty(clausePart,ctx):
            continue
            
        logger.debug("Tower Paint Works Row {0} thisOp: '{1}', pendingOp: '{2}', clausePart: {3}".format(i, thisRowOp, pendingOp, clausePart))
        
        if firstValidRow:
            clause = clausePart
            firstValidRow = False
            pendingOp = thisRowOp
        else:
            # Combine with previous conditions using the operator from the PREVIOUS row
            connectOp = " AND " if pendingOp == "AND" else " OR "
            clause = "{0}{1}{2}".format(clause, connectOp, clausePart)
            pendingOp = thisRowOp
            
    if allRowsEmpty:
        return ""
        
    logger.debug("Final Paint Works clause: " + clause)
    return clause
    
def buildSingleFactorsAndDriverRowClausePart(assetType, assetField, specValue, operator, ctx):
    """
    Builds the SQL fragment for a single row.
    """
    clausePart = '' 
    if assetType or assetField:
    # If the field name is empty, build a clause only for ASSETTYPE
        if Empty(assetField, ctx):
            clausePart = "assettype = '%s' " % ((assetType))
            logger.debug("AssetType-only condition: " + clausePart)
            return clausePart
    
        op = operator
        
        logger.debug("Factor and Driver Row ASSET search: assetType={0}, field={1}, value='{2}', operator={3}".format(assetType, assetField, specValue, op))
    
        if not Empty(specValue, ctx):
            # Case when a value is provided
            safeValue = specValue
            
            if op == "Equal to":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE = {1}".format(assetField,safeValue)
            elif op == "Greater than equal to":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE >= {1}".format(assetField,safeValue)
            elif op == "Greater than":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE > {1}".format(assetField,safeValue)
            elif op == "Less than equal to":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE <= {1}".format(assetField,safeValue)
            elif op == "Less than":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE < {1}".format(assetField,safeValue)
            elif op == "Not equal to":
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE != {1}".format(assetField,safeValue)
            else: # default OPERATOR to equals to
                condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE = {1}".format(assetField,safeValue)
                
            if assetType:
                user_filters = "(b.ASSETTYPE = '{0}' AND {1})".format(assetType.replace("'", "''"), condition)
            else:
                user_filters = "({0})".format(condition)
                
        else:
            # Case when value is empty
            condition = " b.DRIVER_FACTOR_NAME = '{0}' and b.VALUE IS NULL".format(assetField)
            if assetType:
                user_filters = "(b.ASSETTYPE = '{0}' AND {1})".format(assetType.replace("'", "''"), condition)
                
            else:
                user_filters = "({0})".format(condition)
            
        sql_template = """ asset.assetid in (select b.ownerrecordid from maximo.eg_v_drivers_factors b where
            {user_filters})
            """
        clausePart = sql_template.format(user_filters=user_filters)

    return clausePart
    
def buildClauseFromFactorsAndDriverSearch(fieldSearch, ctx):
    """
    Main logic to iterate through the Factors and Drivers DataBean and build the full clause.
    """
    if fieldSearch is None:
        return ""
        
    dialogset = fieldSearch.getMboSet()
    if not dialogset or dialogset.isEmpty():
        return ""
        
    clause = ""
    allRowsEmpty = True
    firstValidRow = True
    pendingOp = "OR" # Initial default
    
    # Iterate through each row in the table
    for i in range(dialogset.count()):
        searchmbo = dialogset.getMbo(i)
        
        if not searchmbo or searchmbo.toBeDeleted():
            continue
            
        logger.debug("Processing FIELD Factors AndDriverMbo {0}".format(i))
        
        # Extract values
        assetType = searchmbo.getString("EG_ASSETTYPE")
        FactorAndDriverField = searchmbo.getString("EG_DRIVER_OR_FACTOR_DESC")
        FactorAndDriverValue = searchmbo.getDouble("EG_DRIVER_FACTOR_VALUE")
        operator = searchmbo.getString("EG_OPERATOR")
        rowAndOr = searchmbo.getString("EG_ANDOR")
        
        allRowsEmpty = False
        thisRowOp = rowAndOr.upper() if not Empty(rowAndOr, ctx) else "OR"
        
        # Build fragment for this row
        clausePart = buildSingleFactorsAndDriverRowClausePart(assetType, FactorAndDriverField, FactorAndDriverValue, operator, ctx)
        
        if Empty(clausePart,ctx):
            continue
            
        logger.debug("Row {0} thisOp: '{1}', pendingOp: '{2}', clausePart: {3}".format(i, thisRowOp, pendingOp, clausePart))
        
        if firstValidRow:
            clause = clausePart
            firstValidRow = False
            pendingOp = thisRowOp
        else:
            # Combine with previous conditions using the operator from the PREVIOUS row
            connectOp = " AND " if pendingOp == "AND" else " OR "
            clause = "{0}{1}{2}".format(clause, connectOp, clausePart)
            pendingOp = thisRowOp
            
    if allRowsEmpty:
        return ""
        
    logger.debug("Final FIELD clause for Factors and Drivers: " + clause)
    return clause
    
    
def eg_assetadvdialogcancel(ctx):
    wcs = ctx.webclientsession()
    app = wcs.getCurrentApp()
    appBean = app.getAppBean()
    appBean.setQbe("EG_ANDOR1", '')
    appBean.setQbe("EG_ANDOR2", '')
    appBean.setQbe("EG_ANDOR3", '')
    appBean.setQbe("EG_ANDOR4", '')
    appBean.setQbe("EG_ANDOR5", '')
    ctx.closeDialog()