import streamlit as st
import pandas as pd
import jiwer
from jiwer import wer
from streamlit_gsheets import GSheetsConnection


def fetch_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    leaderboard = conn.read(worksheet="Sheet1")
    reference_df = conn.read(worksheet="Reference data", names=['ID', 'Correct Transcript'])
    return leaderboard, reference_df

def update_scores(leaderboard):
    # Sort by 'Best WER' in ascending order to find the top scores
    sorted_leaderboard = leaderboard.sort_values(by='Best WER', ascending=True)
    
    # Calculate the average of the top 3 WERs
    top3_average = sorted_leaderboard['Best WER'].head(3).mean()
    #print(top3_average)

    # Fetch the baseline score, which is the Best WER of the user named 'baseline'
    baseline_row = leaderboard[leaderboard['Username'] == 'baseline']
    if not baseline_row.empty:
        score_baseline = baseline_row.iloc[0]['Best WER']
    else:
        st.error("Baseline user score not found. Please ensure a baseline user exists.")
        return leaderboard  # Return the leaderboard unchanged if baseline not found

    # Calculate points for each user
    leaderboard['Points'] = leaderboard['Best WER'].apply(
        lambda score_i: min(15, 15 * ((score_baseline - score_i) / (score_baseline - top3_average)))
    )
    
    return leaderboard

def calculate_wer(reference_df, submitted_df):
    # Merging on sentence ID to align both the correct and the hypothesis transcripts
    comparison_df = pd.merge(reference_df, submitted_df, on='ID', how='left')

    # Ensure all necessary transcripts are present after merge
    if comparison_df['Hypothesis'].isna().any():
        raise ValueError("Some IDs in the submitted file do not have corresponding entries in the reference file.")

    # Convert columns to lists for processing
    reference_texts = comparison_df['Correct Transcript'].tolist()
    hypothesis_texts = comparison_df['Hypothesis'].tolist()


    # Calculate WER using jiwer
    error = wer(reference_texts, hypothesis_texts)
    return error

# Streamlit UI
st.title('G2P Leaderboard')

username = st.text_input("Enter your username")

# File uploader
uploaded_file = st.file_uploader("Upload your TSV file", type='tsv')

# Fetch data on each load/refresh
leaderboard, reference_df = fetch_data()

if uploaded_file and username:
    try:
        submitted_df = pd.read_csv(uploaded_file, sep='\t', header=None, names=['ID', 'Hypothesis'])
        current_wer = calculate_wer(reference_df, submitted_df)
        # Continue with leaderboard update logic...
        if username in leaderboard['Username'].values:
          user_data = leaderboard[leaderboard['Username'] == username]
          if current_wer < user_data['Best WER'].iloc[0]:
              leaderboard.loc[leaderboard['Username'] == username, 'Best WER'] = current_wer
          leaderboard.loc[leaderboard['Username'] == username, 'Submissions'] += 1
        else:
          # Sample data to append as a DataFrame
          new_data = pd.DataFrame([{'Username': username, 'Best WER': current_wer, 'Submissions': 1}])

          # Use concat to append new data to the DataFrame
          leaderboard = pd.concat([leaderboard, new_data], ignore_index=True)      
          
    except ValueError as e:
            st.error(f"Error processing your file: {e}")    # Update leaderboard

            
    #leaderboard.to_csv('leaderboard.csv', index=False)
    conn.update(worksheet="Sheet1", data=leaderboard)

# Calculate ranks based on 'Best WER'
leaderboard['Rank'] = leaderboard['Best WER'].rank(method='min', ascending=True)

leaderboard = update_scores(leaderboard)

leaderboard_display = leaderboard.sort_values(by='Best WER', ascending=True)
st.write(leaderboard_display.set_index('Rank').style.format({"Best WER": "{:.3f}", "Points": "{:.1f}"})) 


# Run the Streamlit app
# streamlit run app.py
