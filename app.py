import streamlit as st
import pdfplumber
import pandas as pd
import io
import traceback
from typing import List, Optional

st.title("PDF Table Extractor")
st.write("Upload a PDF file to extract tables and download as CSV")

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

def extract_tables_from_pdf(pdf_file) -> tuple[List[pd.DataFrame], List[str]]:
    """
    Extract tables from PDF with error handling for individual pages
    Returns: (list of dataframes, list of error messages)
    """
    all_tables = []
    errors = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            
            # Create progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, page in enumerate(pdf.pages):
                try:
                    # Update progress
                    progress = (i + 1) / total_pages
                    progress_bar.progress(progress)
                    status_text.text(f'Processing page {i + 1} of {total_pages}...')
                    
                    # Extract tables from current page
                    tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(tables):
                        if table and len(table) > 0:  # Check if table is not empty
                            try:
                                # Create DataFrame with error handling
                                df = pd.DataFrame(table)
                                
                                # Remove completely empty rows and columns
                                df = df.dropna(how='all').dropna(axis=1, how='all')
                                
                                if not df.empty:
                                    all_tables.append(df)
                                    
                            except Exception as table_error:
                                error_msg = f"Error processing table {table_idx + 1} on page {i + 1}: {str(table_error)}"
                                errors.append(error_msg)
                                
                except Exception as page_error:
                    error_msg = f"Error processing page {i + 1}: {str(page_error)}"
                    errors.append(error_msg)
                    continue
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
    except Exception as pdf_error:
        error_msg = f"Error opening PDF file: {str(pdf_error)}"
        errors.append(error_msg)
        st.error(error_msg)
        return [], errors
    
    return all_tables, errors

def validate_pdf_file(uploaded_file) -> Optional[str]:
    """Validate the uploaded PDF file"""
    if uploaded_file is None:
        return "No file uploaded"
    
    if uploaded_file.size == 0:
        return "Uploaded file is empty"
    
    if uploaded_file.size > 50 * 1024 * 1024:  # 50MB limit
        return "File size too large (maximum 50MB allowed)"
    
    # Check if file is actually a PDF by reading first few bytes
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(4)
        uploaded_file.seek(0)
        if header != b'%PDF':
            return "File does not appear to be a valid PDF"
    except Exception:
        return "Error reading file header"
    
    return None

if uploaded_file is not None:
    # Validate file
    validation_error = validate_pdf_file(uploaded_file)
    if validation_error:
        st.error(f"File validation failed: {validation_error}")
    else:
        st.success("File uploaded successfully!")
        
        # Show file details
        st.info(f"**File name:** {uploaded_file.name}")
        st.info(f"**File size:** {uploaded_file.size / 1024:.1f} KB")
        
        # Extract tables with progress tracking
        try:
            with st.spinner("Initializing PDF processing..."):
                all_tables, errors = extract_tables_from_pdf(uploaded_file)
            
            # Display any errors that occurred during processing
            if errors:
                st.warning("Some errors occurred during processing:")
                for error in errors:
                    st.warning(f"⚠️ {error}")
            
            # Process results
            if all_tables:
                try:
                    # Combine all tables
                    combined = pd.concat(all_tables, ignore_index=True)
                    
                    # Display success metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tables Found", len(all_tables))
                    with col2:
                        st.metric("Total Rows", len(combined))
                    with col3:
                        st.metric("Total Columns", len(combined.columns))
                    
                    # Display the extracted tables
                    st.subheader("📊 Extracted Tables Preview")
                    
                    # Show first few rows with option to expand
                    with st.expander("View Data Preview", expanded=True):
                        st.dataframe(combined.head(100))  # Show first 100 rows
                        if len(combined) > 100:
                            st.info(f"Showing first 100 rows of {len(combined)} total rows")
                    
                    # Data quality information
                    with st.expander("Data Quality Information"):
                        st.write("**Column Information:**")
                        for i, col in enumerate(combined.columns):
                            non_null_count = combined[col].notna().sum()
                            st.write(f"- Column {i}: {non_null_count}/{len(combined)} non-null values")
                    
                    # Convert to CSV for download
                    try:
                        csv_buffer = io.StringIO()
                        combined.to_csv(csv_buffer, index=False)
                        csv_data = csv_buffer.getvalue()
                        
                        # Download button
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv_data,
                            file_name=f"extracted_tables_{uploaded_file.name.replace('.pdf', '')}.csv",
                            mime="text/csv",
                            help="Click to download the extracted tables as a CSV file"
                        )
                        
                        st.success(f"✅ Successfully extracted {len(all_tables)} tables from the PDF!")
                        
                    except Exception as csv_error:
                        st.error(f"Error creating CSV file: {str(csv_error)}")
                        st.error("Please try again or contact support if the problem persists.")
                        
                except Exception as combine_error:
                    st.error(f"Error combining tables: {str(combine_error)}")
                    st.error("This might be due to inconsistent table structures in the PDF.")
                    
                    # Offer individual table download as fallback
                    st.info("**Alternative:** Download individual tables:")
                    for i, table in enumerate(all_tables):
                        try:
                            csv_buffer = io.StringIO()
                            table.to_csv(csv_buffer, index=False)
                            csv_data = csv_buffer.getvalue()
                            
                            st.download_button(
                                label=f"Download Table {i+1}",
                                data=csv_data,
                                file_name=f"table_{i+1}_{uploaded_file.name.replace('.pdf', '')}.csv",
                                mime="text/csv",
                                key=f"table_{i}"
                            )
                        except Exception:
                            st.error(f"Could not process table {i+1}")
                            
            else:
                st.warning("❌ No tables found in the PDF.")
                st.info("""
                **Possible reasons:**
                - The PDF might not contain any tables
                - Tables might be in image format (not extractable as text)
                - The PDF might be password protected
                - Tables might have complex formatting that couldn't be detected
                
                **Suggestions:**
                - Try a different PDF file
                - Ensure the PDF contains text-based tables (not scanned images)
                - Check if the PDF requires a password
                """)
                
        except Exception as main_error:
            st.error("❌ An unexpected error occurred while processing the PDF.")
            st.error(f"Error details: {str(main_error)}")
            
            # Show detailed error in expander for debugging
            with st.expander("Technical Details (for debugging)"):
                st.code(traceback.format_exc())
            
            st.info("""
            **What you can try:**
            1. Refresh the page and try again
            2. Try with a different PDF file
            3. Ensure the PDF is not corrupted
            4. Check that the PDF is not password protected
            """)

# Add sidebar with usage instructions
with st.sidebar:
    st.header("📋 Usage Instructions")
    st.markdown("""
    1. **Upload** a PDF file using the file uploader
    2. **Wait** for the processing to complete
    3. **Review** the extracted tables in the preview
    4. **Download** the CSV file with all tables
    
    **Supported Files:**
    - PDF files up to 50MB
    - Text-based tables (not scanned images)
    - Unprotected PDFs
    
    **Tips:**
    - Larger files may take longer to process
    - Complex table layouts might not extract perfectly
    - Check the data preview before downloading
    """)
    
    st.header("🔧 Troubleshooting")
    st.markdown("""
    **Common Issues:**
    - **No tables found:** PDF might contain image-based tables
    - **Incomplete data:** Complex table formatting
    - **Processing errors:** File might be corrupted
    
    **Contact:** Report issues with specific error messages
    """)
