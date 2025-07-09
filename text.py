import streamlit as st
import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Dict, List
import base64
from io import BytesIO
import numpy as np
from PIL import Image
import logging
import os

# Configure logging to debug issues
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', filename='app.log')
logger = logging.getLogger(__name__)

# Simulated Blockchain Class with Persistence
class Blockchain:
    def __init__(self):
        self.chain: List[Dict] = []
        self.pending_degrees: List[Dict] = []
        self.verifiers = {"HEC": "Higher Education Commission", "IBCC": "Inter Board Committee of Chairmen"}
        self.load_blockchain()
        if not self.chain:
            self.create_block(previous_hash="0")

    def create_block(self, previous_hash: str) -> Dict:
        block = {
            'index': len(self.chain) + 1,
            'timestamp': str(datetime.now()),
            'degrees': self.pending_degrees,
            'previous_hash': previous_hash,
            'hash': ''
        }
        block['hash'] = self.calculate_hash(block)
        self.chain.append(block)
        self.pending_degrees = []
        self.save_blockchain()
        logger.debug(f"Created block #{block['index']} with hash {block['hash']}")
        return block

    def calculate_hash(self, block: Dict) -> str:
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def add_degree(self, degree_data: Dict) -> None:
        self.pending_degrees.append(degree_data)
        logger.debug(f"Added degree {degree_data['degree_id']} to pending transactions")

    def get_latest_block(self) -> Dict:
        return self.chain[-1]

    def verify_degree(self, degree_id: str, status: str, verifier: str) -> bool:
        if verifier not in self.verifiers:
            logger.error(f"Invalid verifier: {verifier}")
            return False
        for block in self.chain:
            for degree in block['degrees']:
                if degree['degree_id'] == degree_id:
                    degree['status'] = status
                    degree['verified_by'] = self.verifiers[verifier]
                    degree['verification_date'] = str(datetime.now())
                    self.save_blockchain()
                    logger.info(f"Verified degree {degree_id} as {status} by {verifier}")
                    return True
        logger.warning(f"Degree ID {degree_id} not found in blockchain")
        return False

    def find_degree(self, degree_id: str) -> Dict | None:
        for block in self.chain:
            for degree in block['degrees']:
                if degree['degree_id'] == degree_id:
                    logger.debug(f"Found degree {degree_id} in blockchain")
                    return degree
        logger.warning(f"Degree {degree_id} not found in blockchain")
        return None

    def save_blockchain(self):
        try:
            with open('blockchain.json', 'w') as f:
                json.dump(self.chain, f, indent=4)
            logger.debug("Saved blockchain to blockchain.json")
        except Exception as e:
            logger.error(f"Error saving blockchain: {e}")

    def load_blockchain(self):
        try:
            if os.path.exists('blockchain.json'):
                with open('blockchain.json', 'r') as f:
                    self.chain = json.load(f)
                logger.debug("Loaded blockchain from blockchain.json")
            else:
                logger.debug("No blockchain.json found, starting with empty chain")
        except Exception as e:
            logger.error(f"Error loading blockchain: {e}")
            self.chain = []

