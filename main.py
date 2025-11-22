import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
from datetime import datetime
import re
import fitz  # PyMuPDF
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
from collections import defaultdict
import json
import pandas as pd
import numpy as np

# Page config
st.set_page_config(
    page_title="SolidAdditive AI - An Agentic model for solid-state additive manufacturing processes",
    page_icon=" ",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced CSS
st.markdown("""
    <style>
    .main {background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 50%, #1e3a8a 100%);}
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
    .knowledge-graph-container {
        background: white;
        padding: 1.5rem;
        border-radius: 0.8rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    .parameter-card {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 3px solid #3b82f6;
    }
    .comparison-table {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
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
if 'process_comparisons' not in st.session_state:
    st.session_state.process_comparisons = []
if 'material_database' not in st.session_state:
    st.session_state.material_database = {}
if 'conversation_context' not in st.session_state:
    st.session_state.conversation_context = []

# Solid-State AM Process Database
SSAM_PROCESSES = {
    "CSAM": {
        "name": "Cold Spray Additive Manufacturing",
        "temperature_range": "< 0.5 Tm",
        "bonding_mechanism": "Kinetic energy, plastic deformation",
        "typical_materials": ["Al", "Cu", "Ti", "Stainless Steel", "Composites"],
        "advantages": ["No melting", "Low oxidation", "High deposition rate", "Thick coatings"],
        "limitations": ["Limited geometry", "Porosity control", "Equipment cost"],
        "typical_velocity": "300-1200 m/s",
        "typical_pressure": "1-5 MPa",
        "applications": ["Repair", "Coatings", "Structural components"]
    },
    "UAM": {
        "name": "Ultrasonic Additive Manufacturing",
        "temperature_range": "< 0.5 Tm",
        "bonding_mechanism": "Ultrasonic vibration, solid-state welding",
        "typical_materials": ["Al", "Cu", "Stainless Steel", "Ti", "Composites"],
        "advantages": ["Precision", "Embedded sensors", "Low temperature", "Dissimilar metals"],
        "limitations": ["Slow deposition", "Layer delamination", "Surface finish"],
        "typical_frequency": "20 kHz",
        "typical_force": "1000-4000 N",
        "applications": ["Aerospace", "Electronics", "Embedded systems"]
    },
    "FSAM": {
        "name": "Friction Stir Additive Manufacturing",
        "temperature_range": "0.6-0.9 Tm",
        "bonding_mechanism": "Friction heat, plastic deformation",
        "typical_materials": ["Al alloys", "Mg alloys", "Steel", "Ti"],
        "advantages": ["Dense parts", "Good mechanical properties", "Large components"],
        "limitations": ["Tool wear", "Complex geometries limited", "Force requirements"],
        "typical_rotation": "200-2000 RPM",
        "typical_traverse": "50-500 mm/min",
        "applications": ["Structural parts", "Large components", "Repair"]
    },
    "AFSD": {
        "name": "Additive Friction Stir Deposition",
        "temperature_range": "0.7-0.95 Tm",
        "bonding_mechanism": "Friction heat, severe plastic deformation",
        "typical_materials": ["Al", "Mg", "Ti", "Steel", "Inconel"],
        "advantages": ["High density", "Excellent properties", "Large parts", "High deposition"],
        "limitations": ["Equipment requirements", "Process control", "Tool design"],
        "typical_rotation": "300-600 RPM",
        "typical_feed_rate": "100-300 mm/min",
        "applications": ["Aerospace", "Defense", "Large structures"]
    }
}

# Material properties database
MATERIAL_DATABASE = {
    "Aluminum 6061": {
        "density": "2.70 g/cm³",
        "melting_point": "582-652°C",
        "thermal_conductivity": "167 W/m·K",
        "yield_strength": "276 MPa",
        "ssam_compatibility": ["CSAM", "UAM", "FSAM", "AFSD"],
        "common_applications": "Aerospace, automotive, structural"
    },
    "Copper": {
        "density": "8.96 g/cm³",
        "melting_point": "1085°C",
        "thermal_conductivity": "401 W/m·K",
        "yield_strength": "70 MPa",
        "ssam_compatibility": ["CSAM", "UAM"],
        "common_applications": "Electronics, heat exchangers, conductors"
    },
    "Titanium Ti-6Al-4V": {
        "density": "4.43 g/cm³",
        "melting_point": "1604-1660°C",
        "thermal_conductivity": "6.7 W/m·K",
        "yield_strength": "880 MPa",
        "ssam_compatibility": ["CSAM", "UAM", "FSAM", "AFSD"],
        "common_applications": "Aerospace, biomedical, high-performance"
    },
    "Stainless Steel 316L": {
        "density": "8.00 g/cm³",
        "melting_point": "1375-1400°C",
        "thermal_conductivity": "16 W/m·K",
        "yield_strength": "170 MPa",
        "ssam_compatibility": ["CSAM", "UAM", "FSAM"],
        "common_applications": "Corrosion resistance, marine, chemical"
    }
}

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
    extraction_prompt = f"""Analyze this text about solid-state additive manufacturing and extract:

Text: {text[:1500]}

Return JSON with:
1. "entities": list of main technical concepts (max 12)
2. "relationships": list of {{"source", "relation", "target"}} dictionaries

Focus on: processes, materials, parameters, properties, defects, applications.
Format: {{"entities": ["term1", "term2"], "relationships": [{{"source": "term1", "relation": "uses", "target": "term2"}}]}}"""
    
    try:
        if st.session_state.model:
            response = st.session_state.model.generate_content(extraction_prompt)
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get('entities', []), data.get('relationships', [])
    except Exception as e:
        pass
    
    # Fallback: extract technical keywords
    keywords = re.findall(r'\b[A-Z][A-Za-z]{3,}\b', text)
    unique_keywords = list(set(keywords))[:12]
    return unique_keywords, []

def create_knowledge_graph(entities, relationships):
    """Create interactive knowledge graph"""
    G = nx.Graph()
    
    for entity in entities:
        G.add_node(entity)
    
    for rel in relationships:
        if 'source' in rel and 'target' in rel:
            G.add_edge(rel['source'], rel['target'], label=rel.get('relation', ''))
    
    if not relationships and len(entities) > 1:
        for i in range(len(entities) - 1):
            G.add_edge(entities[i], entities[i + 1])
    
    pos = nx.spring_layout(G, k=2, iterations=50)
    
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
    
    node_x, node_y, node_text, node_size = [], [], [], []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_size.append(20 + G.degree(node) * 10)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
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
    
    fig = go.Figure(data=edge_trace + [node_trace])
    
    fig.update_layout(
        title={'text': "Knowledge Graph", 'x': 0.5, 'xanchor': 'center',
               'font': {'size': 20, 'color': '#1e293b', 'family': 'Arial Black'}},
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

def create_process_comparison_chart(processes):
    """Create comparison chart for SSAM processes"""
    if not processes or len(processes) < 2:
        return None
    
    categories = ['Temperature', 'Deposition Rate', 'Precision', 'Material Range', 'Cost']
    
    # Normalized scores for comparison (0-10 scale)
    scores = {
        'CSAM': [2, 9, 6, 8, 7],
        'UAM': [2, 3, 9, 7, 6],
        'FSAM': [7, 6, 7, 7, 8],
        'AFSD': [8, 8, 7, 8, 9]
    }
    
    fig = go.Figure()
    
    for process in processes:
        if process in scores:
            fig.add_trace(go.Scatterpolar(
                r=scores[process],
                theta=categories,
                fill='toself',
                name=process
            ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10])
        ),
        showlegend=True,
        title="Process Comparison",
        height=500
    )
    
    return fig

def create_parameter_table(process_name):
    """Create parameter recommendations table"""
    if process_name not in SSAM_PROCESSES:
        return None
    
    process = SSAM_PROCESSES[process_name]
    
    # Create DataFrame
    data = {
        'Parameter': [],
        'Range': [],
        'Notes': []
    }
    
    if process_name == 'CSAM':
        data = {
            'Parameter': ['Particle Velocity', 'Gas Pressure', 'Gas Temperature', 'Standoff Distance', 'Traverse Speed'],
            'Range': ['300-1200 m/s', '1-5 MPa', '200-1000°C', '10-50 mm', '10-500 mm/s'],
            'Notes': ['Critical for bonding', 'Affects velocity', 'Affects particle temp', 'Affects deposition', 'Affects build quality']
        }
    elif process_name == 'UAM':
        data = {
            'Parameter': ['Frequency', 'Amplitude', 'Normal Force', 'Weld Speed', 'Layer Thickness'],
            'Range': ['20 kHz', '10-50 µm', '1000-4000 N', '20-100 mm/s', '100-200 µm'],
            'Notes': ['Fixed by system', 'Key parameter', 'Critical for bonding', 'Affects quality', 'Per layer']
        }
    elif process_name in ['FSAM', 'AFSD']:
        data = {
            'Parameter': ['Rotation Speed', 'Traverse Speed', 'Axial Force', 'Feed Rate', 'Tool Design'],
            'Range': ['200-2000 RPM', '50-500 mm/min', '5-50 kN', '100-300 mm/min', 'Process specific'],
            'Notes': ['Affects heat', 'Affects microstructure', 'Critical parameter', 'Deposition rate', 'Affects flow']
        }
    
    df = pd.DataFrame(data)
    return df

def extract_pdf_text(pdf_file):
    """Extract text from PDF"""
    try:
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        text = ""
        for page_num in range(min(len(pdf_document), 20)):
            page = pdf_document[page_num]
            text += page.get_text()
        
        pdf_document.close()
        return text
    except Exception as e:
        st.error(f"PDF text extraction error: {str(e)}")
        return ""

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
        st.error(f"PDF image extraction error: {str(e)}")
        return []

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

def validate_ssam_query(query):
    """Validate that query is related to solid-state additive manufacturing"""
    
    # SSAM-related keywords
    ssam_keywords = [
        'csam', 'cold spray', 'uam', 'ultrasonic', 'fsam', 'friction stir',
        'afsd', 'additive friction', 'solid state', 'solid-state',
        'kinetic spray', 'supersonic', 'cold gas', 'friction', 'ultrasonic welding',
        'microstructure', 'bonding', 'deposition', 'particle', 'substrate',
        'aluminum', 'copper', 'titanium', 'metal', 'alloy', 'coating'
    ]
    
    # Non-SSAM manufacturing processes to reject
    excluded_keywords = [
        'fdm', 'fused deposition', 'sla', 'stereolithography', 'sls', 'selective laser',
        'dmls', 'direct metal laser', 'ebm', 'electron beam', 'binder jetting',
        'material jetting', 'polyjet', '3d printing', 'powder bed',
        'laser melting', 'laser sintering', 'arc welding', 'mig', 'tig',
        'casting', 'forging', 'machining', 'cnc', 'injection molding',
        'extrusion', 'thermoforming', 'stamping', 'rolling'
    ]
    
    query_lower = query.lower()
    
    # Check for excluded processes first
    for excluded in excluded_keywords:
        if excluded in query_lower:
            return False, f"This app is exclusively for Solid-State Additive Manufacturing (CSAM, UAM, FSAM, AFSD). Questions about '{excluded}' and other non-solid-state processes are outside the scope."
    
    # Check for SSAM-related content
    has_ssam_content = any(keyword in query_lower for keyword in ssam_keywords)
    
    # If query is very short (< 3 words), be lenient
    if len(query.split()) < 3:
        has_ssam_content = True
    
    if not has_ssam_content:
        return False, "This app specializes exclusively in Solid-State Additive Manufacturing (CSAM, UAM, FSAM, AFSD). Please ask questions specifically about these solid-state processes, their materials, parameters, or applications."
    
    return True, ""

def get_gemini_response(prompt, images=None, pdf_files=None, mode="general"):
    """Get AI response with specialized prompts - SSAM ONLY"""
    try:
        if not st.session_state.model:
            return "Please configure API key first", None, [], [], []
        
        # VALIDATE: Ensure query is about solid-state AM only
        is_valid, error_msg = validate_ssam_query(prompt)
        if not is_valid:
            return error_msg, None, [], [], []
        
        all_images = []
        extracted_text = ""
        
        # Process PDFs
        if pdf_files:
            for pdf_file in pdf_files:
                pdf_file.seek(0)
                text = extract_pdf_text(pdf_file)
                if text:
                    extracted_text += f"\n\nPDF Content:\n{text[:3000]}"
                
                pdf_file.seek(0)
                pdf_imgs = extract_pdf_images(pdf_file)
                for idx, img in enumerate(pdf_imgs):
                    all_images.append((img, f"PDF Page {idx + 1}: {pdf_file.name}"))
        
        # Add uploaded images
        if images:
            for idx, img in enumerate(images):
                all_images.append((img, f"Uploaded Image {idx + 1}"))
        
        # Build specialized prompt based on mode
        if mode == "microstructure":
            system_prompt = """You are an expert metallurgist specializing EXCLUSIVELY in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD) microstructure analysis.

CRITICAL: You ONLY discuss solid-state additive manufacturing processes. If asked about fusion-based AM, powder bed fusion, FDM, SLA, or any non-solid-state processes, politely decline and redirect to SSAM topics.

Analyze the provided images/content focusing on:
1. Grain structure and morphology in SSAM processes
2. Phase composition in solid-state deposited materials
3. SSAM-specific defects (porosity, cracks, unbonded regions, particle boundaries)
4. Interface characteristics in cold spray, UAM, friction stir processes
5. Particle deformation (for CSAM/cold spray)
6. Bonding quality indicators specific to solid-state bonding

Provide detailed technical analysis with specific observations related to CSAM, UAM, FSAM, or AFSD."""

        elif mode == "process_design":
            system_prompt = """You are a manufacturing process engineer specializing EXCLUSIVELY in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD).

