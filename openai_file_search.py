from openai import OpenAI
import pandas as pd
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize the OpenAI client
client = OpenAI()

# Function to clean up files and vector storage
def cleanup(file_paths, vector_store_id=None):
    # Delete temporary files
    for path in file_paths:
        if os.path.exists(path):
            os.remove(path)

    # Delete vector store if provided
    if vector_store_id:
        try:
            client.beta.vector_stores.delete(vector_store_id)
        except Exception as e:
            print(f"Error deleting vector store: {e}")

# Function to upload files and handle retries for failed attachments
def upload_files_with_retries(vector_store_id, file_paths, max_retries=3):
    uploaded_files = set()
    failed_files = file_paths.copy()

    for attempt in range(max_retries):
        if not failed_files:
            break

        print(f"Attempt {attempt + 1} to upload {len(failed_files)} files.")
        file_streams = [open(path, "rb") for path in failed_files]

        try:
            file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id, files=file_streams
            )

            # Check the status of the batch
            if file_batch.status == "completed":
                print(f"Batch upload completed successfully.")
                uploaded_files.update(failed_files)
                failed_files.clear()
            else:
                print(f"Batch upload failed. Status: {file_batch.status}")
                # Retry failed files
                failed_files = [path for path in failed_files if path not in uploaded_files]

        except Exception as e:
            print(f"Error uploading batch: {e}")
            # Retry failed files
            failed_files = [path for path in failed_files if path not in uploaded_files]

        finally:
            # Close all file streams
            for stream in file_streams:
                stream.close()

    return uploaded_files, failed_files

# Function to re-attach failed files to the vector store
def reattach_failed_files(vector_store_id):
    try:
        # List files with status 'failed'
        failed_files = client.beta.vector_stores.files.list(
            vector_store_id=vector_store_id,
            filter="failed"
        )

        print(f"Found {len(failed_files.data)} files with status 'failed'.")

        # Re-attach these files to the vector store
        for file in failed_files.data:
            try:
                client.beta.vector_stores.files.create_and_poll(
                    vector_store_id=vector_store_id,
                    file_id=file.id
                )
                print(f"Re-attached file {file.id} to the vector store.")
            except Exception as e:
                print(f"Error re-attaching file {file.id}: {e}")

    except Exception as e:
        print(f"Error listing vector store files: {e}")

# Step 1: Check if the Assistant already exists
assistant_name = "Subsidy Finder Assistant"
assistant = None
try:
    assistants = client.beta.assistants.list()
    for existing_assistant in assistants.data:
        if existing_assistant.name == assistant_name:
            assistant = existing_assistant
            print(f"Assistant '{assistant_name}' already exists. Using existing assistant.")
            break
except Exception as e:
    print(f"Error listing assistants: {e}")

# If the assistant doesn't exist, create it
if not assistant:
    try:
        assistant = client.beta.assistants.create(
            name=assistant_name,
            instructions="Du bist ein Experte für die Suche nach Fördermitteln für deutsche Unternehmen. Deine "
                         "Aufgabe ist es, Unternehmen dabei zu helfen, die passenden Fördermittel zu finden, "
                         "die auf ihre spezifischen Bedürfnisse zugeschnitten sind. Beginne damit, dem Benutzer "
                         "relevante Fragen zu stellen, um ein detailliertes Profil des Unternehmens zu erstellen. "
                         "Frage nach: Standort des Unternehmens (Bundesland, Stadt), Branche oder Tätigkeitsbereich, "
                         "Unternehmensgröße (z.B. Anzahl der Mitarbeiter), Art der Förderung, die gesucht wird (z.B. "
                         "Existenzgründung, Forschung und Entwicklung, Umweltschutz), und sonstige relevante "
                         "Informationen (z.B. spezifische Projekte oder Ziele). Nutze die bereitgestellten Daten, "
                         "um relevante Fördermittel zu finden, die auf das Profil des Unternehmens zugeschnitten "
                         "sind. Sei präzise und klar in deinen Antworten. Wenn du unsicher bist, gib an, "
                         "dass du keine passenden Fördermittel gefunden hast, und schlage vor, weitere Informationen "
                         "bereitzustellen. Halte die Antworten kurz und auf den Punkt, aber stelle sicher, "
                         "dass alle relevanten Details enthalten sind.",
            model="gpt-4o",
            tools=[{"type": "file_search"}],
        )
        print(f"Assistant '{assistant_name}' created.")
    except Exception as e:
        print(f"Error creating assistant: {e}")
        exit(1)

