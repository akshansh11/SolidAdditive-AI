import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from datetime import datetime
import PyPDF2
import re
import requests
from urllib.parse import urlparse, quote
import fitz  # PyMuPDF for better PDF handling
import numpy as np
import json

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
6. If images are provided, analyze them in the context of solid-state AM only
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

def search_images_google(query, num_images=3):
    """Search for images using Google Custom Search API or scraping"""
    try:
        # Use Bing Image Search as it's more accessible
        search_url = f"https://www.bing.com/images/search?q={quote(query)}&form=HDRSC2"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Extract image URLs from the response
        image_urls = re.findall(r'"murl":"([^"]+)"', response.text)
        
        if image_urls:
            return image_urls[:num_images]
        else:
            # Fallback: try to find direct image links
            image_urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|gif|webp)', response.text)
            return list(set(image_urls))[:num_images]
    except Exception as e:
        st.warning(f"Could not search for images: {str(e)}")
        return []

def download_image_from_url(url):
    """Download image from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(url, headers=headers, timeout=15, stream=True)
        response.raise_for_status()
        
        # Read the content
        content = response.content
        
        # Try to open as image
        image = Image.open(io.BytesIO(content))
        
        # Convert to RGB if necessary
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        
        return image
    except Exception as e:
        return None

def extract_urls_from_text(text):
    """Extract URLs from text"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls

def is_image_url(url):
    """Check if URL points to an image"""
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.svg']
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # Check extension
    if any(path.endswith(ext) for ext in image_extensions):
        return True
    
    # Check if URL contains image-related keywords
    if any(keyword in url.lower() for keyword in ['image', 'img', 'photo', 'picture']):
        return True
    
    return False

def should_search_images(prompt):
    """Determine if the prompt is asking to display/show/find images"""
    keywords = [
        'display image', 'show image', 'show me image', 'display picture',
        'show picture', 'find image', 'get image', 'fetch image',
        'can you display', 'can you show', 'show an image', 'display an image',
        'show diagram', 'display diagram', 'show schematic', 'display schematic',
        'show equipment', 'display equipment', 'show setup', 'display setup'
    ]
    
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in keywords)

