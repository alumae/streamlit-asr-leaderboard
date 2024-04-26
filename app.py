import streamlit as st
import pandas as pd
from jiwer import wer
from streamlit_gsheets import GSheetsConnection
import random

# Function to fetch data from Google Sheets
def fetch_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    leaderboard = conn.read(worksheet="Sheet1", ttl=0)
    reference_df = conn.read(worksheet="Reference data", names=['ID', 'Correct Transcript'])
    return leaderboard, reference_df, conn

# Function to update the scores based on WER calculations
def update_scores(leaderboard):
    sorted_leaderboard = leaderboard.sort_values(by='Best WER', ascending=True)
    top3_average = sorted_leaderboard['Best WER'].head(3).mean()
    baseline_row = leaderboard[leaderboard['Username'] == 'baseline']
    if not baseline_row.empty:
        score_baseline = baseline_row.iloc[0]['Best WER']
    else:
        st.error("Baseline user score not found. Please ensure a baseline user exists.")
        return leaderboard

    leaderboard['Points'] = leaderboard['Best WER'].apply(
        lambda score_i: min(15, 15 * ((score_baseline - score_i) / (score_baseline - top3_average)))
    )
    return leaderboard

# Function to calculate WER
def calculate_wer(reference_df, submitted_df):
    submitted_df = submitted_df.fillna("")
    comparison_df = pd.merge(reference_df, submitted_df, on='ID', how='left')
    if comparison_df['Hypothesis'].isna().any():
        print(comparison_df[comparison_df["Hypothesis"].isna()])
        raise ValueError("Some IDs in the submitted file do not have corresponding entries in the reference file.")
    reference_texts = comparison_df['Correct Transcript'].tolist()
    hypothesis_texts = comparison_df['Hypothesis'].tolist()
    error = wer(reference_texts, hypothesis_texts)
    return error

# Streamlit UI
st.title('G2P Leaderboard')
username = st.text_input("Enter your username")
uploaded_file = st.file_uploader("Upload your TSV file", type='tsv')

# Fetch data on each load/refresh
leaderboard, reference_df, conn = fetch_data()

if uploaded_file and username:
    submitted_df = pd.read_csv(uploaded_file, sep='\t', header=None, names=['ID', 'Hypothesis'])
    try:
        current_wer = calculate_wer(reference_df, submitted_df)
        if username in leaderboard['Username'].values:
            user_data = leaderboard[leaderboard['Username'] == username]
            if current_wer < user_data['Best WER'].iloc[0]:
                leaderboard.loc[leaderboard['Username'] == username, 'Best WER'] = current_wer
            leaderboard.loc[leaderboard['Username'] == username, 'Submissions'] += 1
        else:
            new_data = pd.DataFrame([{'Username': username, 'Best WER': current_wer, 'Submissions': 1}])
            leaderboard = pd.concat([leaderboard, new_data], ignore_index=True)
    except ValueError as e:
        st.error(f"Error processing your file: {e}")

    # Update the leaderboard in Google Sheets
    conn.update(worksheet="Sheet1", data=leaderboard)

# Calculate ranks and update scores
leaderboard['Rank'] = leaderboard['Best WER'].rank(method='min', ascending=True)
leaderboard = update_scores(leaderboard)
leaderboard_display = leaderboard.sort_values(by='Best WER', ascending=True)
st.write(leaderboard_display.set_index('Rank').style.format({"Best WER": "{:.3f}", "Points": "{:.1f}"}))
