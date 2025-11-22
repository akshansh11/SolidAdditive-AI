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

# Solid-state AM knowledge base context - MODIFIED to always display images
SOLID_STATE_CONTEXT = """You are an expert AI assistant specialized EXCLUSIVELY in all solid-state additive manufacturing (AM) processes. 

CRITICAL INSTRUCTION: When images are provided to you, YOU MUST analyze them in detail. DO NOT say you cannot display images. The images are already being displayed to the user alongside your response. Your job is to ANALYZE the images that are shown.

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

When answering queries:
1. Always verify the question is about solid-state AM processes
2. Provide technical details with scientific accuracy
3. If images are provided, analyze them directly - they are being displayed to the user
4. Describe specific regions, features, and characteristics you see in the images
5. Reference "In the image shown" or "The diagram displays" when analyzing
6. Never say you cannot display or show images - they are already shown to the user

IMPORTANT: If a user asks "can you display image of X" or "show me image of X", understand that they want you to analyze images that will be fetched and displayed. Provide analysis assuming the images are visible."""

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

def search_wikipedia_images(query, num_images=2):
    """Search Wikipedia for images"""
    try:
        # Search Wikipedia API
        search_url = f"https://en.wikipedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': query,
            'utf8': 1
        }
        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()
        
        image_urls = []
        if 'query' in data and 'search' in data['query']:
            for result in data['query']['search'][:3]:
                title = result['title']
                # Get images from the page
                img_params = {
                    'action': 'query',
                    'format': 'json',
                    'titles': title,
                    'prop': 'images',
                    'imlimit': 5
                }
                img_response = requests.get(search_url, params=img_params, timeout=10)
                img_data = img_response.json()
                
                if 'query' in img_data and 'pages' in img_data['query']:
                    for page_id, page in img_data['query']['pages'].items():
                        if 'images' in page:
                            for img in page['images']:
                                img_title = img['title']
                                # Get actual image URL
                                url_params = {
                                    'action': 'query',
                                    'format': 'json',
                                    'titles': img_title,
                                    'prop': 'imageinfo',
                                    'iiprop': 'url'
                                }
                                url_response = requests.get(search_url, params=url_params, timeout=10)
                                url_data = url_response.json()
                                
                                if 'query' in url_data and 'pages' in url_data['query']:
                                    for url_page_id, url_page in url_data['query']['pages'].items():
                                        if 'imageinfo' in url_page and len(url_page['imageinfo']) > 0:
                                            img_url = url_page['imageinfo'][0].get('url')
                                            if img_url and img_url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                                image_urls.append(img_url)
                                                if len(image_urls) >= num_images:
                                                    return image_urls
        
        return image_urls
    except Exception as e:
        st.warning(f"Wikipedia search failed: {str(e)}")
        return []

def search_wikimedia_commons(query, num_images=3):
    """Search Wikimedia Commons for images"""
    try:
        search_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            'action': 'query',
            'format': 'json',
            'list': 'search',
            'srsearch': query,
            'srnamespace': 6,  # File namespace
            'srlimit': 10,
            'utf8': 1
        }
        
        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()
        
        image_urls = []
        if 'query' in data and 'search' in data['query']:
            for result in data['query']['search'][:num_images]:
                title = result['title']
                
                # Get image info
                info_params = {
                    'action': 'query',
                    'format': 'json',
                    'titles': title,
                    'prop': 'imageinfo',
                    'iiprop': 'url',
                    'utf8': 1
                }
                
                info_response = requests.get(search_url, params=info_params, timeout=10)
                info_data = info_response.json()
                
                if 'query' in info_data and 'pages' in info_data['query']:
                    for page_id, page in info_data['query']['pages'].items():
                        if 'imageinfo' in page and len(page['imageinfo']) > 0:
                            img_url = page['imageinfo'][0].get('url')
                            if img_url:
                                image_urls.append(img_url)
        
        return image_urls
    except Exception as e:
        st.warning(f"Wikimedia Commons search failed: {str(e)}")
        return []

def search_images_serpapi(query, num_images=3):
    """Fallback: Try to scrape Google Images"""
    try:
        # Try direct image search on Google
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        search_url = f"https://www.google.com/search?q={quote(query)}&tbm=isch"
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Extract image URLs using regex
        image_urls = re.findall(r'"ou":"([^"]+)"', response.text)
        
        # Filter for valid image URLs
        valid_urls = []
        for url in image_urls:
            if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                valid_urls.append(url)
                if len(valid_urls) >= num_images:
                    break
        
        return valid_urls
    except Exception as e:
        st.warning(f"Google Images search failed: {str(e)}")
        return []

def download_image_from_url(url):
    """Download image from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/'
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
        
        # Resize if too large
        max_size = 1200
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        return image
    except Exception as e:
        return None

def extract_urls_from_text(text):
    """Extract URLs from text"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, text)
    return urls

def should_search_images(prompt):
    """Determine if the prompt is asking to display/show/find images"""
    keywords = [
        'display image', 'show image', 'show me image', 'display picture',
        'show picture', 'find image', 'get image', 'fetch image',
        'can you display', 'can you show', 'show an image', 'display an image',
        'show diagram', 'display diagram', 'show schematic', 'display schematic',
        'show equipment', 'display equipment', 'show setup', 'display setup',
        'show me', 'display', 'show', 'find diagram'
    ]
    
    prompt_lower = prompt.lower()
    return any(keyword in prompt_lower for keyword in keywords)

