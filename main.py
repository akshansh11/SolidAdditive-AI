import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime
import PyPDF2
import re
try:
    from pdf2image import convert_from_bytes
    PDF_IMAGE_SUPPORT = True
except ImportError:
    PDF_IMAGE_SUPPORT = False
import numpy as np

# Page configuration
st.set_page_config(
    page_title="SolidAdditive AI - An Agentic AI Model for Solid-state Additive Manufacturing Processes",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1e3a8a 100%);
    }
    .stTextInput > div > div > input {
        background-color: white;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #2563eb;
        color: white;
        margin-left: 20%;
    }
    .assistant-message {
        background-color: white;
        color: black;
        margin-right: 20%;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .upload-section {
        background-color: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    h1 {
        color: white !important;
    }
    h2, h3 {
        color: #e0e7ff !important;
    }
    .stButton > button {
        background-color: #2563eb;
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 0.5rem;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #1d4ed8;
    }
    .info-box {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        margin-bottom: 1rem;
    }
    .image-reference {
        background-color: #f0f9ff;
        border-left: 4px solid #2563eb;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
    </style>
""", unsafe_allow_html=True)

# Solid-state AM knowledge base context
SOLID_STATE_CONTEXT = """You are an expert AI assistant specialized EXCLUSIVELY in all solid-state additive manufacturing (AM) processes. 

SOLID-STATE ADDITIVE MANUFACTURING PROCESSES YOU SHOULD DISCUSS:
1. Cold Spray Additive Manufacturing (CSAM)
2. Ultrasonic Additive Manufacturing (UAM)
3. Friction Stir Additive Manufacturing (FSAM)
4. Additive Friction Stir Deposition (AFSD)
5. Solid-State Laser Deposition
6. Binder Jetting (powder-based, solid-state consolidation)

KEY CHARACTERISTICS OF SOLID-STATE AM:
- No melting of feedstock material
- Processing below melting temperature
- Minimal thermal distortion
- Reduced residual stresses
- Better material properties retention
- Suitable for temperature-sensitive materials
- Lower energy consumption compared to fusion-based processes

IMPORTANT RESTRICTIONS:
- DO NOT discuss fusion-based AM processes like: SLM, EBM, DMLS, SLS (melting processes), Wire Arc AM, DED with melting
- DO NOT discuss polymer 3D printing (FDM, SLA, SLS for polymers)
- ONLY focus on solid-state metal and ceramic additive manufacturing
- If asked about non-solid-state processes, politely redirect to solid-state alternatives

When answering queries:
1. Always verify the question is about solid-state AM processes
2. Provide technical details with scientific accuracy
3. Reference material properties, process parameters, and applications
4. Discuss advantages over fusion-based methods when relevant
5. Include information about microstructure, mechanical properties, and process optimization
6. If images are uploaded, analyze them in the context of solid-state AM only
7. When analyzing images, describe specific regions, features, and characteristics
8. Reference figure numbers when discussing content from papers
9. Provide detailed visual descriptions that can be correlated with displayed images

Always maintain focus on solid-state processes and redirect any queries about melting-based or polymer AM processes."""

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'model' not in st.session_state:
    st.session_state.model = None
if 'uploaded_images' not in st.session_state:
    st.session_state.uploaded_images = []

def configure_gemini(api_key):
    """Configure Gemini API with the provided key"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config={
                'temperature': 0.7,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 8192,
            }
        )
        return model
    except Exception as e:
        st.error(f"Error configuring API: {str(e)}")
        return None

def process_image(uploaded_file):
    """Process uploaded image file"""
    try:
        image = Image.open(uploaded_file)
        return image
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def extract_pdf_text(pdf_file):
    """Extract text from PDF file"""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page_num, page in enumerate(pdf_reader.pages):
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
        return None

def extract_pdf_images(pdf_file):
    """Extract images from PDF file as page screenshots"""
    if not PDF_IMAGE_SUPPORT:
        return []
    
    try:
        pdf_file.seek(0)
        images = convert_from_bytes(pdf_file.read(), dpi=150, fmt='PNG')
        return images
    except Exception as e:
        st.warning(f"Could not extract images from PDF: {str(e)}")
        return []

def extract_figure_references(text):
    """Extract figure references from text"""
    pattern = r'(Figure|Fig\.?|FIG\.?)\s*(\d+[a-z]?)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    figure_refs = list(set([f"Figure {m[1]}" for m in matches]))
    return sorted(figure_refs)

def create_image_with_label(image, label):
    """Add a label to an image"""
    try:
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        # Add label background
        text_bbox = draw.textbbox((10, 10), label, font=font)
        draw.rectangle(text_bbox, fill='black')
        draw.text((10, 10), label, fill='white', font=font)
        
        return img_copy
    except Exception as e:
        return image

def get_gemini_response(prompt, images=None, pdf_files=None, pdf_images=None):
    """Get response from Gemini API with multimodal support"""
    try:
        if not st.session_state.model:
            return "Please configure your API key first.", None, None
        
        content_parts = []
        
        # Build comprehensive prompt
        full_prompt = f"{SOLID_STATE_CONTEXT}\n\nUser Query: {prompt}"
        
        # Add PDF text if provided
        if pdf_files:
            for pdf_file in pdf_files:
                pdf_text = extract_pdf_text(pdf_file)
                if pdf_text:
                    full_prompt += f"\n\nPDF Document Content:\n{pdf_text[:50000]}"
                    # Extract figure references
                    fig_refs = extract_figure_references(pdf_text)
                    if fig_refs:
                        full_prompt += f"\n\nFigures mentioned in this paper: {', '.join(fig_refs)}"
        
        # Add instruction for image analysis
        if images or pdf_images:
            full_prompt += "\n\nIMPORTANT: When analyzing images, provide detailed descriptions of specific regions, features, and characteristics. Reference specific areas like 'in the upper left region', 'at the interface shown', 'the grain structure in the center', etc. If multiple images are provided, specify which image you're discussing."
        
        content_parts.append(full_prompt)
        
        # Add uploaded images
        if images:
            for idx, img in enumerate(images):
                content_parts.append(img)
        
        # Add PDF images
        if pdf_images:
            for idx, img in enumerate(pdf_images):
                content_parts.append(img)
        
        # Generate response
        response = st.session_state.model.generate_content(content_parts)
        
        # Return response text, images to display, and figure references
        response_images = []
        if images:
            response_images.extend([(img, f"Uploaded Image {i+1}") for i, img in enumerate(images)])
        if pdf_images:
            response_images.extend([(img, f"PDF Page {i+1}") for i, img in enumerate(pdf_images)])
        
        figure_refs = []
        if pdf_files:
            for pdf_file in pdf_files:
                pdf_file.seek(0)
                pdf_text = extract_pdf_text(pdf_file)
                if pdf_text:
                    figure_refs = extract_figure_references(pdf_text)
        
        return response.text, response_images, figure_refs
    
    except Exception as e:
        return f"Error generating response: {str(e)}", None, None

def display_message(message, is_user=False):
    """Display a chat message with enhanced image display"""
    css_class = "user-message" if is_user else "assistant-message"
    role = "You" if is_user else "AI Assistant"
    
    with st.container():
        st.markdown(f'<div class="chat-message {css_class}">', unsafe_allow_html=True)
        st.markdown(f"**{role}** - {message['timestamp']}")
        
        # Display uploaded files in user messages
        if is_user and 'files' in message and message['files']:
            st.markdown("**Uploaded files:**")
            cols = st.columns(min(len(message['files']), 4))
            for idx, file_info in enumerate(message['files']):
                with cols[idx % 4]:
                    if file_info['type'].startswith('image'):
                        st.image(file_info['data'], caption=file_info['name'], width=150)
                    else:
                        st.text(f"[PDF] {file_info['name']}")
        
        # Display response text
        st.markdown(message['content'])
        
        # Display referenced images in assistant messages
        if not is_user and 'response_images' in message and message['response_images']:
            st.markdown("---")
            st.markdown("**Referenced Images:**")
            
            # Create columns for images
            num_images = len(message['response_images'])
            cols = st.columns(min(num_images, 3))
            
            for idx, (img, label) in enumerate(message['response_images']):
                with cols[idx % 3]:
                    st.image(img, caption=label, use_container_width=True)
        
        # Display figure references
        if not is_user and 'figure_refs' in message and message['figure_refs']:
            st.markdown("---")
            st.markdown(f'<div class="image-reference"><strong>Figures Referenced in Paper:</strong> {", ".join(message["figure_refs"])}</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Sidebar for API configuration
    with st.sidebar:
        st.title("Configuration")
        
        # API Key input
        api_key_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.api_key or "",
            help="Get your API key from https://makersuite.google.com/app/apikey"
        )
        
        if st.button("Configure API"):
            if api_key_input:
                model = configure_gemini(api_key_input)
                if model:
                    st.session_state.api_key = api_key_input
                    st.session_state.model = model
                    st.success("API configured successfully!")
            else:
                st.error("Please enter a valid API key")
        
        st.markdown("---")
        
        # Information section
        st.markdown("### About This Assistant")
        st.markdown("""
        <div class="info-box">
        This assistant specializes in:<br><br>
        - Cold Spray AM (CSAM)<br>
        - Ultrasonic AM (UAM)<br>
        - Friction Stir AM (FSAM)<br>
        - AFSD<br>
        - Other solid-state processes<br><br>
        <strong>No fusion-based or polymer AM!</strong>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Enhanced features notice
        with st.expander("Enhanced Features"):
            st.markdown("""
            **Image Display:**
            - AI shows analyzed images in responses
            - References specific image regions
            - Displays figures from papers
            - Visual correlation with analysis
            
            **Figure Extraction:**
            - Extracts figure references from papers
            - Shows PDF pages as images
            - Links analysis to visual content
            """)
        
        st.markdown("---")
        
        # Example queries
        with st.expander("Example Questions"):
            st.markdown("""
            **With Images:**
            - "Analyze this microstructure image"
            - "Identify defects in the uploaded image"
            - "What process created this structure?"
            
            **With Papers:**
            - "Show me the figures from this paper"
            - "Explain Figure 3 from the uploaded paper"
            - "Summarize the results with images"
            
            **General:**
            - "Compare CSAM and UAM processes"
            - "Explain AFSD microstructure formation"
            """)
        
        st.markdown("---")
        
        # Clear chat button
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.session_state.uploaded_images = []
            st.rerun()
        
        st.markdown("---")
        
        # PDF image extraction notice
        if not PDF_IMAGE_SUPPORT:
            st.warning("Install pdf2image for PDF image extraction: pip install pdf2image")
        
        st.caption("SolidAdditive AI v2.0 - Enhanced Image Display")
    
    # Main content area
    st.title("SolidAdditive AI - Research Assistant")
    st.markdown("**Specialized in Cold Spray, UAM, FSAM, AFSD and other solid-state processes**")
    st.markdown("*Now with enhanced image display and figure extraction*")
    
    # Check if API is configured
    if not st.session_state.api_key:
        st.warning("Please configure your Gemini API key in the sidebar to get started.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            <div class="info-box">
            <h3>Getting Started:</h3>
            <ol>
            <li>Get your API key from <a href="https://makersuite.google.com/app/apikey" target="_blank" style="color: #93c5fd;">Google AI Studio</a></li>
            <li>Enter it in the sidebar</li>
            <li>Click "Configure API"</li>
            <li>Start asking questions!</li>
            </ol>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="info-box">
            <h3>Enhanced Capabilities:</h3>
            <ul>
            <li>AI shows images in responses</li>
            <li>References specific image regions</li>
            <li>Extracts figures from papers</li>
            <li>Visual analysis correlation</li>
            <li>Figure reference tracking</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
        return
    
    # Display welcome message if no chat history
    if not st.session_state.messages:
        st.markdown("""
        <div style='background-color: rgba(255, 255, 255, 0.1); padding: 2rem; border-radius: 0.5rem; color: white; text-align: center;'>
        <h2>Welcome to SolidAdditive AI</h2>
        <p>Ask questions about solid-state additive manufacturing processes, upload images for analysis, or submit research papers for review.</p>
        <p><strong>NEW: Images and figures are now displayed in AI responses!</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Example cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="info-box">
            <h4>Process Questions</h4>
            <p>Ask about CSAM, UAM, FSAM, AFSD parameters, mechanisms, and applications</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="info-box">
            <h4>Image Analysis</h4>
            <p>Upload microstructures - AI will show and reference specific regions in analysis</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="info-box">
            <h4>Paper Review</h4>
            <p>Submit PDFs - AI extracts figures and references them in explanations</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Display chat messages
    for message in st.session_state.messages:
        display_message(message, is_user=(message['role'] == 'user'))
    
    # File upload section
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.expander("Upload Files (Images or PDFs)", expanded=False):
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'],
            accept_multiple_files=True,
            help="Upload images (microstructures, equipment) or PDF research papers"
        )
        
        if uploaded_files:
            st.write(f"Files selected: {len(uploaded_files)}")
            cols = st.columns(min(len(uploaded_files), 4))
            for idx, file in enumerate(uploaded_files):
                with cols[idx % 4]:
                    if file.type.startswith('image'):
                        img = Image.open(file)
                        st.image(img, caption=file.name, width=150)
                    else:
                        st.text(f"[PDF] {file.name}")
    
    # Chat input
    st.markdown("<br>", unsafe_allow_html=True)
    user_input = st.chat_input("Ask about solid-state AM processes (CSAM, UAM, FSAM, AFSD)...")
    
    if user_input:
        # Process uploaded files
        images = []
        pdf_files = []
        pdf_images = []
        file_info = []
        
        if uploaded_files:
            for file in uploaded_files:
                file.seek(0)
                if file.type.startswith('image'):
                    img = process_image(file)
                    if img:
                        images.append(img)
                        file_info.append({
                            'name': file.name,
                            'type': file.type,
                            'data': img
                        })
                elif file.type == 'application/pdf':
                    pdf_files.append(file)
                    file_info.append({
                        'name': file.name,
                        'type': file.type,
                        'data': None
                    })
                    # Extract images from PDF
                    if PDF_IMAGE_SUPPORT:
                        file.seek(0)
                        pdf_imgs = extract_pdf_images(file)
                        if pdf_imgs:
                            pdf_images.extend(pdf_imgs[:5])  # Limit to first 5 pages
        
        # Add user message
        user_message = {
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'files': file_info if file_info else None
        }
        st.session_state.messages.append(user_message)
        
        # Get AI response with enhanced image display
        with st.spinner("Analyzing..."):
            ai_response, response_images, figure_refs = get_gemini_response(
                user_input, 
                images=images if images else None, 
                pdf_files=pdf_files if pdf_files else None,
                pdf_images=pdf_images if pdf_images else None
            )
        
        # Add assistant message with images
        assistant_message = {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'response_images': response_images if response_images else None,
            'figure_refs': figure_refs if figure_refs else None
        }
        st.session_state.messages.append(assistant_message)
        
        # Rerun to display new messages
        st.rerun()

if __name__ == "__main__":
    main()
