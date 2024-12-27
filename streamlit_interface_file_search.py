import streamlit as st
from openai import OpenAI, AssistantEventHandler


# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
# client = OpenAI(api_key="")

# Assistant ID (replace with your actual assistant ID)
ASSISTANT_ID = "asst_lE6BsWFlL6eTucXxdBj48Za6"

# Title
st.title("💬 Fördermittel-Assistent für deutsche Unternehmen")

# Initialize session state for chat history, company profile, and thread
if "messages" not in st.session_state:
    st.session_state.messages = []
if "company_profile" not in st.session_state:
    st.session_state.company_profile = {}
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

# Company profile form
st.header("Unternehmensprofil")
with st.form("company_profile_form"):
    st.write("Bitte geben Sie die folgenden Informationen an:")
    location = st.text_input("Standort (Bundesland, Stadt)", key="location")
    industry = st.text_input("Branche oder Tätigkeitsbereich", key="industry")
    employees = st.number_input("Anzahl der Mitarbeiter", min_value=1, key="employees")
    funding_type = st.selectbox(
        "Art der Förderung",
        ["Existenzgründung", "Forschung und Entwicklung", "Umweltschutz", "Digitalisierung", "Andere"],
        key="funding_type"
    )
    additional_info = st.text_area("Sonstige relevante Informationen (z.B. Projekte, Ziele, Investitionen)", key="additional_info")

    # Submit button for company profile
    if st.form_submit_button("Profil speichern"):
        st.session_state.company_profile = {
            "location": location,
            "industry": industry,
            "employees": employees,
            "funding_type": funding_type,
            "additional_info": additional_info
        }
        st.success("Unternehmensprofil erfolgreich gespeichert!")

        # Send the company profile to the assistant as the first message
        if st.session_state.company_profile:
            profile_message = (
                f"Hier ist das Unternehmensprofil:\n"
                f"Standort: {st.session_state.company_profile['location']}\n"
                f"Branche: {st.session_state.company_profile['industry']}\n"
                f"Mitarbeiter: {st.session_state.company_profile['employees']}\n"
                f"Förderart: {st.session_state.company_profile['funding_type']}\n"
                f"Sonstige Informationen: {st.session_state.company_profile['additional_info']}\n"
                "Bitte finden Sie passende Fördermittel für dieses Unternehmen."
            )

            # Create a new thread if one doesn't exist
            if not st.session_state.thread_id:
                thread = client.beta.threads.create()
                st.session_state.thread_id = thread.id

            # Add the profile message to the thread
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=profile_message
            )

            # Run the assistant
            run = client.beta.threads.runs.create(
                thread_id=st.session_state.thread_id,
                assistant_id=ASSISTANT_ID
            )

            # Wait for the assistant's response
            while run.status != "completed":
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )

            # Retrieve the assistant's messages
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )

            # Add the assistant's response to chat history
            assistant_response = messages.data[0].content[0].text.value
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})

# Chat interface
st.header("Chat mit dem Fördermittel-Assistenten")

# Display chat history
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# User input
if prompt := st.chat_input("Stellen Sie eine Frage oder geben Sie weitere Informationen an:"):
    # Add user input to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # Add the user's message to the thread
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # Define an event handler for streaming
    class EventHandler(AssistantEventHandler):
        def __init__(self):
            super().__init__()
            self.full_response = ""
            self.response_container = st.empty()

        def on_text_created(self, text) -> None:
            self.full_response = ""
            self.response_container = st.empty()

        def on_text_delta(self, delta, snapshot):
            self.full_response += delta.value
            self.response_container.markdown(self.full_response)

        def on_end(self):
            st.session_state.messages.append({"role": "assistant", "content": self.full_response})

    # Run the assistant with streaming
    with client.beta.threads.runs.stream(
        thread_id=st.session_state.thread_id,
        assistant_id=ASSISTANT_ID,
        event_handler=EventHandler(),
    ) as stream:
        stream.until_done()