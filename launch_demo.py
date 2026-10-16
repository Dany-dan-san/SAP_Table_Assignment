from functions import get_dated_netwr
import datetime

# FUNCTION NAME: get_dated_netwr()

# FUNCTION ARGUMENTS:
#  - mandt: client identifier
#  - ebeln: PO identifier
#  - d_date: target date for value calculation

# Note: You can run the function without args, it will use
# default args intead. 

# object = get_dated_netwr()
# total_netwr = object["total_netwr"]
# print(total_netwr)

# Otherwise, set up your own arguments with this structure:

object = get_dated_netwr(10,72109409,datetime.datetime(2021,12,3),report=True)

# STRUCTURED OUTPUTS:

mandt = object["mandt"]
ebeln = object["ebeln"]
current_ntwr = object["current_netwr"]
total_netwr = object["total_netwr"]
df_output = object["df_output"]
df_record_cdpos = object["df_record_cdpos"]

print(total_netwr)