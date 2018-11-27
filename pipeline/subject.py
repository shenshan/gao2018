'''
Schema of subject information.
'''
import datajoint as dj
from pipeline import reference

schema = dj.schema('gao2018_subject')


@schema
class Species(dj.Lookup):
    definition = """
    species_name: varchar(64)
    """
    contents = [['Mus musculus']]

@schema
class Strain(dj.Lookup):
    definition = """
    strain_id: varchar(64)
    """

@schema
class Subject(dj.Manual):
    definition = """
    subject_id: varchar(64)  # name of the subject
    ---
    -> Species
    -> Strain
    sex: enum('M', 'F', 'U')
    date_of_birth: date

    """
