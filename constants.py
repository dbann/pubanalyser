"""
This module contains all constants used in the pubanalyser app.
Change these values to adapt the app to your needs.
"""

# This email address will be included in the API calls to OpenAlex.
USER_EMAIL: str = 'david.bann@ucl.ac.uk'

# max number of publications processed by the app during analysis
MAX_NUM: int = 2000

FOR_PROFIT_PUBLISHERS: set = {
    'elsevier', 'springer', 'springer nature', 'wiley', 'taylor & francis',
    'sage publications', 'frontiers media sa', 'ieee', 'emerald', 'karger',
    'thieme', 'wolters kluwer', 'acs publications', 'lippincott',
    'lippincott williams & wilkins', 'wolters kluwer health',
    'nature publishing group', 'nature portfolio', 'biomed central',
    'biomedcentral', 'bmc', 'hindawi', 'mdpi', 'informa', 'f1000', 'relx',
    'relx group', 'bentham science', 'inderscience', 'igi global', 'sciencedirect',
    'de gruyter', 'sciendo', 'omics international', 'rsc publishing',
}

PREPRINT_SERVERS: set[str] = {
    'cold spring harbor laboratory',
    'biorxiv',
    'medrxiv',
    'arxiv',
    'ssrn'
}

COMPANY_ABBREVIATIONS: list[str] = [
    ' ltd ',
    ' limited ',
    ' bv ',
    ' gmbh ',
    ' inc ',
    ' llc ',
    ' co ',
    ' corp ',
    ' corporation ',
    ' sarl ',
    ' sa ',
    ' pte ',
    ' pty ',
    ' plc ',
    ' ag ',
    ' sl ',
    ' srl ',
    ' ag ',
]



PUBLISHER_NAME_MAPPING = {
    'elsevier': 'elsevier',
    'sciencedirect': 'elsevier',
    'cell press': 'elsevier',
    'relx group': 'elsevier',
    'springer': 'springer nature',
    'nature portfolio': 'springer nature',
    'nature publishing': 'springer nature',
    'wiley': 'wiley',
    'blackwell': 'wiley',
    'taylor & francis': 'taylor & francis',
    'taylor and francis': 'taylor & francis',
    'routledge': 'taylor & francis',
    'wolters': 'wolters kluwer',
    'lippincott': 'wolters kluwer',
    'biomed central': 'biomed central',
    'bmc': 'biomed central',
    'biomedcentral': 'biomed central',
    'sage': 'sage publications',
    'frontiers': 'frontiers media sa',
    'ieee': 'ieee',
    'karger': 'karger',
    'thieme': 'thieme',
    'hindawi': 'hindawi',
    'mdpi': 'mdpi',
    'plos': 'plos',
    'public library of science': 'plos',
    'oxford university press': 'oxford university press',
    'cambridge university press': 'cambridge university press'
}
# These are placeholder values for APCs if all of the below are true:
# - neither OpenAPC nor OpenAlex has APC data for the item
# - the item has no publisher information
# - it was not possible to make a better estimate using OpenAPC data

ESTIMATED_APC = {
    'elsevier': 3000,
    'springer nature': 2800,
    'wiley': 2500,
    'taylor & francis': 2400,
    'sage publications': 2000,
    'frontiers media sa': 2950,
    'ieee': 2000,
    'emerald': 2800,
    'karger': 2800,
    'thieme': 2500,
    'wolters kluwer': 2500,
    'biomed central': 2000,
    'plos': 1700,
    'default': 1500
}
