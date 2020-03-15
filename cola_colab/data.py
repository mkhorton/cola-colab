import os
import pandas as pd
import numpy as np

from warnings import warn
from pathlib import Path
from monty.serialization import loadfn, dumpfn

DATA_DIR = Path(__file__).parent.absolute() / "data"

CAMPUSES = [
    "Berkeley",
    "Davis",
    "Irvine",
    "Los Angeles",
    "Merced",
    "Riverside",
    "San Diego",
    "San Francisco",
    "Santa Barbara",
    "Santa Cruz",
]


# UC-wide salary data from Transparent California
if not (DATA_DIR / "uc_salary_cache.parquet").is_file():

    warn(f"Cached data not found, re-downloading. Looked in {DATA_DIR}")

    # retrieve data for all years, and add additional column specifying year
    dfs = {}
    for year in range(2011, 2019):
        dfs[year] = pd.read_csv(
            f"https://transcal.s3.amazonaws.com/public/export/university-of-california-{year}.csv"
        )
        dfs[year]["Year"] = year

    # join individal dataframes into one master dataframe
    UC_WIDE_SALARY_DF = pd.concat(dfs.values())

    # exclude named employees (anyone with student status has their name redacted)
    # note that the inverse is not necessarily true: a redacted name does not imply student
    UC_WIDE_SALARY_DF = UC_WIDE_SALARY_DF[
        UC_WIDE_SALARY_DF["Employee Name"] == "Not provided"
    ]
    UC_WIDE_SALARY_DF.reset_index(drop=True, inplace=True)

    # prune columns to reduce memory usage
    UC_WIDE_SALARY_DF = UC_WIDE_SALARY_DF.drop(
        [
            "Employee Name",
            "Notes",
            "Agency",
            "Status",
            "Other Pay",
            "Overtime Pay",
            "Benefits",
        ],
        axis=1,
    )

    UC_WIDE_SALARY_DF.to_json(DATA_DIR / "uc_salary_cache.json.gz")

else:

    # specify dtypes to reduce memory usage
    # UC_WIDE_SALARY_DF = pd.read_json(
    #     DATA_DIR / "uc_salary_cache.json.gz",
    #     convert_axes=True,
    #     dtype={
    #         "Job Title": "category",
    #         "Year": "category",
    #         "Base Pay": np.float32,
    #         "Overtime Pay": np.float32,
    #         "Other Pay": np.float32,
    #         "Benefits": np.float32,
    #         "Total Pay": np.float32,
    #         "Total Pay & Benefits": np.float32,
    #     },
    # )
    UC_WIDE_SALARY_DF = pd.read_parquet(DATA_DIR / "uc_salary_cache.parquet")

# see most common job titles
cutoff = 1024  # individuals
MOST_COMMON_JOBS = [
    job_name
    for job_name, job_count in dict(
        UC_WIDE_SALARY_DF["Job Title"].value_counts()
    ).items()
    if job_count > cutoff
]

# specific column names to plot
PAY_TYPES = ("Base Pay", "Total Pay", "Total Pay & Benefits")


# HUD rental market data
HUD = pd.read_csv(DATA_DIR / "hud_data.csv")
# remove empty columns (excel artefact)
HUD = HUD.dropna(how="all")
HUD = HUD.dropna(how="all", axis="columns")

# UCOP survey of rent costs (2017)
SURVEY = pd.read_csv(DATA_DIR / "ucopsurvey_data.csv")
SURVEY = SURVEY.dropna(how="all")
SURVEY = SURVEY.dropna(how="all", axis="columns")

# re-index the dataframes
HUD = HUD.set_index(["UC", "Unit type"])
SURVEY = SURVEY.set_index("UC")

NET_STIPEND = pd.read_csv(
    DATA_DIR / "uc_net_stipend_per_capita_by_discipline_manual_phd.csv"
)
NET_STIPEND = NET_STIPEND.drop(["Source"], axis=1)
DISCIPLINES = tuple(NET_STIPEND["Discipline"].unique())
