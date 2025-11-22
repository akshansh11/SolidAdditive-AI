import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
from datetime import datetime
import re
import requests
import fitz  # PyMuPDF

# Page config
st.set_page_config(
    page_title="SolidAdditive AI",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
    <style>
    .main {background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1e3a8a 100%);}
    .chat-message {padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;}
    .user-message {background-color: #2563eb; color: white; margin-left: 20%;}
    .assistant-message {background-color: white; color: black; margin-right: 20%; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);}
    h1, h2, h3 {color: white !important;}
    .stButton > button {background-color: #2563eb; color: white; border: none; padding: 0.5rem 2rem; border-radius: 0.5rem;}
    .stButton > button:hover {background-color: #1d4ed8;}
    </style>
""", unsafe_allow_html=True)

# Session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'model' not in st.session_state:
    st.session_state.model = None

def configure_gemini(api_key):
    """Configure Gemini"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        return model
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def search_google_images_simple(query, num_results=3):
    """Search for images using multiple methods"""
    image_urls = []
    
    # Method 1: Try DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        st.info("Trying DuckDuckGo search...")
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=num_results))
            image_urls = [r['image'] for r in results if 'image' in r]
            if image_urls:
                st.success(f"DuckDuckGo found {len(image_urls)} images")
                return image_urls
    except Exception as e:
        st.warning(f"DuckDuckGo failed: {str(e)}")
    
    # Method 2: Try Bing scraping
    try:
        st.info("Trying Bing search...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        search_url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&FORM=HDRSC2"
        response = requests.get(search_url, headers=headers, timeout=10)
        
        # Extract murl (media URL) from Bing results
        urls = re.findall(r'"murl":"([^"]+)"', response.text)
        if urls:
            image_urls = urls[:num_results]
            st.success(f"Bing found {len(image_urls)} images")
            return image_urls
    except Exception as e:
        st.warning(f"Bing failed: {str(e)}")
    
    # Method 3: Use hardcoded URLs for common queries
    known_urls = {
        'cold spray': ['https://upload.wikimedia.org/wikipedia/commons/3/3e/Cold_spray_diagram.svg'],
        'csam': ['https://upload.wikimedia.org/wikipedia/commons/3/3e/Cold_spray_diagram.svg'],
        'microstructure': [
            'https://www.researchgate.net/publication/326284434/figure/fig2/AS:646689899421696@1531197765496/Cold-spray-microstructure.png',
            'https://www.researchgate.net/publication/339486642/figure/fig1/AS:862318445121536@1582640155875/Microstructure-of-cold-sprayed-coating.png'
        ]
    }
    
    query_lower = query.lower()
    for keyword, urls in known_urls.items():
        if keyword in query_lower:
            st.info(f"Using known URLs for '{keyword}'")
            return urls
    
    st.warning("Could not find images through search. Please:")
    st.markdown("1. Paste a direct image URL in your message")
    st.markdown("2. Upload an image file")
    
    return []

def download_image(url):
    """Download image from URL"""
    try:
        st.info(f"Attempting to download: {url[:100]}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.google.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        st.info(f"Downloaded {len(response.content)} bytes")
        
        image = Image.open(io.BytesIO(response.content))
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        
        # Resize if too large
        max_size = 1200
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        st.success(f"Successfully loaded image: {image.size}")
        return image
    except Exception as e:
        st.error(f"Failed to download {url[:80]}: {str(e)}")
        return None

def extract_urls_from_text(text):
    """Extract URLs from text"""
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(pattern, text)

def should_search_images(prompt):
    """Check if user wants images"""
    keywords = ['show', 'display', 'find', 'get', 'image', 'diagram', 'picture', 'photo', 'schematic']
    return any(k in prompt.lower() for k in keywords)

def extract_search_query(prompt):
    """Extract search query from prompt"""
    # Remove common words
    remove = ['show', 'display', 'find', 'get', 'me', 'an', 'a', 'the', 'image', 'of', 'picture', 'diagram', 'can', 'you', 'please']
    words = prompt.lower().split()
    search_words = [w for w in words if w not in remove and len(w) > 2]
    return ' '.join(search_words)

def process_image_file(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        return image
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def extract_pdf_images(pdf_file):
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        images = []
        for page_num in range(min(len(pdf_document), 10)):
            page = pdf_document[page_num]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            images.append(image)
        
        pdf_document.close()
        return images
    except Exception as e:
        st.error(f"PDF error: {str(e)}")
        return []

def get_gemini_response(prompt, images=None, pdf_files=None):
    """Get AI response"""
    try:
        if not st.session_state.model:
            return "Configure API key first", None
        
        all_images = []
        
        # Check for URLs in prompt
        urls = extract_urls_from_text(prompt)
        for url in urls:
            img = download_image(url)
            if img:
                all_images.append((img, f"URL: {url[:50]}..."))
                st.success(f"Downloaded: {url[:60]}...")
        
        # Process PDFs
        if pdf_files:
            for pdf_file in pdf_files:
                pdf_file.seek(0)
                pdf_imgs = extract_pdf_images(pdf_file)
                for idx, img in enumerate(pdf_imgs):
                    all_images.append((img, f"PDF Page {idx + 1}"))
        
        # Add uploaded images
        if images:
            for idx, img in enumerate(images):
                all_images.append((img, f"Uploaded Image {idx + 1}"))
        
        # If user wants images and none provided, search for them
        if should_search_images(prompt) and not all_images:
            search_query = extract_search_query(prompt)
            if search_query:
                st.info(f"Searching for: {search_query}")
                
                # First, check if we have known URLs for this query
                known_urls_map = {
                    'cold spray': [
                        'https://upload.wikimedia.org/wikipedia/commons/3/3e/Cold_spray_diagram.svg',
                        'https://www.researchgate.net/profile/Rocco-Lupoi/publication/280921943/figure/fig1/AS:614292107042816@1523469396138/Schematic-representation-of-the-cold-spray-process.png'
                    ],
                    'csam': [
                        'https://upload.wikimedia.org/wikipedia/commons/3/3e/Cold_spray_diagram.svg'
                    ],
                    'microstructure': [
                        'https://www.researchgate.net/publication/326284434/figure/fig2/AS:646689899421696@1531197765496/SEM-image-of-cold-spray-coating-microstructure.png'
                    ]
                }
                
                image_urls = []
                for keyword, urls in known_urls_map.items():
                    if keyword in search_query.lower():
                        st.success(f"Using known URLs for '{keyword}'")
                        image_urls = urls
                        break
                
                # If no known URLs, try searching
                if not image_urls:
                    image_urls = search_google_images_simple(f"{search_query} solid state additive manufacturing", num_results=3)
                
                if image_urls:
                    st.info(f"Found {len(image_urls)} image URL(s)")
                    for url in image_urls:
                        img = download_image(url)
                        if img:
                            all_images.append((img, f"Search: {url[:50]}..."))
                
                if not all_images:
                    st.warning("Could not download images. Try:")
                    st.markdown("- Upload an image file")
                    st.markdown("- Paste a direct image URL")
                    st.markdown(f"- Search Google for '{search_query}' and paste an image URL")
        
        # Build prompt
        prompt_text = f"""You are an expert in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD).

User: {prompt}

CRITICAL: When images are provided, analyze them in detail. The images ARE displayed to the user.
Describe specific regions, features, and components you see in the images."""

        if all_images:
            prompt_text += f"\n\n{len(all_images)} images are shown. Analyze them thoroughly."
        
        # Build content
        content_parts = [prompt_text]
        for img, _ in all_images:
            content_parts.append(img)
        
        # Generate response
        response = st.session_state.model.generate_content(content_parts)
        return response.text, all_images
    
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        st.error(error_msg)
        return error_msg, None

def display_message(message, is_user=False):
    """Display chat message"""
    css_class = "user-message" if is_user else "assistant-message"
    role = "You" if is_user else "AI"
    
    with st.container():
        st.markdown(f'<div class="chat-message {css_class}">', unsafe_allow_html=True)
        st.markdown(f"**{role}** - {message['timestamp']}")
        
        if is_user and message.get('files'):
            st.markdown("**Files:**")
            for f in message['files']:
                if f.get('data'):
                    st.image(f['data'], caption=f['name'], width=150)
        
        st.markdown(message['content'])
        
        if not is_user and message.get('response_images'):
            st.markdown("---")
            st.markdown("**Images:**")
            for img, label in message['response_images']:
                st.image(img, caption=label, use_column_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    with st.sidebar:
        st.title("Configuration")
        
        api_key_input = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key or "")
        
        if st.button("Configure"):
            if api_key_input:
                model = configure_gemini(api_key_input)
                if model:
                    st.session_state.api_key = api_key_input
                    st.session_state.model = model
                    st.success("Configured!")
        
        st.markdown("---")
        
        st.markdown("### How It Works")
        st.markdown("- Searches Bing/DuckDuckGo for images")
        st.markdown("- Downloads and displays them")
        st.markdown("- AI analyzes the images")
        
        st.markdown("---")
        
        st.markdown("### Try These")
        st.code("Show cold spray diagram")
        st.code("Display CSAM process")
        st.code("Find UAM equipment")
        
        st.markdown("---")
        
        if st.button("Clear"):
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("---")
        st.caption("Uses Bing/DuckDuckGo image search")
    
    st.title("SolidAdditive AI")
    st.markdown("**Ask to 'Show CSAM diagram' - will search and display images!**")
    
    if not st.session_state.api_key:
        st.warning("Configure API key in sidebar")
        return
    
    # Display messages
    for msg in st.session_state.messages:
        display_message(msg, is_user=(msg['role'] == 'user'))
    
    # File upload
    with st.expander("Upload Files"):
        uploaded_files = st.file_uploader("Images or PDFs", type=['png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'], accept_multiple_files=True)
    
    # Chat input
    user_input = st.chat_input("Ask: 'Show cold spray diagram'")
    
    if user_input:
        images = []
        pdf_files = []
        file_info = []
        
        if uploaded_files:
            for file in uploaded_files:
                file.seek(0)
                if file.type.startswith('image'):
                    img = process_image_file(file)
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
        
        # Get response
        with st.spinner("Searching and analyzing..."):
            ai_response, response_images = get_gemini_response(user_input, images=images, pdf_files=pdf_files)
        
        # Add AI message
        st.session_state.messages.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'response_images': response_images
        })
        
        st.rerun()

if __name__ == "__main__":
    main()