CRITICAL: You ONLY provide guidance on solid-state AM processes. Do not discuss or recommend fusion-based AM, conventional welding, casting, or any non-solid-state manufacturing. If asked, politely redirect to SSAM alternatives.

Analyze the query and provide:
1. Process parameter recommendations for CSAM, UAM, FSAM, or AFSD
2. Material-process compatibility in solid-state processes
3. Expected outcomes and properties from solid-state bonding
4. SSAM-specific challenges and solutions
5. Best practices for solid-state AM
6. Quality control considerations for solid-state deposited materials

Be specific with numerical ranges and practical guidance for solid-state processes only."""

        elif mode == "troubleshooting":
            system_prompt = """You are a solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD) troubleshooting expert EXCLUSIVELY.

CRITICAL: You ONLY troubleshoot solid-state AM issues. Do not provide solutions for fusion-based AM, conventional manufacturing, or other processes. If asked about non-SSAM processes, explain this is outside your expertise and redirect to SSAM topics.

Analyze the problem and provide:
1. Root cause analysis for SSAM-specific issues
2. Diagnostic steps for solid-state processes
3. Corrective actions applicable to CSAM, UAM, FSAM, or AFSD
4. Preventive measures for solid-state AM
5. Process parameter adjustments for solid-state bonding
6. Quality inspection methods for solid-state deposited parts

