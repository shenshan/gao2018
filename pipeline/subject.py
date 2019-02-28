'''
Schema of subject information.
'''
import datajoint as dj
from pipeline import reference

schema = dj.schema('gao2018_subject')


@schema
class Species(dj.Lookup):
    definition = """
    species: varchar(24)
    """
    contents = zip(['Mus musculus'])

@schema
class Strain(dj.Lookup):
    definition = """
    strain: varchar(24)
    """
    contents = zip(['000664', '012569'])

@schema
class Allele(dj.Lookup):
    definition = """
    allele: varchar(24)
    """
    contents = zip(['L7-cre', 'rosa26-lsl-ChR2-YFP'])

@schema
class Subject(dj.Manual):
    definition = """
    subject: varchar(16)  # name of the subject
    ---
    -> Species
    -> reference.AnimalSource
    sex: enum('M', 'F', 'U')
    date_of_birth: date
    """

@schema
class Zygosity(dj.Manual):
    definition = """
    -> Subject
    -> Allele
    ---
    zygosity:  enum('Homozygous', 'Heterozygous', 'Negative', 'Unknown')
    """