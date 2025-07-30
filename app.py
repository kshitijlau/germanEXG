import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import time
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(
    page_title="Element X Translator",
    page_icon="🇩🇪",
    layout="wide"
)

# --- Master Prompt ---
# This is the finalized prompt we designed. It remains the same.
MASTER_PROMPT = """
# ROLE & PERSONA:
You are a professional German translator with a Ph.D. in Linguistics and over 10 years of experience. You specialize in localizing psychological and HR assessment materials for a corporate audience in Germany. Your translations are culturally and contextually adapted to feel natural and professional. You are meticulous with details.

# CONTEXT:
You are translating content for a corporate well-being assessment named "Element X", created by the company "Mercer Talent Enterprise". The tone must be professional, encouraging, and clear. The target audience is German-speaking employees. You must use the formal German address "Sie" and its corresponding grammatical forms consistently.

# TASK:
Translate the provided English "text_to_translate" into German. You will be given a unique "key" for each piece of text. Your response must be a clean JSON object containing the original "key" and the "german_translation".

# CRITICAL RULES:
1.  **HTML TAG PRESERVATION:** The HTML tags in the source text (e.g., <p>, <b>, <i>, <ul>, <li>) are structural and MUST be preserved *exactly* as they appear. Do not add, remove, or alter any tags. The translated text must be placed correctly within these tags.
2.  **IMMUTABLE ENTITIES:** You MUST NOT translate the following proper nouns and identifiers. They must remain in English exactly as written:
    * The company name: "Mercer Talent Enterprise"
    * The assessment name: "Element X"
    * The email address: "mte.surveys@mercer.com"
3.  **NUANCES OF GERMAN TRANSLATION:**
    * **Formality:** Use the formal "Sie" for "you" throughout.
    * **Vocabulary:** Choose words appropriate for a professional, psychological, and corporate context.
    * **Compound Nouns:** Use correct German compound nouns where appropriate.
4.  **OUTPUT FORMAT:** Your entire output MUST be a single, clean JSON object. Do not include any explanatory text before or after the JSON. The JSON object must have two keys: "key" and "german_translation".

# DATA TO TRANSLATE:
{{
  "key": "{key_from_user_file}",
  "text_to_translate": "{text_from_user_file}"
}}
"""

# Helper function to convert DataFrame to Excel in memory
def to_excel(df):
    output = BytesIO()
    # Use the openpyxl engine to write the Excel file
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Translations')
    processed_data = output.getvalue()
    return processed_data

# --- App UI and Logic ---
st.title("🇩🇪 Element X Assessment Translator (English to German)")
st.markdown("This application uses the Gemini 1.5 Pro API to translate assessment content from an **Excel file** and provides the output as a new **Excel file**.")

# API Key Setup
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter your Google AI API Key", type="password")

if not api_key:
    st.info("Please enter your Google AI API Key in the sidebar to begin.")
    st.stop()

# Configure the generative AI model
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
except Exception as e:
    st.error(f"Error configuring the API. Please check your key. Details: {e}")
    st.stop()

# --- UPDATED: Step 1 - Switched from CSV to Excel ---
st.header("Step 1: Upload your Excel File")
uploaded_file = st.file_uploader("Choose the Excel file with your English text.", type=['xlsx'])

if uploaded_file is not None:
    try:
        # --- UPDATED: Read from Excel instead of CSV ---
        df = pd.read_excel(uploaded_file)
        
        # --- UPDATED: Standardize column names for robustness ---
        # This allows the user's file to have 'Key' or 'key', etc.
        column_mapping = {
            'Key': 'key',
            'Text in english to be translated': 'Text',
        }
        df.rename(columns=column_mapping, inplace=True)

        # Check for the standardized column names
        if 'key' not in df.columns or 'Text' not in df.columns:
            st.error("The uploaded Excel file must contain columns named 'Key' and 'Text in english to be translated'.")
            st.stop()
        
        st.success("File uploaded successfully!")
        st.write("Preview of your data:")
        st.dataframe(df.head())

        if st.button("🚀 Start Translation", type="primary"):
            st.header("Step 2: Translation in Progress...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Add a new column for the translations
            df['German Translation'] = ''

            total_rows = len(df)
            for index, row in df.iterrows():
                key = row['key']
                # Use the standardized 'Text' column
                text_to_translate = row['Text']
                
                status_text.text(f"Translating row {index+1}/{total_rows} (Key: {key})")

                try:
                    # Format the prompt for the current row
                    prompt = MASTER_PROMPT.format(
                        key_from_user_file=key,
                        text_from_user_file=str(text_to_translate) # Ensure text is a string
                    )
                    
                    # Call the API
                    response = model.generate_content(prompt)
                    
                    # Clean and parse the JSON response
                    response_text = response.text.strip().replace("```json", "").replace("```", "")
                    translation_data = json.loads(response_text)
                    
                    # Store the translation in the new column
                    df.at[index, 'German Translation'] = translation_data.get("german_translation", "PARSE_ERROR")

                except Exception as e:
                    st.warning(f"Error on key '{key}': {e}. Skipping.")
                    df.at[index, 'German Translation'] = "TRANSLATION_ERROR"
                
                # Update progress
                progress_bar.progress((index + 1) / total_rows)
                # A small delay can help prevent hitting API rate limits on very large files
                time.sleep(0.5) 

            status_text.text("Translation complete!")
            st.success("All rows have been processed!")
            
            st.header("Step 3: Review and Download")
            # Display the final DataFrame with the new translation column
            st.dataframe(df)
            
            # Convert the final DataFrame to an Excel file in memory
            excel_data = to_excel(df)
            
            # --- UPDATED: Download button provides an .xlsx file ---
            st.download_button(
                label="📥 Download Translated Excel File",
                data=excel_data,
                file_name=f"Translated_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"An error occurred while processing the file: {e}")