# Step 2: Use an existing vector store ID or create a new one
vector_store_id = "vs_kzZBgGUh5OQnH4mCUqqYPnWV"  # Set this to an existing vector store ID if available
vector_store = None

if vector_store_id:
    try:
        vector_store = client.beta.vector_stores.retrieve(vector_store_id)
        print(f"Using existing vector store: {vector_store.name} (ID: {vector_store.id})")
    except Exception as e:
        print(f"Error retrieving vector store: {e}")
        vector_store = None

if not vector_store:
    try:
        vector_store = client.beta.vector_stores.create(name="Subsidy Data")
        print("New vector store created.")
    except Exception as e:
        print(f"Error creating vector store: {e}")
        exit(1)

# Step 3: Re-attach failed files to the vector store
if vector_store:
    reattach_failed_files(vector_store.id)

# Step 4: Upload files and add them to the Vector Store
file_paths = []
try:
    # Load the CSV file
    df = pd.read_csv("foerderungen_list.csv")

    # Check for existing temporary files
    temp_files = [f for f in os.listdir() if f.startswith("temp_") and f.endswith(".json")]
    if temp_files:
        print(f"Found {len(temp_files)} existing temporary files. Skipping file creation.")
        file_paths = temp_files
    else:
        # Convert each row in the CSV to a JSON file
        for index, row in df.iterrows():
            # Convert the row to a JSON string
            row_json = row.to_json()

            # Save the JSON string to a temporary file
            file_path = f"temp_{index}.json"
            with open(file_path, "w") as f:
                f.write(row_json)

            # Add the file path to the list
            file_paths.append(file_path)
        print(f"Created {len(file_paths)} temporary files.")

    # List all files already uploaded to OpenAI with purpose "assistants"
    uploaded_files = client.files.list(purpose="assistants")
    uploaded_filenames = {file.filename for file in uploaded_files.data}
    print(f"Found {len(uploaded_filenames)} files already uploaded to OpenAI.")

    # Filter out files that have already been uploaded
    files_to_upload = [path for path in file_paths if os.path.basename(path) not in uploaded_filenames]
    print(f"{len(files_to_upload)} files need to be uploaded.")

    # Step 4.1: Upload new files with retries for failed attachments
    if files_to_upload:
        uploaded_files, failed_files = upload_files_with_retries(vector_store.id, files_to_upload)

        if failed_files:
            print(f"Failed to upload the following files after retries: {failed_files}")
        else:
            print("All new files uploaded successfully.")

    # Step 5: Update the Assistant to use the Vector Store
    assistant = client.beta.assistants.update(
        assistant_id=assistant.id,
        tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
    )
    print("Assistant updated with vector store.")

    # Step 6: Create a Thread and add a message
    thread = client.beta.threads.create()

    # Example user query
    user_query = "I am a small business in North Rhine-Westphalia. What subsidies are available for me?"
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_query,
    )
    print("Thread created and user query added.")

    # Step 7: Run the Assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )
    print("Assistant run started.")

    # Wait for the run to complete and retrieve the response
    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=thread.id, run_id=run.id
        )
        if run_status.status == "completed":
            break
        time.sleep(1)

    # Retrieve the assistant's response
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for message in messages.data:
        if message.role == "assistant":
            print("Assistant's response:")
            print(message.content[0].text.value)

except Exception as e:
    print(f"An error occurred: {e}")
    # Clean up files and vector storage in case of error
    cleanup(file_paths, vector_store.id if vector_store else None)
    exit(1)

# Clean up temporary files after successful execution
cleanup(file_paths)
print("Temporary files cleaned up.")