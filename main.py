import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
from datetime import datetime
import re
import requests
import fitz  # PyMuPDF
import plotly.graph_objects as go
import networkx as nx
from collections import defaultdict
import json

# Page config
st.set_page_config(
    page_title="SolidAdditive AI",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS with better styling
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1e3a8a 100%);
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.8rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        animation: fadeIn 0.5s;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .user-message {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
        color: white;
        margin-left: 15%;
        border-left: 4px solid #1d4ed8;
    }
    .assistant-message {
        background: white;
        color: black;
        margin-right: 15%;
        border-left: 4px solid #10b981;
    }
    .reference-box {
        background: #f0f9ff;
        border-left: 4px solid #0284c7;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
    }
    .reference-item {
        padding: 0.5rem;
        margin: 0.5rem 0;
        background: white;
        border-radius: 0.4rem;
        border: 1px solid #e5e7eb;
    }
    .knowledge-graph-container {
        background: white;
        padding: 1.5rem;
        border-radius: 0.8rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    h1, h2, h3 {
        color: white !important;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
    }
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: white;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 0.5rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .stat-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        background: #dbeafe;
        color: #1e40af;
        border-radius: 1rem;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'model' not in st.session_state:
    st.session_state.model = None
if 'knowledge_graph' not in st.session_state:
    st.session_state.knowledge_graph = defaultdict(list)
if 'references' not in st.session_state:
    st.session_state.references = []

def configure_gemini(api_key):
    """Configure Gemini API"""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        return model
    except Exception as e:
        st.error(f"Configuration Error: {str(e)}")
        return None

def extract_entities_and_relations(text):
    """Extract key entities and their relationships from text"""
    # Enhanced prompt for entity extraction
    extraction_prompt = f"""Analyze this text and extract key concepts and their relationships.
    
Text: {text[:1000]}

Return a JSON with:
1. "entities": list of main concepts/terms (max 10)
2. "relationships": list of {{source, relation, target}} dictionaries

Focus on technical terms, processes, materials, and their connections.
Format: {{"entities": ["term1", "term2"], "relationships": [{{"source": "term1", "relation": "uses", "target": "term2"}}]}}"""
    
    try:
        if st.session_state.model:
            response = st.session_state.model.generate_content(extraction_prompt)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('entities', []), data.get('relationships', [])
    except Exception as e:
        st.warning(f"Entity extraction failed: {str(e)}")
    
    # Fallback: simple keyword extraction
    keywords = re.findall(r'\b[A-Z][A-Za-z]{3,}\b', text)
    unique_keywords = list(set(keywords))[:10]
    return unique_keywords, []

def create_knowledge_graph(entities, relationships):
    """Create an interactive knowledge graph using Plotly"""
    G = nx.Graph()
    
    # Add nodes
    for entity in entities:
        G.add_node(entity)
    
    # Add edges
    for rel in relationships:
        if 'source' in rel and 'target' in rel:
            G.add_edge(rel['source'], rel['target'], label=rel.get('relation', ''))
    
    # If no relationships, create a simple connected graph
    if not relationships and len(entities) > 1:
        for i in range(len(entities) - 1):
            G.add_edge(entities[i], entities[i + 1])
    
    # Generate layout
    pos = nx.spring_layout(G, k=2, iterations=50)
    
    # Create edge traces
    edge_trace = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace.append(
            go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode='lines',
                line=dict(width=2, color='#94a3b8'),
                hoverinfo='none',
                showlegend=False
            )
        )
    
    # Create node trace
    node_x = []
    node_y = []
    node_text = []
    node_size = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_size.append(20 + G.degree(node) * 10)
    
    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="top center",
        textfont=dict(size=10, color='#1e293b', family='Arial Black'),
        hoverinfo='text',
        marker=dict(
            size=node_size,
            color='#3b82f6',
            line=dict(width=2, color='#1e40af'),
            symbol='circle'
        ),
        showlegend=False
    )
    
    # Create figure
    fig = go.Figure(data=edge_trace + [node_trace])
    
    fig.update_layout(
        title={
            'text': "Knowledge Graph",
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#1e293b', 'family': 'Arial Black'}
        },
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(240, 249, 255, 0.5)',
        paper_bgcolor='white',
        height=500
    )
    
    return fig

