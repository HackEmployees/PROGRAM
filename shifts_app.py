import streamlit as st
import calendar
import csv
import io
import base64
import requests

from datetime import date, timedelta


# ============================================================
# ΡΥΘΜΙΣΕΙΣ
# ============================================================

DATA_FILE = "availability.csv"

# Δευτέρα - Παρασκευή
WEEKDAY_SHIFTS = [
    "03:30-07:30",
    "07:30-15:00",
    "15:00-21:30",
    "21:30-03:30",
]

# Σάββατο - Κυριακή
WEEKEND_SHIFTS = [
    "03:30-11:30",
    "11:30-19:30",
    "19:30-03:30",
]

# Αργίες
HOLIDAY_SHIFTS = [
    "03:30-11:30",
    "11:30-19:30",
    "19:30-03:30",
]


# ============================================================
# ΣΕΛΙΔΑ
# ============================================================

st.set_page_config(
    page_title="Διαθεσιμότητα Εργαζομένων",
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
        "Λείπουν οι ρυθμίσεις GitHub από "
        "τα Streamlit Secrets."
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
# ΔΙΑΒΑΣΜΑ CSV
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

    # Το αρχείο δεν υπάρχει ακόμα
    if response.status_code == 404:

        return [], None


    if not response.ok:

        raise Exception(
            f"Σφάλμα GitHub "
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

    rows = list(reader)

    return rows, sha


# ============================================================
# ΑΠΟΘΗΚΕΥΣΗ CSV
# ============================================================

def save_availability(
    rows,
    sha=None
):

    output = io.StringIO()


    # ΑΚΡΙΒΩΣ αυτά τα 4 columns
    fieldnames = [
        "email",
        "number",
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

            "email":
                row.get("email", ""),

            "number":
                row.get("number", ""),

            "work_date":
                row.get("work_date", ""),

            "shift":
                row.get("shift", "")

        })


    encoded = base64.b64encode(
        output.getvalue().encode(
            "utf-8"
        )
    ).decode(
        "utf-8"
    )


    payload = {

        "message":
            "Ενημέρωση διαθεσιμότητας",

        "content":
            encoded,

        "branch":
            GITHUB_BRANCH
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
            f"Σφάλμα αποθήκευσης GitHub "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# ΚΥΠΡΙΑΚΕΣ ΑΡΓΙΕΣ
# ============================================================

FIXED_HOLIDAYS = {

    (1, 1):
        "Πρωτοχρονιά",

    (1, 6):
        "Θεοφάνεια",

    (3, 25):
        "25η Μαρτίου",

    (4, 1):
        "1η Απριλίου",

    (5, 1):
        "Εργατική Πρωτομαγιά",

    (8, 15):
        "Κοίμηση της Θεοτόκου",

    (10, 1):
        "Ημέρα Ανεξαρτησίας Κύπρου",

    (10, 28):
        "28η Οκτωβρίου",

    (12, 25):
        "Χριστούγεννα",

    (12, 26):
        "Δεύτερη ημέρα Χριστουγέννων",
}


# ============================================================
# ΟΡΘΟΔΟΞΟ ΠΑΣΧΑ
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

    # Μετατροπή Ιουλιανού σε Γρηγοριανό
    return julian + timedelta(
        days=13
    )


# ============================================================
# ΑΡΓΙΕΣ ΓΙΑ ΕΝΑ ΕΤΟΣ
# ============================================================

def get_holidays(year):

    holidays = {}


    # Σταθερές αργίες

    for (month, day), name in FIXED_HOLIDAYS.items():

        holidays[
            date(
                year,
                month,
                day
            )
        ] = name


    # Πάσχα

    easter = orthodox_easter(
        year
    )


    holidays[
        easter - timedelta(days=2)
    ] = "Μεγάλη Παρασκευή"


    holidays[
        easter
    ] = "Κυριακή του Πάσχα"


    holidays[
        easter + timedelta(days=1)
    ] = "Δευτέρα του Πάσχα"


    return holidays


# ============================================================
# ΒΑΡΔΙΕΣ ΓΙΑ ΚΑΘΕ ΗΜΕΡΑ
# ============================================================

def get_shifts_for_date(
    work_date,
    holidays
):

    # Αργία
    if work_date in holidays:

        return HOLIDAY_SHIFTS


    # Σαββατοκύριακο
    if work_date.weekday() >= 5:

        return WEEKEND_SHIFTS


    # Δευτέρα - Παρασκευή
    return WEEKDAY_SHIFTS


# ============================================================
# ΤΙ ΕΧΕΙ ΗΔΗ ΔΗΛΩΣΕΙ Ο ΕΡΓΑΖΟΜΕΝΟΣ
# ============================================================

def get_existing_selections(
    rows,
    email,
    number,
    year,
    month
):

    selections = set()


    email = email.strip().lower()

    number = number.strip()


    for row in rows:

        row_email = (
            row.get("email", "")
            .strip()
            .lower()
        )

        row_number = (
            row.get("number", "")
            .strip()
        )


        if row_email != email:

            continue


        if row_number != number:

            continue


        try:

            work_date = date.fromisoformat(
                row["work_date"]
            )

        except Exception:

            continue


        if (
            work_date.year == year
            and work_date.month == month
        ):

            selections.add(
                (
                    row["work_date"],
                    row["shift"]
                )
            )


    return selections


# ============================================================
# ΤΙΤΛΟΣ
# ============================================================

st.title(
    "📅 Δήλωση Διαθεσιμότητας"
)

st.write(
    "Επιλέξτε τον μήνα και τις βάρδιες "
    "στις οποίες μπορείτε να εργαστείτε."
)


# ============================================================
# 1. ΕΠΙΛΟΓΗ ΜΗΝΑ
# ============================================================

st.subheader(
    "1. Επιλέξτε μήνα"
)


today = date.today()


GREEK_MONTHS = [

    "Ιανουάριος",
    "Φεβρουάριος",
    "Μάρτιος",
    "Απρίλιος",
    "Μάιος",
    "Ιούνιος",
    "Ιούλιος",
    "Αύγουστος",
    "Σεπτέμβριος",
    "Οκτώβριος",
    "Νοέμβριος",
    "Δεκέμβριος",
]


# Μόνο οι επόμενοι 3 μήνες

months = []


for i in range(3):

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

    f"{GREEK_MONTHS[month - 1]} {year}"

    for year, month in months

]


selected_label = st.selectbox(

    "Μήνας",

    month_labels

)


selected_index = month_labels.index(
    selected_label
)


year, month = months[
    selected_index
]


# ============================================================
# 2. ΦΟΡΜΑ ΔΙΑΘΕΣΙΜΟΤΗΤΑΣ
# ============================================================

st.subheader(
    f"2. Διαθεσιμότητα — {selected_label}"
)


st.caption(
    "🟥 Αργία    🟦 Σαββατοκύριακο"
)


holidays = get_holidays(
    year
)


calendar_weeks = calendar.monthcalendar(
    year,
    month
)


GREEK_DAYS = [

    "ΔΕΥ",
    "ΤΡΙ",
    "ΤΕΤ",
    "ΠΕΜ",
    "ΠΑΡ",
    "ΣΑΒ",
    "ΚΥΡ"

]


# ============================================================
# ΗΜΕΡΕΣ ΕΒΔΟΜΑΔΑΣ
# ============================================================

header = st.columns(7)


for i, day_name in enumerate(
    GREEK_DAYS
):

    with header[i]:

        st.markdown(
            f"**{day_name}**"
        )


# ============================================================
# ΕΠΙΛΟΓΕΣ
# ============================================================

selected = []


for week_number, week in enumerate(
    calendar_weeks
):

    columns = st.columns(7)


    for day_index, day_number in enumerate(
        week
    ):

        with columns[day_index]:


            # Κενό κελί

            if day_number == 0:

                st.write("")

                continue


            work_date = date(
                year,
                month,
                day_number
            )


            # ------------------------------------------------
            # ΗΜΕΡΑ
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
            # ΒΑΡΔΙΕΣ
            # ------------------------------------------------

            shifts = get_shifts_for_date(
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
# 3. ΣΤΟΙΧΕΙΑ ΕΡΓΑΖΟΜΕΝΟΥ
# ============================================================

st.divider()


st.subheader(
    "3. Στοιχεία εργαζομένου"
)


email = st.text_input(
    "Email",
    placeholder="maria@company.com"
).strip().lower()


number = st.text_input(
    "Τελ. αριθμός",
    placeholder="1234"
).strip()


# ============================================================
# 4. ΥΠΟΒΟΛΗ
# ============================================================

st.divider()


if st.button(
    "✅ ΥΠΟΒΟΛΗ ΔΙΑΘΕΣΙΜΟΤΗΤΑΣ",
    type="primary",
    use_container_width=True
):


    # --------------------------------------------------------
    # Έλεγχος email
    # --------------------------------------------------------

    if not email:

        st.error(
            "Παρακαλώ συμπληρώστε το email."
        )

        st.stop()


    if "@" not in email:

        st.error(
            "Παρακαλώ συμπληρώστε έγκυρο email."
        )

        st.stop()


    # --------------------------------------------------------
    # Έλεγχος αριθμού
    # --------------------------------------------------------

    if not number:

        st.error(
            "Παρακαλώ συμπληρώστε τον αριθμό."
        )

        st.stop()


    # --------------------------------------------------------
    # Φόρτωση δεδομένων
    # --------------------------------------------------------

    try:

        all_rows, csv_sha = read_availability()

    except Exception as error:

        st.error(
            f"Δεν ήταν δυνατή η φόρτωση των δεδομένων: "
            f"{error}"
        )

        st.stop()


    # --------------------------------------------------------
    # Αφαίρεση προηγούμενων δεδομένων
    # του ίδιου εργαζομένου για τον ίδιο μήνα
    # --------------------------------------------------------

    new_rows = []


    for row in all_rows:

        try:

            row_date = date.fromisoformat(
                row["work_date"]
            )

        except Exception:

            continue


        same_email = (

            row.get("email", "")
            .strip()
            .lower()
            == email

        )


        same_number = (

            row.get("number", "")
            .strip()
            == number

        )


        same_month = (

            row_date.year == year
            and row_date.month == month

        )


        if (

            same_email
            and same_number
            and same_month

        ):

            continue


        new_rows.append(
            row
        )


    # --------------------------------------------------------
    # Προσθήκη νέων επιλογών
    # --------------------------------------------------------

    for item in selected:

        new_rows.append({

            "email":
                email,

            "number":
                number,

            "work_date":
                item["work_date"],

            "shift":
                item["shift"]

        })


    # --------------------------------------------------------
    # Αποθήκευση
    # --------------------------------------------------------

    try:

        save_availability(
            new_rows,
            csv_sha
        )


        st.success(
            "✅ Η διαθεσιμότητά σας αποθηκεύτηκε επιτυχώς!"
        )


        st.info(
            f"Αποθηκεύτηκαν {len(selected)} "
            f"βάρδιες για τον {selected_label}."
        )


    except Exception as error:

        st.error(
            f"Παρουσιάστηκε σφάλμα κατά την αποθήκευση: "
            f"{error}"
        )


# ============================================================
# ΤΕΛΟΣ
# ============================================================

st.divider()

st.caption(
    "Μπορείτε να υποβάλετε ξανά τη διαθεσιμότητά σας "
    "για να την αλλάξετε."
)
