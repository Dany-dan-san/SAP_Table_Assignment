# ==================================================
# 0. LIBRARY IMPORT
# ==================================================

import os
import pandas as pd
import numpy as np
import datetime

# =============================================================================================
# 1. SETTING UP THE FOLDER DIRECTORIES
# =============================================================================================

MAIN_FOLDER = os.getcwd()
SUB_PATH = "\\files"
FILES_PATH = f"{MAIN_FOLDER}{SUB_PATH}"

EKKO_PATH = f"{FILES_PATH}{"\\EKKO_clean.csv"}" # LISTS PURCHASING ORDERS
EKPO_PATH = f"{FILES_PATH}{"\\EKPO_clean.csv"}" # LISTS PO ITEMS
CDHDR_PATH = f"{FILES_PATH}{"\\CDHDR_clean.csv"}" # LISTS DATED HISTORY OF PO CHANGES
CDPOS_PATH = f"{FILES_PATH}{"\\CDPOS_clean.csv"}" # LISTS DETAILED PO CHANGES

# ==============================================================================================
# 2. SETTING UP FUNCTION PARAMETERS
# ==============================================================================================

# These are the default parameters of the function in case one or 
# more arguments are not provided by the user. 

# Either modify these default parameters or directly
# set up the arguments when using the function:

# e.g. gt_crtval(mandt = 10, ebeln = 72289190, date = datetime.datime(2019,2,23))

MANDT = 10
EBELN = 72109409
DATE = datetime.datetime(2021,12,3)

# =============================================================================================
# 3. CUSTOM FUNCTION
# =============================================================================================

