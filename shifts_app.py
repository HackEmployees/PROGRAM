import streamlit as st
import calendar
import csv
import io
import base64
import requests

from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Employee Availability",
    page_icon="📅",
    layout="wide"
)


# ============================================================
# SETTINGS
# ============================================================

DATA_FILE = "availability.csv"

WEEKDAY_SHIFTS = [
    "03:30-07:30",
    "07:30-15:00",
    "15:00-21:30",
    "21:30-03:30",
]

WEEKEND_SHIFTS = [
    "03:30-11:30",
    "11:30-19:30",
    "19:30-03:30",
]

HOLIDAY_SHIFTS = [
    "03:30-11:30",
    "11:30-19:30",
    "19:30-03:30",
]


# ============================================================
# STREAMLIT SECRETS
# ============================================================

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_OWNER = st.secrets["GITHUB_OWNER"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
    GITHUB_BRANCH = st.secrets.get(
        "GITHUB_BRANCH",
        "data"
    )
    MANAGER_PASSWORD = st.secrets["MANAGER_PASSWORD"]

except Exception:
    st.error(
        "GitHub settings or Manager password "
        "are missing from Streamlit Secrets."
    )
    st.stop()


# ============================================================
# GITHUB API
# ============================================================

GITHUB_API = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
    f"{DATA_FILE}"
)


def github_headers():

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ============================================================
# READ DATA FROM GITHUB
# ============================================================

def read_data():

    response = requests.get(
        GITHUB_API,
        headers=github_headers(),
        params={
            "ref": GITHUB_BRANCH
        },
        timeout=20,
    )

    # --------------------------------------------------------
    # File does not exist yet
    # --------------------------------------------------------

    if response.status_code == 404:
        return [], None