def extract_search_query(prompt):
    """Extract what to search for from the prompt"""
    prompt_lower = prompt.lower()
    
    # Common patterns
    patterns = [
        r'(?:display|show|find|get|fetch)\s+(?:an?\s+)?image\s+(?:of|for)\s+(.+?)(?:\?|$|\.)',
        r'(?:display|show|find|get|fetch)\s+(.+?)\s+image',
        r'can you (?:display|show)\s+(?:an?\s+)?image\s+(?:of|for)\s+(.+?)(?:\?|$|\.)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            return match.group(1).strip()
    
    # If no pattern matches, try to extract the main subject
    # Remove common words
    words = prompt_lower.split()
    search_words = [w for w in words if w not in ['can', 'you', 'display', 'show', 'image', 'of', 'an', 'a', 'the', '?', '.']]
    
    return ' '.join(search_words[:5])  # Take first 5 meaningful words

def process_image(uploaded_file):
    """Process uploaded image file"""
    try:
        image = Image.open(uploaded_file)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        return image
    except Exception as e:
        st.error(f"Error processing image: {str(e)}")
        return None

def extract_pdf_text(pdf_file):
    """Extract text from PDF file using PyMuPDF"""
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            text += f"\n--- Page {page_num + 1} ---\n"
            text += page.get_text()
        
        pdf_document.close()
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {str(e)}")
        return None

def extract_pdf_images_pymupdf(pdf_file):
    """Extract images from PDF file using PyMuPDF"""
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        # Open PDF with PyMuPDF
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        images = []
        for page_num in range(min(len(pdf_document), 10)):  # Limit to 10 pages
            page = pdf_document[page_num]
            
            # Render page to image at high resolution
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            images.append(image)
        
        pdf_document.close()
        return images
    except Exception as e:
        st.error(f"Error extracting PDF images: {str(e)}")
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

def get_gemini_response(prompt, images=None, pdf_files=None):
    """Get response from Gemini API with multimodal support"""
    try:
        if not st.session_state.model:
            return "Please configure your API key first.", None, None
        
        content_parts = []
        all_images = []
        pdf_images_list = []
        
        # Build comprehensive prompt
        full_prompt = f"{SOLID_STATE_CONTEXT}\n\nUser Query: {prompt}"
        
        # Check if user is asking to display/show images
        if should_search_images(prompt) and not images and not pdf_files:
            search_query = extract_search_query(prompt)
            st.info(f"Searching for images: {search_query}")
            
            # Search for images
            image_urls = search_images_google(search_query, num_images=3)
            
            url_images = []
            for url in image_urls[:3]:  # Try up to 3 images
                img = download_image_from_url(url)
                if img:
                    url_images.append((img, f"Search result: {url[:60]}..."))
                    st.success(f"Downloaded image from search")
            
            if not url_images:
                st.warning("Could not find images from search. Try providing a direct image URL.")
        else:
            # Extract and download images from URLs in the prompt
            urls = extract_urls_from_text(prompt)
            url_images = []
            
            for url in urls:
                # Try to download any URL as an image
                img = download_image_from_url(url)
                if img:
                    url_images.append((img, f"Image from: {url[:50]}..."))
                    st.info(f"Successfully downloaded image from URL")
        
        # Add PDF text and extract images if provided
        figure_refs = []
        if pdf_files:
            for pdf_file in pdf_files:
                # Extract text
                pdf_file.seek(0)
                pdf_text = extract_pdf_text(pdf_file)
                if pdf_text:
                    full_prompt += f"\n\nPDF Document Content:\n{pdf_text[:50000]}"
                    # Extract figure references
                    fig_refs = extract_figure_references(pdf_text)
                    if fig_refs:
                        figure_refs.extend(fig_refs)
                        full_prompt += f"\n\nFigures mentioned in this paper: {', '.join(fig_refs)}"
                
                # Extract images from PDF
                pdf_file.seek(0)
                pdf_imgs = extract_pdf_images_pymupdf(pdf_file)
                if pdf_imgs:
                    pdf_images_list.extend(pdf_imgs)
                    st.success(f"Extracted {len(pdf_imgs)} pages from PDF as images")
        
        # Add instruction for image analysis
        total_image_count = len(images or []) + len(url_images) + len(pdf_images_list)
        if total_image_count > 0:
            full_prompt += f"\n\nIMPORTANT: There are {total_image_count} images provided with this query. Analyze these images in detail. When analyzing images, provide detailed descriptions of specific regions, features, and characteristics. Reference specific areas like 'in the upper left region', 'at the interface shown', 'the grain structure in the center', etc. Specify which image you're discussing (e.g., 'In Image 1...', 'In the PDF page 2...')."
        
        content_parts.append(full_prompt)
        
        # Add all images to content and tracking
        image_counter = 1
        
        # Add uploaded images
        if images:
            for img in images:
                content_parts.append(img)
                all_images.append((img, f"Uploaded Image {image_counter}"))
                image_counter += 1
        
        # Add URL images
        for img, label in url_images:
            content_parts.append(img)
            all_images.append((img, label))
        
        # Add PDF images
        if pdf_images_list:
            for idx, img in enumerate(pdf_images_list):
                content_parts.append(img)
                all_images.append((img, f"PDF Page {idx + 1}"))
        
        # Generate response
        response = st.session_state.model.generate_content(content_parts)
        
        return response.text, all_images, figure_refs
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Error generating response: {str(e)}")
        st.error(f"Details: {error_details}")
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
                    if file_info['type'].startswith('image') and file_info['data'] is not None:
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
            if num_images > 0:
                cols_per_row = min(num_images, 2)
                
                for i in range(0, num_images, cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j in range(cols_per_row):
                        idx = i + j
                        if idx < num_images:
                            img, label = message['response_images'][idx]
                            with cols[j]:
                                st.image(img, caption=label, use_column_width=True)
        
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
            - Shows analyzed images in responses
            - SEARCHES and downloads images when you ask
            - Downloads images from URLs
            - Extracts images from PDFs (uses PyMuPDF)
            - References specific image regions
            - Visual correlation with analysis
            
            **Figure Extraction:**
            - Extracts figure references from papers
            - Shows PDF pages as images
            - Links analysis to visual content
            
            **Supported:**
            - Direct image uploads
            - Image URLs in messages (just paste the URL)
            - PDF papers with figures
            - "Show me image of CSAM" - will search and display!
            """)
        
        st.markdown("---")
        
        # Example queries
        with st.expander("Example Questions"):
            st.markdown("""
            **Ask AI to Find Images:**
            - "Can you display image of CSAM?"
            - "Show me CSAM microstructure"
            - "Display AFSD equipment setup"
            - "Show diagram of cold spray process"
            
            **With Uploaded Images:**
            - "Analyze this microstructure image"
            - "Identify defects in the uploaded image"
            - "What process created this structure?"
            
            **With URLs:**
            - "Analyze this image: [paste image URL]"
            - "Compare these microstructures: [URL1] [URL2]"
            
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
        
        st.success("PDF image extraction enabled (PyMuPDF)")
        st.success("Web image search enabled")
        
        st.caption("SolidAdditive AI v4.0 - With Image Search!")
    
    # Main content area
    st.title("SolidAdditive AI")
    st.markdown("**Specialized in Cold Spray, UAM, FSAM, AFSD and other solid-state processes**")
    st.markdown("*Now with automatic image search - just ask to display images!*")
    
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
            <li>AI SEARCHES for images automatically</li>
            <li>AI shows images in responses</li>
            <li>Downloads images from URLs</li>
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
        <p><strong>NEW: Just ask "Show me CSAM image" and I'll search and display it!</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Example cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="info-box">
            <h4>Ask for Images</h4>
            <p>"Show me CSAM equipment" - AI will search and display images!</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="info-box">
            <h4>Image Analysis</h4>
            <p>Upload images or paste URLs - AI will show and reference specific regions</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="info-box">
            <h4>Paper Review</h4>
            <p>Submit PDFs - AI extracts pages as images and references them</p>
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
    user_input = st.chat_input("Ask to 'show image of CSAM' or paste URLs...")
    
    if user_input:
        # Process uploaded files
        images = []
        pdf_files = []
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
        
        # Add user message
        user_message = {
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'files': file_info if file_info else None
        }
        st.session_state.messages.append(user_message)
        
        # Get AI response with enhanced image display
        with st.spinner("Analyzing (searching/downloading images, extracting PDF content)..."):
            ai_response, response_images, figure_refs = get_gemini_response(
                user_input, 
                images=images if images else None, 
                pdf_files=pdf_files if pdf_files else None
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