Focus on practical, actionable solutions for solid-state AM only."""

        elif mode == "comparison":
            system_prompt = """You are an expert in solid-state additive manufacturing processes (CSAM, UAM, FSAM, AFSD) EXCLUSIVELY.

CRITICAL: You ONLY compare solid-state AM processes with each other or discuss solid-state vs fusion-based trade-offs. Do not provide detailed guidance on fusion-based processes. Always frame comparisons from a solid-state perspective.

Compare the requested processes/materials providing:
1. Key differences and similarities between SSAM processes
2. Advantages and disadvantages within solid-state AM context
3. Application suitability for CSAM, UAM, FSAM, AFSD
4. Cost considerations specific to solid-state processes
5. Performance characteristics of solid-state bonding
6. Selection criteria among SSAM processes

Use tables or structured comparisons. If comparing SSAM to non-SSAM, focus on why SSAM is preferred."""

        else:  # general mode
            system_prompt = """You are an expert in solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD) EXCLUSIVELY.

CRITICAL SCOPE LIMITATION: 
- You ONLY discuss solid-state additive manufacturing: Cold Spray (CSAM), Ultrasonic AM (UAM), Friction Stir AM (FSAM), and Additive Friction Stir Deposition (AFSD)
- You do NOT discuss: FDM, SLA, SLS, DMLS, EBM, powder bed fusion, laser melting, binder jetting, or any fusion-based or polymer AM processes
- If asked about non-SSAM topics, politely explain: "This system specializes exclusively in solid-state additive manufacturing. For questions about [other process], please consult resources specific to that technology."

