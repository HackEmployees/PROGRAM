import streamlit as st
import calendar
import csv
import io
import base64
import requests

from datetime import date, timedelta


# ============================================================
# CONFIGURATION
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
# PAGE
# ============================================================

st.set_page_config(
    page_title="Shift Availability",
    page_icon="📅",
    layout="wide"
)


# ============================================================
# GITHUB SECRETS
# ============================================================

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_OWNER = st.secrets["GITHUB_OWNER"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]

    GITHUB_BRANCH = st.secrets.get(
        "GITHUB_BRANCH",
        "data"
    )

except Exception:
    st.error(
        "GitHub settings are missing from "
        "Streamlit Secrets."
    )
    st.stop()


# ============================================================
# GITHUB API
# ============================================================

GITHUB_URL = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/"
    f"{GITHUB_REPO}/contents/"
    f"{DATA_FILE}"
)


def github_headers():

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ============================================================
# READ CSV
# ============================================================

def read_availability():

    response = requests.get(
        GITHUB_URL,
        headers=github_headers(),
        params={
            "ref": GITHUB_BRANCH
        },
        timeout=20
    )

    if response.status_code == 404:

        return [], None

    if not response.ok:

        raise Exception(
            f"GitHub error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    sha = data["sha"]

    encoded = data["content"].replace(
        "\n",
        ""
    )

    decoded = base64.b64decode(
        encoded
    ).decode(
        "utf-8"
    )

    reader = csv.DictReader(
        io.StringIO(decoded)
    )

    return list(reader), sha


# ============================================================
# SAVE CSV
# ============================================================

def save_availability(
    rows,
    sha=None
):

    output = io.StringIO()

    fieldnames = [
        "email",
        "work_date",
        "shift"
    ]

    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames
    )

    writer.writeheader()

    for row in rows:

        writer.writerow({
            "email": row["email"],
            "work_date": row["work_date"],
            "shift": row["shift"]
        })

    encoded = base64.b64encode(
        output.getvalue().encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": "Update employee availability",
        "content": encoded,
        "branch": GITHUB_BRANCH
    }

    if sha:

        payload["sha"] = sha

    response = requests.put(
        GITHUB_URL,
        headers=github_headers(),
        json=payload,
        timeout=20
    )

    if response.status_code not in (
        200,
        201
    ):

        raise Exception(
            f"GitHub save error "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# CYPRUS HOLIDAYS
# ============================================================

FIXED_HOLIDAYS = {

    (1, 1): "New Year's Day",
    (1, 6): "Epiphany",
    (3, 25): "Greek National Day",
    (4, 1): "Cyprus National Day",
    (5, 1): "Labour Day",
    (8, 15): "Assumption",
    (10, 1): "Cyprus Independence Day",
    (10, 28): "Ohi Day",
    (12, 25): "Christmas Day",
    (12, 26): "Boxing Day",
}


# ============================================================
# ORTHODOX EASTER
# ============================================================

def orthodox_easter(year):

    a = year % 4
    b = year % 7
    c = year % 19

    d = (
        19 * c + 15
    ) % 30

    e = (
        2 * a
        + 4 * b
        - d
        + 34
    ) % 7

    month = (
        d + e + 114
    ) // 31

    day = (
        (d + e + 114) % 31
    ) + 1

    julian = date(
        year,
        month,
        day
    )

    return julian + timedelta(
        days=13
    )


# ============================================================
# HOLIDAYS
# ============================================================

def get_holidays(year):

    holidays = {}

    for (month, day), name in FIXED_HOLIDAYS.items():

        holidays[
            date(
                year,
                month,
                day
            )
        ] = name

    easter = orthodox_easter(
        year
    )

    holidays[
        easter - timedelta(days=2)
    ] = "Good Friday"

    holidays[
        easter
    ] = "Easter Sunday"

    holidays[
        easter + timedelta(days=1)
    ] = "Easter Monday"

    return holidays


# ============================================================
# SHIFTS FOR DATE
# ============================================================

def get_shifts(
    work_date,
    holidays
):

    if work_date in holidays:

        return HOLIDAY_SHIFTS

    if work_date.weekday() >= 5:

        return WEEKEND_SHIFTS

    return WEEKDAY_SHIFTS


# ============================================================
# EMPLOYEE EXISTING DATA
# ============================================================

def get_existing(
    rows,
    email,
    year,
    month
):

    existing = set()

    for row in rows:

        if row["email"].strip().lower() != email:

            continue

        try:

            d = date.fromisoformat(
                row["work_date"]
            )

        except ValueError:

            continue

        if (
            d.year == year
            and d.month == month
        ):
