'''
Schema of session information.
'''
import datajoint as dj
from pipeline import acquisition

schema = dj.schema('gao2018_behavior')

@schema
class TrialSet(dj.Manual):
    definition = """
    -> acquisition.Session
    ---
    number_of_trials:
    """
    class Trial(dj.Part):
        definition = """
        -> master
        trial_idx:
        ---
        """