Provide comprehensive, technical analysis covering:
1. Detailed explanations of SSAM concepts and mechanisms
2. Technical parameters specific to solid-state processes
3. Material behavior in solid-state bonding
4. Solid-state process mechanics (kinetic energy, ultrasonic, friction)
5. Applications and best practices for CSAM, UAM, FSAM, AFSD
6. Current research in solid-state additive manufacturing

Be thorough and technically accurate about solid-state AM only."""

        # Add context from conversation history
        context = ""
        if st.session_state.conversation_context:
            recent_context = st.session_state.conversation_context[-3:]
            context = "\n\nRecent conversation context:\n" + "\n".join(recent_context)
        
        prompt_text = f"""{system_prompt}

User Query: {prompt}

{extracted_text}

{context}

MANDATORY INSTRUCTIONS:
- This system is EXCLUSIVELY for solid-state additive manufacturing (CSAM, UAM, FSAM, AFSD)
- If images are provided, analyze them ONLY in the context of solid-state processes
- Include technical terminology specific to solid-state bonding mechanisms
- Provide quantitative information relevant to SSAM processes
- Reference ONLY CSAM, UAM, FSAM, or AFSD processes
- If the query mentions non-solid-state processes, politely explain that this is outside the scope
- DO NOT provide guidance on fusion-based AM, FDM, SLA, SLS, DMLS, EBM, or other non-solid-state processes
- Structure your response clearly with SSAM focus"""

        if all_images:
            prompt_text += f"\n\nAnalyzing {len(all_images)} image(s). Provide detailed visual analysis."
        
        # Build content
        content_parts = [prompt_text]
        for img, _ in all_images:
            content_parts.append(img)
        
        # Generate response
        with st.spinner("Generating expert analysis..."):
            response = st.session_state.model.generate_content(content_parts)
            response_text = response.text
        
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
        
        # Update conversation context
        st.session_state.conversation_context.append(f"Q: {prompt[:200]}")
        st.session_state.conversation_context.append(f"A: {response_text[:200]}")
        if len(st.session_state.conversation_context) > 10:
            st.session_state.conversation_context = st.session_state.conversation_context[-10:]
        
        # Create references (now from uploaded content only)
        references = []
        for idx, (img, source) in enumerate(all_images):
            references.append({
                'type': 'Uploaded Content',
                'title': source,
                'description': 'User-provided material for analysis'
            })
        
        references.append({
            'type': 'AI Knowledge Base',
            'title': 'Gemini 2.0 Flash',
            'description': 'Expert knowledge in solid-state additive manufacturing'
        })
        
        return response_text, all_images, references, entities, relationships
    
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        st.error(error_msg)
        return error_msg, None, [], [], []

def display_references(references):
    """Display formatted references"""
    if not references:
        return
    
    st.markdown('<div class="reference-box">', unsafe_allow_html=True)
    st.markdown("### References & Sources")
    
    for idx, ref in enumerate(references, 1):
        ref_type = ref.get('type', 'Source')
        title = ref.get('title', 'Reference')
        desc = ref.get('description', '')
        
        st.markdown(f"""
        <div style="padding: 0.5rem; margin: 0.5rem 0; background: white; border-radius: 0.4rem; border: 1px solid #e5e7eb;">
            <strong>[{idx}] {ref_type}:</strong> {title}<br>
            <small>{desc}</small>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def display_message(message, is_user=False):
    """Display chat message with enhanced formatting"""
    css_class = "user-message" if is_user else "assistant-message"
    role = "You" if is_user else "AI Expert"
    
    with st.container():
        st.markdown(f'<div class="chat-message {css_class}">', unsafe_allow_html=True)
        st.markdown(f"**{role}** • {message['timestamp']}")
        
        if is_user and message.get('files'):
            st.markdown("**Attached Files:**")
            cols = st.columns(min(len(message['files']), 4))
            for idx, f in enumerate(message['files']):
                with cols[idx % 4]:
                    if f.get('data'):
                        st.image(f['data'], caption=f['name'], use_column_width=True)
                    else:
                        st.markdown(f"📄 {f['name']}")
        
        st.markdown(message['content'])
        
        if not is_user and message.get('response_images'):
            st.markdown("---")
            st.markdown("**Analyzed Images:**")
            cols = st.columns(min(len(message['response_images']), 3))
            for idx, (img, label) in enumerate(message['response_images']):
                with cols[idx % 3]:
                    st.image(img, caption=label, use_column_width=True)
        
        if not is_user and message.get('references'):
            display_references(message['references'])
        
        if not is_user and message.get('entities') and len(message['entities']) > 1:
            with st.expander("Knowledge Graph", expanded=False):
                fig = create_knowledge_graph(message['entities'], message.get('relationships', []))
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    """Main application"""
    
    # Sidebar
    with st.sidebar:
        st.title("Configuration")
        
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
                    st.success("API Configured!")
            else:
                st.error("Please enter an API key")
        
        st.markdown("---")
        
        # Analysis Mode Selection
        st.markdown("### Analysis Mode")
        analysis_mode = st.selectbox(
            "Select mode",
            ["General", "Microstructure Analysis", "Process Design", "Troubleshooting", "Comparison"],
            key="analysis_mode"
        )
        
        mode_map = {
            "General": "general",
            "Microstructure Analysis": "microstructure",
            "Process Design": "process_design",
            "Troubleshooting": "troubleshooting",
            "Comparison": "comparison"
        }
        
        st.session_state.current_mode = mode_map[analysis_mode]
        
        st.markdown("---")
        
        # Stats
        st.markdown("### Session Stats")
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
        
        # Quick Access Tools
        st.markdown("### Quick Access")
        
        if st.button("Process Database", use_container_width=True):
            st.session_state.show_process_db = True
        
        if st.button("Material Properties", use_container_width=True):
            st.session_state.show_material_db = True
        
        if st.button("Process Comparison", use_container_width=True):
            st.session_state.show_comparison = True
        
        st.markdown("---")
        
        # Example queries
        st.markdown("### Example Queries")
        examples = {
            "Microstructure": "Analyze this microstructure for bonding quality",
            "Parameters": "What are optimal CSAM parameters for aluminum?",
            "Troubleshooting": "How to reduce porosity in CSAM coatings?",
            "Comparison": "Compare CSAM vs UAM for copper deposition"
        }
        
        for category, example in examples.items():
            if st.button(f"{example[:30]}...", use_container_width=True, key=f"ex_{category}"):
                st.session_state.example_query = example
        
        st.markdown("---")
        
        # Global knowledge graph
        if len(st.session_state.knowledge_graph) > 1:
            if st.button("View Global Knowledge Graph", use_container_width=True):
                st.session_state.show_global_graph = True
        
        st.markdown("---")
        
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.knowledge_graph = defaultdict(list)
            st.session_state.conversation_context = []
            st.rerun()
        
        st.markdown("---")
        st.caption("SSAM AI Pro • Solid-State AM Exclusively")
        st.caption("⚠ CSAM • UAM • FSAM • AFSD Only")
    
    # Main content
    st.title("SolidAdditive AI Pro")
    st.markdown("""
    <div style='background: rgba(255, 255, 255, 0.1); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;'>
        <p style='color: white; margin: 0;'>
            <b>Specialized AI for Solid-State Additive Manufacturing ONLY</b><br>
            <span style='color: #fbbf24;'>⚠ CSAM • UAM • FSAM • AFSD EXCLUSIVELY</span><br>
            <small>This system does NOT cover fusion-based AM (SLS, DMLS, EBM, FDM, SLA, etc.)</small>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.api_key:
        st.warning("Please configure your Gemini API key in the sidebar to get started.")
        st.info("Get your API key from: https://makersuite.google.com/app/apikey")
        return
    
    # Show process database if requested
    if st.session_state.get('show_process_db', False):
        st.markdown("### Solid-State AM Process Database")
        
        process_tabs = st.tabs(list(SSAM_PROCESSES.keys()))
        
        for idx, (process_key, process_data) in enumerate(SSAM_PROCESSES.items()):
            with process_tabs[idx]:
                st.markdown(f"**{process_data['name']}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Temperature Range:** {process_data['temperature_range']}")
                    st.markdown(f"**Bonding Mechanism:** {process_data['bonding_mechanism']}")
                    st.markdown(f"**Materials:** {', '.join(process_data['typical_materials'])}")
                
                with col2:
                    st.markdown("**Advantages:**")
                    for adv in process_data['advantages']:
                        st.markdown(f"- {adv}")
                
                st.markdown("**Limitations:**")
                for lim in process_data['limitations']:
                    st.markdown(f"- {lim}")
                
                # Show parameter table
                param_df = create_parameter_table(process_key)
                if param_df is not None:
                    st.markdown("**Typical Parameters:**")
                    st.dataframe(param_df, use_container_width=True)
        
        if st.button("Close Database"):
            st.session_state.show_process_db = False
            st.rerun()
    
    # Show material database if requested
    if st.session_state.get('show_material_db', False):
        st.markdown("### Material Properties Database")
        
        material_tabs = st.tabs(list(MATERIAL_DATABASE.keys()))
        
        for idx, (material, props) in enumerate(MATERIAL_DATABASE.items()):
            with material_tabs[idx]:
                st.markdown(f"**{material}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Density:** {props['density']}")
                    st.markdown(f"**Melting Point:** {props['melting_point']}")
                    st.markdown(f"**Thermal Conductivity:** {props['thermal_conductivity']}")
                
                with col2:
                    st.markdown(f"**Yield Strength:** {props['yield_strength']}")
                    st.markdown(f"**SSAM Compatibility:** {', '.join(props['ssam_compatibility'])}")
                
                st.markdown(f"**Applications:** {props['common_applications']}")
        
        if st.button("Close Material Database"):
            st.session_state.show_material_db = False
            st.rerun()
    
    # Show process comparison if requested
    if st.session_state.get('show_comparison', False):
        st.markdown("### Process Comparison Tool")
        
        selected_processes = st.multiselect(
            "Select processes to compare",
            list(SSAM_PROCESSES.keys()),
            default=list(SSAM_PROCESSES.keys())[:2]
        )
        
        if len(selected_processes) >= 2:
            fig = create_process_comparison_chart(selected_processes)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Detailed comparison table
            st.markdown("**Detailed Comparison:**")
            
            comparison_data = {
                'Aspect': ['Temperature Range', 'Bonding Mechanism', 'Typical Materials', 'Main Advantages', 'Main Limitations']
            }
            
            for process in selected_processes:
                if process in SSAM_PROCESSES:
                    p = SSAM_PROCESSES[process]
                    comparison_data[process] = [
                        p['temperature_range'],
                        p['bonding_mechanism'],
                        ', '.join(p['typical_materials'][:3]),
                        ', '.join(p['advantages'][:2]),
                        ', '.join(p['limitations'][:2])
                    ]
            
            comp_df = pd.DataFrame(comparison_data)
            st.dataframe(comp_df, use_container_width=True)
        
        if st.button("Close Comparison"):
            st.session_state.show_comparison = False
            st.rerun()
    
    # Show global knowledge graph if requested
    if st.session_state.get('show_global_graph', False):
        st.markdown('<div class="knowledge-graph-container">', unsafe_allow_html=True)
        st.markdown("### Global Knowledge Graph")
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
    with st.expander("Upload Files (Images or PDFs)", expanded=False):
        uploaded_files = st.file_uploader(
            "Upload images of microstructures, processes, or technical PDFs",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff', 'pdf'],
            accept_multiple_files=True,
            help="Upload images for analysis or PDFs for text extraction"
        )
    
    # Chat input
    user_input = st.chat_input(f"Ask about solid-state AM ({analysis_mode} mode)...")
    
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
        current_mode = st.session_state.get('current_mode', 'general')
        with st.spinner(f"Analyzing in {analysis_mode} mode..."):
            ai_response, response_images, references, entities, relationships = get_gemini_response(
                user_input,
                images=images,
                pdf_files=pdf_files,
                mode=current_mode
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
