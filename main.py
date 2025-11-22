import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
from datetime import datetime
import re
import requests
import fitz  # PyMuPDF
import traceback

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
if 'search_model' not in st.session_state:
    st.session_state.search_model = None

def configure_gemini(api_key):
    """Configure Gemini with Google Search grounding"""
    try:
        genai.configure(api_key=api_key)
        
        # Regular model for analyzing uploaded images
        model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config={
                'temperature': 0.7,
                'top_p': 0.95,
                'max_output_tokens': 8192,
            }
        )
        
        # Model with Google Search grounding for finding and showing images
        from google.generativeai.types import Tool
        search_tool = Tool(google_search=True)
        
        search_model = genai.GenerativeModel(
            'gemini-2.5-flash',
            tools=[search_tool],  # THIS IS THE KEY - enables Google Search with images
            generation_config={
                'temperature': 0.7,
                'top_p': 0.95,
                'max_output_tokens': 8192,
            }
        )
        
        return model, search_model
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None, None

def download_image(url):
    """Download image from URL"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        return image
    except Exception as e:
        st.error(f"Could not download: {str(e)}")
        return None

def extract_urls_from_text(text):
    """Extract URLs from text"""
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(pattern, text)

def extract_image_urls_from_response(response_text):
    """Extract image URLs from Gemini's response"""
    # Look for markdown image syntax
    md_images = re.findall(r'!\[.*?\]\((https?://[^\s\)]+)\)', response_text)
    
    # Look for plain URLs that end with image extensions
    url_pattern = r'http[s]?://[^\s<>"]+?\.(?:jpg|jpeg|png|gif|webp)'
    direct_urls = re.findall(url_pattern, response_text, re.IGNORECASE)
    
    # Look for URLs in the response
    all_urls = extract_urls_from_text(response_text)
    image_urls = [url for url in all_urls if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
    
    return list(set(md_images + direct_urls + image_urls))

def should_use_search(prompt):
    """Check if we should use Google Search grounding"""
    search_keywords = ['show', 'display', 'find', 'search', 'get', 'image', 'diagram', 'picture', 'photo']
    return any(keyword in prompt.lower() for keyword in search_keywords)

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
    """Get AI response - uses search model if needed"""
    try:
        if not st.session_state.model:
            return "Configure API key first", None
        
        content_parts = []
        all_images = []
        
        # Check for URLs in prompt
        urls = extract_urls_from_text(prompt)
        url_images = []
        for url in urls:
            img = download_image(url)
            if img:
                url_images.append((img, f"From URL: {url[:50]}..."))
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
        
        # Add URL images
        all_images.extend(url_images)
        
        # If user wants to search for images and no images provided, use search model
        if should_use_search(prompt) and not all_images:
            st.info("Using Google Search to find images...")
            
            # Use the search-enabled model
            search_prompt = f"""You are an expert in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD).

User asked: {prompt}

Please search Google for relevant images and provide:
1. Direct image URLs that you find
2. A detailed technical explanation of the topic
3. Analysis of what these images show

Focus on solid-state AM processes only. Provide actual image URLs that can be downloaded."""

            response = st.session_state.search_model.generate_content(search_prompt)
            response_text = response.text
            
            # Extract image URLs from the response
            image_urls = extract_image_urls_from_response(response_text)
            
            st.info(f"Found {len(image_urls)} image URLs in response")
            
            # Download the images
            for url in image_urls[:5]:  # Limit to 5 images
                st.info(f"Downloading: {url[:80]}...")
                img = download_image(url)
                if img:
                    all_images.append((img, f"Search result: {url[:50]}..."))
                    st.success("Downloaded!")
            
            return response_text, all_images
        
        # Otherwise use regular model with images
        else:
            prompt_text = f"""You are an expert in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD).

User: {prompt}

CRITICAL: When images are provided, analyze them in detail. The images ARE displayed to the user.
Describe specific regions, features, components visible in the images."""

            if all_images:
                prompt_text += f"\n\n{len(all_images)} images are being shown. Analyze them."
            
            content_parts.append(prompt_text)
            for img, _ in all_images:
                content_parts.append(img)
            
            response = st.session_state.model.generate_content(content_parts)
            return response.text, all_images
    
    except Exception as e:
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
                if f['data']:
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
                model, search_model = configure_gemini(api_key_input)
                if model and search_model:
                    st.session_state.api_key = api_key_input
                    st.session_state.model = model
                    st.session_state.search_model = search_model
                    st.success("Configured with Google Search!")
        
        st.markdown("---")
        
        st.markdown("### How It Works")
        st.markdown("Uses Gemini's built-in **Google Search** capability")
        st.markdown("When you ask to show images, it:")
        st.markdown("1. Searches Google")
        st.markdown("2. Finds image URLs")
        st.markdown("3. Downloads and displays them")
        
        st.markdown("---")
        
        st.markdown("### Try These")
        st.code("Show me CSAM diagram")
        st.code("Display cold spray process")
        st.code("Find UAM equipment image")
        
        st.markdown("---")
        
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    
    st.title("SolidAdditive AI")
    st.markdown("**Uses Gemini's Google Search - just ask to show images!**")
    
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
    user_input = st.chat_input("Ask to 'Show me CSAM diagram'")
    
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
        with st.spinner("Searching and processing..."):
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