# Persistent Database Setup (SQLite file-based)
def init_db():
    conn = sqlite3.connect('degrees.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS degrees (
            degree_id TEXT PRIMARY KEY,
            student_name TEXT,
            degree_title TEXT,
            institution TEXT,
            issue_date TEXT,
            document_hash TEXT,
            document_data BLOB,
            file_extension TEXT,
            status TEXT,
            verified_by TEXT,
            verification_date TEXT
        )
    ''')
    conn.commit()
    logger.debug("Initialized SQLite database: degrees.db")
    return conn

# Database Operations
# ... All DB functions remain unchanged (save_degree_to_db, update_degree_status_in_db, find_degree_in_db)
# Assume those are already present, unchanged

# Initialize blockchain and database
blockchain = Blockchain()
db_conn = init_db()

# Streamlit App
st.set_page_config(page_title="Academic Degree Verification System", layout="wide")
st.title("Blockchain-Based Academic Degree Verification System")
st.markdown("Upload, verify, and check academic degrees securely using blockchain and persistent database storage.")

role = st.selectbox("Select Your Role", ["Educational Institution/Student", "Regulatory Body (HEC/IBCC)", "Employer/University"])

if role == "Educational Institution/Student":
    st.header("Upload Degree Document")
    with st.form("upload_form"):
        student_name = st.text_input("Student Name")
        degree_title = st.text_input("Degree Title")
        institution = st.text_input("Institution Name")
        issue_date = st.date_input("Issue Date")
        degree_file = st.file_uploader("Upload Degree Document (PDF/Image)", type=["pdf", "png", "jpg", "jpeg"])
        submit = st.form_submit_button("Upload Degree")

    if submit:
        if student_name and degree_title and institution and issue_date and degree_file:
            try:
                file_bytes = degree_file.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                file_extension = degree_file.name.split('.')[-1].lower()
                degree_id = hashlib.sha256(f"{student_name}{degree_title}{institution}{issue_date}{file_hash}".encode()).hexdigest()

                degree_data = {
                    'degree_id': degree_id,
                    'student_name': student_name,
                    'degree_title': degree_title,
                    'institution': institution,
                    'issue_date': str(issue_date),
                    'document_hash': file_hash,
                    'status': 'Pending',
                    'verified_by': None,
                    'verification_date': None
                }
                blockchain.add_degree(degree_data)
                blockchain.create_block(blockchain.get_latest_block()['hash'])
                save_degree_to_db(db_conn, degree_data, file_bytes, file_extension)

                st.success(f"Degree uploaded successfully! Degree ID: {degree_id}")
                st.info("Share the Degree ID with regulatory bodies for verification.")
            except Exception as e:
                logger.error(f"Error uploading degree: {e}")
                st.error(f"Failed to upload degree: {e}")
        else:
            st.error("Please fill in all fields and upload a document.")

elif role == "Regulatory Body (HEC/IBCC)":
    st.header("Verify Degrees")
    with st.form("verify_form"):
        degree_id = st.text_input("Enter Degree ID to Verify")
        verifier = st.selectbox("Verifier", ["HEC", "IBCC"])
        action = st.selectbox("Action", ["Approve", "Reject"])
        submit = st.form_submit_button("Submit Verification")

    if submit:
        if degree_id and verifier and action:
            try:
                degree_db = find_degree_in_db(db_conn, degree_id)
                if not degree_db:
                    st.error("Degree ID not found in database!")
                status = "Approved" if action == "Approve" else "Rejected"
                if blockchain.verify_degree(degree_id, status, verifier):
                    update_degree_status_in_db(db_conn, degree_id, status, blockchain.verifiers[verifier], str(datetime.now()))
                    st.success(f"Degree {degree_id} has been {status.lower()} by {blockchain.verifiers[verifier]}!")
                else:
                    st.error("Degree ID not found in blockchain! Please ensure it was uploaded correctly.")
            except Exception as e:
                logger.error(f"Error verifying degree {degree_id}: {e}")
                st.error(f"Failed to verify degree: {e}")
        else:
            st.error("Please fill in all fields before submitting.")

elif role == "Employer/University":
    st.header("Verify a Degree")
    with st.form("verify_form"):
        degree_id = st.text_input("Enter Degree ID to Verify")
        uploaded_file = st.file_uploader("Upload Degree Document to Verify Hash (Optional)", type=["pdf", "png", "jpg", "jpeg"])
        submit = st.form_submit_button("Verify Degree")

    if submit:
        if degree_id:
            try:
                degree = find_degree_in_db(db_conn, degree_id)
                if degree:
                    st.write("### Verification Result")
                    st.write(f"**Student Name:** {degree['student_name']}")
                    st.write(f"**Degree Title:** {degree['degree_title']}")
                    st.write(f"**Institution:** {degree['institution']}")
                    st.write(f"**Issue Date:** {degree['issue_date']}")
                    st.write(f"**Document Hash:** {degree['document_hash']}")
                    st.write(f"**Status:** {degree['status']}")
                    st.write(f"**Verified By:** {degree['verified_by'] or 'Pending'}")
                    st.write(f"**Verification Date:** {degree['verification_date'] or 'Not Verified'}")

                    if uploaded_file:
                        file_bytes = uploaded_file.read()
                        uploaded_hash = hashlib.sha256(file_bytes).hexdigest()
                        if uploaded_hash == degree['document_hash']:
                            st.success("Document hash matches! The uploaded document is authentic.")
                        else:
                            st.error("Document hash does not match! The uploaded document may be tampered.")

                    if degree['document_data']:
                        if degree['file_extension'] in ['png', 'jpg', 'jpeg']:
                            st.image(degree['document_data'], caption="Degree Document")
                        else:
                            st.download_button(
                                label="Download Degree Document",
                                data=degree['document_data'],
                                file_name=f"degree_{degree_id}.{degree['file_extension']}",
                                mime="application/pdf" if degree['file_extension'] == 'pdf' else f"image/{degree['file_extension']}"
                            )

                    if degree['status'] == "Approved":
                        st.success("This degree is verified and authentic!")
                    elif degree['status'] == "Rejected":
                        st.error("This degree has been rejected by the regulatory body!")
                    else:
                        st.warning("This degree is pending verification.")
                else:
                    st.error("Degree ID not found!")
            except Exception as e:
                logger.error(f"Error verifying degree {degree_id}: {e}")
                st.error(f"Failed to verify degree: {e}")
        else:
            st.error("Please enter a Degree ID.")