def search_google_images_simple(query, num_results=3):
    """Search for images using multiple methods"""
    image_urls = []
    
    # Method 1: Try DuckDuckGo
    try:
        from duckduckgo_search import DDGS
        st.info("Searching DuckDuckGo...")
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=num_results))
            image_urls = [r['image'] for r in results if 'image' in r]
            if image_urls:
                st.success(f"Found {len(image_urls)} images via DuckDuckGo")
                return image_urls
    except Exception as e:
        st.warning(f"DuckDuckGo search failed: {str(e)}")
    
    # Method 2: Try Bing scraping
    try:
        st.info("Searching Bing...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        search_url = f"https://www.bing.com/images/search?q={requests.utils.quote(query)}&FORM=HDRSC2"
        response = requests.get(search_url, headers=headers, timeout=10)
        
        urls = re.findall(r'"murl":"([^"]+)"', response.text)
        if urls:
            image_urls = urls[:num_results]
            st.success(f"Found {len(image_urls)} images via Bing")
            return image_urls
    except Exception as e:
        st.warning(f"Bing search failed: {str(e)}")
    
    # Method 3: Known URLs database
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
    
    query_lower = query.lower()
    for keyword, urls in known_urls_map.items():
        if keyword in query_lower:
            st.info(f"Using curated sources for '{keyword}'")
            return urls
    
    st.warning("Could not find images. Try uploading files or pasting direct URLs.")
    return []

def download_image(url):
    """Download and process image from URL"""
    try:
        st.info(f"Downloading: {url[:80]}...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.google.com/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        response.raise_for_status()
        
        image = Image.open(io.BytesIO(response.content))
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        
        # Resize if needed
        max_size = 1200
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        st.success(f"Downloaded: {image.size[0]}x{image.size[1]}px")
        return image
    except Exception as e:
        st.error(f"Download failed: {str(e)}")
        return None

def extract_urls_from_text(text):
    """Extract URLs from text"""
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(pattern, text)

def should_search_images(prompt):
    """Determine if image search is needed"""
    keywords = ['show', 'display', 'find', 'get', 'image', 'diagram', 'picture', 'photo', 'schematic', 'visualize']
    return any(k in prompt.lower() for k in keywords)

def extract_search_query(prompt):
    """Extract clean search query from prompt"""
    remove = ['show', 'display', 'find', 'get', 'me', 'an', 'a', 'the', 'image', 'of', 'picture', 'diagram', 'can', 'you', 'please']
    words = prompt.lower().split()
    search_words = [w for w in words if w not in remove and len(w) > 2]
    return ' '.join(search_words)

def process_image_file(uploaded_file):
    """Process uploaded image file"""
    try:
        image = Image.open(uploaded_file)
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')
        return image
    except Exception as e:
        st.error(f"Image processing error: {str(e)}")
        return None

def extract_pdf_images(pdf_file):
    """Extract images from PDF pages"""
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
        st.error(f"PDF extraction error: {str(e)}")
        return []

def extract_references_from_response(response_text, image_sources):
    """Extract and format references from the AI response"""
    references = []
    
    # Add image sources as references
    for idx, (img, source) in enumerate(image_sources):
        if 'URL:' in source:
            url = source.replace('URL:', '').strip()
            references.append({
                'type': 'Image Source',
                'title': f'Image {idx + 1}',
                'url': url,
                'description': 'Visual reference used in analysis'
            })
        elif 'Search:' in source:
            url = source.replace('Search:', '').strip()
            references.append({
                'type': 'Search Result',
                'title': f'Image {idx + 1}',
                'url': url,
                'description': 'Retrieved via image search'
            })
    
    # Extract potential citations from response (URLs, papers, etc.)
    urls_in_response = extract_urls_from_text(response_text)
    for url in urls_in_response:
        references.append({
            'type': 'Cited Source',
            'title': 'Referenced in response',
            'url': url,
            'description': 'Source mentioned by AI'
        })
    
    # Add knowledge base reference
    references.append({
        'type': 'AI Knowledge',
        'title': 'Gemini 2.0 Flash',
        'url': 'https://deepmind.google/technologies/gemini/',
        'description': 'AI model trained on solid-state additive manufacturing knowledge'
    })
    
    return references

def get_gemini_response(prompt, images=None, pdf_files=None):
    """Get AI response with enhanced analysis"""
    try:
        if not st.session_state.model:
            return " Please configure API key first", None, []
        
        all_images = []
        
        # Process URLs in prompt
        urls = extract_urls_from_text(prompt)
        for url in urls:
            img = download_image(url)
            if img:
                all_images.append((img, f"URL: {url[:50]}..."))
        
        # Process PDFs
        if pdf_files:
            for pdf_file in pdf_files:
                pdf_file.seek(0)
                pdf_imgs = extract_pdf_images(pdf_file)
                for idx, img in enumerate(pdf_imgs):
                    all_images.append((img, f"PDF Page {idx + 1}: {pdf_file.name}"))
        
        # Add uploaded images
        if images:
            for idx, img in enumerate(images):
                all_images.append((img, f"Uploaded Image {idx + 1}"))
        
        # Auto-search for images if requested
        if should_search_images(prompt) and not all_images:
            search_query = extract_search_query(prompt)
            if search_query:
                st.info(f" Searching for: **{search_query}**")
                image_urls = search_google_images_simple(f"{search_query} solid state additive manufacturing", num_results=3)
                
                if image_urls:
                    for url in image_urls:
                        img = download_image(url)
                        if img:
                            all_images.append((img, f"Search: {url[:50]}..."))
        
        # Enhanced prompt
        prompt_text = f"""You are an expert in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD).

User Question: {prompt}

Instructions:
1. Provide detailed, technical analysis
2. If images are provided, describe specific features, regions, and components visible
3. Structure your response with clear sections
4. Include technical terminology and explain concepts
5. When applicable, mention key processes, materials, and parameters

Be comprehensive but concise."""

        if all_images:
            prompt_text += f"\n\n Analyzing {len(all_images)} image(s). Provide detailed visual analysis."
        
        # Build content
        content_parts = [prompt_text]
        for img, _ in all_images:
            content_parts.append(img)
        
        # Generate response
        with st.spinner(" Generating response..."):
            response = st.session_state.model.generate_content(content_parts)
            response_text = response.text
        
        # Extract references
        references = extract_references_from_response(response_text, all_images)
        
        # Extract entities for knowledge graph
        entities, relationships = extract_entities_and_relations(response_text)
        
        # Update global knowledge graph
        for entity in entities:
            if entity not in st.session_state.knowledge_graph:
                st.session_state.knowledge_graph[entity] = []
        for rel in relationships:
            if 'source' in rel and 'target' in rel:
                st.session_state.knowledge_graph[rel['source']].append(
                    (rel.get('relation', 'relates_to'), rel['target'])
                )
        
        return response_text, all_images, references, entities, relationships
    
    except Exception as e:
        import traceback
        error_msg = f" Error: {str(e)}\n{traceback.format_exc()}"
        st.error(error_msg)
        return error_msg, None, [], [], []

def display_references(references):
    """Display formatted references"""
    if not references:
        return
    
    st.markdown('<div class="reference-box">', unsafe_allow_html=True)
    st.markdown("###  References & Sources")
    
    for idx, ref in enumerate(references, 1):
        ref_type = ref.get('type', 'Source')
        title = ref.get('title', 'Reference')
        url = ref.get('url', '#')
        desc = ref.get('description', '')
        
        st.markdown(f"""
        <div class="reference-item">
            <strong>[{idx}] {ref_type}:</strong> {title}<br>
            <small>{desc}</small><br>
            <a href="{url}" target="_blank" style="color: #2563eb;">🔗 {url[:80]}...</a>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_message(message, is_user=False):
    """Display chat message with enhanced formatting"""
    css_class = "user-message" if is_user else "assistant-message"
    role = " You" if is_user else " AI Assistant"
    
    with st.container():
        st.markdown(f'<div class="chat-message {css_class}">', unsafe_allow_html=True)
        st.markdown(f"**{role}** • {message['timestamp']}")
        
        # Display user files
        if is_user and message.get('files'):
            st.markdown("** Attached Files:**")
            cols = st.columns(min(len(message['files']), 4))
            for idx, f in enumerate(message['files']):
                with cols[idx % 4]:
                    if f.get('data'):
                        st.image(f['data'], caption=f['name'], use_column_width=True)
                    else:
                        st.markdown(f" {f['name']}")
        
        # Display message content
        st.markdown(message['content'])
        
        # Display response images
        if not is_user and message.get('response_images'):
            st.markdown("---")
            st.markdown("** Analyzed Images:**")
            cols = st.columns(min(len(message['response_images']), 3))
            for idx, (img, label) in enumerate(message['response_images']):
                with cols[idx % 3]:
                    st.image(img, caption=label, use_column_width=True)
        
        # Display references
        if not is_user and message.get('references'):
            display_references(message['references'])
        
        # Display knowledge graph
        if not is_user and message.get('entities') and len(message['entities']) > 1:
            with st.expander(" Knowledge Graph", expanded=False):
                fig = create_knowledge_graph(message['entities'], message.get('relationships', []))
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    """Main application"""
    
    # Sidebar
    with st.sidebar:
        st.title(" Configuration")
        
        api_key_input = st.text_input(
            "Gemini API Key",
            type="password",
            value=st.session_state.api_key or "",
            help="Enter your Google Gemini API key"
        )
        
        if st.button("Configure API", use_container_width=True):
            if api_key_input:
                model = configure_gemini(api_key_input)
                if model:
                    st.session_state.api_key = api_key_input
                    st.session_state.model = model
                    st.success(" API Configured!")
            else:
                st.error("Please enter an API key")
        
        st.markdown("---")
        
        # Stats
        st.markdown("###  Session Stats")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("Messages", len(st.session_state.messages))
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            total_concepts = len(st.session_state.knowledge_graph)
            st.metric("Concepts", total_concepts)
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Features
        st.markdown("###  Features")
        st.markdown("""
        <div style='background: white; padding: 1rem; border-radius: 0.5rem;'>
        •  <b>Smart Image Search</b><br>
        •  <b>Knowledge Graphs</b><br>
        •  <b>Reference Tracking</b><br>
        •  <b>Visual Analytics</b><br>
        •  <b>PDF Processing</b><br>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Example queries
        st.markdown("###  Try These")
        examples = [
            "Show me a cold spray diagram",
            "Explain CSAM microstructure",
            "Display UAM process",
            "Compare FSAM and AFSD"
        ]
        for example in examples:
            if st.button(f" {example}", use_container_width=True, key=example):
                st.session_state.example_query = example
        
        st.markdown("---")
        
        # Global knowledge graph
        if len(st.session_state.knowledge_graph) > 1:
            if st.button(" View Global Knowledge Graph", use_container_width=True):
                st.session_state.show_global_graph = True
        
        st.markdown("---")
        
        # Clear chat
        if st.button(" Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.knowledge_graph = defaultdict(list)
            st.rerun()
        
        st.markdown("---")
        st.caption(" SolidAdditive AI • Powered by Gemini 2.0")
    
    # Main content
    st.title(" SolidAdditive AI")
    st.markdown("""
    <div style='background: rgba(255, 255, 255, 0.1); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;'>
        <p style='color: white; margin: 0;'>
            <b>Advanced AI for Solid-State Additive Manufacturing</b><br>
            Ask questions, analyze images, and explore knowledge graphs! 
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API configuration
    if not st.session_state.api_key:
        st.warning(" Please configure your Gemini API key in the sidebar to get started.")
        st.info("Get your API key from: https://makersuite.google.com/app/apikey")
        return
    
    # Display global knowledge graph if requested
    if st.session_state.get('show_global_graph', False):
        st.markdown('<div class="knowledge-graph-container">', unsafe_allow_html=True)
        st.markdown("###  Global Knowledge Graph")
        st.markdown("*All concepts discussed in this session*")
        
        all_entities = list(st.session_state.knowledge_graph.keys())
        all_relationships = []
        for source, targets in st.session_state.knowledge_graph.items():
            for relation, target in targets:
                all_relationships.append({'source': source, 'relation': relation, 'target': target})
        
        if len(all_entities) > 1:
            fig = create_knowledge_graph(all_entities, all_relationships)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("Close Graph"):
            st.session_state.show_global_graph = False
            st.rerun()
    
    # Display chat messages
    for msg in st.session_state.messages:
        display_message(msg, is_user=(msg['role'] == 'user'))
    
    # File upload section
    with st.expander(" Upload Files (Images or PDFs)", expanded=False):
        uploaded_files = st.file_uploader(
            "Choose files to analyze",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'],
            accept_multiple_files=True,
            help="Upload images or PDF documents for analysis"
        )
    
    # Chat input
    user_input = st.chat_input("Ask me anything about solid-state additive manufacturing...")
    
    # Handle example query
    if st.session_state.get('example_query'):
        user_input = st.session_state.example_query
        st.session_state.example_query = None
    
    if user_input:
        images = []
        pdf_files = []
        file_info = []
        
        # Process uploaded files
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
        
        # Get AI response
        with st.spinner(" Analyzing and generating response..."):
            ai_response, response_images, references, entities, relationships = get_gemini_response(
                user_input,
                images=images,
                pdf_files=pdf_files
            )
        
        # Add AI message
        st.session_state.messages.append({
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'response_images': response_images,
            'references': references,
            'entities': entities,
            'relationships': relationships
        })
        
        st.rerun()

if __name__ == "__main__":
    main()
