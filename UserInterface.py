from openai import OpenAI
import streamlit as st
from PIL import Image
from qdrant_client import QdrantClient, models

# need to install openai dotenv streamlit

qdrant_client = QdrantClient(
    url="your_qdrant_server_url", 
    api_key="your_api_key",
)

#images
logoHult = Image.open("images/headLogoAparavi.png")
st.image(logoHult)



BOT_AVATAR = "images/aparaviLogoIcon.jpg"  
st.markdown("<h1 style='text-align: center;'>Aparavi Customer Support Agent</h1>", unsafe_allow_html=True) 

# initialize the retriever and the embedding model
OPENAI_API_KEY = "your-openai-api-key"
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize session state variables
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o"

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
        if st.session_state["password"] == "ask-aparavi-ai":
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
            collection_name="AparaviChatbot", query_vector=queryVectors, limit=5
        )

        # augment the prompt
        augmentedPrompt = f"""
            You are an AI assistant for Custoer Support at Aparavi (For people using the Aparavi software Platform). A user has asked the following question: "{prompt}".

            Your task is to:
            1. Perform a semantic search on the user's query.
            2. Only return context from the search if the cosine similarity of the result is less than 0.5.
            3. Provide a clear and concise response to the user, and ensure that your response includes only relevant and helpful information. Each query likely leads to one of the articles in the knowledge base for which you will find the https links in the context provided. Hand those links to the user for further reading.
            4. Always include a clickable link to the specific article from the Aparavi Support Knowledge base that is dealing with the requested topic. Ensure the link starts with "http" and if it reads an  /n  ignore that sign and terminate the lonk before.
            5. If a users reuqests information about content/topic that yoou don't have knowledge about (all similiariy distance greater than 0.5). Say so, openly and refer him to contact Tech support via the link and file a ticvket via the ticket link.
            
            For example:
            - If you retrieve a document with a cosine similarity above 0.5, ignore it.
            - If you retrieve multiple relevant results, choose the most relevant 1-3 results and integrate the information into your response.

            The format of your response should be:
            - Provide useful context that answers the user's question.
            - If the user asks you to support them in creating a ticket, answer them with the following the form that is provided on the website: "Which Team is your query for?" -> Hult Technology, "Service Category" -> (You have to decide beased on the user input and context),
              "subject" -> (Define a good title based on the user input and contxt), "Description: Please add as much information as possible" -> (Write a description for the user)
            then send them to this link: https://aparavi-software.helpscoutdocs.com/
            
            If there are no relevant search results, provide a helpful general response or ask a follow-up question to clarify what the user is looking for.

            and here is some details I have retrieved through semantic search in the local database. Please use it to augment your answer and be more precise: 
            
            Use this information to build your answer, dont copy paste it: 
            {semanticResponse}
            Again, ignore any content with a cosine distance of more than 0.5

            Please list always the data link that is whin the context. It should be a starting with "http" and when it has a /n or more in there replace those with spaces (that means that the link finishes there!) Please alsways provide the link so users can click it to get to the resource. 
            
            Don't put the same link twice in a response!
            
            If the user is not asking for any specific information, you shall always provide him with the link to all other articles on the Aparavi Support Page: https://aparavi-software.helpscoutdocs.com/
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