def extract_search_query(prompt):
    """Extract what to search for from the prompt"""
    prompt_lower = prompt.lower()
    
    # Remove request words
    remove_words = ['can', 'you', 'please', 'display', 'show', 'me', 'an', 'a', 'the', 'image', 'of', 'picture', 'diagram', '?', '.']
    words = prompt_lower.split()
    search_words = [w for w in words if w not in remove_words]
    
    return ' '.join(search_words)

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
        url_images = []
        if should_search_images(prompt) and not images and not pdf_files:
            search_query = extract_search_query(prompt)
            st.info(f"Searching for: {search_query}")
            
            # Try multiple sources
            image_urls = []
            
            # Try Wikimedia Commons first (most reliable)
            st.info("Searching Wikimedia Commons...")
            image_urls = search_wikimedia_commons(search_query, num_images=3)
            
            # If not found, try Wikipedia
            if not image_urls:
                st.info("Searching Wikipedia...")
                image_urls = search_wikipedia_images(search_query, num_images=2)
            
            # Last resort: try Google Images scraping
            if not image_urls:
                st.info("Searching Google Images...")
                image_urls = search_images_serpapi(search_query, num_images=3)
            
            # Download images
            if image_urls:
                for url in image_urls:
                    img = download_image_from_url(url)
                    if img:
                        url_images.append((img, f"Found: {url[:60]}..."))
                        st.success(f"Downloaded image from: {url[:80]}...")
                    
            if not url_images:
                st.warning("Could not find images. Try uploading an image or providing a direct URL.")
                full_prompt += "\n\nNote: No images were found for this query. Please provide a detailed text-based explanation instead."
        else:
            # Extract and download images from URLs in the prompt
            urls = extract_urls_from_text(prompt)
            
            for url in urls:
                img = download_image_from_url(url)
                if img:
                    url_images.append((img, f"Image from: {url[:50]}..."))
                    st.info(f"Downloaded image from URL")
        
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
            full_prompt += f"\n\nCRITICAL: There are {total_image_count} images being displayed to the user alongside your response. You MUST analyze these images. Describe what you see in detail. Reference specific features, regions, and components. Start your response by acknowledging and analyzing the images shown."
        
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
        st.error(f"Error: {str(e)}")
        return f"Error: {str(e)}", None, None

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
            st.markdown("**Images Being Analyzed:**")
            
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
        
        st.markdown("### About This Assistant")
        st.markdown("""
        <div class="info-box">
        Specializes in solid-state AM:<br>
        - CSAM, UAM, FSAM, AFSD<br>
        - Searches Wikipedia/Wikimedia for images<br>
        - Analyzes uploaded images<br>
        - Extracts PDF figures
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        with st.expander("How It Works"):
            st.markdown("""
            **When you ask "show me CSAM":**
            1. Searches Wikimedia Commons
            2. Falls back to Wikipedia
            3. Downloads found images
            4. Sends to AI for analysis
            5. DISPLAYS images with analysis
            
            **Sources used:**
            - Wikimedia Commons (open license)
            - Wikipedia images
            - Your uploaded files
            - URLs you provide
            """)
        
        st.markdown("---")
        
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        
        st.success("Image search: Wikimedia + Wikipedia")
        st.caption("SolidAdditive AI v5.0")
    
    # Main content
    st.title("SolidAdditive AI")
    st.markdown("**Try: 'Show me CSAM diagram' or 'Display cold spray equipment'**")
    
    if not st.session_state.api_key:
        st.warning("Configure your Gemini API key in the sidebar")
        return
    
    # Display chat messages
    for message in st.session_state.messages:
        display_message(message, is_user=(message['role'] == 'user'))
    
    # File upload
    with st.expander("Upload Files", expanded=False):
        uploaded_files = st.file_uploader(
            "Images or PDFs",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            st.write(f"Files: {len(uploaded_files)}")
            cols = st.columns(min(len(uploaded_files), 4))
            for idx, file in enumerate(uploaded_files):
                with cols[idx % 4]:
                    if file.type.startswith('image'):
                        img = Image.open(file)
                        st.image(img, caption=file.name, width=150)
                    else:
                        st.text(f"[PDF] {file.name}")
    
    # Chat input
    user_input = st.chat_input("Try: 'Show me CSAM equipment'")
    
    if user_input:
        # Process files
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
                        file_info.append({'name': file.name, 'type': file.type, 'data': img})
                elif file.type == 'application/pdf':
                    pdf_files.append(file)
                    file_info.append({'name': file.name, 'type': file.type, 'data': None})
        
        # Add user message
        st.session_state.messages.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'files': file_info if file_info else None
        })
        
        # Get AI response
        with st.spinner("Processing..."):
            ai_response, response_images, figure_refs = get_gemini_response(
                user_input, 
                images=images if images else None, 
                pdf_files=pdf_files if pdf_files else None
            )
        
        # Add assistant message
        st.session_state.messages.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'response_images': response_images if response_images else None,
            'figure_refs': figure_refs if figure_refs else None
        })
        
        st.rerun()

if __name__ == "__main__":
    main()
