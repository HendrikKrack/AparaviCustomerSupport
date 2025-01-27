from openai import OpenAI
import streamlit as st
from PIL import Image
from qdrant_client import QdrantClient, models
import os
from dotenv import load_dotenv

# Load environment variables
root_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(root_dir, '.env')
load_dotenv(env_path)

# Initialize Qdrant client with environment variables
qdrant_client = QdrantClient(
    url=os.getenv('QDRANT_URL'),
    api_key=os.getenv('QDRANT_API_KEY'),
)

#images
image_dir = os.path.join(root_dir, 'images')
logoAparavi = Image.open(os.path.join(image_dir, "headLogoAparavi.png"))
st.image(logoAparavi)

BOT_AVATAR = os.path.join(image_dir, "aparaviLogoIcon.jpg")  
st.markdown("<h1 style='text-align: center;'>Aparavi Customer Support Agent</h1>", unsafe_allow_html=True) 

# initialize the retriever and the embedding model
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize session state variables
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4"

if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize the sidebar
with st.sidebar:
    st.write("If you were able to resolve an issue and wish to continue with another topic, you should...")

    # Button to clear current chat
    if st.button("Clear Chat"):
        st.session_state.messages = []

# Password protection
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == os.getenv('WEBSITE_PASSWORD'):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password
        else:
            st.session_state["password_correct"] = False
            st.error("😕 Password incorrect. Please try again.")

    # First run, show input for password
    st.text_input(
        "Please enter the password to access the Aparavi Support Agent", 
        type="password", 
        on_change=password_entered, 
        key="password"
    )

    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        
    return st.session_state["password_correct"]

# Only show the main content if the password is correct
if check_password():
    # Display chat messages
    for message in st.session_state.messages:
        avatar = "👩‍💻" if message["role"] == "user" else BOT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # Main chat interface
    if prompt := st.chat_input("Hi there! I am your virtual Aparavi assistant. How can I help?"):
        
        # Get the vectors    
        response = client.embeddings.create(
            input=prompt,
            model="text-embedding-3-small"
        )

        queryVectors = response.data[0].embedding

        # perform semantic search 
        semanticResponse = qdrant_client.search(
            collection_name=os.getenv('COLLECTION_NAME'), 
            query_vector=queryVectors, 
            limit=5
        )

        # augment the prompt
        augmentedPrompt = f"""
            You are an AI assistant for Customer Support at Aparavi, specifically helping users of the Aparavi Software Platform. A user has asked: "{prompt}"

            GUIDELINES FOR RESPONSE:
            1. CONTEXT FILTERING:
               - Only use search results with cosine similarity LESS than 0.5
               - For multiple relevant results, use only the top 1-3 most relevant ones
               - Ignore any results with similarity score > 0.5

            2. RESPONSE STRUCTURE:
               a) Start with a clear, direct answer to the user's question
               b) Include specific examples or steps when applicable
               c) Always provide relevant documentation links (starting with "http")
                  - Remove any '/n' or newlines from links
                  - Each unique link should appear only once
                  - Format links as clickable markdown: [Description](URL)
                  - Provide the link to the PDF and also to the website on the aparavi academy with a hint on the respective video tutorial

            3. Contact SUPPORT:
               If the user needs additional support, provide this structure:
               - Team: Aparavi Technology
               - Service Category: [Select based on context]
               - Subject: [Create clear, specific title]
               - Description: [Detailed problem description]
               Then direct them to: https://www.aparavi.com/contact-us or https://www.aparavi.com/de/kontakt for a german or european custmer

            4. HANDLING LIMITED KNOWLEDGE:
               If no relevant information is found (all similarity scores > 0.5):
               a) Acknowledge the limitation
               b) Ask specific follow-up questions
               c) Suggest getting in contact
               d) Provide the general documentation link: https://aparavi-academy.eu/en

            CONTEXT FROM SEMANTIC SEARCH:
            Use this information to enhance your response (remember to ignore results with similarity > 0.5):
            {semanticResponse}

            ADDITIONAL INSTRUCTIONS:
            - Be concise but thorough
            - Use bullet points for lists or steps
            - Format code snippets in markdown blocks
            - Maintain a professional, helpful tone
            - If the query isn't specific, include the main documentation link
            """
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display the user's message in the chat interface
        with st.chat_message("user", avatar="👩‍💻"):
            st.markdown(prompt)

        # Generate the response using the augmented prompt and chat history
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=st.session_state["messages"] + [{"role": "system", "content": augmentedPrompt}],
                stream=True,
            ):
                full_response += response.choices[0].delta.content or ""
                message_placeholder.markdown(full_response + "|")
            message_placeholder.markdown(full_response)
        
        # Append the assistant's response to the chat history
        st.session_state.messages.append({"role": "assistant", "content": full_response})
