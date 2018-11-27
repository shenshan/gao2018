'''
Schema of session information.
'''
import datajoint as dj
from pipeline import acquisition

schema = dj.schema('gao2018_ephys')

@schema
class Session(dj.Manual):
    definition = """
    -> Subject
    session_date: date    # session date
    ---
    session_directory: 
    session_note: varchar(256) # 
    """