def get_dated_netwr(mandt=None,ebeln=None,d_date=None,report=None):

    if mandt is None:
        mandt = MANDT
    if ebeln is None:
        ebeln = EBELN
    if d_date is None:
        d_date = DATE
    if report is None:
        report = True

    # ================================================
    # DATA FRAME SET UP
    # ================================================

    df_ekko = pd.read_csv(EKKO_PATH)    
    df_ekpo = pd.read_csv(EKPO_PATH)
    df_cdhdr = pd.read_csv(CDHDR_PATH)
    df_cdpos = pd.read_csv(CDPOS_PATH)

    # Filtering based on MANDT and EBELN
    df_ekko = df_ekko[(df_ekko["MANDT"] == mandt) & (df_ekko["EBELN"] == ebeln)]
    df_ekpo = df_ekpo[(df_ekpo["MANDT"] == mandt) & (df_ekpo["EBELN"] == ebeln)]
    df_cdhdr = df_cdhdr[(df_cdhdr["MANDANT"] == mandt) & (df_cdhdr["OBJECTID"] == ebeln)]
    df_cdpos = df_cdpos[(df_cdpos["MANDANT"] == mandt) & (df_cdpos["OBJECTID"] == ebeln)]
  
    # ================================================
    # KEY ASSUMPTION CHECKS
    # ================================================

    # 1. No empty df

    if df_ekko.empty or df_ekpo.empty:
        raise ValueError(
            f"Purchasing Order {ebeln} and/or Client {mandt} not found, "
            f"or no available PO items for Client {mandt}."
        )

    # 2. Target date verification

    target_date = pd.Timestamp(d_date)
    creation_date = pd.to_datetime(df_ekko["AEDAT"]).iloc[0]

    if pd.isna(target_date):
        raise ValueError("Invalid Target Date")

    if pd.isna(creation_date):
        raise ValueError("Invalid Creation Date")

    if target_date.normalize() < creation_date.normalize():
        raise ValueError(
            f"PO {ebeln} was created on {creation_date.date()}"
            f", after the requested date {target_date}"
        )

    # ================================================
    # SETTING UP START-UP OBJECTS
    # ================================================

    # Note. There are unexplained discrepancies between
    # EKPO items and CDPOS items. 

    po_items = df_ekpo["EBELP"]
    po_items = po_items.to_list()

    current_val = np.sum(df_ekpo["NETWR"])

    # ================================================
    # EXTRACTING AND RECONSTRUCTING DATA FROM CDHDR
    # ================================================
    changenr = df_cdhdr["CHANGENR"].to_list()
    dates = df_cdhdr["UDATE"].to_list()
    utimes = df_cdhdr["UTIME"].to_list()

    df_record = pd.DataFrame({
        "MANDANT": mandt,
        "CHANGENR":changenr,
        "DATE": dates,
        "UTIME": utimes
    })

    records_list = []

    for c in df_record["CHANGENR"]:

        subset = df_cdpos[df_cdpos["CHANGENR"] == c]
        subset = subset[(subset["FNAME"] == "NETWR") | (subset["FNAME"] == "KEY")]
        new_rows = subset[["MANDANT", "OBJECTID", "CHANGENR","TABKEY","FNAME", "CHNGIND"]].to_dict(orient="records")
        records_list.extend(new_rows)

    df_record_cdpos = pd.DataFrame(records_list, columns=["MANDANT", "OBJECTID","CHANGENR", "TABKEY", "FNAME", "CHNGIND"])

    df_record_cdpos = df_record_cdpos.merge(
        df_record[["CHANGENR", "DATE", "UTIME"]].rename(
            columns={"DATE": "UDATE"}
        ),
        on="CHANGENR",
        how="left"
    )

    df_record_cdpos = df_record_cdpos.sort_values(
        by=["UDATE", "UTIME"]
    ).reset_index(drop=True)

    df_record_cdpos = df_record_cdpos.merge(
    df_cdpos[df_cdpos["FNAME"] == "NETWR"][
        ["MANDANT", "CHANGENR", "TABKEY", "VALUE_NEW", "VALUE_OLD"]
    ],
    on=["MANDANT", "CHANGENR", "TABKEY"],
    how="left")

    po_items_cdpos = (

        df_record_cdpos["TABKEY"]
        .astype(str) # Convert to string
        .str[-5:] # Only keep 5 last digits
        .astype(int) # Convert to int
        .drop_duplicates() # Remove repeating instances
        .to_list() # Return as list
    )

    cdpos_to_ekpo_missing = set(po_items_cdpos) - set(po_items)

    if report == True:
        if cdpos_to_ekpo_missing:
            print("")
            print("***")
            print(f"ALERT: Mismatch between the unique PO items in CDPOS and those in EKPO.")
            print(f"   EKPO PO Items: {po_items}")
            print(f"   CDPOS PO Items: {po_items_cdpos}")
            print(f"   Mismatch PO Item(s): {cdpos_to_ekpo_missing}")
            print("***")
            print("")

        if len(cdpos_to_ekpo_missing) == 0:
            print("")
            print("***")
            print("CHECK: No structural mistmatch between EKPO and CDPOS")
            print("")
            print(f"EKKO PO ITEMS: {po_items}")
            print(f"CDPOS PO ITEMS: {po_items_cdpos}")
            print("***")
            print("")

    # ======================================================
    # HISTORICAL VALUE CALCULATION
    # ======================================================

    # This section is that which reconstructs the historical value 
    # calculation at {d_date}. Everything occurs within a single loop, 
    # with a combination of IF ELSE statements.
    
    items = []
    values = []
    dates = []
    times = []

    for item in po_items:

        subset = df_record_cdpos[
            df_record_cdpos["TABKEY"].astype(str).str[-5:] == f"{int(item):05d}"
        ].copy()

        subset["UDATE"] = pd.to_datetime(subset["UDATE"])
        subset["UTIME"] = pd.to_datetime(subset["UTIME"])

        # IF [TARGET ITEM] HAS RECORD(S) IN CDPOS, THEN WE NEED
        # TO INVESTIGATE ITS HISTORICAL CHANGES

        if not subset.empty:

            # WE DETERMINE IF ITEM HAS AN INSERTION EVENT 

            i_check = len(subset[subset["CHNGIND"] == "I"])

            if i_check != 0:

                # IF SO, WE EXTRACT THE INSERTION CREATION DATE

                i_date = subset.loc[subset["CHNGIND"] == "I", "UDATE"]
                i_date = pd.to_datetime(i_date).iloc[0]

                # WE DETERMINE IF ITEM WAS CREATED AFTER TARGET DATE

                if i_date.normalize() > target_date.normalize():

                    # IF SO, ITS VALUE IS SET TO 0, BECAUSE IT DID 
                    # NOT YET EXIST UP TO TARGET DATE. 

                    value = 0
                    d = pd.NaT
                    time = pd.NaT

                
                else:

                    # ELSE, WE MUST INVESTIGATE FURTHER.
                    # FIRST, WE LOOK FOR ITS NETWR UPDATE EVENTS

                    df_tracker = subset[(subset["CHNGIND"] == "U") & (subset["FNAME"] == "NETWR")].sort_values(by=["UDATE", "UTIME"])

                    if not df_tracker.empty:

                        # IF THERE ARE SOME NETWR UPDATE EVENTS,
                        # WE LOOK FOR THE LATEST EVENT UP TO TARGET
                        # DATE AND USE ITS 'VALUE_NEW' ENTRY TO
                        # DETERMINE THE ITEM VALUE UP TO TARGET DATE.

                        earliest = df_tracker.iloc[0]
                        value = earliest["VALUE_OLD"]

                        d = i_date
                        time = subset.loc[subset["CHNGIND"] == "I", "UTIME"].iloc[0]

                        for _, update in df_tracker.iterrows():

                            if update["UDATE"].normalize() <= target_date.normalize():
                                value = update["VALUE_NEW"]
                                d = update["UDATE"]
                                time = update["UTIME"]

                    # OTHERWISE, IF ITEM HAS NO UPDATE EVENTS, WE SET ITS VALUE
                    # TO THE CURRENT ITEM VALUE IN EKPO. 

                    else:
                        value = df_ekpo.loc[df_ekpo["EBELP"] == item, "NETWR"].iloc[0]
                        d = i_date
                        time = subset.loc[subset["CHNGIND"] == "I", "UTIME"].iloc[0]


            # NOW, IF ITEM HAS NO INSERTION EVENT, WE LOOK FOR ITS NETWR UPDATE EVENTS.
            else:

                # WE LOOK AT THE [NETWR][U] EVENTS UP TO TARGET DATE ONLY. 

                subset = subset[
                    (subset["CHNGIND"] == "U") &
                    (subset["FNAME"] == "NETWR")
                ].sort_values(by=["UDATE", "UTIME"])

                df_tracker = subset[
                    subset["UDATE"].dt.normalize() <= target_date.normalize()
                ]

                # IF THE ITEM HAS [NETWR][U] EVENTS UP TO TARGET DATE,
                # WE SET ITS VALUE TO THE LATEST EVENT'S NEW VALUE.

                if not df_tracker.empty:

                    latest = df_tracker.iloc[-1]
                    value = latest["VALUE_NEW"]
                    d = latest["UDATE"]
                    time = latest["UTIME"]

                # ELSE IF THE ITEM ONLY HAS [NETWR][U] AFTER THE TARGET DATE,
                # WE SET ITS VALUE TO THE EARLIEST EVENT'S OLD VALUE. 

                elif not subset.empty:

                    earliest = subset.iloc[0]
                    value = earliest["VALUE_OLD"]
                    d = pd.NaT
                    time = pd.NaT

                # ELSE IF THE ITEM HAS NO [NETWR][U] EVENTS AT ALL, WE USE
                # ITS CURRENT NETWR VALUE IN EKPO AS THE VALUE UP TO TARGET DATE.

                else:

                    value = df_ekpo.loc[
                        df_ekpo["EBELP"] == item, "NETWR"
                    ].iloc[0]
                    d = pd.NaT
                    time = pd.NaT

        # LASTLY, IF THE ITEM HAS NO [I] OR [U] RECORD IN CDPOS,
        # ITS VALUE UP TO TARGET DATE IS SET THE CURRENT VALUE
        # INSIDE EKPO. 

        else:
            value = df_ekpo[df_ekpo["EBELP"] == item]["NETWR"].iloc[0]
            d = df_ekko[df_ekko["EBELN"] == ebeln]["AEDAT"].iloc[0]
            time = datetime.time(0,0,0)     

        items.append(item)
        values.append(value)
        dates.append(d)
        times.append(time)      

    df_output = pd.DataFrame({
        "PO ITEM":items,
        "VALUE":values,
        "LATEST_UDATE":dates,
        "LATEST_UTIME":times
    })         

    df_output["VALUE"] = pd.to_numeric(df_output["VALUE"])
    total_value = df_output["VALUE"].sum()

    if report == True:

        print("===================================")
        print("CURRENT REPORT:")
        print("===================================")
        print(f"MANDT: {mandt}")
        print(f"PO IDENTIFIER: {ebeln}")
        print(f"PO UNIQUE ITEMS: {po_items}")
        print(f"CURRENT TOTAL NET ORDER VALUE: {current_val:,.2f}")
        print("")        

        print("================================================")
        print(f"TARGET REPORT FOR THE TARGET DATE:")
        print("================================================")

        print(f"MANDT:{mandt}")
        print(f"PO IDENTIFIER:{ebeln}")
        print(f"TARGET DATE: {target_date.date()}")
        print(f"TOTAL NET ORDER VALUE :{total_value:,.2f}")
        print("")
        print(df_output.to_string(
            index=False,
            formatters={"VALUE": "{:,.2f}".format}
        ))
        print("")
        print("================================================")
        print(f"FULL CDPOS TABLE FOR EBELN = {ebeln}")
        print("================================================")
        print(df_record_cdpos)

    return {

    "mandt":mandt,
    "ebeln":ebeln,
    "current_netwr":current_val,
    "total_netwr":total_value,
    "df_output":df_output,
    "df_record_cdpos":df_record_cdpos
    
}
            