"""
This module will retrieve core data from the web in order to enrich results from the main pubanalyser.
These sources are:
- OpenAPC dataset
    https://github.com/OpenAPC/openapc-de

    This dataset contains APC data for ~240.000 articles from 450 instutions. This data can be used both for direct APC information,
    but also to determine a better APC estimate for a given publisher/journal/year.

    The main data is stored as a CSV file. This script will retrieve that file, extract the relevant data, and store it as a parquet file.
    This can be loaded in by the main script to enrich the data.
"""
