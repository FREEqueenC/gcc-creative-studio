import sys
import os

# Add backend folder to sys.path so we can import src
sys.path.append(r"C:\Users\Ashle\Documents\GitHub\gcc-creative-studio\backend")

# Configure environment variables to simulate running inside backend
os.environ["ENVIRONMENT"] = "local"
os.environ["PROJECT_ID"] = "gentle-scene-485705-n4"
os.environ["GOOGLE_CLOUD_PROJECT"] = "gentle-scene-485705-n4"
os.environ["LOCATION"] = "us-central1"

from src.common.schema.genai_model_setup import GenAIModelSetup
from google.genai import types

def probe_models():
    print("Initializing GenAI Client...")
    client = GenAIModelSetup.get_client()
    
    candidates = [
        "gemini-2.5-flash-image",
    ]
    
    prompt = "A golden spiral."
    
    print("Probing simplified gemini-2.5-flash-image via client.models.generate_content...")
    for model_id in candidates:
        print(f"\n--- Testing model: {model_id} ---")
        try:
            parts = [types.Part.from_text(text=prompt)]
            contents = [types.Content(role="user", parts=parts)]
            
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
            )
            
            response = client.models.generate_content(
                model=model_id,
                contents=contents,
                config=generate_content_config,
            )
            print(f"SUCCESS! {model_id} worked via generate_content.")
            found_image = False
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.inline_data:
                            print(f"Found inline_data mime_type: {part.inline_data.mime_type}, bytes length: {len(part.inline_data.data)}")
                            found_image = True
            if not found_image:
                print("No image part found in response. Text content:", response.text)
        except Exception as e:
            print(f"FAILED for {model_id}: {e}")

if __name__ == "__main__":
    probe_models()
