import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Exam Analyzer Pro", layout="wide")

# --- SESSION STATE INITIALIZATION ---
if 'answers' not in st.session_state:
    st.session_state['answers'] = {}
if 'current_question' not in st.session_state:
    st.session_state['current_question'] = 0
if 'exam_started' not in st.session_state:
    st.session_state['exam_started'] = False
if 'exam_submitted' not in st.session_state:
    st.session_state['exam_submitted'] = False
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = None

# --- FILE HANDLING ---
def extract_questions_from_pdf(uploaded_file):
    questions = []
    with pdfplumber.open(uploaded_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    # Regex to find questions starting with numbers (1., 2., etc.)
    pattern = r'(\d+\.\s.*?)(?=\d+\.\s|$)' 
    matches = re.findall(pattern, text, re.DOTALL)
    
    if not matches:
        return ["Could not auto-detect questions. Please ensure PDF text is selectable and numbered (1. , 2. )."]
        
    return [m.strip() for m in matches]

def load_answer_key(uploaded_key):
    # Expects CSV with columns: 'Question', 'Answer' (e.g., 1, A)
    try:
        df = pd.read_csv(uploaded_key)
        # Convert to a dictionary: {1: 'A', 2: 'B', ...}
        # Normalize keys to integers and values to uppercase strings
        key_dict = dict(zip(df.iloc[:, 0], df.iloc[:, 1].str.upper().str.strip()))
        return key_dict
    except Exception as e:
        st.error(f"Error reading Answer Key: {e}")
        return {}

# --- DATABASE (CSV) FOR HISTORY ---
DB_FILE = 'exam_history.csv'

def save_score(shift_name, score, total_q, correct, wrong):
    if not os.path.isfile(DB_FILE):
        df = pd.DataFrame(columns=["Shift", "Score", "Total_Q", "Correct", "Wrong", "Date"])
        df.to_csv(DB_FILE, index=False)
    
    new_data = {
        "Shift": shift_name,
        "Score": score,
        "Total_Q": total_q,
        "Correct": correct,
        "Wrong": wrong,
        "Date": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
    }
    df = pd.read_csv(DB_FILE)
    df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def get_history():
    if os.path.isfile(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame()

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.title("⚙️ Exam Setup")
    shift_name = st.text_input("Enter Shift Name", "Morning Shift - Set A")
    positive_marks = st.number_input("Marks for Correct", value=4)
    negative_marks = st.number_input("Negative Marks", value=1)
    
    st.divider()
    st.subheader("1. Upload Paper")
    uploaded_pdf = st.file_uploader("Question Paper (PDF)", type=['pdf'])
    
    st.subheader("2. Upload Answer Key")
    uploaded_key = st.file_uploader("Answer Key (CSV)", type=['csv'])
    st.caption("CSV format: Col 1 = Question No, Col 2 = Option (A,B,C,D)")
    
    # Start Button Logic
    if uploaded_pdf and uploaded_key and not st.session_state['exam_started']:
        if st.button("Start Mock Test", type="primary"):
            st.session_state['questions'] = extract_questions_from_pdf(uploaded_pdf)
            st.session_state['real_answer_key'] = load_answer_key(uploaded_key)
            st.session_state['exam_started'] = True
            st.session_state['start_time'] = time.time()
            st.rerun()

# --- MAIN APP LOGIC ---

st.title("📝 Mock Test Exam Analyzer")

# 1. LANDING STATE
if not st.session_state['exam_started'] and not st.session_state['exam_submitted']:
    st.info("👈 Please upload both the **Question PDF** and the **Answer Key CSV** in the sidebar to begin.")
    
    history = get_history()
    if not history.empty:
        st.subheader("📊 Your Shift-wise Performance")
        st.line_chart(history, x="Shift", y="Score")
        st.dataframe(history)

# 2. EXAM TAKING STATE
elif st.session_state['exam_started'] and not st.session_state['exam_submitted']:
    questions = st.session_state['questions']
    idx = st.session_state['current_question']
    
    # Timer
    elapsed = int(time.time() - st.session_state['start_time'])
    st.metric("Time Elapsed", f"{elapsed // 60}m {elapsed % 60}s")
    st.progress((idx + 1) / len(questions))
    
    # Question Display
    st.subheader(f"Question {idx + 1}")
    st.markdown(f"**{questions[idx]}**")
    
    # Answer Input
    answer = st.radio(
        "Select your answer:", 
        ["Unattempted", "A", "B", "C", "D"], 
        index=0, 
        key=f"q_{idx}"
    )
    
    if answer != "Unattempted":
        st.session_state['answers'][idx] = answer
    
    # Navigation
    col1, col2, col3 = st.columns([1, 4, 1])
    with col1:
        if idx > 0 and st.button("Previous"):
            st.session_state['current_question'] -= 1
            st.rerun()
    with col3:
        if idx < len(questions) - 1:
            if st.button("Next"):
                st.session_state['current_question'] += 1
                st.rerun()
        else:
            if st.button("Submit Exam", type="primary"):
                st.session_state['exam_submitted'] = True
                st.rerun()

# 3. ANALYSIS & RESULTS STATE
elif st.session_state['exam_submitted']:
    st.balloons()
    st.success("Exam Submitted! Analyzing results...")
    
    questions = st.session_state['questions']
    user_answers = st.session_state['answers']
    real_key = st.session_state['real_answer_key']
    
    correct_count = 0
    wrong_count = 0
    unattempted_count = 0
    results_data = []
    
    for i in range(len(questions)):
        q_num = i + 1
        user_ans = user_answers.get(i, "Unattempted")
        
        # Fetch correct answer from uploaded key. 
        # Default to "N/A" if key is missing for that question index
        correct_ans = real_key.get(q_num, "N/A") 
        
        status = "Unattempted"
        
        if user_ans == "Unattempted":
            unattempted_count += 1
        elif user_ans == correct_ans:
            correct_count += 1
            status = "Correct"
        else:
            if correct_ans != "N/A": # Only count wrong if we know the right answer
                wrong_count += 1
                status = "Wrong"
            else:
                # If answer key is missing for this q, treat as unattempted/neutral
                status = "Key Missing"
            
        results_data.append({
            "Q No.": q_num,
            "Your Answer": user_ans,
            "Correct Answer": correct_ans,
            "Status": status
        })

    final_score = (correct_count * positive_marks) - (wrong_count * negative_marks)
    
    # Scorecard
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Score", f"{final_score}", delta_color="normal")
    col2.metric("Correct", f"{correct_count}", delta_color="inverse")
    col3.metric("Wrong", f"{wrong_count}", "-ve Marks")
    col4.metric("Unattempted", f"{unattempted_count}")
    
    # Table
    st.subheader("Detailed Analysis")
    df_results = pd.DataFrame(results_data)
    
    def color_status(val):
        if val == 'Correct': return 'background-color: #d4edda; color: #155724'
        elif val == 'Wrong': return 'background-color: #f8d7da; color: #721c24'
        return ''
        
    st.dataframe(df_results.style.map(color_status, subset=['Status']), use_container_width=True)
    
    # Save & Reset
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("Save Result to History"):
            save_score(shift_name, final_score, len(questions), correct_count, wrong_count)
            st.success("Saved! Check home screen.")
            
    with col_reset:
        if st.button("Take Another Test"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
