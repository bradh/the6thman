import os
import uuid
import base64
import mimetypes
import requests
from datetime import datetime

supportedMimeTypes = [
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif'
]


def getMimeType(fileName):
    return mimetypes.guess_type(fileName)[0]


def isSupportedMimeType(mimeType):
    return mimeType in supportedMimeTypes


def extractWithAiOcr(buffer, originalMimeType):
    fileSignature = buffer[:5].decode(errors='ignore')

    workingBuffer = buffer
    mimeType = originalMimeType

    print(f"🖼️ Detected file (sig: {fileSignature})")
    mimeType = originalMimeType or 'image/png'

    base64Image = base64.b64encode(workingBuffer).decode('utf-8')

    payload = {
        "model": "gemma3:27b",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
                        You are a visual analysis model focused on situational awareness.

                        Your tasks are to analyze the image and answer the following questions as simply and objectively as possible. 
                        Return a **single raw JSON object** with these exact keys:

                        {
                          "peopleCount": <integer>,
                          "hostiles": true/false,
                          "weaponsDetected": true/false,
                          "Hazards": true/false,
                          "rubble": true/false
                        }

                        Definitions:
                        - peopleCount: Number of distinct HUMAN people visible (ignore mannequins, posters, photos, statues).
                        - weaponsDetected: true if any weapons (guns, knives, explosives, etc.) are visible; false otherwise.
                        - hostiles: assume true if weapons present; false otherwise
                        - Hazards: true if hazards like fire, smoke, chemical spill, collapsed structures, or flood are visible.
                        - rubble: true if debris/rubble from destruction (collapsed walls, broken concrete, wreckage) is visible.

                        Rules:
                        - Always output ALL five keys.
                        - Use boolean true/false (lowercase).
                        - If unsure, lean towards false, except peopleCount which should be your best estimate.
                        - Output must be **only the JSON object** with no commentary, explanation, or formatting.
                        """.strip()
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mimeType};base64,{base64Image}"
                        }
                    }
                ]
            }
        ]
    }
    # payload = {
    #     "model": "gemma3:27b",
    #     "messages": [
    #         {
    #             "role": "user",
    #             "content": [
    #                 {
    #                     "type": "text",
    #                     "text": """
    #                     You are a visual analysis model focused on situational awareness.
    #
    #                     Task:
    #                     Count how many distinct HUMAN PEOPLE are present in the image and return ONLY a raw JSON object.
    #
    #                     Rules:
    #                     - Count real people only (ignore posters, statues, photos on screens, mannequins, drawings).
    #                     - Include partially visible people (e.g., only a head/arm visible) if you’re confident they’re human.
    #                     - If the scene is too ambiguous to be sure, return your best estimate as an integer.
    #                     - If there are no people, return 0.
    #                     - Output must be a pure JSON object with no commentary or markdown.
    #
    #                     Output JSON schema (exact keys):
    #                     {
    #                       "peopleCount": <integer>
    #                     }
    #                     """.strip()
    #                 },
    #                 {
    #                     "type": "image_url",
    #                     "image_url": {
    #                         "url": f"data:{mimeType};base64,{base64Image}"
    #                     }
    #                 }
    #             ]
    #         }
    #     ]
    # }

    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/json',
        'User-Agent': 'tp-ai-ocr-service',
        'Authorization': 'Bearer token-abc123'
    }

    response = requests.post(
        'http://10.1.1.198:11434/v1/chat/completions',
        json=payload,
        headers=headers
    )

    content = response.json()['choices'][0]['message']['content']

    return content


def handleImageRecognitionUpload(fileBuffer, fileName):
    mimeType = getMimeType(fileName)
    print(f"MIME Type: {mimeType}")

    if not isSupportedMimeType(mimeType):
        raise ValueError(f"Unsupported file type: {mimeType}")

    return extractWithAiOcr(fileBuffer, mimeType)


def main():
    images_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../files/images'))

    if not os.path.exists(images_dir):
        print(f"⚠️  Directory not found: {images_dir}")
        return

    print(f"📂 Scanning directory: {images_dir}")

    for file_name in os.listdir(images_dir):
        file_path = os.path.join(images_dir, file_name)

        if not os.path.isfile(file_path):
            continue

        mime_type = getMimeType(file_name)
        if not isSupportedMimeType(mime_type):
            print(f"⛔ Skipping unsupported file: {file_name} (MIME: {mime_type})")
            continue

        try:
            with open(file_path, 'rb') as f:
                file_buffer = f.read()

            print(f"\n📨 Sending {file_name} to The 6th Man for Analysis...")
            result = handleImageRecognitionUpload(file_buffer, file_name)
            print(f"Situational analysis for {file_name}:\n{result}\n")

        except Exception as e:
            print(f"💥 Failed to process {file_name}: {str(e)}")


if __name__ == "__main__":
    main()
