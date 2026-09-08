import streamlit as st
import calendar
import csv
import io
import base64
import requests

from datetime import date, timedelta


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
    ).decode("utf-8")

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

    easter = orthodox_easter(year)

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
# SHIFTS
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
# LOAD EXISTING EMPLOYEE DATA
# ============================================================

def get_existing(
    rows,
    email,
    year,
    month
):

    existing = set()

    email = email.strip().lower()

    for row in rows:

        if (
            row["email"]
            .strip()
            .lower()
            != email
        ):
            continue

        try:

            work_date = date.fromisoformat(
                row["work_date"]
            )

        except ValueError:

            continue

        if (
            work_date.year == year
            and work_date.month == month
        ):

            existing.add(
                (
                    row["work_date"],
                    row["shift"]
                )
            )

    return existing


# ============================================================
# TITLE
# ============================================================

st.title(
    "📅 Shift Availability"
)

st.write(
    "Choose the month and select all shifts "
    "when you are available to work."
)


# ============================================================
# MONTH SELECTION
# ============================================================

st.subheader(
    "1. Choose month"
)


today = date.today()


# Create the next 12 months

months = []

for i in range(12):

    total_months = (
        today.year * 12
        + today.month
        - 1
        + i
    )

    year = total_months // 12

    month = total_months % 12 + 1

    months.append(
        (
            year,
            month
        )
    )


month_labels = [
    f"{calendar.month_name[m]} {y}"
    for y, m in months
]


selected_label = st.selectbox(
    "Month",
    month_labels
)


selected_index = month_labels.index(
    selected_label
)


year, month = months[
    selected_index
]


# ============================================================
# LOAD DATA
# ============================================================

try:

    all_rows, csv_sha = read_availability()

except Exception as error:

    st.error(
        f"Could not load availability: "
        f"{error}"
    )

    st.stop()


# ============================================================
# CALENDAR
# ============================================================

st.subheader(
    f"2. Availability — {selected_label}"
)

st.caption(
    "🟥 Public holiday   "
    "🟦 Weekend"
)


holidays = get_holidays(
    year
)


calendar_data = calendar.monthcalendar(
    year,
    month
)


weekday_names = [
    "MON",
    "TUE",
    "WED",
    "THU",
    "FRI",
    "SAT",
    "SUN"
]


# ============================================================
# DAY HEADERS
# ============================================================

header = st.columns(7)

for i, day_name in enumerate(
    weekday_names
):

    header[i].markdown(
        f"**{day_name}**"
    )


# ============================================================
# CALENDAR
# ============================================================

selected = []


for week_number, week in enumerate(
    calendar_data
):

    columns = st.columns(7)


    for day_index, day_number in enumerate(
        week
    ):

        with columns[day_index]:

            # Empty calendar cell

            if day_number == 0:

                st.write("")

                continue


            work_date = date(
                year,
                month,
                day_number
            )


            # ------------------------------------------------
            # DATE
            # ------------------------------------------------

            if work_date in holidays:

                st.markdown(
                    f"**🟥 {day_number}**"
                )

                st.caption(
                    holidays[work_date]
                )

            elif work_date.weekday() >= 5:

                st.markdown(
                    f"**🟦 {day_number}**"
                )

            else:

                st.markdown(
                    f"**{day_number}**"
                )


            # ------------------------------------------------
            # SHIFTS
            # ------------------------------------------------

            shifts = get_shifts(
                work_date,
                holidays
            )


            for shift_index, shift in enumerate(
                shifts
            ):

                checkbox_key = (
                    f"shift_"
                    f"{year}_"
                    f"{month}_"
                    f"{day_number}_"
                    f"{shift_index}"
                )


                checked = st.checkbox(
                    shift,
                    key=checkbox_key
                )


                if checked:

                    selected.append({
                        "work_date":
                            work_date.isoformat(),
                        "shift":
                            shift
                    })


# ============================================================
# EMAIL — LAST
# ============================================================

st.divider()

st.subheader(
    "3. Submit"
)

st.write(
    "Enter your email after selecting "
    "all your available shifts."
)


email = st.text_input(
    "Email address",
    placeholder="name@company.com"
).strip().lower()


# ============================================================
# SUBMIT EVERYTHING
# ============================================================

if st.button(
    "✅ SUBMIT AVAILABILITY",
    type="primary",
    use_container_width=True
):

    # --------------------------------------------------------
    # Validate email
    # --------------------------------------------------------

    if not email:

        st.error(
            "Please enter your email address."
        )

        st.stop()


    if "@" not in email:

        st.error(
            "Please enter a valid email address."
        )

        st.stop()


    # --------------------------------------------------------
    # Remove old entries for this employee/month
    # --------------------------------------------------------

    new_rows = []


    for row in all_rows:

        try:

            work_date = date.fromisoformat(
                row["work_date"]
            )

        except ValueError:

            continue


        same_email = (
            row["email"]
            .strip()
            .lower()
            == email
        )


        same_month = (
            work_date.year == year
            and work_date.month == month
        )


        if (
            same_email
            and same_month
        ):

            continue


        new_rows.append(
            row
        )


    # --------------------------------------------------------
    # Add selected availability
    # --------------------------------------------------------

    for item in selected:

        new_rows.append({
            "email": email,
            "work_date":
                item["work_date"],
            "shift":
                item["shift"]
        })


    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:

        save_availability(
            new_rows,
            csv_sha
        )

        st.success(
            "✅ Availability submitted successfully!"
        )

        st.info(
            f"{len(selected)} shifts submitted "
            f"for {selected_label}."
        )

    except Exception as error:

        st.error(
            f"Could not save availability: "
            f"{error}"
        )
