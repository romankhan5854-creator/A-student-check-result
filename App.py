import os

import pandas as pd
import streamlit as st

try:
    from google import genai
except ImportError:  # app still works without the AI part
    genai = None

# ----------------------------------------------------------------------------
# Page setup
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Student Result Checker", page_icon="🎓", layout="wide")

GEMINI_MODEL = "gemini-2.5-flash"
ATTENDANCE_REQUIRED = 75.0  # minimum % most universities require

# (minimum percentage, grade, grade points) - common 4.0 scale, edit to match your university
GRADE_SCALE = [
    (85, "A", 4.00),
    (80, "A-", 3.67),
    (75, "B+", 3.33),
    (71, "B", 3.00),
    (68, "B-", 2.67),
    (64, "C+", 2.33),
    (61, "C", 2.00),
    (58, "C-", 1.67),
    (54, "D+", 1.33),
    (50, "D", 1.00),
    (0, "F", 0.00),
]


def get_grade(percentage: float):
    for minimum, grade, points in GRADE_SCALE:
        if percentage >= minimum:
            return grade, points
    return "F", 0.0


def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY", "")


def ask_gemini(api_key: str, summary: str) -> str:
    client = genai.Client(api_key=api_key)
    prompt = (
        "You are a friendly academic advisor. A student shared their results below. "
        "Explain the result in simple language: 1) overall verdict, 2) attendance status, "
        "3) strongest and weakest subjects, 4) what GPA/grade they are heading for, and "
        "5) three practical tips to improve. Keep it under 250 words. "
        "Do not invent numbers that are not in the data.\n\n" + summary
    )
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.title("🎓 Student Result Checker")
st.caption("Check your attendance, marks, GPA and grade - and get an AI explanation of your result.")

with st.sidebar:
    st.header("Settings")
    api_key = get_api_key()
    if not api_key:
        api_key = st.text_input("Gemini API key", type="password",
                                help="Get a free key from Google AI Studio.")
    else:
        st.success("Gemini API key loaded.")
    name = st.text_input("Student name (optional)")
    st.markdown("---")
    st.markdown("**Grade scale used**")
    st.dataframe(
        pd.DataFrame(GRADE_SCALE, columns=["Min %", "Grade", "Points"]),
        hide_index=True,
        use_container_width=True,
    )

st.subheader("Enter your subjects")
st.write("Add one row per subject. Use the **+** at the bottom of the table to add more rows.")

default_data = pd.DataFrame(
    {
        "Subject": ["Mathematics", "Physics", "English"],
        "Credit Hours": [3, 3, 2],
        "Marks Obtained": [78.0, 65.0, 82.0],
        "Total Marks": [100.0, 100.0, 100.0],
        "Classes Attended": [28, 24, 20],
        "Total Classes": [32, 32, 24],
    }
)

data = st.data_editor(
    default_data,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Credit Hours": st.column_config.NumberColumn(min_value=1, max_value=6, step=1),
        "Marks Obtained": st.column_config.NumberColumn(min_value=0.0),
        "Total Marks": st.column_config.NumberColumn(min_value=1.0),
        "Classes Attended": st.column_config.NumberColumn(min_value=0, step=1),
        "Total Classes": st.column_config.NumberColumn(min_value=1, step=1),
    },
)

if st.button("Check my result", type="primary"):
    df = data.dropna().copy()
    df = df[df["Subject"].astype(str).str.strip() != ""]

    if df.empty:
        st.error("Please enter at least one complete subject row.")
        st.stop()

    if (df["Marks Obtained"] > df["Total Marks"]).any():
        st.error("Marks obtained cannot be greater than total marks.")
        st.stop()
    if (df["Classes Attended"] > df["Total Classes"]).any():
        st.error("Classes attended cannot be greater than total classes.")
        st.stop()

    # Calculations
    df["Percentage"] = (df["Marks Obtained"] / df["Total Marks"] * 100).round(2)
    grades = df["Percentage"].apply(get_grade)
    df["Grade"] = grades.apply(lambda g: g[0])
    df["Grade Points"] = grades.apply(lambda g: g[1])
    df["Attendance %"] = (df["Classes Attended"] / df["Total Classes"] * 100).round(2)
    df["Attendance Status"] = df["Attendance %"].apply(
        lambda a: "OK" if a >= ATTENDANCE_REQUIRED else "Short"
    )

    total_credits = df["Credit Hours"].sum()
    gpa = (df["Grade Points"] * df["Credit Hours"]).sum() / total_credits
    overall_pct = df["Marks Obtained"].sum() / df["Total Marks"].sum() * 100
    overall_grade, _ = get_grade(overall_pct)
    overall_attendance = df["Classes Attended"].sum() / df["Total Classes"].sum() * 100
    failed = df[df["Grade"] == "F"]["Subject"].tolist()
    short_att = df[df["Attendance Status"] == "Short"]["Subject"].tolist()

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("GPA", f"{gpa:.2f} / 4.00")
    c2.metric("Overall Grade", overall_grade)
    c3.metric("Overall Percentage", f"{overall_pct:.1f}%")
    c4.metric("Overall Attendance", f"{overall_attendance:.1f}%")

    if failed:
        st.error(f"Failed in: {', '.join(failed)}")
    else:
        st.success("You passed all subjects.")
    if short_att:
        st.warning(f"Attendance below {ATTENDANCE_REQUIRED:.0f}% in: {', '.join(short_att)}")

    st.subheader("Subject-wise breakdown")
    st.dataframe(
        df[["Subject", "Credit Hours", "Marks Obtained", "Total Marks", "Percentage",
            "Grade", "Grade Points", "Attendance %", "Attendance Status"]],
        hide_index=True,
        use_container_width=True,
    )

    chart_df = df.set_index("Subject")[["Percentage", "Attendance %"]]
    st.bar_chart(chart_df)

    # AI explanation
    st.subheader("🤖 AI explanation")
    summary = (
        f"Student: {name or 'Not provided'}\n"
        f"GPA: {gpa:.2f}/4.00, Overall grade: {overall_grade}, Overall %: {overall_pct:.1f}, "
        f"Overall attendance: {overall_attendance:.1f}% (required {ATTENDANCE_REQUIRED:.0f}%)\n"
        f"Failed subjects: {failed or 'None'}\n"
        f"Short attendance subjects: {short_att or 'None'}\n\n"
        + df[["Subject", "Credit Hours", "Percentage", "Grade", "Attendance %"]].to_string(index=False)
    )

    if genai is None:
        st.info("Install the `google-genai` package to enable AI explanations.")
    elif not api_key:
        st.info("Add your Gemini API key in the sidebar to get an AI explanation.")
    else:
        with st.spinner("Gemini is analysing your result..."):
            try:
                st.write(ask_gemini(api_key, summary))
            except Exception as e:
                st.error(f"Could not get the AI explanation: {e}")
